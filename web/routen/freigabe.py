"""Route fuer "Lesen & Freigeben" (Task 5, Copy-Rework 20.07.2026) - die sicherheitskritischste
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
from pipeline.models import Lead
from pipeline.personalize import regenerate_step
from pipeline.quality import check as quality_check
from pipeline.run_store import RunStore
from web import auth
from web.freigabe_status import (
    SCHRITTE,
    FreigabeStatusStore,
    VeralteterStand,
    grundtexte_fuer_lauf,
)
from web.laufmanager import Laufmanager, _lade_json_sicher
from web.instantly_leser import geteilten_leser
from web.nav import nav_kontext
from web.wartende import kunde_fuer as _kunde_fuer, pruefbare_laeufe

router = APIRouter()

BEGRUENDUNG_FEHLER = "Bitte kurz begründen, was nicht gepasst hat."

KUNDE_DATEI_FEHLER = ("Die Angebots-Datei zu dieser E-Mail-Runde ist gerade nicht lesbar oder "
                      "beschädigt. Bitte im Angebote-Bereich prüfen.")

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
    return f"Diese E-Mail-Runde {grund} — {aktion} ist jetzt nicht mehr möglich. Lade die Seite neu."


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


def _hole_ki(request: Request):
    ki = getattr(request.app.state, "ki", None)
    if ki is not None:
        return ki
    from pipeline.ki import KI

    return KI()


def _hole_webseiten_leser(request: Request):
    leser = getattr(request.app.state, "webseiten_leser", None)
    if leser is not None:
        return leser
    from pipeline.website import fetch_text

    return fetch_text


def _lauf_dir_oder_404(daten_dir, slug: str, ts: str) -> Path:
    lauf_dir = Path(daten_dir) / "laeufe" / slug / ts
    laeufe_wurzel = (Path(daten_dir) / "laeufe").resolve()
    try:
        aufgeloest = lauf_dir.resolve()
    except OSError:
        raise HTTPException(status_code=404, detail="E-Mail-Runde nicht gefunden.")
    if laeufe_wurzel not in aufgeloest.parents or not aufgeloest.is_dir():
        raise HTTPException(status_code=404, detail="E-Mail-Runde nicht gefunden.")
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


def _empfaenger_liste(texte: list, info_by_email: dict, status_ansicht: dict) -> list[dict]:
    status_by_email = {
        e["email"].strip().lower(): e for e in status_ansicht["recipients"]
    }
    ergebnis = []
    for t in texte:
        email_key = t["email"].strip().lower()
        info = info_by_email.get(email_key, {})
        status = status_by_email[email_key]
        name = " ".join(filter(None, [info.get("first_name"), info.get("last_name")])).strip()
        alle_bestaetigt = all(s["approved"] for s in status["steps"].values())
        zeilen_status = (
            "nacharbeit" if status["qa_blocked"]
            else "fertig" if alle_bestaetigt
            else "offen"
        )
        ergebnis.append({
            "id": status["id"],
            "email": t["email"],
            "name": name or t["email"],
            "firma": info.get("company", ""),
            "rolle": info.get("title", ""),
            "status": zeilen_status,
            "qa_blocked": status["qa_blocked"],
            "qa_reason": status["qa_reason"],
            "betreff": t.get("betreff", ""),
            "mail_1": t.get("mail_1", ""),
            "follow_up_1": t.get("follow_up_1", ""),
            "follow_up_2": t.get("follow_up_2", ""),
            "steps": [
                {"key": "mail_1", "label": "E-Mail 1", "betreff": t.get("betreff", ""),
                 "text": t.get("mail_1", ""), **status["steps"]["mail_1"]},
                {"key": "follow_up_1", "label": "Follow-up 1", "betreff": "",
                 "text": t.get("follow_up_1", ""), **status["steps"]["follow_up_1"]},
                {"key": "follow_up_2", "label": "Follow-up 2", "betreff": "",
                 "text": t.get("follow_up_2", ""), **status["steps"]["follow_up_2"]},
            ],
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


def _live_status_anreichern(empfaenger: list[dict], recipients: dict) -> int:
    """Verbindet belegte Instantly-Werte ueber die normalisierte E-Mail."""
    fehlend = 0
    for eintrag in empfaenger:
        live = recipients.get(eintrag["email"].strip().lower())
        eintrag["live_known"] = live is not None
        if live is None:
            fehlend += 1
            live = {"steps": {}, "overall": {}}
        live_schritte = live.get("steps") or {}
        for schritt in eintrag["steps"]:
            schritt_live = live_schritte.get(schritt["key"]) or {}
            schritt["sent_at"] = schritt_live.get("sent_at")
            schritt["replied"] = schritt_live.get("replied")
        eintrag["live_overall"] = live.get("overall") or {
            "replied": None, "status": None,
        }
    return fehlend


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
    info_by_email = _dedupe_info_by_email(lauf_dir)
    try:
        grundtexte = grundtexte_fuer_lauf(
            lauf_dir,
            nacharbeit_einschliessen=stand["zustand"] != "uebergeben",
        )
        status_store = FreigabeStatusStore(lauf_dir)
        status_ansicht = status_store.ansicht(
            grundtexte,
            freigabe_info(store) if is_approved(store) else None,
        )
        wirksame_texte = status_store.materialisieren(grundtexte)
        empfaenger = _empfaenger_liste(wirksame_texte, info_by_email, status_ansicht)
    except (OSError, ValueError, KeyError) as status_fehler:
        grundtexte = []
        status_ansicht = {"revision": "", "recipients": [], "all_approved": False}
        empfaenger = []
        fehler = fehler or str(status_fehler)

    voll_bestaetigt = sum(e["status"] == "fertig" for e in empfaenger)
    nacharbeit_anzahl = sum(e["status"] == "nacharbeit" for e in empfaenger)
    offen_anzahl = len(empfaenger) - voll_bestaetigt - nacharbeit_anzahl
    pflichttexte_vollstaendig = bool(empfaenger) and all(
        e["email"] and e["betreff"] and e["mail_1"]
        and e["follow_up_1"] and e["follow_up_2"]
        for e in empfaenger
    )

    campaign_id = (store.load_step("versand_komplett")["campaign_id"]
                   if store.step_done("versand_komplett") else None)
    live_erreichbar = None
    live_stand = None
    live_warnung = None
    if campaign_id:
        try:
            live = geteilten_leser(request.app).freigabe_stand(campaign_id)
        except (KeyError, OSError, RuntimeError, requests.exceptions.RequestException):
            live = {"recipients": {}, "erreichbar": False, "stand": None}
        live_erreichbar = live.get("erreichbar", False)
        live_stand = live.get("stand")
        fehlend = _live_status_anreichern(empfaenger, live.get("recipients") or {})
        if not live_erreichbar:
            if live_stand is None:
                live_warnung = (
                    "Instantly ist gerade nicht erreichbar. Versand und Antworten "
                    "sind deshalb unbekannt."
                )
            else:
                live_warnung = (
                    "Instantly ist gerade nicht erreichbar. Gezeigt wird der zuletzt "
                    "bekannte Stand."
                )
        elif fehlend:
            live_warnung = (
                "Instantly hat nicht für alle Empfänger einen belegbaren Stand geliefert. "
                "Fehlende Werte bleiben unbekannt."
            )
    else:
        _live_status_anreichern(empfaenger, {})

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
        "empfaenger": empfaenger,
        "empf_anzahl": len(empfaenger),
        "voll_bestaetigt": voll_bestaetigt,
        "offen_anzahl": offen_anzahl,
        "nacharbeit": _nacharbeit_liste(personalisierung.get("nacharbeit", []), info_by_email),
        "nacharbeit_anzahl": nacharbeit_anzahl,
        "revision": status_ansicht["revision"],
        "uebergabe_bereit": status_ansicht["all_approved"] and pflichttexte_vollstaendig,
        "schreibgeschuetzt": stand["zustand"] == "uebergeben",
        "fehler": fehler,
        "versand_fehler": versand_fehler,
        "live_erreichbar": live_erreichbar,
        "live_stand": live_stand,
        "live_warnung": live_warnung,
        "freigabe": freigabe_info(store),
        "abgelehnt": abgelehnt,
        "heute": datetime.now().strftime("%d.%m.%Y, %H:%M"),
        "campaign_id": campaign_id,
    }


def _freigabe_fehlerseite(
    request: Request, slug: str, ts: str, fehler: str, status_code: int
):
    return request.app.state.templates.TemplateResponse(
        request,
        "freigabe_lesen.html",
        _lese_kontext(request, slug, ts, fehler=fehler),
        status_code=status_code,
    )


def _pruefung_ist_schreibbar(request: Request, lauf_dir: Path) -> str | None:
    zustand = _manager(request).status(lauf_dir)["zustand"]
    if zustand == "wartet_auf_freigabe":
        return None
    return _zustand_fehler("Ändern", zustand)


def _pflichttexte_pruefen(texte: list[dict]) -> None:
    if not texte:
        raise ValueError("Diese E-Mail-Runde enthält keine Empfänger.")
    pflicht = ("email", "betreff", "mail_1", "follow_up_1", "follow_up_2")
    for text in texte:
        if any(not isinstance(text.get(feld), str) or not text[feld].strip()
               for feld in pflicht):
            raise ValueError(
                "Mindestens ein Empfänger hat noch nicht alle drei vollständigen E-Mails."
            )


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
            "gruppen": pruefbare_laeufe(request.app.state.daten_dir),
        },
    )


@router.get("/pruefen/{slug}/{ts}")
async def freigabe_lesen(request: Request, slug: str, ts: str):
    kontext = _lese_kontext(request, slug, ts)
    return request.app.state.templates.TemplateResponse(request, "freigabe_lesen.html", kontext)


@router.post("/pruefen/{slug}/{ts}/bestaetigen")
def schritt_bestaetigen(
    request: Request,
    slug: str,
    ts: str,
    revision: str = Form(...),
    recipient_id: str = Form(...),
    step: str = Form(...),
    approved: str = Form("1"),
):
    lauf_dir = _lauf_dir_oder_404(request.app.state.daten_dir, slug, ts)
    zustand_fehler = _pruefung_ist_schreibbar(request, lauf_dir)
    if zustand_fehler:
        return _freigabe_fehlerseite(request, slug, ts, zustand_fehler, 400)
    if step not in SCHRITTE or approved not in {"0", "1"}:
        return _freigabe_fehlerseite(
            request, slug, ts, "Die gewählte Änderung ist ungültig.", 400
        )
    try:
        texte = grundtexte_fuer_lauf(lauf_dir)
        FreigabeStatusStore(lauf_dir).bestaetigungen_setzen(
            texte,
            [recipient_id],
            actor=auth.aktueller_nutzer(request),
            approved=approved == "1",
            revision=revision,
            step=step,
        )
    except VeralteterStand:
        return _freigabe_fehlerseite(
            request,
            slug,
            ts,
            "Die E-Mail-Runde wurde inzwischen geändert. Die Seite wurde neu geladen; "
            "bitte prüfe deine Auswahl noch einmal.",
            409,
        )
    except (OSError, ValueError, KeyError) as fehler:
        return _freigabe_fehlerseite(request, slug, ts, str(fehler), 400)
    return RedirectResponse(f"/pruefen/{slug}/{ts}", status_code=303)


@router.post("/pruefen/{slug}/{ts}/mehrfach")
def empfaenger_mehrfach_bestaetigen(
    request: Request,
    slug: str,
    ts: str,
    revision: str = Form(...),
    recipient_ids: list[str] = Form([]),
    action: str = Form(...),
):
    lauf_dir = _lauf_dir_oder_404(request.app.state.daten_dir, slug, ts)
    zustand_fehler = _pruefung_ist_schreibbar(request, lauf_dir)
    if zustand_fehler:
        return _freigabe_fehlerseite(request, slug, ts, zustand_fehler, 400)
    if action not in {"approve", "clear"}:
        return _freigabe_fehlerseite(
            request, slug, ts, "Die gewählte Mehrfachaktion ist ungültig.", 400
        )
    try:
        texte = grundtexte_fuer_lauf(lauf_dir)
        FreigabeStatusStore(lauf_dir).bestaetigungen_setzen(
            texte,
            recipient_ids,
            actor=auth.aktueller_nutzer(request),
            approved=action == "approve",
            revision=revision,
            step=None,
        )
    except VeralteterStand:
        return _freigabe_fehlerseite(
            request,
            slug,
            ts,
            "Die E-Mail-Runde wurde inzwischen geändert. Die Seite wurde neu geladen; "
            "bitte prüfe deine Auswahl noch einmal.",
            409,
        )
    except (OSError, ValueError, KeyError) as fehler:
        return _freigabe_fehlerseite(request, slug, ts, str(fehler), 400)
    return RedirectResponse(f"/pruefen/{slug}/{ts}", status_code=303)


@router.post("/pruefen/{slug}/{ts}/neu-erzeugen")
def schritt_neu_erzeugen(
    request: Request,
    slug: str,
    ts: str,
    revision: str = Form(...),
    recipient_id: str = Form(...),
    step: str = Form(...),
):
    lauf_dir = _lauf_dir_oder_404(request.app.state.daten_dir, slug, ts)
    zustand_fehler = _pruefung_ist_schreibbar(request, lauf_dir)
    if zustand_fehler:
        return _freigabe_fehlerseite(request, slug, ts, zustand_fehler, 400)
    if step not in SCHRITTE:
        return _freigabe_fehlerseite(
            request, slug, ts, "Der gewählte E-Mail-Schritt ist ungültig.", 400
        )

    status_store = FreigabeStatusStore(lauf_dir)
    try:
        grundtexte = grundtexte_fuer_lauf(lauf_dir)
        stand = status_store.ansicht(grundtexte)
        if stand["revision"] != revision:
            raise VeralteterStand("Die E-Mail-Runde wurde inzwischen geändert.")
        status_empfaenger = next(
            (e for e in stand["recipients"] if e["id"] == recipient_id), None
        )
        if status_empfaenger is None:
            raise ValueError("Der ausgewählte Empfänger ist nicht mehr vorhanden.")

        wirksame_texte = status_store.materialisieren(grundtexte)
        aktuelle_texte = next(
            text for text in wirksame_texte
            if text["email"].strip().lower() == status_empfaenger["email"].strip().lower()
        )
        info = _dedupe_info_by_email(lauf_dir).get(
            status_empfaenger["email"].strip().lower()
        )
        if not info:
            raise ValueError("Die Empfängerdaten für diese E-Mail sind nicht vollständig.")
        lead = Lead(**{
            feld: info.get(feld, "")
            for feld in ("first_name", "last_name", "email", "company",
                         "title", "website", "source")
        })
        kunde = _kunde_fuer(request.app.state.daten_dir, lauf_dir)
        ki = _hole_ki(request)
        webseiten_text = _hole_webseiten_leser(request)(lead.website)
        neuer_schritt = regenerate_step(
            lead, kunde, ki, webseiten_text, aktuelle_texte, step
        )

        kandidat = dict(aktuelle_texte)
        if step == "mail_1":
            kandidat["betreff"] = neuer_schritt["betreff"]
        kandidat[step] = neuer_schritt["text"]
        try:
            _pflichttexte_pruefen([kandidat])
        except ValueError:
            qa_ok, qa_grund = False, "Weitere E-Mail-Schritte fehlen"
        else:
            qa_ok, qa_grund = quality_check(kandidat, lead, kunde, ki)

        status_store.override_setzen(
            grundtexte,
            recipient_id,
            step,
            neuer_schritt,
            revision,
            qa_cleared=qa_ok,
            qa_reason=None if qa_ok else qa_grund,
        )
    except VeralteterStand:
        return _freigabe_fehlerseite(
            request,
            slug,
            ts,
            "Die E-Mail-Runde wurde inzwischen geändert. Die Seite wurde neu geladen; "
            "bitte erzeuge den Schritt bei Bedarf noch einmal.",
            409,
        )
    except (OSError, ValueError, RuntimeError, requests.RequestException, KeyError) as fehler:
        return _freigabe_fehlerseite(request, slug, ts, str(fehler), 400)
    return RedirectResponse(f"/pruefen/{slug}/{ts}", status_code=303)


@router.post("/pruefen/{slug}/{ts}/freigeben")
# Bewusst KEIN `async def` - _versand_ausfuehren macht (moeglicherweise)
# einen synchronen HTTP-Aufruf an Instantly; als Koroutine wuerde das den
# Event-Loop fuer ALLE Nutzer blockieren (gleicher Grund wie in
# web/routen/auftraege.py bei auftrag_neu_starten).
def freigabe_absenden(request: Request, slug: str, ts: str):
    daten_dir = request.app.state.daten_dir
    lauf_dir = _lauf_dir_oder_404(daten_dir, slug, ts)
    store = RunStore.resume(lauf_dir)
    status_store = FreigabeStatusStore(lauf_dir)

    # Ein gemeinsamer RLock umfasst Zustandsprüfung, Audit-Trail, letzte
    # Inhaltsprüfung, Materialisierung und Versand. So kann ein Doppelklick
    # nicht zwischen Prüfung und approve() rutschen.
    with status_store.lock:
        zustand = _manager(request).status(lauf_dir)["zustand"]
        if zustand not in ZUSTAND_ERLAUBT_FREIGEBEN:
            return _freigabe_fehlerseite(
                request, slug, ts, _zustand_fehler("Freigeben", zustand), 400
            )
        if is_approved(store):
            info = freigabe_info(store)
            fehler = (
                f"Diese E-Mail-Runde ist bereits freigegeben von "
                f"{info['von'] or 'unbekannt'} am {info['am']}. "
                "Zum erneuten Senden »Erneut senden« benutzen."
            )
            return _freigabe_fehlerseite(request, slug, ts, fehler, 400)

        try:
            grundtexte = grundtexte_fuer_lauf(lauf_dir)
            if not status_store.alles_bestaetigt(grundtexte):
                return _freigabe_fehlerseite(
                    request,
                    slug,
                    ts,
                    "Noch nicht alle E-Mails sind bestätigt oder eine Nacharbeit ist offen.",
                    400,
                )
            wirksame_texte = status_store.materialisieren(grundtexte)
            _pflichttexte_pruefen(wirksame_texte)
        except (OSError, ValueError, KeyError) as fehler:
            return _freigabe_fehlerseite(request, slug, ts, str(fehler), 400)

        store.save_step("pruefung_ok", wirksame_texte)
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
