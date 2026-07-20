"""Tests fuer den Postfaecher-Bereich (Baustein 2): rein lesende Uebersicht
des Verbindungs-/Anwaerm-Status aller Instantly-Sende-Postfaecher.
Instantly ist ueber app.state.instantly_leser gefaked - exakt das Muster
aus tests/web/test_postfach.py/test_kampagnen.py (dort FakeInstantlyLeser.
emails_stand/kampagnen_stand, hier FakeInstantlyLeser.postfaecher)."""
from __future__ import annotations

from datetime import datetime

import pytest
import yaml
from fastapi.testclient import TestClient
from passlib.context import CryptContext

from web.app import create_app

PWD_CONTEXT = CryptContext(schemes=["bcrypt"], deprecated="auto")


class FakeInstantlyLeser:
    """Ersetzt web.instantly_leser.InstantlyLeser.postfaecher - liefert ein
    vorbereitetes Ergebnis statt echter HTTP-Aufrufe (gleiche Form wie
    InstantlyLeser.postfaecher(), siehe dort)."""

    def __init__(self, postfaecher: list[dict] | None = None, erreichbar: bool = True,
                 stand: datetime | None = None):
        self._postfaecher = postfaecher or []
        self.erreichbar = erreichbar
        self.stand = stand if stand is not None else datetime(2026, 7, 20, 9, 30)
        self.aufrufe = 0

    def postfaecher(self):
        self.aufrufe += 1
        return {
            "postfaecher": self._postfaecher,
            "erreichbar": self.erreichbar,
            "stand": self.stand if (self.erreichbar or self._postfaecher) else None,
        }


def _postfach(email="team@firma.de", status="verbunden", warmup="an", daily_limit=100):
    return {"email": email, "status": status, "warmup": warmup, "daily_limit": daily_limit}


@pytest.fixture
def daten_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("WEB_SECRET", "test-geheimnis-nur-fuer-tests")
    monkeypatch.setenv("WEB_COOKIE_SECURE", "0")
    nutzer = [{"name": "Lena Hartmann", "passwort_hash": PWD_CONTEXT.hash("richtig123")}]
    (tmp_path / "users.yaml").write_text(yaml.safe_dump(nutzer, allow_unicode=True), encoding="utf-8")
    (tmp_path / "kunden").mkdir()
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
    client.cookies.set("intro_gesehen", "1")
    return client


# Anmeldung / Methode -------------------------------------------------------

def test_verlangt_anmeldung(client):
    antwort = client.get("/postfaecher", follow_redirects=False)
    assert antwort.status_code == 303
    assert antwort.headers["location"] == "/login"


def test_keine_post_route(angemeldeter_client):
    antwort = angemeldeter_client.post("/postfaecher")
    assert antwort.status_code == 405


# Liste / Status-Anzeige ------------------------------------------------------

def test_gesundes_postfach_zeigt_verbunden_chip(angemeldeter_client):
    app = angemeldeter_client.app
    app.state.instantly_leser = FakeInstantlyLeser([
        _postfach(email="gesund@firma.de", status="verbunden", warmup="an", daily_limit=100),
    ])
    antwort = angemeldeter_client.get("/postfaecher")
    assert antwort.status_code == 200
    text = antwort.text
    assert "gesund@firma.de" in text
    assert "VERBUNDEN" in text
    assert "Aufwärmen läuft" in text
    assert ">100<" in text


def test_kaputtes_postfach_zeigt_lauten_verbindungsfehler_chip(angemeldeter_client):
    app = angemeldeter_client.app
    app.state.instantly_leser = FakeInstantlyLeser([
        _postfach(email="kaputt@firma.de", status="verbindungsfehler", warmup="aus", daily_limit=None),
    ])
    antwort = angemeldeter_client.get("/postfaecher")
    assert antwort.status_code == 200
    text = antwort.text
    assert "kaputt@firma.de" in text
    assert "VERBINDUNGSFEHLER" in text
    assert "Aufwärmen aus" in text


def test_fehlendes_tageslimit_zeigt_strich_statt_erfundenem_wert(angemeldeter_client):
    app = angemeldeter_client.app
    app.state.instantly_leser = FakeInstantlyLeser([
        _postfach(email="ohne-limit@firma.de", daily_limit=None),
    ])
    antwort = angemeldeter_client.get("/postfaecher")
    assert antwort.status_code == 200
    assert ">–<" in antwort.text


def test_stand_zeitpunkt_wird_angezeigt(angemeldeter_client):
    app = angemeldeter_client.app
    app.state.instantly_leser = FakeInstantlyLeser(
        [_postfach()], stand=datetime(2026, 7, 20, 8, 45))
    antwort = angemeldeter_client.get("/postfaecher")
    assert antwort.status_code == 200
    assert "Stand 08:45" in antwort.text


def test_ohne_postfaecher_zeigt_leeren_zustand(angemeldeter_client):
    app = angemeldeter_client.app
    app.state.instantly_leser = FakeInstantlyLeser([])
    antwort = angemeldeter_client.get("/postfaecher")
    assert antwort.status_code == 200
    assert "Noch kein Postfach" in antwort.text


# Laute Warnbox bei Verbindungsproblem ---------------------------------------

def test_warnbox_erscheint_bei_verbindungsfehler(angemeldeter_client):
    app = angemeldeter_client.app
    app.state.instantly_leser = FakeInstantlyLeser([
        _postfach(email="gesund@firma.de", status="verbunden"),
        _postfach(email="kaputt@firma.de", status="verbindungsfehler"),
    ])
    antwort = angemeldeter_client.get("/postfaecher")
    assert antwort.status_code == 200
    text = antwort.text
    assert "Verbindungsproblem bei einem Postfach" in text
    assert "Ein Postfach hat gerade ein Problem — bitte in Instantly neu verbinden." in text
    assert "In Instantly öffnen ↗" in text


def test_warnbox_fehlt_wenn_alle_postfaecher_gesund_sind(angemeldeter_client):
    app = angemeldeter_client.app
    app.state.instantly_leser = FakeInstantlyLeser([
        _postfach(email="gesund@firma.de", status="verbunden"),
        _postfach(email="pausiert@firma.de", status="pausiert"),
    ])
    antwort = angemeldeter_client.get("/postfaecher")
    assert antwort.status_code == 200
    assert "Verbindungsproblem bei einem Postfach" not in antwort.text


# API-Ausfall ----------------------------------------------------------------

def test_api_nicht_erreichbar_zeigt_freundlichen_text_statt_absturz(angemeldeter_client):
    app = angemeldeter_client.app
    app.state.instantly_leser = FakeInstantlyLeser([], erreichbar=False)
    antwort = angemeldeter_client.get("/postfaecher")
    assert antwort.status_code == 200
    assert "Live-Stand gerade nicht erreichbar" in antwort.text


def test_api_ausfall_mit_cache_zeigt_letzten_bekannten_stand(angemeldeter_client):
    app = angemeldeter_client.app
    app.state.instantly_leser = FakeInstantlyLeser(
        [_postfach(email="gesund@firma.de")], erreichbar=False,
        stand=datetime(2026, 7, 20, 8, 0))
    antwort = angemeldeter_client.get("/postfaecher")
    assert antwort.status_code == 200
    text = antwort.text
    assert "gesund@firma.de" in text
    assert "Live-Stand gerade nicht erreichbar" in text


def test_ohne_instantly_key_zeigt_seite_statt_absturz(angemeldeter_client, monkeypatch):
    # Regression (Review-Fund, siehe web.routen.postfaecher.postfaecher_stand):
    # ohne INSTANTLY_API_KEY UND ohne app.state.instantly_leser (kein Fake
    # injiziert - simuliert einen App-Start ganz ohne Schluessel) wirft
    # web.instantly_leser.geteilten_leser() beim Bauen des Lesers ein
    # KeyError, VOR jeder eigenen Fehlertoleranz von InstantlyLeser.
    # postfaecher(). Die Seite muss trotzdem den ehrlichen "Live-Stand
    # gerade nicht erreichbar"-Zustand zeigen statt mit 500 abzustuerzen.
    monkeypatch.delenv("INSTANTLY_API_KEY", raising=False)
    app = angemeldeter_client.app
    app.state.instantly_leser = None
    antwort = angemeldeter_client.get("/postfaecher")
    assert antwort.status_code == 200
    assert "Live-Stand gerade nicht erreichbar" in antwort.text


# Read-only Hinweis -----------------------------------------------------------

def test_zeigt_ehrlichen_hinweis_dass_verbinden_nur_in_instantly_geht(angemeldeter_client):
    app = angemeldeter_client.app
    app.state.instantly_leser = FakeInstantlyLeser([_postfach()])
    antwort = angemeldeter_client.get("/postfaecher")
    assert antwort.status_code == 200
    assert "Ein Postfach neu verbinden oder reparieren geht nur in Instantly" in antwort.text


# Nav ------------------------------------------------------------------------

def test_nav_zeigt_postfaecher_eintrag(angemeldeter_client):
    app = angemeldeter_client.app
    app.state.instantly_leser = FakeInstantlyLeser([_postfach()])
    antwort = angemeldeter_client.get("/postfaecher")
    assert antwort.status_code == 200
    assert 'href="/postfaecher"' in antwort.text
    assert "Postfächer" in antwort.text
