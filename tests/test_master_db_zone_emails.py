"""The database reads the addresses the zone runs paid for (Jira AP-210/221).

Dropcontact answers a zone in its own result file. Until 23.09.2026 the
database only saw those answers if somebody ran a write-back tool by
hand, and that had only been done for zones 32 to 34: 154 paid addresses
were missing, 137 of them from zones 35 to 39. The rebuild now reads the
result files itself, so nothing depends on remembering a step.

What must not change while doing that: an address already in the
database is never overwritten, and what Dropcontact sends along with it
(the person's number, the LinkedIn profile) only fills empty fields.
"""
import json
import sqlite3

import pytest

from pipeline.master_db import DB_NAME, bauen


def _write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


@pytest.fixture
def daten(tmp_path):
    _write(tmp_path / "laeufe/leadquellen/zona77-stadt-2026-01-01/firmen.json", [
        {"name": "A GmbH", "domain": "a.de", "website": "https://a.de",
         "plz": "77001", "quelle": "maps",
         "offers_automation_services": "no",
         "entscheider": [{"name": "Anna Alt", "vorname": "Anna",
                          "nachname": "Alt", "rolle": "Geschäftsführerin",
                          "quelle": "impressum"}]},
        # Bernd already has a checked address and a number of his own.
        {"name": "B GmbH", "domain": "b.de", "website": "https://b.de",
         "plz": "77002", "quelle": "maps",
         "offers_automation_services": "no",
         "entscheider": [{"name": "Bernd Bach", "vorname": "Bernd",
                          "nachname": "Bach", "rolle": "Inhaber",
                          "email": "alt@b.de", "status": "mail_geprueft",
                          "telefon": "0111 111", "quelle": "impressum"}]},
    ])
    _write(tmp_path / "laeufe/leadquellen/zona77-dropcontact-2026-01-02/ergebnisse.json", [
        {"name": "A GmbH", "domain": "a.de", "website": "https://a.de",
         "rolle": "Geschäftsführerin",
         "dropcontact": {"phone": "+49 700 1",
                         "linkedin": "https://linkedin.com/in/anna"},
         "leads": [{"first_name": "Anna", "last_name": "Alt",
                    "email": "anna@a.de", "title": "Geschäftsführerin",
                    "source": "dropcontact"}]},
        {"name": "B GmbH", "domain": "b.de", "website": "https://b.de",
         "dropcontact": {"phone": "+49 700 2"},
         "leads": [{"first_name": "Bernd", "last_name": "Bach",
                    "email": "neu@b.de", "source": "dropcontact"}]},
        # A result whose company is not in any collection - it must not
        # create a company out of a payment receipt.
        {"name": "Z GmbH", "domain": "z.de", "website": "https://z.de",
         "dropcontact": {},
         "leads": [{"first_name": "Zoe", "last_name": "Zink",
                    "email": "zoe@z.de", "source": "dropcontact"}]},
    ])
    return tmp_path


def _personen(daten_dir):
    db = sqlite3.connect(daten_dir / DB_NAME)
    db.row_factory = sqlite3.Row
    return {r["name"]: r for r in db.execute("SELECT * FROM decision_makers")}


def test_a_paid_address_reaches_the_database_without_a_hand_step(daten):
    bauen(str(daten))

    anna = _personen(daten)["Anna Alt"]
    assert anna["email"] == "anna@a.de"
    assert anna["email_art"] == "persoenlich"
    assert anna["status"] == "mail_geprueft"


def test_what_dropcontact_sent_along_fills_only_empty_fields(daten):
    bauen(str(daten))
    personen = _personen(daten)

    assert personen["Anna Alt"]["telefon"] == "+49 700 1"
    assert personen["Anna Alt"]["linkedin"] == "https://linkedin.com/in/anna"
    # Bernd had both already - a newer answer does not replace them.
    assert personen["Bernd Bach"]["email"] == "alt@b.de"
    assert personen["Bernd Bach"]["telefon"] == "0111 111"


def test_a_result_without_a_collected_company_is_left_out(daten):
    zahlen = bauen(str(daten))

    assert zahlen["firmen"] == 2
    assert "Zoe Zink" not in _personen(daten)
