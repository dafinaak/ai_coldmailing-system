"""Die strenge Kampagnen-Regel (Oliver, Phase 1, 20.08.2026).

Empfaenger einer Kampagne ist NUR ein benannter Entscheider mit
persoenlicher, geprueft er Geschaefts-Adresse. Sammeladressen (info@,
contact@, ...) bleiben als Firmen-Information gespeichert, werden aber
nie angeschrieben - durchgesetzt an vier Stellen (Lead-Erzeugung,
Text-Erzeugung, Uebergabe, Instantly-Import). Die zehn Pflichtfaelle
aus dem Auftrag stehen hier in dieser Reihenfolge.
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



from pipeline.campaign_eligibility import (eligible_leads, is_generic_email,
                                           lead_eligibility)
from pipeline.config import Kunde
from pipeline.senders.instantly import InstantlySender
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


class _HunterOhnePruefer:
    """Wie Hunter, aber ohne email_pruefen - der 'kein Pruefer'-Fall."""

    def entscheider_finden(self, domain, limit=10):
        return []


class _FakeDropcontact:
    def __init__(self, mail_je_vorname=None):
        self._mails = mail_je_vorname or {}
        self.aufrufe = []

    def email_bauen(self, first_name, last_name, website, company=""):
        self.aufrufe.append(first_name)
        wert = self._mails.get(first_name)
        return {"email": wert} if wert else None


class _UnbedenklichKI:
    """Sagt zu jeder Firma "keine Automatisierung".

    Thema dieser Datei ist Olivers Kampagnen-Tauglichkeit (Phase 1), NICHT
    die Automatisierungs-Prüfung. Seit diese Pflicht ist (21.08.2026),
    braucht auch dieser Weg ein Urteil - ohne KI-Baustein wäre jede Firma
    unsicher und käme gar nicht erst bis zu den Regeln, die hier geprüft
    werden. Die zwei Tests, in denen das Urteil selbst zählt, setzen sich
    ihre eigene KI (siehe unten).
    """

    def frage(self, system, prompt):
        return json.dumps({"wettbewerber": False, "belege": ""})


class _FakeImpressum:
    def __init__(self, personen_je_domain=None):
        self._personen = personen_je_domain or {}
        self.ki = _UnbedenklichKI()

    def impressum_text(self, website):
        return "Impressum ..." if website else None

    def entscheider_lesen(self, text, firmenname, domain="", hinweis_name=""):
        return {"personen": list(self._personen.get(domain, [])),
                "mail_domain": None}


def _kunde():
    return Kunde(name="Demo", zielgruppe={}, angebot="A", tonalitaet="T",
                 absender="Ab", follow_up_tage=[1, 2],
                 test_empfaenger=["t@example.com"],
                 maps_suche="IT-Dienstleister", kontakt_rollen=["Inhaber"],
                 anbieter_reihenfolge=["impressum"])


def _firma(domain):
    return {"name": domain, "website": f"https://{domain}", "domain": domain,
            "address": "", "categories": []}


def _lauf(personen, mails, hunter=None):
    return source_leads(
        _kunde(), 10, "k", "k", "k",
        apify_source=_FakeApify([_firma("a.de")]),
        hunter_source=hunter if hunter is not None else _FakeHunter(),
        dropcontact_source=_FakeDropcontact(mails),
        impressum_quelle=_FakeImpressum({"a.de": personen}))


def person(vor, nach, rolle):
    return {"vorname": vor, "nachname": nach, "rolle": rolle,
            "linkedin": None}


# TEST 1 - benannter Chef + persoenliche geprueft Adresse -> tauglich
def test_1_benannter_chef_mit_persoenlicher_mail_ist_tauglich():
    leads, deckung, firmen_aus = _lauf(
        [person("Otto", "Alt", "Inhaber")], {"Otto": "otto.alt@a.de"})
    assert [l.email for l in leads] == ["otto.alt@a.de"]
    assert lead_eligibility(leads[0]) == (True, "")
    assert deckung["firmen_mit_kontakt"] == 1
    assert "campaign_eligible" not in firmen_aus[0]      # nicht unfaehig


# TEST 2 - benannter Chef, aber nur info@ -> NICHT tauglich, kein Lead
def test_2_nur_info_adresse_ergibt_keinen_lead():
    leads, deckung, firmen_aus = _lauf(
        [person("Otto", "Alt", "Inhaber")], {})      # Dropcontact findet nichts
    assert leads == []
    eintrag = firmen_aus[0]
    assert eintrag["ausgang"] == "ohne_persoenliche_mail"
    assert eintrag["campaign_eligible"] is False
    assert (eintrag["campaign_ineligibility_reason"]
            == "personal_decision_maker_email_missing")
    # Die gefundene Information bleibt: Adresse, Pruefstatus, Chef-Name.
    assert eintrag["info_email"] == "info@a.de"
    assert eintrag["info_pruefstatus"] == "valid"
    assert eintrag["entscheider_primaer"]["name"] == "Otto Alt"
    assert deckung["firmen_mit_kontakt"] == 0


# TEST 3 - contact@ und andere Sammeladressen sind nie tauglich
def test_3_contact_und_andere_sammeladressen_sind_generisch():
    for adresse in ("contact@a.de", "office@a.de", "sales@a.de",
                    "hello@a.de", "support@a.de", "info@a.de",
                    "kontakt@a.de", "vertrieb@a.de"):
        assert is_generic_email(adresse), adresse
    assert not is_generic_email("max.mustermann@a.de")
    ok, grund = lead_eligibility({"email": "contact@a.de",
                                  "first_name": "Max",
                                  "last_name": "Mustermann",
                                  "source": "dropcontact"})
    assert (ok, grund) == (False, "generic_email")


# TEST 4 - kein benannter Entscheider + info@ -> NICHT tauglich
def test_4_ohne_entscheider_bleibt_die_firma_ohne_lead():
    leads, _, firmen_aus = _lauf([], {})
    assert leads == []
    eintrag = firmen_aus[0]
    assert eintrag["campaign_eligible"] is False
    assert eintrag["campaign_ineligibility_reason"] == "no_decision_maker"
    assert eintrag["info_email"] == "info@a.de"          # bleibt gespeichert


# TEST 5 - benannter Chef, persoenliche Mail OHNE Pruefung -> NICHT tauglich
def test_5_ungepruefte_persoenliche_mail_ist_nicht_tauglich():
    ok, grund = lead_eligibility({"email": "otto.alt@a.de",
                                  "first_name": "Otto", "last_name": "Alt",
                                  "source": ""})      # keine buergende Quelle
    assert (ok, grund) == (False, "email_not_verified")


# TEST 6 - Automatisierungs-Anbieter + persoenliche geprueft Mail -> NICHT tauglich
def test_6_wettbewerber_bleibt_trotz_persoenlicher_mail_draussen():
    class _UrteilKI:
        def frage(self, system, prompt):
            return json.dumps({"wettbewerber": True,
                               "belege": "Prozessautomatisierung"})

    impressum = _FakeImpressum({"a.de": [person("Otto", "Alt", "Inhaber")]})
    impressum.ki = _UrteilKI()
    dropcontact = _FakeDropcontact({"Otto": "otto.alt@a.de"})
    kunde = Kunde(name="Demo", zielgruppe={}, angebot="A", tonalitaet="T",
                  absender="Ab", follow_up_tage=[1, 2],
                  test_empfaenger=["t@example.com"],
                  maps_suche="IT", kontakt_rollen=["Inhaber"],
                  anbieter_reihenfolge=["impressum"],
                  wettbewerber_pruefung=True)
    leads, _, firmen_aus = source_leads(
        kunde, 10, "k", "k", "k",
        apify_source=_FakeApify([_firma("a.de")]),
        hunter_source=_FakeHunter(), dropcontact_source=dropcontact,
        impressum_quelle=impressum)
    assert leads == []
    assert dropcontact.aufrufe == []          # kein bezahlter Schritt
    assert firmen_aus[0]["campaign_eligible"] is False
    assert (firmen_aus[0]["campaign_ineligibility_reason"]
            == "automation_provider")


# TEST 7 - benannter Chef + geprueft persoenlich + Automatisierung "nein"
def test_7_sauberer_chef_mit_pruefung_nein_ist_tauglich():
    class _NeinKI:
        def frage(self, system, prompt):
            return json.dumps({"wettbewerber": False, "belege": ""})

    impressum = _FakeImpressum({"a.de": [person("Otto", "Alt", "Inhaber")]})
    impressum.ki = _NeinKI()
    kunde = Kunde(name="Demo", zielgruppe={}, angebot="A", tonalitaet="T",
                  absender="Ab", follow_up_tage=[1, 2],
                  test_empfaenger=["t@example.com"],
                  maps_suche="IT", kontakt_rollen=["Inhaber"],
                  anbieter_reihenfolge=["impressum"],
                  wettbewerber_pruefung=True)
    leads, _, firmen_aus = source_leads(
        kunde, 10, "k", "k", "k",
        apify_source=_FakeApify([_firma("a.de")]),
        hunter_source=_FakeHunter(),
        dropcontact_source=_FakeDropcontact({"Otto": "otto.alt@a.de"}),
        impressum_quelle=impressum)
    assert [l.email for l in leads] == ["otto.alt@a.de"]
    assert lead_eligibility(leads[0]) == (True, "")
    assert firmen_aus[0]["offers_automation_services"] == "no"


# TEST 8 - kein Pruefer verfuegbar + info@ -> NICHT tauglich, nichts versendet
def test_8_ohne_pruefer_wird_info_nie_empfaenger():
    # Frueher wurde info@ hier UNGEPRUEFT zum Lead (Altlast) - jetzt
    # bleibt sie nur als ungepruefte Firmen-Information stehen.
    leads, _, firmen_aus = _lauf([person("Otto", "Alt", "Inhaber")], {},
                                 hunter=_HunterOhnePruefer())
    assert leads == []
    eintrag = firmen_aus[0]
    assert eintrag["ausgang"] == "ohne_persoenliche_mail"
    assert eintrag["info_email"] == "info@a.de"
    assert eintrag["info_pruefstatus"] == "ungeprueft"
    assert eintrag["campaign_eligible"] is False


# TEST 9 - Sammeladresse bleibt gespeichert, kommt aber nie in den
# Instantly-Import (letztes Tor schlaegt laut Alarm)
def test_9_instantly_import_stoppt_sammeladressen_laut():
    class _Kaputt(Exception):
        pass

    class _Sender(InstantlySender):
        def __init__(self):
            super().__init__("key")

        def _post(self, url, payload):
            self.payload = payload
            return {}

    sender = _Sender()
    texte = {"betreff": "B", "mail_1": "M",
             "follow_up_1": "F1", "follow_up_2": "F2"}
    with pytest.raises(ValueError) as fehler:
        sender.import_leads("c1", [{"email": "info@a.de", **texte},
                                   {"email": "otto.alt@a.de", **texte}])
    assert "Sammeladresse" in str(fehler.value)
    assert not hasattr(sender, "payload")      # NICHTS ging an Instantly

    # Nur persoenliche Adressen: der Import laeuft durch.
    sender.import_leads("c1", [{"email": "otto.alt@a.de", **texte}])
    assert [l["email"] for l in sender.payload["leads"]] == ["otto.alt@a.de"]

    # Auch der Anrede-Importweg kennt das Tor.
    with pytest.raises(ValueError):
        sender.import_leads_mit_anrede("c1", [
            {"email": "info@a.de", "anrede": "zusammen"}])

    # Ansichts-Probe an die EIGENE Adresse bleibt erlaubt.
    sender.import_leads("c1", [{"email": "info@meinefirma.de", **texte}],
                        eigene_adresse=True)
    assert [l["email"] for l in sender.payload["leads"]] == \
        ["info@meinefirma.de"]


# TEST 10 - alte Laufordner mit info@-Leads werden nicht veraendert;
# die Uebergabe filtert nur den Weg nach draussen
def test_10_alte_laufordner_bleiben_unangetastet(tmp_path, monkeypatch):
    from pipeline.__main__ import SendenFehler, _versand_ausfuehren
    from pipeline.run_store import RunStore

    monkeypatch.chdir(tmp_path)
    store = RunStore(tmp_path / "laeufe", "alt-kunde")
    texte = {"betreff": "B", "mail_1": "M",
             "follow_up_1": "F1", "follow_up_2": "F2"}
    store.save_step("pruefung_ok", [{"email": "info@a.de", **texte},
                                    {"email": "otto.alt@a.de", **texte}])
    (store.run_dir / "FREIGABE.txt").write_text("ok", encoding="utf-8")
    pruefung_datei = store.run_dir / "pruefung_ok.json"
    vorher = pruefung_datei.read_text(encoding="utf-8")

    class _Sender:
        def create_campaign(self, kunde, name=None, absender_emails=None,
                            betreffs=None):
            return "c1"

        def import_leads(self, campaign_id, texte_pro_lead, **_):
            self.importiert = [t["email"] for t in texte_pro_lead]
            return None

    kunde = Kunde(name="Alt", zielgruppe={}, angebot="A", tonalitaet="T",
                  absender="Ab", follow_up_tage=[1, 2],
                  test_empfaenger=["info@a.de", "otto.alt@a.de"],
                  versand_modus="echt")
    sender = _Sender()
    _versand_ausfuehren(store, sender, kunde=kunde)

    # Nur die persoenliche Adresse ging raus ...
    assert sender.importiert == ["otto.alt@a.de"]
    # ... die historische Freigabe-Datei ist unveraendert ...
    assert pruefung_datei.read_text(encoding="utf-8") == vorher
    # ... und der Ausschluss ist sichtbar festgehalten.
    ausgeschlossen = json.loads(
        (store.run_dir / "versand_ausgeschlossen.json").read_text(
            encoding="utf-8"))
    assert ausgeschlossen["emails"] == ["info@a.de"]

    # Besteht die Freigabe NUR aus Sammeladressen, bricht die Uebergabe
    # mit klarer Ansage ab.
    store2 = RunStore(tmp_path / "laeufe", "nur-info")
    store2.save_step("pruefung_ok", [{"email": "info@b.de", **texte}])
    (store2.run_dir / "FREIGABE.txt").write_text("ok", encoding="utf-8")
    with pytest.raises(SendenFehler):
        _versand_ausfuehren(store2, sender, kunde=kunde)


# Zusatz: der Filter vor der Text-Erzeugung (Schutz alter Laufordner)
def test_text_erzeugung_filtert_sammeladressen_aus_alten_laeufen():
    leads = [
        {"first_name": "", "last_name": "", "email": "info@a.de",
         "company": "A", "title": "", "website": "", "source": "info@",
         "notizen": []},
        {"first_name": "Otto", "last_name": "Alt",
         "email": "otto.alt@a.de", "company": "A", "title": "Inhaber",
         "website": "", "source": "impressum", "notizen": []},
    ]
    zulaessig, aussortiert = eligible_leads(leads)
    assert [l["email"] for l in zulaessig] == ["otto.alt@a.de"]
    assert aussortiert == [{"email": "info@a.de", "grund": "generic_email"}]
