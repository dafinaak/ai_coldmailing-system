"""Die Zonen-Tabelle - ein Kreis je Postleitregion, fuer alle Quellen.

Bis hierher stand der Kreis einer Zone in werkzeuge/zonen-maps.py. Der
Dateiname hat einen Bindestrich, also kann ihn kein anderes Werkzeug und
kein Test importieren: das Overpass-Werkzeug und das Gelbe-Seiten-Werkzeug
haetten jeweils eine eigene Kopie der Mittelpunkte gebraucht. Drei Kopien
derselben Zahl sind der Weg, auf dem eine Zone irgendwann still mit dem
falschen Kreis gesammelt wird. Deshalb steht sie jetzt einmal hier.

Mittelpunkt und Radius sind kein Geschmack, sondern Geld:

  zu klein  - bestellte Postleitzahlen fallen aus dem Kreis, die Firmen
              dort tauchen nie auf, und niemand merkt es;
  zu gross  - Apify zahlt je gefundenem Ort, auch fuer Orte weit ausserhalb
              der Zone. Bezahlte Flaeche, die uns nichts bringt.

Die Radien sind deshalb so gewaehlt, dass sie die aeusserste bestellte
Postleitzahl gerade noch decken - gemessen am Vieleck, nicht am Kreis
(siehe kreis_polygon). tests/test_zonen.py prueft beide Richtungen.

Zone 37 faellt mit 67 km aus der Reihe: die Region Goettingen zieht sich
bis Herleshausen (37293) im Suedosten, rund 65 km vom Mittelpunkt. Der
Kreis muss mit, also wird dort mehr Umland mitbezahlt als in den anderen
Zonen. Nicht zu aendern, ohne Postleitzahlen fallen zu lassen.

"stadt" ist der Ortsname fuer Gelbe Seiten. Der Actor sucht nach Ort, nicht
nach Flaeche - stuende dort "Deutschland", liefe die Suche ueber das ganze
Land und kostete ein Vielfaches.
"""
from __future__ import annotations

import math
from pathlib import Path

PROJEKT = Path(__file__).resolve().parent.parent
PLZ_ORDNER = PROJEKT / "laeufe" / "leadquellen"

# Der Kreis geht als Vieleck an Apify. 24 Ecken sind der Stand seit dem
# ersten Zonen-Lauf (21.08.2026) - die Zahl steht hier, weil die Tests
# damit rechnen muessen, wie tief das Vieleck in den Kreis einschneidet.
POLYGON_PUNKTE = 24

# Dieselben Suchbegriffe wie am 21.08.2026, damit jede Zone nach demselben
# Kriterium gesammelt wird und die Listen vergleichbar bleiben. Sie stehen
# hier und nicht im Maps-Werkzeug, weil Gelbe Seiten dieselben Begriffe
# braucht: nur dann heisst "Gelbe Seiten kennt diese Firma und Maps nicht"
# wirklich, dass die Quelle mehr weiss - und nicht bloss, dass anders
# gesucht wurde.
SUCHBEGRIFFE = [
    "IT-Dienstleister", "IT-Service", "Computerservice", "IT-Systemhaus",
    "EDV-Dienstleistungen", "IT-Support", "Netzwerktechnik",
    "Softwareentwicklung", "IT-Sicherheit", "Cloud-Dienstleistungen",
]

ZONEN = {
    # Willingen (34508) im Westen, Bad Karlshafen (34385) im Norden,
    # Ottrau (34633) im Sueden - die aeusserste liegt 50,3 km weit.
    "34": {"mitte": (51.25, 9.25), "radius": 52, "stadt": "Kassel",
           "plz": "plz-liste-oliver-zona34.txt",
           "lauf": "zona34-kassel-2026-08-28"},
    # Lichtenfels (35104) im Norden, Hungen (35410) im Sueden,
    # Breidenbach (35236) im Westen; die aeusserste liegt 38,8 km weit.
    "35": {"mitte": (50.81, 8.83), "radius": 48, "stadt": "Gießen",
           "plz": "plz-liste-oliver-zona35.txt",
           "lauf": "zona35-giessen-2026-08-28"},
    # Steinau an der Straße (36396) im Suedwesten, 46,6 km weit.
    "36": {"mitte": (50.70, 9.72), "radius": 49, "stadt": "Fulda",
           "plz": "plz-liste-oliver-zona36.txt",
           "lauf": "zona36-fulda-2026-09-01"},
    # Herleshausen (37293) im Suedosten, 64,8 km weit - siehe Kopf.
    "37": {"mitte": (51.57, 9.93), "radius": 67, "stadt": "Göttingen",
           "plz": "plz-liste-oliver-zona37.txt",
           "lauf": "zona37-goettingen-2026-09-01"},
    # Jeeben (38489) im Nordosten, 50,8 km weit.
    "38": {"mitte": (52.28, 10.65), "radius": 53, "stadt": "Braunschweig",
           "plz": "plz-liste-oliver-zona38.txt",
           "lauf": "zona38-braunschweig-2026-09-01"},
    # Wegenstedt (39359) im Nordwesten, 32,8 km weit.
    "39": {"mitte": (52.17, 11.50), "radius": 35, "stadt": "Magdeburg",
           "plz": "plz-liste-oliver-zona39.txt",
           "lauf": "zona39-magdeburg-2026-09-01"},
}


def zone(nummer: str) -> dict:
    """Die Zone zu "34", "35" ... - unbekannt ist ein Fehler, keine Stille."""
    nummer = str(nummer).strip()
    if nummer not in ZONEN:
        raise KeyError(
            f"Zone {nummer!r} steht nicht in der Tabelle. Bekannt sind: "
            f"{', '.join(sorted(ZONEN))}")
    return ZONEN[nummer]


def plz_datei(nummer: str) -> Path:
    return PLZ_ORDNER / zone(nummer)["plz"]


def plz_kodes(nummer: str) -> list:
    """Die bestellten Postleitzahlen der Zone. Leerzeilen und Kommentare
    fallen raus; alles andere muss eine fuenfstellige Zahl sein - eine
    schiefe Zeile ist ein Fehler und kein stilles Ueberspringen, sonst
    faellt eine bestellte Postleitzahl unbemerkt weg."""
    datei = plz_datei(nummer)
    if not datei.exists():
        raise FileNotFoundError(f"PLZ-Liste fehlt: {datei}")
    kodes = []
    for nr, zeile in enumerate(datei.read_text(encoding="utf-8").splitlines(), 1):
        text = zeile.strip()
        if not text or text.startswith("#"):
            continue
        if not (len(text) == 5 and text.isdigit()):
            raise ValueError(f"{datei.name} Zeile {nr}: {text!r} ist keine PLZ")
        kodes.append(text)
    return kodes


def kreis_polygon(lat: float, lon: float, radius_km: float,
                  punkte: int = POLYGON_PUNKTE) -> dict:
    """Kreis als GeoJSON-Vieleck, so wie Apify es erwartet.

    Das Vieleck liegt IM Kreis: in der Mitte einer Kante ist es
    cos(pi/punkte) mal so weit vom Mittelpunkt entfernt wie an einer Ecke.
    Bei 24 Ecken sind das rund 0,7 % weniger - deshalb rechnen die Tests
    mit dieser Zahl und nicht mit dem vollen Radius."""
    grad_lat = radius_km / 111.32
    grad_lon = radius_km / (111.32 * math.cos(math.radians(lat)))
    ring = []
    for nummer in range(punkte):
        winkel = 2 * math.pi * nummer / punkte
        ring.append([round(lon + grad_lon * math.cos(winkel), 6),
                     round(lat + grad_lat * math.sin(winkel), 6)])
    ring.append(ring[0])                      # der Ring muss sich schliessen
    return {"type": "Polygon", "coordinates": [ring]}
