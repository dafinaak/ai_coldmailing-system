"""Alle Namen in EINER Dropcontact-Anfrage statt fuenfzig Wartezeiten.

Dropcontact arbeitet mit Warteschleife: abgeben, Nummer bekommen,
nachfragen bis fertig - zehn bis dreissig Sekunden je Person. Bei fuenfzig
Firmen lagen fuenfzig solche Wartezeiten hintereinander und machten den
groessten Teil der Laufzeit aus (gemessen am 17.08.2026).

Geprueft wird, dass dabei nichts verlorengeht: gleiche Kontakte, gleiche
Zuordnung, gleicher Credit-Verbrauch - und dass ein Abbruch in der
Wartezeit nicht doppelt bezahlt wird.
"""
import json

import pytest

from pipeline.config import Kunde
from pipeline.sourcing import BatchSpeicher, source_leads


def _kunde():
    return Kunde(name="Probe", zielgruppe={"titel": ["Geschäftsführer"]},
                 angebot="A", tonalitaet="ruhig", absender="Oliver",
                 follow_up_tage=[7, 14], test_empfaenger=["ich@example.com"],
                 maps_suche="IT Hannover", kontakt_rollen=["Geschäftsführer"],
                 anbieter_reihenfolge=["impressum"])


class FakeApify:
    def __init__(self, firmen):
        self.firmen = firmen

    def search(self, suche, limit):
        return self.firmen


class FakeImpressum:
    def impressum_text(self, website):
        return "Impressum: Geschäftsführer"

    def entscheider_lesen(self, text, name, domain="", hinweis_name=""):
        nummer = "".join(c for c in domain if c.isdigit()) or "0"
        return {"personen": [{"vorname": "Max", "nachname": f"Muster{nummer}"}],
                "mail_domain": domain}


class BuendelDropcontact:
    """Zaehlt, wie oft wirklich abgegeben wurde."""

    def __init__(self, fehlt=(), fehler_beim_abholen=False):
        self.abgaben = []
        self.fehlt = set(fehlt)
        self.fehler_beim_abholen = fehler_beim_abholen
        self.abholungen = 0

    def batch_abgeben(self, anfragen):
        self.abgaben.append(list(anfragen))
        return f"auftrag-{len(self.abgaben)}", list(anfragen)

    def batch_abholen(self, request_id, gesendet, gesamt=None):
        self.abholungen += 1
        if self.fehler_beim_abholen:
            raise RuntimeError("Dropcontact liefert kein Ergebnis")
        return [None if a["last_name"] in self.fehlt else
                {"email": f"{a['last_name'].lower()}@{a['company']}.de",
                 "qualification": "nominative@pro"}
                for a in gesendet]


def _firmen(anzahl):
    return [{"name": f"firma{i}", "website": f"https://firma{i}.de",
             "domain": f"firma{i}.de"} for i in range(anzahl)]


def _lauf(firmen, dropcontact, **rest):
    return source_leads(_kunde(), limit=len(firmen), apify_key="k",
                        hunter_key="k", dropcontact_key="k",
                        apify_source=FakeApify(firmen), hunter_source=object(),
                        dropcontact_source=dropcontact,
                        impressum_quelle=FakeImpressum(), **rest)


def test_alle_namen_gehen_in_einer_anfrage_raus():
    dc = BuendelDropcontact()

    leads, deckung, _ = _lauf(_firmen(10), dc)

    assert len(dc.abgaben) == 1, "es wurde mehr als einmal abgegeben"
    assert len(dc.abgaben[0]) == 10
    assert len(leads) == 10
    assert deckung["firmen_mit_kontakt"] == 10


def test_jede_adresse_landet_bei_ihrer_firma():
    # Die groesste Gefahr beim Buendeln: verrutschte Zuordnung.
    dc = BuendelDropcontact()

    leads, _, _ = _lauf(_firmen(5), dc)

    for lead in leads:
        assert lead.company in lead.email, f"{lead.email} passt nicht zu {lead.company}"


def test_reihenfolge_bleibt_die_der_firmenliste():
    leads, _, _ = _lauf(_firmen(6), BuendelDropcontact())

    assert [l.company for l in leads] == [f"firma{i}" for i in range(6)]


def test_die_anfrage_selbst_ist_reproduzierbar():
    # Die Namen kommen aus parallelen Threads. Zwei gleiche Laeufe sollen
    # trotzdem dieselbe Anfrage erzeugen - sonst ist ein Fehler nicht
    # nachstellbar.
    dc = BuendelDropcontact()
    _lauf(_firmen(8), dc)

    assert [a["last_name"] for a in dc.abgaben[0]] == \
        [f"Muster{i}" for i in range(8)]


def test_firmen_ohne_treffer_fallen_auf_info_zurueck():
    # Wer keine persoenliche Adresse bekommt, geht nicht verloren, sondern
    # faellt auf info@ - genau wie auf dem alten, ungebuendelten Weg.
    dc = BuendelDropcontact(fehlt=["Muster2", "Muster4"])

    leads, deckung, firmen_mit_ausgang = _lauf(_firmen(5), dc)

    persoenlich = [l for l in leads if l.source == "impressum"]
    assert len(persoenlich) == 3
    assert {l.email for l in leads if l.source == "info@"} == {
        "info@firma2.de", "info@firma4.de"}
    ausgaenge = {f["name"]: f["ausgang"] for f in firmen_mit_ausgang}
    assert ausgaenge["firma2"] == "info_fallback"
    assert deckung["je_stufe"]["impressum"] == 3


def test_alte_quellen_ohne_buendelung_gehen_weiter():
    # Aeltere Quellen kennen nur email_bauen - dann eben einzeln.
    class NurEinzeln:
        def __init__(self):
            self.aufrufe = 0

        def email_bauen(self, vorname, nachname, website, company=""):
            self.aufrufe += 1
            return {"email": f"{nachname.lower()}@{company}.de",
                    "qualification": "nominative@pro"}

    dc = NurEinzeln()
    leads, _, _ = _lauf(_firmen(3), dc)

    assert dc.aufrufe == 3
    assert len(leads) == 3


# --- Abbruchfestigkeit ----------------------------------------------------

def test_offener_auftrag_wird_gemerkt(tmp_path):
    # Zwischen Abgeben und Abholen sind die Credits bezahlt. Stirbt der
    # Lauf dort, muss die Auftragsnummer auf der Platte liegen.
    class StirbtBeimAbholen(BuendelDropcontact):
        def batch_abholen(self, request_id, gesendet, gesamt=None):
            raise KeyboardInterrupt("Lauf abgebrochen")

    with pytest.raises(KeyboardInterrupt):
        _lauf(_firmen(3), StirbtBeimAbholen(), lauf_dir=tmp_path)

    gemerkt = json.loads((tmp_path / "dropcontact-offen.json").read_text())
    assert gemerkt["request_id"] == "auftrag-1"
    assert gemerkt["anzahl"] == 3


def test_gemerkter_auftrag_wird_abgeholt_statt_neu_bezahlt(tmp_path):
    BatchSpeicher(tmp_path).schreiben({
        "request_id": "auftrag-alt",
        "gesendet": [{"first_name": "Max", "last_name": f"Muster{i}",
                      "website": f"https://firma{i}.de", "company": f"firma{i}"}
                     for i in range(3)],
        "anzahl": 3})
    dc = BuendelDropcontact()

    leads, _, _ = _lauf(_firmen(3), dc, lauf_dir=tmp_path)

    assert dc.abgaben == [], "es wurde noch einmal bezahlt"
    assert len(leads) == 3


def test_merkzettel_wird_nach_erfolg_geloescht(tmp_path):
    _lauf(_firmen(2), BuendelDropcontact(), lauf_dir=tmp_path)

    assert not (tmp_path / "dropcontact-offen.json").exists()


def test_unbrauchbarer_merkzettel_blockiert_nicht(tmp_path):
    BatchSpeicher(tmp_path).schreiben({"request_id": "tot", "gesendet": [],
                                        "anzahl": 2})
    dc = BuendelDropcontact()

    leads, _, _ = _lauf(_firmen(2), dc, lauf_dir=tmp_path)

    # Die alte Nummer passte nicht zur Anzahl - also neu abgeben statt raten.
    assert len(dc.abgaben) == 1
    assert len(leads) == 2
