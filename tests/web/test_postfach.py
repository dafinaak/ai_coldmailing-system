"""Tests fuer den Postfach-Bereich (Task 9): rein lesende Konversationsliste
+ Detailbereich in EINEM Screen (siehe web.routen.postfach Modul-Docstring).
Instantly ist ueber app.state.instantly_leser gefaked - exakt das Muster aus
tests/web/test_kampagnen.py (dort FakeInstantlyLeser.kampagnen_stand, hier
FakeInstantlyLeser.emails_stand). Fuer die Firmen-Anreicherung braucht es
echte leads.json-Eintraege wie in tests/web/test_kontakte.py (_lauf dort)."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient
from passlib.context import CryptContext

from pipeline.approval import approve
from pipeline.run_store import RunStore
from web.app import create_app

PWD_CONTEXT = CryptContext(schemes=["bcrypt"], deprecated="auto")

KUNDE_A_YAML = """
name: Demo GmbH
zielgruppe:
  titel: [CEO]
angebot: Testangebot
tonalitaet: ruhig
absender: Jonas Wilde
follow_up_tage: [4, 9]
test_empfaenger: [anna@firma.de]
sperrliste: []
"""


class FakeInstantlyLeser:
    """Ersetzt web.instantly_leser.InstantlyLeser.emails_stand - liefert
    vorbereitete Rohdaten statt echter HTTP-Aufrufe. `emails_by_campaign`
    bildet campaign_id auf eine Liste roher Email-Objekte ab (wie sie das
    Schema liefert, siehe web.instantly_leser Modul-Docstring)."""

    def __init__(self, emails_by_campaign: dict | None = None, erreichbar: bool = True,
                 stand: datetime | None = None):
        self.emails_by_campaign = emails_by_campaign or {}
        self.erreichbar = erreichbar
        self.stand = stand if stand is not None else datetime(2026, 7, 20, 9, 30)
        self.angefragt: list[str] = []

    def emails_stand(self, campaign_ids):
        self.angefragt = list(campaign_ids)
        ergebnis = {}
        for cid in campaign_ids:
            ergebnis[cid] = {
                "items": self.emails_by_campaign.get(cid, []),
                "erreichbar": self.erreichbar,
                "stand": self.stand if self.erreichbar else None,
            }
        return ergebnis


def _email(campaign_id="camp-1", ue_type=1, to="anna@firma.de", frm=None,
           betreff="Anschreiben", zeit="2026-07-20T09:00:00.000Z", text="Text der Mail"):
    return {
        "id": "mail-1", "campaign_id": campaign_id, "ue_type": ue_type,
        "to_address_email_list": to, "from_address_email": frm,
        "subject": betreff, "timestamp_email": zeit, "timestamp_created": zeit,
        "body": {"text": text}, "content_preview": text, "eaccount": "wir@digitaldiamonds.de",
    }


def _lead(vorname, nachname, email, firma):
    return {"first_name": vorname, "last_name": nachname, "email": email,
            "company": firma, "title": "CEO", "website": "https://" + firma.lower() + ".de",
            "source": "apollo"}


def _lauf(daten_dir: Path, slug: str, kunde_datei: str, ts: str, leads: list, *,
          campaign_id: str = "camp-1", name: str = "Lena Hartmann") -> Path:
    """Baut einen vollstaendig uebergebenen Lauf (Freigabe + versand_komplett)
    mit echten leads.json-Eintraegen - noetig, damit sowohl
    web.routen.kampagnen._alle_laeufe (liefert die campaign_id) als auch
    web.kontakte.sammle_kontakte (liefert die Firma zur Anreicherung) etwas
    zum Finden haben."""
    lauf_dir = daten_dir / "laeufe" / slug / ts
    lauf_dir.mkdir(parents=True)
    store = RunStore.resume(lauf_dir)
    store.save_step("kunde_pfad", {"pfad": f"kunden/{kunde_datei}"})
    store.save_step("leads", {"leads": leads, "ohne_email": 0})
    pruefung_ok = [{"email": l["email"], "betreff": "Betreff"} for l in leads]
    store.save_step("pruefung_ok", pruefung_ok)
    approve(store, name=name)
    store.save_step("versand", {"campaign_id": campaign_id})
    store.save_step("versand_komplett", {"campaign_id": campaign_id})
    return lauf_dir


@pytest.fixture
def daten_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("WEB_SECRET", "test-geheimnis-nur-fuer-tests")
    monkeypatch.setenv("WEB_COOKIE_SECURE", "0")
    nutzer = [{"name": "Lena Hartmann", "passwort_hash": PWD_CONTEXT.hash("richtig123")}]
    (tmp_path / "users.yaml").write_text(yaml.safe_dump(nutzer, allow_unicode=True), encoding="utf-8")
    (tmp_path / "kunden").mkdir()
    (tmp_path / "kunden" / "demo-gmbh.yaml").write_text(KUNDE_A_YAML, encoding="utf-8")
    return tmp_path


@pytest.fixture
def app(daten_dir):
    return create_app(daten_dir)


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def angemeldeter_client(client):
    client.post("/login", data={"name": "Lena Hartmann", "passwort": "richtig123"})
    # Copy-Rework (20.07.2026): siehe tests/web/test_dashboard.py fuer den Grund.
    client.cookies.set("intro_gesehen", "1")
    return client


# Anmeldung / Methode -----------------------------------------------------

def test_verlangt_anmeldung(client):
    antwort = client.get("/postfach", follow_redirects=False)
    assert antwort.status_code == 303
    assert antwort.headers["location"] == "/login"


def test_keine_post_route(angemeldeter_client):
    antwort = angemeldeter_client.post("/postfach")
    assert antwort.status_code == 405


# Leer-/Fehlzustaende -------------------------------------------------------

def test_ohne_kampagnen_zeigt_neutralen_leer_zustand_ohne_instantly_abfrage(angemeldeter_client):
    app = angemeldeter_client.app
    leser = FakeInstantlyLeser()
    app.state.instantly_leser = leser
    antwort = angemeldeter_client.get("/postfach")
    assert antwort.status_code == 200
    assert "Noch keine Konversation" in antwort.text
    assert leser.angefragt == []  # keine Kampagnen -> kein Abruf noetig


def test_api_nicht_erreichbar_zeigt_freundlichen_text(angemeldeter_client, daten_dir):
    _lauf(daten_dir, "demo-gmbh", "demo-gmbh.yaml", "20260720-090000",
          leads=[_lead("Anna", "Muster", "anna@firma.de", "Demo GmbH")], campaign_id="camp-1")
    app = angemeldeter_client.app
    app.state.instantly_leser = FakeInstantlyLeser(erreichbar=False)
    antwort = angemeldeter_client.get("/postfach")
    assert antwort.status_code == 200
    assert "Live-Stand gerade nicht erreichbar" in antwort.text


def test_erreichbar_aber_leer_zeigt_ehrlichen_hinweis(angemeldeter_client, daten_dir):
    _lauf(daten_dir, "demo-gmbh", "demo-gmbh.yaml", "20260720-090000",
          leads=[_lead("Anna", "Muster", "anna@firma.de", "Demo GmbH")], campaign_id="camp-1")
    app = angemeldeter_client.app
    app.state.instantly_leser = FakeInstantlyLeser(emails_by_campaign={"camp-1": []})
    antwort = angemeldeter_client.get("/postfach")
    assert antwort.status_code == 200
    assert "Antworten siehst du derzeit nur in Instantly." in antwort.text


# Konversationsliste + Detail -----------------------------------------------

def test_liste_zeigt_konversation_mit_firmen_anreicherung_und_richtung(angemeldeter_client, daten_dir):
    _lauf(daten_dir, "demo-gmbh", "demo-gmbh.yaml", "20260720-090000",
          leads=[_lead("Anna", "Muster", "anna@firma.de", "Demo GmbH")], campaign_id="camp-1")
    app = angemeldeter_client.app
    app.state.instantly_leser = FakeInstantlyLeser(emails_by_campaign={"camp-1": [
        _email(ue_type=1, to="anna@firma.de", betreff="Anschreiben",
               zeit="2026-07-20T09:00:00.000Z", text="Erstes Anschreiben"),
        _email(ue_type=2, frm="anna@firma.de", betreff="Re: Anschreiben",
               zeit="2026-07-21T10:00:00.000Z", text="Klingt gut, mehr Infos?"),
    ]})
    antwort = angemeldeter_client.get("/postfach")
    assert antwort.status_code == 200
    assert "Anna Muster" in antwort.text
    assert "Demo GmbH" in antwort.text
    assert "Re: Anschreiben" in antwort.text  # Betreff der juengsten Nachricht
    assert "Antwort erhalten" in antwort.text  # Richtungs-Indikator: letzte Nachricht empfangen


def test_detail_zeigt_chronologische_nachrichten_mit_sichtbarer_richtung(angemeldeter_client, daten_dir):
    _lauf(daten_dir, "demo-gmbh", "demo-gmbh.yaml", "20260720-090000",
          leads=[_lead("Anna", "Muster", "anna@firma.de", "Demo GmbH")], campaign_id="camp-1")
    app = angemeldeter_client.app
    app.state.instantly_leser = FakeInstantlyLeser(emails_by_campaign={"camp-1": [
        _email(ue_type=1, to="anna@firma.de", betreff="Anschreiben",
               zeit="2026-07-20T09:00:00.000Z", text="Erstes Anschreiben"),
        _email(ue_type=2, frm="anna@firma.de", betreff="Re: Anschreiben",
               zeit="2026-07-21T10:00:00.000Z", text="Klingt gut, mehr Infos?"),
    ]})
    antwort = angemeldeter_client.get("/postfach?kontakt=anna@firma.de")
    assert antwort.status_code == 200
    text = antwort.text
    # beide Nachrichten sichtbar, chronologisch (gesendet vor empfangen)...
    assert text.index("Erstes Anschreiben") < text.index("Klingt gut, mehr Infos?")
    # ... und optisch unterscheidbar (eigene CSS-Klassen je Richtung).
    assert "postfach-nachricht--gesendet" in text
    assert "postfach-nachricht--empfangen" in text
    # Antwort-Knopf zeigt zu Instantly, kein eigenes Antwortfeld im Markup.
    assert "In Instantly antworten ↗" in text
    assert "<textarea" not in text


def test_neuere_konversation_ist_zuerst_ausgewaehlt_ohne_query_parameter(angemeldeter_client, daten_dir):
    _lauf(daten_dir, "demo-gmbh", "demo-gmbh.yaml", "20260720-090000",
          leads=[_lead("Anna", "Muster", "anna@firma.de", "Demo GmbH"),
                 _lead("Bob", "Beispiel", "bob@firma.de", "Beispiel AG")],
          campaign_id="camp-1")
    app = angemeldeter_client.app
    app.state.instantly_leser = FakeInstantlyLeser(emails_by_campaign={"camp-1": [
        _email(ue_type=1, to="anna@firma.de", betreff="Anschreiben Anna",
               zeit="2026-07-18T09:00:00.000Z", text="An Anna"),
        _email(ue_type=1, to="bob@firma.de", betreff="Anschreiben Bob",
               zeit="2026-07-20T09:00:00.000Z", text="An Bob"),
    ]})
    antwort = angemeldeter_client.get("/postfach")
    assert antwort.status_code == 200
    # Bob ist die juengere Konversation (20.07. vs. 18.07.) -> Detailbereich
    # zeigt seine Nachricht, ohne dass ein Kontakt explizit gewaehlt wurde.
    assert "An Bob" in antwort.text
