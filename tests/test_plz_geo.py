"""Postal code to map point.

Distances decide which companies land in a campaign, so the numbers are
checked against real, known distances rather than against themselves.
"""
import pytest

from pipeline.plz_geo import (
    entfernung_km, mittelpunkt, plz_tabelle, punkt_fuer_ort, punkt_fuer_plz,
)


def test_bekannte_postleitzahl_liegt_wo_sie_soll():
    # Hannover Mitte
    lat, lon = punkt_fuer_plz("30159")
    assert 52.3 < lat < 52.5
    assert 9.6 < lon < 9.9


def test_unbekannte_und_kaputte_eingaben_geben_nichts():
    assert punkt_fuer_plz("99999") is None
    assert punkt_fuer_plz("") is None
    assert punkt_fuer_plz(None) is None
    assert punkt_fuer_plz("Hannover") is None       # Ort, keine PLZ


def test_postleitzahl_mit_beiwerk_wird_gelesen():
    # Aus Listen kommen Werte wie "D-30159" oder "30159 Hannover".
    assert punkt_fuer_plz("D-30159") == punkt_fuer_plz("30159")


def test_ortsname_findet_die_mitte_der_stadt():
    punkt = punkt_fuer_ort("Hannover")
    assert punkt is not None
    assert entfernung_km(punkt, punkt_fuer_plz("30159")) < 10


def test_ortsname_ist_gross_klein_egal():
    assert punkt_fuer_ort("hannover") == punkt_fuer_ort("Hannover")


def test_mittelpunkt_nimmt_beides():
    assert mittelpunkt("30159") == punkt_fuer_plz("30159")
    assert mittelpunkt("Hannover") == punkt_fuer_ort("Hannover")
    assert mittelpunkt("  ") is None


def test_entfernung_stimmt_mit_der_wirklichkeit():
    # Hannover - Hildesheim sind rund 30 km Luftlinie.
    km = entfernung_km(punkt_fuer_plz("30159"), punkt_fuer_plz("31134"))
    assert 25 < km < 35


def test_entfernung_zu_sich_selbst_ist_null():
    punkt = punkt_fuer_plz("30159")
    assert entfernung_km(punkt, punkt) == pytest.approx(0, abs=0.001)


def test_weite_strecke_stimmt():
    # Hamburg - München sind rund 610 km Luftlinie.
    km = entfernung_km(punkt_fuer_plz("20095"), punkt_fuer_plz("80331"))
    assert 590 < km < 630


def test_tabelle_ist_vollstaendig_genug():
    tabelle = plz_tabelle()
    assert len(tabelle) > 8000
    assert all(e["ort"] for e in tabelle.values())


def test_fehlende_tabelle_sagt_es_deutlich():
    plz_tabelle.cache_clear()
    with pytest.raises(FileNotFoundError, match="Postleitzahlen-Tabelle"):
        plz_tabelle("/gibt/es/nicht.csv")
    plz_tabelle.cache_clear()
