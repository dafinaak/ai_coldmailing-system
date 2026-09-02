"""One shared zone table for all three sources.

Until now the zone circles lived inside werkzeuge/zonen-maps.py. That file
has a hyphen in its name, so no other tool and no test could import it -
the Overpass tool and the Gelbe-Seiten tool would each have had to keep
their own copy of the centres. Three copies of the same number is how a
zone silently gets collected with the wrong circle.

The tests below guard the two things a wrong circle costs us:

  coverage - every ordered postal code must fall inside the circle,
             otherwise we quietly lose companies and nobody notices;
  waste    - Apify charges per place found, also for places outside the
             zone, so the circle must not be blown up beyond its job.
"""
import math

import pytest

from pipeline import zonen
from pipeline.plz_geo import entfernung_km, plz_tabelle


# The circle is sent to Apify as a 24-point polygon inscribed in it. At the
# midpoint of each edge the polygon sits closest to the centre, so this -
# not the radius - is the distance that is guaranteed to be covered.
SICHER = math.cos(math.pi / zonen.POLYGON_PUNKTE)


def test_jede_zone_hat_was_die_drei_quellen_brauchen():
    for nummer, zone in zonen.ZONEN.items():
        assert zone["mitte"], f"Zone {nummer} ohne Mittelpunkt"
        assert zone["radius"] > 0, f"Zone {nummer} ohne Radius"
        assert zone["stadt"], f"Zone {nummer} ohne Stadt (Gelbe Seiten)"
        assert zone["plz"], f"Zone {nummer} ohne PLZ-Liste"
        assert zone["lauf"], f"Zone {nummer} ohne Lauf-Ordner"


def test_stadt_ist_gesetzt_weil_gelbe_seiten_sonst_deutschland_absucht():
    """Gelbe Seiten braucht einen Ortsnamen. Ohne ihn wuerde die Suche
    ueber ganz Deutschland laufen und ein Vielfaches kosten."""
    for nummer, zone in zonen.ZONEN.items():
        assert zone["stadt"] != "Deutschland", f"Zone {nummer}"


def test_plz_listen_enthalten_nur_die_eigene_zone():
    for nummer in zonen.ZONEN:
        kodes = zonen.plz_kodes(nummer)
        assert kodes, f"Zone {nummer}: leere PLZ-Liste"
        fremd = [k for k in kodes if not k.startswith(nummer)]
        assert not fremd, f"Zone {nummer} enthaelt fremde Kodes: {fremd}"


def test_jede_bestellte_plz_liegt_im_kreis():
    """Der Kreis muss die Zone decken - sonst fehlen Firmen im Ergebnis,
    ohne dass ein Fehler auffaellt."""
    tabelle = plz_tabelle()
    for nummer, zone in zonen.ZONEN.items():
        gedeckt = zone["radius"] * SICHER
        for kode in zonen.plz_kodes(nummer):
            eintrag = tabelle.get(kode)
            if eintrag is None:
                continue          # nicht in der Koordinatentabelle - eigener Fall
            weg = entfernung_km(zone["mitte"], (eintrag["lat"], eintrag["lon"]))
            assert weg <= gedeckt, (
                f"Zone {nummer}: {kode} ({eintrag['ort']}) liegt {weg:.1f} km "
                f"vom Mittelpunkt, gedeckt sind nur {gedeckt:.1f} km")


def test_kreis_ist_nicht_unnoetig_gross():
    """Jeder Ort ausserhalb der Zone kostet gleich viel wie einer drinnen.
    Mehr als 15 km Luft ueber die aeusserste bestellte PLZ hinaus ist
    bezahlte Flaeche, die uns nichts bringt."""
    tabelle = plz_tabelle()
    for nummer, zone in zonen.ZONEN.items():
        weiteste = max(
            entfernung_km(zone["mitte"], (tabelle[k]["lat"], tabelle[k]["lon"]))
            for k in zonen.plz_kodes(nummer) if k in tabelle)
        assert zone["radius"] - weiteste <= 15, (
            f"Zone {nummer}: Radius {zone['radius']} km, aeusserste PLZ aber "
            f"nur {weiteste:.1f} km entfernt - der Kreis ist zu weit")


def test_unbekannte_zone_ist_ein_fehler_keine_stille():
    with pytest.raises(KeyError):
        zonen.zone("99")


def test_polygon_schliesst_sich_und_umschliesst_den_mittelpunkt():
    ring = zonen.kreis_polygon(51.0, 9.0, 50)["coordinates"][0]
    assert ring[0] == ring[-1], "GeoJSON-Ring muss geschlossen sein"
    assert len(ring) == zonen.POLYGON_PUNKTE + 1
    for lon, lat in ring:
        weg = entfernung_km((51.0, 9.0), (lat, lon))
        assert 49 <= weg <= 51, f"Eckpunkt liegt {weg:.1f} km statt 50 km weit"
