import pytest
from pipeline.sources.impressum import ImpressumQuelle, MIN_TEXTLAENGE


LANGER_IMPRESSUM_TEXT = (
    "Startseite Leistungen Impressum Angaben gemäß § 5 TMG ius Systemhaus "
    "Inhaberin Nadine Pelaccia Misburger Straße 81A 30625 Hannover "
    "Kontakt Telefon 0511 123456 E-Mail info@ius-systemhaus.de " * 5)


class FakeResponse:
    def __init__(self, status_code, text):
        self.status_code, self.text = status_code, text


class FakeSession:
    """Liefert je URL eine feste HTML-Antwort; unbekannte URLs sind 404."""
    def __init__(self, seiten=None):
        self.seiten, self.urls = seiten or {}, []
    def get(self, url, headers=None, timeout=None):
        self.urls.append(url)
        if url in self.seiten:
            return FakeResponse(200, self.seiten[url])
        return FakeResponse(404, "nicht da")


class FakeKI:
    def __init__(self, antwort):
        self.antwort, self.systeme, self.prompts = antwort, [], []
    def frage(self, system, prompt):
        self.systeme.append(system)
        self.prompts.append(prompt)
        return self.antwort


def quelle(seiten=None, ki_antwort='{"personen": [], "mail_domain": null}',
           renderer=None):
    return ImpressumQuelle(FakeKI(ki_antwort), session=FakeSession(seiten),
                           renderer=renderer)


# --- Impressum-Seite finden ------------------------------------------------

def test_findet_impressum_ueber_standardpfad():
    q = quelle({"https://firma.de/impressum": f"<html>{LANGER_IMPRESSUM_TEXT}</html>"})
    text = q.impressum_text("https://firma.de")
    assert text and "Nadine Pelaccia" in text


def test_faellt_auf_linksuche_der_startseite_zurueck():
    start = '<html><a href="/rechtliches/impressum-und-datenschutz">Impressum</a></html>'
    q = quelle({"https://firma.de": start,
                "https://firma.de/rechtliches/impressum-und-datenschutz":
                    f"<html>{LANGER_IMPRESSUM_TEXT}</html>"})
    text = q.impressum_text("https://firma.de")
    assert text and "Nadine Pelaccia" in text


def test_javascript_seite_wird_per_renderer_gelesen():
    # Pflichtfall (Messlauf it-blickwinkel.de): die Seite liefert per HTTP nur
    # eine winzige Huelle - erst das Browser-Rendering zeigt den Inhalt.
    gerendert = []
    def renderer(url):
        gerendert.append(url)
        return LANGER_IMPRESSUM_TEXT
    q = quelle({"https://firma.de/impressum": "<html>IT Blickwinkel</html>"},
               renderer=renderer)
    text = q.impressum_text("https://firma.de")
    assert text and "Nadine Pelaccia" in text
    assert gerendert  # Renderer wurde wirklich benutzt


def test_kein_impressum_gibt_none():
    q = quelle({"https://firma.de": "<html>nur Startseite ohne Links</html>"})
    assert q.impressum_text("https://firma.de") is None


def test_ohne_website_gibt_none():
    assert quelle().impressum_text("") is None


# --- Namen lesen (KI) ------------------------------------------------------

def test_ki_liest_personen_und_abweichende_mail_domain():
    q = quelle(ki_antwort='{"personen": [{"vorname": "Thomas", "nachname": "Riek"}], '
                          '"mail_domain": "hannover-edv.de"}')
    ergebnis = q.entscheider_lesen(LANGER_IMPRESSUM_TEXT, "N&R EDV", "it-hannover.de")
    assert ergebnis["personen"] == [{"vorname": "Thomas", "nachname": "Riek",
                                     "rolle": "", "linkedin": None}]
    assert ergebnis["mail_domain"] == "hannover-edv.de"
    # Der Impressums-Text und der Firmenname muessen im Prompt stecken:
    ki = q.ki
    assert "Nadine Pelaccia" in ki.prompts[0] and "N&R EDV" in ki.prompts[0]


def test_firmenname_wird_nicht_als_person_uebernommen():
    # Pflichtfall (Listen-Stichprobe): "VR Immobilien & Service" ist eine
    # Firma, kein Geschaeftsfuehrer - solche Antworten werden verworfen.
    q = quelle(ki_antwort='{"personen": [{"vorname": "VR", "nachname": "Immobilien & Service GmbH"},'
                          '{"vorname": "Anna", "nachname": "Muster"}], "mail_domain": null}')
    ergebnis = q.entscheider_lesen(LANGER_IMPRESSUM_TEXT, "Aimway", "aimway.de")
    assert ergebnis["personen"] == [{"vorname": "Anna", "nachname": "Muster",
                                     "rolle": "", "linkedin": None}]


def test_unvollstaendige_namen_werden_verworfen():
    q = quelle(ki_antwort='{"personen": [{"vorname": "G.", "nachname": "Hellberg"},'
                          '{"vorname": "", "nachname": "Meier"}], "mail_domain": null}')
    ergebnis = q.entscheider_lesen(LANGER_IMPRESSUM_TEXT, "Hellberg EDV", "drhellberg.de")
    # Abgekuerzte Vornamen ("G.") reichen Dropcontact nicht - raus damit.
    assert ergebnis["personen"] == []


def test_ki_antwort_mit_text_drumherum_wird_geparst():
    q = quelle(ki_antwort='Hier das Ergebnis:\n```json\n{"personen": '
                          '[{"vorname": "Anna", "nachname": "Muster"}], "mail_domain": null}\n```')
    ergebnis = q.entscheider_lesen(LANGER_IMPRESSUM_TEXT, "Firma", "firma.de")
    assert ergebnis["personen"] == [{"vorname": "Anna", "nachname": "Muster",
                                     "rolle": "", "linkedin": None}]


def test_unbrauchbare_ki_antwort_gibt_leeres_ergebnis():
    q = quelle(ki_antwort="Ich kann leider kein JSON.")
    ergebnis = q.entscheider_lesen(LANGER_IMPRESSUM_TEXT, "Firma", "firma.de")
    assert ergebnis == {"personen": [], "mail_domain": None}


def test_listen_hinweis_und_zitatschutz_stehen_im_auftrag():
    # Pflichtfall (ihre-helden.de): "Geschaeftsfuehrer" in einer
    # Kundenbewertung darf nicht als Chef durchgehen - die Anweisung dazu
    # muss im KI-Auftrag stehen, ebenso der Namens-Hinweis aus der Liste.
    q = quelle(ki_antwort='{"personen": [], "mail_domain": null}')
    q.entscheider_lesen(LANGER_IMPRESSUM_TEXT, "Firma", "firma.de",
                        hinweis_name="Nadine Pelaccia")
    ki = q.ki
    system = ki.systeme[0].lower()
    assert "kundenstimmen" in system or "bewertung" in system
    assert "Nadine Pelaccia" in ki.prompts[0]
