"""Route fuer Auftraege: der Dialog "Anschreiben erstellen lassen" (Start
eines neuen Anschreiben-Auftrags) und die Fortschrittsseite eines laufenden/
angehaltenen/wartenden Auftrags. Nutzt web.laufmanager.Laufmanager, die den
eigentlichen Unterprozess startet/ueberwacht - diese Route uebersetzt nur
Formulare/URLs in Aufrufe davon und rendert die Vorlagen aus dem Leitfaden."""
from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse

from pipeline.config import load_kunde
from web import auth
from web.laufmanager import LaufBereitsAktiv, Laufmanager, LaufmanagerFehler, SCHRITTE
from web.nav import nav_kontext
from web.routen.kunden import _kunden_dir, _zielgruppe_text

router = APIRouter()

LIMIT_OPTIONEN = [25, 40, 60]
LIMIT_DEFAULT = 60

KEINE_KUNDEN_HINWEIS = (
    "Noch keine Kunden angelegt. Leg zuerst einen Kunden an, bevor Anschreiben "
    "erstellt werden können."
)


def _manager(request: Request) -> Laufmanager:
    return Laufmanager(request.app.state.daten_dir)


def _kunden_optionen(daten_dir) -> list[dict]:
    dateien = sorted(_kunden_dir(daten_dir).glob("*.yaml"))
    optionen = []
    for pfad in dateien:
        try:
            kunde = load_kunde(pfad)
        except ValueError:
            continue  # kaputte Kunden-Datei fehlt einfach in der Auswahl
        optionen.append({
            "dateiname": pfad.stem,
            "name": kunde.name,
            "ziel_text": _zielgruppe_text(kunde.zielgruppe),
        })
    return optionen


def _dialog_antwort(request: Request, *, fehler: str | None = None, status_code: int = 200):
    daten_dir = request.app.state.daten_dir
    return request.app.state.templates.TemplateResponse(
        request,
        "auftrag_neu.html",
        {
            "nutzer": auth.aktueller_nutzer(request),
            "nav": nav_kontext(request),
            "kunden": _kunden_optionen(daten_dir),
            "limit_optionen": LIMIT_OPTIONEN,
            "limit_default": LIMIT_DEFAULT,
            "fehler": fehler,
        },
        status_code=status_code,
    )


def _ergaenze_meta(lauf_dir: Path, **felder) -> None:
    """Ergaenzt auftrag_meta.json (von Laufmanager.starte() mit kunde_datei+
    limit angelegt) um Anzeige-Felder, die nur die Web-Schicht kennt (wer hat
    gestartet, wann in Anzeige-Format) - Laufmanager selbst kennt keine
    angemeldeten Nutzer."""
    meta_pfad = lauf_dir / "auftrag_meta.json"
    daten = json.loads(meta_pfad.read_text(encoding="utf-8")) if meta_pfad.exists() else {}
    daten.update(felder)
    meta_pfad.write_text(json.dumps(daten, ensure_ascii=False), encoding="utf-8")


def _wartet_seit_text(lauf_dir: Path) -> str:
    """Formuliert 'Wartet seit ... auf Prüfung' - wörtliches Muster aus dem
    Karten-Beispiel im Leitfaden (docs/text-leitfaden-interface.md), nur die
    Dauer ist dynamisch (dort als Beispiel '2 Std.' vorgegeben)."""
    pruefung_pfad = lauf_dir / "pruefung_ok.json"
    try:
        sekunden = time.time() - pruefung_pfad.stat().st_mtime
    except OSError:
        sekunden = 0
    if sekunden < 60:
        dauer = "gerade eben"
    elif sekunden < 3600:
        dauer = f"{int(sekunden // 60)} Min."
    else:
        dauer = f"{int(sekunden // 3600)} Std."
    return f"Wartet seit {dauer} auf Prüfung"


def _lade_meta(lauf_dir: Path) -> dict:
    meta_pfad = lauf_dir / "auftrag_meta.json"
    if not meta_pfad.exists():
        return {}
    try:
        return json.loads(meta_pfad.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _lauf_dir_oder_404(daten_dir, slug: str, ts: str) -> Path:
    lauf_dir = (Path(daten_dir) / "laeufe" / slug / ts)
    laeufe_wurzel = (Path(daten_dir) / "laeufe").resolve()
    try:
        aufgeloest = lauf_dir.resolve()
    except OSError:
        raise HTTPException(status_code=404, detail="Auftrag nicht gefunden.")
    if laeufe_wurzel not in aufgeloest.parents or not aufgeloest.is_dir():
        raise HTTPException(status_code=404, detail="Auftrag nicht gefunden.")
    return aufgeloest


# Routen ---------------------------------------------------------------

@router.get("/auftraege/neu")
async def auftrag_neu_formular(request: Request):
    return _dialog_antwort(request)


@router.post("/auftraege/neu")
async def auftrag_neu_starten(
    request: Request,
    kunde_dateiname: str = Form(""),
    limit: int = Form(LIMIT_DEFAULT),
):
    if not kunde_dateiname.strip():
        return _dialog_antwort(request, fehler=KEINE_KUNDEN_HINWEIS, status_code=400)

    manager = _manager(request)
    kunde_datei = f"kunden/{kunde_dateiname}.yaml"
    try:
        lauf_dir = manager.starte(kunde_datei, limit)
    except LaufmanagerFehler as fehler:
        return _dialog_antwort(request, fehler=str(fehler), status_code=400)

    _ergaenze_meta(
        lauf_dir,
        gestartet_von=auth.aktueller_nutzer(request),
        gestartet_am=datetime.now().strftime("%d.%m.%Y, %H:%M"),
    )

    slug, ts = lauf_dir.parent.name, lauf_dir.name
    return RedirectResponse(f"/auftraege/{slug}/{ts}", status_code=303)


@router.get("/auftraege/{slug}/{ts}")
async def auftrag_fortschritt(request: Request, slug: str, ts: str):
    daten_dir = request.app.state.daten_dir
    lauf_dir = _lauf_dir_oder_404(daten_dir, slug, ts)

    manager = _manager(request)
    stand = manager.status(lauf_dir)
    meta = _lade_meta(lauf_dir)

    kunde_name = meta.get("kunde_name")
    if not kunde_name:
        try:
            kunde_name = load_kunde(Path(daten_dir) / meta["kunde_datei"]).name
        except (KeyError, ValueError, FileNotFoundError):
            kunde_name = slug

    return request.app.state.templates.TemplateResponse(
        request,
        "auftrag_fortschritt.html",
        {
            "nutzer": auth.aktueller_nutzer(request),
            "nav": nav_kontext(request),
            "slug": slug,
            "ts": ts,
            "kunde_name": kunde_name,
            "gestartet_am": meta.get("gestartet_am", ""),
            "gestartet_von": meta.get("gestartet_von"),
            "schritte": SCHRITTE,
            "wartet_seit_text": _wartet_seit_text(lauf_dir),
            **stand,
        },
    )


@router.get("/auftraege/{slug}/{ts}/status.json")
async def auftrag_status_json(request: Request, slug: str, ts: str):
    daten_dir = request.app.state.daten_dir
    lauf_dir = _lauf_dir_oder_404(daten_dir, slug, ts)
    manager = _manager(request)
    return JSONResponse(manager.status(lauf_dir))


@router.post("/auftraege/{slug}/{ts}/fortsetzen")
async def auftrag_fortsetzen(request: Request, slug: str, ts: str):
    daten_dir = request.app.state.daten_dir
    lauf_dir = _lauf_dir_oder_404(daten_dir, slug, ts)
    manager = _manager(request)
    try:
        if manager.status(lauf_dir)["zustand"] != "laeuft":
            manager.setze_fort(lauf_dir)
    except LaufBereitsAktiv:
        pass  # zwischenzeitlich schon fortgesetzt (z.B. Doppelklick) - kein Fehler
    return RedirectResponse(f"/auftraege/{slug}/{ts}", status_code=303)
