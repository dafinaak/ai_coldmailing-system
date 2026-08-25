"""Tests für den FullEnrich-Abdeckungstest.

Kein Netz, keine Credits. Der wichtigste Test hier ist der letzte: es
darf KEINEN Codepfad zur teuren Anreicherung geben.
"""
import pathlib

import pytest

from pipeline.fullenrich_abdeckung import (
    bericht_text, kennzahlen_rechnen, kosten_schaetzen, person_beurteilen)


def person(titel=None, headline="", firma="Beispiel GmbH",
           domain="beispiel.de", name="Anna Beispiel"):
    stelle = {"is_current": True,
              "company": {"name": firma, "domain": domain}}
    if titel is not None:
        stelle["title"] = titel
    return {"full_name": name, "first_name": name.split()[0],
            "last_name": name.split()[-1], "headline": headline,
            "employment": [stelle],
            "social_profiles": {"professional_network": {"url": "https://x/y"}}}


UNSERE = {"name": "Beispiel GmbH", "domain": "beispiel.de",
          "website": "https://beispiel.de"}


# --------------------------------------------------------- Personen-Urteil

@pytest.mark.parametrize("titel", [
    "CEO", "Chief Executive Officer", "Geschäftsführer", "Geschäftsführerin",
    "Owner", "Inhaber", "Inhaberin", "Managing Director", "Founder",
    "Gründer", "Managing Partner", "Proprietor"])
def test_echte_entscheider_titel_gelten(titel):
    urteil = person_beurteilen(person(titel), UNSERE)
    assert urteil["urteil"] == "valid"
    assert titel in urteil["begruendung"]


def test_ohne_stellentitel_kein_entscheider():
    urteil = person_beurteilen(
        person(None, "Digital problem solver in all things web"), UNSERE)
    assert urteil["urteil"] == "no_job_title"
    assert urteil["job_title"] == ""
    # Die headline muss im Bericht sichtbar sein - sonst sieht niemand,
    # WAS FullEnrich statt eines Titels geliefert hat.
    assert "Digital problem solver" in urteil["begruendung"]
    assert urteil["headline"].startswith("Digital problem solver")


def test_headline_wird_nie_zum_titel():
    urteil = person_beurteilen(person(None, "CEO bei irgendwas"), UNSERE)
    # Auch wenn "CEO" in der headline steht: kein Titel, kein Entscheider.
    assert urteil["urteil"] == "no_job_title"
    assert urteil["job_title"] == ""


def test_unpassender_titel_wird_abgelehnt():
    urteil = person_beurteilen(person("Werkstudent"), UNSERE)
    assert urteil["urteil"] == "unrelated_title"
    assert "Werkstudent" in urteil["begruendung"]


def test_fremde_domain_ist_company_mismatch():
    urteil = person_beurteilen(
        person("CEO", domain="ganzanders.de"), UNSERE)
    assert urteil["urteil"] == "company_mismatch"
    assert "ganzanders.de" in urteil["begruendung"]


def test_fremder_firmenname_ohne_domain_ist_company_mismatch():
    urteil = person_beurteilen(
        person("CEO", firma="Ganz Andere AG", domain=""), UNSERE)
    assert urteil["urteil"] == "company_mismatch"


def test_teilweise_gleicher_firmenname_ist_in_ordnung():
    urteil = person_beurteilen(
        person("Geschäftsführer", firma="Beispiel", domain=""), UNSERE)
    assert urteil["urteil"] == "valid"


# ------------------------------------------------------------- Kennzahlen

def _firma(gefunden=1, personen=0, gueltig=0):
    return {"fullenrich_company_found": gefunden,
            "people_returned": personen, "valid_decision_makers": gueltig}


def _person_zeile(urteil, titel=""):
    return {"urteil": urteil, "job_title": titel}


def test_kennzahlen_trennen_titel_von_urteil():
    firmen = [_firma(1, 2, 1), _firma(1, 1, 0), _firma(0, 0, 0)]
    personen = [_person_zeile("valid", "CEO"),
                _person_zeile("no_job_title", ""),
                _person_zeile("unrelated_title", "Werkstudent")]
    k = kennzahlen_rechnen(firmen, personen)
    assert k["companies_tested"] == 3
    assert k["companies_matched"] == 2
    assert k["companies_not_found"] == 1
    assert k["total_people_returned"] == 3
    assert k["people_with_real_job_title"] == 2
    assert k["people_without_job_title"] == 1
    assert k["valid_decision_makers"] == 1
    assert k["uncertain_decision_makers"] == 1
    assert k["companies_with_valid_dm"] == 1
    assert k["companies_without_valid_dm"] == 2


def test_quoten_teilen_nicht_durch_null():
    k = kennzahlen_rechnen([], [])
    assert k["company_match_rate"] == 0.0
    assert k["valid_dm_rate_among_people"] == 0.0


def test_bericht_nennt_alle_elf_kennzahlen():
    text = bericht_text(kennzahlen_rechnen([_firma()], []))
    for stueck in ("Companies tested", "Companies matched",
                   "Companies not found", "Total people returned",
                   "People with a real job title", "People WITHOUT a job title",
                   "Valid decision makers", "Uncertain", "Company mismatches",
                   "Companies with >=1 valid DM", "Companies with ZERO valid DM",
                   "company match rate", "Valid DM rate per company",
                   "Valid DM rate among returned people",
                   "No-decision-maker rate"):
        assert stueck in text, stueck


def test_bericht_zeigt_credits_wenn_bekannt():
    text = bericht_text(kennzahlen_rechnen([_firma()], []), 100.0, 81.25)
    assert "Credits before" in text
    assert "18.75" in text


# ----------------------------------------------------------------- Kosten

def test_kostenschaetzung_rechnet_nur_mit_suche():
    kosten = kosten_schaetzen(25, personen_je_firma=2.0)
    assert kosten["company_lookups"] == 6.25      # 25 * 0,25
    assert kosten["people_search"] == 12.5        # 25 * 2 * 0,25
    assert kosten["gesamt"] == 18.75


# --------------------------------------------------------------- Sicherung

def test_dieses_modul_kann_keine_anreicherung_ausloesen():
    """Die Sicherung gegen teure Aufrufe ist kein Vorsatz, sondern das
    Fehlen jedes Codepfads dorthin. Dieser Test hält das fest."""
    quelle = pathlib.Path(
        "pipeline/fullenrich_abdeckung.py").read_text(encoding="utf-8")
    code = "\n".join(zeile for zeile in quelle.split("\n")
                     if not zeile.strip().startswith("#"))
    # Der Doppelpunkt-Block ganz oben ist Dokumentation - der Code selbst
    # darf diese Namen nirgends benutzen.
    ohne_docstring = code.split('"""', 2)[-1]
    for verboten in ("anreicherung_starten", "anreicherung_abholen",
                     "enrich/bulk", "contact.work_emails",
                     "contact.personal_emails", "contact.phones"):
        assert verboten not in ohne_docstring, verboten
