"""CRM-Bereich (Bauplan CRM-Verkaufsstufen, Schritt 3; freigegeben
29.07.2026): Kontakte nach Verkaufsstufen, Vorlage ist Wholix'
Contacts-Ansicht (Stufen-Leiste mit Zaehlern ueber der Liste, KEIN
Spalten-Board - an den Screenshots geprueft).

- Zufluss: automatisch NUR Antwortende (web.crm_zufluss, angeschlossen
  an den Postfach-Abruf) plus ein "+ Hinzufuegen" fuer Einzelfaelle.
- Bretter: eines je Kampagne (Kampagnen-Auswahl oben), plus "Alle" -
  Leonards Vorgabe: mehrere Kampagnen von Beginn an.
- Stufe wechseln: Auswahlfeld direkt in der Zeile (POST /crm/stufe),
  Einzelnutzer-Betrieb, keine Gleichzeitigkeits-Technik.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

from web import auth
from web.crm_speicher import KontakteSpeicher, STUFEN, STUFEN_BESCHRIFTUNG
from web.kontakte import sammle_kontakte
from web.nav import nav_kontext

router = APIRouter()

_SUCH_FELDER = ("name", "firma", "email", "kampagne")


def _speicher(request: Request) -> KontakteSpeicher:
    return KontakteSpeicher(Path(request.app.state.daten_dir) / "kontakte.db")


@router.get("/crm")
async def crm_seite(request: Request):
    speicher = _speicher(request)
    # Archiv-Ansicht (Struktur-Paket 30.07.2026): Das fruehere
    # "Kontakte"-Verzeichnis (alle je Angeschriebenen, rein lesend) lebt
    # jetzt als Ansicht IM CRM - ein Chip neben den Stufen.
    archiv = request.query_params.get("ansicht", "") == "archiv"
    kampagne = request.query_params.get("kampagne", "").strip() or None
    stufe = request.query_params.get("stufe", "").strip() or None
    if stufe is not None and stufe not in STUFEN:
        raise HTTPException(status_code=400, detail="Unbekannte Stufe.")
    suche = request.query_params.get("q", "").strip()

    if archiv:
        kontakte = sammle_kontakte(request.app.state.daten_dir)
    else:
        kontakte = speicher.kontakte(kampagne=kampagne, stufe=stufe)
    if suche:
        klein = suche.lower()
        kontakte = [k for k in kontakte if any(
            klein in str(k.get(feld, "")).lower() for feld in _SUCH_FELDER)]
    zaehler = speicher.zaehler(kampagne=kampagne)

    return request.app.state.templates.TemplateResponse(
        request, "crm.html",
        {
            "nutzer": auth.aktueller_nutzer(request),
            "nav": nav_kontext(request),
            "kampagnen": speicher.kampagnen(),
            "aktive_kampagne": kampagne or "",
            "stufen": [(name, STUFEN_BESCHRIFTUNG[name], zaehler[name])
                       for name in STUFEN],
            "stufen_beschriftung": STUFEN_BESCHRIFTUNG,
            "zaehler_alle": zaehler["alle"],
            "aktive_stufe": stufe or "",
            "archiv": archiv,
            "suche": suche,
            "kontakte": kontakte,
            "leer": not kontakte,
        },
    )


@router.post("/crm/stufe")
async def stufe_wechseln(request: Request):
    form = await request.form()
    email = str(form.get("email") or "").strip().lower()
    stufe = str(form.get("stufe") or "")
    try:
        _speicher(request).stufe_setzen(email, stufe)
    except ValueError as fehler:
        raise HTTPException(status_code=400, detail=str(fehler))
    zurueck = str(form.get("zurueck") or "/crm")
    if not zurueck.startswith("/crm"):
        zurueck = "/crm"     # kein offener Redirect
    return RedirectResponse(zurueck, status_code=303)


@router.post("/crm/anlegen")
async def kontakt_anlegen(request: Request):
    """Einzelkontakt von Hand (der kleine "+ Hinzufuegen"-Knopf -
    Wholix hat ihn auch; kein Massen-Import)."""
    form = await request.form()
    email = str(form.get("email") or "").strip().lower()
    if not email or "@" not in email:
        raise HTTPException(status_code=400,
                            detail="Bitte eine E-Mail-Adresse angeben.")
    _speicher(request).kontakt_anlegen(
        email,
        name=str(form.get("name") or "").strip(),
        firma=str(form.get("firma") or "").strip(),
        kampagne=str(form.get("kampagne") or "").strip())
    return RedirectResponse("/crm", status_code=303)
