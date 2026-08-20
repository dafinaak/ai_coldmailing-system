"""Phase 2: Dreiteilung des Automatisierungs-Urteils + Pool-Klassifikation.

automation / keine_automation / unsicher - "unsicher" heisst: gespeichert
ja, Kampagne nein, kein Cent Anreicherung, KEIN Urteil aus dem blossen
Firmennamen (Benchmark-Fund 20.08.2026).
"""
import json

import pytest

import pipeline.automation_klassifikation as klass
import pipeline.website
from pipeline.branchen_filter import ist_wettbewerber
from pipeline.config import Kunde
from pipeline.master_db import DB_NAME, bauen
from pipeline.sourcing import source_leads


class _KI:
    def __init__(self, antwort):
        self.antwort = antwort
        self.fragen = []

    def frage(self, system, prompt):
        self.fragen.append(prompt)
        return self.antwort


class _NieKI:
    def frage(self, system, prompt):
        raise AssertionError("KI darf hier nicht gefragt werden")


# --- Dreiteilung des Parsers ----------------------------------------------

def test_einstufung_automation_und_keine_und_unsicher():
    ja = ist_wettbewerber({"name": "A"}, "text",
                          _KI('{"einstufung": "automation", "belege": "RPA"}'))
    assert (ja["wettbewerber"], ja["unsicher"]) == (True, False)

    nein = ist_wettbewerber({"name": "A"}, "text",
                            _KI('{"einstufung": "keine_automation"}'))
    assert (nein["wettbewerber"], nein["unsicher"]) == (False, False)

    offen = ist_wettbewerber({"name": "A"}, "text",
                             _KI('{"einstufung": "unsicher"}'))
    assert (offen["wettbewerber"], offen["unsicher"]) == (False, True)


def test_alte_antwortform_bleibt_lesbar():
    alt = ist_wettbewerber({"name": "A"}, "text",
                           _KI('{"wettbewerber": true, "belege": "x"}'))
    assert (alt["wettbewerber"], alt["unsicher"]) == (True, False)


def test_unlesbare_antwort_ist_unsicher_nicht_wettbewerber():
    kaputt = ist_wettbewerber({"name": "A"}, "text", _KI("kein json"))
    assert (kaputt["wettbewerber"], kaputt["unsicher"]) == (False, True)
    assert kaputt["belege"] == "KI-Antwort nicht lesbar"


# --- Im Kampagnen-Lauf -----------------------------------------------------

class _FakeApify:
    def __init__(self, firmen):
        self._firmen = firmen

    def search(self, suchbegriff, limit):
        return self._firmen


class _FakeHunter:
    def entscheider_finden(self, domain, limit=10):
        return []

    def email_pruefen(self, email):
        return {"status": "valid"}


class _FakeDropcontact:
    def __init__(self):
        self.aufrufe = []

    def email_bauen(self, first_name, last_name, website, company=""):
        self.aufrufe.append(first_name)
        return None


class _FakeImpressum:
    def __init__(self, ki):
        self.ki = ki

    def impressum_text(self, website):
        return "Impressum ..."

    def entscheider_lesen(self, text, firmenname, domain="", hinweis_name=""):
        return {"personen": [], "mail_domain": None}


def _kunde():
    return Kunde(name="Demo", zielgruppe={}, angebot="A", tonalitaet="T",
                 absender="Ab", follow_up_tage=[1, 2],
                 test_empfaenger=["t@example.com"], maps_suche="IT",
                 kontakt_rollen=["Inhaber"],
                 anbieter_reihenfolge=["impressum"],
                 wettbewerber_pruefung=True)


@pytest.fixture
def hermetisch(monkeypatch):
    monkeypatch.setattr(pipeline.website, "fetch_text",
                        lambda url, max_zeichen=5000: f"Webseite von {url}")
    monkeypatch.setattr(klass, "laden", lambda daten_dir=".": {})


def _lauf(ki, firma_extra=None, dropcontact=None):
    firma = {"name": "robo.de", "website": "https://robo.de",
             "domain": "robo.de", "address": "", "categories": [],
             **(firma_extra or {})}
    dc = dropcontact or _FakeDropcontact()
    leads, _, firmen_aus = source_leads(
        _kunde(), 10, "k", "k", "k", apify_source=_FakeApify([firma]),
        hunter_source=_FakeHunter(), dropcontact_source=dc,
        impressum_quelle=_FakeImpressum(ki))
    return leads, firmen_aus, dc


def test_unsicher_wird_wie_ja_ausgeschlossen_aber_mit_eigenem_grund(hermetisch):
    leads, firmen_aus, dc = _lauf(_KI('{"einstufung": "unsicher"}'))
    assert leads == []
    assert dc.aufrufe == []          # kein bezahlter Schritt
    eintrag = firmen_aus[0]
    assert eintrag["ausgang"] == "automation_unsicher"
    assert eintrag["offers_automation_services"] == "uncertain"
    assert eintrag["campaign_eligible"] is False
    assert eintrag["campaign_ineligibility_reason"] == "automation_uncertain"


def test_unlesbare_webseite_wird_unsicher_ohne_ki_aufruf(hermetisch, monkeypatch):
    monkeypatch.setattr(pipeline.website, "fetch_text",
                        lambda url, max_zeichen=5000: "")
    leads, firmen_aus, _ = _lauf(_NieKI())      # KI wuerde schreien
    assert leads == []
    eintrag = firmen_aus[0]
    assert eintrag["offers_automation_services"] == "uncertain"
    assert eintrag["automation_check_reason"] == "Webseite nicht lesbar"
    assert eintrag["automation_check_source"] == "keine-webseite"


def test_pool_urteil_wird_wiederverwendet_ohne_ki_und_ohne_fetch(monkeypatch):
    def _kein_fetch(url, max_zeichen=5000):
        raise AssertionError("fetch darf nicht laufen - Urteil liegt vor")

    monkeypatch.setattr(pipeline.website, "fetch_text", _kein_fetch)
    monkeypatch.setattr(klass, "laden", lambda daten_dir=".": {
        "robo.de": {"offers_automation_services": "yes",
                    "automation_check_reason": "RPA-Angebot"}})
    leads, firmen_aus, dc = _lauf(_NieKI())
    assert leads == []
    assert dc.aufrufe == []
    eintrag = firmen_aus[0]
    assert eintrag["ausgang"] == "wettbewerber"
    assert eintrag["automation_check_source"] == "pool-klassifikation"


# --- Pool-Klassifikation ---------------------------------------------------

def _sammlung(daten_dir, firmen):
    ziel = daten_dir / "laeufe" / "leadquellen" / "s1"
    ziel.mkdir(parents=True)
    (ziel / "firmen.json").write_text(json.dumps(firmen), encoding="utf-8")


def test_klassifizieren_beurteilt_speichert_und_nimmt_wieder_auf(tmp_path):
    _sammlung(tmp_path, [
        {"name": "Robo GmbH", "domain": "robo.de", "website": "https://robo.de"},
        {"name": "Sauber GmbH", "domain": "sauber.de",
         "website": "https://sauber.de"},
        {"name": "Ohne Web", "domain": "ohne.de"},
    ])

    class _JeNachDomain:
        def __init__(self):
            self.fragen = 0

        def frage(self, system, prompt):
            self.fragen += 1
            if "robo.de" in prompt:
                return '{"einstufung": "automation", "belege": "RPA"}'
            return '{"einstufung": "keine_automation"}'

    ki = _JeNachDomain()
    stand = klass.klassifizieren(
        tmp_path, ki=ki, fetch=lambda url, max_zeichen=8000: f"Seite {url}",
        log=lambda *_: None)

    assert stand["robo.de"]["offers_automation_services"] == "yes"
    assert stand["sauber.de"]["offers_automation_services"] == "no"
    # Ohne Webseite: unsicher, OHNE KI-Aufruf.
    assert stand["ohne.de"]["offers_automation_services"] == "uncertain"
    assert ki.fragen == 2
    gespeichert = json.loads(
        (tmp_path / klass.DATEI).read_text(encoding="utf-8"))
    assert set(gespeichert) == {"robo.de", "sauber.de", "ohne.de"}

    # Wiederaufnahme: nichts offen, kein weiterer KI-Aufruf.
    klass.klassifizieren(tmp_path, ki=_NieKI(),
                         fetch=lambda url, max_zeichen=8000: "x",
                         log=lambda *_: None)


def test_master_db_uebernimmt_das_pool_urteil(tmp_path):
    _sammlung(tmp_path, [
        {"name": "Robo GmbH", "domain": "robo.de", "website": "https://robo.de",
         "plz": "30159", "categories": ["IT-Service"]},
        {"name": "Frag GmbH", "domain": "frag.de", "website": "https://frag.de",
         "plz": "30159", "categories": ["IT-Service"]},
    ])
    (tmp_path / "daten").mkdir()
    (tmp_path / klass.DATEI).write_text(json.dumps({
        "robo.de": {"offers_automation_services": "yes",
                    "automation_check_reason": "RPA",
                    "automation_checked_at": "2026-08-20T18:00:00"},
        "frag.de": {"offers_automation_services": "uncertain",
                    "automation_check_reason": "Webseite nicht lesbar",
                    "automation_checked_at": "2026-08-20T18:00:00"},
    }), encoding="utf-8")

    bauen(tmp_path)

    import sqlite3
    db = sqlite3.connect(tmp_path / DB_NAME)
    db.row_factory = sqlite3.Row
    zeilen = {z["domain"]: z for z in db.execute("SELECT * FROM companies")}
    assert zeilen["robo.de"]["offers_automation_services"] == "yes"
    assert zeilen["robo.de"]["ineligibility_reason"] == "automation_provider"
    assert zeilen["frag.de"]["offers_automation_services"] == "uncertain"
    assert zeilen["frag.de"]["ineligibility_reason"] == "automation_uncertain"
    db.close()
