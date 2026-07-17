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
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse

from pipeline.__main__ import SendenFehler, _versand_ausfuehren
from pipeline.approval import approve, freigabe_info
from pipeline.config import load_kunde
from pipeline.run_store import RunStore
from web import auth
from web.laufmanager import Laufmanager
from web.nav import nav_kontext
from web.routen.auftraege import _wartet_seit_text

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


def _kunde_fuer(daten_dir, lauf_dir: Path):
    store = RunStore.resume(lauf_dir)
    pfad = Path(store.load_step("kunde_pfad")["pfad"])
    if not pfad.is_absolute():
        pfad = Path(daten_dir) / pfad
    return load_kunde(pfad)


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
    daten_dir = request.app.state.daten_dir
    manager = _manager(request)
    laeufe_wurzel = Path(daten_dir) / "laeufe"
    eintraege = []
    if not laeufe_wurzel.is_dir():
        return eintraege
    for kunden_ordner in sorted(p for p in laeufe_wurzel.iterdir() if p.is_dir()):
        for lauf_dir in sorted(p for p in kunden_ordner.iterdir() if p.is_dir()):
            stand = manager.status(lauf_dir)
            if stand["zustand"] != "wartet_auf_freigabe":
                continue
            try:
                kunde_name = _kunde_fuer(daten_dir, lauf_dir).name
            except (OSError, ValueError, KeyError):
                kunde_name = kunden_ordner.name
            eintraege.append({
                "slug": kunden_ordner.name,
                "ts": lauf_dir.name,
                "kunde_name": kunde_name,
                "fertig": stand["fertig"],
                "nacharbeit": stand["nacharbeit"],
                "wartet_seit_text": _wartet_seit_text(lauf_dir),
            })
    return eintraege


def _lese_kontext(request: Request, slug: str, ts: str, *,
                   fehler: str | None = None, versand_fehler: dict | None = None) -> dict:
    daten_dir = request.app.state.daten_dir
    lauf_dir = _lauf_dir_oder_404(daten_dir, slug, ts)
    stand = _manager(request).status(lauf_dir)
    store = RunStore.resume(lauf_dir)
    kunde = _kunde_fuer(daten_dir, lauf_dir)

    personalisierung = (store.load_step("personalisierung")
                         if store.step_done("personalisierung") else {"fertig": [], "nacharbeit": []})
    pruefung_ok = store.load_step("pruefung_ok") if store.step_done("pruefung_ok") else []
    info_by_email = _dedupe_info_by_email(lauf_dir)

    abgelehnt = None
    abgelehnt_pfad = lauf_dir / "abgelehnt.json"
    if abgelehnt_pfad.exists():
        abgelehnt = json.loads(abgelehnt_pfad.read_text(encoding="utf-8"))

    tage = kunde.follow_up_tage or [0, 0]

    return {
        "nutzer": auth.aktueller_nutzer(request),
        "nav": nav_kontext(request),
        "slug": slug, "ts": ts,
        "kunde_name": kunde.name,
        "absender": kunde.absender,
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
    try:
        # kunde wird HIER (relativ zu daten_dir) geladen und durchgereicht -
        # _versand_ausfuehren wuerde den in kunde_pfad.json gespeicherten
        # Pfad sonst relativ zum cwd DIESES Prozesses (des Webservers, nicht
        # daten_dir) lesen und ihn nicht finden (siehe Docstring dort).
        kunde = _kunde_fuer(daten_dir, lauf_dir)
        _versand_ausfuehren(store, sender, kunde=kunde)
    except Exception as fehler:  # SendenFehler (Gate) oder RuntimeError (Instantly-HTTP)
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
    if len(set(checkliste) & {"1", "2", "3"}) < 3:
        kontext = _lese_kontext(request, slug, ts, fehler=CHECKLISTE_FEHLER)
        return request.app.state.templates.TemplateResponse(
            request, "freigabe_lesen.html", kontext, status_code=400)

    store = RunStore.resume(lauf_dir)
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
