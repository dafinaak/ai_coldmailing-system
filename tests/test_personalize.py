import json, pytest
from pipeline.personalize import personalize
from pipeline.models import Lead
from pipeline.config import Kunde

KUNDE = Kunde(name="Demo GmbH", zielgruppe={}, angebot="KI-Automatisierung",
              tonalitaet="ruhig", absender="Leonard", follow_up_tage=[3, 7],
              test_empfaenger=["t@example.com"])
LEAD = Lead(first_name="Anna", last_name="Muster", email="anna@firma.de",
            company="Firma GmbH", title="CEO", website="", source="apollo")

class FakeKI:
    def __init__(self, antwort):
        self.antwort, self.prompts = antwort, []
    def frage(self, system, prompt):
        self.prompts.append(prompt)
        return self.antwort

def test_liefert_alle_textteile():
    ki = FakeKI(json.dumps({"betreff": "B", "mail_1": "M", "follow_up_1": "F1", "follow_up_2": "F2"}))
    texte = personalize(LEAD, KUNDE, ki, webseiten_text="Wir bauen Rohre.")
    assert texte["betreff"] == "B"
    assert "Firma GmbH" in ki.prompts[0] and "Wir bauen Rohre." in ki.prompts[0]

def test_unvollstaendige_antwort_wirft_fehler():
    ki = FakeKI(json.dumps({"betreff": "B"}))
    with pytest.raises(ValueError):
        personalize(LEAD, KUNDE, ki, webseiten_text="")
