import pytest
from pipeline.branchen_filter import (firma_bewerten, harter_ausschluss,
                                      AUSSCHLUSS_GRUENDE)


class _FakeKI:
    """Gibt eine vorgegebene KI-Antwort zurueck und merkt sich den Prompt."""
    def __init__(self, antwort):
        self.antwort = antwort
        self.prompts = []

    def frage(self, system, prompt):
        self.prompts.append((system, prompt))
        return self.antwort


def firma(name="Muster IT GmbH", categories=None, website="https://muster-it.de"):
    return {"name": name, "categories": categories or ["IT-Berater"],
            "website": website, "domain": "muster-it.de"}


# Harte Regeln (ohne KI, ohne Netz) --------------------------------------

def test_niederlassung_und_filiale_fliegen_hart_raus():
    # Olivers Vorgabe: "bei Filialisten/Niederlassungen ausschliesslich die
    # Zentrale".
    for name in ["GREEN IT Das Systemhaus GmbH Niederlassung Hannover",
                 "lmbit GmbH, Niederlassung Hannover",
                 "Beispiel AG - Filiale Hildesheim",
                 "Muster GmbH Zweigstelle Hannover"]:
        assert harter_ausschluss(firma(name=name)) == "niederlassung"


def test_zentrale_ohne_niederlassungs_hinweis_bleibt():
    assert harter_ausschluss(firma(name="GREEN IT Das Systemhaus GmbH")) is None


def test_klar_fremde_kategorien_fliegen_hart_raus():
    for kategorie, grund in [("Zeitarbeit", "branchenfremd"),
                             ("Immobilienagentur", "branchenfremd"),
                             ("Lebensmittelgeschäft", "branchenfremd"),
                             ("Gebäudereinigung", "branchenfremd"),
                             ("Augenarzt", "branchenfremd")]:
        assert harter_ausschluss(firma(categories=[kategorie])) == grund


def test_it_kategorie_schuetzt_nicht_vor_klarem_fremd_treffer():
    # "Clean-it-Narin Glas und Gebaeudereinigung" hatte auch eine
    # IT-Kategorie - Reinigung bleibt trotzdem raus.
    assert harter_ausschluss(
        firma(name="Clean-it-Narin Glas und Gebäudereinigung",
              categories=["IT-Berater", "Gebäudereinigung"])) == "branchenfremd"


# KI-Urteil ---------------------------------------------------------------

def test_ki_urteil_passt_wird_uebernommen():
    ki = _FakeKI('{"passt": true, "typ": "IT-Systemhaus", '
                 '"grund": "Betreut IT von Mittelstaendlern"}')
    ergebnis = firma_bewerten(firma(), webtext="Wir betreuen Ihre IT ...", ki=ki)
    assert ergebnis["passt"] is True
    assert ergebnis["typ"] == "IT-Systemhaus"
    assert ergebnis["quelle"] == "ki"


def test_ki_erkennt_automations_wettbewerber():
    ki = _FakeKI('{"passt": false, "typ": "Automations-Dienstleister", '
                 '"grund": "bietet selbst Prozessautomatisierung an"}')
    ergebnis = firma_bewerten(firma(), webtext="Wir automatisieren Prozesse", ki=ki)
    assert ergebnis["passt"] is False
    assert "Automations" in ergebnis["typ"]


def test_prompt_enthaelt_olivers_profil_und_die_firmendaten():
    ki = _FakeKI('{"passt": true, "typ": "IT-Service", "grund": "ok"}')
    firma_bewerten(firma(name="Nordfalke IT", categories=["IT-Berater"]),
                   webtext="Systembetreuung", ki=ki)
    system, prompt = ki.prompts[0]
    for pflicht in ["IT-Systemhaus", "Rechenzentr", "Hoster",
                    "Automation", "Computerhandel"]:
        assert pflicht in system
    assert "Nordfalke IT" in prompt and "Systembetreuung" in prompt


def test_unlesbare_ki_antwort_faellt_auf_unsicher_zurueck():
    # Zuverlaessigkeit zuerst: keine Antwort = kein Versand, aber als
    # "unsicher" gekennzeichnet statt still verworfen.
    ergebnis = firma_bewerten(firma(), webtext="x", ki=_FakeKI("kaputt"))
    assert ergebnis["passt"] is False
    assert ergebnis["typ"] == "unsicher"


def test_ohne_webtext_urteilt_die_ki_nur_nach_name_und_kategorien():
    ki = _FakeKI('{"passt": false, "typ": "Softwarehersteller", "grund": "Produktfirma"}')
    ergebnis = firma_bewerten(firma(website=""), webtext="", ki=ki)
    assert ergebnis["passt"] is False
    _, prompt = ki.prompts[0]
    assert "keine Webseite" in prompt.lower() or "kein text" in prompt.lower()


def test_harter_ausschluss_spart_den_ki_aufruf():
    ki = _FakeKI('{"passt": true, "typ": "x", "grund": "y"}')
    ergebnis = firma_bewerten(firma(name="Muster GmbH Niederlassung Hannover"),
                              webtext="", ki=ki)
    assert ergebnis["passt"] is False
    assert ergebnis["typ"] in AUSSCHLUSS_GRUENDE
    assert ki.prompts == []          # keine KI-Kosten fuer klare Faelle


# Regressions-Tests: Olivers echte Beschwerdefaelle vom 30.07.2026 -------
# Jede dieser Firmen stand in der Liste, die an Oliver ging. Sie sind hier
# namentlich festgenagelt, damit kein spaeterer Umbau des Filters sie
# wieder durchlaesst.

OLIVERS_BESCHWERDEFAELLE = [
    ("CARE Vision Augenlasern & Lasik Hannover", ["Augenarzt"]),
    ("Denns BioMarkt Hildesheim", ["Lebensmittelgeschäft"]),
    ("SPIELZEUGKISTE - Spielwaren, Modellbahnen", ["Spielwarengeschäft"]),
    ("Tina Voß GmbH Zeitarbeit", ["Zeitarbeit"]),
    ("Alpha Immobilien Service GmbH", ["Immobilienagentur"]),
    ("Interhyp Baufinanzierung", ["Baufinanzierung"]),
    ("Clean-it-Narin Glas und Gebäudereinigung", ["IT-Berater", "Gebäudereinigung"]),
    ("event it AG", ["Veranstaltungsservice", "Eventmanagement-Firma"]),
    ("PC-COLLEGE Hannover", ["Berufsbildende Schulen", "Schulen"]),
    ("GREEN IT Das Systemhaus GmbH Niederlassung Hannover", ["IT-Berater"]),
    ("lmbit GmbH, Niederlassung Hannover", ["IT-Dienstleister / IT-Systemhaus"]),
    ("Infinigate Deutschland GmbH, Niederlassung Hannover", ["IT-Berater"]),
]


@pytest.mark.parametrize("name,kategorien", OLIVERS_BESCHWERDEFAELLE)
def test_olivers_beschwerdefaelle_fliegen_ohne_ki_raus(name, kategorien):
    """Diese Firmen muessen schon von den harten Regeln erwischt werden -
    ohne KI, ohne Netz, in Millisekunden."""
    grund = harter_ausschluss({"name": name, "categories": kategorien})
    assert grund in ("niederlassung", "branchenfremd"), f"{name} rutscht durch!"


def test_zweite_chance_fragt_nur_nach_fremd_it_betreuung():
    """Rueckgewinn-Lauf (30.07.2026): Grenzfaelle (Software-Hersteller,
    Berater) werden mit EINER Frage nachgeprueft - betreut die Firma
    fremde IT? Automations-Anbieter bleiben trotzdem draussen."""
    from pipeline.branchen_filter import ZWEITE_CHANCE_SYSTEM
    ki = _FakeKI('{"passt": true, "typ": "Softwarehaus mit Managed Services", '
                 '"grund": "betreut zusaetzlich Kunden-IT"}')
    ergebnis = firma_bewerten(firma(), webtext="Wir entwickeln Software und "
                              "betreuen die IT unserer Kunden", ki=ki,
                              system=ZWEITE_CHANCE_SYSTEM)
    assert ergebnis["passt"] is True
    system, _ = ki.prompts[0]
    assert "IT ANDERER Unternehmen" in system
    assert "Automation" in system          # Wettbewerber bleiben ausgeschlossen
    assert "Managed Services" in system
