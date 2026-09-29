"""A newer run never drops what an older one found (Jira AP-221).

Until 23.09.2026 the decision-maker list of the newer run replaced the
older one completely. If the newer run did not find a person any more -
the website was rebuilt, the imprint changed, the reading failed - that
person disappeared from the database together with the address we had
paid for. The same held for the leads of a run.

Oliver's rule is the other way round: existing values are preserved, and
nothing is overwritten only because a newer source has a different
opinion. So the lists are merged: same name means the same person, empty
fields are filled, filled ones stay.
"""
import json
import sqlite3

import pytest

from pipeline.master_db import DB_NAME, bauen


def _write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def _person(name, vorname, nachname, rolle, **rest):
    return {"name": name, "vorname": vorname, "nachname": nachname,
            "rolle": rolle, "quelle": "impressum", **rest}


@pytest.fixture
def daten(tmp_path):
    # The older collection knows two people; Anna has a checked address.
    _write(tmp_path / "laeufe/leadquellen/sammlung-a/firmen.json", [
        {"name": "A GmbH", "domain": "a.de", "website": "https://a.de",
         "plz": "30161", "quelle": "maps",
         "offers_automation_services": "no",
         "entscheider": [
             _person("Anna Alt", "Anna", "Alt", "Inhaberin",
                     email="anna@a.de", status="mail_geprueft",
                     telefon="0111 1"),
             _person("Bernd Bach", "Bernd", "Bach", "Prokurist")]},
    ])
    # The newer one only finds Bernd - with another role and a number.
    _write(tmp_path / "laeufe/leadquellen/sammlung-b/firmen.json", [
        {"name": "A GmbH", "domain": "a.de", "quelle": "overpass",
         "entscheider": [
             _person("Bernd Bach", "Bernd", "Bach", "Geschäftsführer",
                     telefon="0222 2")]},
    ])
    return tmp_path


def _personen(daten_dir):
    db = sqlite3.connect(daten_dir / DB_NAME)
    db.row_factory = sqlite3.Row
    return {r["name"]: r for r in db.execute("SELECT * FROM decision_makers")}


def test_a_newer_run_does_not_drop_a_person_it_did_not_find(daten):
    bauen(str(daten))

    personen = _personen(daten)
    assert sorted(personen) == ["Anna Alt", "Bernd Bach"]
    assert personen["Anna Alt"]["email"] == "anna@a.de"


def test_the_newer_run_fills_empty_fields_but_keeps_the_old_ones(daten):
    bauen(str(daten))

    bernd = _personen(daten)["Bernd Bach"]
    assert bernd["rolle"] == "Prokurist"      # not replaced by the new opinion
    assert bernd["telefon"] == "0222 2"       # was empty, so it is filled


def test_addresses_from_two_campaign_runs_are_kept_together(tmp_path):
    firma = [{"name": "C GmbH", "domain": "c.de", "website": "https://c.de",
              "ausgang": "mit_entscheider", "offers_automation_services": "no"}]
    for stempel, lead in (("20260101-000000", ("Carla", "Curt", "carla@c.de")),
                          ("20260202-000000", ("Dora", "Dach", "dora@c.de"))):
        ziel = tmp_path / "laeufe/kunde-x" / stempel
        _write(ziel / "firmen.json", firma)
        _write(ziel / "leads.json", {"leads": [
            {"first_name": lead[0], "last_name": lead[1], "email": lead[2],
             "company": "C GmbH", "website": "https://c.de",
             "source": "impressum"}]})

    bauen(str(tmp_path))

    adressen = sorted(p["email"] for p in _personen(tmp_path).values())
    assert adressen == ["carla@c.de", "dora@c.de"]
