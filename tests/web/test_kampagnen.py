"""Tests fuer den Kampagnen-Bereich (Task 6): Liste (Vorbereitung + Alle
Kampagnen mit Live-Stand) und Detail-Ansicht. Instantly ist ueber
app.state.instantly_leser gefaked - exakt das Muster aus
tests/web/test_freigabe.py (dort app.state.instantly fuer den
Schreib-Pfad)."""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient
from passlib.context import CryptContext

from pipeline.approval import approve
from pipeline.run_store import RunStore
from web.app import create_app
from web.instantly_leser import InstantlyLeser

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

_TEXT = {"email": "anna@firma.de", "betreff": "Betreff", "mail_1": "Text",
         "follow_up_1": "F1", "follow_up_2": "F2"}


class FakeInstantly:
    """Ersetzt pipeline.senders.instantly.InstantlySender fuer den
    Schreib-Pfad (Baustein 1: scharf schalten/pausieren) - exakt das Muster
    aus tests/web/test_freigabe.py FakeInstantly, hier um
    aktiviere_kampagne/pausiere_kampagne erweitert."""

    def __init__(self, fehler_bei: str | None = None):
        self.aktiviert: list[str] = []
        self.pausiert: list[str] = []
        self.fehler_bei = fehler_bei

    def aktiviere_kampagne(self, campaign_id: str) -> None:
        if self.fehler_bei == "aktivieren":
            raise RuntimeError("Instantly antwortet mit 500 auf /activate: Server-Fehler")
        self.aktiviert.append(campaign_id)

    def pausiere_kampagne(self, campaign_id: str) -> None:
        if self.fehler_bei == "pausieren":
            raise RuntimeError("Instantly antwortet mit 500 auf /pause: Server-Fehler")
        self.pausiert.append(campaign_id)


class FakeInstantlyLeser:
    """Ersetzt web.instantly_leser.InstantlyLeser: liefert vorbereitete
    Antworten statt echter HTTP-Aufrufe. `antworten` bildet campaign_id auf
    einen fertigen Stand-Datensatz ab (wie kampagnen_stand() ihn liefert)."""

    def __init__(self, antworten: dict):
        self.antworten = antworten
        self.angefragt: list[str] = []

    def kampagnen_stand(self, campaign_ids):
        self.angefragt = list(campaign_ids)
        return {cid: self.antworten.get(cid, {
            "erreichbar": False, "status": None, "name": None,
            "versendet": None, "antworten": None, "schritte": [], "stand": None,
        }) for cid in campaign_ids}

    def postfaecher(self):
        return {
            "erreichbar": True,
            "stand": datetime(2026, 7, 22, 10, 30),
            "postfaecher": [{
                "email": "sender@firma.de", "status": "verbunden",
                "warmup": "an", "daily_limit": 20,
            }],
        }


def _stand(status="pausiert", name="[TEST] Demo GmbH", versendet=3, antworten=1,
           schritte=None, erreichbar=True, stand=None):
    return {
        "erreichbar": erreichbar, "status": status, "name": name,
        "versendet": versendet, "antworten": antworten,
        "empfaenger": 12, "geoeffnet": 4, "unzustellbar": 1,
        "abgeschlossen": 3, "heute_versendet": 7,
        "absender": ["sender@firma.de"],
        "sendefenster": [{
            "name": "Werktage", "von": "08:00", "bis": "19:00",
            "tage": {"0": False, "1": True, "2": True, "3": True,
                     "4": True, "5": True, "6": False},
            "zeitzone": "Europe/Berlin",
        }],
        "schritte": schritte if schritte is not None else [
            {"schritt": 1, "versendet": versendet}],
        "stand": stand if stand is not None else datetime(2026, 7, 20, 9, 30),
    }


@pytest.fixture
def daten_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("WEB_SECRET", "test-geheimnis-nur-fuer-tests")
    monkeypatch.setenv("WEB_COOKIE_SECURE", "0")
    nutzer = [{"name": "Lena Hartmann", "passwort_hash": PWD_CONTEXT.hash("richtig123")}]
    (tmp_path / "users.yaml").write_text(yaml.safe_dump(nutzer, allow_unicode=True), encoding="utf-8")
    (tmp_path / "kunden").mkdir()
    (tmp_path / "kunden" / "demo-gmbh.yaml").write_text(KUNDE_A_YAML, encoding="utf-8")
    (tmp_path / "kunden" / "moveo.yaml").write_text(KUNDE_B_YAML, encoding="utf-8")
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


def _lauf_anlegen(daten_dir: Path, slug: str, kunde_datei: str, *, ts: str,
                   zustand: str = "uebergeben", campaign_id: str | None = "camp-1") -> Path:
    """Baut einen Laufordner im gewuenschten Zustand nach (siehe
    web.laufmanager.Laufmanager.status fuer die Zustandslogik):
    - "laeuft": nur leads.json (kein dedupe/personalisierung) -> schritt 3
    - "angehalten": wie "laeuft", aber leads+dedupe da, kein personalisierung -
      Laufmanager braucht dafuer eigentlich einen toten pid; hier ohne pid-
      Datei ist der Prozess per Definition nicht "laeuft", also "angehalten".
    - "wartet_auf_freigabe": pruefung_ok.json vorhanden, keine FREIGABE.txt
    - "freigegeben": FREIGABE.txt vorhanden, kein versand_komplett
    - "uebergeben": versand_komplett.json vorhanden (campaign_id)
    """
    lauf_dir = daten_dir / "laeufe" / slug / ts
    lauf_dir.mkdir(parents=True)
    store = RunStore.resume(lauf_dir)
    store.save_step("kunde_pfad", {"pfad": f"kunden/{kunde_datei}"})

    if zustand == "laeuft_platzhalter":
        return lauf_dir  # nur kunde_pfad - Schritt 1 laeuft laut leads=None

    store.save_step("dedupe", {"behalten": [], "verworfen": []})
    if zustand == "angehalten":
        (lauf_dir / "lauf.log").write_text("Irgendein Fehler ist aufgetreten.", encoding="utf-8")
        return lauf_dir

    store.save_step("personalisierung", {"fertig": [_TEXT], "nacharbeit": []})
    store.save_step("pruefung_ok", [_TEXT])
    if zustand == "wartet_auf_freigabe":
        return lauf_dir

    approve(store, name="Lena Hartmann")
    if zustand == "freigegeben":
        return lauf_dir
    if zustand == "freigegeben_mit_versand":
        store.save_step("versand", {"campaign_id": campaign_id})
        return lauf_dir

    store.save_step("versand", {"campaign_id": campaign_id})
    store.save_step("versand_komplett", {"campaign_id": campaign_id})
    return lauf_dir


# Anmeldung -------------------------------------------------------------

def test_liste_verlangt_anmeldung(client):
    antwort = client.get("/kampagnen", follow_redirects=False)
    assert antwort.status_code == 303
    assert antwort.headers["location"] == "/login"


def test_detail_verlangt_anmeldung(client, daten_dir):
    _lauf_anlegen(daten_dir, "demo-gmbh", "demo-gmbh.yaml", ts="20260720-090000")
    antwort = client.get("/kampagnen/demo-gmbh/20260720-090000", follow_redirects=False)
    assert antwort.status_code == 303


# Liste -------------------------------------------------------------------

def test_liste_leer_zeigt_hinweis(angemeldeter_client):
    antwort = angemeldeter_client.get("/kampagnen")
    assert antwort.status_code == 200
    assert "Noch keine Kampagne" in antwort.text


def test_liste_aggregiert_ueber_zwei_kunden_mit_korrekten_spalten(angemeldeter_client, daten_dir):
    app = angemeldeter_client.app
    app.state.instantly_leser = FakeInstantlyLeser({
        "camp-a": _stand(status="aktiv", name="[TEST] Demo GmbH", versendet=5),
        "camp-b": _stand(status="abgeschlossen", name="MOVEO – Welle 1", versendet=12),
    })
    _lauf_anlegen(daten_dir, "demo-gmbh", "demo-gmbh.yaml", ts="20260720-090000",
                  zustand="uebergeben", campaign_id="camp-a")
    _lauf_anlegen(daten_dir, "moveo", "moveo.yaml", ts="20260720-091500",
                  zustand="uebergeben", campaign_id="camp-b")

    antwort = angemeldeter_client.get("/kampagnen")
    assert antwort.status_code == 200
    text = antwort.text
    assert "[TEST] Demo GmbH" in text
    assert "MOVEO – Welle 1" in text
    assert "Demo GmbH" in text
    assert "MOVEO Personalberatung" in text
    assert "AKTIV" in text
    assert "FERTIG" in text
    assert ">5<" in text or "5" in text
    assert "12" in text
    assert "/kampagnen/demo-gmbh/20260720-090000" in text
    assert "/kampagnen/moveo/20260720-091500" in text


def test_liste_zeigt_wholix_kennzahlen_und_filtert_nach_status(angemeldeter_client, daten_dir):
    angemeldeter_client.app.state.instantly_leser = FakeInstantlyLeser({
        "camp-a": _stand(status="aktiv", name="Aktive Runde"),
        "camp-b": _stand(status="abgeschlossen", name="Fertige Runde"),
    })
    _lauf_anlegen(daten_dir, "demo-gmbh", "demo-gmbh.yaml",
                  ts="20260720-090000", campaign_id="camp-a")
    _lauf_anlegen(daten_dir, "moveo", "moveo.yaml",
                  ts="20260720-091500", campaign_id="camp-b")

    antwort = angemeldeter_client.get("/kampagnen?status=aktiv")
    assert antwort.context["kennzahlen"] == {
        "kampagnen": 2,
        "aktiv": 1,
        "empfaenger": 2,
        "geoeffnet": 8,
        "versendet": 6,
        "antworten": 2,
        "fehlgeschlagen": None,
        "unzustellbar": 2,
    }
    assert [zeile["name"] for zeile in antwort.context["kampagnen"]] == ["Aktive Runde"]
    assert antwort.context["status_filter"] == "aktiv"


def test_liste_zeigt_vorbereitung_fuer_wartende_und_angehaltene_auftraege(angemeldeter_client, daten_dir):
    app = angemeldeter_client.app
    app.state.instantly_leser = FakeInstantlyLeser({})
    _lauf_anlegen(daten_dir, "demo-gmbh", "demo-gmbh.yaml", ts="20260720-090000",
                  zustand="wartet_auf_freigabe")
    _lauf_anlegen(daten_dir, "moveo", "moveo.yaml", ts="20260720-091500",
                  zustand="angehalten")

    antwort = angemeldeter_client.get("/kampagnen")
    assert antwort.status_code == 200
    text = antwort.text
    assert "IN VORBEREITUNG" in text
    assert "Demo GmbH" in text
    assert "Jetzt lesen" in text
    assert "/pruefen/demo-gmbh/20260720-090000" in text
    assert "Angehalten" in text
    assert "/auftraege/moveo/20260720-091500" in text
    assert "Fortsetzen" in text
    # Ohne Kampagne noch nicht in der Kampagnen-Tabelle:
    assert "Noch keine Kampagne" in text


def test_liste_zeigt_anschreiben_erstellen_lassen_knopf(angemeldeter_client):
    antwort = angemeldeter_client.get("/kampagnen")
    assert antwort.status_code == 200
    assert "E-Mails schreiben lassen" in antwort.text
    assert "/auftraege/neu" in antwort.text


def test_liste_zeigt_konto_problem_chip_statt_pausiert(angemeldeter_client, daten_dir):
    # Review-Fund: Instantly-Konto-Stoerungen (Account Suspended/Unhealthy/
    # Bounce Protect) duerfen nicht als harmloses "pausiert" durchgehen -
    # eigener, lauter Chip "KONTO-PROBLEM".
    app = angemeldeter_client.app
    app.state.instantly_leser = FakeInstantlyLeser({
        "camp-a": _stand(status="kontoproblem", name="[TEST] Demo GmbH"),
    })
    _lauf_anlegen(daten_dir, "demo-gmbh", "demo-gmbh.yaml", ts="20260720-090000",
                  zustand="uebergeben", campaign_id="camp-a")

    antwort = angemeldeter_client.get("/kampagnen")
    assert antwort.status_code == 200
    assert "KONTO-PROBLEM" in antwort.text
    assert "PAUSIERT" not in antwort.text


def test_liste_bei_api_ausfall_zeigt_freundlichen_hinweis_statt_absturz(angemeldeter_client, daten_dir):
    class KaputterLeser:
        def kampagnen_stand(self, campaign_ids):
            return {cid: {"erreichbar": False, "status": None, "name": None,
                          "versendet": None, "antworten": None, "schritte": [],
                          "stand": datetime(2026, 7, 20, 8, 45)} for cid in campaign_ids}

    app = angemeldeter_client.app
    app.state.instantly_leser = KaputterLeser()
    _lauf_anlegen(daten_dir, "demo-gmbh", "demo-gmbh.yaml", ts="20260720-090000",
                  zustand="uebergeben", campaign_id="camp-a")

    antwort = angemeldeter_client.get("/kampagnen")
    assert antwort.status_code == 200
    assert "Live-Stand gerade nicht erreichbar" in antwort.text
    assert "08:45" in antwort.text
    # Zeile erscheint trotzdem (lokale Daten reichen fuer Name/Kunde):
    assert "/kampagnen/demo-gmbh/20260720-090000" in antwort.text


# Detail --------------------------------------------------------------------

def test_liste_zeigt_freigegeben_am_als_deutsches_datum_nicht_iso(angemeldeter_client, daten_dir):
    # E-Fix 3: FREIGABE.txt speichert 'am' als ISO-Zeitstempel (siehe
    # pipeline.approval.approve, datetime.now().isoformat()) - roh angezeigt
    # waere das fuer Laien unlesbar ("2026-07-17T09:33:00.123"). Ein
    # gemeinsamer Helfer formatiert das als deutsches Datum
    # "17.07.2026, 09:33 Uhr".
    app = angemeldeter_client.app
    app.state.instantly_leser = FakeInstantlyLeser({
        "camp-a": _stand(status="aktiv", name="[TEST] Demo GmbH"),
    })
    _lauf_anlegen(daten_dir, "demo-gmbh", "demo-gmbh.yaml", ts="20260720-090000",
                  zustand="uebergeben", campaign_id="camp-a")

    antwort = angemeldeter_client.get("/kampagnen")
    assert antwort.status_code == 200
    assert re.search(r"\d{2}\.\d{2}\.\d{4}, \d{2}:\d{2} Uhr", antwort.text)
    # Kein roher ISO-Zeitstempel (enthaelt ein 'T' zwischen Datum und Zeit)
    # mehr in der Antwort:
    assert not re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", antwort.text)


def test_detail_zeigt_freigegeben_am_als_deutsches_datum_nicht_iso(angemeldeter_client, daten_dir):
    app = angemeldeter_client.app
    app.state.instantly_leser = FakeInstantlyLeser({
        "camp-a": _stand(status="aktiv"),
    })
    _lauf_anlegen(daten_dir, "demo-gmbh", "demo-gmbh.yaml", ts="20260720-090000",
                  zustand="uebergeben", campaign_id="camp-a")

    antwort = angemeldeter_client.get("/kampagnen/demo-gmbh/20260720-090000")
    assert antwort.status_code == 200
    assert re.search(r"\d{2}\.\d{2}\.\d{4}, \d{2}:\d{2} Uhr", antwort.text)
    assert not re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", antwort.text)


def test_detail_zeigt_schritte_mit_echten_tagen_und_wer_wann(angemeldeter_client, daten_dir):
    app = angemeldeter_client.app
    app.state.instantly_leser = FakeInstantlyLeser({
        "camp-a": _stand(status="aktiv", name="[TEST] Demo GmbH", versendet=3,
                          schritte=[{"schritt": 1, "versendet": 3}, {"schritt": 2, "versendet": 1}]),
    })
    _lauf_anlegen(daten_dir, "demo-gmbh", "demo-gmbh.yaml", ts="20260720-090000",
                  zustand="uebergeben", campaign_id="camp-a")

    antwort = angemeldeter_client.get("/kampagnen/demo-gmbh/20260720-090000")
    assert antwort.status_code == 200
    text = antwort.text
    # follow_up_tage: [4, 9] fuer Demo GmbH
    assert "nach 4 Tagen" in text
    assert "nach 9 Tagen" in text
    assert "Erste E-Mail (geht sofort raus)" in text
    assert "Freigegeben von Lena Hartmann am" in text
    assert "3 von 1 versendet" in text or "3 von" in text
    assert "app.instantly.ai/app/campaign/camp-a" in text


def test_detail_zeigt_warteschlange_sendefenster_und_tageslimit(angemeldeter_client, daten_dir):
    angemeldeter_client.app.state.instantly_leser = FakeInstantlyLeser({
        "camp-1": _stand(status="aktiv"),
    })
    _lauf_anlegen(daten_dir, "demo-gmbh", "demo-gmbh.yaml",
                  ts="20260720-093000", campaign_id="camp-1")

    antwort = angemeldeter_client.get("/kampagnen/demo-gmbh/20260720-093000")
    assert antwort.context["kd_warteschlange"] == {
        "gesamt": 4, "versendet": 3, "unzustellbar": 1, "ungetrennt": 0,
    }
    assert antwort.context["kd_tageslimit"] == {"heute": 7, "limit": 20}
    assert antwort.context["kd_sendefenster"] == [{
        "tage_text": "Mo–Fr", "zeit_text": "08:00–19:00",
        "zeitzone": "Europe/Berlin", "ist_jetzt": True,
    }]


def test_detail_zeigt_pausiert_hinweis_nur_wenn_pausiert(angemeldeter_client, daten_dir):
    # Baustein 1 (20.07.2026): Text geaendert - der Start passiert jetzt HIER
    # im Tool (Knopf "Jetzt verschicken"), nicht mehr "von Hand" in Instantly.
    app = angemeldeter_client.app
    app.state.instantly_leser = FakeInstantlyLeser({
        "camp-a": _stand(status="pausiert"),
    })
    _lauf_anlegen(daten_dir, "demo-gmbh", "demo-gmbh.yaml", ts="20260720-090000",
                  zustand="uebergeben", campaign_id="camp-a")
    antwort = angemeldeter_client.get("/kampagnen/demo-gmbh/20260720-090000")
    assert antwort.status_code == 200
    assert "Diese Kampagne ist in Instantly angelegt, aber noch nicht gestartet." in antwort.text
    assert "Jetzt verschicken" in antwort.text
    assert "Gestartet wird dort von Hand" not in antwort.text


def test_detail_zeigt_keinen_pausiert_hinweis_wenn_aktiv(angemeldeter_client, daten_dir):
    app = angemeldeter_client.app
    app.state.instantly_leser = FakeInstantlyLeser({
        "camp-a": _stand(status="aktiv"),
    })
    _lauf_anlegen(daten_dir, "demo-gmbh", "demo-gmbh.yaml", ts="20260720-090000",
                  zustand="uebergeben", campaign_id="camp-a")
    antwort = angemeldeter_client.get("/kampagnen/demo-gmbh/20260720-090000")
    assert antwort.status_code == 200
    assert "liegt pausiert in Instantly" not in antwort.text


def test_detail_zeigt_konto_problem_hinweis_statt_pausiert_saetze(angemeldeter_client, daten_dir):
    # Review-Fund: bei "kontoproblem" muss die eigene, laute Erklaerung
    # erscheinen - NICHT die pausiert-Saetze ("das ist Absicht" waere hier
    # schlicht falsch, das Ruhen ist ein Fehler, keine Absicht).
    app = angemeldeter_client.app
    app.state.instantly_leser = FakeInstantlyLeser({
        "camp-a": _stand(status="kontoproblem"),
    })
    _lauf_anlegen(daten_dir, "demo-gmbh", "demo-gmbh.yaml", ts="20260720-090000",
                  zustand="uebergeben", campaign_id="camp-a")
    antwort = angemeldeter_client.get("/kampagnen/demo-gmbh/20260720-090000")
    assert antwort.status_code == 200
    text = antwort.text
    assert "KONTO-PROBLEM" in text
    assert "Instantly-Konto" in text and "hat ein Problem" in text
    assert "An den Texten und Empfängern hat sich nichts geändert" in text
    assert "liegt pausiert in Instantly" not in text
    assert "das ist Absicht" not in text
    assert "app.instantly.ai/app/campaign/camp-a" in text


def test_detail_ohne_kampagne_404(angemeldeter_client, daten_dir):
    _lauf_anlegen(daten_dir, "demo-gmbh", "demo-gmbh.yaml", ts="20260720-090000",
                  zustand="wartet_auf_freigabe")
    antwort = angemeldeter_client.get("/kampagnen/demo-gmbh/20260720-090000")
    assert antwort.status_code == 404


def test_detail_unbekannter_lauf_404(angemeldeter_client):
    antwort = angemeldeter_client.get("/kampagnen/nix/nix")
    assert antwort.status_code == 404


def test_detail_bei_api_ausfall_zeigt_freundlichen_hinweis(angemeldeter_client, daten_dir):
    class KaputterLeser:
        def kampagnen_stand(self, campaign_ids):
            return {cid: {"erreichbar": False, "status": None, "name": None,
                          "versendet": None, "antworten": None, "schritte": [],
                          "stand": None} for cid in campaign_ids}

    app = angemeldeter_client.app
    app.state.instantly_leser = KaputterLeser()
    _lauf_anlegen(daten_dir, "demo-gmbh", "demo-gmbh.yaml", ts="20260720-090000",
                  zustand="uebergeben", campaign_id="camp-a")
    antwort = angemeldeter_client.get("/kampagnen/demo-gmbh/20260720-090000")
    assert antwort.status_code == 200
    assert "Live-Stand gerade nicht erreichbar" in antwort.text


# Geteilter InstantlyLeser (IMPORTANT Review-Fund) ---------------------------

def test_instantly_leser_wird_beim_start_eager_gebaut_und_zwischen_requests_geteilt(
        daten_dir, monkeypatch):
    """Der 60s-Cache in InstantlyLeser (siehe web.instantly_leser Klassen-
    Docstring) wirkt nur, wenn ALLE Requests denselben InstantlyLeser
    teilen. Vorher baute _hole_leser() ohne app.state.instantly_leser (der
    Normalfall in Produktion - nur Tests faken ihn) bei JEDEM Request einen
    frischen InstantlyLeser, der Cache griff nie. Beweis hier: KEIN
    app.state.instantly_leser wird von Hand gesetzt (anders als die anderen
    Tests in dieser Datei) - INSTANTLY_API_KEY ist schon VOR create_app()
    gesetzt (eager-Pfad), zwei GET-Requests treffen auf denselben, echten
    InstantlyLeser (gezaehlt ueber __init__-Aufrufe; die eigentlichen
    HTTP-Aufrufe sind ueber _get gefaked, damit kein echtes Netzwerk
    angefasst wird)."""
    aufrufe = []
    original_init = InstantlyLeser.__init__

    def zaehlender_init(self, *a, **kw):
        aufrufe.append(1)
        original_init(self, *a, **kw)

    def gefakter_get(self, pfad, params):
        if "steps" in pfad:
            return []
        if "analytics" in pfad:
            return [{"emails_sent_count": 1, "reply_count": 0}]
        return {"status": 1, "name": "X"}

    monkeypatch.setattr(InstantlyLeser, "__init__", zaehlender_init)
    monkeypatch.setattr(InstantlyLeser, "_get", gefakter_get)
    monkeypatch.setenv("INSTANTLY_API_KEY", "fake-schluessel-nur-fuer-test")

    app = create_app(daten_dir)
    assert len(aufrufe) == 1  # eager beim App-Start gebaut

    client = TestClient(app)
    client.post("/login", data={"name": "Lena Hartmann", "passwort": "richtig123"})
    _lauf_anlegen(daten_dir, "demo-gmbh", "demo-gmbh.yaml", ts="20260720-090000",
                  zustand="uebergeben", campaign_id="camp-a")

    erste = client.get("/kampagnen/demo-gmbh/20260720-090000")
    zweite = client.get("/kampagnen/demo-gmbh/20260720-090000")
    assert erste.status_code == 200 and zweite.status_code == 200
    assert len(aufrufe) == 1  # immer noch nur EIN InstantlyLeser fuer beide Requests


# Baustein 1: Kampagne im Tool scharf schalten/pausieren ---------------------

def test_detail_zeigt_jetzt_verschicken_nur_wenn_bekannt_und_pausiert(angemeldeter_client, daten_dir):
    app = angemeldeter_client.app
    app.state.instantly_leser = FakeInstantlyLeser({
        "camp-a": _stand(status="pausiert"),
    })
    _lauf_anlegen(daten_dir, "demo-gmbh", "demo-gmbh.yaml", ts="20260720-090000",
                  zustand="uebergeben", campaign_id="camp-a")
    antwort = angemeldeter_client.get("/kampagnen/demo-gmbh/20260720-090000")
    assert antwort.status_code == 200
    assert "Jetzt verschicken" in antwort.text
    assert "Versand pausieren" not in antwort.text


def test_detail_zeigt_versand_pausieren_nur_wenn_aktiv(angemeldeter_client, daten_dir):
    app = angemeldeter_client.app
    app.state.instantly_leser = FakeInstantlyLeser({
        "camp-a": _stand(status="aktiv"),
    })
    _lauf_anlegen(daten_dir, "demo-gmbh", "demo-gmbh.yaml", ts="20260720-090000",
                  zustand="uebergeben", campaign_id="camp-a")
    antwort = angemeldeter_client.get("/kampagnen/demo-gmbh/20260720-090000")
    assert antwort.status_code == 200
    assert "Versand pausieren" in antwort.text
    assert "Jetzt verschicken" not in antwort.text


def test_detail_zeigt_keinen_aktions_knopf_bei_kontoproblem(angemeldeter_client, daten_dir):
    app = angemeldeter_client.app
    app.state.instantly_leser = FakeInstantlyLeser({
        "camp-a": _stand(status="kontoproblem"),
    })
    _lauf_anlegen(daten_dir, "demo-gmbh", "demo-gmbh.yaml", ts="20260720-090000",
                  zustand="uebergeben", campaign_id="camp-a")
    antwort = angemeldeter_client.get("/kampagnen/demo-gmbh/20260720-090000")
    assert antwort.status_code == 200
    assert "Jetzt verschicken" not in antwort.text
    assert "Versand pausieren" not in antwort.text


def test_detail_zeigt_keinen_aktions_knopf_ohne_versand_komplett(angemeldeter_client, daten_dir):
    # Lead-Import noch nicht abgeschlossen (nur "versand", kein
    # "versand_komplett") - kein "bekannt" im Sinne des Bausteins, deshalb
    # kein Scharf-schalten-Knopf, auch wenn Instantly schon "pausiert" meldet.
    app = angemeldeter_client.app
    app.state.instantly_leser = FakeInstantlyLeser({
        "camp-a": _stand(status="pausiert"),
    })
    _lauf_anlegen(daten_dir, "demo-gmbh", "demo-gmbh.yaml", ts="20260720-090000",
                  zustand="freigegeben_mit_versand", campaign_id="camp-a")
    antwort = angemeldeter_client.get("/kampagnen/demo-gmbh/20260720-090000")
    assert antwort.status_code == 200
    assert "Jetzt verschicken" not in antwort.text
    assert "Versand pausieren" not in antwort.text


def test_aktivieren_verlangt_anmeldung(client, daten_dir):
    _lauf_anlegen(daten_dir, "demo-gmbh", "demo-gmbh.yaml", ts="20260720-090000",
                  zustand="uebergeben", campaign_id="camp-a")
    antwort = client.post("/kampagnen/demo-gmbh/20260720-090000/aktivieren",
                           data={"bestaetigt": "ja"}, follow_redirects=False)
    assert antwort.status_code == 303
    assert antwort.headers["location"] == "/login"


def test_aktivieren_ohne_bestaetigung_ruft_instantly_nicht_auf(angemeldeter_client, daten_dir):
    app = angemeldeter_client.app
    fake = FakeInstantly()
    app.state.instantly = fake
    app.state.instantly_leser = FakeInstantlyLeser({"camp-a": _stand(status="pausiert")})
    _lauf_anlegen(daten_dir, "demo-gmbh", "demo-gmbh.yaml", ts="20260720-090000",
                  zustand="uebergeben", campaign_id="camp-a")
    antwort = angemeldeter_client.post("/kampagnen/demo-gmbh/20260720-090000/aktivieren")
    assert antwort.status_code in (200, 303)
    assert fake.aktiviert == []


def test_aktivieren_mit_bestaetigung_ruft_instantly_auf_und_schreibt_audit(
        angemeldeter_client, daten_dir):
    app = angemeldeter_client.app
    fake = FakeInstantly()
    app.state.instantly = fake
    app.state.instantly_leser = FakeInstantlyLeser({"camp-a": _stand(status="aktiv")})
    lauf_dir = _lauf_anlegen(daten_dir, "demo-gmbh", "demo-gmbh.yaml", ts="20260720-090000",
                              zustand="uebergeben", campaign_id="camp-a")
    antwort = angemeldeter_client.post(
        "/kampagnen/demo-gmbh/20260720-090000/aktivieren",
        data={"bestaetigt": "ja"}, follow_redirects=False)
    assert antwort.status_code == 303
    assert antwort.headers["location"] == "/kampagnen/demo-gmbh/20260720-090000"
    assert fake.aktiviert == ["camp-a"]
    audit = json.loads((lauf_dir / "aktiviert.json").read_text(encoding="utf-8"))
    assert audit["von"] == "Lena Hartmann"
    assert audit["am"]

    folge = angemeldeter_client.get("/kampagnen/demo-gmbh/20260720-090000")
    assert "Gestartet von Lena Hartmann am" in folge.text


def test_aktivieren_bei_instantly_fehler_zeigt_freundlichen_hinweis(angemeldeter_client, daten_dir):
    app = angemeldeter_client.app
    fake = FakeInstantly(fehler_bei="aktivieren")
    app.state.instantly = fake
    app.state.instantly_leser = FakeInstantlyLeser({"camp-a": _stand(status="pausiert")})
    _lauf_anlegen(daten_dir, "demo-gmbh", "demo-gmbh.yaml", ts="20260720-090000",
                  zustand="uebergeben", campaign_id="camp-a")
    antwort = angemeldeter_client.post(
        "/kampagnen/demo-gmbh/20260720-090000/aktivieren", data={"bestaetigt": "ja"})
    assert antwort.status_code == 200
    assert "nicht geantwortet" in antwort.text or "Instantly" in antwort.text


def test_aktivieren_unbekannter_lauf_404(angemeldeter_client, daten_dir):
    _lauf_anlegen(daten_dir, "demo-gmbh", "demo-gmbh.yaml", ts="20260720-090000",
                  zustand="wartet_auf_freigabe")
    antwort = angemeldeter_client.post(
        "/kampagnen/demo-gmbh/20260720-090000/aktivieren", data={"bestaetigt": "ja"})
    assert antwort.status_code == 404


def test_pausieren_verlangt_anmeldung(client, daten_dir):
    _lauf_anlegen(daten_dir, "demo-gmbh", "demo-gmbh.yaml", ts="20260720-090000",
                  zustand="uebergeben", campaign_id="camp-a")
    antwort = client.post("/kampagnen/demo-gmbh/20260720-090000/pausieren",
                           data={"bestaetigt": "ja"}, follow_redirects=False)
    assert antwort.status_code == 303
    assert antwort.headers["location"] == "/login"


def test_pausieren_ohne_bestaetigung_ruft_instantly_nicht_auf(angemeldeter_client, daten_dir):
    app = angemeldeter_client.app
    fake = FakeInstantly()
    app.state.instantly = fake
    app.state.instantly_leser = FakeInstantlyLeser({"camp-a": _stand(status="aktiv")})
    _lauf_anlegen(daten_dir, "demo-gmbh", "demo-gmbh.yaml", ts="20260720-090000",
                  zustand="uebergeben", campaign_id="camp-a")
    antwort = angemeldeter_client.post("/kampagnen/demo-gmbh/20260720-090000/pausieren")
    assert antwort.status_code in (200, 303)
    assert fake.pausiert == []


def test_pausieren_mit_bestaetigung_ruft_instantly_auf(angemeldeter_client, daten_dir):
    app = angemeldeter_client.app
    fake = FakeInstantly()
    app.state.instantly = fake
    app.state.instantly_leser = FakeInstantlyLeser({"camp-a": _stand(status="aktiv")})
    _lauf_anlegen(daten_dir, "demo-gmbh", "demo-gmbh.yaml", ts="20260720-090000",
                  zustand="uebergeben", campaign_id="camp-a")
    antwort = angemeldeter_client.post(
        "/kampagnen/demo-gmbh/20260720-090000/pausieren",
        data={"bestaetigt": "ja"}, follow_redirects=False)
    assert antwort.status_code == 303
    assert antwort.headers["location"] == "/kampagnen/demo-gmbh/20260720-090000"
    assert fake.pausiert == ["camp-a"]


def test_pausieren_bei_instantly_fehler_zeigt_freundlichen_hinweis(angemeldeter_client, daten_dir):
    app = angemeldeter_client.app
    fake = FakeInstantly(fehler_bei="pausieren")
    app.state.instantly = fake
    app.state.instantly_leser = FakeInstantlyLeser({"camp-a": _stand(status="aktiv")})
    _lauf_anlegen(daten_dir, "demo-gmbh", "demo-gmbh.yaml", ts="20260720-090000",
                  zustand="uebergeben", campaign_id="camp-a")
    antwort = angemeldeter_client.post(
        "/kampagnen/demo-gmbh/20260720-090000/pausieren", data={"bestaetigt": "ja"})
    assert antwort.status_code == 200
    assert "nicht geantwortet" in antwort.text or "Instantly" in antwort.text


def test_pausieren_unbekannter_lauf_404(angemeldeter_client, daten_dir):
    _lauf_anlegen(daten_dir, "demo-gmbh", "demo-gmbh.yaml", ts="20260720-090000",
                  zustand="wartet_auf_freigabe")
    antwort = angemeldeter_client.post(
        "/kampagnen/demo-gmbh/20260720-090000/pausieren", data={"bestaetigt": "ja"})
    assert antwort.status_code == 404
