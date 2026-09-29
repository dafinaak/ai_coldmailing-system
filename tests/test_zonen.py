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
        kreise = zonen.kreise(nummer)
        assert kreise, f"Zone {nummer} ohne Suchkreis"
        for mitte, radius in kreise:
            assert mitte, f"Zone {nummer} ohne Mittelpunkt"
            assert radius > 0, f"Zone {nummer} ohne Radius"
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


def _zuordnung(nummer, tabelle):
    """For every circle of the zone, the distances of the ordered codes it
    carries - a code belongs to the circle that holds it with the most room."""
    kreise = zonen.kreise(nummer)
    getragen = [[] for _ in kreise]
    for kode in zonen.plz_kodes(nummer):
        eintrag = tabelle.get(kode)
        if eintrag is None:
            continue          # nicht in der Koordinatentabelle - eigener Fall
        punkt = (eintrag["lat"], eintrag["lon"])
        wege = [entfernung_km(mitte, punkt) for mitte, _ in kreise]
        bester = min(range(len(kreise)),
                     key=lambda i: wege[i] - kreise[i][1] * SICHER)
        getragen[bester].append((kode, eintrag["ort"], wege[bester]))
    return kreise, getragen


def test_jede_bestellte_plz_liegt_im_kreis():
    """Der Kreis muss die Zone decken - sonst fehlen Firmen im Ergebnis,
    ohne dass ein Fehler auffaellt."""
    tabelle = plz_tabelle()
    for nummer in zonen.ZONEN:
        kreise, getragen = _zuordnung(nummer, tabelle)
        for (mitte, radius), kodes in zip(kreise, getragen):
            gedeckt = radius * SICHER
            for kode, ort, weg in kodes:
                assert weg <= gedeckt, (
                    f"Zone {nummer}: {kode} ({ort}) liegt {weg:.1f} km "
                    f"vom Mittelpunkt, gedeckt sind nur {gedeckt:.1f} km")


def test_kreis_ist_nicht_unnoetig_gross():
    """Jeder Ort ausserhalb der Zone kostet gleich viel wie einer drinnen.
    Mehr als 15 km Luft ueber die aeusserste bestellte PLZ hinaus ist
    bezahlte Flaeche, die uns nichts bringt.

    A zone with several circles: every circle must also carry at least one
    ordered code - an empty circle is paid area and nothing else."""
    tabelle = plz_tabelle()
    for nummer in zonen.ZONEN:
        kreise, getragen = _zuordnung(nummer, tabelle)
        for (mitte, radius), kodes in zip(kreise, getragen):
            assert kodes, (f"Zone {nummer}: der Kreis um {mitte} traegt "
                           f"keine bestellte PLZ")
            weiteste = max(weg for _, _, weg in kodes)
            assert radius - weiteste <= 15, (
                f"Zone {nummer}: Radius {radius} km, aeusserste PLZ aber "
                f"nur {weiteste:.1f} km entfernt - der Kreis ist zu weit")


def test_one_circle_goes_to_apify_exactly_as_before():
    """Zones 32-40 must be searched with the very same polygon as before,
    or their lists stop being comparable with the ones already delivered."""
    for nummer, zone in zonen.ZONEN.items():
        if "kreise" in zone:
            continue
        assert zonen.suchgebiet(nummer) == zonen.kreis_polygon(
            *zone["mitte"], zone["radius"])


def test_several_circles_become_one_multipolygon():
    """Zone 41 is four towns. One circle around all of them would reach
    into Duesseldorf, and its places would use up the 110 per search word."""
    gebiet = zonen.suchgebiet("41")
    assert gebiet["type"] == "MultiPolygon"
    assert len(gebiet["coordinates"]) == len(zonen.kreise("41")) > 1
    for polygon in gebiet["coordinates"]:
        ring = polygon[0]
        assert ring[0] == ring[-1], "GeoJSON-Ring muss geschlossen sein"
        assert len(ring) == zonen.POLYGON_PUNKTE + 1


def test_reused_maps_datasets_exist():
    """A zone can reuse the places a neighbour's paid Maps run found inside
    it. If such a file were missing, the zone would lose them silently."""
    for nummer, zone in zonen.ZONEN.items():
        for datei in zone.get("maps_dazu", []):
            assert (zonen.PLZ_ORDNER / datei).exists(), (
                f"Zone {nummer}: {datei} fehlt")


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
