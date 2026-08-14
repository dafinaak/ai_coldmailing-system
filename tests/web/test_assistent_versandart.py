"""Schritt 5: Probe oder echter Versand - und alle Einstellungen landen
in der Kundendatei.

Gefunden am 14.08.2026 an einer echten Probe: Schritt 5 fragte nach
Postfach, Tageslimit, Zeitfenster, Wochentagen und Signatur - keine dieser
Antworten stand danach in der Kundendatei, also kam auch nichts bei
Instantly an. Und ohne Probe/Echt-Schalter konnte eine im Formular gebaute
Kampagne ueberhaupt nie an echte Empfaenger uebergeben werden.
"""
from pathlib import Path

from fastapi.testclient import TestClient
from passlib.context import CryptContext
import pytest
import yaml

from web.app import create_app
from web.routen.assistent import _kunde_schreiben

PWD_CONTEXT = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _entwurf(**schritt5):
    daten = {
        "name": "Probe Kampagne", "verkaeufer_url": "beispiel.de",
        "absender_email": "post@example.com",
        "usp": [{"titel": "Schnell", "erklaerung": "Sehr schnell."}],
        "icp": {}, "ort": "Hannover", "abstand_1_2": 7, "abstand_2_3": 7,
    }
    daten.update(schritt5)
    return {"kennung": "20260814-120000", "daten": daten}


def _geschriebene_datei(tmp_path, **schritt5) -> dict:
    # _kunde_schreiben liefert den Pfad RELATIV zum Datenverzeichnis.
    pfad = Path(tmp_path) / _kunde_schreiben(Path(tmp_path), _entwurf(**schritt5))
    return yaml.safe_load(pfad.read_text(encoding="utf-8"))


def test_versand_einstellungen_stehen_in_der_kundendatei(tmp_path):
    inhalt = _geschriebene_datei(
        tmp_path, versand_postfach="post@example.com", tageslimit=35,
        zeit_von="09:00", zeit_bis="17:00", wochentage=["mo", "fr"],
        signatur="Oliver Redschlag\nPolePosition Automation")

    assert inhalt["versand_postfach"] == "post@example.com"
    assert inhalt["tageslimit"] == 35
    assert inhalt["zeit_von"] == "09:00"
    assert inhalt["zeit_bis"] == "17:00"
    assert inhalt["wochentage"] == ["mo", "fr"]
    assert "PolePosition" in inhalt["signatur"]


def test_absender_ist_der_name_aus_der_signatur_nicht_die_adresse(tmp_path):
    # "absender" steht unter den Mails und geht in die Textgenerierung.
    # Eine E-Mail-Adresse als Unterschrift liest sich wie ein Fehler.
    inhalt = _geschriebene_datei(
        tmp_path, versand_postfach="post@example.com",
        signatur="Oliver Redschlag\nPolePosition Automation")

    assert inhalt["absender"] == "Oliver Redschlag"


def test_ohne_signatur_bleibt_die_adresse_als_notnagel(tmp_path):
    inhalt = _geschriebene_datei(tmp_path, versand_postfach="post@example.com")

    assert inhalt["absender"] == "post@example.com"


def test_ohne_angabe_bleibt_es_probe_versand(tmp_path):
    inhalt = _geschriebene_datei(tmp_path, versand_postfach="post@example.com")

    assert inhalt["versand_modus"] == "test"


def test_echt_wird_uebernommen(tmp_path):
    inhalt = _geschriebene_datei(
        tmp_path, versand_postfach="post@example.com", versand_modus="echt")

    assert inhalt["versand_modus"] == "echt"


def test_alles_andere_als_echt_bleibt_probe(tmp_path):
    # Ein verlorener oder verfremdeter Formularwert darf nie als
    # "an alle senden" gelesen werden.
    for wert in ("Echt", "ECHT", "ja", "1", "", None, "echter versand"):
        inhalt = _geschriebene_datei(
            tmp_path / str(wert), versand_postfach="post@example.com",
            versand_modus=wert)
        assert inhalt["versand_modus"] == "test", wert


# --- durch das Formular hindurch -----------------------------------------

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
    return client, tmp_path


def _bis_schritt_5(client):
    antwort = client.get("/assistent", follow_redirects=False)
    return antwort.headers["location"].split("/")[2]


def test_schritt_5_zeigt_beide_moeglichkeiten(angemeldet):
    client, _ = angemeldet
    kennung = _bis_schritt_5(client)

    seite = client.get(f"/assistent/{kennung}/5").text

    assert 'name="versand_modus" value="test"' in seite
    assert 'name="versand_modus" value="echt"' in seite
    # Probe ist vorausgewaehlt.
    assert seite.index('value="test"') < seite.index('value="echt"')
    vor_echt = seite[:seite.index('value="echt"')]
    assert "checked" in vor_echt


def test_formular_speichert_die_wahl(angemeldet):
    client, daten_dir = angemeldet
    kennung = _bis_schritt_5(client)

    client.post(f"/assistent/{kennung}/5",
                data={"versand_postfach": "post@example.com",
                      "versand_modus": "echt"}, follow_redirects=False)

    from pipeline import assistent_entwurf as entwuerfe
    entwurf = entwuerfe.laden(daten_dir, kennung)
    assert entwurf["daten"]["versand_modus"] == "echt"
