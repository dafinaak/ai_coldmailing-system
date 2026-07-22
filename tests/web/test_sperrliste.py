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
    # Copy-Rework (20.07.2026): siehe tests/web/test_dashboard.py fuer den Grund.
    client.cookies.set("intro_gesehen", "1")
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
        "für welches Angebot." in antwort.text
    )
    assert "Angebot-Formular" in antwort.text
    assert "Beide Listen gelten zusammen." in antwort.text


def test_seite_zeigt_leere_liste(angemeldeter_client):
    antwort = angemeldeter_client.get("/domains")
    assert antwort.status_code == 200
    assert "Noch keine gesperrten Domains" in antwort.text


def test_domain_hinzufuegen_schreibt_datei(angemeldeter_client, daten_dir):
    antwort = angemeldeter_client.post(
        "/domains/hinzufuegen",
        data={"domain": "  *.Bund.de  ", "grund": "Kunde", "kommentar": "Vertrag"},
        follow_redirects=False,
    )
    assert antwort.status_code == 303
    assert antwort.headers["location"] == "/domains"
    inhalt = yaml.safe_load((daten_dir / "sperrliste-global.yaml").read_text(encoding="utf-8"))
    assert inhalt == [{
        "domain": "*.bund.de", "reason": "Kunde", "comment": "Vertrag",
    }]


def test_seite_zeigt_vorhandene_domains(angemeldeter_client, daten_dir):
    (daten_dir / "sperrliste-global.yaml").write_text(
        yaml.safe_dump(["konkurrent-ki.de"]), encoding="utf-8"
    )
    antwort = angemeldeter_client.get("/domains")
    assert "konkurrent-ki.de" in antwort.text


def test_sperrliste_zeigt_wholix_spalten_und_strukturierte_werte(
        angemeldeter_client, daten_dir):
    (daten_dir / "sperrliste-global.yaml").write_text(
        '- domain: "*.bund.de"\n  reason: "Kunde"\n  comment: "Rahmenvertrag"\n',
        encoding="utf-8",
    )

    antwort = angemeldeter_client.get("/domains")

    assert antwort.status_code == 200
    for text in (
        "Domain", "Grund", "Kommentar", "Aktionen", "*.bund.de",
        "Kunde", "Rahmenvertrag",
    ):
        assert text in antwort.text
    assert 'id="sperrliste-suche"' in antwort.text
    assert "<table" in antwort.text
    assert "/domains/bearbeiten" in antwort.text
    assert "/domains/entfernen" in antwort.text


def test_domain_hinzufuegen_leer_gibt_deutschen_fehler(angemeldeter_client, daten_dir):
    antwort = angemeldeter_client.post(
        "/domains/hinzufuegen",
        data={"domain": "   ", "grund": "Sonstiges", "kommentar": ""},
    )
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
        "/domains/hinzufuegen",
        data={"domain": "Konkurrent-KI.de", "grund": "Konkurrent", "kommentar": ""},
    )
    assert antwort.status_code == 400
    assert "steht schon auf der Liste" in antwort.text
    inhalt = yaml.safe_load((daten_dir / "sperrliste-global.yaml").read_text(encoding="utf-8"))
    assert inhalt == ["konkurrent-ki.de"]


@pytest.mark.parametrize(
    "domain",
    ["https://firma.de", "firma.de/pfad", "*firma.de", "firma", "fi rma.de"],
)
def test_ungueltiges_domain_muster_wird_abgewiesen(
        angemeldeter_client, daten_dir, domain):
    antwort = angemeldeter_client.post(
        "/domains/hinzufuegen",
        data={"domain": domain, "grund": "Kunde", "kommentar": ""},
    )

    assert antwort.status_code == 400
    assert "gültige Domain" in antwort.text
    assert not (daten_dir / "sperrliste-global.yaml").exists()


def test_einzelne_domain_wird_abgewiesen_wenn_wildcard_sie_schon_abdeckt(
        angemeldeter_client, daten_dir):
    pfad = daten_dir / "sperrliste-global.yaml"
    pfad.write_text('- "*.bund.de"\n', encoding="utf-8")
    vorher = pfad.read_bytes()

    antwort = angemeldeter_client.post(
        "/domains/hinzufuegen",
        data={"domain": "amt.bund.de", "grund": "Kunde", "kommentar": ""},
    )

    assert antwort.status_code == 400
    assert "*.bund.de" in antwort.text
    assert pfad.read_bytes() == vorher


def test_neuer_platzhalter_wird_abgewiesen_wenn_er_einzelne_domain_abdeckt(
        angemeldeter_client, daten_dir):
    pfad = daten_dir / "sperrliste-global.yaml"
    pfad.write_text('- "amt.bund.de"\n', encoding="utf-8")
    vorher = pfad.read_bytes()

    antwort = angemeldeter_client.post(
        "/domains/hinzufuegen",
        data={"domain": "*.bund.de", "grund": "Kunde", "kommentar": ""},
    )

    assert antwort.status_code == 400
    assert "amt.bund.de" in antwort.text
    assert pfad.read_bytes() == vorher


@pytest.mark.parametrize("grund", ["", "Lieferant", "kunde"])
def test_ungueltiger_grund_aendert_datei_nicht(
        angemeldeter_client, daten_dir, grund):
    antwort = angemeldeter_client.post(
        "/domains/hinzufuegen",
        data={"domain": "firma.de", "grund": grund, "kommentar": ""},
    )

    assert antwort.status_code == 400
    assert "Grund" in antwort.text
    assert not (daten_dir / "sperrliste-global.yaml").exists()


def test_zu_langer_kommentar_aendert_datei_nicht(angemeldeter_client, daten_dir):
    antwort = angemeldeter_client.post(
        "/domains/hinzufuegen",
        data={"domain": "firma.de", "grund": "Partner", "kommentar": "x" * 1001},
    )

    assert antwort.status_code == 400
    assert "1000" in antwort.text
    assert not (daten_dir / "sperrliste-global.yaml").exists()


def test_alten_eintrag_bearbeiten_wandelt_nur_ihn_in_struktur_um(
        angemeldeter_client, daten_dir):
    pfad = daten_dir / "sperrliste-global.yaml"
    pfad.write_text('- "alt.de"\n- "bleibt.de"\n', encoding="utf-8")

    antwort = angemeldeter_client.post(
        "/domains/bearbeiten",
        data={
            "urspruengliche_domain": "alt.de", "domain": "neu.de",
            "grund": "Sonstiges", "kommentar": "Umbenannt",
        },
        follow_redirects=False,
    )

    assert antwort.status_code == 303
    assert yaml.safe_load(pfad.read_text(encoding="utf-8")) == [
        {"domain": "neu.de", "reason": "Sonstiges", "comment": "Umbenannt"},
        "bleibt.de",
    ]


def test_strukturierter_eintrag_wird_mit_domain_entfernt(
        angemeldeter_client, daten_dir):
    pfad = daten_dir / "sperrliste-global.yaml"
    pfad.write_text(
        '- domain: "firma.de"\n  reason: "Kunde"\n  comment: "Vertrag"\n'
        '- "bleibt.de"\n',
        encoding="utf-8",
    )

    antwort = angemeldeter_client.post(
        "/domains/entfernen", data={"domain": "firma.de"}, follow_redirects=False,
    )

    assert antwort.status_code == 303
    assert yaml.safe_load(pfad.read_text(encoding="utf-8")) == ["bleibt.de"]


def test_speichern_hinterlaesst_keine_temporaeren_dateien(angemeldeter_client, daten_dir):
    # E-Fix 1: sperrliste-global.yaml wird atomar geschrieben (temp-Datei +
    # os.replace, gleiches Muster wie web.routen.kunden._validieren_und_
    # speichern) - nach dem Schreiben darf keine liegen gebliebene temporaere
    # Datei im Datenverzeichnis zurueckbleiben (z.B. bei einem Absturz
    # mitten im write_text waere die Zieldatei vorher kurzzeitig
    # kaputt/leer gewesen).
    angemeldeter_client.post(
        "/domains/hinzufuegen",
        data={"domain": "konkurrent.de", "grund": "Konkurrent", "kommentar": ""},
    )
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
