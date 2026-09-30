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
    # Nachgetragen am 03.09.2026 fuer den Gelbe-Seiten-Nachschlag. Die
    # Maps-Sammlung vom 21.08. lief noch ueber den alten Bielefeld-Kreis.
    # Schieder-Schwalenberg (32816) im Suedosten, 39,9 km weit.
    "32": {"mitte": (52.14, 8.80), "radius": 42, "stadt": "Herford",
           "plz": "plz-liste-oliver-zona32.txt",
           "lauf": "zona32-herford-2026-08-21"},
    # Nachgetragen am 03.09.2026: Zone 33 wurde am 25.08. nur ueber Maps
    # gesammelt, Overpass lief dort nie. Fuer den freien Nachschlag
    # braucht sie denselben Kreis wie die anderen.
    # Brakel (33034) im Suedosten, 46,3 km weit.
    "33": {"mitte": (51.89, 8.58), "radius": 48, "stadt": "Bielefeld",
           "plz": "plz-liste-oliver-zona33.txt",
           "lauf": "zona33-bielefeld-2026-08-25"},
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
    # Zones 40-69 are cities, not whole postal regions, and their codes come
    # from the corrected list (daten/plz-liste-oliver-40-69-corrected.csv,
    # 29.09.2026). Zone 40 is Duesseldorf with Ratingen, Mettmann, Hilden,
    # Langenfeld, Monheim and Meerbusch; Langenfeld (40764) in the south is
    # the farthest, 16.6 km away.
    "40": {"mitte": (51.23, 6.81), "radius": 19, "stadt": "Düsseldorf",
           "plz": "plz-liste-oliver-zona40.txt",
           "lauf": "zona40-duesseldorf-2026-09-29"},
    # Zone 41 is four towns, and one circle around all of them (21 km)
    # would reach into central Duesseldorf - its places would use up the
    # 110 per search word before Moenchengladbach is done. So one circle per
    # town, each covering its farthest code (MG 6.2 km, Neuss 4.6 km,
    # Dormagen 2.6 km; Kaarst has one code, its circle covers the town).
    # "maps_dazu": the Maps run of zone 40 (29.09.2026) already paid for
    # 99 places in Neuss, Kaarst and Dormagen - they are read as well.
    "41": {"kreise": [
               {"ort": "Mönchengladbach", "mitte": (51.18, 6.43), "radius": 8},
               # 7 km, not 5.5: the coordinate table put 41470 (Uedesheim,
               # Grimlinghausen) on the town centre, so it looked covered.
               # Its real centre is 5.7 km out - corrected on 29.09.2026.
               {"ort": "Neuss", "mitte": (51.19, 6.70), "radius": 7},
               {"ort": "Kaarst", "mitte": (51.23, 6.62), "radius": 4},
               {"ort": "Dormagen", "mitte": (51.11, 6.81), "radius": 5}],
           "stadt": "Mönchengladbach",
           "plz": "plz-liste-oliver-zona41.txt",
           "lauf": "zona41-moenchengladbach-2026-09-29",
           "maps_dazu": ["apify-ds-5gLzrkb4NPjyijWbG.json"]},
    # Zone 42 is the three towns of the Bergisches Land, one circle each
    # around its own codes (Wuppertal 8.3 km, Solingen 4.2 km, Remscheid
    # 4.0 km). The zone 40 run already paid for 108 places in Solingen and
    # west Wuppertal - read as well.
    "42": {"kreise": [
               {"ort": "Wuppertal", "mitte": (51.26, 7.16), "radius": 10},
               {"ort": "Solingen", "mitte": (51.17, 7.06), "radius": 6},
               {"ort": "Remscheid", "mitte": (51.19, 7.21), "radius": 6}],
           "stadt": "Wuppertal",
           "plz": "plz-liste-oliver-zona42.txt",
           "lauf": "zona42-wuppertal-2026-09-29",
           "maps_dazu": ["apify-ds-5gLzrkb4NPjyijWbG.json"]},
    # Zone 43 does not exist: no German postal code starts with 43.
    # Zone 44 is Dortmund and Bochum, 18 km apart - one circle each around
    # its own codes (Dortmund 9.3 km, Bochum 6.8 km). No earlier run
    # reached them, so there is nothing to reuse.
    "44": {"kreise": [
               {"ort": "Dortmund", "mitte": (51.51, 7.47), "radius": 11},
               {"ort": "Bochum", "mitte": (51.47, 7.22), "radius": 8.5}],
           "stadt": "Dortmund",
           "plz": "plz-liste-oliver-zona44.txt",
           "lauf": "zona44-dortmund-2026-09-29"},
    # Zone 45 is Essen and Gelsenkirchen, only 10 km apart - one circle
    # each (Essen covers its codes at 8.3 km, Gelsenkirchen at 7.9). The
    # two circles overlap, and that is still the cheaper shape: a single
    # circle around both would need 17 km and would pay for 816 km2 of
    # map instead of 598, most of it outside the zone (Bochum, Oberhausen,
    # Gladbeck). Places two paid runs already found here - 30 from zone 40
    # and 10 from zone 44 - are read from their datasets, not bought again.
    "45": {"kreise": [
               # 11.5 km, not 10: the coordinate table put 45219 (Kettwig)
               # on the town centre, so it looked covered. Its real centre
               # is 10.4 km south - corrected on 29.09.2026.
               {"ort": "Essen", "mitte": (51.45, 7.02), "radius": 11.5},
               {"ort": "Gelsenkirchen", "mitte": (51.54, 7.08), "radius": 9.5}],
           "stadt": "Essen",
           "plz": "plz-liste-oliver-zona45.txt",
           "lauf": "zona45-essen-2026-09-29",
           "maps_dazu": ["apify-ds-5gLzrkb4NPjyijWbG.json",
                         "apify-ds-S6QcmCYDi5zf0N1dq.json"]},
    # Zone 46 does not exist in Oliver's list - it jumps from 45 to 47, the
    # same way it skips 43. Do not add one without asking him first.
    # Zone 47 is Duisburg and Krefeld, 18 km apart, so one circle each.
    # Duisburg gets a third, small one: its postal codes reach up to
    # Walsum (47178), whose centre sits 12.1 km out - measured against the
    # postal code areas in OpenStreetMap, not guessed. Widening the main
    # circle to 14 km would cover it but would pay for 615 km2 of map
    # instead of 380, nearly all of it Oberhausen, Moers and Dinslaken,
    # outside the zone. A 4 km circle over Walsum costs 50 km2 instead.
    # 56 places inside this zone were already paid for by zone 40's run and
    # are read from its dataset instead of being bought again.
    "47": {"kreise": [
               {"ort": "Duisburg", "mitte": (51.44, 6.76), "radius": 11},
               {"ort": "Duisburg-Walsum", "mitte": (51.5442, 6.7119),
                "radius": 4},
               {"ort": "Krefeld", "mitte": (51.335, 6.565), "radius": 8}],
           "stadt": "Duisburg",
           "plz": "plz-liste-oliver-zona47.txt",
           "lauf": "zona47-duisburg-2026-09-29",
           "maps_dazu": ["apify-ds-5gLzrkb4NPjyijWbG.json"]},
}


def zone(nummer: str) -> dict:
    """Die Zone zu "34", "35" ... - unbekannt ist ein Fehler, keine Stille."""
    nummer = str(nummer).strip()
    if nummer not in ZONEN:
        raise KeyError(
            f"Zone {nummer!r} steht nicht in der Tabelle. Bekannt sind: "
            f"{', '.join(sorted(ZONEN))}")
    return ZONEN[nummer]


def kreise(nummer: str) -> list:
    """[(mitte, radius_km), ...] - one circle for zones 32-40, one per town
    for a zone of several towns ("kreise")."""
    eintrag = zone(nummer)
    if "kreise" in eintrag:
        return [(k["mitte"], k["radius"]) for k in eintrag["kreise"]]
    return [(eintrag["mitte"], eintrag["radius"])]


def suchgebiet(nummer: str) -> dict:
    """The search area as Apify takes it: the same polygon as always for a
    single circle, a MultiPolygon for several (supported by the actor, see
    its README "Custom search area", checked 29.09.2026)."""
    polygone = [kreis_polygon(*mitte, radius) for mitte, radius in kreise(nummer)]
    if len(polygone) == 1:
        return polygone[0]
    return {"type": "MultiPolygon",
            "coordinates": [p["coordinates"] for p in polygone]}


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
