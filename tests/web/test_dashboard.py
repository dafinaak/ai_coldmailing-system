"""Tests fuer das Dashboard (Task 7): die Startseite ('/'). Baut auf
denselben Fixtures/Mustern wie tests/web/test_kampagnen.py (_lauf_anlegen,
FakeInstantlyLeser ueber app.state.instantly_leser) - das Dashboard ruft
dieselbe Aggregation (web.routen.kampagnen._alle_laeufe) und denselben
Live-Stand-Abruf auf wie der Kampagnen-Bereich, plus web.wartende fuer die
wartenden Freigaben."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient
from passlib.context import CryptContext

from pipeline.approval import approve
from pipeline.run_store import RunStore
from web.app import create_app

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


class FakeInstantlyLeser:
    """Gleiches Muster wie tests/web/test_kampagnen.py. Baustein 2:
    zusaetzlich postfaecher() (das Dashboard ruft es jetzt IMMER ab, siehe
    web.routen.dashboard._postfach_probleme) - `postfaecher_liste` ist per
    Default leer (kein Postfach-Problem), Tests fuer die Dashboard-Zeile
    setzen es explizit."""

    def __init__(self, antworten: dict, postfaecher_liste: list[dict] | None = None):
        self.antworten = antworten
        self.angefragt: list[str] = []
        self.aufrufe = 0
        self.postfaecher_aufrufe = 0
        self._postfaecher_liste = postfaecher_liste or []

    def kampagnen_stand(self, campaign_ids):
        self.aufrufe += 1
        self.angefragt = list(campaign_ids)
        return {cid: self.antworten.get(cid, {
            "erreichbar": False, "status": None, "name": None,
            "versendet": None, "antworten": None, "schritte": [], "stand": None,
        }) for cid in campaign_ids}

    def postfaecher(self):
        self.postfaecher_aufrufe += 1
        return {"postfaecher": self._postfaecher_liste, "erreichbar": True,
                "stand": datetime(2026, 7, 20, 9, 30)}


def _stand(status="aktiv", name="[TEST] Demo GmbH", versendet=3, antworten=1,
           schritte=None, erreichbar=True, stand=None):
    return {
        "erreichbar": erreichbar, "status": status, "name": name,
        "versendet": versendet, "antworten": antworten,
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
    app = create_app(daten_dir)
    # Baustein 2: Default-Fake, damit Tests, die app.state.instantly_leser
    # nicht selbst setzen, trotzdem funktionieren (siehe FakeInstantlyLeser.
    # postfaecher() oben - das Dashboard ruft es jetzt IMMER ab). Tests, die
    # ihn brauchen, ueberschreiben ihn wie bisher selbst.
    app.state.instantly_leser = FakeInstantlyLeser({})
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def angemeldeter_client(client):
    client.post("/login", data={"name": "Lena Hartmann", "passwort": "richtig123"})
    # Copy-Rework (20.07.2026): ohne das Cookie leitet '/' zur Einstiegsseite
    # "So funktioniert's" um (siehe web.routen.dashboard/web.routen.intro) -
    # fuer Tests, die das NICHT selbst pruefen, hier wie ein wiederkehrender
    # Nutzer simuliert.
    client.cookies.set("intro_gesehen", "1")
    return client


def _lauf_anlegen(daten_dir: Path, slug: str, kunde_datei: str, *, ts: str,
                   zustand: str = "uebergeben", campaign_id: str | None = "camp-1") -> Path:
    """Identisches Muster wie tests/web/test_kampagnen.py._lauf_anlegen."""
    lauf_dir = daten_dir / "laeufe" / slug / ts
    lauf_dir.mkdir(parents=True)
    store = RunStore.resume(lauf_dir)
    store.save_step("kunde_pfad", {"pfad": f"kunden/{kunde_datei}"})

    if zustand == "laeuft_platzhalter":
        return lauf_dir

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

    store.save_step("versand", {"campaign_id": campaign_id})
    store.save_step("versand_komplett", {"campaign_id": campaign_id})
    return lauf_dir


# Anmeldung ------------------------------------------------------------

def test_root_verlangt_anmeldung(client):
    antwort = client.get("/", follow_redirects=False)
    assert antwort.status_code == 303
    assert antwort.headers["location"] == "/login"


def test_root_zeigt_dashboard_kein_platzhalter(angemeldeter_client):
    antwort = angemeldeter_client.get("/")
    assert antwort.status_code == 200
    assert "Dashboard" in antwort.text
    assert "Hier siehst du auf einen Blick, was läuft und was auf dich wartet." in antwort.text
    # Kein Platzhalter-Text mehr:
    assert "noch nicht gebaut" not in antwort.text.lower()


# Kacheln ----------------------------------------------------------------

def test_kacheln_zeigen_korrekte_zahlen(angemeldeter_client, daten_dir):
    app = angemeldeter_client.app
    app.state.instantly_leser = FakeInstantlyLeser({
        "camp-a": _stand(status="aktiv", versendet=5, antworten=2),
        "camp-b": _stand(status="pausiert", versendet=1, antworten=0),
    })
    _lauf_anlegen(daten_dir, "demo-gmbh", "demo-gmbh.yaml", ts="20260720-090000",
                  zustand="uebergeben", campaign_id="camp-a")
    _lauf_anlegen(daten_dir, "moveo", "moveo.yaml", ts="20260720-091500",
                  zustand="uebergeben", campaign_id="camp-b")
    _lauf_anlegen(daten_dir, "demo-gmbh", "demo-gmbh.yaml", ts="20260720-100000",
                  zustand="wartet_auf_freigabe")

    antwort = angemeldeter_client.get("/")
    assert antwort.status_code == 200
    text = antwort.text
    assert "Warten auf deine Freigabe" in text
    assert "Aktive Kampagnen" in text
    assert "Heute versendet" in text
    assert "Neue Antworten" in text
    # 1 wartender Lauf, 1 aktive Kampagne (camp-a):
    assert ">1<" in text  # wartend
    assert (
        '<div class="dash-kachel-wert">1</div>\n'
        '      <div class="dash-kachel-label">Aktive Kampagnen</div>'
    ) in text


def test_kachel_wartende_freigabe_verlinkt_pruefen(angemeldeter_client, daten_dir):
    _lauf_anlegen(daten_dir, "demo-gmbh", "demo-gmbh.yaml", ts="20260720-090000",
                  zustand="wartet_auf_freigabe")
    antwort = angemeldeter_client.get("/")
    assert antwort.status_code == 200
    assert 'href="/pruefen"' in antwort.text


def test_kachel_heute_versendet_zeigt_platzhalter_ohne_erfundenen_wert(angemeldeter_client):
    # Die Instantly-API liefert (Stand Task 6) keinen "heute versendet"-
    # Zaehler - die Kachel darf keinen erfundenen Wert zeigen.
    antwort = angemeldeter_client.get("/")
    assert antwort.status_code == 200
    assert "Heute versendet" in antwort.text
    assert (
        '<div class="dash-kachel-wert">–</div>\n'
        '      <div class="dash-kachel-label">Heute versendet</div>'
    ) in antwort.text


def test_kachel_neue_antworten_zeigt_platzhalter_statt_lifetime_zaehler(angemeldeter_client, daten_dir):
    # Reviewer-Fix 1: InstantlyLeser.kampagnen_stand()["antworten"] ist der
    # LIFETIME-reply_count der Kampagne, nicht "neu" - selbst wenn die API
    # einen Wert liefert, darf die Kachel ihn nicht als "neu" ausgeben.
    app = angemeldeter_client.app
    app.state.instantly_leser = FakeInstantlyLeser({
        "camp-a": _stand(status="aktiv", antworten=7),
    })
    _lauf_anlegen(daten_dir, "demo-gmbh", "demo-gmbh.yaml", ts="20260720-090000",
                  zustand="uebergeben", campaign_id="camp-a")

    antwort = angemeldeter_client.get("/")
    assert antwort.status_code == 200
    text = antwort.text
    assert (
        '<div class="dash-kachel-wert">–</div>\n'
        '      <div class="dash-kachel-label">Neue Antworten</div>'
    ) in text


# WARTET AUF DEINE FREIGABE -----------------------------------------------

def test_wartende_liste_mit_jetzt_pruefen_knopf(angemeldeter_client, daten_dir):
    _lauf_anlegen(daten_dir, "demo-gmbh", "demo-gmbh.yaml", ts="20260720-090000",
                  zustand="wartet_auf_freigabe")
    antwort = angemeldeter_client.get("/")
    assert antwort.status_code == 200
    text = antwort.text
    assert "BITTE LESEN UND FREIGEBEN" in text
    assert "E-Mail-Runde für Demo GmbH · 1 Empfänger" in text
    assert "Jetzt lesen" in text
    assert "/pruefen/demo-gmbh/20260720-090000" in text


def test_wartende_liste_leer_wird_nicht_angezeigt(angemeldeter_client):
    antwort = angemeldeter_client.get("/")
    assert antwort.status_code == 200
    assert "BITTE LESEN UND FREIGEBEN" not in antwort.text


# Angehalten-Banner --------------------------------------------------------

def test_angehalten_banner_erscheint_mit_fortsetzen_link(angemeldeter_client, daten_dir):
    _lauf_anlegen(daten_dir, "moveo", "moveo.yaml", ts="20260720-091500",
                  zustand="angehalten")
    antwort = angemeldeter_client.get("/")
    assert antwort.status_code == 200
    text = antwort.text
    assert "Angehalten" in text
    assert "MOVEO Personalberatung" in text
    assert "/auftraege/moveo/20260720-091500" in text
    assert "Fortsetzen" in text


def test_angehalten_banner_fehlt_ohne_angehaltenen_lauf(angemeldeter_client, daten_dir):
    _lauf_anlegen(daten_dir, "demo-gmbh", "demo-gmbh.yaml", ts="20260720-090000",
                  zustand="wartet_auf_freigabe")
    antwort = angemeldeter_client.get("/")
    assert antwort.status_code == 200
    assert "Angehalten:" not in antwort.text


# Konto-Problem-Zeile --------------------------------------------------------

def test_kontoproblem_kampagne_erscheint_als_laute_zeile(angemeldeter_client, daten_dir):
    app = angemeldeter_client.app
    app.state.instantly_leser = FakeInstantlyLeser({
        "camp-a": _stand(status="kontoproblem", name="[TEST] Demo GmbH"),
    })
    _lauf_anlegen(daten_dir, "demo-gmbh", "demo-gmbh.yaml", ts="20260720-090000",
                  zustand="uebergeben", campaign_id="camp-a")
    antwort = angemeldeter_client.get("/")
    assert antwort.status_code == 200
    text = antwort.text
    assert "Konto-Problem" in text
    assert "[TEST] Demo GmbH" in text
    assert "/kampagnen/demo-gmbh/20260720-090000" in text


def test_ohne_kontoproblem_keine_laute_zeile(angemeldeter_client, daten_dir):
    app = angemeldeter_client.app
    app.state.instantly_leser = FakeInstantlyLeser({
        "camp-a": _stand(status="aktiv"),
    })
    _lauf_anlegen(daten_dir, "demo-gmbh", "demo-gmbh.yaml", ts="20260720-090000",
                  zustand="uebergeben", campaign_id="camp-a")
    antwort = angemeldeter_client.get("/")
    assert antwort.status_code == 200
    assert "Konto-Problem" not in antwort.text


# Postfach-Problem-Zeile (Baustein 2) -----------------------------------------

def test_postfach_problem_erscheint_als_laute_zeile(angemeldeter_client):
    app = angemeldeter_client.app
    app.state.instantly_leser = FakeInstantlyLeser({}, postfaecher_liste=[
        {"email": "kaputt@firma.de", "status": "verbindungsfehler", "warmup": "aus",
         "daily_limit": None},
    ])
    antwort = angemeldeter_client.get("/")
    assert antwort.status_code == 200
    text = antwort.text
    assert "Postfach-Problem bei" in text
    assert "kaputt@firma.de" in text
    assert 'href="/postfaecher"' in text


def test_ohne_postfach_problem_keine_laute_zeile(angemeldeter_client):
    app = angemeldeter_client.app
    app.state.instantly_leser = FakeInstantlyLeser({}, postfaecher_liste=[
        {"email": "gesund@firma.de", "status": "verbunden", "warmup": "an", "daily_limit": 100},
    ])
    antwort = angemeldeter_client.get("/")
    assert antwort.status_code == 200
    assert "Postfach-Problem bei" not in antwort.text


def test_dashboard_ohne_instantly_key_und_ohne_kampagnen_stuerzt_nicht_ab(
        angemeldeter_client, monkeypatch):
    # Regression (Review-Fund): das Dashboard ruft _postfach_probleme() JETZT
    # IMMER auf, unabhaengig von lokalen Kampagnen (anders als der
    # Kampagnen-Pfad, der bei mit_kampagne == [] den Leser gar nicht erst
    # anfasst). Ohne INSTANTLY_API_KEY UND ohne app.state.instantly_leser
    # (kein Fake injiziert - simuliert einen App-Start ohne Schluessel)
    # wirft web.instantly_leser.geteilten_leser() ein KeyError beim Bauen
    # des Lesers, BEVOR InstantlyLeser.postfaecher() seine eigene
    # Fehlertoleranz greifen lassen kann - das darf die Seite nicht mit
    # einem 500er abschiessen, sondern muss genauso degradieren wie ein
    # erreichbarer, aber fehlgeschlagener Abruf (Zeile einfach abwesend).
    monkeypatch.delenv("INSTANTLY_API_KEY", raising=False)
    app = angemeldeter_client.app
    app.state.instantly_leser = None
    antwort = angemeldeter_client.get("/")
    assert antwort.status_code == 200
    assert "Dashboard" in antwort.text
    assert "Postfach-Problem bei" not in antwort.text


# Kampagnen-Kurzliste --------------------------------------------------------

def test_kampagnen_kurzliste_mit_link_zu_allen_kampagnen(angemeldeter_client, daten_dir):
    app = angemeldeter_client.app
    app.state.instantly_leser = FakeInstantlyLeser({
        "camp-a": _stand(status="aktiv", name="[TEST] Demo GmbH", versendet=5),
    })
    _lauf_anlegen(daten_dir, "demo-gmbh", "demo-gmbh.yaml", ts="20260720-090000",
                  zustand="uebergeben", campaign_id="camp-a")
    antwort = angemeldeter_client.get("/")
    assert antwort.status_code == 200
    text = antwort.text
    assert "KAMPAGNEN" in text
    assert "[TEST] Demo GmbH" in text
    assert "Alle Kampagnen ansehen" in text
    assert 'href="/kampagnen"' in text
    assert "/kampagnen/demo-gmbh/20260720-090000" in text


def test_kampagnen_kurzliste_leer_zeigt_hinweis(angemeldeter_client):
    antwort = angemeldeter_client.get("/")
    assert antwort.status_code == 200
    assert "Noch keine Kampagne" in antwort.text


# API-Ausfall ----------------------------------------------------------------

def test_api_ausfall_zeigt_platzhalter_ohne_absturz(angemeldeter_client, daten_dir):
    class KaputterLeser:
        def __init__(self):
            self.aufrufe = 0

        def kampagnen_stand(self, campaign_ids):
            self.aufrufe += 1
            return {cid: {"erreichbar": False, "status": None, "name": None,
                          "versendet": None, "antworten": None, "schritte": [],
                          "stand": None} for cid in campaign_ids}

        def postfaecher(self):
            return {"postfaecher": [], "erreichbar": False, "stand": None}

    app = angemeldeter_client.app
    leser = KaputterLeser()
    app.state.instantly_leser = leser
    _lauf_anlegen(daten_dir, "demo-gmbh", "demo-gmbh.yaml", ts="20260720-090000",
                  zustand="uebergeben", campaign_id="camp-a")

    antwort = angemeldeter_client.get("/")
    assert antwort.status_code == 200
    assert "Live-Stand gerade nicht erreichbar" in antwort.text
    assert ">–<" in antwort.text or "–" in antwort.text
    # Nur EIN gemeinsamer Abruf fuer die ganze Seite (Kacheln + Liste),
    # nicht einer je Kachel/Abschnitt:
    assert leser.aufrufe == 1


def test_api_ausfall_mit_cache_zeigt_stand_von_zeit(angemeldeter_client, daten_dir):
    app = angemeldeter_client.app
    app.state.instantly_leser = FakeInstantlyLeser({
        "camp-a": {"erreichbar": False, "status": None, "name": None,
                   "versendet": None, "antworten": None, "schritte": [],
                   "stand": datetime(2026, 7, 20, 8, 45)},
    })
    _lauf_anlegen(daten_dir, "demo-gmbh", "demo-gmbh.yaml", ts="20260720-090000",
                  zustand="uebergeben", campaign_id="camp-a")
    antwort = angemeldeter_client.get("/")
    assert antwort.status_code == 200
    assert "08:45" in antwort.text


# Sidebar-Badge --------------------------------------------------------------

def test_badge_zeigt_wartende_anzahl_auf_anderer_seite(angemeldeter_client, daten_dir):
    _lauf_anlegen(daten_dir, "demo-gmbh", "demo-gmbh.yaml", ts="20260720-090000",
                  zustand="wartet_auf_freigabe")
    _lauf_anlegen(daten_dir, "moveo", "moveo.yaml", ts="20260720-091500",
                  zustand="wartet_auf_freigabe")

    antwort = angemeldeter_client.get("/kunden")
    assert antwort.status_code == 200
    assert "nav-badge" in antwort.text
    assert ">2<" in antwort.text


def test_badge_fehlt_ohne_wartende_laeufe(angemeldeter_client):
    antwort = angemeldeter_client.get("/kunden")
    assert antwort.status_code == 200
    assert "nav-badge" not in antwort.text


def test_badge_erscheint_auch_auf_dem_dashboard_selbst(angemeldeter_client, daten_dir):
    _lauf_anlegen(daten_dir, "demo-gmbh", "demo-gmbh.yaml", ts="20260720-090000",
                  zustand="wartet_auf_freigabe")
    antwort = angemeldeter_client.get("/")
    assert antwort.status_code == 200
    assert "nav-badge" in antwort.text
    assert ">1<" in antwort.text
