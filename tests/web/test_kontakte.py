"""Tests fuer den Kontakte-Bereich (Task 8): web.kontakte.sammle_kontakte
(reine Aggregation, ohne HTTP) UND die Route /kontakte (Suche, Anmeldung,
rein lesend). Muster/Fixtures angelehnt an tests/web/test_kampagnen.py
(_lauf_anlegen dort) - hier eigene _lauf()-Hilfe, weil dieser Bereich
zusaetzlich echte leads.json-Eintraege (Name/Firma) braucht, die
test_kampagnen.py nicht schreibt."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient
from passlib.context import CryptContext

from pipeline.approval import approve
from pipeline.run_store import RunStore
from web.app import create_app
from web.kontakte import sammle_kontakte

PWD_CONTEXT = CryptContext(schemes=["bcrypt"], deprecated="auto")

KUNDE_A_YAML = """
name: Demo GmbH
zielgruppe:
  titel: [CEO]
angebot: Testangebot
tonalitaet: ruhig
absender: Jonas Wilde
follow_up_tage: [4, 9]
test_empfaenger: [anna@firma.de]
sperrliste: []
"""

KUNDE_B_YAML = """
name: MOVEO Personalberatung
zielgruppe:
  titel: [CTO]
angebot: Testangebot B
tonalitaet: sachlich
absender: Petra Wolf
follow_up_tage: [3, 8]
test_empfaenger: [bob@firma.de]
sperrliste: []
"""


def _lead(vorname, nachname, email, firma):
    return {"first_name": vorname, "last_name": nachname, "email": email,
            "company": firma, "title": "CEO", "website": "https://" + firma.lower() + ".de",
            "source": "apollo"}


def _lauf(daten_dir: Path, slug: str, kunde_datei: str, ts: str, leads: list, *,
          legacy_leads: bool = False, pruefung_ok: list | None = None,
          versand_komplett: bool = False, name: str = "Lena Hartmann") -> Path:
    """Baut einen Laufordner mit echten leads.json-Eintraegen (Name/Firma)
    plus optional pruefung_ok/Freigabe/Uebergabe - fuer die Kontakte-
    Aggregation braucht es (anders als test_kampagnen.py) echte Lead-Daten,
    keine reinen Marker-Dateien."""
    lauf_dir = daten_dir / "laeufe" / slug / ts
    lauf_dir.mkdir(parents=True)
    store = RunStore.resume(lauf_dir)
    store.save_step("kunde_pfad", {"pfad": f"kunden/{kunde_datei}"})

    if legacy_leads:
        (lauf_dir / "leads.json").write_text(json.dumps(leads), encoding="utf-8")
    else:
        (lauf_dir / "leads.json").write_text(
            json.dumps({"leads": leads, "ohne_email": 0}), encoding="utf-8")

    if pruefung_ok is not None:
        store.save_step("pruefung_ok", pruefung_ok)
    if versand_komplett:
        approve(store, name=name)
        store.save_step("versand", {"campaign_id": "camp-x"})
        store.save_step("versand_komplett", {"campaign_id": "camp-x"})
    return lauf_dir


@pytest.fixture
def daten_dir(tmp_path):
    (tmp_path / "kunden").mkdir()
    (tmp_path / "kunden" / "demo-gmbh.yaml").write_text(KUNDE_A_YAML, encoding="utf-8")
    (tmp_path / "kunden" / "moveo.yaml").write_text(KUNDE_B_YAML, encoding="utf-8")
    return tmp_path


# sammle_kontakte() - reine Aggregation, ohne HTTP -------------------------

def test_ohne_laeufe_ordner_leere_liste(tmp_path):
    assert sammle_kontakte(tmp_path) == []


def test_aggregiert_ueber_zwei_kunden_drei_laeufe_inkl_legacy_leads(daten_dir):
    # Kunde A, Lauf 1: altes Listenformat, nie versendet.
    _lauf(daten_dir, "demo-gmbh", "demo-gmbh.yaml", "20260701-090000",
          leads=[_lead("Anna", "Muster", "anna@demo.de", "Alte Firma GmbH")],
          legacy_leads=True)
    # Kunde A, Lauf 2: gefunden, geprueft UND uebergeben -> "angeschrieben".
    _lauf(daten_dir, "demo-gmbh", "demo-gmbh.yaml", "20260705-090000",
          leads=[_lead("Bob", "Beispiel", "bob@demo.de", "Demo GmbH")],
          pruefung_ok=[{"email": "bob@demo.de", "betreff": "Betreff"}],
          versand_komplett=True)
    # Kunde B, Lauf 1: gefunden und Pruefung bestanden, aber NICHT uebergeben
    # (noch nicht freigegeben) -> zaehlt trotzdem nur als "gefunden".
    _lauf(daten_dir, "moveo", "moveo.yaml", "20260703-090000",
          leads=[_lead("Carla", "Chef", "carla@moveo.de", "Moveo Kunden AG")],
          pruefung_ok=[{"email": "carla@moveo.de", "betreff": "Betreff"}])

    kontakte = sammle_kontakte(daten_dir)
    assert len(kontakte) == 3
    by_mail = {k["email"]: k for k in kontakte}

    anna = by_mail["anna@demo.de"]
    assert anna["name"] == "Anna Muster"
    assert anna["firma"] == "Alte Firma GmbH"
    assert anna["kunde"] == "Demo GmbH"
    assert anna["zuletzt"] == "nur gefunden, nie angeschrieben"

    carla = by_mail["carla@moveo.de"]
    assert carla["kunde"] == "MOVEO Personalberatung"  # Kundenname aus der Kunden-Datei, nicht die Firma
    assert carla["zuletzt"] == "nur gefunden, nie angeschrieben"

    # Sortierung: neuester Lauf zuerst (Bob 07-05 > Carla 07-03 > Anna 07-01).
    assert [k["email"] for k in kontakte] == ["bob@demo.de", "carla@moveo.de", "anna@demo.de"]


def test_angeschrieben_am_zeigt_deutsches_datum_nicht_iso(daten_dir):
    # E-Fix 3: freigabe_info()["am"] ist ein ISO-Zeitstempel (siehe
    # pipeline.approval.approve) - fuer die Anzeige muss das als deutsches
    # Datum "17.07.2026, 09:33 Uhr" erscheinen, nicht roh.
    _lauf(daten_dir, "demo-gmbh", "demo-gmbh.yaml", "20260705-090000",
          leads=[_lead("Bob", "Beispiel", "bob@demo.de", "Demo GmbH")],
          pruefung_ok=[{"email": "bob@demo.de", "betreff": "Betreff"}],
          versand_komplett=True)

    kontakte = sammle_kontakte(daten_dir)
    zuletzt = kontakte[0]["zuletzt"]
    assert re.match(r"angeschrieben am \d{2}\.\d{2}\.\d{4}, \d{2}:\d{2} Uhr$", zuletzt)


def test_gefunden_und_uebergeben_wird_ehrlich_als_angeschrieben_beschriftet(daten_dir):
    _lauf(daten_dir, "demo-gmbh", "demo-gmbh.yaml", "20260705-090000",
          leads=[_lead("Bob", "Beispiel", "bob@demo.de", "Demo GmbH")],
          pruefung_ok=[{"email": "bob@demo.de", "betreff": "Betreff"}],
          versand_komplett=True)

    kontakte = sammle_kontakte(daten_dir)
    assert len(kontakte) == 1
    assert kontakte[0]["zuletzt"].startswith("angeschrieben am ")


def test_gefunden_aber_von_der_pruefung_aussortiert_bleibt_nie_angeschrieben(daten_dir):
    # Uebergeben (versand_komplett), aber DIESER Kontakt steht nicht in
    # pruefung_ok (z.B. von der Qualitaets-Pruefung aussortiert) - er darf
    # trotzdem nicht als "angeschrieben" durchgehen.
    _lauf(daten_dir, "demo-gmbh", "demo-gmbh.yaml", "20260705-090000",
          leads=[_lead("Bob", "Beispiel", "bob@demo.de", "Demo GmbH"),
                 _lead("Nora", "Nacharbeit", "nora@demo.de", "Demo GmbH")],
          pruefung_ok=[{"email": "bob@demo.de", "betreff": "Betreff"}],
          versand_komplett=True)

    kontakte = sammle_kontakte(daten_dir)
    by_mail = {k["email"]: k for k in kontakte}
    assert by_mail["bob@demo.de"]["zuletzt"].startswith("angeschrieben am ")
    assert by_mail["nora@demo.de"]["zuletzt"] == "nur gefunden, nie angeschrieben"


def test_dedupe_per_email_neuester_lauf_gewinnt(daten_dir):
    _lauf(daten_dir, "demo-gmbh", "demo-gmbh.yaml", "20260701-090000",
          leads=[_lead("Anna", "Alt", "anna@demo.de", "Alte Firma GmbH")])
    _lauf(daten_dir, "demo-gmbh", "demo-gmbh.yaml", "20260710-090000",
          leads=[_lead("Anna", "Neu", "anna@demo.de", "Neue Firma GmbH")],
          pruefung_ok=[{"email": "anna@demo.de", "betreff": "Betreff"}],
          versand_komplett=True)

    kontakte = sammle_kontakte(daten_dir)
    assert len(kontakte) == 1
    assert kontakte[0]["name"] == "Anna Neu"
    assert kontakte[0]["firma"] == "Neue Firma GmbH"
    assert kontakte[0]["zuletzt"].startswith("angeschrieben am ")


def test_kaputter_laufordner_wird_uebersprungen_andere_bleiben(daten_dir):
    kaputt_dir = daten_dir / "laeufe" / "demo-gmbh" / "20260701-090000"
    kaputt_dir.mkdir(parents=True)
    (kaputt_dir / "leads.json").write_text("{das ist kein gueltiges JSON", encoding="utf-8")

    _lauf(daten_dir, "demo-gmbh", "demo-gmbh.yaml", "20260702-090000",
          leads=[_lead("Bob", "Beispiel", "bob@demo.de", "Demo GmbH")])

    kontakte = sammle_kontakte(daten_dir)
    assert len(kontakte) == 1
    assert kontakte[0]["email"] == "bob@demo.de"


def test_nicht_ordner_im_laeufe_verzeichnis_stuerzt_nicht_ab(daten_dir):
    (daten_dir / "laeufe" / "demo-gmbh").mkdir(parents=True)
    (daten_dir / "laeufe" / "demo-gmbh" / "irgendwas.txt").write_text("x", encoding="utf-8")
    assert sammle_kontakte(daten_dir) == []


# Route /kontakte -----------------------------------------------------------

@pytest.fixture
def app(daten_dir, monkeypatch):
    monkeypatch.setenv("WEB_SECRET", "test-geheimnis-nur-fuer-tests")
    monkeypatch.setenv("WEB_COOKIE_SECURE", "0")
    nutzer = [{"name": "Lena Hartmann", "passwort_hash": PWD_CONTEXT.hash("richtig123")}]
    (daten_dir / "users.yaml").write_text(yaml.safe_dump(nutzer, allow_unicode=True), encoding="utf-8")
    return create_app(daten_dir)


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def angemeldeter_client(client):
    client.post("/login", data={"name": "Lena Hartmann", "passwort": "richtig123"})
    return client


def test_liste_verlangt_anmeldung(client):
    antwort = client.get("/kontakte", follow_redirects=False)
    assert antwort.status_code == 303
    assert antwort.headers["location"] == "/login"


def test_liste_zeigt_leeren_zustand(angemeldeter_client):
    antwort = angemeldeter_client.get("/kontakte")
    assert antwort.status_code == 200
    assert "Nichts gefunden. Andere Schreibweise versuchen?" in antwort.text
    assert "0 Kontakte" in antwort.text


def test_liste_zeigt_kontakte_mit_allen_spalten(angemeldeter_client, daten_dir):
    _lauf(daten_dir, "demo-gmbh", "demo-gmbh.yaml", "20260705-090000",
          leads=[_lead("Bob", "Beispiel", "bob@demo.de", "Demo GmbH")],
          pruefung_ok=[{"email": "bob@demo.de", "betreff": "Betreff"}],
          versand_komplett=True)

    antwort = angemeldeter_client.get("/kontakte")
    assert antwort.status_code == 200
    text = antwort.text
    assert "Bob Beispiel" in text
    assert "Demo GmbH" in text
    assert "bob@demo.de" in text
    assert "angeschrieben am" in text
    assert "1 Kontakte" in text


def test_suche_filtert_ueber_name_firma_und_kunde(angemeldeter_client, daten_dir):
    _lauf(daten_dir, "demo-gmbh", "demo-gmbh.yaml", "20260701-090000",
          leads=[_lead("Anna", "Muster", "anna@demo.de", "Alte Firma GmbH")])
    _lauf(daten_dir, "moveo", "moveo.yaml", "20260702-090000",
          leads=[_lead("Carla", "Chef", "carla@moveo.de", "Moveo Kunden AG")])

    # Treffer ueber den Namen
    antwort = angemeldeter_client.get("/kontakte", params={"q": "Anna"})
    assert "anna@demo.de" in antwort.text
    assert "carla@moveo.de" not in antwort.text

    # Treffer ueber die Firma
    antwort = angemeldeter_client.get("/kontakte", params={"q": "Kunden AG"})
    assert "carla@moveo.de" in antwort.text
    assert "anna@demo.de" not in antwort.text

    # Treffer ueber den Kunden-Namen (nicht die Firma des Kontakts)
    antwort = angemeldeter_client.get("/kontakte", params={"q": "MOVEO Personalberatung"})
    assert "carla@moveo.de" in antwort.text
    assert "anna@demo.de" not in antwort.text

    # Kein Treffer -> Leer-Zustand
    antwort = angemeldeter_client.get("/kontakte", params={"q": "gibtsnicht"})
    assert "Nichts gefunden. Andere Schreibweise versuchen?" in antwort.text


def test_seite_ist_rein_lesend_keine_post_route(angemeldeter_client):
    antwort = angemeldeter_client.post("/kontakte")
    assert antwort.status_code == 405
