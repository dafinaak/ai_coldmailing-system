"""Turn a German postal code or town name into a point on the map.

The lead sources we use (Google Maps, Gelbe Seiten, OpenStreetMap) all
know where a company sits, but our fusion step only kept the postal
code - the coordinates were thrown away. Rather than re-scrape
everything, a company is placed at the centre of its postal code. That
is accurate to a few kilometres, which is what a search like "IT
companies within 30 km of Hannover" actually needs.

The table (pipeline/daten/plz_koordinaten.csv, 10813 rows) comes from
the free GeoNames postal code export. One row per postal code: the
averaged point of all places sharing it, plus a town name for display.

Nothing here talks to the network.
"""

from __future__ import annotations

import csv
import math
import re
from functools import lru_cache
from pathlib import Path

TABELLE = Path(__file__).parent / "daten" / "plz_koordinaten.csv"
ERDRADIUS_KM = 6371.0


@lru_cache(maxsize=1)
def plz_tabelle(pfad: str | None = None) -> dict:
    """{plz: {"ort", "lat", "lon"}} - read once, then kept in memory."""
    quelle = Path(pfad) if pfad else TABELLE
    if not quelle.exists():
        raise FileNotFoundError(
            f"Die Postleitzahlen-Tabelle fehlt: {quelle}. Ohne sie kann der "
            f"Umkreis nicht berechnet werden.")
    tabelle = {}
    with quelle.open(encoding="utf-8") as f:
        for zeile in csv.DictReader(f):
            tabelle[zeile["plz"]] = {
                "ort": zeile["ort"],
                "lat": float(zeile["lat"]),
                "lon": float(zeile["lon"]),
            }
    return tabelle


def entfernung_km(punkt_a: tuple, punkt_b: tuple) -> float:
    """Great-circle distance between two (lat, lon) points."""
    lat1, lon1 = math.radians(punkt_a[0]), math.radians(punkt_a[1])
    lat2, lon2 = math.radians(punkt_b[0]), math.radians(punkt_b[1])
    d_lat, d_lon = lat2 - lat1, lon2 - lon1
    a = (math.sin(d_lat / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin(d_lon / 2) ** 2)
    return 2 * ERDRADIUS_KM * math.asin(math.sqrt(a))


def punkt_fuer_plz(plz: object, pfad: str | None = None) -> tuple | None:
    """(lat, lon) for a postal code, or None if it is unknown."""
    schluessel = re.sub(r"\D", "", str(plz or ""))
    if len(schluessel) != 5:
        return None
    eintrag = plz_tabelle(pfad).get(schluessel)
    return (eintrag["lat"], eintrag["lon"]) if eintrag else None


def punkt_fuer_ort(name: str, pfad: str | None = None) -> tuple | None:
    """(lat, lon) for a town name - the mean of all its postal codes.

    A town like Hannover covers dozens of postal codes; their midpoint
    is a better centre for a radius than whichever one happens to be
    listed first.
    """
    gesucht = _vergleichbar(name)
    if not gesucht:
        return None
    treffer = [e for e in plz_tabelle(pfad).values()
               if _vergleichbar(e["ort"]) == gesucht]
    if not treffer:
        treffer = [e for e in plz_tabelle(pfad).values()
                   if gesucht in _vergleichbar(e["ort"])]
    if not treffer:
        return None
    return (sum(e["lat"] for e in treffer) / len(treffer),
            sum(e["lon"] for e in treffer) / len(treffer))


def mittelpunkt(eingabe: str, pfad: str | None = None) -> tuple | None:
    """Centre of a search: accepts a postal code or a town name."""
    text = str(eingabe or "").strip()
    if not text:
        return None
    return punkt_fuer_plz(text, pfad) or punkt_fuer_ort(text, pfad)


def _vergleichbar(text: object) -> str:
    ohne = re.sub(r"[^\wäöüß ]", " ", str(text or "").casefold())
    return " ".join(ohne.split())
