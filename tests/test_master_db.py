"""Master-Datenbank: das wiederverwendbare Firmen-Gedaechtnis.

Olivers Auftrag (19.08.2026): Firmen gehen nie verloren, Herkunft bleibt
nachvollziehbar, Entscheider haengen an der Firma, ausgeschlossene
Automatisierungs-Anbieter bleiben gespeichert, und die Kampagnen-
Faehigkeit ist streng. Die Datenbank ist ein NACHBAU aus den Dateien -
loeschen und neu bauen aendert nichts am Ergebnis.
"""
import json
import sqlite3

import pytest

from pipeline.master_db import DB_NAME, bauen, export_excel


def _sammlung(daten_dir, ordner, firmen):
    ziel = daten_dir / "laeufe" / "leadquellen" / ordner
    ziel.mkdir(parents=True)
    (ziel / "firmen.json").write_text(json.dumps(firmen, ensure_ascii=False),
                                      encoding="utf-8")


def _lauf(daten_dir, slug, ts, firmen, leads=()):
    ziel = daten_dir / "laeufe" / slug / ts
    ziel.mkdir(parents=True)
    (ziel / "firmen.json").write_text(json.dumps(firmen, ensure_ascii=False),
                                      encoding="utf-8")
    (ziel / "leads.json").write_text(
        json.dumps({"leads": list(leads)}, ensure_ascii=False),
        encoding="utf-8")


@pytest.fixture
def daten(tmp_path):
    _sammlung(tmp_path, "sammlung-a", [
        {"name": "A GmbH", "domain": "a.de", "website": "https://a.de",
         "address": "Rolandstr. 2, 30161 Hannover", "plz": "30161",
         "ort": "Hannover", "telefon": "0511 1",
         "categories": ["IT-Service"], "quellen": ["maps", "gelbe_seiten"]},
        {"name": "B GmbH", "domain": "b.de", "website": "https://b.de",
         "plz": "30159", "categories": ["Softwareentwicklung"],
         "quelle": "maps"},
    ])
    # Eine zweite Sammlung kennt A ebenfalls - mit Zusatzfeld, ohne dass
    # etwas verloren gehen darf.
    _sammlung(tmp_path, "sammlung-b", [
        {"name": "A GmbH", "domain": "a.de", "vorhandene_email": "info@a.de",
         "quelle": "overpass"},
        {"name": "Robo GmbH", "domain": "robo.de", "website": "https://robo.de",
         "quelle": "maps"},
    ])
    _lauf(tmp_path, "kampagne-x", "20260819-120000", [
        {"name": "A GmbH", "domain": "a.de", "website": "https://a.de",
         "ausgang": "mit_entscheider", "offers_automation_services": "no",
         "automation_checked_at": "2026-08-19T12:00:00",
         "entscheider": [
             {"vorname": "Otto", "nachname": "Alt", "name": "Otto Alt",
              "rolle": "Inhaber", "linkedin": None, "quelle": "impressum",
              "status": "mail_geprueft", "email": "alt@a.de"},
             {"vorname": "Gerd", "nachname": "Chef", "name": "Gerd Chef",
              "rolle": "Geschäftsführer", "linkedin": None,
              "quelle": "impressum", "status": "ohne_mail"}],
         "entscheider_primaer": {"name": "Otto Alt", "rolle": "Inhaber"}},
        {"name": "Robo GmbH", "domain": "robo.de", "website": "https://robo.de",
         "ausgang": "wettbewerber", "offers_automation_services": "yes",
         "automation_check_reason": "Prozessautomatisierung",
         "automation_checked_at": "2026-08-19T12:00:00",
         "campaign_eligible": False,
         "campaign_ineligibility_reason": "automation_provider"},
    ], leads=[
        {"first_name": "Otto", "last_name": "Alt", "email": "alt@a.de",
         "company": "A GmbH", "title": "Inhaber (laut Impressum)",
         "website": "https://a.de", "source": "impressum"},
    ])
    return tmp_path


def _db(daten_dir):
    verbindung = sqlite3.connect(daten_dir / DB_NAME)
    verbindung.row_factory = sqlite3.Row
    return verbindung


def test_jede_firma_genau_einmal_und_nichts_geht_verloren(daten):
    zahlen = bauen(daten)
    assert zahlen["firmen"] == 3          # A, B, Robo - A nur einmal

    db = _db(daten)
    a = db.execute("SELECT * FROM companies WHERE domain='a.de'").fetchone()
    # Felder aus BEIDEN Sammlungen und dem Lauf sind zusammengefuehrt.
    assert a["telefon"] == "0511 1"
    assert a["email_allgemein"] == "info@a.de"
    assert a["strasse"] == "Rolandstr. 2"
    assert a["ort"] == "Hannover" and a["plz"] == "30161"
    assert a["ceo_owner"] == "Otto Alt - Inhaber"


def test_herkunft_bleibt_je_quelle_nachvollziehbar(daten):
    bauen(daten)
    db = _db(daten)
    belege = db.execute(
        """SELECT provider, herkunft FROM company_sources cs
           JOIN companies c ON c.id = cs.company_id
           WHERE c.domain='a.de'""").fetchall()
    anbieter = {b["provider"] for b in belege}
    assert {"maps", "gelbe_seiten", "overpass", "lauf"} <= anbieter
    assert any("sammlung-a" in b["herkunft"] for b in belege)


def test_mehrere_entscheider_je_firma_bester_rang_zuerst(daten):
    bauen(daten)
    db = _db(daten)
    personen = db.execute(
        """SELECT dm.* FROM decision_makers dm
           JOIN companies c ON c.id = dm.company_id
           WHERE c.domain='a.de' ORDER BY dm.id""").fetchall()
    assert [p["name"] for p in personen] == ["Otto Alt", "Gerd Chef"]
    assert personen[0]["email"] == "alt@a.de"
    assert personen[0]["email_art"] == "persoenlich"
    assert personen[1]["status"] == "ohne_mail"


def test_persoenliche_und_allgemeine_mail_bleiben_getrennt(daten):
    bauen(daten)
    db = _db(daten)
    a = db.execute("SELECT * FROM companies WHERE domain='a.de'").fetchone()
    assert a["email_allgemein"] == "info@a.de"
    mail = db.execute(
        """SELECT email FROM decision_makers dm JOIN companies c
           ON c.id=dm.company_id WHERE c.domain='a.de'
           AND email_art='persoenlich'""").fetchone()
    assert mail["email"] == "alt@a.de"


def test_kampagnenfaehigkeit_ist_streng(daten):
    bauen(daten)
    db = _db(daten)
    faehig = {z["domain"]: (z["campaign_eligible"], z["ineligibility_reason"])
              for z in db.execute("SELECT * FROM companies")}
    assert faehig["a.de"] == (1, "")
    # Wettbewerber: gespeichert, aber nie kampagnenfaehig.
    assert faehig["robo.de"] == (0, "automation_provider")
    # Ohne Automatisierungs-Pruefung keine Kampagne (Punkt 16, streng).
    assert faehig["b.de"] == (0, "automation_not_checked")


def test_neubau_ist_wiederholbar(daten):
    erste = bauen(daten)
    zweite = bauen(daten)
    assert erste["firmen"] == zweite["firmen"]
    db = _db(daten)
    assert db.execute("SELECT COUNT(*) FROM companies").fetchone()[0] == 3


def test_export_traegt_olivers_spalten_und_a_bis_e(daten):
    import openpyxl

    ziel = export_excel(daten)
    blatt = openpyxl.load_workbook(ziel)["Firmen-Master"]
    zeilen = [list(r) for r in blatt.iter_rows(values_only=True)]
    kopf = zeilen[0]

    for spalte in ("Sektor", "Firma", "CEO/Inhaber", "Straße", "Ort", "PLZ",
                   "Land", "Tel", "E-Mail (allgemein)", "Webseite",
                   "A) Name", "A) Rolle", "A) E-Mail", "B) Name",
                   "E) E-Mail", "Automatisierungs-Anbieter",
                   "Kampagnenfähig", "Ausschlussgrund"):
        assert spalte in kopf, spalte

    a_zeile = next(z for z in zeilen[1:] if z[kopf.index("Firma")] == "A GmbH")
    assert a_zeile[kopf.index("A) Name")] == "Otto Alt"
    assert a_zeile[kopf.index("A) E-Mail")] == "alt@a.de"
    assert a_zeile[kopf.index("B) Name")] == "Gerd Chef"
    assert a_zeile[kopf.index("Kampagnenfähig")] == "ja"

    robo = next(z for z in zeilen[1:] if z[kopf.index("Firma")] == "Robo GmbH")
    assert robo[kopf.index("Kampagnenfähig")] == "nein"
    assert robo[kopf.index("Ausschlussgrund")] == "automation_provider"
