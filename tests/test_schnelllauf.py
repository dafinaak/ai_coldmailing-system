"""The fast runner has to behave exactly like grosslauf, only quicker.

What is pinned here: the cascade outcomes stay the same, the info@ rule
still runs through Hunter, finished companies are not paid for twice, and
- the reason the rounds exist at all - a company whose first manager
already yielded an address never gets billed for its second one.
"""
import pytest

from pipeline.config import Kunde
from pipeline.schnelllauf import lauf_ausfuehren


class FakeImpressum:
    """Returns the managers we prepared per domain."""
    def __init__(self, nach_domain, kaputt=()):
        self.nach_domain, self.kaputt = nach_domain, set(kaputt)
        self.gelesen = []

    def impressum_text(self, website):
        return f"text von {website}"

    def entscheider_lesen(self, text, firmenname, domain="", hinweis_name=""):
        self.gelesen.append(domain)
        if domain in self.kaputt:
            raise RuntimeError("Webseite antwortet nicht")
        return self.nach_domain.get(domain, {"personen": [], "mail_domain": None})


class FakeDropcontact:
    """Hands out addresses for the names we listed; records every batch.

    Mirrors the two-step contract of the real source: handing a batch
    over is what costs a credit, fetching it is free.
    """
    def __init__(self, adressen):
        self.adressen, self.batches = adressen, []
        self._offen, self._zaehler = {}, 0

    def batch_abgeben(self, anfragen):
        gesendet = [(nr, a) for nr, a in enumerate(anfragen)
                    if a.get("first_name") and a.get("last_name")]
        if not gesendet:
            return None, []
        self._zaehler += 1
        request_id = f"r{self._zaehler}"
        self.batches.append([f"{a['first_name']} {a['last_name']}"
                             for _, a in gesendet])
        self._offen[request_id] = gesendet
        return request_id, gesendet

    def _mail(self, anfrage):
        schluessel = f"{anfrage['first_name']} {anfrage['last_name']}"
        if schluessel not in self.adressen:
            return None
        return {"email": self.adressen[schluessel], "qualification": "nominative@pro"}

    def batch_abholen(self, request_id, gesendet, gesamt=None):
        ergebnisse = [None] * (gesamt if gesamt is not None else len(gesendet))
        for nr, anfrage in gesendet:
            ergebnisse[nr] = self._mail(anfrage)
        return ergebnisse

    def zeilen_holen(self, request_id):
        return [{"first_name": a["first_name"], "last_name": a["last_name"],
                 "website": a.get("website"), "email": []}
                for _, a in self._offen[request_id]]


class FakeHunter:
    def __init__(self, status="valid"):
        self.status, self.geprueft = status, []

    def email_pruefen(self, email):
        self.geprueft.append(email)
        return {"status": self.status}


KUNDE = Kunde(name="Test", zielgruppe={}, angebot="-", tonalitaet="-",
              absender="-", follow_up_tage=[3, 7],
              test_empfaenger=["test@example.com"],
              maps_suche="(Liste)", kontakt_rollen=["Geschäftsführer"],
              anbieter_reihenfolge=["impressum"])


def firma(name, domain):
    return {"name": name, "domain": domain, "website": f"https://{domain}"}


def person(vorname, nachname):
    return {"vorname": vorname, "nachname": nachname}


def test_findet_persoenliche_mails_fuer_die_ganze_liste():
    firmen = [firma("A GmbH", "a.de"), firma("B GmbH", "b.de")]
    impressum = FakeImpressum({
        "a.de": {"personen": [person("Anna", "Muster")], "mail_domain": None},
        "b.de": {"personen": [person("Bernd", "Beispiel")], "mail_domain": None}})
    dropcontact = FakeDropcontact({"Anna Muster": "anna@a.de",
                                   "Bernd Beispiel": "bernd@b.de"})

    ergebnisse = lauf_ausfuehren(firmen, KUNDE, dropcontact, impressum,
                                 FakeHunter(), arbeiter=2, fortschritt=lambda _: None)

    assert [e["ausgang"] for e in ergebnisse] == ["mit_entscheider"] * 2
    assert [e["leads"][0]["email"] for e in ergebnisse] == ["anna@a.de", "bernd@b.de"]
    assert ergebnisse[0]["stufe"] == "impressum"


def test_alle_personen_einer_runde_gehen_in_einer_anfrage_raus():
    firmen = [firma(f"F{i}", f"f{i}.de") for i in range(5)]
    impressum = FakeImpressum({
        f"f{i}.de": {"personen": [person("Vor", f"Nach{i}")], "mail_domain": None}
        for i in range(5)})
    dropcontact = FakeDropcontact({f"Vor Nach{i}": f"m{i}@f{i}.de" for i in range(5)})

    lauf_ausfuehren(firmen, KUNDE, dropcontact, impressum, FakeHunter(),
                    arbeiter=4, fortschritt=lambda _: None)

    assert len(dropcontact.batches) == 1
    assert len(dropcontact.batches[0]) == 5


def test_zweiter_chef_wird_nur_bei_bedarf_gefragt():
    # Die Kostenregel: A findet gleich beim ersten Namen eine Adresse und
    # darf den zweiten NICHT mehr kosten. B braucht den zweiten wirklich.
    firmen = [firma("A GmbH", "a.de"), firma("B GmbH", "b.de")]
    impressum = FakeImpressum({
        "a.de": {"personen": [person("Anna", "Muster"), person("Alt", "Zweit")],
                 "mail_domain": None},
        "b.de": {"personen": [person("Bernd", "Leer"), person("Berta", "Zweit")],
                 "mail_domain": None}})
    dropcontact = FakeDropcontact({"Anna Muster": "anna@a.de",
                                   "Berta Zweit": "berta@b.de"})

    ergebnisse = lauf_ausfuehren(firmen, KUNDE, dropcontact, impressum,
                                 FakeHunter(), arbeiter=2, fortschritt=lambda _: None)

    assert dropcontact.batches[0] == ["Anna Muster", "Bernd Leer"]
    assert dropcontact.batches[1] == ["Berta Zweit"]        # nur B, nicht A
    assert "Alt Zweit" not in [n for b in dropcontact.batches for n in b]
    assert [e["leads"][0]["email"] for e in ergebnisse] == ["anna@a.de", "berta@b.de"]


def test_ohne_persoenliche_mail_kommt_geprueftes_info_at():
    firmen = [firma("A GmbH", "a.de")]
    impressum = FakeImpressum({"a.de": {"personen": [], "mail_domain": None}})
    hunter = FakeHunter(status="valid")

    ergebnisse = lauf_ausfuehren(firmen, KUNDE, FakeDropcontact({}), impressum,
                                 hunter, arbeiter=1, fortschritt=lambda _: None)

    assert hunter.geprueft == ["info@a.de"]
    # Kampagnen-Regel (20.08.2026): geprueft und GESPEICHERT - nie Lead.
    assert ergebnisse[0]["ausgang"] == "ohne_persoenliche_mail"
    assert ergebnisse[0]["leads"] == []
    assert ergebnisse[0]["info_email"] == "info@a.de"
    assert ergebnisse[0]["info_pruefstatus"] == "valid"
    assert ergebnisse[0]["campaign_eligible"] is False


def test_nicht_zustellbares_info_at_wird_verworfen():
    firmen = [firma("A GmbH", "a.de")]
    impressum = FakeImpressum({"a.de": {"personen": [], "mail_domain": None}})

    ergebnisse = lauf_ausfuehren(firmen, KUNDE, FakeDropcontact({}), impressum,
                                 FakeHunter(status="invalid"), arbeiter=1,
                                 fortschritt=lambda _: None)

    assert ergebnisse[0]["ausgang"] == "info_ungueltig"
    assert ergebnisse[0]["leads"] == []


def test_kaputte_webseite_reisst_den_lauf_nicht_mit():
    firmen = [firma("A GmbH", "a.de"), firma("B GmbH", "b.de")]
    impressum = FakeImpressum(
        {"b.de": {"personen": [person("Bernd", "Beispiel")], "mail_domain": None}},
        kaputt=["a.de"])
    dropcontact = FakeDropcontact({"Bernd Beispiel": "bernd@b.de"})

    ergebnisse = lauf_ausfuehren(firmen, KUNDE, dropcontact, impressum,
                                 FakeHunter(), arbeiter=2, fortschritt=lambda _: None)

    assert ergebnisse[0]["ausgang"] == "fehler"
    assert ergebnisse[1]["ausgang"] == "mit_entscheider"


def test_fertige_firmen_werden_nicht_noch_einmal_bezahlt():
    firmen = [firma("A GmbH", "a.de"), firma("B GmbH", "b.de")]
    fertig = {**firma("A GmbH", "a.de"), "ausgang": "mit_entscheider",
              "stufe": "impressum",
              "leads": [{"first_name": "Anna", "last_name": "Muster",
                         "email": "anna@a.de", "company": "A GmbH", "title": "",
                         "website": "https://a.de", "source": "impressum",
                         "notizen": []}]}
    impressum = FakeImpressum({
        "b.de": {"personen": [person("Bernd", "Beispiel")], "mail_domain": None}})
    dropcontact = FakeDropcontact({"Bernd Beispiel": "bernd@b.de"})

    ergebnisse = lauf_ausfuehren(firmen, KUNDE, dropcontact, impressum,
                                 FakeHunter(), vorhandene=[fertig], arbeiter=2,
                                 fortschritt=lambda _: None)

    assert impressum.gelesen == ["b.de"]                    # A nicht neu gelesen
    assert dropcontact.batches == [["Bernd Beispiel"]]      # A nicht neu bezahlt
    assert ergebnisse[0]["leads"][0]["email"] == "anna@a.de"
    assert ergebnisse[1]["leads"][0]["email"] == "bernd@b.de"


def test_abweichende_mail_domain_wird_benutzt():
    firmen = [firma("A GmbH", "a.de")]
    impressum = FakeImpressum({
        "a.de": {"personen": [person("Anna", "Muster")], "mail_domain": "andere.de"}})
    dropcontact = FakeDropcontact({"Anna Muster": "anna@andere.de"})

    lauf_ausfuehren(firmen, KUNDE, dropcontact, impressum, FakeHunter(),
                    arbeiter=1, fortschritt=lambda _: None)

    assert dropcontact.batches == [["Anna Muster"]]
