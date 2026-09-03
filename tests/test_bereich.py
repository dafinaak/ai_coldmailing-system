"""Entscheider-Bereich aus der Rolle - abgeleitet, nicht geraten."""
import json
import sqlite3

from pipeline.bereich import aus_rolle
from pipeline.master_db import DB_NAME, bauen


def test_geschaeftsfuehrung_in_allen_schreibweisen():
    for rolle in ("Geschäftsführer", "Geschäftsführung (laut Impressum)",
                  "Inhaber", "Inh.", "GF", "Vorstand", "Geschäftsführerin",
                  "vertretungsberechtigter Gesellschafter", "Vertreten durch"):
        assert aus_rolle(rolle) == "Geschäftsführung", rolle


def test_aufsichtsrat_ist_ein_eigener_bereich():
    """Der Aufsichtsrat kontrolliert - er ist kein Einkaufsentscheider,
    deshalb darf er nicht unter Geschaeftsfuehrung verschwinden."""
    assert aus_rolle("Vorsitzender des Aufsichtsrats") == "Aufsichtsrat"
    assert aus_rolle("Aufsichtsratvorsitzender") == "Aufsichtsrat"


def test_fachbereiche():
    assert aus_rolle("Vertriebsleiter") == "Vertrieb"
    assert aus_rolle("Head of Marketing") == "Marketing"
    assert aus_rolle("Leiter Einkauf") == "Einkauf"
    assert aus_rolle("Kaufmännische Leitung") == "Finanzen"
    assert aus_rolle("Personalleiterin") == "Personal"
    assert aus_rolle("IT-Leiter") == "IT"


def test_leitungsebene_schlaegt_fachbereich():
    """"Geschaeftsfuehrer IT" leitet die Firma, nicht die IT-Abteilung."""
    assert aus_rolle("Geschäftsführer IT") == "Geschäftsführung"


def test_ohne_rolle_bleibt_leer():
    assert aus_rolle("") == ""
    assert aus_rolle(None) == ""
    assert aus_rolle("   ") == ""


def test_unbekannte_rolle_bleibt_leer():
    """Nicht raten: eine Rolle, die keinen Bereich nennt, bekommt keinen."""
    assert aus_rolle("Mitarbeiter") == ""
    assert aus_rolle("Ansprechpartner") == ""


def test_bereich_landet_in_der_datenbank(tmp_path):
    """Bisher stand hier fest eine leere Zeichenkette - das Feld war zu
    100% leer, obwohl die Angabe in der Rolle stand."""
    ziel = tmp_path / "laeufe" / "leadquellen" / "lauf1"
    ziel.mkdir(parents=True)
    (ziel / "firmen.json").write_text(json.dumps([{
        "name": "A GmbH", "domain": "a.de",
        "entscheider": [
            {"name": "Anna Chef", "vorname": "Anna", "nachname": "Chef",
             "rolle": "Geschäftsführerin"},
            {"name": "Bernd Vertrieb", "vorname": "Bernd",
             "nachname": "Vertrieb", "rolle": "Vertriebsleiter"},
        ]}], ensure_ascii=False), encoding="utf-8")

    bauen(str(tmp_path))
    db = sqlite3.connect(tmp_path / DB_NAME)
    bereiche = dict(db.execute("SELECT name, bereich FROM decision_makers"))
    assert bereiche["Anna Chef"] == "Geschäftsführung"
    assert bereiche["Bernd Vertrieb"] == "Vertrieb"
