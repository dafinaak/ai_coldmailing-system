"""Die Absaetze einer Mail muessen auch die Browser-Uebersetzung ueberleben.

Gefunden am 13.08.2026: Der Mailtext stand als EIN Block mit \\n im HTML
(white-space: pre-wrap). Chrome ersetzt beim Uebersetzen einen Textknoten
komplett und liefert ihn ohne die Zeilenumbrueche zurueck - die Mail wurde
zu einer einzigen Textwand, in der man nichts mehr fand. Steht jede Zeile
in einem eigenen Element, uebersetzt der Browser sie einzeln und die
Struktur bleibt.
"""
from fastapi.testclient import TestClient
from passlib.context import CryptContext
import pytest
import yaml

from web.app import create_app
from web.routen.postfach import _nachrichten_zeilen

PWD_CONTEXT = CryptContext(schemes=["bcrypt"], deprecated="auto")

MAILTEXT = "Guten Tag Frau Keqmezi,\n\nwas sagen Sie?\n\nViele Grüße\nOliver"


class FakeLeser:
    def emails_stand(self, campaign_ids):
        return {}


@pytest.fixture
def angemeldet(tmp_path, monkeypatch):
    monkeypatch.setenv("WEB_SECRET", "test-geheimnis-nur-fuer-tests")
    monkeypatch.setenv("WEB_COOKIE_SECURE", "0")
    (tmp_path / "users.yaml").write_text(yaml.safe_dump(
        [{"name": "Lena Hartmann", "passwort_hash": PWD_CONTEXT.hash("richtig123")}],
        allow_unicode=True), encoding="utf-8")
    app = create_app(tmp_path)
    app.state.instantly_leser = FakeLeser()
    monkeypatch.setattr(
        "web.routen.postfach.konversationen_aus_email_stand",
        lambda stand: [{
            "kontakt_email": "kontakt@example.com",
            "betreff": "Anfrage",
            "letzte_zeit": None,
            "richtung_letzte": "gesendet",
            "nachrichten": [{"richtung": "gesendet", "zeit": None,
                             "betreff": "Anfrage", "text": MAILTEXT,
                             "id": "1", "eaccount": "wir@example.com",
                             "campaign_id": "c1"}],
        }])
    client = TestClient(app)
    client.post("/login", data={"name": "Lena Hartmann", "passwort": "richtig123"})
    client.cookies.set("intro_gesehen", "1")
    return client


def test_jede_zeile_steht_in_einem_eigenen_element(angemeldet):
    seite = angemeldet.get("/postfach").text

    for zeile in ("Guten Tag Frau Keqmezi,", "was sagen Sie?", "Viele Grüße", "Oliver"):
        assert f'<div class="postfach-nachricht-zeile">{zeile}</div>' in seite


def test_leerzeilen_bleiben_als_eigene_elemente_erhalten(angemeldet):
    # Die leeren Zeilen SIND die Absatz-Abstaende. Wuerden sie wegfallen,
    # klebte die Mail wieder zusammen - genau der Fehler von vorher.
    seite = angemeldet.get("/postfach").text

    assert seite.count('<div class="postfach-nachricht-zeile"></div>') == 2


def test_zeilen_werden_aus_dem_text_gebaut():
    zeilen = _nachrichten_zeilen(
        [{"richtung": "gesendet", "zeit": None, "betreff": "B", "text": MAILTEXT}],
        "Wer")[0]["zeilen"]

    assert zeilen == ["Guten Tag Frau Keqmezi,", "", "was sagen Sie?", "",
                      "Viele Grüße", "Oliver"]


def test_leerer_text_ergibt_keine_kaputte_liste():
    zeilen = _nachrichten_zeilen(
        [{"richtung": "gesendet", "zeit": None, "betreff": "B", "text": ""}],
        "Wer")[0]["zeilen"]

    assert zeilen == [""]
