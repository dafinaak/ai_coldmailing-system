"""Auf der Anruf-Liste muss der echte Grund stehen.

Gefunden am 14.08.2026 an einer echten Probe: Drei von fünf Firmen landeten
auf der Anruf-Liste mit "Fehler bei der Suche (später erneut versuchen)".
In Wahrheit war Hunters Prüf-Kontingent erschöpft - erneut versuchen hilft
dort erst nach dem Zurücksetzen. Wer mit der Liste telefoniert, probiert es
sonst sinnlos noch einmal.
"""
import json

import openpyxl

from pipeline.kontakte_excel import mappe_bauen
from pipeline.sourcing import fehler_satz


def test_kontingent_wird_als_solches_benannt():
    satz = fehler_satz(
        "Hunter antwortet mit 429 auf https://api.hunter.io/v2/email-verifier: "
        '{"errors": [{"id": "too_many_requests", "code": 429}]}')

    assert "Kontingent" in satz
    assert "später erneut versuchen" not in satz


def test_englische_kontingent_meldung_wird_erkannt():
    satz = fehler_satz(
        "You've reached the limit for the number of verifications per "
        "billing period included in your plan.")

    assert "Kontingent" in satz


def test_anderer_fehler_behaelt_den_alten_satz():
    satz = fehler_satz("Verbindung abgebrochen")

    assert satz == "Fehler bei der Suche (später erneut versuchen)"


def _lauf(tmp_path, firmen):
    lauf = tmp_path / "lauf"
    lauf.mkdir()
    (lauf / "firmen.json").write_text(json.dumps(firmen), encoding="utf-8")
    (lauf / "dedupe.json").write_text(json.dumps({"behalten": []}), encoding="utf-8")
    (lauf / "personalisierung.json").write_text(
        json.dumps({"fertig": [], "nacharbeit": []}), encoding="utf-8")
    return lauf


def _anruf_zeilen(lauf):
    blatt = mappe_bauen(lauf)["Anruf & Brief"]
    return list(blatt.iter_rows(min_row=2, values_only=True))


def test_excel_zeigt_den_genauen_grund(tmp_path):
    lauf = _lauf(tmp_path, [{
        "name": "Webdesign Haas", "ausgang": "fehler",
        "fehler_grund": "Prüf-Kontingent erschöpft - die Adresse konnte nicht "
                        "geprüft werden.",
        "telefon": "+49 162 9575407", "plz": "30161",
        "website": "http://www.webdesign-haas.de/"}])

    zeile = _anruf_zeilen(lauf)[0]
    # Spalte 2 seit 19.08.2026: davor steht "Person (falls gefunden)".
    assert "Kontingent" in zeile[2]
    assert "später erneut versuchen" not in zeile[2]


def test_ohne_genauen_grund_bleibt_der_sammelbegriff(tmp_path):
    # Alte Laufordner kennen das Feld nicht - sie sollen weiter lesbar sein.
    lauf = _lauf(tmp_path, [{"name": "Alte Firma", "ausgang": "fehler",
                             "telefon": "1", "plz": "2", "website": "x.de"}])

    zeile = _anruf_zeilen(lauf)[0]
    assert zeile[2] == "Fehler bei der Suche (später erneut versuchen)"


def test_firmen_mit_kontakt_stehen_nicht_auf_der_anruf_liste(tmp_path):
    lauf = _lauf(tmp_path, [
        {"name": "Mit Person", "ausgang": "mit_entscheider"},
        {"name": "Ohne Webseite", "ausgang": "keine_webseite"}])

    namen = [z[0] for z in _anruf_zeilen(lauf)]
    assert namen == ["Ohne Webseite"]
