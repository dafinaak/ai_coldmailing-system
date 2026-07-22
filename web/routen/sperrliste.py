"""Zuverlaessige globale Domain-Sperrliste mit alten und neuen Eintraegen."""
from __future__ import annotations

import os
import re
import tempfile
import threading
from pathlib import Path

import yaml
from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from pipeline.config import lade_globale_sperrlisten_eintraege
from web import auth
from web.nav import nav_kontext

router = APIRouter()

DATEINAME = "sperrliste-global.yaml"
GRUENDE = ("Kunde", "Partner", "Konkurrent", "Sonstiges")
DOMAIN_RE = re.compile(
    r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
    r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$"
)
_SPERRLISTEN_LOCK = threading.RLock()


def normalisiere_domain_muster(roh: str) -> str:
    wert = roh.strip().lower()
    if not wert:
        raise ValueError("Bitte eine Domain eintragen.")
    wildcard = wert.startswith("*.")
    kern = wert[2:] if wildcard else wert
    if not kern or "://" in kern or "/" in kern or any(c.isspace() for c in kern) or "*" in kern:
        raise ValueError(
            "Bitte eine gültige Domain oder ein Muster wie *.bund.de eintragen."
        )
    try:
        kern = kern.rstrip(".").encode("idna").decode("ascii")
    except UnicodeError as fehler:
        raise ValueError("Bitte eine gültige Domain eintragen.") from fehler
    if not DOMAIN_RE.fullmatch(kern):
        raise ValueError(
            "Bitte eine gültige Domain oder ein Muster wie *.bund.de eintragen."
        )
    return f"*.{kern}" if wildcard else kern


def muster_deckt_domain(muster: str, domain: str) -> bool:
    if muster.startswith("*."):
        suffix = muster[1:]
        return domain.endswith(suffix) and domain != muster[2:]
    return muster == domain


def _roh_laden(daten_dir: Path) -> list[str | dict]:
    # Zuerst ueber den gemeinsamen strengen Leser validieren.
    lade_globale_sperrlisten_eintraege(daten_dir)
    pfad = Path(daten_dir) / DATEINAME
    if not pfad.exists():
        return []
    return yaml.safe_load(pfad.read_text(encoding="utf-8")) or []


def _domain_aus_roh(eintrag: str | dict) -> str:
    return eintrag if isinstance(eintrag, str) else eintrag["domain"]


def _speichern(daten_dir: Path, eintraege: list[str | dict]) -> None:
    """Schreibt atomar und entfernt die Temp-Datei auch bei einem Fehler."""
    daten_dir = Path(daten_dir)
    ziel = daten_dir / DATEINAME
    tmp_pfad = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", dir=daten_dir, prefix=f".{DATEINAME}-", suffix=".tmp",
            delete=False, encoding="utf-8",
        ) as tmp:
            yaml.safe_dump(eintraege, tmp, allow_unicode=True, sort_keys=False)
            tmp_pfad = Path(tmp.name)
        os.replace(tmp_pfad, ziel)
    finally:
        if tmp_pfad is not None and tmp_pfad.exists():
            tmp_pfad.unlink()


def _angaben_pruefen(
    domain: str, grund: str | None, kommentar: str
) -> tuple[str, str, str]:
    normalisiert = normalisiere_domain_muster(domain)
    if not isinstance(grund, str):
        raise ValueError("Bitte einen gültigen Grund auswählen.")
    grund = grund.strip()
    if grund not in GRUENDE:
        raise ValueError("Bitte einen gültigen Grund auswählen.")
    kommentar = kommentar.strip()
    if len(kommentar) > 1000:
        raise ValueError("Der Kommentar darf höchstens 1000 Zeichen lang sein.")
    return normalisiert, grund, kommentar


def _konflikt_finden(neu: str, vorhanden: list[str]) -> str | None:
    for alt in vorhanden:
        if neu == alt:
            return f"'{neu}' steht schon auf der Liste."
        if muster_deckt_domain(alt, neu):
            return f"'{neu}' wird bereits durch '{alt}' gesperrt."
        if muster_deckt_domain(neu, alt):
            return (
                f"'{neu}' würde den vorhandenen Eintrag '{alt}' ebenfalls abdecken. "
                "Bitte den vorhandenen Eintrag zuerst prüfen."
            )
    return None


def _seite(request: Request, fehler: str | None = None, status_code: int = 200):
    daten_dir = request.app.state.daten_dir
    eintraege = lade_globale_sperrlisten_eintraege(daten_dir)
    return request.app.state.templates.TemplateResponse(
        request,
        "sperrliste.html",
        {
            "nutzer": auth.aktueller_nutzer(request),
            "nav": nav_kontext(request),
            "domains": eintraege,
            "eintraege": eintraege,
            "gruende": GRUENDE,
            "fehler": fehler,
        },
        status_code=status_code,
    )


@router.get("/domains")
async def domains_liste(request: Request):
    return _seite(request)


@router.post("/domains/hinzufuegen")
async def domain_hinzufuegen(
    request: Request,
    domain: str = Form(...),
    grund: str | None = Form(None),
    kommentar: str = Form(""),
):
    daten_dir = Path(request.app.state.daten_dir)
    try:
        neu, grund, kommentar = _angaben_pruefen(domain, grund, kommentar)
        with _SPERRLISTEN_LOCK:
            vorhanden_roh = _roh_laden(daten_dir)
            vorhanden = [
                normalisiere_domain_muster(_domain_aus_roh(e)) for e in vorhanden_roh
            ]
            konflikt = _konflikt_finden(neu, vorhanden)
            if konflikt:
                raise ValueError(konflikt)
            _speichern(daten_dir, vorhanden_roh + [{
                "domain": neu, "reason": grund, "comment": kommentar,
            }])
    except ValueError as fehler:
        return _seite(request, fehler=str(fehler), status_code=400)
    return RedirectResponse("/domains", status_code=303)


@router.post("/domains/bearbeiten")
async def domain_bearbeiten(
    request: Request,
    urspruengliche_domain: str = Form(...),
    domain: str = Form(...),
    grund: str = Form(...),
    kommentar: str = Form(""),
):
    daten_dir = Path(request.app.state.daten_dir)
    try:
        neu, grund, kommentar = _angaben_pruefen(domain, grund, kommentar)
        ursprung = normalisiere_domain_muster(urspruengliche_domain)
        with _SPERRLISTEN_LOCK:
            vorhanden_roh = _roh_laden(daten_dir)
            domains = [normalisiere_domain_muster(_domain_aus_roh(e)) for e in vorhanden_roh]
            treffer = [i for i, wert in enumerate(domains) if wert == ursprung]
            if len(treffer) != 1:
                raise ValueError("Der zu bearbeitende Eintrag wurde nicht eindeutig gefunden.")
            index = treffer[0]
            konflikt = _konflikt_finden(neu, domains[:index] + domains[index + 1:])
            if konflikt:
                raise ValueError(konflikt)
            neu_roh = list(vorhanden_roh)
            neu_roh[index] = {"domain": neu, "reason": grund, "comment": kommentar}
            _speichern(daten_dir, neu_roh)
    except ValueError as fehler:
        return _seite(request, fehler=str(fehler), status_code=400)
    return RedirectResponse("/domains", status_code=303)


@router.post("/domains/entfernen")
async def domain_entfernen(request: Request, domain: str = Form(...)):
    daten_dir = Path(request.app.state.daten_dir)
    try:
        gesucht = normalisiere_domain_muster(domain)
        with _SPERRLISTEN_LOCK:
            vorhanden = _roh_laden(daten_dir)
            behalten = [
                e for e in vorhanden
                if normalisiere_domain_muster(_domain_aus_roh(e)) != gesucht
            ]
            _speichern(daten_dir, behalten)
    except ValueError as fehler:
        return _seite(request, fehler=str(fehler), status_code=400)
    return RedirectResponse("/domains", status_code=303)
