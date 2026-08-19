"""Die Zahl in Schritt 1 begrenzt FIRMEN, nicht Kontakte.

Am 18.08.2026 wurden aus 10 eingetragenen "Kontakten" 7 Kontakte: die Zahl
bestimmt, wie viele FIRMEN in die Suche gehen. Kontakte entstehen erst
danach, und nicht jede Firma gibt einen her. Das Feld hiess trotzdem
"Anzahl Kontakte" - wer 10 Kontakte wollte, bekam weniger und wusste
nicht warum.
"""
from fastapi.testclient import TestClient
from passlib.context import CryptContext
import pytest
import yaml

from web.app import create_app

PWD_CONTEXT = CryptContext(schemes=["bcrypt"], deprecated="auto")


@pytest.fixture
def angemeldet(tmp_path, monkeypatch):
    monkeypatch.setenv("WEB_SECRET", "test-geheimnis-nur-fuer-tests")
    monkeypatch.setenv("WEB_COOKIE_SECURE", "0")
    (tmp_path / "users.yaml").write_text(yaml.safe_dump(
        [{"name": "Lena Hartmann", "passwort_hash": PWD_CONTEXT.hash("richtig123")}],
        allow_unicode=True), encoding="utf-8")
    client = TestClient(create_app(tmp_path))
    client.post("/login", data={"name": "Lena Hartmann", "passwort": "richtig123"})
    client.cookies.set("intro_gesehen", "1")
    return client


def _kennung(client):
    return client.get("/assistent", follow_redirects=False
                      ).headers["location"].split("/")[2]


def test_feld_heisst_firmen_nicht_kontakte(angemeldet):
    seite = angemeldet.get(f"/assistent/{_kennung(angemeldet)}/1").text

    assert "Anzahl Firmen" in seite
    assert "Anzahl Kontakte" not in seite


def test_der_hinweis_nennt_das_verhaeltnis(angemeldet):
    # Sieben von zehn - gemessen, nicht geschaetzt.
    seite = angemeldet.get(f"/assistent/{_kennung(angemeldet)}/1").text

    assert "sieben von zehn" in seite


def test_das_feld_selbst_heisst_weiter_anzahl_leads(angemeldet):
    # Nur die Beschriftung aendert sich, nicht der gespeicherte Name -
    # sonst verlieren bestehende Entwuerfe ihren Wert.
    seite = angemeldet.get(f"/assistent/{_kennung(angemeldet)}/1").text

    assert 'name="anzahl_leads"' in seite
