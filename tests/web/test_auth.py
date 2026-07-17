"""Tests fuer das Web-Geruest: Anmeldung, Session-Cookie, Ausloggen,
Seitenleiste, /health ohne Login. Treibt die Routen mit dem synchronen
TestClient (httpx darunter) gegen eine App mit tmp-Datenverzeichnis -
keine echten API-Aufrufe noetig."""
from fastapi.testclient import TestClient
from passlib.context import CryptContext
import pytest
import yaml

from web.app import create_app

PWD_CONTEXT = CryptContext(schemes=["bcrypt"], deprecated="auto")

SIEBEN_BEREICHE = [
    "Dashboard",
    "Kampagnen",
    "Prüfen &amp; Freigeben",  # Jinja escaped korrekt HTML-sicher; das "&" bleibt sichtbarer Text
    "Kontakte",
    "Postfach",
    "Gesperrte Domains",
    "Kunden",
]


@pytest.fixture
def daten_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("WEB_SECRET", "test-geheimnis-nur-fuer-tests")
    nutzer = [{"name": "Lena Hartmann", "passwort_hash": PWD_CONTEXT.hash("richtig123")}]
    (tmp_path / "users.yaml").write_text(
        yaml.safe_dump(nutzer, allow_unicode=True), encoding="utf-8"
    )
    return tmp_path


@pytest.fixture
def client(daten_dir):
    app = create_app(daten_dir)
    return TestClient(app)


def test_unangemeldet_wird_zu_login_umgeleitet(client):
    antwort = client.get("/", follow_redirects=False)
    assert antwort.status_code == 303
    assert antwort.headers["location"] == "/login"


def test_falsches_passwort_zeigt_deutschen_fehlertext(client):
    antwort = client.post("/login", data={"name": "Lena Hartmann", "passwort": "falsch"})
    assert antwort.status_code == 401
    assert "Name oder Passwort stimmt nicht" in antwort.text


def test_richtiges_login_setzt_cookie_und_zeigt_name_und_nav(client):
    antwort = client.post(
        "/login",
        data={"name": "Lena Hartmann", "passwort": "richtig123"},
        follow_redirects=False,
    )
    assert antwort.status_code == 303
    assert antwort.headers["location"] == "/"
    assert len(client.cookies) > 0

    start = client.get("/")
    assert start.status_code == 200
    assert "Lena Hartmann" in start.text
    for label in SIEBEN_BEREICHE:
        assert label in start.text


def test_health_ohne_login_erreichbar(client):
    antwort = client.get("/health")
    assert antwort.status_code == 200
    assert antwort.json()["status"] == "ok"


def test_logout_loescht_session(client):
    client.post("/login", data={"name": "Lena Hartmann", "passwort": "richtig123"})
    eingeloggt = client.get("/")
    assert eingeloggt.status_code == 200

    client.post("/logout")
    danach = client.get("/", follow_redirects=False)
    assert danach.status_code == 303
    assert danach.headers["location"] == "/login"
