"""Ein angefragter Verlauf, den es nicht gibt, darf keinen fremden zeigen.

Gefunden am 13.08.2026: Der Link "Verlauf" im CRM führt nach
/postfach?kontakt=<adresse>. Hatte dieser Kontakt nie geantwortet, fiel
die Seite still auf das ERSTE Gespräch der Liste zurück - man las den
Schriftwechsel eines Fremden und hielt ihn für den eigenen. Ohne Namen
im Kopf fällt das nicht einmal auf.
"""
from fastapi.testclient import TestClient
from passlib.context import CryptContext
import pytest
import yaml

from web.app import create_app

PWD_CONTEXT = CryptContext(schemes=["bcrypt"], deprecated="auto")


class FakeLeser:
    """Liefert genau ein Gespräch - mit jemand anderem."""

    def emails_stand(self, campaign_ids):
        return {}

    def konversationen(self):
        return []


@pytest.fixture
def daten_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("WEB_SECRET", "test-geheimnis-nur-fuer-tests")
    monkeypatch.setenv("WEB_COOKIE_SECURE", "0")
    (tmp_path / "users.yaml").write_text(yaml.safe_dump(
        [{"name": "Lena Hartmann", "passwort_hash": PWD_CONTEXT.hash("richtig123")}],
        allow_unicode=True), encoding="utf-8")
    return tmp_path


@pytest.fixture
def angemeldet(daten_dir, monkeypatch):
    app = create_app(daten_dir)
    app.state.instantly_leser = FakeLeser()
    # Das Modul importiert die Funktion direkt - deshalb dort ersetzen,
    # nicht in web.instantly_leser, sonst greift der Austausch nicht.
    monkeypatch.setattr(
        "web.routen.postfach.konversationen_aus_email_stand",
        lambda stand: [{
            "kontakt_email": "fremder@example.com",
            "betreff": "Re: Anfrage",
            "letzte_zeit": None,
            "richtung_letzte": "empfangen",
            "nachrichten": [{"richtung": "empfangen", "zeit": None,
                             "betreff": "Re: Anfrage", "text": "Hallo",
                             "id": "1", "eaccount": "wir@example.com",
                             "campaign_id": "c1"}],
        }])
    client = TestClient(app)
    client.post("/login", data={"name": "Lena Hartmann", "passwort": "richtig123"})
    client.cookies.set("intro_gesehen", "1")
    return client


def test_unbekannter_kontakt_zeigt_keinen_fremden_verlauf(angemeldet):
    seite = angemeldet.get("/postfach?kontakt=niemand@beispiel.de").text

    assert "noch keinen Verlauf" in seite
    assert "niemand@beispiel.de" in seite
    # Der Schriftwechsel des Fremden darf NICHT im Detailbereich stehen.
    assert "Hallo" not in seite
    # Der Satz steht rot im Detailbereich, nicht als grauer Hinweis oben:
    # der leere weisse Kasten daneben sah aus wie eine halb geladene Seite.
    assert "postfach-nicht-gefunden" in seite
    assert "Nicht gefunden" in seite


def test_bekannter_kontakt_zeigt_seinen_verlauf(angemeldet):
    seite = angemeldet.get("/postfach?kontakt=fremder@example.com").text

    assert "Hallo" in seite
    assert "noch keinen Verlauf" not in seite


def test_ohne_kontaktangabe_bleibt_die_erste_auswahl(angemeldet):
    # Wer die Seite normal öffnet, soll wie bisher das erste Gespräch sehen.
    seite = angemeldet.get("/postfach").text

    assert "Hallo" in seite
    assert "noch keinen Verlauf" not in seite
