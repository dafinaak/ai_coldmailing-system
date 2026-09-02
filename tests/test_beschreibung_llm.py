"""Kurz-Beschreibung: ein Satz, und nur aus dem, was dasteht."""
from pipeline.beschreibung_llm import MAX_LAENGE, _saeubern, beschreiben


class FakeKI:
    def __init__(self, antwort="", fehler=None):
        self.antwort, self.fehler = antwort, fehler
        self.prompts = []

    def frage(self, system, prompt):
        if self.fehler:
            raise self.fehler
        self.prompts.append(prompt)
        return self.antwort


TEXT = "Wir betreuen die IT von Handwerksbetrieben. " * 20


def test_ein_satz_kommt_zurueck():
    ki = FakeKI("Betreut die IT von Handwerksbetrieben in Ostwestfalen.")
    assert beschreiben(ki, "A GmbH", TEXT) == \
        "Betreut die IT von Handwerksbetrieben in Ostwestfalen."


def test_zu_wenig_text_gibt_leer():
    """Unter der Mindestlaenge wird gar nicht erst gefragt - das spart
    Geld und verhindert geratene Saetze."""
    ki = FakeKI("Irgendwas")
    assert beschreiben(ki, "A GmbH", "Cookies akzeptieren") == ""
    assert ki.prompts == []


def test_leerer_text_gibt_leer():
    ki = FakeKI("Irgendwas")
    assert beschreiben(ki, "A GmbH", "") == ""
    assert beschreiben(ki, "A GmbH", None) == ""
    assert ki.prompts == []


def test_unklar_wird_zu_leer():
    """Sagt das Modell selbst, dass der Text nichts hergibt, wird nichts
    behauptet."""
    assert beschreiben(FakeKI("UNKLAR"), "A GmbH", TEXT) == ""


def test_ausfall_bricht_nicht_ab():
    """Ein Netzfehler darf einen Lauf ueber tausend Firmen nicht kippen."""
    assert beschreiben(FakeKI(fehler=OSError("kein Netz")), "A", TEXT) == ""


def test_anfuehrungszeichen_werden_entfernt():
    assert _saeubern('"Betreut IT-Systeme."') == "Betreut IT-Systeme."


def test_zeilenumbrueche_werden_zu_einem_satz():
    assert _saeubern("Betreut\n  IT-Systeme.") == "Betreut IT-Systeme."


def test_zu_lang_wird_gekuerzt():
    lang = "Diese Firma macht sehr viele Dinge. " * 20
    ergebnis = _saeubern(lang)
    assert len(ergebnis) <= MAX_LAENGE
    assert ergebnis.endswith(".")          # am Satzende geschnitten


def test_langes_wort_wird_nicht_zerhackt():
    lang = "Wort " * 100
    ergebnis = _saeubern(lang)
    assert len(ergebnis) <= MAX_LAENGE + 2
    assert not ergebnis.endswith("Wor")


def test_der_prompt_enthaelt_firma_und_text():
    ki = FakeKI("Ein Satz.")
    beschreiben(ki, "Muster GmbH", TEXT)
    assert "Muster GmbH" in ki.prompts[0]
    assert "Handwerksbetrieben" in ki.prompts[0]


def test_nur_der_anfang_des_textes_wird_geschickt():
    """Weiter unten stehen Impressum und Rechtstexte - die kosten Tokens
    und sagen nichts ueber die Taetigkeit."""
    ki = FakeKI("Ein Satz.")
    beschreiben(ki, "A GmbH", "A" * 50000)
    assert len(ki.prompts[0]) < 2000
