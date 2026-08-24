"""Kein Versand ohne ausdrückliche menschliche Freigabe.

Auftrag Dafinas vom 21.08.2026, Anlass: Björn Hagen (Nivako) und Achim
Gärtner (GRTNR.IT) hatten Mails bekommen und ihre Streichung verlangt.

Was hier festgenagelt wird:
  - eine Kampagne ANLEGEN ist keine Freigabe zu senden;
  - nichts aktiviert oder setzt sich von selbst fort;
  - eine Freigabe gilt für genau EINE Kampagne und ist widerrufbar;
  - gesperrte Empfänger kommen auf KEINEM Import-Weg an Instantly vorbei,
    auch nicht über die eigene Ansichts-Probe.

Hier geht nichts ins Netz: der Sender ist eine Attrappe, die jeden
Aufruf nur aufschreibt. Es wird keine einzige Mail verschickt.
"""
import json

import pytest
import yaml

from pipeline import versand_freigabe
from pipeline.senders.instantly import InstantlySender
from pipeline.versand_freigabe import VersandGesperrt


class _MitschriftSender(InstantlySender):
    """Echte Klasse, aber ohne Netz: _post wird nur mitgeschrieben."""

    def __init__(self):
        self.aufrufe = []

    def _post(self, url, daten):
        self.aufrufe.append((url, daten))
        return {}


def _sperrliste(tmp_path, eintraege):
    (tmp_path / "sperrliste-global.yaml").write_text(
        yaml.safe_dump(eintraege, allow_unicode=True), encoding="utf-8")


# --- Freigabe: anlegen ist nicht senden --------------------------------

def test_kampagne_anlegen_ist_keine_freigabe(tmp_path):
    # Der Lauf-Ordner existiert, die Kampagne ist angelegt - und trotzdem
    # gilt: gesperrt, bis ein Mensch ausdrücklich freigibt.
    assert versand_freigabe.lesen(tmp_path) is None
    assert versand_freigabe.ist_freigegeben(tmp_path, "c1") is False
    with pytest.raises(VersandGesperrt):
        versand_freigabe.pruefen(tmp_path, "c1")


def test_ohne_freigabe_wird_nicht_aktiviert(tmp_path):
    sender = _MitschriftSender()
    with pytest.raises(VersandGesperrt):
        sender.aktiviere_kampagne("c1")
    assert sender.aufrufe == []          # nichts ging an Instantly


def test_erst_nach_ausdruecklicher_freigabe_darf_aktiviert_werden(tmp_path):
    sender = _MitschriftSender()
    freigabe = versand_freigabe.erteilen(tmp_path, "c1", "dafina")

    sender.aktiviere_kampagne("c1", freigabe=freigabe)

    assert [u for u, _ in sender.aufrufe] == [
        "https://api.instantly.ai/api/v2/campaigns/c1/activate"]
    assert freigabe["freigegeben_von"] == "dafina"
    assert freigabe["freigegeben_am"]


def test_freigabe_gilt_nur_fuer_ihre_eigene_kampagne(tmp_path):
    sender = _MitschriftSender()
    freigabe = versand_freigabe.erteilen(tmp_path, "c1", "dafina")

    with pytest.raises(VersandGesperrt):
        sender.aktiviere_kampagne("c2", freigabe=freigabe)
    assert sender.aufrufe == []
    with pytest.raises(VersandGesperrt):
        versand_freigabe.pruefen(tmp_path, "c2")


def test_widerrufene_freigabe_erlaubt_nichts_mehr(tmp_path):
    sender = _MitschriftSender()
    versand_freigabe.erteilen(tmp_path, "c1", "dafina")
    versand_freigabe.widerrufen(tmp_path, "dafina")

    assert versand_freigabe.ist_freigegeben(tmp_path, "c1") is False
    with pytest.raises(VersandGesperrt):
        versand_freigabe.pruefen(tmp_path, "c1")
    with pytest.raises(VersandGesperrt):
        sender.aktiviere_kampagne("c1", freigabe=versand_freigabe.lesen(tmp_path))
    assert sender.aufrufe == []


def test_freigabe_ohne_menschen_ist_keine_freigabe(tmp_path):
    with pytest.raises(ValueError):
        versand_freigabe.erteilen(tmp_path, "c1", "")
    # Auch eine von Hand hingelegte Datei ohne Namen zählt nicht.
    versand_freigabe.pfad(tmp_path).write_text(
        json.dumps({"campaign_id": "c1", "freigegeben_von": ""}),
        encoding="utf-8")
    with pytest.raises(VersandGesperrt):
        versand_freigabe.pruefen(tmp_path, "c1")


def test_unlesbare_freigabe_gilt_als_keine(tmp_path):
    versand_freigabe.pfad(tmp_path).write_text("kein JSON", encoding="utf-8")
    assert versand_freigabe.ist_freigegeben(tmp_path, "c1") is False
    with pytest.raises(VersandGesperrt):
        versand_freigabe.pruefen(tmp_path, "c1")


def test_kein_selbsttaetiges_fortsetzen(tmp_path):
    # Eine einmal erteilte und benutzte Freigabe darf nach dem Widerruf
    # nicht "wieder aufleben" - es gibt keinen Weg zurück ausser einer
    # neuen, ausdrücklichen Freigabe.
    sender = _MitschriftSender()
    freigabe = versand_freigabe.erteilen(tmp_path, "c1", "dafina")
    sender.aktiviere_kampagne("c1", freigabe=freigabe)
    versand_freigabe.widerrufen(tmp_path, "dafina")

    with pytest.raises(VersandGesperrt):
        versand_freigabe.pruefen(tmp_path, "c1")

    neu = versand_freigabe.erteilen(tmp_path, "c1", "dafina")
    sender.aktiviere_kampagne("c1", freigabe=neu)
    assert len(sender.aufrufe) == 2


# --- Sperrliste: die beiden Betroffenen --------------------------------

def test_gesperrte_person_kommt_nicht_in_den_import(tmp_path, monkeypatch):
    _sperrliste(tmp_path, [
        {"email": "hagen.bjoern@nivako.de", "reason": "Widerspruch"}])
    monkeypatch.chdir(tmp_path)
    sender = _MitschriftSender()

    with pytest.raises(ValueError, match="gesperrte"):
        sender.import_leads("c1", [{"email": "hagen.bjoern@nivako.de",
                                    "betreff": "B", "mail_1": "1",
                                    "follow_up_1": "2", "follow_up_2": "3"}])
    assert sender.aufrufe == []


def test_gesperrte_domain_deckt_jede_adresse_der_firma(tmp_path, monkeypatch):
    _sperrliste(tmp_path, [{"domain": "grtnr.it", "reason": "Widerspruch"}])
    monkeypatch.chdir(tmp_path)
    sender = _MitschriftSender()

    with pytest.raises(ValueError, match="gesperrte"):
        sender.import_leads_mit_anrede("c1", [{
            "email": "achim.gaertner@grtnr.it", "anrede": "Guten Tag",
            "first_name": "Achim", "last_name": "Gärtner"}])
    assert sender.aufrufe == []


def test_sperre_gilt_auch_fuer_die_eigene_ansichts_probe(tmp_path, monkeypatch):
    # eigene_adresse=True hebelt die Sammeladressen-Regel aus - die
    # Sperrliste darf es NICHT aushebeln.
    _sperrliste(tmp_path, [
        {"email": "hagen.bjoern@nivako.de", "reason": "Widerspruch"}])
    monkeypatch.chdir(tmp_path)
    sender = _MitschriftSender()

    with pytest.raises(ValueError, match="gesperrte"):
        sender.import_leads("c1", [{"email": "hagen.bjoern@nivako.de",
                                    "betreff": "B", "mail_1": "1",
                                    "follow_up_1": "2", "follow_up_2": "3"}],
                            eigene_adresse=True)
    assert sender.aufrufe == []


def test_nicht_gesperrte_adresse_geht_weiter_durch(tmp_path, monkeypatch):
    _sperrliste(tmp_path, [{"domain": "grtnr.it", "reason": "Widerspruch"}])
    monkeypatch.chdir(tmp_path)
    sender = _MitschriftSender()

    sender.import_leads("c1", [{"email": "otto.alt@sauber.de", "betreff": "B",
                                "mail_1": "1", "follow_up_1": "2",
                                "follow_up_2": "3"}])

    assert [u for u, _ in sender.aufrufe] == [
        "https://api.instantly.ai/api/v2/leads/add"]


def test_kaputte_sperrliste_stoppt_den_import(tmp_path, monkeypatch):
    # "Sperrliste unlesbar" darf nie "dann eben ohne Sperre" heissen.
    (tmp_path / "sperrliste-global.yaml").write_text(
        "das: ist keine Liste\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    sender = _MitschriftSender()

    with pytest.raises(ValueError, match="Sperrliste"):
        sender.import_leads("c1", [{"email": "otto@sauber.de", "betreff": "B",
                                    "mail_1": "1", "follow_up_1": "2",
                                    "follow_up_2": "3"}])
    assert sender.aufrufe == []


def test_die_echte_projekt_sperrliste_kennt_beide_betroffenen():
    # Der eigentliche Auftrag: diese beiden nie wieder.
    from pathlib import Path

    from pipeline.config import (lade_gesperrte_adressen,
                                 lade_globale_sperrliste)

    wurzel = Path(__file__).resolve().parents[1]
    adressen = set(lade_gesperrte_adressen(wurzel))
    domains = set(lade_globale_sperrliste(wurzel))

    assert "hagen.bjoern@nivako.de" in adressen     # Björn Hagen
    assert "achim@grtnr.it" in adressen             # Achim Gärtner
    assert "nivako.de" in domains
    assert "grtnr.it" in domains
