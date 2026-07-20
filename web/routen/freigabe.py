"""Route fuer "Prüfen & Freigeben" (Task 5) - die sicherheitskritischste
Seite des Interfaces: Liste der Auftraege, die auf eine Person warten,
Lese-/Freigabe-Ansicht mit der eingefrorenen Checklisten-Geste (drei Haken,
siehe docs/design/Poleposition-v4.dc.html, checkTexte) und Ablehnen.

Fuer den eigentlichen Versand wird bewusst NICHT neu geschrieben, was die
CLI schon kann: pipeline.__main__._versand_ausfuehren traegt den
Test-Empfaenger-Gate (nie an zwei Stellen pflegen!) und die
versand/versand_komplett-Idempotenz. Instantly ist ueber
request.app.state.instantly fakebar - gleiches Muster wie
request.app.state.ki in web.routen.kunden fuer die KI."""
from __future__ import annotations

import json
import os
import threading
from datetime import datetime
from pathlib import Path

import requests
from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse

from pipeline.__main__ import SendenFehler, _versand_ausfuehren
from pipeline.approval import approve, freigabe_info, is_approved
from pipeline.run_store import RunStore
from web import auth
from web.laufmanager import Laufmanager, _lade_json_sicher
from web.nav import nav_kontext
from web.wartende import kunde_fuer as _kunde_fuer, wartende_laeufe

router = APIRouter()

# Woertlich aus docs/design/Poleposition-v4.dc.html (checkTexte) - die drei
# Punkte der Freigabe-Checkliste, eingefroren als Freigabe-Geste.
CHECKLISTE_TEXTE = [
    "Ich habe die Anschreiben und Nachfass-Mails gelesen",
    "Ich habe die aussortierten Texte und ihre Gründe gesehen",
    "Absender, gesperrte Domains und Test-Adressen stimmen",
]

CHECKLISTE_FEHLER = "Bitte alle drei Punkte abhaken, bevor du freigibst."
BEGRUENDUNG_FEHLER = "Bitte kurz begründen, was nicht gepasst hat."

KUNDE_DATEI_FEHLER = ("Die Kunden-Datei zu diesem Auftrag ist gerade nicht lesbar oder "
                      "beschädigt. Bitte im Kunden-Bereich prüfen.")

# Review-Fund (Task 5): POST /freigeben und POST /ablehnen duerfen nur im
# jeweils dafuer vorgesehenen Zustand etwas tun - sonst koennte z.B. ein
# abgelehnter Auftrag trotzdem noch freigegeben und versendet werden
# (waehrend die Ablehnen-Ansicht "Nichts wurde versendet" verspricht), oder
# ein laengst uebergebener Auftrag im Nachhinein "abgelehnt" werden.
# "freigegeben" ist bei FREIGEBEN bewusst mit erlaubt (nicht bei ABLEHNEN):
# das ist der Fall "schon freigegeben, Versand aber noch nicht durch" - dafuer
# gibt es die eigene, praezisere Meldung in freigabe_absenden() (is_approved).
ZUSTAND_ERLAUBT_FREIGEBEN = {"wartet_auf_freigabe", "freigegeben"}
ZUSTAND_ERLAUBT_ABLEHNEN = {"wartet_auf_freigabe"}

_ZUSTAND_TEXT = {
    "abgelehnt": "wurde bereits abgelehnt",
    "uebergeben": "ist bereits an Instantly übergeben",
    "laeuft": "wird gerade noch bearbeitet",
    "angehalten": "ist noch nicht bereit dafür",
}


def _zustand_fehler(aktion: str, zustand: str) -> str:
    grund = _ZUSTAND_TEXT.get(zustand, f"ist gerade nicht bereit dafür (Zustand: {zustand})")
    return f"Dieser Auftrag {grund} — {aktion} ist jetzt nicht mehr möglich. Lade die Seite neu."


# E-Fix 6 (Doppelklick-Schutz): EIN threading.Lock JE Laufordner, in einem
# module-level Dict gehalten - schuetzt _versand_ausfuehren gegen einen
# Doppelklick-/Retry-Race auf "Freigeben"/"Erneut senden": FastAPI fuehrt
# diese synchronen Routen in einem Threadpool aus (siehe Kommentare an den
# Routen unten), zwei fast gleichzeitige POSTs koennten sonst beide
# store.step_done("versand") als False lesen, bevor der erste seinen
# Kampagnen-Anlage-Schritt speichert, und beide eine Kampagne anlegen. Der
# Zugriff auf das Dict selbst ist durch einen eigenen Lock abgesichert
# (Erzeugen eines neuen Locks fuer einen bisher unbekannten Laufordner ist
# selbst ein Race, wenn zwei Threads gleichzeitig den ersten Zugriff
# machen).
_VERSAND_LOCKS: dict[str, threading.Lock] = {}
_VERSAND_LOCKS_GUARD = threading.Lock()


def _versand_lock_fuer(lauf_dir: Path) -> threading.Lock:
    schluessel = str(lauf_dir)
    with _VERSAND_LOCKS_GUARD:
        lock = _VERSAND_LOCKS.get(schluessel)
        if lock is None:
            lock = threading.Lock()
            _VERSAND_LOCKS[schluessel] = lock
        return lock


# Hilfsfunktionen ------------------------------------------------------------

def _manager(request: Request) -> Laufmanager:
    return Laufmanager(request.app.state.daten_dir)


def _hole_instantly(request: Request):
    """Wie web.routen.kunden._hole_ki: app.state.instantly gewinnt (Tests
    faken hier), sonst ein echter InstantlySender mit dem Umgebungs-Key -
    der Import passiert erst hier, damit Tests nie 'requests' brauchen."""
    instantly = getattr(request.app.state, "instantly", None)
    if instantly is not None:
        return instantly
    from pipeline.senders.instantly import InstantlySender

    return InstantlySender(os.environ["INSTANTLY_API_KEY"])


def _lauf_dir_oder_404(daten_dir, slug: str, ts: str) -> Path:
    lauf_dir = Path(daten_dir) / "laeufe" / slug / ts
    laeufe_wurzel = (Path(daten_dir) / "laeufe").resolve()
    try:
        aufgeloest = lauf_dir.resolve()
    except OSError:
        raise HTTPException(status_code=404, detail="Auftrag nicht gefunden.")
    if laeufe_wurzel not in aufgeloest.parents or not aufgeloest.is_dir():
        raise HTTPException(status_code=404, detail="Auftrag nicht gefunden.")
    return aufgeloest


def _dedupe_info_by_email(lauf_dir: Path) -> dict:
    """Liest dedupe.json (falls vorhanden) und baut eine Zuordnung
    email -> {first_name, last_name, company, title} - die Texte in
    pruefung_ok.json/personalisierung.json kennen nur die E-Mail-Adresse,
    Name/Firma/Rolle fuer die Anzeige kommen aus dem Dedupe-Schritt."""
    store = RunStore.resume(lauf_dir)
    if not store.step_done("dedupe"):
        return {}
    behalten = store.load_step("dedupe").get("behalten", [])
    return {d["email"].strip().lower(): d for d in behalten if d.get("email")}


def _empfaenger_liste(texte: list, info_by_email: dict) -> list[dict]:
    ergebnis = []
    for t in texte:
        info = info_by_email.get(t["email"].strip().lower(), {})
        name = " ".join(filter(None, [info.get("first_name"), info.get("last_name")])).strip()
        ergebnis.append({
            "email": t["email"],
            "name": name or t["email"],
            "firma": info.get("company", ""),
            "rolle": info.get("title", ""),
            "betreff": t.get("betreff", ""),
            "mail_1": t.get("mail_1", ""),
            "follow_up_1": t.get("follow_up_1", ""),
            "follow_up_2": t.get("follow_up_2", ""),
        })
    return ergebnis


def _nacharbeit_liste(nacharbeit: list, info_by_email: dict) -> list[dict]:
    ergebnis = []
    for n in nacharbeit:
        info = info_by_email.get(n["email"].strip().lower(), {})
        name = " ".join(filter(None, [info.get("first_name"), info.get("last_name")])).strip()
        ergebnis.append({
            "email": n["email"],
            "name": name or n["email"],
            "firma": info.get("company", ""),
            "grund": n.get("grund", ""),
            "betreff": n.get("betreff", ""),
            "mail_1": n.get("mail_1", ""),
            "follow_up_1": n.get("follow_up_1", ""),
            "follow_up_2": n.get("follow_up_2", ""),
            "hat_text": bool(n.get("betreff")),
        })
    return ergebnis


def _wartende_laeufe(request: Request) -> list[dict]:
    # Task 7: die Aggregation selbst lebt jetzt in web.wartende (geteilt mit
    # dem Dashboard und dem Sidebar-Badge) - hier nur noch ein duenner
    # Wrapper, damit der Rest dieser Datei (freigabe_liste) unveraendert
    # bleibt.
    return wartende_laeufe(request.app.state.daten_dir)


def _lese_kontext(request: Request, slug: str, ts: str, *,
                   fehler: str | None = None, versand_fehler: dict | None = None) -> dict:
    daten_dir = request.app.state.daten_dir
    lauf_dir = _lauf_dir_oder_404(daten_dir, slug, ts)
    stand = _manager(request).status(lauf_dir)
    store = RunStore.resume(lauf_dir)
    # Gleicher defensiver Umgang wie in _wartende_laeufe (Review-Fund Task
    # 5): eine kaputte/nicht mehr lesbare Kunden-Datei darf die Lese-Ansicht
    # nicht mit einem 500er abstuerzen lassen - stattdessen ein sichtbarer,
    # deutscher Fehlerhinweis und leere/neutrale Platzhalter fuer die
    # kunde-abhaengigen Felder.
    try:
        kunde = _kunde_fuer(daten_dir, lauf_dir)
        kunde_name, absender, follow_up_tage = kunde.name, kunde.absender, kunde.follow_up_tage
    except (OSError, ValueError, KeyError):
        kunde_name, absender, follow_up_tage = slug, "", []
        fehler = fehler or KUNDE_DATEI_FEHLER

    personalisierung = (store.load_step("personalisierung")
                         if store.step_done("personalisierung") else {"fertig": [], "nacharbeit": []})
    pruefung_ok = store.load_step("pruefung_ok") if store.step_done("pruefung_ok") else []
    info_by_email = _dedupe_info_by_email(lauf_dir)

    # E-Fix 4: sicheres JSON-Lade-Muster (web.laufmanager._lade_json_sicher)
    # statt direktem json.loads - eine kaputte/nicht mehr gueltige
    # abgelehnt.json (z.B. Unterprozess mitten im Schreiben abgebrochen)
    # darf die Lese-Ansicht nicht mit einem 500er abstuerzen lassen. Das
    # Template zeigt den Abgelehnt-Kasten ohnehin nur, wenn abgelehnt
    # truthy ist (siehe freigabe_lesen.html) - None ist hier also sicher.
    abgelehnt = _lade_json_sicher(lauf_dir / "abgelehnt.json")

    tage = follow_up_tage or [0, 0]

    return {
        "nutzer": auth.aktueller_nutzer(request),
        "nav": nav_kontext(request),
        "slug": slug, "ts": ts,
        "kunde_name": kunde_name,
        "absender": absender,
        "tag_1": tage[0], "tag_2": tage[1] if len(tage) > 1 else tage[0],
        "zustand": stand["zustand"],
        "empfaenger": _empfaenger_liste(pruefung_ok, info_by_email),
        "empf_anzahl": len(pruefung_ok),
        "nacharbeit": _nacharbeit_liste(personalisierung.get("nacharbeit", []), info_by_email),
        "nacharbeit_anzahl": len(personalisierung.get("nacharbeit", [])),
        "checkliste_texte": CHECKLISTE_TEXTE,
        "fehler": fehler,
        "versand_fehler": versand_fehler,
        "freigabe": freigabe_info(store),
        "abgelehnt": abgelehnt,
        "heute": datetime.now().strftime("%d.%m.%Y, %H:%M"),
        "campaign_id": (store.load_step("versand_komplett")["campaign_id"]
                        if store.step_done("versand_komplett") else None),
    }


def _versand_fehlertext(fehler: Exception) -> dict:
    """Dreiteiliger deutscher Fehlertext (Muster aus dem Leitfaden): Was ist
    passiert · Was ist NICHT passiert · Was du tun kannst. SendenFehler
    (Gate-/Zustands-Ablehnung durch die Pipeline selbst) bekommt den
    konkreten Grund im dritten Teil; alles andere (i.d.R. RuntimeError von
    InstantlySender._post bei einem HTTP-Fehler) den generischen
    Instantly-Text - in beiden Faellen bleibt die Freigabe bestehen."""
    if isinstance(fehler, SendenFehler):
        return {
            "was": "Der Versand wurde von der Pipeline abgelehnt.",
            "nicht": "Es ist nichts verloren gegangen — die Freigabe bleibt bestehen.",
            "tu": f"{fehler} Behebe das und versuch es über »Erneut senden« noch einmal.",
        }
    return {
        "was": "Instantly hat gerade nicht geantwortet.",
        "nicht": ("Es ist nichts verloren gegangen — die Freigabe bleibt bestehen, "
                  "die Kampagne ist noch nicht fertig angelegt."),
        "tu": "Versuch es in ein paar Minuten über »Erneut senden« noch einmal.",
    }


def _versand_antwort(request: Request, slug: str, ts: str, status_code: int = 200):
    daten_dir = request.app.state.daten_dir
    lauf_dir = _lauf_dir_oder_404(daten_dir, slug, ts)
    store = RunStore.resume(lauf_dir)
    sender = _hole_instantly(request)
    # E-Fix 6: Doppelklick-/Retry-Schutz - siehe _versand_lock_fuer oben.
    lock = _versand_lock_fuer(lauf_dir)
    try:
        # kunde wird HIER (relativ zu daten_dir) geladen und durchgereicht -
        # _versand_ausfuehren wuerde den in kunde_pfad.json gespeicherten
        # Pfad sonst relativ zum cwd DIESES Prozesses (des Webservers, nicht
        # daten_dir) lesen und ihn nicht finden (siehe Docstring dort).
        kunde = _kunde_fuer(daten_dir, lauf_dir)
        with lock:
            _versand_ausfuehren(store, sender, kunde=kunde)
    # E-Fix 5: vorher `except Exception` - das verschluckte auch echte
    # Programmierfehler (TypeError/AttributeError/...) und zeigte sie
    # faelschlich als "Instantly hat gerade nicht geantwortet" an. Konkret
    # erwartet sind: SendenFehler (Gate-Ablehnung durch die Pipeline),
    # RuntimeError (Instantly-HTTP-Fehler, siehe InstantlySender._post),
    # ValueError (z.B. create_campaign()-Validierung/leerer Lead-Import),
    # requests.RequestException (Netzwerk-/Timeout-Probleme) sowie
    # OSError/KeyError (_kunde_fuer kann beim Laden der Kunden-Datei
    # scheitern, gleicher Umgang wie web.wartende.wartende_laeufe).
    except (SendenFehler, RuntimeError, ValueError, requests.RequestException,
            OSError, KeyError) as fehler:
        kontext = _lese_kontext(request, slug, ts, versand_fehler=_versand_fehlertext(fehler))
        return request.app.state.templates.TemplateResponse(
            request, "freigabe_lesen.html", kontext, status_code=status_code)
    return RedirectResponse(f"/pruefen/{slug}/{ts}", status_code=303)


# Routen ----------------------------------------------------------------

@router.get("/pruefen")
async def freigabe_liste(request: Request):
    return request.app.state.templates.TemplateResponse(
        request, "freigabe_liste.html",
        {
            "nutzer": auth.aktueller_nutzer(request),
            "nav": nav_kontext(request),
            "laeufe": _wartende_laeufe(request),
        },
    )


@router.get("/pruefen/{slug}/{ts}")
async def freigabe_lesen(request: Request, slug: str, ts: str):
    kontext = _lese_kontext(request, slug, ts)
    return request.app.state.templates.TemplateResponse(request, "freigabe_lesen.html", kontext)


@router.post("/pruefen/{slug}/{ts}/freigeben")
# Bewusst KEIN `async def` - _versand_ausfuehren macht (moeglicherweise)
# einen synchronen HTTP-Aufruf an Instantly; als Koroutine wuerde das den
# Event-Loop fuer ALLE Nutzer blockieren (gleicher Grund wie in
# web/routen/auftraege.py bei auftrag_neu_starten).
def freigabe_absenden(request: Request, slug: str, ts: str,
                       checkliste: list[str] = Form([])):
    daten_dir = request.app.state.daten_dir
    lauf_dir = _lauf_dir_oder_404(daten_dir, slug, ts)
    store = RunStore.resume(lauf_dir)

    # Zustands-Waechter (Review-Fund Task 5) - MUSS vor jeder Mutation
    # stehen: ohne ihn koennte z.B. ein abgelehnter Auftrag trotzdem noch
    # freigegeben und an Instantly uebergeben werden.
    zustand = _manager(request).status(lauf_dir)["zustand"]
    if zustand not in ZUSTAND_ERLAUBT_FREIGEBEN:
        kontext = _lese_kontext(request, slug, ts,
                                 fehler=_zustand_fehler("Freigeben", zustand))
        return request.app.state.templates.TemplateResponse(
            request, "freigabe_lesen.html", kontext, status_code=400)

    # Audit-Trail-Schutz (Review-Fund Task 5): ist schon freigegeben (Zustand
    # "freigegeben" - Versand nur noch nicht durch), darf ein weiteres POST
    # NICHT approve() erneut aufrufen (das wuerde Name/Zeitstempel der
    # urspruenglichen Freigabe in FREIGABE.txt ueberschreiben). Der Versand-
    # Retry hat mit /senden-erneut einen eigenen, dafuer vorgesehenen Weg.
    if is_approved(store):
        info = freigabe_info(store)
        fehler = (f"Dieser Auftrag ist bereits freigegeben von {info['von'] or 'unbekannt'} "
                  f"am {info['am']}. Zum erneuten Senden »Erneut senden« benutzen.")
        kontext = _lese_kontext(request, slug, ts, fehler=fehler)
        return request.app.state.templates.TemplateResponse(
            request, "freigabe_lesen.html", kontext, status_code=400)

    if len(set(checkliste) & {"1", "2", "3"}) < 3:
        kontext = _lese_kontext(request, slug, ts, fehler=CHECKLISTE_FEHLER)
        return request.app.state.templates.TemplateResponse(
            request, "freigabe_lesen.html", kontext, status_code=400)

    approve(store, name=auth.aktueller_nutzer(request))
    return _versand_antwort(request, slug, ts)


@router.post("/pruefen/{slug}/{ts}/senden-erneut")
# Bewusst KEIN `async def` - siehe freigabe_absenden.
def freigabe_erneut_senden(request: Request, slug: str, ts: str):
    return _versand_antwort(request, slug, ts)


@router.post("/pruefen/{slug}/{ts}/ablehnen")
async def freigabe_ablehnen(request: Request, slug: str, ts: str,
                             begruendung: str = Form("")):
    daten_dir = request.app.state.daten_dir
    lauf_dir = _lauf_dir_oder_404(daten_dir, slug, ts)

    # Zustands-Waechter (Review-Fund Task 5), siehe freigabe_absenden.
    zustand = _manager(request).status(lauf_dir)["zustand"]
    if zustand not in ZUSTAND_ERLAUBT_ABLEHNEN:
        kontext = _lese_kontext(request, slug, ts,
                                 fehler=_zustand_fehler("Ablehnen", zustand))
        return request.app.state.templates.TemplateResponse(
            request, "freigabe_lesen.html", kontext, status_code=400)

    begruendung = begruendung.strip()
    if not begruendung:
        kontext = _lese_kontext(request, slug, ts, fehler=BEGRUENDUNG_FEHLER)
        return request.app.state.templates.TemplateResponse(
            request, "freigabe_lesen.html", kontext, status_code=400)

    (lauf_dir / "abgelehnt.json").write_text(json.dumps({
        "von": auth.aktueller_nutzer(request),
        "am": datetime.now().strftime("%d.%m.%Y, %H:%M"),
        "begruendung": begruendung,
    }, ensure_ascii=False), encoding="utf-8")
    return RedirectResponse(f"/pruefen/{slug}/{ts}", status_code=303)
