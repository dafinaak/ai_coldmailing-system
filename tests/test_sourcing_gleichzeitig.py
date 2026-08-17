"""Die Firmen-Suche muss mehrere Firmen gleichzeitig bearbeiten.

Gemessen am 14.08.2026: ein Lauf ueber 50 Firmen brauchte rund elf Minuten
und verbrauchte dabei 1,9 Sekunden Rechenzeit. 99,7 % der Zeit stand das
Programm still und wartete auf fremde Webserver - nacheinander. Genau diese
Wartezeit laesst sich teilen.

Geprueft wird beides: dass wirklich parallel gearbeitet wird UND dass
Reihenfolge, Zaehlung und Fehlerbehandlung dabei unveraendert bleiben.
"""
import threading
import time

import pytest

from pipeline.config import Kunde
from pipeline.sourcing import source_leads


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


class LangsamesImpressum:
    """Jeder Abruf kostet Wartezeit - wie ein echter Webserver."""

    def __init__(self, wartezeit=0.2):
        self.wartezeit = wartezeit
        self.gleichzeitig = 0
        self.hoechststand = 0
        self._schloss = threading.Lock()

    def impressum_text(self, website):
        with self._schloss:
            self.gleichzeitig += 1
            self.hoechststand = max(self.hoechststand, self.gleichzeitig)
        try:
            time.sleep(self.wartezeit)
            return "Impressum: Geschäftsführer Max Muster"
        finally:
            with self._schloss:
                self.gleichzeitig -= 1

    def entscheider_lesen(self, text, name, domain="", hinweis_name=""):
        return {"personen": [{"vorname": "Max", "nachname": "Muster"}],
                "mail_domain": domain}


class FakeDropcontact:
    def email_bauen(self, vorname, nachname, website, company=""):
        return {"email": f"{nachname.lower()}@{company.lower()}.de".replace(" ", "")}


class FakeHunter:
    def email_pruefen(self, email):
        return {"status": "valid", "score": 90}


def _firmen(anzahl):
    return [{"name": f"Firma {i}", "website": f"https://firma{i}.de",
             "domain": f"firma{i}.de"} for i in range(anzahl)]


def _lauf(firmen, impressum, **abweichungen):
    return source_leads(
        _kunde(), limit=len(firmen), apify_key="k", hunter_key="k",
        dropcontact_key="k", apify_source=FakeApify(firmen),
        hunter_source=FakeHunter(), dropcontact_source=FakeDropcontact(),
        impressum_quelle=impressum, **abweichungen)


def test_firmen_werden_gleichzeitig_bearbeitet():
    impressum = LangsamesImpressum(wartezeit=0.2)

    start = time.monotonic()
    _lauf(_firmen(8), impressum)
    dauer = time.monotonic() - start

    # Nacheinander waeren das 8 x 0,2s = 1,6s. Parallel deutlich weniger.
    assert dauer < 1.0, f"zu langsam: {dauer:.2f}s - läuft es wirklich parallel?"
    assert impressum.hoechststand > 1, "es lief nur eine Firma zur Zeit"


def test_reihenfolge_bleibt_die_der_firmenliste():
    leads, _, firmen_mit_ausgang = _lauf(_firmen(6), LangsamesImpressum(0.05))

    assert [f["name"] for f in firmen_mit_ausgang] == [
        "Firma 0", "Firma 1", "Firma 2", "Firma 3", "Firma 4", "Firma 5"]
    assert [l.company for l in leads] == [
        "Firma 0", "Firma 1", "Firma 2", "Firma 3", "Firma 4", "Firma 5"]


def test_deckung_zaehlt_wie_vorher():
    _, deckung, _ = _lauf(_firmen(5), LangsamesImpressum(0.01))

    assert deckung["firmen_gesamt"] == 5
    assert deckung["firmen_mit_kontakt"] == 5
    assert deckung["je_stufe"]["impressum"] == 5


def test_eine_kaputte_firma_reisst_den_lauf_nicht_mit():
    class MalKaputt(LangsamesImpressum):
        def impressum_text(self, website):
            if "firma2" in website:
                raise RuntimeError("Anbieter antwortet mit 500")
            return super().impressum_text(website)

    leads, deckung, firmen_mit_ausgang = _lauf(_firmen(4), MalKaputt(0.01))

    ausgaenge = {f["name"]: f["ausgang"] for f in firmen_mit_ausgang}
    assert ausgaenge["Firma 2"] == "fehler"
    assert deckung["firmen_gesamt"] == 4
    assert deckung["firmen_mit_kontakt"] == 3
    assert "Firma 2" not in [l.company for l in leads]


def test_leere_firmenliste_bricht_nicht():
    leads, deckung, firmen_mit_ausgang = _lauf([], LangsamesImpressum(0.01))

    assert leads == [] and firmen_mit_ausgang == []
    assert deckung["firmen_gesamt"] == 0
