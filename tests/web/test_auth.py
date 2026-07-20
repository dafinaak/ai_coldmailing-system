"""Tests fuer das Web-Geruest: Anmeldung, Session-Cookie, Ausloggen,
Seitenleiste, /health ohne Login. Treibt die Routen mit dem synchronen
TestClient (httpx darunter) gegen eine App mit tmp-Datenverzeichnis -
keine echten API-Aufrufe noetig."""
from fastapi.testclient import TestClient
from passlib.context import CryptContext
import pytest
import yaml

from web.app import create_app
from web.auth import lade_nutzer

PWD_CONTEXT = CryptContext(schemes=["bcrypt"], deprecated="auto")

SIEBEN_BEREICHE = [
    "Dashboard",
    "Kampagnen",
    "Lesen &amp; Freigeben",  # Jinja escaped korrekt HTML-sicher; das "&" bleibt sichtbarer Text
    "Kontakte",
    "Postfach",
    "Gesperrte Domains",
    "Angebote",
]


@pytest.fixture
def daten_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("WEB_SECRET", "test-geheimnis-nur-fuer-tests")
    # TestClient spricht ueber http://testserver (kein TLS). Ein Secure-Cookie
    # wuerde vom httpx-Cookie-Jar bei folgenden Requests nicht mehr
    # zurueckgeschickt - fuer die meisten Tests hier daher bewusst aus.
    # Der eigene Test fuer das Secure-Flag setzt/entfernt die Variable selbst.
    monkeypatch.setenv("WEB_COOKIE_SECURE", "0")
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


def test_login_seite_zeigt_leitfaden_satz(client):
    antwort = client.get("/login")
    assert antwort.status_code == 200
    assert "Melde dich an, um weiterzumachen." in antwort.text


def test_secure_cookie_per_default_gesetzt(daten_dir, monkeypatch):
    # Ohne WEB_COOKIE_SECURE gesetzt (Default) muss der Cookie das
    # Secure-Attribut tragen - Produktion laeuft ueber HTTPS, und ohne
    # Secure koennte der Cookie ueber eine Klartext-Verbindung mitgelesen
    # werden. Wir pruefen den rohen Set-Cookie-Header direkt (nicht ueber
    # den Cookie-Jar), weil der Jar einen Secure-Cookie ueber die
    # http://testserver-Verbindung des TestClient gar nicht erst behaelt.
    monkeypatch.delenv("WEB_COOKIE_SECURE", raising=False)
    app = create_app(daten_dir)
    client_ohne_flag = TestClient(app)
    antwort = client_ohne_flag.post(
        "/login",
        data={"name": "Lena Hartmann", "passwort": "richtig123"},
        follow_redirects=False,
    )
    set_cookie = antwort.headers.get("set-cookie", "")
    assert "Secure" in set_cookie


def test_secure_cookie_abschaltbar_per_flag(daten_dir, monkeypatch):
    monkeypatch.setenv("WEB_COOKIE_SECURE", "0")
    app = create_app(daten_dir)
    client_ohne_secure = TestClient(app)
    antwort = client_ohne_secure.post(
        "/login",
        data={"name": "Lena Hartmann", "passwort": "richtig123"},
        follow_redirects=False,
    )
    set_cookie = antwort.headers.get("set-cookie", "")
    assert "Secure" not in set_cookie


def test_richtiges_login_setzt_cookie_und_zeigt_name_und_nav(client):
    antwort = client.post(
        "/login",
        data={"name": "Lena Hartmann", "passwort": "richtig123"},
        follow_redirects=False,
    )
    assert antwort.status_code == 303
    assert antwort.headers["location"] == "/"
    assert len(client.cookies) > 0

    # Copy-Rework (20.07.2026): erster Aufruf von "/" ohne das Cookie
    # 'intro_gesehen' leitet einmalig zur Einstiegsseite "So funktioniert's"
    # um (siehe web.routen.dashboard/web.routen.intro) - eigener Test unten
    # (test_erster_dashboard_aufruf_ohne_intro_cookie_leitet_um) prueft genau
    # das; hier simulieren wir einen wiederkehrenden Nutzer, um Name/Nav zu
    # pruefen.
    client.cookies.set("intro_gesehen", "1")
    start = client.get("/")
    assert start.status_code == 200
    assert "Lena Hartmann" in start.text
    for label in SIEBEN_BEREICHE:
        assert label in start.text


def test_erster_dashboard_aufruf_ohne_intro_cookie_leitet_um(client):
    client.post("/login", data={"name": "Lena Hartmann", "passwort": "richtig123"})
    antwort = client.get("/", follow_redirects=False)
    assert antwort.status_code == 303
    assert antwort.headers["location"] == "/so-funktionierts"


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


def test_kaputte_users_yaml_gibt_klaren_fehler(tmp_path):
    (tmp_path / "users.yaml").write_text(
        yaml.safe_dump({"nicht": "eine-liste"}, allow_unicode=True), encoding="utf-8"
    )
    with pytest.raises(RuntimeError, match="users.yaml"):
        lade_nutzer(tmp_path)


def test_users_yaml_mit_fehlenden_feldern_gibt_klaren_fehler(tmp_path):
    (tmp_path / "users.yaml").write_text(
        yaml.safe_dump([{"name": "Lena Hartmann"}], allow_unicode=True), encoding="utf-8"
    )
    with pytest.raises(RuntimeError, match="users.yaml"):
        lade_nutzer(tmp_path)
