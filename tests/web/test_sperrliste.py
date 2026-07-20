"""Tests fuer die Seite "Gesperrte Domains" (globale Sperrliste): Anzeige,
Hinzufuegen/Entfernen per POST, Anmeldepflicht. Treibt die Routen mit dem
synchronen TestClient gegen eine App mit tmp-Datenverzeichnis - keine echten
API-Aufrufe noetig. Nutzt dasselbe daten_dir/client-Fixture-Muster wie
tests/web/test_auth.py."""
from fastapi.testclient import TestClient
from passlib.context import CryptContext
import pytest
import yaml

from web.app import create_app

PWD_CONTEXT = CryptContext(schemes=["bcrypt"], deprecated="auto")


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
    return TestClient(app)


@pytest.fixture
def angemeldeter_client(client):
    client.post("/login", data={"name": "Lena Hartmann", "passwort": "richtig123"})
    return client


def test_seite_verlangt_anmeldung(client):
    antwort = client.get("/domains", follow_redirects=False)
    assert antwort.status_code == 303
    assert antwort.headers["location"] == "/login"


def test_seite_zeigt_leitfaden_saetze(angemeldeter_client):
    antwort = angemeldeter_client.get("/domains")
    assert antwort.status_code == 200
    assert (
        "An Firmen mit diesen Internet-Adressen wird nie geschrieben — egal "
        "für welchen Kunden." in antwort.text
    )
    assert "Kunden-Formular" in antwort.text
    assert "Beide Listen gelten zusammen." in antwort.text


def test_seite_zeigt_leere_liste(angemeldeter_client):
    antwort = angemeldeter_client.get("/domains")
    assert antwort.status_code == 200
    assert "Noch keine gesperrten Domains" in antwort.text


def test_domain_hinzufuegen_schreibt_datei(angemeldeter_client, daten_dir):
    antwort = angemeldeter_client.post(
        "/domains/hinzufuegen", data={"domain": "  *.Bund.de  "}, follow_redirects=False
    )
    assert antwort.status_code == 303
    assert antwort.headers["location"] == "/domains"
    inhalt = yaml.safe_load((daten_dir / "sperrliste-global.yaml").read_text(encoding="utf-8"))
    assert inhalt == ["*.bund.de"]  # getrimmt und kleingeschrieben


def test_seite_zeigt_vorhandene_domains(angemeldeter_client, daten_dir):
    (daten_dir / "sperrliste-global.yaml").write_text(
        yaml.safe_dump(["konkurrent-ki.de"]), encoding="utf-8"
    )
    antwort = angemeldeter_client.get("/domains")
    assert "konkurrent-ki.de" in antwort.text


def test_domain_hinzufuegen_leer_gibt_deutschen_fehler(angemeldeter_client, daten_dir):
    antwort = angemeldeter_client.post("/domains/hinzufuegen", data={"domain": "   "})
    assert antwort.status_code == 400
    assert "Bitte eine Domain eintragen." in antwort.text
    assert not (daten_dir / "sperrliste-global.yaml").exists()


def test_domain_hinzufuegen_doppelt_gibt_deutschen_fehler_und_aendert_datei_nicht(
    angemeldeter_client, daten_dir
):
    (daten_dir / "sperrliste-global.yaml").write_text(
        yaml.safe_dump(["konkurrent-ki.de"]), encoding="utf-8"
    )
    antwort = angemeldeter_client.post(
        "/domains/hinzufuegen", data={"domain": "Konkurrent-KI.de"}
    )
    assert antwort.status_code == 400
    assert "steht schon auf der Liste" in antwort.text
    inhalt = yaml.safe_load((daten_dir / "sperrliste-global.yaml").read_text(encoding="utf-8"))
    assert inhalt == ["konkurrent-ki.de"]


def test_speichern_hinterlaesst_keine_temporaeren_dateien(angemeldeter_client, daten_dir):
    # E-Fix 1: sperrliste-global.yaml wird atomar geschrieben (temp-Datei +
    # os.replace, gleiches Muster wie web.routen.kunden._validieren_und_
    # speichern) - nach dem Schreiben darf keine liegen gebliebene temporaere
    # Datei im Datenverzeichnis zurueckbleiben (z.B. bei einem Absturz
    # mitten im write_text waere die Zieldatei vorher kurzzeitig
    # kaputt/leer gewesen).
    angemeldeter_client.post("/domains/hinzufuegen", data={"domain": "konkurrent.de"})
    reste = [p for p in daten_dir.iterdir() if p.name.startswith(".sperrliste-global")]
    assert reste == []


def test_domain_entfernen_aendert_datei(angemeldeter_client, daten_dir):
    (daten_dir / "sperrliste-global.yaml").write_text(
        yaml.safe_dump(["konkurrent-ki.de", "*.bund.de"]), encoding="utf-8"
    )
    antwort = angemeldeter_client.post(
        "/domains/entfernen", data={"domain": "konkurrent-ki.de"}, follow_redirects=False
    )
    assert antwort.status_code == 303
    inhalt = yaml.safe_load((daten_dir / "sperrliste-global.yaml").read_text(encoding="utf-8"))
    assert inhalt == ["*.bund.de"]
