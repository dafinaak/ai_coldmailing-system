"""Campaign runs ask the Dropcontact register before paying (Jira AP-216).

The zone tool is one of four places that pay Dropcontact. The campaign
path pays in three more: one bundled request for all imprint names, one
person at a time when several stages run, and the fast runner. All of
them look into the register first. A person found before is not sent
again - the address is taken over with a note where it came from, and a
source that the register itself never reads back, so an old check never
gets a new date. A person asked before without a result is not asked
again.
"""
from datetime import date

from pipeline.config import Kunde
from pipeline.dropcontact_register import REUSED_SOURCE, Register, person_key
from pipeline.schnelllauf import Zwischenstand, lauf_ausfuehren
from pipeline.sourcing import source_leads

RUN = "zona33-dropcontact-2026-08-28"


def _register(found=(), asked=()):
    register = Register()
    for last in found:
        register.add(person_key("Max", last, f"https://{last.lower()}.de"),
                     date.today(), f"max@{last.lower()}.de", RUN)
    for last in asked:
        register.add(person_key("Max", last, f"https://{last.lower()}.de"),
                     date.today(), None, RUN)
    return register


def _kunde(order):
    return Kunde(name="Probe", zielgruppe={"titel": ["Geschäftsführer"]},
                 angebot="A", tonalitaet="ruhig", absender="Oliver",
                 follow_up_tage=[7, 14], test_empfaenger=["ich@example.com"],
                 maps_suche="IT Hannover", kontakt_rollen=["Geschäftsführer"],
                 anbieter_reihenfolge=order)


# Company "a" at a.de has one manager, Max A - and so on.
def _firmen(*names):
    return [{"name": name, "website": f"https://{name}.de",
             "domain": f"{name}.de"} for name in names]


class FakeApify:
    def __init__(self, firmen):
        self.firmen = firmen

    def search(self, suche, limit):
        return self.firmen


class FakeImpressum:
    def impressum_text(self, website):
        return "Impressum: Geschäftsführer"

    def entscheider_lesen(self, text, name, domain="", hinweis_name=""):
        return {"personen": [{"vorname": "Max",
                              "nachname": domain.split(".")[0].upper()}],
                "mail_domain": domain}


class FakeHunter:
    def entscheider_finden(self, domain):
        return []


class FakeDropcontact:
    """Answers everything it is asked - and remembers whom it was paid for."""

    def __init__(self):
        self.paid_for = []

    def _mail(self, request):
        return {"email": f"neu.{request['last_name'].lower()}@firma.de",
                "qualification": "nominative@pro"}

    def batch_abgeben(self, anfragen):
        self.paid_for += [a["last_name"] for a in anfragen]
        return "r1", list(enumerate(anfragen))

    def batch_abholen(self, request_id, gesendet, gesamt=None):
        return [self._mail(a) for _, a in gesendet]

    def email_bauen(self, first_name, last_name, website, company=""):
        self.paid_for.append(last_name)
        return self._mail({"last_name": last_name})

    def zeilen_holen(self, request_id):
        return []


def _campaign(order, firmen, dropcontact, register):
    leads, _, _ = source_leads(
        _kunde(order), limit=len(firmen), apify_key="k", hunter_key="k",
        dropcontact_key="k", apify_source=FakeApify(firmen),
        hunter_source=FakeHunter(), dropcontact_source=dropcontact,
        impressum_quelle=FakeImpressum(), register=register)
    return {lead.company: lead for lead in leads}


def test_bundled_request_leaves_out_a_person_found_before():
    dc = FakeDropcontact()

    leads = _campaign(["impressum"], _firmen("a", "b", "c"), dc,
                      _register(found=["A"]))

    assert dc.paid_for == ["B", "C"]
    assert leads["a"].email == "max@a.de"
    assert leads["a"].source == REUSED_SOURCE
    assert any(RUN in note for note in leads["a"].notizen)
    assert leads["b"].email == "neu.b@firma.de"


def test_bundled_request_does_not_ask_again_who_had_no_result():
    dc = FakeDropcontact()

    leads = _campaign(["impressum"], _firmen("a", "b"), dc,
                      _register(asked=["A"]))

    assert dc.paid_for == ["B"]
    assert "a" not in leads


def test_no_request_at_all_when_everyone_is_known():
    dc = FakeDropcontact()

    leads = _campaign(["impressum"], _firmen("a", "b"), dc,
                      _register(found=["A", "B"]))

    assert dc.paid_for == []
    assert sorted(leads) == ["a", "b"]


def test_one_by_one_stages_look_into_the_register_too():
    # Two stages: the imprint stage asks one person at a time.
    dc = FakeDropcontact()

    leads = _campaign(["impressum", "hunter_dropcontact"],
                      _firmen("a", "b"), dc, _register(found=["A"]))

    assert dc.paid_for == ["B"]
    assert leads["a"].email == "max@a.de"
    assert leads["a"].source == REUSED_SOURCE


def test_the_old_company_by_company_runner_passes_the_register_on():
    from pipeline.grosslauf import lauf_ausfuehren as grosslauf
    dc = FakeDropcontact()

    ergebnisse = grosslauf(_firmen("a", "b"), _kunde(["impressum"]), None, dc,
                           FakeImpressum(), hunter=FakeHunter(),
                           fortschritt=lambda _: None,
                           register=_register(found=["A"]))

    assert dc.paid_for == ["B"]
    assert ergebnisse[0]["leads"][0]["email"] == "max@a.de"


def test_fast_runner_does_not_pay_for_a_person_found_before(tmp_path):
    dc = FakeDropcontact()

    ergebnisse = lauf_ausfuehren(
        _firmen("a", "b"), _kunde(["impressum"]), dc, FakeImpressum(),
        lauf_dir=tmp_path, fortschritt=lambda _: None,
        register=_register(found=["A"]))

    assert dc.paid_for == ["B"]
    lead = ergebnisse[0]["leads"][0]
    assert lead["email"] == "max@a.de"
    assert lead["source"] == REUSED_SOURCE
    # The cache keeps only what this run paid for - a reused address
    # written there would get this run's date and outlive its 90 days.
    assert list(Zwischenstand(tmp_path).adressen) == ["max|b|b.de"]
