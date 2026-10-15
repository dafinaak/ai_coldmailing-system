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
    # Zone 48 is Munster alone, 13 codes that all sit inside 7 km of their
    # middle - one circle is enough, and no earlier run reaches up here,
    # so there is nothing to reuse.
    "48": {"kreise": [
               {"ort": "Münster", "mitte": (51.954, 7.629), "radius": 8}],
           "stadt": "Münster",
           "plz": "plz-liste-oliver-zona48.txt",
           "lauf": "zona48-muenster-2026-09-30"},
    # Zones 50, 51 and 52 - the list continues in order from 07.10.2026.
    # Three is what the 96 remaining Dropcontact credits stretch to.
    #
    # Cologne gets two circles for the same reason Duisburg did: three
    # codes (50765, 50767, 50769 - Chorweiler and around) sit up to 12 km
    # north of the rest. One circle would have to be 14.3 km and would pay
    # for 642 km2 of map; a 11 km circle plus a small one over the north
    # covers the same codes with 412 km2.
    #
    # 50919, 50960 and 50962 stay in the code list but steer no circle:
    # they are Sonder-PLZ (PO box / large customer), so they have no area
    # on the map at all - the same case as 47118 in Duisburg.
    "50": {"kreise": [
               {"ort": "Köln", "mitte": (50.9346, 6.9283), "radius": 11},
               {"ort": "Köln-Chorweiler", "mitte": (51.023, 6.8764),
                "radius": 3.5}],
           "stadt": "Köln",
           "plz": "plz-liste-oliver-zona50.txt",
           "lauf": "zona50-koeln-2026-10-07"},
    # Zone 50's paid run already found 161 places inside zone 51 - the two
    # halves of Cologne overlap - so its dataset is read here instead of
    # being bought a second time.
    "51": {"kreise": [
               {"ort": "Köln-Ost", "mitte": (50.9268, 7.0447), "radius": 10},
               {"ort": "Leverkusen", "mitte": (51.0493, 7.0142),
                "radius": 5.5}],
           "stadt": "Köln",
           "plz": "plz-liste-oliver-zona51.txt",
           "lauf": "zona51-koeln-ost-2026-10-07",
           # Zweiter Eintrag: der erste Versuch am 07.10.2026 lief in die
           # Geldbremse (2,50 USD) und gilt damit als unvollstaendig - die
           # 834 schon bezahlten Orte werden trotzdem mitgelesen, damit
           # der volle Lauf sie nicht umsonst gemacht hat.
           "maps_dazu": ["apify-ds-j9JNWNkUuoRczYnwK.json",
                         "apify-ds-Hy9lX3YjkSRYtBJc4.json"]},
    "52": {"kreise": [
               {"ort": "Aachen", "mitte": (50.7677, 6.1029), "radius": 8}],
           "stadt": "Aachen",
           "plz": "plz-liste-oliver-zona52.txt",
           "lauf": "zona52-aachen-2026-10-07"},
    "53": {"kreise": [
               {"ort": "Bonn", "mitte": (50.7225, 7.1158), "radius": 9.5}],
           "stadt": "Bonn",
           "plz": "plz-liste-oliver-zona53.txt",
           "lauf": "zona53-bonn-2026-10-07"},
    # One circle covers Mainz and the single Wiesbaden code with it - the
    # two centres are 4.5 km apart, so a second circle would only pay for
    # the same ground twice. 55118 and 55127 sat on the town centre in the
    # coordinate table; measured against OSM on 07.10.2026 and corrected,
    # 55127 really lies 4.7 km out. Both stay inside this circle.
    "55": {"kreise": [
               {"ort": "Mainz", "mitte": (49.9949, 8.2566), "radius": 7.2}],
           "stadt": "Mainz",
           "plz": "plz-liste-oliver-zona55.txt",
           "lauf": "zona55-mainz-2026-10-07"},
    # --- Dekade 60-69, alle acht Zonen am 07.10.2026 ---
    #
    # Zwei davon werden bewusst in zwei Kreise geteilt, weil ihre Staedte
    # weit auseinander liegen und ein einzelner Kreis fast nur leeres Feld
    # dazwischen bezahlen wuerde:
    #   Zone 65  ein Kreis 1.521 km2  ->  zwei Kreise 325 km2
    #   Zone 67  ein Kreis 4.072 km2  ->  zwei Kreise 187 km2
    #
    # Und zwei Radien sind groesser, als die Koordinatentabelle nahegelegt
    # haette: in Zone 66 sassen acht Codes und in Zone 68 vier Codes auf
    # dem Stadtmittelpunkt. Gegen OSM gemessen liegen sie bis 9,0 bzw.
    # 9,5 km draussen - mit den alten Werten waeren fuenf Codes gar nicht
    # abgesucht worden (derselbe Fehler wie 41470 und 45219 am 29.09.).
    "60": {"kreise": [
               {"ort": "Frankfurt am Main", "mitte": (50.1174, 8.6607),
                "radius": 13.7}],
           "stadt": "Frankfurt am Main",
           "plz": "plz-liste-oliver-zona60.txt",
           "lauf": "zona60-frankfurt-2026-10-07"},
    "63": {"kreise": [
               {"ort": "Offenbach am Main", "mitte": (50.104, 8.765),
                "radius": 3.9}],
           "stadt": "Offenbach am Main",
           "plz": "plz-liste-oliver-zona63.txt",
           "lauf": "zona63-offenbach-2026-10-07"},
    "64": {"kreise": [
               {"ort": "Darmstadt", "mitte": (49.8718, 8.6533),
                "radius": 7.2}],
           "stadt": "Darmstadt",
           "plz": "plz-liste-oliver-zona64.txt",
           "lauf": "zona64-darmstadt-2026-10-07"},
    "65": {"kreise": [
               {"ort": "Wiesbaden", "mitte": (50.0778, 8.2453),
                "radius": 8.8},
               {"ort": "Frankfurt-West", "mitte": (50.1034, 8.5569),
                "radius": 5.1}],
           "stadt": "Wiesbaden",
           "plz": "plz-liste-oliver-zona65.txt",
           "lauf": "zona65-wiesbaden-2026-10-07"},
    "66": {"kreise": [
               {"ort": "Saarbrücken", "mitte": (49.2342, 6.9951),
                "radius": 10.8}],
           "stadt": "Saarbrücken",
           "plz": "plz-liste-oliver-zona66.txt",
           "lauf": "zona66-saarbruecken-2026-10-07"},
    "67": {"kreise": [
               {"ort": "Ludwigshafen am Rhein", "mitte": (49.4866, 8.4181),
                "radius": 5.4},
               {"ort": "Kaiserslautern", "mitte": (49.4375, 7.7565),
                "radius": 5.5}],
           "stadt": "Ludwigshafen am Rhein",
           "plz": "plz-liste-oliver-zona67.txt",
           "lauf": "zona67-ludwigshafen-2026-10-07"},
    "68": {"kreise": [
               {"ort": "Mannheim", "mitte": (49.492, 8.4991), "radius": 9.7}],
           "stadt": "Mannheim",
           "plz": "plz-liste-oliver-zona68.txt",
           "lauf": "zona68-mannheim-2026-10-07"},
    "69": {"kreise": [
               {"ort": "Heidelberg", "mitte": (49.4074, 8.6913),
                "radius": 4.6}],
           "stadt": "Heidelberg",
           "plz": "plz-liste-oliver-zona69.txt",
           "lauf": "zona69-heidelberg-2026-10-07"},
    # --- Rajoni 70-79, dhjete zona qytetesh (08.10.2026) ---
    #
    # NUK eshte porosi e Oliverit (lista e tij mbaron te 69); e kerkoi
    # Dafina. Marrim vetem qytete me >= 4 kode dhe vetem kodet brenda
    # 10 km nga qendra - me larg eshte qytet tjeter qe tabela e quan me
    # emrin e qytetit te madh. 42 kode u maten me OSM para se te caktohej
    # ndonje rreth; 15 koordinata ishin te ngjeshura te qendra e qytetit
    # dhe u ndreqen, 25 dolen kuti postare pa zone, dhe 2 (76110, 79093)
    # perputheshin me kode te huaja (Franca, Meksika) - te lena jashte.
    "70": {"kreise": [
               {"ort": "Stuttgart", "mitte": (48.7774, 9.178), "radius": 9.3},
               {"ort": "Esslingen", "mitte": (48.6944, 9.1777), "radius": 6.5}],
           "stadt": "Stuttgart",
           "plz": "plz-liste-70-79-zona70.txt",
           "lauf": "zona70-stuttgart-2026-10-08"},
    "71": {"kreise": [
               {"ort": "Ludwigsburg", "mitte": (48.8924, 9.1898), "radius": 3.6},
               {"ort": "Böblingen", "mitte": (48.6821, 8.9842), "radius": 8.0},
               {"ort": "Sindelfingen", "mitte": (48.7172, 9.0077), "radius": 3.9}],
           "stadt": "Ludwigsburg",
           "plz": "plz-liste-70-79-zona71.txt",
           "lauf": "zona71-ludwigsburg-2026-10-08"},
    "72": {"kreise": [
               {"ort": "Tübingen", "mitte": (48.5241, 9.0581), "radius": 11.8},
               {"ort": "Reutlingen", "mitte": (48.4942, 9.2125), "radius": 4.5}],
           "stadt": "Tübingen",
           "plz": "plz-liste-70-79-zona72.txt",
           "lauf": "zona72-tuebingen-2026-10-08"},
    "73": {"kreise": [
               {"ort": "Göppingen", "mitte": (48.7, 9.6667), "radius": 5.9},
               {"ort": "Aalen", "mitte": (48.8409, 10.0931), "radius": 9.2},
               {"ort": "Esslingen am Neckar", "mitte": (48.7394, 9.3061), "radius": 4.4}],
           "stadt": "Göppingen",
           "plz": "plz-liste-70-79-zona73.txt",
           "lauf": "zona73-goeppingen-2026-10-08"},
    "74": {"kreise": [
               {"ort": "Heilbronn", "mitte": (49.1624, 9.2175), "radius": 6.3}],
           "stadt": "Heilbronn",
           "plz": "plz-liste-70-79-zona74.txt",
           "lauf": "zona74-heilbronn-2026-10-08"},
    "75": {"kreise": [
               {"ort": "Pforzheim", "mitte": (48.8919, 8.6831), "radius": 4.7}],
           "stadt": "Pforzheim",
           "plz": "plz-liste-70-79-zona75.txt",
           "lauf": "zona75-pforzheim-2026-10-08"},
    "76": {"kreise": [
               {"ort": "Karlsruhe", "mitte": (49.0078, 8.4043), "radius": 9.7},
               {"ort": "Baden-Baden", "mitte": (48.7781, 8.1937), "radius": 9.5}],
           "stadt": "Karlsruhe",
           "plz": "plz-liste-70-79-zona76.txt",
           "lauf": "zona76-karlsruhe-2026-10-08"},
    "77": {"kreise": [
               {"ort": "Offenburg", "mitte": (48.4639, 7.9438), "radius": 11.1}],
           "stadt": "Offenburg",
           "plz": "plz-liste-70-79-zona77.txt",
           "lauf": "zona77-offenburg-2026-10-08"},
    "78": {"kreise": [
               {"ort": "Konstanz", "mitte": (47.6723, 9.181), "radius": 3},
               {"ort": "Villingen-Schwenningen", "mitte": (48.0622, 8.4406), "radius": 7.3}],
           "stadt": "Konstanz",
           "plz": "plz-liste-70-79-zona78.txt",
           "lauf": "zona78-konstanz-2026-10-08"},
    "79": {"kreise": [
               {"ort": "Freiburg im Breisgau", "mitte": (47.999, 7.8327), "radius": 10.1}],
           "stadt": "Freiburg im Breisgau",
           "plz": "plz-liste-70-79-zona79.txt",
           "lauf": "zona79-freiburg-2026-10-08"},
    # --- Rajoni 80-86, kater zona qytetesh (08.10.2026) ---
    #
    # NUK eshte porosi e Oliverit; e kerkoi Dafina. I tere rajoni ka
    # vetem kater qytete me >= 4 kode: Mynihu, Augsburgu, Rosenheim-i
    # dhe Ingolstadt-i. Dhjeteshet 82 e 84 s'kane asnje - fshatra.
    #
    # Mynihu eshte zona "8", jo "80": kodet e tij shtrihen neper 80xxx,
    # 81xxx dhe 85xxx, dhe emri i zones duhet te jete fillimi i cdo kodi.
    #
    # 13 kode u maten me OSM; 11 koordinata ishin te ngjeshura te qendra
    # (81249 dilte 1,5 km po eshte 13,3 km larg - do te kishte mbetur
    # jashte rrethit), 1 s'kishte zone, dhe 85770 perputhej me nje kod
    # 959 km larg - te dy te lene jashte.
    "8": {"kreise": [
               {"ort": "München", "mitte": (48.1372, 11.5755), "radius": 15.5}],
           "stadt": "München",
           "plz": "plz-liste-80-86-zona8.txt",
           "lauf": "zona8-muenchen-2026-10-08"},
    "86": {"kreise": [
               {"ort": "Augsburg", "mitte": (48.3705, 10.8978), "radius": 8.1}],
           "stadt": "Augsburg",
           "plz": "plz-liste-80-86-zona86.txt",
           "lauf": "zona86-augsburg-2026-10-08",
           # Prova e pare me 08.10.2026 ra ne kufirin e parave qe
           # i vumë vete, pra u shenua e paplote. Vendet e paguara
           # atehere lexohen ketu, qe rivrapimi i plote te mos i
           # bleje dy here.
           "maps_dazu": ["apify-ds-1slGjQLL8lFHlmZEU.json"]},
    "83": {"kreise": [
               {"ort": "Rosenheim", "mitte": (47.8561, 12.1289), "radius": 5.3}],
           "stadt": "Rosenheim",
           "plz": "plz-liste-80-86-zona83.txt",
           "lauf": "zona83-rosenheim-2026-10-08",
           # Prova e pare me 08.10.2026 ra ne kufirin e parave qe
           # i vumë vete, pra u shenua e paplote. Vendet e paguara
           # atehere lexohen ketu, qe rivrapimi i plote te mos i
           # bleje dy here.
           "maps_dazu": ["apify-ds-QtClghytiSbUtTDk6.json"]},
    "85": {"kreise": [
               {"ort": "Ingolstadt", "mitte": (48.7665, 11.4258), "radius": 6.5}],
           "stadt": "Ingolstadt",
           "plz": "plz-liste-80-86-zona85.txt",
           "lauf": "zona85-ingolstadt-2026-10-08"},
    # Zone 49 is NOT in Oliver's list - neither the original nor the
    # corrected one holds a single 49xxx code. Dafina asked for it on
    # 30.09.2026 and chose "Osnabrueck plus the bigger towns": the whole
    # zone is 119 codes of villages across Emsland and Osnabruecker Land,
    # so only the five towns are searched, one circle each.
    "49": {"kreise": [
               {"ort": "Osnabrück", "mitte": (52.2799, 8.0472), "radius": 8},
               {"ort": "Melle", "mitte": (52.1992, 8.3463), "radius": 3},
               {"ort": "Ibbenbüren", "mitte": (52.2634, 7.7234), "radius": 3},
               {"ort": "Cloppenburg", "mitte": (52.825, 8.0827), "radius": 4.7},
               {"ort": "Lingen", "mitte": (52.5176, 7.3195), "radius": 3}],
           "stadt": "Osnabrück",
           "plz": "plz-liste-oliver-zona49.txt",
           "lauf": "zona49-osnabrueck-2026-09-30"},
    # Two corners that were never searched, because the coordinate table
    # had put their code on the town centre (see 29.09.2026). The circles
    # of zones 41 and 45 are widened now, but their paid runs were already
    # over - so each corner gets one small circle of its own instead of
    # paying for the whole zone a second time. The key is the finer postal
    # region ("414", "452"), which is what the code itself starts with.
    "414": {"kreise": [
                {"ort": "Neuss-Uedesheim", "mitte": (51.1356, 6.7390),
                 "radius": 2}],
            "stadt": "Neuss",
            "plz": "plz-liste-oliver-zona414.txt",
            "lauf": "zona41-uedesheim-2026-09-30"},
    "452": {"kreise": [
                {"ort": "Essen-Kettwig", "mitte": (51.3684, 6.9457),
                 "radius": 2.5}],
            "stadt": "Essen",
            "plz": "plz-liste-oliver-zona452.txt",
            "lauf": "zona45-kettwig-2026-09-30"},
    # Qytetet e mesme, 09.10.2026 ("vazhdo me qytetet e mesme njehere lej
    # fshatrat"). Nga 4.684 kodet e pakerkuara te 40000-89999 mbeten ato
    # vende me >= 4 kode: 69 sosh. Prej tyre 27 ishin grupe kutish
    # postare (HUK-Coburg, BARMER, zyra tatimore) dhe 14 rrijne brenda
    # rratheve te vrapuar - pra 25 qytete te vertete, 116 kode.
    #
    # Rrathet u maten me zonat postare te OSM-se, NUK me tabelen e
    # koordinatave: 37 nga kodet ulen te nje pike e vetme (shtate kode
    # te Limburgut te njejta, gjashte te Taunussteinit). Me tabelen
    # Limburgu dilte 3 km; me OSM-in eshte 8,5 km - pra rrethi i vjeter
    # do te kishte lene gjysmen e qytetit pa kerkuar. E gjithe fushata
    # dilte 3.079 km2 (~15 $) me tabelen, dhe 9.597 km2 (~57 $) me OSM.
    #
    # Emrat kane dy-tri shifra, sepse emri i zones duhet te jete fillimi
    # i cdo kodi te vet dhe disa qytete rrijne ne te njejten dhjeteshe:
    # Hagen "58", Luedenscheid "585", Iserlohn "586", Arnsberg "59",
    # Hamm "590", Koblenz "560", Neuwied "565".
    "417": {"kreise": [
                {"ort": "Viersen", "mitte": (51.2694, 6.361),
                 "radius": 10.2}],
            "stadt": "Viersen",
            "plz": "plz-liste-qytete-mesme-zona417.txt",
            "lauf": "zona417-viersen-2026-10-09"},
    "425": {"kreise": [
                {"ort": "Velbert", "mitte": (51.3371, 7.0842),
                 "radius": 8.9}],
            "stadt": "Velbert",
            "plz": "plz-liste-qytete-mesme-zona425.txt",
            "lauf": "zona425-velbert-2026-10-09"},
    "445": {"kreise": [
                {"ort": "Castrop-Rauxel", "mitte": (51.5732, 7.3072),
                 "radius": 8.5}],
            "stadt": "Castrop-Rauxel",
            "plz": "plz-liste-qytete-mesme-zona445.txt",
            "lauf": "zona445-castrop-rauxel-2026-10-09"},
    "456": {"kreise": [
                {"ort": "Recklinghausen", "mitte": (51.6021, 7.2155),
                 "radius": 9.0}],
            "stadt": "Recklinghausen",
            "plz": "plz-liste-qytete-mesme-zona456.txt",
            "lauf": "zona456-recklinghausen-2026-10-09"},
    "464": {"kreise": [
                {"ort": "Wesel", "mitte": (51.67, 6.587),
                 "radius": 12.0}],
            "stadt": "Wesel",
            "plz": "plz-liste-qytete-mesme-zona464.txt",
            "lauf": "zona464-wesel-2026-10-09"},
    "476": {"kreise": [
                {"ort": "Kevelaer", "mitte": (51.59, 6.2675),
                 "radius": 11.8}],
            "stadt": "Kevelaer",
            "plz": "plz-liste-qytete-mesme-zona476.txt",
            "lauf": "zona476-kevelaer-2026-10-09"},
    "523": {"kreise": [
                {"ort": "Düren", "mitte": (50.7993, 6.462),
                 "radius": 9.6}],
            "stadt": "Düren",
            "plz": "plz-liste-qytete-mesme-zona523.txt",
            "lauf": "zona523-duren-2026-10-09"},
    "542": {"kreise": [
                {"ort": "Trier", "mitte": (49.7779, 6.6495),
                 "radius": 12.8}],
            "stadt": "Trier",
            "plz": "plz-liste-qytete-mesme-zona542.txt",
            "lauf": "zona542-trier-2026-10-09"},
    "560": {"kreise": [
                {"ort": "Koblenz", "mitte": (50.3463, 7.5873),
                 "radius": 10.0}],
            "stadt": "Koblenz",
            "plz": "plz-liste-qytete-mesme-zona560.txt",
            "lauf": "zona560-koblenz-2026-10-09"},
    "565": {"kreise": [
                {"ort": "Neuwied", "mitte": (50.4603, 7.4819),
                 "radius": 10.1}],
            "stadt": "Neuwied",
            "plz": "plz-liste-qytete-mesme-zona565.txt",
            "lauf": "zona565-neuwied-2026-10-09"},
    "570": {"kreise": [
                {"ort": "Siegen", "mitte": (50.8814, 8.0248),
                 "radius": 12.1}],
            "stadt": "Siegen",
            "plz": "plz-liste-qytete-mesme-zona570.txt",
            "lauf": "zona570-siegen-2026-10-09"},
    "58": {"kreise": [
                {"ort": "Hagen", "mitte": (51.3417, 7.4874),
                 "radius": 12.2}],
            "stadt": "Hagen",
            "plz": "plz-liste-qytete-mesme-zona58.txt",
            "lauf": "zona58-hagen-2026-10-09"},
    "585": {"kreise": [
                {"ort": "Lüdenscheid", "mitte": (51.2129, 7.6361),
                 "radius": 10.1}],
            "stadt": "Lüdenscheid",
            "plz": "plz-liste-qytete-mesme-zona585.txt",
            "lauf": "zona585-ludenscheid-2026-10-09"},
    "586": {"kreise": [
                {"ort": "Iserlohn", "mitte": (51.3877, 7.6646),
                 "radius": 12.3}],
            "stadt": "Iserlohn",
            "plz": "plz-liste-qytete-mesme-zona586.txt",
            "lauf": "zona586-iserlohn-2026-10-09"},
    "59": {"kreise": [
                {"ort": "Arnsberg", "mitte": (51.423, 8.0371),
                 "radius": 16.0}],
            "stadt": "Arnsberg",
            "plz": "plz-liste-qytete-mesme-zona59.txt",
            "lauf": "zona59-arnsberg-2026-10-09"},
    "590": {"kreise": [
                {"ort": "Hamm", "mitte": (51.6612, 7.8361),
                 "radius": 14.5}],
            "stadt": "Hamm",
            "plz": "plz-liste-qytete-mesme-zona590.txt",
            "lauf": "zona590-hamm-2026-10-09"},
    "634": {"kreise": [
                {"ort": "Hanau", "mitte": (50.1354, 8.9454),
                 "radius": 10.3}],
            "stadt": "Hanau",
            "plz": "plz-liste-qytete-mesme-zona634.txt",
            "lauf": "zona634-hanau-2026-10-09"},
    "637": {"kreise": [
                {"ort": "Aschaffenburg", "mitte": (49.9707, 9.1591),
                 "radius": 9.1}],
            "stadt": "Aschaffenburg",
            "plz": "plz-liste-qytete-mesme-zona637.txt",
            "lauf": "zona637-aschaffenburg-2026-10-09"},
    "645": {"kreise": [
                {"ort": "Groß-Gerau", "mitte": (49.9145, 8.4777),
                 "radius": 8.9}],
            "stadt": "Groß-Gerau",
            "plz": "plz-liste-qytete-mesme-zona645.txt",
            "lauf": "zona645-gro-gerau-2026-10-09"},
    "652": {"kreise": [
                {"ort": "Taunusstein", "mitte": (50.1575, 8.1706),
                 "radius": 10.0}],
            "stadt": "Taunusstein",
            "plz": "plz-liste-qytete-mesme-zona652.txt",
            "lauf": "zona652-taunusstein-2026-10-09"},
    "653": {"kreise": [
                {"ort": "Eltville am Rhein", "mitte": (50.05, 8.0806),
                 "radius": 8.6}],
            "stadt": "Eltville am Rhein",
            "plz": "plz-liste-qytete-mesme-zona653.txt",
            "lauf": "zona653-eltville-am-rhein-2026-10-09"},
    "655": {"kreise": [
                {"ort": "Limburg an der Lahn", "mitte": (50.4014, 8.0704),
                 "radius": 8.5}],
            "stadt": "Limburg an der Lahn",
            "plz": "plz-liste-qytete-mesme-zona655.txt",
            "lauf": "zona655-limburg-an-der-lahn-2026-10-09"},
    "675": {"kreise": [
                {"ort": "Worms", "mitte": (49.6613, 8.3422),
                 "radius": 12.7}],
            "stadt": "Worms",
            "plz": "plz-liste-qytete-mesme-zona675.txt",
            "lauf": "zona675-worms-2026-10-09"},
    "882": {"kreise": [
                {"ort": "Ravensburg", "mitte": (47.7584, 9.5734),
                 "radius": 10.6}],
            "stadt": "Ravensburg",
            "plz": "plz-liste-qytete-mesme-zona882.txt",
            "lauf": "zona882-ravensburg-2026-10-09"},
    "890": {"kreise": [
                {"ort": "Ulm", "mitte": (48.3876, 9.9427),
                 "radius": 13.2}],
            "stadt": "Ulm",
            "plz": "plz-liste-qytete-mesme-zona890.txt",
            "lauf": "zona890-ulm-2026-10-09"},
    # Qytetet e mesme, raundi 2 (09.10.2026). Pyetja e Dafines: "a i ke kry
    # te gjitha zonat ne qytete te mesme" - jo. Prerja e raundit 1 ("4 kode
    # ose me shume") nuk ishte mase e madhesise: jashte mbeten Lünen
    # (86.000), Rheine (76.000), Troisdorf (75.000), Landshut (73.000),
    # Kempten (69.000), kurse brenda hyri Eltville me 17.000. Dhe tri
    # qytete te listes se raundit 1 - Marl, Schwäbisch Hall, Bergheim -
    # rreshqiten jashte pa u vene re, se filtri kerkonte 4 kode brenda 10
    # km nga qendra dhe kodet e tyre shtrihen me larg.
    #
    # Ketu hyjne 43 qytete, 106 kode: te gjitha vendet me >= 3 kode jashte
    # rratheve tane, plus 13 qytete te vertete me 2 kode (Landshut,
    # Böblingen, Rastatt, Euskirchen ...). Fshatrat - 2.690 vende me nje
    # kod te vetem - mbeten jashte me fjalen e Dafines.
    #
    # Emrat kane deri 4 shifra: dy qytete ndajne shpesh te njejtin fillim
    # tri-shifror (Bergheim 50126 dhe Kerpen 50169 ndajne "501",
    # Castrop-Rauxel dhe Lünen ndajne "445"). Emrin e gjate e marrin
    # qytetet qe e kane, qe emrat e shkurter te mbeten te lire.
    #
    # Nente qytete nuk kishin asnje kod me zone postare te OSM-se
    # (Marl, Bocholt, Böblingen, Biberach ...); rrethi i tyre u mat me
    # tabelen e koordinatave dhe u mbajt te paku 6 km, se atje pikat
    # mund te jene te ngjeshura te qendra e qytetit.
    "4151": {"kreise": [
                 {"ort": "Grevenbroich", "mitte": (51.0861, 6.6171),
                  "radius": 11.6}],
             "stadt": "Grevenbroich",
             "plz": "plz-liste-qytete-mesme2-zona4151.txt",
             "lauf": "zona4151-grevenbroich-2026-10-09"},
    "4453": {"kreise": [
                 {"ort": "Lünen", "mitte": (51.6153, 7.5051),
                  "radius": 8.4}],
             "stadt": "Lünen",
             "plz": "plz-liste-qytete-mesme2-zona4453.txt",
             "lauf": "zona4453-lunen-2026-10-09"},
    "4552": {"kreise": [
                 {"ort": "Hattingen", "mitte": (51.3676, 7.1826),
                  "radius": 9.4}],
             "stadt": "Hattingen",
             "plz": "plz-liste-qytete-mesme2-zona4552.txt",
             "lauf": "zona4552-hattingen-2026-10-09"},
    "457": {"kreise": [
                 {"ort": "Marl", "mitte": (51.6614, 7.1094),
                  "radius": 6.0}],
             "stadt": "Marl",
             "plz": "plz-liste-qytete-mesme2-zona457.txt",
             "lauf": "zona457-marl-2026-10-09"},
    "4628": {"kreise": [
                 {"ort": "Dorsten", "mitte": (51.7119, 6.991),
                  "radius": 13.6}],
             "stadt": "Dorsten",
             "plz": "plz-liste-qytete-mesme2-zona4628.txt",
             "lauf": "zona4628-dorsten-2026-10-09"},
    "4639": {"kreise": [
                 {"ort": "Bocholt", "mitte": (51.8331, 6.6139),
                  "radius": 6.0}],
             "stadt": "Bocholt",
             "plz": "plz-liste-qytete-mesme2-zona4639.txt",
             "lauf": "zona4639-bocholt-2026-10-09"},
    "484": {"kreise": [
                 {"ort": "Rheine", "mitte": (52.2668, 7.4758),
                  "radius": 12.7}],
             "stadt": "Rheine",
             "plz": "plz-liste-qytete-mesme2-zona484.txt",
             "lauf": "zona484-rheine-2026-10-09"},
    "485": {"kreise": [
                 {"ort": "Nordhorn", "mitte": (52.4436, 7.1011),
                  "radius": 13.2}],
             "stadt": "Nordhorn",
             "plz": "plz-liste-qytete-mesme2-zona485.txt",
             "lauf": "zona485-nordhorn-2026-10-09"},
    "4856": {"kreise": [
                 {"ort": "Steinfurt", "mitte": (52.1378, 7.3583),
                  "radius": 10.5}],
             "stadt": "Steinfurt",
             "plz": "plz-liste-qytete-mesme2-zona4856.txt",
             "lauf": "zona4856-steinfurt-2026-10-09"},
    "501": {"kreise": [
                 {"ort": "Kerpen", "mitte": (50.8737, 6.6774),
                  "radius": 12.1}],
             "stadt": "Kerpen",
             "plz": "plz-liste-qytete-mesme2-zona501.txt",
             "lauf": "zona501-kerpen-2026-10-09"},
    "5012": {"kreise": [
                 {"ort": "Bergheim", "mitte": (50.9689, 6.6653),
                  "radius": 10.6}],
             "stadt": "Bergheim",
             "plz": "plz-liste-qytete-mesme2-zona5012.txt",
             "lauf": "zona5012-bergheim-2026-10-09"},
    "5164": {"kreise": [
                 {"ort": "Gummersbach", "mitte": (51.0297, 7.5744),
                  "radius": 13.2}],
             "stadt": "Gummersbach",
             "plz": "plz-liste-qytete-mesme2-zona5164.txt",
             "lauf": "zona5164-gummersbach-2026-10-09"},
    "5222": {"kreise": [
                 {"ort": "Stolberg (Rheinland)", "mitte": (50.7451, 6.2701),
                  "radius": 10.8}],
             "stadt": "Stolberg (Rheinland)",
             "plz": "plz-liste-qytete-mesme2-zona5222.txt",
             "lauf": "zona5222-stolberg-rheinland-2026-10-09"},
    "5252": {"kreise": [
                 {"ort": "Heinsberg", "mitte": (51.0593, 6.091),
                  "radius": 12.6}],
             "stadt": "Heinsberg",
             "plz": "plz-liste-qytete-mesme2-zona5252.txt",
             "lauf": "zona5252-heinsberg-2026-10-09"},
    "538": {"kreise": [
                 {"ort": "Euskirchen", "mitte": (50.6318, 6.8227),
                  "radius": 12.7}],
             "stadt": "Euskirchen",
             "plz": "plz-liste-qytete-mesme2-zona538.txt",
             "lauf": "zona538-euskirchen-2026-10-09"},
    "5384": {"kreise": [
                 {"ort": "Troisdorf", "mitte": (50.818, 7.146),
                  "radius": 9.1}],
             "stadt": "Troisdorf",
             "plz": "plz-liste-qytete-mesme2-zona5384.txt",
             "lauf": "zona5384-troisdorf-2026-10-09"},
    "5554": {"kreise": [
                 {"ort": "Bad Kreuznach", "mitte": (49.8426, 7.8513),
                  "radius": 6.0}],
             "stadt": "Bad Kreuznach",
             "plz": "plz-liste-qytete-mesme2-zona5554.txt",
             "lauf": "zona5554-bad-kreuznach-2026-10-09"},
    "574": {"kreise": [
                 {"ort": "Olpe", "mitte": (51.0791, 7.876),
                  "radius": 6.8}],
             "stadt": "Olpe",
             "plz": "plz-liste-qytete-mesme2-zona574.txt",
             "lauf": "zona574-olpe-2026-10-09"},
    "5942": {"kreise": [
                 {"ort": "Unna", "mitte": (51.5345, 7.7358),
                  "radius": 10.2}],
             "stadt": "Unna",
             "plz": "plz-liste-qytete-mesme2-zona5942.txt",
             "lauf": "zona5942-unna-2026-10-09"},
    "665": {"kreise": [
                 {"ort": "Neunkirchen/Saar", "mitte": (49.3465, 7.1874),
                  "radius": 10.3}],
             "stadt": "Neunkirchen/Saar",
             "plz": "plz-liste-qytete-mesme2-zona665.txt",
             "lauf": "zona665-neunkirchen-saar-2026-10-09"},
    "6695": {"kreise": [
                 {"ort": "Pirmasens", "mitte": (49.2037, 7.5958),
                  "radius": 10.5}],
             "stadt": "Pirmasens",
             "plz": "plz-liste-qytete-mesme2-zona6695.txt",
             "lauf": "zona6695-pirmasens-2026-10-09"},
    "6743": {"kreise": [
                 {"ort": "Neustadt an der Weinstraße", "mitte": (49.3516, 8.1427),
                  "radius": 6.0}],
             "stadt": "Neustadt an der Weinstraße",
             "plz": "plz-liste-qytete-mesme2-zona6743.txt",
             "lauf": "zona6743-neustadt-an-der-weinstrae-2026-10-09"},
    "711": {"kreise": [
                 {"ort": "Böblingen", "mitte": (48.5244, 8.8431),
                  "radius": 6.0}],
             "stadt": "Böblingen",
             "plz": "plz-liste-qytete-mesme2-zona711.txt",
             "lauf": "zona711-boblingen-2026-10-09"},
    "7133": {"kreise": [
                 {"ort": "Waiblingen", "mitte": (48.8598, 9.3217),
                  "radius": 7.4}],
             "stadt": "Waiblingen",
             "plz": "plz-liste-qytete-mesme2-zona7133.txt",
             "lauf": "zona7133-waiblingen-2026-10-09"},
    "724": {"kreise": [
                 {"ort": "Albstadt", "mitte": (48.2323, 9.0215),
                  "radius": 6.0}],
             "stadt": "Albstadt",
             "plz": "plz-liste-qytete-mesme2-zona724.txt",
             "lauf": "zona724-albstadt-2026-10-09"},
    "7248": {"kreise": [
                 {"ort": "Sigmaringen", "mitte": (48.0049, 9.2422),
                  "radius": 10.6}],
             "stadt": "Sigmaringen",
             "plz": "plz-liste-qytete-mesme2-zona7248.txt",
             "lauf": "zona7248-sigmaringen-2026-10-09"},
    "7352": {"kreise": [
                 {"ort": "Schwäbisch Gmünd", "mitte": (48.7973, 9.8286),
                  "radius": 14.1}],
             "stadt": "Schwäbisch Gmünd",
             "plz": "plz-liste-qytete-mesme2-zona7352.txt",
             "lauf": "zona7352-schwabisch-gmund-2026-10-09"},
    "7452": {"kreise": [
                 {"ort": "Schwäbisch Hall", "mitte": (49.1065, 9.7328),
                  "radius": 14.0}],
             "stadt": "Schwäbisch Hall",
             "plz": "plz-liste-qytete-mesme2-zona7452.txt",
             "lauf": "zona7452-schwabisch-hall-2026-10-09"},
    "7643": {"kreise": [
                 {"ort": "Rastatt", "mitte": (48.867, 8.1902),
                  "radius": 9.2}],
             "stadt": "Rastatt",
             "plz": "plz-liste-qytete-mesme2-zona7643.txt",
             "lauf": "zona7643-rastatt-2026-10-09"},
    "7672": {"kreise": [
                 {"ort": "Germersheim", "mitte": (49.2163, 8.3734),
                  "radius": 5.9}],
             "stadt": "Germersheim",
             "plz": "plz-liste-qytete-mesme2-zona7672.txt",
             "lauf": "zona7672-germersheim-2026-10-09"},
    "7931": {"kreise": [
                 {"ort": "Emmendingen", "mitte": (48.1248, 7.8624),
                  "radius": 6.6}],
             "stadt": "Emmendingen",
             "plz": "plz-liste-qytete-mesme2-zona7931.txt",
             "lauf": "zona7931-emmendingen-2026-10-09"},
    "795": {"kreise": [
                 {"ort": "Lörrach", "mitte": (47.6346, 7.6812),
                  "radius": 6.9}],
             "stadt": "Lörrach",
             "plz": "plz-liste-qytete-mesme2-zona795.txt",
             "lauf": "zona795-lorrach-2026-10-09"},
    "8225": {"kreise": [
                 {"ort": "Fürstenfeldbruck", "mitte": (48.1794, 11.2309),
                  "radius": 6.6}],
             "stadt": "Fürstenfeldbruck",
             "plz": "plz-liste-qytete-mesme2-zona8225.txt",
             "lauf": "zona8225-furstenfeldbruck-2026-10-09"},
    "823": {"kreise": [
                 {"ort": "Starnberg", "mitte": (48.0041, 11.3286),
                  "radius": 10.0}],
             "stadt": "Starnberg",
             "plz": "plz-liste-qytete-mesme2-zona823.txt",
             "lauf": "zona823-starnberg-2026-10-09"},
    "840": {"kreise": [
                 {"ort": "Landshut", "mitte": (48.5329, 12.1023),
                  "radius": 7.9}],
             "stadt": "Landshut",
             "plz": "plz-liste-qytete-mesme2-zona840.txt",
             "lauf": "zona840-landshut-2026-10-09"},
    "8527": {"kreise": [
                 {"ort": "Pfaffenhofen an der Ilm", "mitte": (48.5435, 11.4869),
                  "radius": 10.7}],
             "stadt": "Pfaffenhofen an der Ilm",
             "plz": "plz-liste-qytete-mesme2-zona8527.txt",
             "lauf": "zona8527-pfaffenhofen-an-der-ilm-2026-10-09"},
    "8535": {"kreise": [
                 {"ort": "Freising", "mitte": (48.3898, 11.7381),
                  "radius": 11.1}],
             "stadt": "Freising",
             "plz": "plz-liste-qytete-mesme2-zona8535.txt",
             "lauf": "zona8535-freising-2026-10-09"},
    "8689": {"kreise": [
                 {"ort": "Landsberg am Lech", "mitte": (48.0337, 10.8656),
                  "radius": 7.7}],
             "stadt": "Landsberg am Lech",
             "plz": "plz-liste-qytete-mesme2-zona8689.txt",
             "lauf": "zona8689-landsberg-am-lech-2026-10-09"},
    "8743": {"kreise": [
                 {"ort": "Kempten", "mitte": (47.7363, 10.3054),
                  "radius": 8.2}],
             "stadt": "Kempten",
             "plz": "plz-liste-qytete-mesme2-zona8743.txt",
             "lauf": "zona8743-kempten-2026-10-09"},
    "88": {"kreise": [
                 {"ort": "Biberach", "mitte": (48.1287, 9.641),
                  "radius": 13.4}],
             "stadt": "Biberach",
             "plz": "plz-liste-qytete-mesme2-zona88.txt",
             "lauf": "zona88-biberach-2026-10-09"},
    "8804": {"kreise": [
                 {"ort": "Friedrichshafen", "mitte": (47.6878, 9.4711),
                  "radius": 10.0}],
             "stadt": "Friedrichshafen",
             "plz": "plz-liste-qytete-mesme2-zona8804.txt",
             "lauf": "zona8804-friedrichshafen-2026-10-09"},
    "8931": {"kreise": [
                 {"ort": "Günzburg", "mitte": (48.469, 10.2812),
                  "radius": 8.1}],
             "stadt": "Günzburg",
             "plz": "plz-liste-qytete-mesme2-zona8931.txt",
             "lauf": "zona8931-gunzburg-2026-10-09"},
    "895": {"kreise": [
                 {"ort": "Heidenheim an der Brenz", "mitte": (48.7135, 10.1908),
                  "radius": 11.5}],
             "stadt": "Heidenheim an der Brenz",
             "plz": "plz-liste-qytete-mesme2-zona895.txt",
             "lauf": "zona895-heidenheim-an-der-brenz-2026-10-09"},
}


# Prozessberater, 15.10.2026 (Dafina: "ky eshte jo IT, AMA TNJEJTIN SEN").
# Dieselbe Geografie wie die IT-Zonen des Postleitzahl-Raums 30-39: die
# Kreise und die Postleitzahl-Liste werden WIEDERVERWENDET, nicht kopiert.
# Zwei Kopien wuerden mit der Zeit auseinanderlaufen, und dann sucht eine
# Zielgruppe ein anderes Gebiet ab als die andere. Eigen ist nur der
# Lauf-Ordner: sonst schreiben beide in denselben und die Firmen der
# einen landen in der Liste der anderen.
#
# 30 und 31 fehlen hier noch: sie sind nie als Zone gebaut worden (der
# Raum 30-31 wurde im Sommer mit dem alten Ablauf gesammelt, Ordner
# "plr-30-31"), haben also keine Postleitzahl-Liste in diesem Format.
ZONEN_PROZESS = {
    nr: {**ZONEN[nr], "lauf": f"zona{nr}-prozess-2026-10-15"}
    for nr in ("32", "33", "34", "35", "36", "37", "38", "39")
}

ZONEN_JE_ZIELGRUPPE = {"it": ZONEN, "prozess": ZONEN_PROZESS}


def zonen_tabelle(zielgruppe: str = "it") -> dict:
    """Die Zonen-Tabelle einer Zielgruppe - unbekannt ist ein Fehler.

    Keine stille Rueckkehr zur IT: wer sich vertippt, wuerde sonst die
    falsche Branche sammeln und dafuer zahlen.
    """
    try:
        return ZONEN_JE_ZIELGRUPPE[zielgruppe]
    except KeyError:
        raise KeyError(
            f"Unbekannte Zielgruppe {zielgruppe!r} - bekannt: "
            f"{', '.join(sorted(ZONEN_JE_ZIELGRUPPE))}") from None


def zone(nummer: str, zielgruppe: str = "it") -> dict:
    """Die Zone zu "34", "35" ... - unbekannt ist ein Fehler, keine Stille."""
    nummer = str(nummer).strip()
    tabelle = zonen_tabelle(zielgruppe)
    if nummer not in tabelle:
        raise KeyError(
            f"Zone {nummer!r} steht nicht in der Tabelle der Zielgruppe "
            f"{zielgruppe!r}. Bekannt sind: {', '.join(sorted(tabelle))}")
    return tabelle[nummer]


def kreise(nummer: str, zielgruppe: str = "it") -> list:
    """[(mitte, radius_km), ...] - one circle for zones 32-40, one per town
    for a zone of several towns ("kreise")."""
    eintrag = zone(nummer, zielgruppe)
    if "kreise" in eintrag:
        return [(k["mitte"], k["radius"]) for k in eintrag["kreise"]]
    return [(eintrag["mitte"], eintrag["radius"])]


def suchgebiet(nummer: str, zielgruppe: str = "it") -> dict:
    """The search area as Apify takes it: the same polygon as always for a
    single circle, a MultiPolygon for several (supported by the actor, see
    its README "Custom search area", checked 29.09.2026)."""
    polygone = [kreis_polygon(*mitte, radius)
                for mitte, radius in kreise(nummer, zielgruppe)]
    if len(polygone) == 1:
        return polygone[0]
    return {"type": "MultiPolygon",
            "coordinates": [p["coordinates"] for p in polygone]}


def plz_datei(nummer: str, zielgruppe: str = "it") -> Path:
    return PLZ_ORDNER / zone(nummer, zielgruppe)["plz"]


def plz_kodes(nummer: str, zielgruppe: str = "it") -> list:
    """Die bestellten Postleitzahlen der Zone. Leerzeilen und Kommentare
    fallen raus; alles andere muss eine fuenfstellige Zahl sein - eine
    schiefe Zeile ist ein Fehler und kein stilles Ueberspringen, sonst
    faellt eine bestellte Postleitzahl unbemerkt weg."""
    datei = plz_datei(nummer, zielgruppe)
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
