"""Bundesland zu einer Postleitzahl - nachgeschlagen, nicht geraten.

Olivers DataWarehouse-Liste verlangt ein Feld "Bundesland". Es aus den
ersten zwei Ziffern abzuleiten waere schnell und in unseren eigenen Zonen
falsch: 34117 (Kassel) ist Hessen, 34414 (Warburg) und 34434
(Borgentreich) sind Nordrhein-Westfalen. Alle drei stehen in den Daten
der Zone 34.

Deshalb wird einmal beim oeffentlichen deutschen Postleitzahlen-Register
nachgefragt und die Antwort in daten/plz-bundesland.json gespeichert.
Danach ist es ein reiner Nachschlag ohne Netz - der Neubau von master.db
geht NIE ins Netz, sonst haenge ein Neubau an einer fremden Verfuegbarkeit
(Projektregel: Zuverlaessigkeit zuerst).

Was nicht eindeutig ist - eine Postleitzahl ueber zwei Bundeslaender -
bleibt leer. Ein falsches Bundesland ist schlechter als ein leeres Feld.
"""
from __future__ import annotations

import json
from pathlib import Path

SPEICHER_NAME = "daten/plz-bundesland.json"
REGISTER_URL = "https://openplzapi.org/de/Localities"


def plz_normal(wert: object) -> str:
    """' 34117 ' und 34117 als Zahl sind dieselbe Postleitzahl."""
    text = str(wert or "").strip()
    return text if text.isdigit() and len(text) == 5 else ""


def nachschlagen(plz: object, speicher: dict) -> str:
    """Bundesland aus dem Speicher. Unbekannt -> leer, nie geraten."""
    return speicher.get(plz_normal(plz), "") if plz_normal(plz) else ""


def speicher_lesen(daten_dir) -> dict:
    pfad = Path(daten_dir) / SPEICHER_NAME
    if not pfad.exists():
        return {}
    try:
        inhalt = json.loads(pfad.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return inhalt if isinstance(inhalt, dict) else {}


def speicher_schreiben(daten_dir, speicher: dict) -> None:
    pfad = Path(daten_dir) / SPEICHER_NAME
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(json.dumps(speicher, ensure_ascii=False, indent=1,
                               sort_keys=True), encoding="utf-8")


def aus_orten(orte) -> str:
    """Antwort des Registers -> ein Bundesland oder leer.

    Das Register liefert je Postleitzahl alle Orte. Liegen die in
    verschiedenen Bundeslaendern, wird nichts behauptet.
    """
    laender = {(ort or {}).get("federalState", {}).get("name")
               for ort in (orte or [])}
    laender.discard(None)
    return laender.pop() if len(laender) == 1 else ""


def _holen(plz: str) -> str:
    """Eine Abfrage beim oeffentlichen Register. Nur hier faellt Netz an."""
    import requests

    antwort = requests.get(REGISTER_URL, params={"postalCode": plz},
                           timeout=30)
    antwort.raise_for_status()
    return aus_orten(antwort.json())


def speicher_fuellen(daten_dir, plz_liste, holen=None, log=None) -> dict:
    """Fragt NUR die unbekannten Postleitzahlen ab und speichert sie.

    Eine fehlgeschlagene Abfrage wird nicht gespeichert: sonst setzte sich
    ein Netzfehler als "kein Bundesland" fest und das Feld bliebe fuer
    immer leer, obwohl es eine Antwort gaebe.
    """
    holen = holen or _holen
    speicher = speicher_lesen(daten_dir)
    offen = sorted({p for p in (plz_normal(x) for x in plz_liste)
                    if p and p not in speicher})
    if log:
        log(f"bekannt: {len(speicher)}, te reja per te pyetur: {len(offen)}")

    for nummer, plz in enumerate(offen, 1):
        try:
            speicher[plz] = holen(plz)
        except Exception as fehler:              # noqa: BLE001
            if log:
                log(f"    {plz}: s'u mor ({fehler})")
            continue
        if log and nummer % 100 == 0:
            log(f"    ... {nummer}/{len(offen)}")
        if nummer % 100 == 0:
            speicher_schreiben(daten_dir, speicher)   # kunder humbjes

    speicher_schreiben(daten_dir, speicher)
    return speicher
