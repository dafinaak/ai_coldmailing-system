"""Der USP/ICP-Vorschlag muss wissen, wen die Kampagne anschreibt.

Gefunden am 14.08.2026: Der Vorschlag bekam NUR die Verkaeufer-Webseite.
Die KI beschrieb daraufhin den gewoehnlichen Endkunden dieser Firma
("mittelständische Unternehmen, die Automation suchen") - angeschrieben
werden sollten aber die IT-Dienstleister, die das Angebot an ihre eigenen
Kunden weitergeben. Jede erzeugte E-Mail haette den Leser als Kaeufer
angesprochen statt als Partner.
"""
from pipeline.offer import draft_usp_icp
from web.routen.assistent import _kampagnen_zweck

ANTWORT = """{
  "usp": [{"titel": "Schnell", "erklaerung": "Sehr schnell."}],
  "icp": {"firmografisch": "IT-Dienstleister", "technografisch": "CRM",
          "verhalten": "Kundenanfragen", "entscheider": "Inhaber"}
}"""


class FakeKI:
    def __init__(self):
        self.prompt = None

    def frage(self, system, prompt):
        self.prompt = prompt
        return ANTWORT


def test_zweck_steht_im_prompt():
    ki = FakeKI()

    draft_usp_icp("Wir bauen Automationen.", ki,
                  "Partnerschafts-Anfrage an IT-Dienstleister")

    assert "Partnerschafts-Anfrage an IT-Dienstleister" in ki.prompt


def test_ohne_zweck_bleibt_der_prompt_ehrlich_leer():
    ki = FakeKI()

    draft_usp_icp("Wir bauen Automationen.", ki)

    # Kein erfundener Zweck - die Vorlage sagt der KI ausdruecklich, dass
    # nichts angegeben wurde, statt die Zeile wegzulassen.
    assert "(nichts angegeben)" in ki.prompt


def test_prompt_verlangt_die_empfaenger_der_kampagne():
    ki = FakeKI()

    draft_usp_icp("Text", ki, "Partner gesucht")

    assert "DIESE KAMPAGNE anschreibt" in ki.prompt


def test_zweck_wird_aus_name_beschreibung_und_hinweisen_gebaut():
    zweck = _kampagnen_zweck({
        "name": "IT-Partner Hannover",
        "beschreibung": "Technologie-Partnerschaft anbieten.",
        "anweisungen": "Ruhig und erklärend.",
    })

    assert zweck == ("IT-Partner Hannover\n"
                     "Technologie-Partnerschaft anbieten.\n"
                     "Ruhig und erklärend.")


def test_leere_felder_erzeugen_keine_leerzeilen():
    assert _kampagnen_zweck({"name": "Nur Name"}) == "Nur Name"
    assert _kampagnen_zweck({}) == ""
