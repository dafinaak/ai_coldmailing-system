"""Tests fuer die Einstiegsseite "So funktioniert's" (Copy-Rework,
20.07.2026, siehe docs/copy-rework-brief.md) und den Erst-Login-Redirect
vom Dashboard dorthin. Nutzt dasselbe daten_dir/client-Fixture-Muster wie
tests/web/test_auth.py."""
from fastapi.testclient import TestClient
from passlib.context import CryptContext
import pytest
import yaml

from web.app import create_app

PWD_CONTEXT = CryptContext(schemes=["bcrypt"], deprecated="auto")


class _FakeInstantlyLeser:
    """Gleicher Fake wie tests/web/test_auth.py._FakeInstantlyLeser - noetig,
    weil das Dashboard seit Baustein 2 IMMER InstantlyLeser.postfaecher()
    aufruft (siehe web.routen.dashboard._postfach_probleme), auch wenn
    dieser Test nur die Einstiegsseite/den Redirect dorthin prueft."""

    def kampagnen_stand(self, campaign_ids):
        return {cid: {"erreichbar": False, "status": None, "name": None,
                       "versendet": None, "antworten": None, "schritte": [],
                       "stand": None} for cid in campaign_ids}

    def postfaecher(self):
        return {"postfaecher": [], "erreichbar": True, "stand": None}


@pytest.fixture
def daten_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("WEB_SECRET", "test-geheimnis-nur-fuer-tests")
    monkeypatch.setenv("WEB_COOKIE_SECURE", "0")
    nutzer = [{"name": "Lena Hartmann", "passwort_hash": PWD_CONTEXT.hash("richtig123")}]
    (tmp_path / "users.yaml").write_text(
        yaml.safe_dump(nutzer, allow_unicode=True), encoding="utf-8"
    )
    return tmp_path


@pytest.fixture
def client(daten_dir):
    app = create_app(daten_dir)
    app.state.instantly_leser = _FakeInstantlyLeser()
    return TestClient(app)


@pytest.fixture
def angemeldeter_client(client):
    client.post("/login", data={"name": "Lena Hartmann", "passwort": "richtig123"})
    return client


def test_intro_seite_verlangt_anmeldung(client):
    antwort = client.get("/so-funktionierts", follow_redirects=False)
    assert antwort.status_code == 303
    assert antwort.headers["location"] == "/login"


def test_intro_seite_zeigt_die_vier_schritte(angemeldeter_client):
    antwort = angemeldeter_client.get("/so-funktionierts")
    assert antwort.status_code == 200
    text = antwort.text
    assert "So funktioniert Poleposition" in text
    assert "Angebot anlegen" in text
    assert "E-Mail-Runde starten" in text
    assert "Lesen &amp; freigeben" in text
    assert "Verschicken" in text
    assert "Verstanden, los geht's" in text


def test_erster_dashboard_aufruf_ohne_cookie_leitet_zur_intro_um(angemeldeter_client):
    antwort = angemeldeter_client.get("/", follow_redirects=False)
    assert antwort.status_code == 303
    assert antwort.headers["location"] == "/so-funktionierts"


def test_dashboard_aufruf_mit_cookie_zeigt_dashboard(angemeldeter_client):
    angemeldeter_client.cookies.set("intro_gesehen", "1")
    antwort = angemeldeter_client.get("/", follow_redirects=False)
    assert antwort.status_code == 200
    assert "Dashboard" in antwort.text


def test_verstanden_knopf_setzt_cookie_und_leitet_zum_dashboard(angemeldeter_client):
    antwort = angemeldeter_client.post("/so-funktionierts/verstanden", follow_redirects=False)
    assert antwort.status_code == 303
    assert antwort.headers["location"] == "/"
    assert angemeldeter_client.cookies.get("intro_gesehen") == "1"

    # Danach zeigt "/" direkt das Dashboard statt erneut umzuleiten.
    danach = angemeldeter_client.get("/", follow_redirects=False)
    assert danach.status_code == 200
    assert "Dashboard" in danach.text


def test_intro_seite_jederzeit_erreichbar_auch_mit_cookie(angemeldeter_client):
    angemeldeter_client.cookies.set("intro_gesehen", "1")
    antwort = angemeldeter_client.get("/so-funktionierts")
    assert antwort.status_code == 200
    assert "So funktioniert Poleposition" in antwort.text


def test_nav_zeigt_so_funktionierts_eintrag(angemeldeter_client):
    angemeldeter_client.cookies.set("intro_gesehen", "1")
    antwort = angemeldeter_client.get("/")
    assert antwort.status_code == 200
    # Jinja escaped den Apostroph korrekt HTML-sicher (gleiches Muster wie
    # "Lesen &amp; Freigeben" in tests/web/test_auth.py).
    assert "So funktioniert&#39;s" in antwort.text
    assert 'href="/so-funktionierts"' in antwort.text
