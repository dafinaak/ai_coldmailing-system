"""Everything Dropcontact returns must survive - not only the address.

Until 03.09.2026 batch_abholen() read exactly one field out of the answer,
"email", and dropped the rest of the row on the floor. That rest is not a
bonus: Dropcontact bills "pay on success" - one credit per verified
address, and the phone number, the LinkedIn profile and the company data
come inside that same paid row. Throwing them away meant paying for data
and then deleting it. Measured on the eight zones: 202 phone numbers and
110 LinkedIn profiles, all already paid for.

These tests pin that the extra fields come through, and - just as
important - that they never displace the address logic: an answer without
a usable "nominative@pro" address stays a miss, no matter how much other
data the row carries.
"""
import pytest

from pipeline.sources.dropcontact import DropcontactSource
from tests.test_dropcontact import FakeResponse, FakeSession, abgegeben, email


@pytest.fixture(autouse=True)
def _kein_guthaben_leck(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


ANFRAGE = [{"first_name": "Anna", "last_name": "Muster",
            "website": "https://a.de", "company": "A GmbH"}]


def fertig_mit(*zeilen):
    return FakeResponse(200, {"error": False, "success": True,
                              "data": list(zeilen)})


def holen(zeile):
    session = FakeSession([abgegeben("r1"), fertig_mit(zeile)])
    quelle = DropcontactSource("k", session=session, wartezeit=0)
    return quelle.batch_abholen("r1", [(0, ANFRAGE[0])], 1)[0]


def test_telefon_kommt_mit():
    ergebnis = holen({"first_name": "Anna", "last_name": "Muster",
                      "email": [email("anna@a.de")],
                      "phone": "+49 5121 10221"})
    assert ergebnis["email"] == "anna@a.de"
    assert ergebnis["felder"]["phone"] == "+49 5121 10221"


def test_linkedin_und_firmendaten_kommen_mit():
    ergebnis = holen({"first_name": "Anna", "last_name": "Muster",
                      "email": [email("anna@a.de")],
                      "linkedin": "https://linkedin.com/in/anna",
                      "company_linkedin": "https://linkedin.com/company/a",
                      "nb_employees": "42",
                      "siret_city": "Hannover", "siret_zip": "30159"})
    felder = ergebnis["felder"]
    assert felder["linkedin"] == "https://linkedin.com/in/anna"
    assert felder["company_linkedin"] == "https://linkedin.com/company/a"
    assert felder["nb_employees"] == "42"
    assert felder["siret_city"] == "Hannover"
    assert felder["siret_zip"] == "30159"


def test_leere_felder_stehen_nicht_im_ergebnis():
    """Ein leeres Feld ist keine Information. Stuende es drin, waere in der
    Liste nicht mehr zu sehen, ob Dropcontact nichts wusste oder ob wir
    nicht gefragt haben."""
    ergebnis = holen({"first_name": "Anna", "last_name": "Muster",
                      "email": [email("anna@a.de")],
                      "phone": "", "linkedin": None})
    assert "phone" not in ergebnis["felder"]
    assert "linkedin" not in ergebnis["felder"]


def test_eingabefelder_werden_nicht_wiederholt():
    """Name, Firma und Webseite haben wir selbst geschickt - sie gehoeren
    nicht in die Zusatzfelder, sonst stuende dieselbe Angabe zweimal in
    der Zeile und man wuesste nicht, welche gilt."""
    ergebnis = holen({"first_name": "Anna", "last_name": "Muster",
                      "full_name": "Anna Muster", "company": "A GmbH",
                      "website": "https://a.de",
                      "email": [email("anna@a.de")],
                      "phone": "+49 511 1"})
    for feld in ("first_name", "last_name", "full_name", "company",
                 "website", "email"):
        assert feld not in ergebnis["felder"], feld


def test_ohne_brauchbare_adresse_bleibt_es_ein_fehlschlag():
    """Eine Zeile voller Telefonnummern ohne persoenliche Adresse ist kein
    Treffer - sonst landete jemand ohne Mail in der Versandliste."""
    ergebnis = holen({"first_name": "Anna", "last_name": "Muster",
                      "email": [{"email": "info@a.de",
                                 "qualification": "generic@pro"}],
                      "phone": "+49 5121 10221",
                      "linkedin": "https://linkedin.com/in/anna"})
    assert ergebnis is None


def test_zeile_ganz_ohne_zusatzfelder_bleibt_gueltig():
    ergebnis = holen({"first_name": "Anna", "last_name": "Muster",
                      "email": [email("anna@a.de")]})
    assert ergebnis["email"] == "anna@a.de"
    assert ergebnis["felder"] == {}
