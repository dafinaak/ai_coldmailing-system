"""Zonen je Zielgruppe: dieselbe Geografie, eigener Lauf (15.10.2026).

Die Prozessberater liegen im selben Postleitzahl-Gebiet wie die
IT-Dienstleister. Die Zonen-Tabelle hat aber eine Zeile je Zonen-Nummer,
und "32" ist fuer die IT vergeben. Darum eine zweite Tabelle, die die
Geografie der ersten WIEDERVERWENDET - gleiche Kreise, gleiche
Postleitzahl-Liste - und nur den Lauf-Ordner eigen hat. Zwei Kopien der
Kreise wuerden mit der Zeit auseinanderlaufen, und dann sucht die eine
Zielgruppe ein anderes Gebiet ab als die andere.
"""
import pytest

from pipeline import zonen


def test_ohne_angabe_ist_es_die_it_tabelle():
    assert zonen.zone("32") is zonen.ZONEN["32"]
    assert zonen.zone("32", "it") is zonen.ZONEN["32"]


@pytest.mark.parametrize("nr", ["32", "33", "34", "35", "36", "37", "38", "39"])
def test_prozess_teilt_die_geografie_der_it_zone(nr):
    it, pr = zonen.zone(nr, "it"), zonen.zone(nr, "prozess")
    assert zonen.kreise(nr, "prozess") == zonen.kreise(nr, "it")
    assert pr["plz"] == it["plz"]
    assert zonen.plz_kodes(nr, "prozess") == zonen.plz_kodes(nr, "it")


@pytest.mark.parametrize("nr", ["32", "39"])
def test_der_lauf_ordner_ist_eigen(nr):
    """Sonst schreiben beide Zielgruppen in denselben Ordner und die
    Firmen der einen landen in der Liste der anderen."""
    it, pr = zonen.zone(nr, "it"), zonen.zone(nr, "prozess")
    assert pr["lauf"] != it["lauf"]
    assert "prozess" in pr["lauf"]


def test_unbekannte_zielgruppe_ist_ein_fehler():
    with pytest.raises(KeyError, match="prozesse"):
        zonen.zone("32", "prozesse")


def test_eine_zone_ohne_prozess_zeile_ist_ein_fehler():
    """Die mittelgrossen Staedte haben keine Prozess-Zeile - danach zu
    fragen ist ein Fehler, keine stille IT-Zone."""
    with pytest.raises(KeyError):
        zonen.zone("890", "prozess")
