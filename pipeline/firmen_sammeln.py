"""Firmen fuer einen Umkreis frisch sammeln.

Die Bruecke zwischen dem, was das Formular fragt ("Hannover, 25 km,
Webdesigner"), und den Quellen-Bausteinen, die es schon gibt: Google Maps
ueber Apify, Gelbe Seiten ueber Apify, OpenStreetMap ueber Overpass -
zusammengefuehrt von pipeline.listen_fusion.

Warum es das braucht (17.08.2026): Der gesammelte Bestand deckt nur die
Postleitregionen 30 und 31 ab, also den Raum Hannover. Fuer jede andere
Stadt lieferte Schritt 4 des Formulars schlicht null Firmen - das Werkzeug
konnte nur eine einzige Region bedienen.

Kosten: Die beiden Apify-Aktoren rechnen pro Lauf ab. Die Sammlung vom
29.07.2026 kostete rund sieben Dollar fuer zwei Postleitregionen. Deshalb
sammelt niemand automatisch - der Mensch waehlt es in Schritt 3
ausdruecklich (siehe web.routen.assistent).

Das Ergebnis wird als eigener Ordner unter laeufe/leadquellen/ abgelegt.
Aeltere Sammlungen bleiben unangetastet; zusammengefuehrt wird erst beim
Lesen (web.routen.assistent._firmen_bestand).
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from pipeline.listen_fusion import fusionieren
from pipeline.plz_geo import entfernung_km, plz_tabelle

# Ein Kreis wird als Vieleck angenaehert - der Maps-Actor will ein
# Polygon. 24 Ecken sind auf Stadtgroesse vom Kreis nicht zu unterscheiden.
_ECKEN = 24
# Grad pro Kilometer in Nord-Sued-Richtung (die Erde als Kugel gerechnet).
_GRAD_PRO_KM = 1 / 111.32


def plz_im_umkreis(ort: str, radius_km: float, tabelle=None) -> list[str]:
    """Alle Postleitzahlen, deren Mittelpunkt im Umkreis liegt."""
    tabelle = tabelle if tabelle is not None else plz_tabelle()
    zentrum = _zentrum(ort, tabelle)
    if zentrum is None:
        raise ValueError(
            f"Den Ort {ort!r} kennen wir nicht - bitte einen Ortsnamen oder "
            f"eine Postleitzahl angeben.")
    treffer = []
    for plz, eintrag in tabelle.items():
        if entfernung_km(zentrum, (eintrag["lat"], eintrag["lon"])) <= radius_km:
            treffer.append(plz)
    return sorted(treffer)


def _zentrum(ort: str, tabelle: dict):
    from pipeline.plz_geo import _vergleichbar

    eintrag = tabelle.get(str(ort).strip())
    if eintrag:
        return (eintrag["lat"], eintrag["lon"])
    gesucht = _vergleichbar(ort)
    passende = [e for e in tabelle.values() if _vergleichbar(e["ort"]) == gesucht]
    if not passende:
        return None
    return (sum(e["lat"] for e in passende) / len(passende),
            sum(e["lon"] for e in passende) / len(passende))


def kreis_geojson(zentrum: tuple, radius_km: float) -> dict:
    """Umkreis als GeoJSON-Polygon fuer den Maps-Actor."""
    lat, lon = zentrum
    # Ein Laengengrad wird zu den Polen hin kuerzer - sonst waere der Kreis
    # in Norddeutschland ein liegendes Ei.
    lon_faktor = max(math.cos(math.radians(lat)), 0.01)
    punkte = []
    for i in range(_ECKEN):
        winkel = 2 * math.pi * i / _ECKEN
        punkte.append([
            round(lon + radius_km * _GRAD_PRO_KM / lon_faktor * math.cos(winkel), 6),
            round(lat + radius_km * _GRAD_PRO_KM * math.sin(winkel), 6),
        ])
    punkte.append(punkte[0])       # GeoJSON-Ringe sind geschlossen
    return {"type": "Polygon", "coordinates": [punkte]}


def bounding_box(zentrum: tuple, radius_km: float) -> tuple:
    """(sued, west, nord, ost) - so will Overpass es."""
    lat, lon = zentrum
    lon_faktor = max(math.cos(math.radians(lat)), 0.01)
    d_lat = radius_km * _GRAD_PRO_KM
    d_lon = radius_km * _GRAD_PRO_KM / lon_faktor
    return (round(lat - d_lat, 6), round(lon - d_lon, 6),
            round(lat + d_lat, 6), round(lon + d_lon, 6))


def sammeln(ort: str, radius_km: float, dienste, *, maps=None,
            gelbe_seiten=None, overpass=None, limit_pro_suche: int = 200,
            tabelle=None) -> tuple[list, dict]:
    """Firmen im Umkreis sammeln und zu EINER Liste zusammenfuehren.

    Quellen sind einzeln uebergebbar (Tests, und damit ein Ausfall einer
    Quelle nicht die ganze Sammlung kostet). Faellt eine Quelle aus, wird
    das im Bericht vermerkt und mit den uebrigen weitergemacht - eine
    halbe Sammlung ist mehr wert als gar keine, und bezahlt ist sie ohnehin.
    """
    if not dienste:
        raise ValueError("Ohne Suchbegriffe kann nicht gesammelt werden.")
    tabelle = tabelle if tabelle is not None else plz_tabelle()
    zentrum = _zentrum(ort, tabelle)
    if zentrum is None:
        raise ValueError(
            f"Den Ort {ort!r} kennen wir nicht - bitte einen Ortsnamen oder "
            f"eine Postleitzahl angeben.")

    plz_liste = plz_im_umkreis(ort, radius_km, tabelle)
    # Die Fusion filtert ueber PLZ-PRAEFIXE, nicht ueber einzelne
    # Postleitzahlen. Aus den gefundenen PLZ die Praefixe ableiten, sonst
    # wuerde die Fusion alles als "fremde PLZ" wegwerfen.
    praefixe = sorted({p[:3] for p in plz_liste}) or [""]

    listen, fehler = [], {}

    if maps is not None:
        try:
            listen.append(maps.search_gebiet(
                list(dienste), kreis_geojson(zentrum, radius_km),
                limit_pro_suche))
        except Exception as f:      # noqa: BLE001
            fehler["maps"] = str(f)

    if gelbe_seiten is not None:
        gefunden = []
        for begriff in dienste:
            try:
                gefunden += gelbe_seiten.search(begriff, ort)
            except Exception as f:      # noqa: BLE001
                fehler.setdefault("gelbe_seiten", str(f))
        listen.append(gefunden)

    if overpass is not None:
        try:
            listen.append(overpass.search(
                tuple(praefixe), bounding_box(zentrum, radius_km)))
        except Exception as f:      # noqa: BLE001
            fehler["overpass"] = str(f)

    firmen, bericht = fusionieren(listen, praefixe)
    bericht.update({"ort": ort, "radius_km": radius_km,
                    "dienste": list(dienste), "plz_im_umkreis": len(plz_liste),
                    "plz_praefixe": praefixe, "quellen_fehler": fehler})
    return firmen, bericht


def ordnername(ort: str, radius_km: float, datum: str) -> str:
    """Sprechender, dateisystem-tauglicher Name der Sammlung."""
    sauber = "".join(c if c.isalnum() else "-" for c in str(ort).casefold())
    return f"{sauber.strip('-') or 'ort'}-{int(radius_km)}km-{datum}"


def speichern(daten_dir, firmen: list, bericht: dict, ordner_name: str) -> Path:
    """Sammlung als eigenen Ordner ablegen - aeltere bleiben unberuehrt."""
    ziel = Path(daten_dir) / "laeufe" / "leadquellen" / ordner_name
    ziel.mkdir(parents=True, exist_ok=True)
    (ziel / "firmen.json").write_text(
        json.dumps(firmen, ensure_ascii=False, indent=1), encoding="utf-8")
    (ziel / "sammelbericht.json").write_text(
        json.dumps(bericht, ensure_ascii=False, indent=1), encoding="utf-8")
    return ziel
