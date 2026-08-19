"""Schritt 3 sagt schon beim Tippen, wie viele Firmen der Bestand hergibt.

Vorher sah man erst in Schritt 4, dass der Bestand fuer diese Stadt leer
ist - und stand dann vor einer Null, ohne zu wissen warum. Der Bestand
deckt heute nur den Raum Hannover ab; fuer jede andere Stadt muss man neu
sammeln, und das soll man VORHER wissen.
"""
import json

from fastapi.testclient import TestClient
from passlib.context import CryptContext
import pytest
import yaml

from web.app import create_app

PWD_CONTEXT = CryptContext(schemes=["bcrypt"], deprecated="auto")

FIRMEN = [
    {"name": "Eins", "domain": "eins.de", "website": "https://eins.de",
     "plz": "30159", "categories": ["Webdesigner"]},
    {"name": "Zwei", "domain": "zwei.de", "website": "https://zwei.de",
     "plz": "30161", "categories": ["IT-Berater"]},
]


@pytest.fixture
def angemeldet(tmp_path, monkeypatch):
    monkeypatch.setenv("WEB_SECRET", "test-geheimnis-nur-fuer-tests")
    monkeypatch.setenv("WEB_COOKIE_SECURE", "0")
    (tmp_path / "users.yaml").write_text(yaml.safe_dump(
        [{"name": "Lena Hartmann", "passwort_hash": PWD_CONTEXT.hash("richtig123")}],
        allow_unicode=True), encoding="utf-8")
    quelle = tmp_path / "laeufe" / "leadquellen" / "probe"
    quelle.mkdir(parents=True)
    (quelle / "firmen.json").write_text(json.dumps(FIRMEN), encoding="utf-8")
    client = TestClient(create_app(tmp_path))
    client.post("/login", data={"name": "Lena Hartmann", "passwort": "richtig123"})
    client.cookies.set("intro_gesehen", "1")
    return client


def _kennung(client):
    return client.get("/assistent", follow_redirects=False
                      ).headers["location"].split("/")[2]


def _zahl(client, **fragen):
    kennung = _kennung(client)
    return client.get(f"/assistent/{kennung}/bestand-zahl", params=fragen).json()


def test_treffer_werden_gezaehlt(angemeldet):
    antwort = _zahl(angemeldet, ort="Hannover", radius_km=25,
                    dienste="Webdesigner")

    assert antwort["bekannt"] is True
    assert antwort["treffer"] == 1
    assert "1 passende" in antwort["text"]


def test_leerer_bestand_wird_deutlich_gesagt(angemeldet):
    # Der Fall, um den es geht: eine Stadt, fuer die wir nichts haben.
    antwort = _zahl(angemeldet, ort="München", radius_km=25,
                    dienste="Webdesigner")

    assert antwort["treffer"] == 0
    assert "keine einzige Firma" in antwort["text"]
    assert "leer" in antwort["text"]


def test_unbekannter_ort_ist_kein_fehler_sondern_auskunft(angemeldet):
    antwort = _zahl(angemeldet, ort="Timbuktu", radius_km=25)

    assert antwort["bekannt"] is False
    assert "Timbuktu" in antwort["text"]


def test_ohne_leistung_zaehlt_alles_im_umkreis(angemeldet):
    antwort = _zahl(angemeldet, ort="Hannover", radius_km=25)

    assert antwort["treffer"] == 2


def test_mehrere_leistungen_gehen_mit_komma(angemeldet):
    antwort = _zahl(angemeldet, ort="Hannover", radius_km=25,
                    dienste="Webdesigner,IT-Berater")

    assert antwort["treffer"] == 2


def test_die_seite_bringt_den_zaehler_mit(angemeldet):
    kennung = _kennung(angemeldet)

    seite = angemeldet.get(f"/assistent/{kennung}/3").text

    assert 'id="bestand-treffer"' in seite
    assert "bestand-zahl" in seite
