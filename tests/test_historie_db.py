"""Historie-Datenbank: das Gedaechtnis, das ein Neubau NICHT loeschen darf.

Entscheidung Dafina, 28.08.2026 (Weg A - zwei getrennte Datenbanken):
master.db bleibt ein Nachbau aus den Dateien und wird jedes Mal neu
gebaut. Was einmal passiert ist, gehoert dagegen hierher - Uebergabe an
ColdCaller, jeder Kontaktversuch, und vor allem der Widerspruch.

Der wichtigste Test dieser Datei ist der letzte: ein Opt-Out muss einen
kompletten Neubau von master.db ueberleben. Geht er verloren, schreiben
wir jemandem, der ausdruecklich Nein gesagt hat - das ist kein Fehler
mehr, das ist ein Rechtsverstoss.
"""
import json
import sqlite3
from pathlib import Path

import pytest

from pipeline import historie_db as h


# --------------------------------------------------------------- Aufbau

def test_datenbank_wird_angelegt(tmp_path):
    h.verbindung(tmp_path).close()
    assert (tmp_path / h.DB_NAME).exists()


def test_tabellen_sind_vollstaendig(tmp_path):
    db = h.verbindung(tmp_path)
    namen = {r[0] for r in db.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"coldcaller_uebergabe", "kontakt_versuch", "opt_out"} <= namen


def test_schema_enthaelt_kein_drop():
    """Die Sicherheit dieses Wegs haengt an genau einem Satz: hier wird
    nie geloescht. Steht irgendwann doch ein DROP im Schema, faellt es
    hier auf und nicht erst, wenn die Daten weg sind."""
    assert "DROP" not in h._SCHEMA.upper()
    assert "IF NOT EXISTS" in h._SCHEMA.upper()


def test_zweites_oeffnen_loescht_nichts(tmp_path):
    h.opt_out_eintragen(tmp_path, domain="beispiel.de", datum="2026-08-28",
                        weg="E-Mail")
    h.verbindung(tmp_path).close()          # noch einmal oeffnen
    assert len(h.opt_outs(tmp_path)) == 1


# ------------------------------------------------------------ Uebergabe

def test_uebergabe_wird_gespeichert(tmp_path):
    h.uebergabe_eintragen(tmp_path, kennung="beispiel.de", name="Max Mueller",
                          art_der_person="ColdCaller", datum="2026-08-28")
    eintraege = h.historie(tmp_path)["beispiel.de"]["uebergaben"]
    assert eintraege[0]["name"] == "Max Mueller"
    assert eintraege[0]["art_der_person"] == "ColdCaller"


# -------------------------------------------------------- Kontaktversuch

def test_kontaktversuche_bleiben_getrennt(tmp_path):
    for nummer in (1, 2, 3):
        h.kontakt_eintragen(tmp_path, kennung="beispiel.de", nummer=nummer,
                            produkt="IT-Wartung", durch_wen="Oliver",
                            weg="E-Mail", resultat="keine Antwort",
                            datum=f"2026-08-2{nummer}",
                            absender_email="oliver@uns.de")
    kontakte = h.historie(tmp_path)["beispiel.de"]["kontakte"]
    assert [k["nummer"] for k in kontakte] == [1, 2, 3]
    assert kontakte[0]["absender_email"] == "oliver@uns.de"


def test_gleicher_versuch_zweimal_bleibt_einer(tmp_path):
    """Ein Skript darf zweimal laufen, ohne die Historie zu verdoppeln."""
    for _ in range(2):
        h.kontakt_eintragen(tmp_path, kennung="beispiel.de", nummer=1,
                            produkt="IT-Wartung", durch_wen="Oliver",
                            weg="E-Mail", resultat="keine Antwort",
                            datum="2026-08-21", absender_email="oliver@uns.de")
    assert len(h.historie(tmp_path)["beispiel.de"]["kontakte"]) == 1


def test_kontaktnummer_muss_1_bis_3_sein(tmp_path):
    with pytest.raises(ValueError):
        h.kontakt_eintragen(tmp_path, kennung="beispiel.de", nummer=4,
                            datum="2026-08-28")


# ----------------------------------------------------------- Widerspruch

def test_opt_out_fuer_ganze_firma(tmp_path):
    h.opt_out_eintragen(tmp_path, domain="beispiel.de", datum="2026-08-28",
                        weg="E-Mail", notiz="Bitte keine Mails mehr")
    eintrag = h.opt_outs(tmp_path)[0]
    assert eintrag["domain"] == "beispiel.de"
    assert eintrag["weg"] == "E-Mail"


def test_opt_out_fuer_einzelne_person(tmp_path):
    h.opt_out_eintragen(tmp_path, email="person@beispiel.de",
                        datum="2026-08-28", weg="Telefon")
    eintrag = h.opt_outs(tmp_path)[0]
    assert eintrag["email"] == "person@beispiel.de"
    assert eintrag["domain"] == ""


def test_opt_out_braucht_domain_oder_email(tmp_path):
    with pytest.raises(ValueError):
        h.opt_out_eintragen(tmp_path, datum="2026-08-28", weg="E-Mail")


def test_opt_out_domain_wird_vereinheitlicht(tmp_path):
    """'https://WWW.Beispiel.de/kontakt' und 'beispiel.de' sind dieselbe
    Firma. Wer widerspricht, darf nicht an der Schreibweise scheitern."""
    h.opt_out_eintragen(tmp_path, domain="https://WWW.Beispiel.de/kontakt",
                        datum="2026-08-28", weg="E-Mail")
    assert h.opt_outs(tmp_path)[0]["domain"] == "beispiel.de"


def test_opt_out_zweimal_bleibt_einer(tmp_path):
    for _ in range(2):
        h.opt_out_eintragen(tmp_path, domain="beispiel.de",
                            datum="2026-08-28", weg="E-Mail")
    assert len(h.opt_outs(tmp_path)) == 1


# ------------------------------------------- das eigentliche Versprechen

def test_opt_out_ueberlebt_neubau_von_master_db(tmp_path):
    """Der Kern von Weg A. master.db wird komplett neu gebaut - der
    Widerspruch muss danach immer noch da sein."""
    from pipeline.master_db import bauen

    ziel = tmp_path / "laeufe" / "leadquellen" / "lauf1"
    ziel.mkdir(parents=True)
    (ziel / "firmen.json").write_text(json.dumps([{
        "name": "Beispiel GmbH", "domain": "beispiel.de",
        "website": "https://beispiel.de", "plz": "33602", "ort": "Bielefeld",
    }]), encoding="utf-8")

    h.opt_out_eintragen(tmp_path, domain="beispiel.de", datum="2026-08-28",
                        weg="E-Mail")
    for _ in range(3):
        bauen(str(tmp_path))

    assert [e["domain"] for e in h.opt_outs(tmp_path)] == ["beispiel.de"]


def test_historie_ueberlebt_auch_wenn_firma_verschwindet(tmp_path):
    """Eine Firma kann aus den Dateien fallen. Was ihr gegenueber passiert
    ist, bleibt trotzdem nachvollziehbar."""
    h.kontakt_eintragen(tmp_path, kennung="weg.de", nummer=1,
                        datum="2026-08-21", weg="E-Mail")
    from pipeline.master_db import bauen
    (tmp_path / "laeufe" / "leadquellen").mkdir(parents=True)
    bauen(str(tmp_path))
    assert "weg.de" in h.historie(tmp_path)


# ------------------------------------------ Anschluss an die Sperrliste

def test_opt_out_wirkt_in_der_globalen_sperrliste(tmp_path):
    """Es darf keinen zweiten, parallelen Schutz geben: wer hier
    widerspricht, muss ueber denselben Weg gesperrt sein wie bisher."""
    from pipeline.config import lade_globale_sperrlisten_eintraege

    (tmp_path / "sperrliste-global.yaml").write_text(
        "- domain: alt.de\n", encoding="utf-8")
    h.opt_out_eintragen(tmp_path, domain="neu.de", datum="2026-08-28",
                        weg="E-Mail")

    domains = {e["domain"] for e in
               lade_globale_sperrlisten_eintraege(str(tmp_path))}
    assert {"alt.de", "neu.de"} <= domains


def test_sperrliste_funktioniert_ohne_historie_datei(tmp_path):
    """Alte Projektordner haben noch keine historie.db - das darf die
    Sperrliste nicht zum Absturz bringen."""
    from pipeline.config import lade_globale_sperrlisten_eintraege

    (tmp_path / "sperrliste-global.yaml").write_text(
        "- domain: alt.de\n", encoding="utf-8")
    assert lade_globale_sperrlisten_eintraege(str(tmp_path))
