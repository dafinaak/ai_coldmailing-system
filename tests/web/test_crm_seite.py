"""Tests fuer den CRM-Bereich (Bauplan CRM-Verkaufsstufen, Schritt 3):
Route /crm (Stufen-Leiste, Kampagnen-Braetter, Suche, Stufenwechsel,
Einzel-Anlage). Fixtures nach dem Muster von tests/web/test_kontakte.py."""
from __future__ import annotations

import pytest
import yaml
from fastapi.testclient import TestClient
from passlib.context import CryptContext

from web.app import create_app
from web.crm_speicher import KontakteSpeicher

PWD_CONTEXT = CryptContext(schemes=["bcrypt"], deprecated="auto")


@pytest.fixture
def daten_dir(tmp_path):
    return tmp_path


@pytest.fixture
def app(daten_dir, monkeypatch):
    monkeypatch.setenv("WEB_SECRET", "test-geheimnis-nur-fuer-tests")
    monkeypatch.setenv("WEB_COOKIE_SECURE", "0")
    nutzer = [{"name": "Lena Hartmann",
               "passwort_hash": PWD_CONTEXT.hash("richtig123")}]
    (daten_dir / "users.yaml").write_text(
        yaml.safe_dump(nutzer, allow_unicode=True), encoding="utf-8")
    return create_app(daten_dir)


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def angemeldeter_client(client):
    client.post("/login", data={"name": "Lena Hartmann",
                                "passwort": "richtig123"})
    client.cookies.set("intro_gesehen", "1")
    return client


def _befuellen(daten_dir):
    s = KontakteSpeicher(daten_dir / "kontakte.db",
                         uhr=lambda: "2026-07-30T09:00:00")
    s.kontakt_anlegen("m.ehlers@itanix.de", name="Malte Ehlers",
                      firma="ITANIX GmbH", kampagne="Partnerschaft IT")
    s.kontakt_anlegen("s.braun@marc-cain.com", name="Solveig Braun",
                      firma="Marc Cain", kampagne="SEO")
    s.stufe_setzen("s.braun@marc-cain.com", "gewonnen")
    return s


def test_crm_verlangt_anmeldung(client):
    antwort = client.get("/crm", follow_redirects=False)
    assert antwort.status_code in (302, 303)
    assert antwort.headers["location"] == "/login"


def test_crm_zeigt_stufenleiste_kampagnen_und_kontakte(daten_dir,
                                                       angemeldeter_client):
    _befuellen(daten_dir)
    antwort = angemeldeter_client.get("/crm")
    assert antwort.status_code == 200
    text = antwort.text
    for erwartet in ("Neuer Lead", "Demo-Termin", "Nachfassen", "Angebot",
                     "Gewonnen", "Verloren", "Alle Kampagnen",
                     "Partnerschaft IT", "SEO", "Malte Ehlers",
                     "Solveig Braun"):
        assert erwartet in text


def test_kampagnen_brett_filtert_und_zaehlt_nur_seine_kontakte(
        daten_dir, angemeldeter_client):
    _befuellen(daten_dir)
    antwort = angemeldeter_client.get("/crm", params={"kampagne": "SEO"})
    assert "Solveig Braun" in antwort.text
    assert "Malte Ehlers" not in antwort.text


def test_stufen_filter_und_suche(daten_dir, angemeldeter_client):
    _befuellen(daten_dir)
    nur_gewonnen = angemeldeter_client.get("/crm", params={"stufe": "gewonnen"})
    assert "Solveig Braun" in nur_gewonnen.text
    assert "Malte Ehlers" not in nur_gewonnen.text
    suche = angemeldeter_client.get("/crm", params={"q": "itanix"})
    assert "Malte Ehlers" in suche.text and "Solveig Braun" not in suche.text
    assert angemeldeter_client.get("/crm",
                                   params={"stufe": "quatsch"}).status_code == 400


def test_stufe_wechseln_per_post(daten_dir, angemeldeter_client):
    s = _befuellen(daten_dir)
    antwort = angemeldeter_client.post(
        "/crm/stufe", data={"email": "m.ehlers@itanix.de",
                            "stufe": "angebot", "zurueck": "/crm"},
        follow_redirects=False)
    assert antwort.status_code == 303
    assert s.kontakte(stufe="angebot")[0]["email"] == "m.ehlers@itanix.de"
    kaputt = angemeldeter_client.post(
        "/crm/stufe", data={"email": "m.ehlers@itanix.de",
                            "stufe": "raketenstart"})
    assert kaputt.status_code == 400


def test_kontakt_von_hand_anlegen(daten_dir, angemeldeter_client):
    _befuellen(daten_dir)
    antwort = angemeldeter_client.post(
        "/crm/anlegen", data={"email": "Neu@Firma.DE", "name": "Nora Neu",
                              "firma": "Neu GmbH", "kampagne": ""},
        follow_redirects=False)
    assert antwort.status_code == 303
    s = KontakteSpeicher(daten_dir / "kontakte.db")
    assert any(k["email"] == "neu@firma.de" for k in s.kontakte())
    ohne_mail = angemeldeter_client.post("/crm/anlegen", data={"email": "x"})
    assert ohne_mail.status_code == 400
