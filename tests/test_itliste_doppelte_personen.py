"""One person, one row - even when two runs hold the very same record.

Found on 29.09.2026: zones 44 and 45 were asked at Dropcontact a second
time, into a separate folder, so the catch-up companies could be added
without paying again for everyone already found. The final list merges
every "zona<NR>-dropcontact-*" folder of the zone, and Nils Kathagen
(zone 44) and Erik Bacher (zone 45) came out twice.

The dedupe itself was right - it keeps one entry per person. What went
wrong was the line that applied it: it filtered the rows by value

    daten = [f for f in daten if f in beste.values()]

and the two records were byte for byte identical, so both compared equal
to the kept one and both survived. Two identical rows mean the same
person can be written to twice from one campaign - the mistake that was
stopped on 17.08.2026.
"""
import importlib.util
from pathlib import Path

import pytest

PROJEKT = Path(__file__).resolve().parent.parent


def _werkzeug():
    pfad = PROJEKT / "werkzeuge" / "zona32-itliste-final.py"
    spec = importlib.util.spec_from_file_location("itliste_final", pfad)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def _firma(vorname, nachname, mail, rolle="", name="Firma GmbH"):
    return {"name": name, "rolle": rolle,
            "leads": [{"first_name": vorname, "last_name": nachname,
                       "email": mail}]}


def test_zwei_gleiche_eintraege_geben_eine_zeile():
    """Der Fall aus Zone 44: derselbe Datensatz in zwei Laufordnern."""
    modul = _werkzeug()
    einer = _firma("Nils", "Kathagen", "nk@systemhaus-ruhrgebiet.de",
                   rolle="Vertreten durch", name="IT-Systemhaus Ruhrgebiet GmbH")
    zwei = dict(einer)          # der zweite Ordner hat ihn unveraendert
    behalten, doppelte = modul.ohne_doppelte_personen([einer, zwei])
    assert len(behalten) == 1
    assert len(doppelte) == 1


def test_eintrag_mit_position_gewinnt():
    """Zwei Zeilen zur selben Person: die mit Position bleibt stehen."""
    modul = _werkzeug()
    ohne = _firma("Anna", "Alt", "a@a.de")
    mit = _firma("Anna", "Alt", "a@a.de", rolle="Geschäftsführerin")
    behalten, doppelte = modul.ohne_doppelte_personen([ohne, mit])
    assert [f["rolle"] for f in behalten] == ["Geschäftsführerin"]
    assert len(doppelte) == 1


def test_zwei_verschiedene_personen_bleiben_beide():
    modul = _werkzeug()
    behalten, doppelte = modul.ohne_doppelte_personen(
        [_firma("Anna", "Alt", "a@a.de"), _firma("Bernd", "Bach", "b@b.de")])
    assert len(behalten) == 2
    assert doppelte == []


def test_reihenfolge_bleibt_wie_gelesen():
    """Die Liste wird spaeter nummeriert - die Reihenfolge darf nicht
    davon abhaengen, in welchem Ordner jemand zuerst stand."""
    modul = _werkzeug()
    a = _firma("Anna", "Alt", "a@a.de")
    b = _firma("Bernd", "Bach", "b@b.de")
    c = _firma("Carla", "Cle", "c@c.de")
    behalten, _ = modul.ohne_doppelte_personen([a, b, c, dict(b)])
    assert [f["leads"][0]["first_name"] for f in behalten] == [
        "Anna", "Bernd", "Carla"]


def test_ohne_lead_faellt_raus():
    modul = _werkzeug()
    behalten, _ = modul.ohne_doppelte_personen(
        [{"name": "Ohne Person", "leads": []}, _firma("Anna", "Alt", "a@a.de")])
    assert len(behalten) == 1
