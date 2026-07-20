"""Tests fuer den Kunden-Bereich: Liste, Anlegen/Bearbeiten-Formular,
Speichern (validiert ueber pipeline.config.load_kunde) und die
Angebots-Ableitung von der Firmen-Webseite (KI gefaked, kein echter
API-Aufruf). Nutzt dasselbe daten_dir/client-Fixture-Muster wie
tests/web/test_sperrliste.py."""
import json

from fastapi.testclient import TestClient
from passlib.context import CryptContext
import pytest
import yaml

from tests.test_personalize import FakeKI
from web.app import create_app

PWD_CONTEXT = CryptContext(schemes=["bcrypt"], deprecated="auto")

GUELTIGE_FORMULARDATEN = {
    "name": "Neue Firma GmbH",
    "webseite": "https://neuefirma.de",
    "zielgruppe_titel": "CEO, Head of Sales",
    "zielgruppe_region": "Germany",
    "zielgruppe_firmengroesse": "11-50",
    "angebot": "KI-Automatisierung fuer Vertriebsprozesse",
    "tonalitaet": "ruhig, erklaerend, keine Superlative",
    "absender": "Leonard von Digital Diamonds",
    "follow_up_tag_1": "3",
    "follow_up_tag_2": "7",
    "test_empfaenger": "test1@example.com\ntest2@example.com",
    "sperrliste": "konkurrent.de\n*.bund.de",
}


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
def app(daten_dir):
    return create_app(daten_dir)


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def angemeldeter_client(client):
    client.post("/login", data={"name": "Lena Hartmann", "passwort": "richtig123"})
    # Copy-Rework (20.07.2026): siehe tests/web/test_dashboard.py fuer den Grund.
    client.cookies.set("intro_gesehen", "1")
    return client


def _kunde_datei(daten_dir, dateiname):
    return daten_dir / "kunden" / f"{dateiname}.yaml"


# Anmeldung -----------------------------------------------------------------

def test_liste_verlangt_anmeldung(client):
    antwort = client.get("/kunden", follow_redirects=False)
    assert antwort.status_code == 303
    assert antwort.headers["location"] == "/login"


# Liste -----------------------------------------------------------------

def test_liste_zeigt_leeren_zustand(angemeldeter_client):
    antwort = angemeldeter_client.get("/kunden")
    assert antwort.status_code == 200
    assert "Noch keine Angebote angelegt." in antwort.text
    assert "Angebot anlegen" in antwort.text


def test_liste_zeigt_vorhandenen_kunden(angemeldeter_client, daten_dir):
    (daten_dir / "kunden").mkdir()
    _kunde_datei(daten_dir, "demo-gmbh").write_text(
        yaml.safe_dump({
            "name": "Demo GmbH",
            "zielgruppe": {"titel": ["CEO"], "region": ["Germany"], "firmengroesse": ["11-50"]},
            "angebot": "Automatisierung",
            "tonalitaet": "ruhig",
            "absender": "Leonard",
            "follow_up_tage": [3, 7],
            "test_empfaenger": ["test@example.com"],
        }, allow_unicode=True),
        encoding="utf-8",
    )
    antwort = angemeldeter_client.get("/kunden")
    assert antwort.status_code == 200
    assert "Demo GmbH" in antwort.text
    assert "/kunden/demo-gmbh/bearbeiten" in antwort.text


# Anlegen -----------------------------------------------------------------

def test_kunde_anlegen_schreibt_ladbare_datei(angemeldeter_client, daten_dir):
    antwort = angemeldeter_client.post(
        "/kunden/neu", data=GUELTIGE_FORMULARDATEN, follow_redirects=False
    )
    assert antwort.status_code == 303
    assert antwort.headers["location"] == "/kunden"

    pfad = _kunde_datei(daten_dir, "neue-firma-gmbh")
    assert pfad.exists()

    from pipeline.config import load_kunde

    kunde = load_kunde(pfad)
    assert kunde.name == "Neue Firma GmbH"
    assert kunde.webseite == "https://neuefirma.de"
    assert kunde.zielgruppe == {
        "titel": ["CEO", "Head of Sales"],
        "region": ["Germany"],
        "firmengroesse": ["11-50"],
    }
    assert kunde.angebot == "KI-Automatisierung fuer Vertriebsprozesse"
    assert kunde.tonalitaet == "ruhig, erklaerend, keine Superlative"
    assert kunde.absender == "Leonard von Digital Diamonds"
    assert kunde.follow_up_tage == [3, 7]
    assert kunde.test_empfaenger == ["test1@example.com", "test2@example.com"]
    assert kunde.sperrliste == ["konkurrent.de", "*.bund.de"]


def test_kunde_anlegen_ohne_pflichtfeld_zeigt_deutschen_fehler_und_behaelt_eingaben(
    angemeldeter_client, daten_dir
):
    daten = dict(GUELTIGE_FORMULARDATEN)
    daten["angebot"] = ""
    antwort = angemeldeter_client.post("/kunden/neu", data=daten)
    assert antwort.status_code == 400
    assert "angebot" in antwort.text
    assert "Neue Firma GmbH" in antwort.text  # eingetippter Name bleibt im Formular
    assert not _kunde_datei(daten_dir, "neue-firma-gmbh").exists()


# Bearbeiten -----------------------------------------------------------------

def test_bearbeiten_formular_zeigt_vorhandene_werte(angemeldeter_client, daten_dir):
    (daten_dir / "kunden").mkdir()
    _kunde_datei(daten_dir, "demo-gmbh").write_text(
        yaml.safe_dump({
            "name": "Demo GmbH",
            "webseite": "https://demo.de",
            "zielgruppe": {"titel": ["CEO"], "region": ["Germany"], "firmengroesse": ["11-50"]},
            "angebot": "Bestehendes Angebot",
            "tonalitaet": "ruhig",
            "absender": "Leonard",
            "follow_up_tage": [3, 7],
            "test_empfaenger": ["test@example.com"],
            "sperrliste": ["alt.de"],
        }, allow_unicode=True),
        encoding="utf-8",
    )
    antwort = angemeldeter_client.get("/kunden/demo-gmbh/bearbeiten")
    assert antwort.status_code == 200
    assert 'value="Demo GmbH"' in antwort.text
    assert 'value="https://demo.de"' in antwort.text
    assert "Bestehendes Angebot" in antwort.text
    assert "alt.de" in antwort.text
    assert 'value="3"' in antwort.text and 'value="7"' in antwort.text


def test_bearbeiten_formular_bei_kaputter_datei_zeigt_freundlichen_fehler_statt_absturz(
    angemeldeter_client, daten_dir
):
    # E-Fix 2a: GET .../bearbeiten auf einer kaputten Kunden-Datei (z.B.
    # Pflichtfelder fehlen, load_kunde wirft ValueError) darf nicht mit
    # einem 500er abstuerzen - gleiches Prinzip wie web.routen.freigabe.
    # _lese_kontext (siehe test_freigabe.py, "kaputte Kunden-Datei").
    (daten_dir / "kunden").mkdir()
    _kunde_datei(daten_dir, "demo-gmbh").write_text("name: Demo GmbH\n", encoding="utf-8")
    antwort = angemeldeter_client.get("/kunden/demo-gmbh/bearbeiten")
    assert antwort.status_code == 200
    assert "nicht lesbar" in antwort.text or "beschädigt" in antwort.text


def test_bearbeiten_speichern_fuer_nicht_vorhandenen_kunden_gibt_404(
    angemeldeter_client, daten_dir
):
    # E-Fix 2b: POST .../bearbeiten auf einen Dateinamen, der noch gar
    # nicht existiert, darf nicht still einen neuen Kunden anlegen (das
    # waere ein Umgehen von /kunden/neu ueber eine erratene URL) - sondern
    # muss 404 geben, wie das GET-Pendant es schon tut.
    daten = dict(GUELTIGE_FORMULARDATEN)
    antwort = angemeldeter_client.post("/kunden/gibts-nicht/bearbeiten", data=daten)
    assert antwort.status_code == 404
    assert not _kunde_datei(daten_dir, "gibts-nicht").exists()


def test_bearbeiten_speichert_aenderungen_unter_gleichem_dateinamen(
    angemeldeter_client, daten_dir
):
    (daten_dir / "kunden").mkdir()
    _kunde_datei(daten_dir, "demo-gmbh").write_text(
        yaml.safe_dump({
            "name": "Demo GmbH",
            "zielgruppe": {"titel": ["CEO"], "region": ["Germany"], "firmengroesse": ["11-50"]},
            "angebot": "Altes Angebot",
            "tonalitaet": "ruhig",
            "absender": "Leonard",
            "follow_up_tage": [3, 7],
            "test_empfaenger": ["test@example.com"],
        }, allow_unicode=True),
        encoding="utf-8",
    )
    daten = dict(GUELTIGE_FORMULARDATEN)
    daten["name"] = "Demo GmbH"  # Name aendert sich, Dateiname bleibt gleich
    daten["angebot"] = "Neues Angebot nach Bearbeitung"
    antwort = angemeldeter_client.post(
        "/kunden/demo-gmbh/bearbeiten", data=daten, follow_redirects=False
    )
    assert antwort.status_code == 303

    from pipeline.config import load_kunde

    pfad = _kunde_datei(daten_dir, "demo-gmbh")
    assert pfad.exists()
    kunde = load_kunde(pfad)
    assert kunde.angebot == "Neues Angebot nach Bearbeitung"


def test_bearbeiten_behaelt_fremde_yaml_felder_die_das_formular_nicht_kennt(
    angemeldeter_client, daten_dir
):
    (daten_dir / "kunden").mkdir()
    _kunde_datei(daten_dir, "demo-gmbh").write_text(
        yaml.safe_dump({
            "name": "Demo GmbH",
            "zielgruppe": {"titel": ["CEO"], "region": ["Germany"], "firmengroesse": ["11-50"]},
            "angebot": "Altes Angebot",
            "tonalitaet": "ruhig",
            "absender": "Leonard",
            "follow_up_tage": [3, 7],
            "test_empfaenger": ["test@example.com"],
            "notizen_intern": "Nur fuers Team - nicht im Formular abgebildet",
        }, allow_unicode=True),
        encoding="utf-8",
    )
    daten = dict(GUELTIGE_FORMULARDATEN)
    daten["name"] = "Demo GmbH"
    antwort = angemeldeter_client.post(
        "/kunden/demo-gmbh/bearbeiten", data=daten, follow_redirects=False
    )
    assert antwort.status_code == 303

    pfad = _kunde_datei(daten_dir, "demo-gmbh")
    gespeichert = yaml.safe_load(pfad.read_text(encoding="utf-8"))
    assert gespeichert["notizen_intern"] == "Nur fuers Team - nicht im Formular abgebildet"
    assert gespeichert["angebot"] == GUELTIGE_FORMULARDATEN["angebot"]


def test_bearbeiten_mit_geleertem_pflichtfeld_loest_pruefung_aus(
    angemeldeter_client, daten_dir
):
    (daten_dir / "kunden").mkdir()
    _kunde_datei(daten_dir, "demo-gmbh").write_text(
        yaml.safe_dump({
            "name": "Demo GmbH",
            "zielgruppe": {"titel": ["CEO"], "region": ["Germany"], "firmengroesse": ["11-50"]},
            "angebot": "Altes Angebot",
            "tonalitaet": "ruhig",
            "absender": "Leonard",
            "follow_up_tage": [3, 7],
            "test_empfaenger": ["test@example.com"],
        }, allow_unicode=True),
        encoding="utf-8",
    )
    daten = dict(GUELTIGE_FORMULARDATEN)
    daten["name"] = "Demo GmbH"
    daten["angebot"] = ""  # Pflichtfeld im Formular geleert
    antwort = angemeldeter_client.post(
        "/kunden/demo-gmbh/bearbeiten", data=daten, follow_redirects=False
    )
    assert antwort.status_code == 400
    assert "angebot" in antwort.text
    assert "Pflichtfelder fehlen" in antwort.text

    gespeichert = yaml.safe_load(_kunde_datei(daten_dir, "demo-gmbh").read_text(encoding="utf-8"))
    assert gespeichert["angebot"] == "Altes Angebot"  # Datei unveraendert


def test_pflichtfeld_fehler_zeigt_keinen_temp_pfad(angemeldeter_client, daten_dir):
    daten = dict(GUELTIGE_FORMULARDATEN)
    daten["angebot"] = ""
    antwort = angemeldeter_client.post("/kunden/neu", data=daten)
    assert antwort.status_code == 400
    assert "angebot" in antwort.text
    assert ".tmp" not in antwort.text
    assert str(daten_dir) not in antwort.text


# Angebot ableiten -----------------------------------------------------------

def test_ableiten_fuellt_nur_leere_felder_und_zeigt_badge(
    angemeldeter_client, app, monkeypatch
):
    monkeypatch.setattr(
        "web.routen.kunden.fetch_text", lambda url: "Wir bauen Automationen."
    )
    app.state.ki = FakeKI(json.dumps({
        "angebot": "Abgeleitetes Angebot", "tonalitaet": "Abgeleitete Tonalitaet",
    }))

    daten = dict(GUELTIGE_FORMULARDATEN)
    daten["angebot"] = ""
    daten["tonalitaet"] = ""
    antwort = angemeldeter_client.post("/kunden/neu/ableiten", data=daten)

    assert antwort.status_code == 200
    assert "VORSCHLAG VON DER WEBSEITE" in antwort.text
    assert antwort.text.count("VORSCHLAG VON DER WEBSEITE") == 2
    assert "Abgeleitetes Angebot" in antwort.text
    assert "Abgeleitete Tonalitaet" in antwort.text
    # Nichts wurde gespeichert - der Vorschlag ist nur im Formular sichtbar
    assert not (app.state.daten_dir / "kunden").exists()


def test_ableiten_ueberschreibt_handeingetragenes_angebot_nicht(
    angemeldeter_client, app, monkeypatch
):
    monkeypatch.setattr(
        "web.routen.kunden.fetch_text", lambda url: "Wir bauen Automationen."
    )
    app.state.ki = FakeKI(json.dumps({
        "angebot": "Abgeleitetes Angebot", "tonalitaet": "Abgeleitete Tonalitaet",
    }))

    daten = dict(GUELTIGE_FORMULARDATEN)
    daten["angebot"] = "Handeingetragener Text"
    daten["tonalitaet"] = ""
    antwort = angemeldeter_client.post("/kunden/neu/ableiten", data=daten)

    assert antwort.status_code == 200
    assert "Handeingetragener Text" in antwort.text
    assert "Abgeleitetes Angebot" not in antwort.text  # nicht ueberschrieben
    assert "Abgeleitete Tonalitaet" in antwort.text  # leeres Feld wurde gefuellt
    assert antwort.text.count("VORSCHLAG VON DER WEBSEITE") == 1  # nur bei Tonalitaet


def test_ableiten_bei_ki_fehler_zeigt_dreiteiligen_deutschen_fehler(
    angemeldeter_client, app, monkeypatch
):
    class KaputteKI:
        def frage(self, system, prompt):
            raise RuntimeError("KI-Dienst nicht erreichbar")

    monkeypatch.setattr(
        "web.routen.kunden.fetch_text", lambda url: "Wir bauen Automationen."
    )
    app.state.ki = KaputteKI()

    daten = dict(GUELTIGE_FORMULARDATEN)
    daten["angebot"] = ""
    daten["tonalitaet"] = ""
    antwort = angemeldeter_client.post("/kunden/neu/ableiten", data=daten)

    assert antwort.status_code == 200
    assert "hat gerade nicht geklappt" in antwort.text  # Was ist passiert
    assert "nichts gespeichert oder verändert" in antwort.text  # Beruhigung
    assert "noch einmal versuchen" in antwort.text  # Was du tun kannst
    assert "Neue Firma GmbH" in antwort.text  # Eingaben bleiben erhalten
    assert "VORSCHLAG VON DER WEBSEITE" not in antwort.text


def test_ableiten_laesst_programmierfehler_durch_statt_ihn_zu_verschlucken(
    angemeldeter_client, app, monkeypatch
):
    # E-Fix 5: _ableiten_antwort hatte `except Exception` - das wuerde auch
    # echte Programmierfehler (z.B. ein TypeError in eigenem Code) leise
    # verschlucken und als "hat gerade nicht geklappt" anzeigen. Jetzt sind
    # nur noch die konkret erwarteten Ausnahmen gefangen (requests-/KI-
    # Fehler), ein TypeError muss sichtbar bleiben.
    class KaputteKIProgrammierfehler:
        def frage(self, system, prompt):
            raise TypeError("das ist ein Programmierfehler, kein erwarteter KI-Fehler")

    monkeypatch.setattr(
        "web.routen.kunden.fetch_text", lambda url: "Wir bauen Automationen."
    )
    app.state.ki = KaputteKIProgrammierfehler()

    daten = dict(GUELTIGE_FORMULARDATEN)
    daten["angebot"] = ""
    daten["tonalitaet"] = ""
    with pytest.raises(TypeError):
        angemeldeter_client.post("/kunden/neu/ableiten", data=daten)


def test_ableiten_ohne_webseite_bricht_ab_ohne_ki_aufruf(angemeldeter_client, app):
    class KIDieNichtGerufenWerdenDarf:
        def frage(self, system, prompt):
            raise AssertionError("KI haette bei fehlender Webseite nicht aufgerufen werden duerfen")

    app.state.ki = KIDieNichtGerufenWerdenDarf()

    daten = dict(GUELTIGE_FORMULARDATEN)
    daten["webseite"] = "   "
    daten["angebot"] = ""
    daten["tonalitaet"] = ""
    antwort = angemeldeter_client.post("/kunden/neu/ableiten", data=daten)

    assert antwort.status_code == 200
    assert (
        "Trag zuerst die Webseite der Firma ein — daraus wird das Angebot abgeleitet."
        in antwort.text
    )
    assert "Neue Firma GmbH" in antwort.text  # Eingaben bleiben erhalten
    assert "VORSCHLAG VON DER WEBSEITE" not in antwort.text
