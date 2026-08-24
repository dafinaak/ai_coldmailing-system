"""Die Automatisierungs-Pruefung ist Pflicht - sie darf NIE still ausfallen.

Auftrag Dafinas (21.08.2026). Vorher konnte die Pruefung an drei Stellen
lautlos verschwinden, und dann kam JEDE Firma durch:

  1. `wettbewerber_pruefung` stand auf false (Standard!) - alle 17
     Kundendateien hatten die Zeile gar nicht;
  2. die Kaskade hatte keinen KI-Baustein - dann wurde nur ein Satz
     gedruckt und ein leeres Urteil zurueckgegeben;
  3. pipeline.schnelllauf kannte die Pruefung ueberhaupt nicht - ein
     ganzer Ausfuehrungsweg ohne jede Wettbewerber-Frage.

Neue Regel, in allen drei Faellen gleich: wer nicht eindeutig als
"keine Automatisierung" beurteilt werden kann, gilt als UNSICHER und
kommt in keine Kampagne. Lieber ein Lauf ohne Leads als ein Wettbewerber
im Postfach.

  AUTOMATISIERUNG -> blockiert
  UNSICHER        -> blockiert
  KEINE           -> darf weiter zu den naechsten Pruefungen

Hier fliesst kein Geld: alle Anbieter sind Attrappen, es gibt kein Netz.
"""
import json
from pathlib import Path

import pytest
import yaml

import pipeline.automation_klassifikation as _klass
import pipeline.website as _website
from pipeline.config import Kunde, load_kunde
from pipeline.sourcing import source_leads

KUNDEN_ORDNER = Path(__file__).resolve().parents[1] / "kunden"


@pytest.fixture(autouse=True)
def _kein_netz_kein_pool(monkeypatch):
    monkeypatch.setattr(_website, "fetch_text",
                        lambda url, max_zeichen=5000: f"Webseite von {url}")
    monkeypatch.setattr(_klass, "laden", lambda daten_dir=".": {})


# --- Attrappen ----------------------------------------------------------

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


class _UrteilKI:
    """Sagt "Automatisierung" fuer die genannten Domains, sonst nein."""

    def __init__(self, wettbewerber_domains=()):
        self._treffer = set(wettbewerber_domains)

    def frage(self, system, prompt):
        ist = any(d in prompt for d in self._treffer)
        return json.dumps({"wettbewerber": ist,
                           "belege": "Prozessautomatisierung" if ist else ""})


class _FakeImpressum:
    def __init__(self, wettbewerber_domains=(), personen_je_domain=None,
                 ki=True):
        if ki:
            self.ki = _UrteilKI(wettbewerber_domains)
        self._personen = personen_je_domain or {}

    def impressum_text(self, website):
        return "Impressum ..." if website else None

    def entscheider_lesen(self, text, firmenname, domain="", hinweis_name=""):
        return {"personen": list(self._personen.get(domain, [])),
                "mail_domain": None}


def _kunde(**extra):
    basis = dict(name="Demo", zielgruppe={}, angebot="A", tonalitaet="T",
                 absender="Ab", follow_up_tage=[1, 2],
                 test_empfaenger=["t@example.com"],
                 maps_suche="IT-Dienstleister", kontakt_rollen=["Inhaber"],
                 anbieter_reihenfolge=["impressum"])
    basis.update(extra)
    return Kunde(**basis)


def _firma(domain, website=None):
    return {"name": domain,
            "website": f"https://{domain}" if website is None else website,
            "domain": domain, "address": "", "categories": []}


def _lauf(firmen, impressum, mails=None, kunde=None):
    hunter = _FakeHunter()
    dropcontact = _FakeDropcontact(mails)
    leads, _, firmen_aus = source_leads(
        kunde or _kunde(), 10, "k", "k", "k",
        apify_source=_FakeApify(firmen), hunter_source=hunter,
        dropcontact_source=dropcontact, impressum_quelle=impressum)
    return leads, firmen_aus, hunter, dropcontact


def _satz(firmen_aus, domain):
    return next(f for f in firmen_aus if f["domain"] == domain)


# --- 1. Neue Kampagne: Pruefung ist von sich aus an ---------------------

def test_neue_kampagne_hat_die_pruefung_von_haus_aus_an():
    # Ohne dass jemand etwas eintraegt.
    assert Kunde.__dataclass_fields__["wettbewerber_pruefung"].default is True
    assert _kunde().wettbewerber_pruefung is True


# --- 2. Bestehende Kampagnen-Ordner ------------------------------------

def test_jede_bestehende_kundendatei_hat_die_pruefung_an():
    dateien = sorted(KUNDEN_ORDNER.glob("*.yaml"))
    assert dateien, "keine Kundendateien gefunden"
    ohne = [d.name for d in dateien
            if yaml.safe_load(d.read_text(encoding="utf-8"))
            .get("wettbewerber_pruefung") is not True]
    assert ohne == [], f"Kundendateien ohne Pruefung: {ohne}"


def test_geladene_kundendatei_meldet_die_pruefung_als_an():
    # Nicht nur der Text in der Datei - auch das geladene Objekt.
    # Dateien, die aus GANZ anderen Gruenden nicht laden (eine hat seit
    # jeher follow_up_tage [7, 7]), sind hier nicht das Thema und werden
    # uebersprungen - der Text-Test oben deckt sie trotzdem ab.
    geprueft = 0
    for datei in sorted(KUNDEN_ORDNER.glob("*.yaml")):
        try:
            kunde = load_kunde(datei)
        except ValueError:
            continue
        assert kunde.wettbewerber_pruefung is True, datei.name
        geprueft += 1
    assert geprueft > 0


# --- 3./4./5. Die drei Ausgaenge ---------------------------------------

def test_automatisierung_wird_blockiert():
    impressum = _FakeImpressum(wettbewerber_domains=("robo.de",))
    _, firmen_aus, hunter, dropcontact = _lauf([_firma("robo.de")], impressum)

    robo = _satz(firmen_aus, "robo.de")
    assert robo["offers_automation_services"] == "yes"
    assert robo["campaign_eligible"] is False
    assert robo["campaign_ineligibility_reason"] == "automation_provider"
    # Kein bezahlter Schritt fuer ihn.
    assert dropcontact.aufrufe == []
    assert hunter.geprueft == []


def test_unsicher_wird_genauso_blockiert_wie_automatisierung():
    class _KaputteKI:
        def frage(self, system, prompt):
            return "kein JSON"

    impressum = _FakeImpressum()
    impressum.ki = _KaputteKI()
    _, firmen_aus, hunter, dropcontact = _lauf([_firma("x.de")], impressum)

    x = _satz(firmen_aus, "x.de")
    assert x["offers_automation_services"] == "uncertain"
    assert x["campaign_eligible"] is False
    assert x["campaign_ineligibility_reason"] == "automation_uncertain"
    assert dropcontact.aufrufe == []
    assert hunter.geprueft == []


def test_keine_automatisierung_darf_weiter_zu_den_naechsten_pruefungen():
    impressum = _FakeImpressum(
        personen_je_domain={"gut.de": [{"vorname": "Otto", "nachname": "Alt",
                                        "rolle": "Inhaber"}]})
    leads, firmen_aus, _, dropcontact = _lauf(
        [_firma("gut.de")], impressum, mails={"Otto": "alt@gut.de"})

    gut = _satz(firmen_aus, "gut.de")
    assert gut["offers_automation_services"] == "no"
    # "darf weiter" heisst: der bezahlte Schritt lief und der Lead steht.
    assert dropcontact.aufrufe == ["Otto"]
    assert [l.email for l in leads] == ["alt@gut.de"]


# --- 6. Keine lesbare Webseite -> unsicher -> blockiert -----------------

def test_ohne_lesbare_webseite_bleibt_es_unsicher_und_blockiert(monkeypatch):
    # Die Seite laesst sich nicht lesen: aus dem Namen zu urteilen waere
    # geraten (Eichung 20.08.2026), also unsicher - und damit blockiert.
    monkeypatch.setattr(_website, "fetch_text",
                        lambda url, max_zeichen=5000: "")
    impressum = _FakeImpressum()
    _, firmen_aus, hunter, dropcontact = _lauf([_firma("leer.de")], impressum)

    leer = _satz(firmen_aus, "leer.de")
    assert leer["offers_automation_services"] == "uncertain"
    assert leer["campaign_eligible"] is False
    assert leer["campaign_ineligibility_reason"] == "automation_uncertain"
    assert dropcontact.aufrufe == []
    assert hunter.geprueft == []


def test_firma_ganz_ohne_webseite_ist_unsicher_und_blockiert():
    impressum = _FakeImpressum()
    _, firmen_aus, _, dropcontact = _lauf([_firma("ohne.de", website="")],
                                          impressum)

    ohne = _satz(firmen_aus, "ohne.de")
    assert ohne["offers_automation_services"] == "uncertain"
    assert ohne["campaign_eligible"] is False
    assert dropcontact.aufrufe == []


# --- Die drei fruehereren Schlupfloecher -------------------------------

def test_ohne_ki_baustein_faellt_die_pruefung_nicht_aus_sondern_blockiert():
    # Frueher: eine Zeile Ausgabe, leeres Urteil - und JEDE Firma kam
    # durch. Jetzt: niemand kommt durch.
    impressum = _FakeImpressum(ki=False)
    assert not hasattr(impressum, "ki")

    _, firmen_aus, hunter, dropcontact = _lauf([_firma("y.de")], impressum)

    y = _satz(firmen_aus, "y.de")
    assert y["offers_automation_services"] == "uncertain"
    assert y["campaign_eligible"] is False
    assert y["campaign_ineligibility_reason"] == "automation_uncertain"
    assert dropcontact.aufrufe == []
    assert hunter.geprueft == []


def test_schnelllauf_kennt_die_pruefung_und_blockiert_den_anbieter():
    # pipeline.schnelllauf ist ein EIGENER Ausfuehrungsweg (er geht nicht
    # durch source_leads) und hatte die Pruefung ueberhaupt nicht.
    from pipeline.schnelllauf import lauf_ausfuehren

    class _Impressum:
        def __init__(self):
            self.ki = _UrteilKI(("robo.de",))
            self.gelesen = []

        def impressum_text(self, website):
            return f"text von {website}"

        def entscheider_lesen(self, text, firmenname, domain="",
                              hinweis_name=""):
            self.gelesen.append(domain)
            return {"personen": [{"vorname": "Otto", "nachname": "Alt"}],
                    "mail_domain": None}

    class _Dropcontact:
        def __init__(self):
            self.batches = []

        def batch_abgeben(self, anfragen):
            gesendet = [(nr, a) for nr, a in enumerate(anfragen)
                        if a.get("first_name")]
            if not gesendet:
                return None, []
            self.batches.append([a["first_name"] for _, a in gesendet])
            return "r1", gesendet

        def batch_abholen(self, request_id, gesendet, gesamt=None):
            ergebnisse = [None] * (gesamt or len(gesendet))
            for nr, anfrage in gesendet:
                ergebnisse[nr] = {"email": f"{anfrage['first_name']}@x.de",
                                  "qualification": "nominative@pro"}
            return ergebnisse

    impressum, dropcontact = _Impressum(), _Dropcontact()
    ergebnis = lauf_ausfuehren(
        [_firma("robo.de"), _firma("gut.de")], _kunde(),
        dropcontact, impressum, hunter=None)

    robo = next(e for e in ergebnis if e["domain"] == "robo.de")
    assert robo["offers_automation_services"] == "yes"
    assert robo["campaign_eligible"] is False
    assert robo["campaign_ineligibility_reason"] == "automation_provider"
    assert robo.get("leads") == []
    # Der Wettbewerber hat keinen bezahlten Schritt ausgeloest.
    assert all("Otto" not in b or "robo.de" not in str(b)
               for b in dropcontact.batches)
    assert "robo.de" not in impressum.gelesen

    gut = next(e for e in ergebnis if e["domain"] == "gut.de")
    assert gut["offers_automation_services"] == "no"
    assert gut["ausgang"] == "mit_entscheider"


def test_schnelllauf_ohne_ki_baustein_blockiert_alle():
    from pipeline.schnelllauf import lauf_ausfuehren

    class _ImpressumOhneKI:
        def impressum_text(self, website):
            return f"text von {website}"

        def entscheider_lesen(self, text, firmenname, domain="",
                              hinweis_name=""):
            return {"personen": [{"vorname": "Otto", "nachname": "Alt"}],
                    "mail_domain": None}

    class _Dropcontact:
        def __init__(self):
            self.batches = []

        def batch_abgeben(self, anfragen):
            self.batches.append(anfragen)
            return None, []

    dropcontact = _Dropcontact()
    ergebnis = lauf_ausfuehren([_firma("gut.de")], _kunde(),
                               dropcontact, _ImpressumOhneKI(), hunter=None)

    gut = ergebnis[0]
    assert gut["offers_automation_services"] == "uncertain"
    assert gut["campaign_eligible"] is False
    assert dropcontact.batches == []


def test_ausdruecklich_abgeschaltete_pruefung_laesst_niemanden_durch():
    # Der Schalter darf die Pruefung nicht mehr lautlos aushebeln: wer
    # sie abschaltet, bekommt keine Leads statt ungeprueften Leads.
    impressum = _FakeImpressum(
        personen_je_domain={"gut.de": [{"vorname": "Otto", "nachname": "Alt",
                                        "rolle": "Inhaber"}]})
    leads, firmen_aus, _, dropcontact = _lauf(
        [_firma("gut.de")], impressum, mails={"Otto": "alt@gut.de"},
        kunde=_kunde(wettbewerber_pruefung=False))

    gut = _satz(firmen_aus, "gut.de")
    assert gut["offers_automation_services"] == "uncertain"
    assert gut["campaign_eligible"] is False
    assert leads == []
    assert dropcontact.aufrufe == []
