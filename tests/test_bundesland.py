"""Bundesland aus der Postleitzahl - aber nachgeschlagen, nicht geraten.

Olivers DataWarehouse-Liste hat ein Feld "Bundesland". Die naheliegende
Loesung waere, es an den ersten zwei Ziffern abzulesen. Genau das geht in
unseren eigenen Zonen schief: 34117 (Kassel) ist Hessen, 34414 (Warburg)
und 34434 (Borgentreich) sind Nordrhein-Westfalen. Beide stehen in den
Daten der Zone 34.

Deshalb wird nachgeschlagen und das Ergebnis gespeichert. Was nicht
eindeutig ist, bleibt leer - ein falsches Bundesland ist schlechter als
ein leeres Feld.
"""
import json

from pipeline import bundesland as b


def test_leere_plz_gibt_leer(tmp_path):
    assert b.nachschlagen("", {}) == ""
    assert b.nachschlagen(None, {}) == ""


def test_nachschlagen_aus_dem_speicher():
    assert b.nachschlagen("34117", {"34117": "Hessen"}) == "Hessen"


def test_unbekannte_plz_bleibt_leer():
    assert b.nachschlagen("34117", {}) == ""


def test_plz_wird_vereinheitlicht():
    """'34117 ' und 34117 als Zahl sind dieselbe Postleitzahl."""
    speicher = {"34117": "Hessen"}
    assert b.nachschlagen(" 34117 ", speicher) == "Hessen"
    assert b.nachschlagen(34117, speicher) == "Hessen"


def test_speicher_wird_gelesen_und_geschrieben(tmp_path):
    b.speicher_schreiben(tmp_path, {"34117": "Hessen"})
    assert b.speicher_lesen(tmp_path) == {"34117": "Hessen"}


def test_speicher_fehlt_gibt_leeren_speicher(tmp_path):
    assert b.speicher_lesen(tmp_path) == {}


def test_fuellen_fragt_nur_unbekannte(tmp_path):
    """Was schon im Speicher steht, wird nicht noch einmal abgefragt -
    sonst kostet jeder Neubau wieder tausend Anfragen."""
    gefragt = []

    def holen(plz):
        gefragt.append(plz)
        return "Hessen"

    b.speicher_schreiben(tmp_path, {"34117": "Hessen"})
    b.speicher_fuellen(tmp_path, ["34117", "35037"], holen=holen)
    assert gefragt == ["35037"]


def test_fuellen_speichert_das_ergebnis(tmp_path):
    b.speicher_fuellen(tmp_path, ["35037"], holen=lambda p: "Hessen")
    assert b.speicher_lesen(tmp_path)["35037"] == "Hessen"


def test_mehrdeutige_plz_bleibt_leer(tmp_path):
    """Liegt eine Postleitzahl in zwei Bundeslaendern, wird nichts
    behauptet."""
    assert b.aus_orten([{"federalState": {"name": "Hessen"}},
                        {"federalState": {"name": "Nordrhein-Westfalen"}}]) == ""


def test_eindeutige_plz_wird_uebernommen():
    assert b.aus_orten([{"federalState": {"name": "Hessen"}},
                        {"federalState": {"name": "Hessen"}}]) == "Hessen"


def test_leere_antwort_gibt_leer():
    assert b.aus_orten([]) == ""
    assert b.aus_orten(None) == ""


def test_fehlgeschlagene_abfrage_wird_nicht_gespeichert(tmp_path):
    """Ein Netzfehler darf sich nicht als 'kein Bundesland' festsetzen -
    sonst bleibt das Feld fuer immer leer, obwohl es eine Antwort gaebe."""
    def holen(plz):
        raise OSError("kein Netz")

    b.speicher_fuellen(tmp_path, ["35037"], holen=holen)
    assert "35037" not in b.speicher_lesen(tmp_path)


def test_master_db_schreibt_bundesland(tmp_path):
    """Der eigentliche Zweck: das Feld landet in der Datenbank."""
    import sqlite3

    from pipeline.master_db import DB_NAME, bauen

    ziel = tmp_path / "laeufe" / "leadquellen" / "lauf1"
    ziel.mkdir(parents=True)
    (ziel / "firmen.json").write_text(json.dumps([
        {"name": "Kassel GmbH", "domain": "kassel.de", "plz": "34117",
         "ort": "Kassel"},
        {"name": "Warburg GmbH", "domain": "warburg.de", "plz": "34414",
         "ort": "Warburg"},
    ]), encoding="utf-8")
    b.speicher_schreiben(tmp_path, {"34117": "Hessen",
                                    "34414": "Nordrhein-Westfalen"})

    bauen(str(tmp_path))
    db = sqlite3.connect(tmp_path / DB_NAME)
    laender = dict(db.execute("SELECT domain, bundesland FROM companies"))
    assert laender["kassel.de"] == "Hessen"
    assert laender["warburg.de"] == "Nordrhein-Westfalen"


def test_master_db_ohne_speicher_bleibt_leer(tmp_path):
    """Kein Speicher da: das Feld bleibt leer, der Neubau laeuft trotzdem
    durch und geht NICHT ins Netz."""
    import sqlite3

    from pipeline.master_db import DB_NAME, bauen

    ziel = tmp_path / "laeufe" / "leadquellen" / "lauf1"
    ziel.mkdir(parents=True)
    (ziel / "firmen.json").write_text(json.dumps([
        {"name": "Kassel GmbH", "domain": "kassel.de", "plz": "34117"},
    ]), encoding="utf-8")

    bauen(str(tmp_path))
    db = sqlite3.connect(tmp_path / DB_NAME)
    assert db.execute(
        "SELECT bundesland FROM companies").fetchone()[0] == ""
