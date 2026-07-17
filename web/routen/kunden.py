"""Route fuer den Kunden-Bereich: Liste, Anlegen/Bearbeiten-Formular,
Speichern und die Angebots-Ableitung von der Firmen-Webseite.

Speichern validiert NICHT mit eigener Logik, sondern schreibt die
eingetippten Daten in eine temporaere YAML-Datei und laedt sie mit
pipeline.config.load_kunde - dieselbe Funktion, die auch die Pipeline
beim Start eines Auftrags nutzt. So gibt es nur eine Wahrheit dafuer,
was ein gueltiger Kunde ist; die Web-Seite uebersetzt nur die
ValueError-Meldungen in einen sichtbaren Formular-Fehler.

Der Dateiname eines Kunden (Slug aus dem Namen, siehe pipeline.run_store)
steht mit dem Anlegen fest und aendert sich bei spaeteren Namensaenderungen
NICHT mehr - sonst wuerden Links/Auftraege auf den alten Dateinamen ins
Leere laufen."""
from __future__ import annotations

import tempfile
from pathlib import Path

import yaml
from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse

from pipeline.config import load_kunde
from pipeline.offer import draft_offer
from pipeline.run_store import _slug
from pipeline.website import fetch_text
from web import auth
from web.nav import nav_kontext

router = APIRouter()

KUNDEN_ORDNER = "kunden"

FORMULAR_FELDER = [
    "name", "webseite",
    "zielgruppe_titel", "zielgruppe_region", "zielgruppe_firmengroesse",
    "angebot", "tonalitaet", "absender",
    "follow_up_tag_1", "follow_up_tag_2",
    "test_empfaenger", "sperrliste",
]

LEERE_WERTE = {feld: "" for feld in FORMULAR_FELDER}

VORSCHLAG_HINWEIS = "Vorschlag von der Webseite übernommen — nur leere Felder wurden ausgefüllt."

ABLEITEN_FEHLER = (
    "Der Vorschlag von der Webseite hat gerade nicht geklappt. Es ist nichts "
    "gespeichert oder verändert worden — deine bisherigen Eingaben stehen unten "
    "weiterhin so, wie du sie eingetragen hast. Du kannst es gleich noch einmal "
    "versuchen oder Angebot und Tonalität von Hand eintragen."
)


# Hilfsfunktionen ---------------------------------------------------------

def _kunden_dir(daten_dir) -> Path:
    ordner = Path(daten_dir) / KUNDEN_ORDNER
    ordner.mkdir(parents=True, exist_ok=True)
    return ordner


def _zielgruppe_text(zielgruppe: dict) -> str:
    teile = []
    titel = ", ".join(zielgruppe.get("titel") or [])
    region = ", ".join(zielgruppe.get("region") or [])
    groesse = ", ".join(zielgruppe.get("firmengroesse") or [])
    if titel:
        teile.append(titel)
    if region:
        teile.append(region)
    if groesse:
        teile.append(f"{groesse} Mitarbeiter")
    return " · ".join(teile) if teile else "Keine Zielgruppe hinterlegt"


def _liste_eintrag(pfad: Path) -> dict | None:
    try:
        kunde = load_kunde(pfad)
    except ValueError:
        # Eine kaputte Kunden-Datei soll nicht die ganze Liste zum Absturz
        # bringen - sie fehlt dann einfach, bis sie im Formular repariert wird.
        return None
    return {
        "dateiname": pfad.stem,
        "name": kunde.name,
        "ziel_text": _zielgruppe_text(kunde.zielgruppe),
        "absender": kunde.absender,
        "sperr_text": ", ".join(kunde.sperrliste) if kunde.sperrliste else "keine",
    }


def _werte_aus_kunde(kunde) -> dict:
    tage = kunde.follow_up_tage or []
    return {
        "name": kunde.name,
        "webseite": kunde.webseite,
        "zielgruppe_titel": ", ".join(kunde.zielgruppe.get("titel") or []),
        "zielgruppe_region": ", ".join(kunde.zielgruppe.get("region") or []),
        "zielgruppe_firmengroesse": ", ".join(kunde.zielgruppe.get("firmengroesse") or []),
        "angebot": kunde.angebot,
        "tonalitaet": kunde.tonalitaet,
        "absender": kunde.absender,
        "follow_up_tag_1": str(tage[0]) if len(tage) > 0 else "",
        "follow_up_tag_2": str(tage[1]) if len(tage) > 1 else "",
        "test_empfaenger": "\n".join(kunde.test_empfaenger or []),
        "sperrliste": "\n".join(kunde.sperrliste or []),
    }


def _kommaliste(text: str) -> list:
    return [teil.strip() for teil in (text or "").split(",") if teil.strip()]


def _zeilenliste(text: str) -> list:
    return [zeile.strip() for zeile in (text or "").splitlines() if zeile.strip()]


def _zahl(text: str):
    text = (text or "").strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return float(text.replace(",", "."))
    except ValueError:
        return text  # bleibt String - load_kunde meldet den Fehler dann klar


def _daten_fuer_load_kunde(werte: dict) -> dict:
    """Baut aus den Formular-Rohwerten ein Dict fuer load_kunde. Pflichtfelder,
    die leer geblieben sind, werden bewusst WEGGELASSEN (statt als leerer
    String uebergeben) - so greift dieselbe 'Pflichtfelder fehlen'-Meldung
    wie beim direkten Bearbeiten der YAML-Datei, ohne die Regel hier
    nochmal nachzubauen."""
    daten: dict = {}

    name = werte["name"].strip()
    if name:
        daten["name"] = name

    zielgruppe = {
        "titel": _kommaliste(werte["zielgruppe_titel"]),
        "region": _kommaliste(werte["zielgruppe_region"]),
        "firmengroesse": _kommaliste(werte["zielgruppe_firmengroesse"]),
    }
    if any(zielgruppe.values()):
        daten["zielgruppe"] = zielgruppe

    angebot = werte["angebot"].strip()
    if angebot:
        daten["angebot"] = angebot

    tonalitaet = werte["tonalitaet"].strip()
    if tonalitaet:
        daten["tonalitaet"] = tonalitaet

    absender = werte["absender"].strip()
    if absender:
        daten["absender"] = absender

    tage = [t for t in (_zahl(werte["follow_up_tag_1"]), _zahl(werte["follow_up_tag_2"]))
            if t is not None]
    if tage:
        daten["follow_up_tage"] = tage

    empfaenger = _zeilenliste(werte["test_empfaenger"])
    if empfaenger:
        daten["test_empfaenger"] = empfaenger

    daten["sperrliste"] = _zeilenliste(werte["sperrliste"])
    daten["webseite"] = werte["webseite"].strip()

    return daten


def _freier_dateiname(kunden_dir: Path, basis: str) -> str:
    basis = basis or "kunde"
    kandidat = basis
    zaehler = 2
    while (kunden_dir / f"{kandidat}.yaml").exists():
        kandidat = f"{basis}-{zaehler}"
        zaehler += 1
    return kandidat


def _validieren_und_speichern(kunden_dir: Path, dateiname: str, daten: dict) -> None:
    kunden_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", dir=kunden_dir, prefix=f".{dateiname}-", suffix=".yaml.tmp",
        delete=False, encoding="utf-8",
    ) as tmp:
        yaml.safe_dump(daten, tmp, allow_unicode=True, sort_keys=False)
        tmp_pfad = Path(tmp.name)
    try:
        load_kunde(tmp_pfad)
    except ValueError:
        tmp_pfad.unlink(missing_ok=True)
        raise
    tmp_pfad.replace(kunden_dir / f"{dateiname}.yaml")


def _hole_ki(request: Request):
    ki = getattr(request.app.state, "ki", None)
    if ki is not None:
        return ki
    from pipeline.ki import KI  # spaeter Import: nur bei echtem Aufruf noetig

    return KI()


def _formular_antwort(
    request: Request, *, modus: str, dateiname: str | None, werte: dict,
    fehler: str | None = None, status_code: int = 200,
    vorschlag_hinweis: str | None = None,
    angebot_ist_vorschlag: bool = False, tonalitaet_ist_vorschlag: bool = False,
):
    return request.app.state.templates.TemplateResponse(
        request,
        "kunde_form.html",
        {
            "nutzer": auth.aktueller_nutzer(request),
            "nav": nav_kontext(request),
            "modus": modus,
            "dateiname": dateiname,
            "werte": werte,
            "fehler": fehler,
            "vorschlag_hinweis": vorschlag_hinweis,
            "angebot_ist_vorschlag": angebot_ist_vorschlag,
            "tonalitaet_ist_vorschlag": tonalitaet_ist_vorschlag,
        },
        status_code=status_code,
    )


async def _ableiten_antwort(request: Request, *, modus: str, dateiname: str | None, werte: dict):
    angebot_leer = not werte["angebot"].strip()
    tonalitaet_leer = not werte["tonalitaet"].strip()

    try:
        ki = _hole_ki(request)
        text = fetch_text(werte["webseite"].strip())
        entwurf = draft_offer(text, ki)
    except Exception:
        return _formular_antwort(
            request, modus=modus, dateiname=dateiname, werte=werte, fehler=ABLEITEN_FEHLER,
        )

    neue_werte = dict(werte)
    angebot_wird_vorschlag = angebot_leer and bool(entwurf.get("angebot"))
    tonalitaet_wird_vorschlag = tonalitaet_leer and bool(entwurf.get("tonalitaet"))
    if angebot_wird_vorschlag:
        neue_werte["angebot"] = entwurf["angebot"]
    if tonalitaet_wird_vorschlag:
        neue_werte["tonalitaet"] = entwurf["tonalitaet"]

    hinweis = VORSCHLAG_HINWEIS if (angebot_wird_vorschlag or tonalitaet_wird_vorschlag) else None

    return _formular_antwort(
        request, modus=modus, dateiname=dateiname, werte=neue_werte,
        vorschlag_hinweis=hinweis,
        angebot_ist_vorschlag=angebot_wird_vorschlag,
        tonalitaet_ist_vorschlag=tonalitaet_wird_vorschlag,
    )


# Routen -------------------------------------------------------------------

@router.get("/kunden")
async def kunden_liste(request: Request):
    daten_dir = request.app.state.daten_dir
    dateien = sorted(_kunden_dir(daten_dir).glob("*.yaml"))
    kunden = [e for e in (_liste_eintrag(p) for p in dateien) if e is not None]
    return request.app.state.templates.TemplateResponse(
        request,
        "kunden_liste.html",
        {
            "nutzer": auth.aktueller_nutzer(request),
            "nav": nav_kontext(request),
            "kunden": kunden,
        },
    )


@router.get("/kunden/neu")
async def kunde_neu_formular(request: Request):
    return _formular_antwort(request, modus="neu", dateiname=None, werte=dict(LEERE_WERTE))


@router.get("/kunden/{dateiname}/bearbeiten")
async def kunde_bearbeiten_formular(request: Request, dateiname: str):
    pfad = _kunden_dir(request.app.state.daten_dir) / f"{dateiname}.yaml"
    if not pfad.exists():
        raise HTTPException(status_code=404, detail="Kunde nicht gefunden.")
    kunde = load_kunde(pfad)
    return _formular_antwort(
        request, modus="bearbeiten", dateiname=dateiname, werte=_werte_aus_kunde(kunde),
    )


@router.post("/kunden/neu")
async def kunde_neu_speichern(
    request: Request,
    name: str = Form(""), webseite: str = Form(""),
    zielgruppe_titel: str = Form(""), zielgruppe_region: str = Form(""),
    zielgruppe_firmengroesse: str = Form(""),
    angebot: str = Form(""), tonalitaet: str = Form(""), absender: str = Form(""),
    follow_up_tag_1: str = Form(""), follow_up_tag_2: str = Form(""),
    test_empfaenger: str = Form(""), sperrliste: str = Form(""),
):
    werte = dict(
        name=name, webseite=webseite,
        zielgruppe_titel=zielgruppe_titel, zielgruppe_region=zielgruppe_region,
        zielgruppe_firmengroesse=zielgruppe_firmengroesse,
        angebot=angebot, tonalitaet=tonalitaet, absender=absender,
        follow_up_tag_1=follow_up_tag_1, follow_up_tag_2=follow_up_tag_2,
        test_empfaenger=test_empfaenger, sperrliste=sperrliste,
    )
    daten = _daten_fuer_load_kunde(werte)
    kunden_dir = _kunden_dir(request.app.state.daten_dir)
    dateiname = _freier_dateiname(kunden_dir, _slug(werte["name"]))
    try:
        _validieren_und_speichern(kunden_dir, dateiname, daten)
    except ValueError as fehler:
        return _formular_antwort(
            request, modus="neu", dateiname=None, werte=werte,
            fehler=str(fehler), status_code=400,
        )
    return RedirectResponse("/kunden", status_code=303)


@router.post("/kunden/{dateiname}/bearbeiten")
async def kunde_bearbeiten_speichern(
    request: Request, dateiname: str,
    name: str = Form(""), webseite: str = Form(""),
    zielgruppe_titel: str = Form(""), zielgruppe_region: str = Form(""),
    zielgruppe_firmengroesse: str = Form(""),
    angebot: str = Form(""), tonalitaet: str = Form(""), absender: str = Form(""),
    follow_up_tag_1: str = Form(""), follow_up_tag_2: str = Form(""),
    test_empfaenger: str = Form(""), sperrliste: str = Form(""),
):
    werte = dict(
        name=name, webseite=webseite,
        zielgruppe_titel=zielgruppe_titel, zielgruppe_region=zielgruppe_region,
        zielgruppe_firmengroesse=zielgruppe_firmengroesse,
        angebot=angebot, tonalitaet=tonalitaet, absender=absender,
        follow_up_tag_1=follow_up_tag_1, follow_up_tag_2=follow_up_tag_2,
        test_empfaenger=test_empfaenger, sperrliste=sperrliste,
    )
    daten = _daten_fuer_load_kunde(werte)
    kunden_dir = _kunden_dir(request.app.state.daten_dir)
    try:
        _validieren_und_speichern(kunden_dir, dateiname, daten)
    except ValueError as fehler:
        return _formular_antwort(
            request, modus="bearbeiten", dateiname=dateiname, werte=werte,
            fehler=str(fehler), status_code=400,
        )
    return RedirectResponse("/kunden", status_code=303)


@router.post("/kunden/neu/ableiten")
async def kunde_neu_ableiten(
    request: Request,
    name: str = Form(""), webseite: str = Form(""),
    zielgruppe_titel: str = Form(""), zielgruppe_region: str = Form(""),
    zielgruppe_firmengroesse: str = Form(""),
    angebot: str = Form(""), tonalitaet: str = Form(""), absender: str = Form(""),
    follow_up_tag_1: str = Form(""), follow_up_tag_2: str = Form(""),
    test_empfaenger: str = Form(""), sperrliste: str = Form(""),
):
    werte = dict(
        name=name, webseite=webseite,
        zielgruppe_titel=zielgruppe_titel, zielgruppe_region=zielgruppe_region,
        zielgruppe_firmengroesse=zielgruppe_firmengroesse,
        angebot=angebot, tonalitaet=tonalitaet, absender=absender,
        follow_up_tag_1=follow_up_tag_1, follow_up_tag_2=follow_up_tag_2,
        test_empfaenger=test_empfaenger, sperrliste=sperrliste,
    )
    return await _ableiten_antwort(request, modus="neu", dateiname=None, werte=werte)


@router.post("/kunden/{dateiname}/ableiten")
async def kunde_bearbeiten_ableiten(
    request: Request, dateiname: str,
    name: str = Form(""), webseite: str = Form(""),
    zielgruppe_titel: str = Form(""), zielgruppe_region: str = Form(""),
    zielgruppe_firmengroesse: str = Form(""),
    angebot: str = Form(""), tonalitaet: str = Form(""), absender: str = Form(""),
    follow_up_tag_1: str = Form(""), follow_up_tag_2: str = Form(""),
    test_empfaenger: str = Form(""), sperrliste: str = Form(""),
):
    werte = dict(
        name=name, webseite=webseite,
        zielgruppe_titel=zielgruppe_titel, zielgruppe_region=zielgruppe_region,
        zielgruppe_firmengroesse=zielgruppe_firmengroesse,
        angebot=angebot, tonalitaet=tonalitaet, absender=absender,
        follow_up_tag_1=follow_up_tag_1, follow_up_tag_2=follow_up_tag_2,
        test_empfaenger=test_empfaenger, sperrliste=sperrliste,
    )
    return await _ableiten_antwort(request, modus="bearbeiten", dateiname=dateiname, werte=werte)
