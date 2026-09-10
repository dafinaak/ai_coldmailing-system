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


# Dafinas Fund vom 31.08.2026 --------------------------------------------
# Sechs Firmen standen in den fertigen Listen der Zonen 33 und 34, obwohl
# sie eigene Software entwickeln/verkaufen, ein Nischenprodukt vertreten
# oder im Kern Security-Anbieter sind. Vier kamen ueber die "zweite
# Chance" herein - genau den Weg, den Dafinas Regel jetzt schliesst.

DAFINAS_SOFTWAREFAELLE = [
    ("Mibema Software UG (haftungsbeschränkt)",
     ["Softwareentwickler/-hersteller"]),
    ("GRAPHISOFT Center Kassel, CAD intern GmbH",
     ["Softwareentwickler/-hersteller", "IT-Berater"]),
    ("elastify GmbH & Co. KG",
     ["Softwareentwickler/-hersteller", "Unternehmensberater", "IT-Berater"]),
    ("kisocon Kirchensoftware & Consulting",
     ["Softwareentwickler/-hersteller", "IT-Berater",
      "Schulungsinstitut für Software"]),
]


# Praezisierung Dafina, 03.09.2026: die Verzeichnis-Kategorie allein
# entscheidet NICHT mehr - die Webseite entscheidet, geprueft mit der
# strengen Regel. Beim Nachpruefen der Zonen 32-34 hatte die Kategorie
# 61 Firmen aussortiert; die Webseite bestaetigte das fuer 49 und holte
# 12 echte Systemhaeuser zurueck. Die Kategorie bleibt ein Hinweis an die
# KI, damit sie bei solchen Firmen genau hinsieht.

@pytest.mark.parametrize("name,kategorien", DAFINAS_SOFTWAREFAELLE)
def test_software_kategorie_ist_kein_harter_ausschluss_mehr(name, kategorien):
    """Die Kategorie schickt die Firma zur KI - sie wirft sie nicht raus."""
    assert harter_ausschluss({"name": name, "categories": kategorien}) is None


def test_software_kategorie_geht_als_hinweis_an_die_ki():
    ki = _FakeKI('{"passt": false, "typ": "Softwarehersteller", '
                 '"grund": "entwickelt eigene Software"}')
    firma_bewerten(
        firma(name="Mibema Software UG",
              categories=["Softwareentwickler/-hersteller"]),
        webtext="Wir entwickeln Software", ki=ki)
    assert len(ki.prompts) == 1
    _system, prompt = ki.prompts[0]
    assert "Softwareentwickler/-hersteller" in prompt
    assert "Hinweis" in prompt


def test_ohne_software_kategorie_kein_hinweis():
    ki = _FakeKI('{"passt": true, "typ": "IT-Systemhaus", "grund": "betreut IT"}')
    firma_bewerten(firma(name="Pietsch IT GmbH",
                         categories=["IT-Berater", "Computerservice"]),
                   webtext="Wir betreuen die IT unserer Kunden", ki=ki)
    _system, prompt = ki.prompts[0]
    assert "Hinweis" not in prompt


def test_webseite_mit_eigener_software_faellt_trotz_it_betreuung_raus():
    """Die strenge Regel bleibt: eigene Software = raus, auch mit Support.
    Genau das hatte die alte 'zweite Chance' mit ihrem weichen Prompt
    uebersehen - hier urteilt die KI mit dem strengen SYSTEM_PROMPT."""
    ki = _FakeKI('{"passt": false, "typ": "Softwarehersteller mit Support", '
                 '"grund": "eigenes Produkt, Support nur dazu"}')
    ergebnis = firma_bewerten(
        firma(name="Mibema Software UG",
              categories=["Softwareentwickler/-hersteller"]),
        webtext="Wir entwickeln Software und betreuen die IT unserer Kunden",
        ki=ki)
    assert ergebnis["passt"] is False
    assert ergebnis["quelle"] == "ki"


def test_webseite_mit_reiner_it_betreuung_bleibt_trotz_kategorie_drin():
    """Der Fall Computer live / Deltatec / Klanke: Karte sagt Software,
    Webseite zeigt reine IT-Betreuung ohne Produkt - die Webseite gilt."""
    ki = _FakeKI('{"passt": true, "typ": "IT-Dienstleister mit Managed Services", '
                 '"grund": "laufende Betreuung, kein eigenes Produkt"}')
    ergebnis = firma_bewerten(
        firma(name="Computer live oHG",
              categories=["Softwareentwickler/-hersteller", "Computerservice"]),
        webtext="Managed Services, Netzwerk- und Serverbetreuung für Firmen",
        ki=ki)
    assert ergebnis["passt"] is True


def test_eigene_software_wird_nur_an_der_kategorie_erkannt():
    """Der Firmenname darf NICHT ausschlaggebend sein: "Eulah IT -
    Systemhaus fuer Digitalisierung, Software & IT" ist ein echtes
    Systemhaus und muss zur KI weitergehen, nicht hart rausfliegen."""
    assert harter_ausschluss(firma(
        name="Eulah IT - Systemhaus für Digitalisierung, Software & IT",
        categories=["IT-Dienstleister", "Computerservice"])) is None


def test_normales_systemhaus_bleibt_von_der_neuen_regel_unberuehrt():
    assert harter_ausschluss(firma(
        name="Pietsch IT GmbH",
        categories=["IT-Berater", "Computerservice"])) is None


def test_eigene_software_ist_kein_harter_grund_mehr():
    assert "eigene_software" not in AUSSCHLUSS_GRUENDE


def test_prompt_nennt_dafinas_neue_ausschluesse():
    """BLUVIT (Security) und netgo tax (DATEV-Partner fuer Kanzleien)
    tragen keine Software-Kategorie - sie muessen am Prompt scheitern.
    Microsoft-365-Betreuung bleibt ausdruecklich erlaubt, sonst wuerde
    die Regel echte Systemhaeuser mitreissen."""
    ki = _FakeKI('{"passt": true, "typ": "IT-Service", "grund": "ok"}')
    firma_bewerten(firma(), webtext="Systembetreuung", ki=ki)
    system, _ = ki.prompts[0]
    for pflicht in ["EIGENER Software", "Branchen-", "Salesforce", "DATEV",
                    "im Kern IT-Sicherheit", "Microsoft 365"]:
        assert pflicht in system, f"'{pflicht}' fehlt im Prompt"


def test_zweite_chance_ist_abgeschafft():
    """Die 'zweite Chance' holte Software-Hersteller zurueck, sobald sie
    zusaetzlich IT betreuten. Dafinas Regel vom 31.08.2026 sagt das
    Gegenteil, also ist der Schritt ersatzlos entfernt - dieser Test
    haelt ihn fern."""
    import pipeline.branchen_filter as bf
    assert not hasattr(bf, "ZWEITE_CHANCE_SYSTEM")


# Wettbewerber-Pruefung (Olivers Fund "Michael Wessel", 30.07.2026) -------
# Der bisherige Filter fragte "betreut die Firma fremde IT?" - und liess
# bei Ja durch, ohne zu pruefen, ob dieselbe Firma AUCH Automatisierung
# oder KI anbietet. Genau daran ist Michael Wessel durchgerutscht
# ("IT-Prozesse intelligent automatisieren - mit KI-Loesungen").

def test_wettbewerber_pruefung_erkennt_automations_angebot():
    from pipeline.branchen_filter import ist_wettbewerber, WETTBEWERBER_SYSTEM
    ki = _FakeKI('{"wettbewerber": true, "belege": "IT-Prozesse intelligent '
                 'automatisieren mit KI-Loesungen"}')
    ergebnis = ist_wettbewerber(firma(), webtext="... automatisieren ...", ki=ki)
    assert ergebnis["wettbewerber"] is True
    assert "automatisieren" in ergebnis["belege"]
    system, _ = ki.prompts[0]
    for pflicht in ["Automatisierung", "KI", "RPA", "Workflow"]:
        assert pflicht in system


def test_reines_systemhaus_ist_kein_wettbewerber():
    from pipeline.branchen_filter import ist_wettbewerber
    ki = _FakeKI('{"wettbewerber": false, "belege": ""}')
    ergebnis = ist_wettbewerber(firma(), webtext="Managed Services, Wartung",
                                ki=ki)
    assert ergebnis["wettbewerber"] is False


def test_unlesbare_antwort_gilt_als_unsicher():
    """Zuverlaessigkeit zuerst: Wer nicht eindeutig als unbedenklich
    erkannt wird, wird nicht angeschrieben - seit der Phase-2-Eichung
    (20.08.2026) als "unsicher" statt faelschlich als Anbieter."""
    from pipeline.branchen_filter import ist_wettbewerber
    ergebnis = ist_wettbewerber(firma(), webtext="x", ki=_FakeKI("murks"))
    assert ergebnis["wettbewerber"] is False
    assert ergebnis["unsicher"] is True
    assert "nicht lesbar" in ergebnis["belege"].lower()
