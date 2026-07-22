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
from zoneinfo import ZoneInfo

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

    def __init__(self, antworten: dict, postfach_antwort: dict | None = None):
        self.antworten = antworten
        self.angefragt: list[str] = []
        self.postfach_antwort = postfach_antwort

    def kampagnen_stand(self, campaign_ids):
        self.angefragt = list(campaign_ids)
        return {cid: self.antworten.get(cid, {
            "erreichbar": False, "status": None, "name": None,
            "versendet": None, "antworten": None, "schritte": [], "stand": None,
        }) for cid in campaign_ids}

    def postfaecher(self):
        return self.postfach_antwort or {
            "erreichbar": True,
            "stand": datetime(2026, 7, 22, 10, 30),
            "postfaecher": [{
                "email": "sender@firma.de", "status": "verbunden",
                "warmup": "an", "daily_limit": 20,
            }],
        }


def _stand(status="pausiert", name="[TEST] Demo GmbH", versendet=3, antworten=1,
           schritte=None, erreichbar=True, stand=None, empfaenger=12):
    return {
        "erreichbar": erreichbar, "status": status, "name": name,
        "versendet": versendet, "antworten": antworten,
        "empfaenger": empfaenger, "geoeffnet": 4, "unzustellbar": 1,
        "abgeschlossen": 3, "heute_versendet": 7,
        "erstellt_am": "2026-07-18T14:05:00+00:00",
        "absender": ["sender@firma.de"],
        "sendefenster": [{
            "name": "Werktage", "von": "08:00", "bis": "19:00",
            "tage": {"0": False, "1": True, "2": True, "3": True,
                     "4": True, "5": True, "6": False},
            "zeitzone": "Europe/Berlin",
        }],
        "schritte": schritte if schritte is not None else [
            {"schritt": 1, "versendet": versendet, "geoeffnet": 2}],
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

    texte = [
        {**_TEXT, "email": f"test-{nummer:02d}@example.test"}
        for nummer in range(1, 13)
    ]
    store.save_step("personalisierung", {"fertig": texte, "nacharbeit": []})
    store.save_step("pruefung_ok", texte)
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
        "empfaenger": 24,
        "geoeffnet": 8,
        "versendet": 6,
        "antworten": 2,
        "fehlgeschlagen": None,
        "unzustellbar": 2,
    }
    assert [zeile["name"] for zeile in antwort.context["kampagnen"]] == ["Aktive Runde"]
    assert antwort.context["status_filter"] == "aktiv"


def test_liste_zeigt_aktive_kampagnen_bei_vollstaendigem_live_ausfall_unbekannt(
        angemeldeter_client, daten_dir):
    angemeldeter_client.app.state.instantly_leser = FakeInstantlyLeser({})
    _lauf_anlegen(daten_dir, "demo-gmbh", "demo-gmbh.yaml",
                  ts="20260720-090000", campaign_id="camp-a")

    antwort = angemeldeter_client.get("/kampagnen")

    assert antwort.context["kennzahlen"]["aktiv"] is None
    assert re.search(
        r"<strong>—</strong><span>Aktive Kampagnen</span>", antwort.text,
    )


def test_liste_zeigt_aktive_kampagnen_bei_teilweisem_live_ausfall_unbekannt(
        angemeldeter_client, daten_dir):
    angemeldeter_client.app.state.instantly_leser = FakeInstantlyLeser({
        "camp-a": _stand(status="aktiv", name="Aktive Runde"),
    })
    _lauf_anlegen(daten_dir, "demo-gmbh", "demo-gmbh.yaml",
                  ts="20260720-090000", campaign_id="camp-a")
    _lauf_anlegen(daten_dir, "moveo", "moveo.yaml",
                  ts="20260720-091500", campaign_id="camp-b")

    antwort = angemeldeter_client.get("/kampagnen")

    assert antwort.context["kennzahlen"]["aktiv"] is None
    assert re.search(
        r"<strong>—</strong><span>Aktive Kampagnen</span>", antwort.text,
    )


def test_liste_rendert_wholix_uebersicht_mit_filtern_und_vorbereitung(
        angemeldeter_client, daten_dir):
    stand = _stand(status="aktiv", name="Demo Kampagne", antworten=0)
    stand["unzustellbar"] = None
    angemeldeter_client.app.state.instantly_leser = FakeInstantlyLeser({
        "camp-a": stand,
    })
    _lauf_anlegen(daten_dir, "demo-gmbh", "demo-gmbh.yaml",
                  ts="20260720-090000", campaign_id="camp-a")
    _lauf_anlegen(daten_dir, "moveo", "moveo.yaml",
                  ts="20260720-091500", zustand="wartet_auf_freigabe",
                  campaign_id=None)

    antwort = angemeldeter_client.get("/kampagnen?suche=demo&status=aktiv")

    assert antwort.status_code == 200
    text = antwort.text
    karten = re.search(
        r'<section class="wholix-karten"[^>]*>(.*?)</section>', text, re.S,
    )
    assert karten is not None
    for bezeichnung in (
        "Kampagnen", "Aktive Kampagnen", "Empfänger", "Geöffnet",
        "Versendet", "Antworten", "Fehlgeschlagen", "Unzustellbar",
    ):
        assert f"<span>{bezeichnung}</span>" in karten.group(1)
    assert "<strong>0</strong><span>Antworten</span>" in karten.group(1)
    assert "<strong>—</strong><span>Unzustellbar</span>" in karten.group(1)
    assert 'name="suche" value="demo"' in text
    assert re.search(r'<option value="aktiv" selected>Aktiv</option>', text)
    for spalte in (
        "KAMPAGNE", "ANGEBOT", "STATUS", "EMPFÄNGER", "GEÖFFNET",
        "VERSENDET", "ANTWORTEN", "UNZUSTELLBAR",
    ):
        assert f">{spalte}<" in text
    assert "IN VORBEREITUNG" in text
    assert "MOVEO Personalberatung" in text


def test_liste_behaelt_kampagnenzeile_als_nativen_link(
        angemeldeter_client, daten_dir):
    angemeldeter_client.app.state.instantly_leser = FakeInstantlyLeser({
        "camp-a": _stand(status="aktiv", name="Demo Kampagne"),
    })
    _lauf_anlegen(daten_dir, "demo-gmbh", "demo-gmbh.yaml",
                  ts="20260720-090000", campaign_id="camp-a")

    antwort = angemeldeter_client.get("/kampagnen")

    link = re.search(r'<a href="/kampagnen/[^\"]+" class="kamp-detail-link"[^>]*>',
                     antwort.text)
    assert link is not None
    assert "role=" not in link.group(0)


def test_liste_rendert_eine_semantische_tabelle_mit_spaltenkoepfen(
        angemeldeter_client, daten_dir):
    angemeldeter_client.app.state.instantly_leser = FakeInstantlyLeser({
        "camp-a": _stand(status="aktiv", name="Demo Kampagne"),
    })
    _lauf_anlegen(daten_dir, "demo-gmbh", "demo-gmbh.yaml",
                  ts="20260720-090000", campaign_id="camp-a")

    antwort = angemeldeter_client.get("/kampagnen")
    tabelle = re.search(r'<table class="kamp-tabelle[^"]*">(.*?)</table>',
                        antwort.text, re.S)

    assert tabelle is not None
    assert "<thead>" in tabelle.group(1)
    assert "<tbody>" in tabelle.group(1)
    assert tabelle.group(1).count('scope="col"') == 9
    assert "<th " in tabelle.group(1)
    assert "<td " in tabelle.group(1)
    assert re.search(
        r'<td class="kamp-name">\s*<a href="/kampagnen/demo-gmbh/20260720-090000"',
        tabelle.group(1), re.S,
    )


def test_kampagnen_mindestbreite_ist_auf_wholix_rahmen_begrenzt():
    css_pfad = Path(__file__).parents[2] / "web" / "static" / "stil.css"
    css = css_pfad.read_text(encoding="utf-8")
    allgemeine_tabelle = re.search(r"^\.kamp-tabelle\s*\{([^}]*)\}", css, re.M | re.S)
    wholix_tabelle = re.search(
        r"^\.kamp-tabellenrahmen > \.kamp-tabelle\s*\{([^}]*)\}",
        css, re.M | re.S,
    )

    assert allgemeine_tabelle is not None
    assert "min-width" not in allgemeine_tabelle.group(1)
    assert "background: var(--farbe-weiss)" in allgemeine_tabelle.group(1)
    assert "border: 1px solid var(--farbe-rand)" in allgemeine_tabelle.group(1)
    assert "border-radius: 12px" in allgemeine_tabelle.group(1)
    assert "overflow: hidden" in allgemeine_tabelle.group(1)
    assert wholix_tabelle is not None
    assert "min-width: 1180px" in wholix_tabelle.group(1)


def test_kampagnenzeilen_fokus_liegt_innerhalb_der_abgeschnittenen_tabelle():
    css_pfad = Path(__file__).parents[2] / "web" / "static" / "stil.css"
    css = css_pfad.read_text(encoding="utf-8")
    zeilen_fokus = re.search(
        r"^\.kamp-detail-link:focus-visible\s*\{([^}]*)\}", css, re.M | re.S,
    )

    assert zeilen_fokus is not None
    assert "outline-offset: -2px" in zeilen_fokus.group(1)


def test_kennzahlenfarben_haben_auf_weiss_mindestens_drei_zu_eins_kontrast():
    css = (Path(__file__).parents[2] / "web" / "static" / "stil.css").read_text(
        encoding="utf-8",
    )

    def helligkeit(hex_farbe: str) -> float:
        werte = [int(hex_farbe[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        linear = [wert / 12.92 if wert <= .04045 else ((wert + .055) / 1.055) ** 2.4
                  for wert in werte]
        return .2126 * linear[0] + .7152 * linear[1] + .0722 * linear[2]

    def kontrast_zu_weiss(selector: str) -> float:
        regel = re.search(rf"^{re.escape(selector)}\s*\{{([^}}]*)\}}", css, re.M | re.S)
        assert regel is not None, selector
        farbe = re.search(r"color:\s*(#[0-9A-Fa-f]{6})", regel.group(1))
        assert farbe is not None, selector
        return 1.05 / (helligkeit(farbe.group(1)) + .05)

    for selector in (
        ".wholix-karte--gruen strong",
        ".wholix-karte--mint strong",
        ".wholix-karte--orange strong",
        ".kamp-metrik--gruen strong",
        ".kamp-metrik--orange strong",
        ".kamp-metrik--gelb strong",
    ):
        assert kontrast_zu_weiss(selector) >= 3, selector


def test_fehlgeschlagen_erklaerung_ist_ohne_maus_sichtbar_und_verknuepft(
        angemeldeter_client):
    antwort = angemeldeter_client.get("/kampagnen")

    assert 'aria-describedby="kamp-fehlgeschlagen-erklaerung"' in antwort.text
    assert ('id="kamp-fehlgeschlagen-erklaerung">'
            'Instantly liefert keinen verlässlichen Zähler</small>') in antwort.text
    assert 'title="Instantly liefert keinen verlässlichen Zähler"' not in antwort.text


def test_mobile_kampagnenuebersicht_nutzt_volle_breite_und_lokalen_tabellenscroll():
    basis = Path(__file__).parents[2]
    css = (basis / "web" / "static" / "stil.css").read_text(encoding="utf-8")
    vorlage = (basis / "web" / "templates" / "kampagnen_liste.html").read_text(
        encoding="utf-8",
    )
    mobile_start = css.index("@media (max-width: 820px)")
    mobile_ende = css.index("@media (max-width: 760px)", mobile_start)
    mobile_css = css[mobile_start:mobile_ende]

    def regel(selector: str) -> str:
        treffer = re.search(
            rf"^\s*{re.escape(selector)}\s*\{{([^}}]*)\}}",
            mobile_css, re.M | re.S,
        )
        assert treffer is not None, selector
        return treffer.group(1)

    assert "flex-direction: column" in regel(
        ".rahmen:has(.kamp-uebersicht-seite)",
    )
    seitenleiste = regel(
        ".rahmen:has(.kamp-uebersicht-seite) .seitenleiste",
    )
    assert "width: 100%" in seitenleiste
    assert "flex-direction: row" in seitenleiste
    navigation = regel(".rahmen:has(.kamp-uebersicht-seite) .nav")
    assert "flex-direction: row" in navigation
    assert "overflow-x: auto" in navigation
    inhalt = regel(".rahmen:has(.kamp-uebersicht-seite) .inhalt")
    assert "width: 100%" in inhalt
    assert "min-width: 0" in inhalt
    assert "overflow-x: hidden" in inhalt
    seite = regel(".kamp-uebersicht-seite")
    assert "width: 100%" in seite
    assert "min-width: 0" in seite
    tabellenrahmen = regel(".kamp-uebersicht-seite .kamp-tabellenrahmen")
    assert "width: 100%" in tabellenrahmen
    assert "max-width: 100%" in tabellenrahmen
    assert 'class="seite seite--breit kamp-uebersicht-seite"' in vorlage


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
    assert "3 versendet · — geöffnet" in text
    assert "app.instantly.ai/app/campaign/camp-a" in text


def test_detail_zeigt_warteschlange_sendefenster_und_tageslimit(angemeldeter_client, daten_dir):
    app = angemeldeter_client.app
    app.state.instantly_leser = FakeInstantlyLeser({
        "camp-1": _stand(status="aktiv"),
    })
    app.state.jetzt = lambda: datetime(2026, 7, 22, 10, 30, tzinfo=ZoneInfo("Europe/Berlin"))
    _lauf_anlegen(daten_dir, "demo-gmbh", "demo-gmbh.yaml",
                  ts="20260720-093000", campaign_id="camp-1")

    antwort = angemeldeter_client.get("/kampagnen/demo-gmbh/20260720-093000")
    assert antwort.context["kd_warteschlange"] == {
        "gesamt": 36, "versendet": 3, "unzustellbar": 1, "ungetrennt": 33,
    }
    assert antwort.context["kd_kennzahlen"]["moeglich"] == 36
    assert antwort.context["kd_tageslimit"] == {"heute": 7, "limit": 20}
    assert antwort.context["kd_sendefenster"] == [{
        "tage_text": "Mo–Fr", "zeit_text": "08:00–19:00",
        "zeitzone": "Europe/Berlin", "ist_jetzt": True,
    }]
    assert antwort.context["kd_absender"] == ["sender@firma.de"]
    assert "sender@firma.de" in antwort.text

    app.state.jetzt = lambda: datetime(2026, 7, 26, 10, 30, tzinfo=ZoneInfo("Europe/Berlin"))
    sonntag = angemeldeter_client.get("/kampagnen/demo-gmbh/20260720-093000")
    assert sonntag.context["kd_sendefenster"][0]["ist_jetzt"] is False


def test_liste_und_detail_nutzen_live_empfaenger_und_zeigen_lokalen_wert_getrennt(
        angemeldeter_client, daten_dir):
    angemeldeter_client.app.state.instantly_leser = FakeInstantlyLeser({
        "camp-a": _stand(status="aktiv", empfaenger=7, versendet=3),
    })
    _lauf_anlegen(daten_dir, "demo-gmbh", "demo-gmbh.yaml",
                  ts="20260720-090000", campaign_id="camp-a")

    liste = angemeldeter_client.get("/kampagnen")
    detail = angemeldeter_client.get("/kampagnen/demo-gmbh/20260720-090000")

    assert liste.context["kennzahlen"]["empfaenger"] == 7
    assert liste.context["kampagnen"][0]["empfaenger"] == 7
    assert detail.context["kd_kennzahlen"]["empfaenger"] == 7
    assert detail.context["kd_kennzahlen"]["moeglich"] == 21
    assert detail.context["kd_warteschlange"]["gesamt"] == 21
    assert detail.context["kd_gesamt"] == 12
    assert re.search(
        r"<dt>Empfänger im freigegebenen Lauf</dt>\s*<dd>12</dd>",
        detail.text,
    )


def test_unbekannte_live_empfaenger_machen_abhaengige_werte_unbekannt(
        angemeldeter_client, daten_dir):
    stand = _stand(status="aktiv", empfaenger=None)
    angemeldeter_client.app.state.instantly_leser = FakeInstantlyLeser({"camp-a": stand})
    _lauf_anlegen(daten_dir, "demo-gmbh", "demo-gmbh.yaml",
                  ts="20260720-090000", campaign_id="camp-a")

    liste = angemeldeter_client.get("/kampagnen")
    detail = angemeldeter_client.get("/kampagnen/demo-gmbh/20260720-090000")

    assert liste.context["kennzahlen"]["empfaenger"] is None
    assert detail.context["kd_kennzahlen"]["moeglich"] is None
    assert detail.context["kd_warteschlange"]["gesamt"] is None
    assert detail.context["kd_warteschlange"]["ungetrennt"] is None


def test_detail_nutzt_letzten_postfachstand_und_zeigt_dessen_ausfallzeit(
        angemeldeter_client, daten_dir):
    postfach_antwort = {
        "erreichbar": False,
        "stand": datetime(2026, 7, 22, 8, 15),
        "postfaecher": [{
            "email": "sender@firma.de", "status": "verbunden",
            "warmup": "an", "daily_limit": 20,
        }],
    }
    angemeldeter_client.app.state.instantly_leser = FakeInstantlyLeser(
        {"camp-a": _stand(status="aktiv")}, postfach_antwort=postfach_antwort,
    )
    _lauf_anlegen(daten_dir, "demo-gmbh", "demo-gmbh.yaml",
                  ts="20260720-090000", campaign_id="camp-a")

    antwort = angemeldeter_client.get("/kampagnen/demo-gmbh/20260720-090000")

    assert antwort.context["kd_tageslimit"] == {"heute": 7, "limit": 20}
    assert "Live-Stand gerade nicht erreichbar" in antwort.text
    assert "08:15" in antwort.text


def test_detail_zeigt_oeffnungen_je_mail_schritt_auch_bei_unbekannten_werten(
        angemeldeter_client, daten_dir):
    stand = _stand(status="aktiv", schritte=[
        {"schritt": 1, "versendet": 3, "geoeffnet": 2},
        {"schritt": 2, "versendet": 1, "geoeffnet": None},
        {"schritt": 3, "versendet": None, "geoeffnet": None},
    ])
    angemeldeter_client.app.state.instantly_leser = FakeInstantlyLeser({"camp-a": stand})
    _lauf_anlegen(daten_dir, "demo-gmbh", "demo-gmbh.yaml",
                  ts="20260720-090000", campaign_id="camp-a")

    antwort = angemeldeter_client.get("/kampagnen/demo-gmbh/20260720-090000")

    assert "3 versendet · 2 geöffnet" in antwort.text
    assert "1 versendet · — geöffnet" in antwort.text
    assert "— versendet · — geöffnet" in antwort.text


def test_detail_benennt_warteschlangenrest_nicht_als_noch_offen(
        angemeldeter_client, daten_dir):
    angemeldeter_client.app.state.instantly_leser = FakeInstantlyLeser({
        "camp-a": _stand(status="aktiv"),
    })
    _lauf_anlegen(daten_dir, "demo-gmbh", "demo-gmbh.yaml",
                  ts="20260720-090000", campaign_id="camp-a")

    antwort = angemeldeter_client.get("/kampagnen/demo-gmbh/20260720-090000")

    assert "Nicht getrennt verfügbar: 33" in antwort.text
    assert "33 nicht getrennt verfügbar" in antwort.text
    assert "Noch offen" not in antwort.text


def test_warteschlangenring_zieht_unzustellbar_nicht_vom_rest_ab(
        angemeldeter_client, daten_dir):
    stand = _stand(status="aktiv", versendet=3)
    stand["unzustellbar"] = None
    angemeldeter_client.app.state.instantly_leser = FakeInstantlyLeser({
        "camp-a": stand,
    })
    _lauf_anlegen(daten_dir, "demo-gmbh", "demo-gmbh.yaml",
                  ts="20260720-090000", campaign_id="camp-a")

    antwort = angemeldeter_client.get("/kampagnen/demo-gmbh/20260720-090000")
    css = (Path(__file__).parents[2] / "web" / "static" / "stil.css").read_text(
        encoding="utf-8",
    )
    ring_regel = re.search(r"^\.kamp-ring\s*\{([^}]*)\}", css, re.M | re.S)

    assert antwort.context["kd_warteschlange"] == {
        "gesamt": 36, "versendet": 3, "unzustellbar": None, "ungetrennt": 33,
    }
    assert ('aria-label="3 versendet, 33 nicht getrennt verfügbar, '
            '36 mögliche E-Mails insgesamt"' in antwort.text)
    assert "--kamp-unzustellbar" not in antwort.text
    assert "kamp-punkt--orange" not in antwort.text
    assert "Unzustellbar: —" in antwort.text
    assert "kann sich mit „Versendet“ überschneiden" in antwort.text
    assert ring_regel is not None
    assert "--kamp-unzustellbar" not in ring_regel.group(1)
    assert "#F5A000" not in ring_regel.group(1)


def test_detail_zeigt_instantly_erstellzeit_deutsch_oder_als_strich(
        angemeldeter_client, daten_dir):
    angemeldeter_client.app.state.instantly_leser = FakeInstantlyLeser({
        "camp-a": _stand(status="aktiv"),
    })
    _lauf_anlegen(daten_dir, "demo-gmbh", "demo-gmbh.yaml",
                  ts="20260720-090000", campaign_id="camp-a")

    bekannt = angemeldeter_client.get("/kampagnen/demo-gmbh/20260720-090000")
    assert re.search(r"<dt>Erstellt</dt>\s*<dd>18\.07\.2026, 14:05 Uhr</dd>", bekannt.text)

    stand_ohne_zeit = _stand(status="aktiv")
    stand_ohne_zeit["erstellt_am"] = None
    angemeldeter_client.app.state.instantly_leser = FakeInstantlyLeser({
        "camp-a": stand_ohne_zeit,
    })
    unbekannt = angemeldeter_client.get("/kampagnen/demo-gmbh/20260720-090000")
    assert re.search(r"<dt>Erstellt</dt>\s*<dd>—</dd>", unbekannt.text)


def test_sendefenster_ueber_mitternacht_zaehlt_am_folgetag_zum_vortag(
        angemeldeter_client, daten_dir):
    stand = _stand(status="aktiv")
    stand["sendefenster"] = [{
        "name": "Montagnacht", "von": "22:00", "bis": "02:00",
        "tage": {"0": False, "1": True, "2": False, "3": False,
                 "4": False, "5": False, "6": False},
        "zeitzone": "Europe/Berlin",
    }]
    angemeldeter_client.app.state.instantly_leser = FakeInstantlyLeser({"camp-a": stand})
    angemeldeter_client.app.state.jetzt = lambda: datetime(
        2026, 7, 21, 1, 0, tzinfo=ZoneInfo("Europe/Berlin"),
    )
    _lauf_anlegen(daten_dir, "demo-gmbh", "demo-gmbh.yaml",
                  ts="20260720-090000", campaign_id="camp-a")

    antwort = angemeldeter_client.get("/kampagnen/demo-gmbh/20260720-090000")

    assert antwort.context["kd_sendefenster"][0]["ist_jetzt"] is True


def test_detail_zeigt_unbekannte_live_werte_ohne_scheinbare_nullen(
        angemeldeter_client, daten_dir):
    stand = _stand(status="pausiert", schritte=[])
    stand.update({
        "empfaenger": None,
        "versendet": None,
        "geoeffnet": None,
        "antworten": None,
        "unzustellbar": None,
        "heute_versendet": None,
        "absender": None,
        "sendefenster": None,
    })
    angemeldeter_client.app.state.instantly_leser = FakeInstantlyLeser({
        "camp-a": stand,
    })
    _lauf_anlegen(daten_dir, "demo-gmbh", "demo-gmbh.yaml",
                  ts="20260720-090000", campaign_id="camp-a")

    antwort = angemeldeter_client.get("/kampagnen/demo-gmbh/20260720-090000")

    assert antwort.status_code == 200
    text = antwort.text
    for bezeichnung in (
        "Empfänger", "Mögliche E-Mails", "Versendet", "Geöffnet",
        "Antworten", "Fehlgeschlagen", "Unzustellbar",
    ):
        assert bezeichnung in text
    assert text.count("—") >= 9
    assert "Instantly liefert keinen verlässlichen Zähler" in text
    assert "Nicht in Instantly hinterlegt" in text
    assert 'class="kamp-ring kamp-ring--unbekannt"' in text
    assert "aria-valuenow" not in text
    assert antwort.context["kd_absender"] is None
    angaben = re.search(
        r'<section class="kamp-detail-karte" aria-labelledby="kamp-angaben-titel">(.*?)</section>',
        text, re.S,
    )
    assert angaben is not None
    assert re.search(r"<dt>Absender</dt>\s*<dd>—</dd>", angaben.group(1))


def test_detail_behaelt_aktivieren_formular_und_bestaetigung(
        angemeldeter_client, daten_dir):
    angemeldeter_client.app.state.instantly_leser = FakeInstantlyLeser({
        "camp-a": _stand(status="pausiert"),
    })
    _lauf_anlegen(daten_dir, "demo-gmbh", "demo-gmbh.yaml",
                  ts="20260720-090000", campaign_id="camp-a")

    antwort = angemeldeter_client.get("/kampagnen/demo-gmbh/20260720-090000")

    assert antwort.status_code == 200
    assert ('action="/kampagnen/demo-gmbh/20260720-090000/aktivieren"'
            in antwort.text)
    assert "Wenn du jetzt startest, verschickt Instantly die E-Mails dieser Kampagne" in antwort.text
    assert 'name="bestaetigt" value="ja"' in antwort.text


def test_detail_gibt_dem_inhalt_auf_schmalen_bildschirmen_die_volle_breite():
    css_pfad = Path(__file__).parents[2] / "web" / "static" / "stil.css"
    css = css_pfad.read_text(encoding="utf-8")
    rahmen = re.search(
        r"^  \.rahmen:has\(\.kamp-detail-seite\)\s*\{([^}]*)\}",
        css, re.M | re.S,
    )
    seitenleiste = re.search(
        r"^  \.rahmen:has\(\.kamp-detail-seite\) \.seitenleiste\s*\{([^}]*)\}",
        css, re.M | re.S,
    )

    assert rahmen is not None
    assert "flex-direction: column" in rahmen.group(1)
    assert seitenleiste is not None
    assert "width: 100%" in seitenleiste.group(1)


def test_detail_fokus_ist_auf_weiss_kontrastreich_statt_hellorange():
    css_pfad = Path(__file__).parents[2] / "web" / "static" / "stil.css"
    css = css_pfad.read_text(encoding="utf-8")
    fokus = re.search(
        r"\.kamp-detail-zurueck:focus-visible,(.*?)\{([^}]*)\}",
        css, re.S,
    )

    assert fokus is not None
    assert "#8A4D00" in fokus.group(2)
    assert "#F5A000" not in fokus.group(2)


def test_uebersicht_behaelt_760px_waehrend_details_bei_820px_stapeln():
    css_pfad = Path(__file__).parents[2] / "web" / "static" / "stil.css"
    css = css_pfad.read_text(encoding="utf-8")
    start_820 = css.index("@media (max-width: 820px)")
    ende_820 = css.index("@media (max-width: 760px)", start_820)
    ende_760 = css.index("@media (prefers-reduced-motion: reduce)", ende_820)
    media_820 = css[start_820:ende_820]
    media_760 = css[ende_820:ende_760]

    assert ".kamp-detail-kennzahlen" in media_820
    assert ".kamp-warteschlange-raster" in media_820
    assert ".kamp-uebersicht-kopf" not in media_820
    assert ".kamp-filter" not in media_820
    assert ".wholix-karten" not in media_820
    assert ".kamp-uebersicht-kopf" in media_760
    assert ".kamp-filter" in media_760
    assert ".wholix-karten" in media_760


def test_detail_behaelt_bekannte_nullwerte_auch_im_warteschlangenring(
        angemeldeter_client, daten_dir):
    stand = _stand(status="aktiv", versendet=0, antworten=0, schritte=[])
    stand.update({
        "empfaenger": 0,
        "geoeffnet": 0,
        "unzustellbar": 0,
        "heute_versendet": 0,
    })
    angemeldeter_client.app.state.instantly_leser = FakeInstantlyLeser({
        "camp-a": stand,
    })
    lauf_dir = _lauf_anlegen(
        daten_dir, "demo-gmbh", "demo-gmbh.yaml",
        ts="20260720-090000", campaign_id="camp-a",
    )
    (lauf_dir / "pruefung_ok.json").write_text("[]", encoding="utf-8")

    antwort = angemeldeter_client.get("/kampagnen/demo-gmbh/20260720-090000")

    assert antwort.status_code == 200
    assert ('aria-label="0 versendet, 0 nicht getrennt verfügbar, '
            '0 mögliche E-Mails insgesamt"' in antwort.text)
    assert 'class="kamp-ring kamp-ring--unbekannt"' not in antwort.text


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
