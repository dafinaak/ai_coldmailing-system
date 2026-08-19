"""Leistungs-Familien: "Computer Services" steht fuer die ganze IT-Familie.

Olivers Vorgabe (19.08.2026): die Auswahl darf kein exaktes Schlagwort
sein. EINE Zuordnung versorgt Formular, Zaehler, Filter und Sammlung -
diese Tests nageln fest, dass sie sich ueberall gleich verhaelt.
"""
from pipeline.firmen_filter import filtern
from pipeline.service_categories import (expand_for_matching,
                                         expand_for_search, families,
                                         family_of)


def test_familie_wird_in_jeder_schreibweise_erkannt():
    assert family_of("Computer Services") == "Computer Services"
    assert family_of("computer services") == "Computer Services"
    assert family_of("IT-Dienstleister") == "Computer Services"
    assert family_of("edv-service") == "Computer Services"


def test_freie_begriffe_sind_keine_familie():
    assert family_of("Dachdecker") is None
    assert family_of("") is None


def test_matching_erweitert_die_familie_und_behaelt_freie_begriffe():
    erweitert = expand_for_matching(["Computer Services", "Dachdecker"])
    text = " ".join(erweitert).casefold()
    assert "Dachdecker" in erweitert
    assert "netzwerk" in text
    assert "software" in text
    assert "cybersecurity" in text
    assert "cloud" in text


def test_matching_ohne_familie_bleibt_unveraendert():
    assert expand_for_matching(["Systemhaus"]) == ["Systemhaus"]


def test_matching_dedupliziert_ohne_die_reihenfolge_zu_verlieren():
    erweitert = expand_for_matching(["Computer Services", "Computer Services"])
    assert len(erweitert) == len({e.casefold() for e in erweitert})
    assert erweitert[0] == "Computer Services"


def test_suchliste_ist_kurz_und_deutsch():
    # Bezahlte Suche: bewusst wenige, starke Begriffe.
    suche = expand_for_search(["Computer Services"])
    assert 1 <= len(suche) <= 10
    assert "IT-Dienstleister" in suche
    # Ausgeschlossene Familien (Hosting/Automation) werden nicht bezahlt.
    assert not any("hosting" in s.casefold() for s in suche)
    assert not any("automation" in s.casefold() for s in suche)


def test_suchliste_laesst_freie_begriffe_durch_und_kappt():
    suche = expand_for_search(["Computer Services", "Dachdecker"],
                              max_terms=3)
    assert len(suche) == 3


def test_familien_liste_fuers_formular():
    anzeige = families()
    assert "Computer Services" in anzeige
    assert any("Netzwerk" in u for u in anzeige["Computer Services"])


def test_filter_findet_unterkategorien_ueber_die_familie():
    # Der eigentliche Zweck: Firmen, die unter "Softwareentwicklung" oder
    # "Netzwerktechnik" gelistet sind, passen zur Familie.
    firmen = [
        {"name": "Nordsoft", "website": "https://nordsoft.de",
         "categories": ["Softwareentwicklung"], "plz": ""},
        {"name": "NetzWerk GmbH", "website": "https://netzwerk.de",
         "categories": ["Netzwerktechnik"], "plz": ""},
        {"name": "Bäckerei Krume", "website": "https://krume.de",
         "categories": ["Bäckerei"], "plz": ""},
    ]
    ergebnis = filtern(firmen, dienste=["Computer Services"])
    namen = {f["name"] for f in ergebnis["treffer"]}
    assert namen == {"Nordsoft", "NetzWerk GmbH"}
