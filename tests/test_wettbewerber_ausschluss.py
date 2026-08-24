"""Automatisierungs-Anbieter fliegen VOR dem bezahlten Schritt raus.

Olivers Regel (19.08.2026): Firmen, die selbst Automatisierung anbieten,
sind Wettbewerber - keine Kampagne, kein Credit, kein Anruf. Aber sie
bleiben GESPEICHERT (Master-Datenbank), mit Urteil, Grund und Zeitpunkt.
"""
import json

import pytest

import pipeline.automation_klassifikation as _klass
import pipeline.website as _website


@pytest.fixture(autouse=True)
def _feste_webseite(monkeypatch):
    """Kein echtes Netz und kein echter Pool-Stand in diesen Tests."""
    monkeypatch.setattr(_website, "fetch_text",
                        lambda url, max_zeichen=5000: f"Webseite von {url}")
    monkeypatch.setattr(_klass, "laden", lambda daten_dir=".": {})



from pipeline.config import Kunde
from pipeline.kontakte_excel import mappe_bauen
from pipeline.sourcing import source_leads


class _FakeApify:
    def __init__(self, firmen):
        self._firmen = firmen

    def search(self, suchbegriff, limit):
        return self._firmen[:limit]


class _FakeHunter:
    def __init__(self):
        self.geprueft = []

    def entscheider_finden(self, domain, limit=10):
        return []

    def email_pruefen(self, email):
        self.geprueft.append(email)
        return {"status": "valid"}


class _FakeDropcontact:
    def __init__(self, mail_je_vorname=None):
        self._mails = mail_je_vorname or {}
        self.aufrufe = []

    def email_bauen(self, first_name, last_name, website, company=""):
        self.aufrufe.append(first_name)
        wert = self._mails.get(first_name)
        return {"email": wert} if wert else None


class _FakeImpressum:
    """Impressum-Quelle samt KI-Attrappe fuer die Wettbewerber-Pruefung."""

    def __init__(self, wettbewerber_domains=(), personen_je_domain=None):
        self.ki = _UrteilKI(wettbewerber_domains)
        self._personen = personen_je_domain or {}

    def impressum_text(self, website):
        return "Impressum ..." if website else None

    def entscheider_lesen(self, text, firmenname, domain="", hinweis_name=""):
        return {"personen": list(self._personen.get(domain, [])),
                "mail_domain": None}


class _UrteilKI:
    def __init__(self, wettbewerber_domains):
        self._treffer = set(wettbewerber_domains)

    def frage(self, system, prompt):
        ist = any(d in prompt for d in self._treffer)
        return json.dumps({"wettbewerber": ist,
                           "belege": "Prozessautomatisierung" if ist else ""})


def _kunde(**extra):
    basis = dict(name="Demo", zielgruppe={}, angebot="A", tonalitaet="T",
                 absender="Ab", follow_up_tage=[1, 2],
                 test_empfaenger=["t@example.com"],
                 maps_suche="IT-Dienstleister", kontakt_rollen=["Inhaber"],
                 anbieter_reihenfolge=["impressum"],
                 wettbewerber_pruefung=True)
    basis.update(extra)
    return Kunde(**basis)


def _firma(domain):
    return {"name": domain, "website": f"https://{domain}", "domain": domain,
            "address": "", "categories": []}


def _lauf(firmen, impressum, mails=None, kunde=None):
    hunter = _FakeHunter()
    dropcontact = _FakeDropcontact(mails)
    leads, deckung, firmen_aus = source_leads(
        kunde or _kunde(), 10, "k", "k", "k",
        apify_source=_FakeApify(firmen), hunter_source=hunter,
        dropcontact_source=dropcontact, impressum_quelle=impressum)
    return leads, deckung, firmen_aus, hunter, dropcontact


def test_wettbewerber_bleibt_gespeichert_aber_ohne_lead_und_ohne_credits():
    impressum = _FakeImpressum(
        wettbewerber_domains=("robo.de",),
        personen_je_domain={"a.de": [{"vorname": "Otto", "nachname": "Alt",
                                      "rolle": "Inhaber"}]})
    leads, _, firmen_aus, hunter, dropcontact = _lauf(
        [_firma("robo.de"), _firma("a.de")], impressum,
        mails={"Otto": "alt@a.de"})

    # Der Wettbewerber steht im Firmensatz - markiert, nicht geloescht.
    robo = next(f for f in firmen_aus if f["domain"] == "robo.de")
    assert robo["ausgang"] == "wettbewerber"
    assert robo["offers_automation_services"] == "yes"
    assert robo["campaign_eligible"] is False
    assert robo["campaign_ineligibility_reason"] == "automation_provider"
    assert robo["automation_checked_at"]

    # Kein Lead, kein Dropcontact-Aufruf, keine info@-Pruefung fuer ihn.
    assert [l.email for l in leads] == ["alt@a.de"]
    assert dropcontact.aufrufe == ["Otto"]
    assert hunter.geprueft == []          # a.de hat persoenliche Mail

    # Die saubere Firma traegt das "nein" samt Grundfeldern.
    sauber = next(f for f in firmen_aus if f["domain"] == "a.de")
    assert sauber["offers_automation_services"] == "no"


def test_unlesbares_urteil_gilt_als_uncertain_und_schliesst_aus():
    class _KaputteKI:
        def frage(self, system, prompt):
            return "kein json"

    impressum = _FakeImpressum()
    impressum.ki = _KaputteKI()
    _, _, firmen_aus, _, dropcontact = _lauf([_firma("a.de")], impressum)

    assert firmen_aus[0]["offers_automation_services"] == "uncertain"
    assert firmen_aus[0]["campaign_eligible"] is False
    assert dropcontact.aufrufe == []


def test_abgeschaltete_flagge_laesst_niemanden_mehr_durch():
    # Bis 21.08.2026 hiess wettbewerber_pruefung=false: gar nicht pruefen -
    # und dann kam JEDE Firma ungeprueft durch, auch der Wettbewerber.
    # Seit Dafinas Auftrag hebelt der Schalter die Pruefung nicht mehr aus:
    # abgeschaltet heisst unsicher, und unsicher heisst keine Kampagne.
    impressum = _FakeImpressum(wettbewerber_domains=("a.de",))
    leads, _, firmen_aus, hunter, dropcontact = _lauf(
        [_firma("a.de")], impressum, kunde=_kunde(wettbewerber_pruefung=False))

    assert firmen_aus[0]["offers_automation_services"] == "uncertain"
    assert firmen_aus[0]["campaign_eligible"] is False
    assert firmen_aus[0]["campaign_ineligibility_reason"] == "automation_uncertain"
    assert leads == []
    assert dropcontact.aufrufe == []
    assert hunter.geprueft == []


def test_wettbewerber_steht_nicht_auf_anruf_und_brief(tmp_path):
    (tmp_path / "leads.json").write_text(json.dumps({"leads": []}),
                                         encoding="utf-8")
    (tmp_path / "firmen.json").write_text(json.dumps([
        {"name": "Robo GmbH", "domain": "robo.de", "ausgang": "wettbewerber",
         "telefon": "1", "plz": "30159"},
        {"name": "Leer GmbH", "domain": "leer.de",
         "ausgang": "kein_entscheider", "telefon": "2", "plz": "30159"}]),
        encoding="utf-8")
    (tmp_path / "personalisierung.json").write_text(
        json.dumps({"fertig": [], "nacharbeit": []}), encoding="utf-8")

    zeilen = [list(r) for r in mappe_bauen(tmp_path)["Anruf & Brief"]
              .iter_rows(values_only=True)]
    assert [z[0] for z in zeilen[1:]] == ["Leer GmbH"]


def test_formular_kampagnen_pruefen_immer():
    # Das Formular schreibt wettbewerber_pruefung: true in die Kundendatei.
    from web.routen.assistent import _kunde_schreiben
    import yaml

    class _Req:
        pass

    entwurf = {"kennung": "t1", "daten": {"name": "Test", "usp": [],
                                          "icp": {}}}
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as ordner:
        datei = _kunde_schreiben(Path(ordner), entwurf)
        inhalt = yaml.safe_load((Path(ordner) / datei).read_text(
            encoding="utf-8"))
    assert inhalt["wettbewerber_pruefung"] is True
