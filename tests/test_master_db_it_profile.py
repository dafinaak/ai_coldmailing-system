"""The IT profile decides in the database too (Jira AP-221).

The rule of 31.08.2026 - only companies that maintain other companies' IT
are written to, not software makers, product partners or security
houses - lived in the run files and in the zone lists. The database did
not know it: on 23.09.2026, 110 of the 443 companies marked ready for a
campaign were ones our own rule had judged as "not our target", and 56
more had never been judged at all.

So the judgement moves into the database and counts like the automation
check: whoever is not clearly judged "yes" does not enter a campaign,
and the reason says which of the two it was. Nothing is guessed - an
unjudged company is blocked, not assumed to be fine.
"""
import json
import sqlite3

import pytest

from pipeline.master_db import DB_NAME, bauen


def _write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def _firma(domain, **rest):
    """A company that passes every other gate: automation checked "no",
    a decision-maker with a checked personal address."""
    return {"name": domain, "domain": domain, "website": f"https://{domain}",
            "plz": "30161", "quelle": "maps",
            "offers_automation_services": "no",
            "entscheider": [{"name": "Anna Alt", "vorname": "Anna",
                             "nachname": "Alt", "rolle": "Inhaberin",
                             "email": f"anna@{domain}",
                             "status": "mail_geprueft",
                             "quelle": "impressum"}],
            **rest}


@pytest.fixture
def daten(tmp_path):
    _write(tmp_path / "laeufe/leadquellen/sammlung-a/firmen.json", [
        _firma("ja.de", profil_passt=True, profil_typ="IT-Dienstleister"),
        _firma("nein.de", profil_passt=False,
               profil_typ="Softwarehersteller",
               profil_grund="Verkauft eigene Software"),
        _firma("unbekannt.de"),                    # never judged
        _firma("neubewertet.de", profil_passt=True,
               profil_typ="IT-Dienstleister"),
    ])
    # The later collection judges one company again, this time "no".
    _write(tmp_path / "laeufe/leadquellen/sammlung-b/firmen.json", [
        {"name": "neubewertet.de", "domain": "neubewertet.de",
         "quelle": "overpass", "profil_passt": False,
         "profil_typ": "Sicherheit", "profil_grund": "Pentest-Anbieter"},
    ])
    return tmp_path


def _firmen(daten_dir):
    db = sqlite3.connect(daten_dir / DB_NAME)
    db.row_factory = sqlite3.Row
    return {r["kennung"]: r for r in db.execute("SELECT * FROM companies")}


def test_a_judged_company_still_passes(daten):
    bauen(str(daten))

    ja = _firmen(daten)["ja.de"]
    assert ja["it_profil"] == "yes"
    assert ja["campaign_eligible"] == 1
    assert ja["ineligibility_reason"] == ""


def test_a_company_outside_the_it_profile_never_enters_a_campaign(daten):
    bauen(str(daten))

    nein = _firmen(daten)["nein.de"]
    assert nein["it_profil"] == "no"
    assert nein["campaign_eligible"] == 0
    assert nein["ineligibility_reason"] == "it_profile_no"
    assert "eigene Software" in nein["it_profil_grund"]


def test_a_company_that_was_never_judged_is_blocked_not_guessed(daten):
    bauen(str(daten))

    offen = _firmen(daten)["unbekannt.de"]
    assert offen["it_profil"] == "not_checked"
    assert offen["campaign_eligible"] == 0
    assert offen["ineligibility_reason"] == "it_profile_not_checked"


def test_a_newer_judgement_replaces_an_older_one(daten):
    # "no" is the answer that must not be lost on the way: it is the one
    # that keeps a wrong company out.
    bauen(str(daten))

    neu = _firmen(daten)["neubewertet.de"]
    assert neu["it_profil"] == "no"
    assert neu["campaign_eligible"] == 0
