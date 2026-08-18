"""Die info@-Prüfung läuft über Dropcontact statt über Hunter.

Hunters Freikontingent ist zu klein für unsere Arbeitsweise: am 17.08.2026
fielen dadurch 23 von 50 Firmen aus einer Kampagne heraus. Dropcontact kann
dieselbe Frage beantworten und ist bezahlt - gemessen am selben Tag:

    info@bundesweit.digital  -> "generic@pro", Adresse kommt zurück
    quatschpostfach999@…     -> "invalid@pro", Adresse leer

Alle Adressen gehen in EINER Anfrage raus, nicht einzeln.
"""
import pytest

from pipeline.config import Kunde
from pipeline.sources.dropcontact import _pruefurteil
from pipeline.sourcing import source_leads


def _kunde():
    return Kunde(name="Probe", zielgruppe={"titel": ["Geschäftsführer"]},
                 angebot="A", tonalitaet="ruhig", absender="Oliver",
                 follow_up_tage=[7, 14], test_empfaenger=["ich@example.com"],
                 maps_suche="IT Hannover", kontakt_rollen=["Geschäftsführer"],
                 anbieter_reihenfolge=["impressum"])


class OhneImpressum:
    """Findet nie einen Namen - so greift immer die info@-Regel."""

    def impressum_text(self, website):
        return None

    def entscheider_lesen(self, *a, **k):
        return {"personen": []}


class PruefenderDropcontact:
    def __init__(self, urteile=None, fehler=None):
        self.urteile = urteile or {}
        self.fehler = fehler
        self.anfragen = []

    def adressen_pruefen(self, adressen):
        self.anfragen.append(list(adressen))
        if self.fehler:
            raise RuntimeError(self.fehler)
        return [{"status": self.urteile.get(a, "gueltig"), "qualification": ""}
                for a in adressen]


class FakeApify:
    def __init__(self, firmen):
        self.firmen = firmen

    def search(self, suche, limit):
        return self.firmen


def _firmen(anzahl):
    return [{"name": f"firma{i}", "website": f"https://firma{i}.de",
             "domain": f"firma{i}.de"} for i in range(anzahl)]


def _lauf(firmen, dropcontact, hunter=None):
    return source_leads(_kunde(), limit=len(firmen), apify_key="k",
                        hunter_key="k", dropcontact_key="k",
                        apify_source=FakeApify(firmen),
                        hunter_source=hunter or object(),
                        dropcontact_source=dropcontact,
                        impressum_quelle=OhneImpressum())


# --- Das Urteil selbst ----------------------------------------------------

def test_echte_info_adresse_gilt_als_gueltig():
    zeile = {"email": [{"email": "info@firma.de", "qualification": "generic@pro"}]}

    assert _pruefurteil(zeile)["status"] == "gueltig"


def test_erfundene_adresse_gilt_als_ungueltig():
    zeile = {"email": [{"email": "", "qualification": "invalid@pro"}]}

    assert _pruefurteil(zeile)["status"] == "ungueltig"


def test_persoenliche_adresse_gilt_auch_als_gueltig():
    # Nicht auf "generic" einengen: entscheidend ist nur, dass Dropcontact
    # die Adresse kennt und nicht als ungueltig ausweist.
    zeile = {"email": [{"email": "max@firma.de", "qualification": "nominative@pro"}]}

    assert _pruefurteil(zeile)["status"] == "gueltig"


def test_gar_keine_antwort_heisst_nicht_versenden():
    assert _pruefurteil({})["status"] == "ungueltig"
    assert _pruefurteil({"email": []})["status"] == "ungueltig"


# --- Im Lauf --------------------------------------------------------------

def test_alle_info_adressen_in_einer_anfrage():
    dc = PruefenderDropcontact()

    leads, _, _ = _lauf(_firmen(8), dc)

    assert len(dc.anfragen) == 1, "es wurde mehr als einmal gefragt"
    assert len(dc.anfragen[0]) == 8
    assert len(leads) == 8


def test_gueltige_gehen_raus_ungueltige_nicht():
    dc = PruefenderDropcontact(urteile={"info@firma1.de": "ungueltig",
                                         "info@firma3.de": "ungueltig"})

    leads, deckung, firmen_mit_ausgang = _lauf(_firmen(5), dc)

    assert {l.email for l in leads} == {"info@firma0.de", "info@firma2.de",
                                         "info@firma4.de"}
    ausgaenge = {f["name"]: f["ausgang"] for f in firmen_mit_ausgang}
    assert ausgaenge["firma1"] == "info_ungueltig"
    assert deckung["je_stufe"]["info@"] == 3


def test_hunter_wird_gar_nicht_mehr_gefragt():
    class HunterDerSchreit:
        def email_pruefen(self, email):
            raise AssertionError("Hunter darf hier nicht mehr gefragt werden")

    leads, _, _ = _lauf(_firmen(3), PruefenderDropcontact(),
                        hunter=HunterDerSchreit())

    assert len(leads) == 3


def test_gescheiterte_pruefung_laesst_niemanden_durch():
    # Zuverlaessigkeit zuerst: ungeprueft heisst nicht versenden.
    dc = PruefenderDropcontact(fehler="Dropcontact antwortet mit 402")

    leads, _, firmen_mit_ausgang = _lauf(_firmen(4), dc)

    assert leads == []
    assert all(f["ausgang"] == "fehler" for f in firmen_mit_ausgang)
    # Der Grund muss beim Menschen ankommen, nicht nur im Protokoll.
    assert firmen_mit_ausgang[0]["fehler_grund"]


def test_quelle_ohne_pruefung_faellt_auf_hunter_zurueck():
    class NurEinzeln:
        def email_bauen(self, *a, **k):
            return None

    class HunterMitKontingent:
        def __init__(self):
            self.gefragt = []

        def email_pruefen(self, email):
            self.gefragt.append(email)
            return {"status": "valid", "score": 90}

    hunter = HunterMitKontingent()
    leads, _, _ = _lauf(_firmen(3), NurEinzeln(), hunter=hunter)

    assert hunter.gefragt == ["info@firma0.de", "info@firma1.de", "info@firma2.de"]
    assert len(leads) == 3
