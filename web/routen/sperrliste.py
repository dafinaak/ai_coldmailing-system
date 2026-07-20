"""Route fuer "Gesperrte Domains" (globale Sperrliste): anzeigen, Domain
hinzufuegen/entfernen. Die Datei sperrliste-global.yaml, die hier
geschrieben wird, ist dieselbe, die pipeline.__main__.lauf beim naechsten
Auftrag liest (pipeline.config.lade_globale_sperrliste) - eine Aenderung
hier wirkt direkt auf die Pipeline, ohne Neustart der App noetig. Diese
Liste gilt fuer ALLE Kunden zusaetzlich zu deren eigener Sperrliste (die
im Kunden-Formular gepflegt wird, siehe Task 3)."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import yaml
from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from pipeline.config import lade_globale_sperrliste
from web import auth
from web.nav import nav_kontext

router = APIRouter()

DATEINAME = "sperrliste-global.yaml"


def _speichern(daten_dir: Path, domains: list[str]) -> None:
    """E-Fix 1: temp-Datei + os.replace statt direktem write_text (gleiches
    Muster wie web.routen.kunden._validieren_und_speichern) - os.replace ist
    ein atomarer Betriebssystem-Rename, die Zieldatei ist also NIE
    kurzzeitig leer/halb geschrieben sichtbar (z.B. fuer einen parallelen
    Lauf, der pipeline.config.lade_globale_sperrliste genau in diesem
    Moment liest)."""
    daten_dir = Path(daten_dir)
    ziel = daten_dir / DATEINAME
    with tempfile.NamedTemporaryFile(
        "w", dir=daten_dir, prefix=f".{DATEINAME}-", suffix=".tmp",
        delete=False, encoding="utf-8",
    ) as tmp:
        yaml.safe_dump(domains, tmp, allow_unicode=True)
        tmp_pfad = Path(tmp.name)
    os.replace(tmp_pfad, ziel)


def _seite(request: Request, fehler: str | None = None, status_code: int = 200):
    daten_dir = request.app.state.daten_dir
    domains = lade_globale_sperrliste(daten_dir)
    return request.app.state.templates.TemplateResponse(
        request,
        "sperrliste.html",
        {
            "nutzer": auth.aktueller_nutzer(request),
            "nav": nav_kontext(request),
            "domains": domains,
            "fehler": fehler,
        },
        status_code=status_code,
    )


@router.get("/domains")
async def domains_liste(request: Request):
    return _seite(request)


@router.post("/domains/hinzufuegen")
async def domain_hinzufuegen(request: Request, domain: str = Form(...)):
    daten_dir = request.app.state.daten_dir
    neu = domain.strip().lower()
    if not neu:
        return _seite(request, fehler="Bitte eine Domain eintragen.", status_code=400)

    vorhandene = lade_globale_sperrliste(daten_dir)
    if neu in [d.strip().lower() for d in vorhandene]:
        return _seite(
            request, fehler=f"'{neu}' steht schon auf der Liste.", status_code=400
        )

    _speichern(daten_dir, vorhandene + [neu])
    return RedirectResponse("/domains", status_code=303)


@router.post("/domains/entfernen")
async def domain_entfernen(request: Request, domain: str = Form(...)):
    daten_dir = request.app.state.daten_dir
    vorhandene = lade_globale_sperrliste(daten_dir)
    _speichern(daten_dir, [d for d in vorhandene if d != domain])
    return RedirectResponse("/domains", status_code=303)
