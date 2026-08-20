"""Entscheider mit Prioritaet und Rolle (Olivers Vorgabe, 19.08.2026).

Die Kontaktsuche darf keinen zufaelligen Mitarbeiter liefern: CEO/GF vor
Inhaber vor Gruender vor Managing Director vor sonstiger Leitung. Der
beste Fund ist der PRIMAERE Entscheider und steht am Firmensatz - auch
dann, wenn fuer ihn keine Adresse geprueft werden konnte. Firmen ganz
ohne Fund bleiben im System ("kein_entscheider"), wie bisher.
"""
from pipeline.config import Kunde
from pipeline.decision_maker import (build_entscheider, rank_role,
                                     sort_by_priority)
from pipeline.sourcing import source_leads
from pipeline.sources.impressum import ImpressumQuelle


class _FakeApify:
    def __init__(self, firmen):
        self._firmen = firmen

    def search(self, suchbegriff, limit):
        return self._firmen[:limit]


class _FakeHunter:
    def entscheider_finden(self, domain, limit=10):
        return []


class _FakeDropcontact:
    def __init__(self, mail_je_vorname=None):
        self._mails = mail_je_vorname or {}
        self.aufrufe = []

    def email_bauen(self, first_name, last_name, website, company=""):
        self.aufrufe.append((first_name, last_name, website))
        wert = self._mails.get(first_name)
        return {"email": wert} if wert else None


class _FakeImpressum:
    def __init__(self, texte=None, ergebnisse=None):
        self.texte = texte or {}
        self.ergebnisse = ergebnisse or {}

    def impressum_text(self, website):
        return self.texte.get(website)

    def entscheider_lesen(self, text, firmenname, domain="", hinweis_name=""):
        return self.ergebnisse.get(domain,
                                   {"personen": [], "mail_domain": None})


def _kunde():
    return Kunde(name="Demo", zielgruppe={}, angebot="A", tonalitaet="T",
                 absender="Ab", follow_up_tage=[1, 2],
                 test_empfaenger=["t@example.com"],
                 maps_suche="IT-Dienstleister Hannover",
                 kontakt_rollen=["Geschäftsführer"],
                 anbieter_reihenfolge=["impressum"])


def _firma(domain):
    return {"name": domain, "website": f"https://{domain}", "domain": domain,
            "address": "", "categories": []}


def person(vor, nach, rolle="", linkedin=None):
    return {"vorname": vor, "nachname": nach, "rolle": rolle,
            "linkedin": linkedin}


# --- Rangfolge -------------------------------------------------------------

def test_rangfolge_inhaber_vor_ceo_vor_gf_vor_gruender_vor_leitung():
    # Olivers Reihenfolge vom 19.08.2026 (abends): Owner/Inhaber zuerst.
    raenge = [rank_role(r) for r in (
        "Inhaberin", "Owner", "CEO", "Geschäftsführer", "Managing Director",
        "Gründer", "Co-Founder", "Vorstand", "")]
    assert raenge == [0, 0, 1, 2, 2, 3, 3, 4, 5]
    assert rank_role("Geschäftsführender Gesellschafter") == 2


def test_sortierung_stellt_den_besten_nach_vorn_und_bleibt_stabil():
    personen = [person("Ines", "Beck", "Prokuristin"),
                person("Gerd", "Chef", "Geschäftsführer"),
                person("Otto", "Alt", "Inhaber"),
                person("Zoe", "Zwei", "Geschäftsführerin")]
    sortiert = sort_by_priority(personen)
    assert [p["vorname"] for p in sortiert] == ["Otto", "Gerd", "Zoe", "Ines"]


# --- Firmensatz ------------------------------------------------------------

def test_firmensatz_haelt_alle_entscheider_und_markiert_den_primaeren():
    satz = build_entscheider(
        [person("Gerd", "Chef", "Geschäftsführer"),
         person("Otto", "Alt", "Inhaber")],
        [{"first_name": "Gerd", "last_name": "Chef", "email": "chef@a.de",
          "title": "Geschäftsführer (laut Impressum)", "source": "impressum"}])
    assert [e["name"] for e in satz] == ["Otto Alt", "Gerd Chef"]
    assert satz[0]["status"] == "ohne_mail"          # bester Rang = primaer
    assert satz[1]["status"] == "mail_geprueft"
    assert satz[1]["email"] == "chef@a.de"


def test_kontakt_ohne_impressum_fund_wird_zum_satz():
    satz = build_entscheider([], [{
        "first_name": "Anna", "last_name": "Muster", "email": "a@b.de",
        "title": "Geschäftsführerin", "source": "hunter"}])
    assert satz[0]["name"] == "Anna Muster"
    assert satz[0]["status"] == "mail_geprueft"
    assert satz[0]["quelle"] == "hunter"


def test_info_adresse_ist_keine_person():
    assert build_entscheider([], [{
        "first_name": "", "last_name": "", "email": "info@b.de",
        "title": "", "source": "info@"}]) == []


# --- Impressum-Lesen liefert Rolle und LinkedIn ---------------------------

class _RolleKI:
    def frage(self, system, prompt):
        return ('{"personen": [{"vorname": "Nadine", "nachname": "Pelaccia",'
                ' "rolle": "Inhaberin",'
                ' "linkedin": "https://www.linkedin.com/in/np"},'
                ' {"vorname": "Falsch", "nachname": "Profil",'
                ' "rolle": "Geschäftsführer", "linkedin": "np-linkedin"}],'
                ' "mail_domain": null}')


def test_impressum_lesen_uebernimmt_rolle_und_prueft_linkedin():
    quelle = ImpressumQuelle(ki=_RolleKI())
    ergebnis = quelle.entscheider_lesen("Impressum ...", "A GmbH")
    personen = ergebnis["personen"]
    assert personen[0]["rolle"] == "Inhaberin"
    assert personen[0]["linkedin"] == "https://www.linkedin.com/in/np"
    # "np-linkedin" ist keine URL - lieber nichts als etwas Erfundenes.
    assert personen[1]["linkedin"] is None


# --- Ende-zu-Ende ueber source_leads (Weg des Formulars) ------------------

def _lauf(ergebnisse, mails):
    firmen = [_firma("a.de")]
    impressum = _FakeImpressum(texte={"https://a.de": "Impressum ..."},
                               ergebnisse=ergebnisse)
    return source_leads(
        _kunde(), 10, "k", "k", "k", apify_source=_FakeApify(firmen),
        hunter_source=_FakeHunter(),
        dropcontact_source=_FakeDropcontact(mails),
        impressum_quelle=impressum)


def test_bester_rang_bekommt_den_ersten_bezahlten_adressbau():
    # Inhaber schlaegt Geschaeftsfuehrer (Olivers Reihenfolge, abends).
    leads, _, firmen_aus = _lauf(
        {"a.de": {"personen": [person("Gerd", "Chef", "Geschäftsführer"),
                               person("Otto", "Alt", "Inhaber")],
                  "mail_domain": None}},
        {"Otto": "alt@a.de"})
    assert [l.email for l in leads] == ["alt@a.de"]
    assert leads[0].title == "Inhaber (laut Impressum)"
    satz = firmen_aus[0]["entscheider"]
    assert firmen_aus[0]["entscheider_primaer"]["name"] == "Otto Alt"
    assert satz[0]["status"] == "mail_geprueft"
    assert (satz[1]["name"], satz[1]["status"]) == ("Gerd Chef", "ohne_mail")


def test_person_ohne_gepruefte_mail_bleibt_am_firmensatz():
    # Firma mit Domain: sie faellt in die info@-Regel - aber der gelesene
    # Chef-Name muss trotzdem am Firmensatz stehen, nicht verschwinden.
    leads, _, firmen_aus = _lauf(
        {"a.de": {"personen": [person("Gerd", "Chef", "Geschäftsführer")],
                  "mail_domain": None}},
        {})      # Dropcontact findet nichts
    assert [l.source for l in leads] == ["info@"]
    eintrag = firmen_aus[0]
    assert eintrag["ausgang"] == "info_fallback"
    assert eintrag["entscheider_primaer"]["name"] == "Gerd Chef"
    assert eintrag["entscheider_primaer"]["status"] == "ohne_mail"


def test_firma_ohne_domain_und_ohne_fund_bleibt_im_system():
    firmen = [{"name": "A GmbH", "website": "https://a.de", "domain": "",
               "address": "", "categories": []}]
    impressum = _FakeImpressum(texte={"https://a.de": "Impressum ..."},
                               ergebnisse={})
    _, _, firmen_aus = source_leads(
        _kunde(), 10, "k", "k", "k", apify_source=_FakeApify(firmen),
        hunter_source=_FakeHunter(),
        dropcontact_source=_FakeDropcontact({}),
        impressum_quelle=impressum)
    assert firmen_aus[0]["ausgang"] == "kein_entscheider"
    assert "entscheider" not in firmen_aus[0]
