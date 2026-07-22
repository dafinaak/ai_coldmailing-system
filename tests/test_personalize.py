import json, pytest
from pipeline.personalize import personalize, regenerate_step
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

def test_kaputtes_json_wirft_valueerror():
    ki = FakeKI('{"betreff": kaputt}')
    with pytest.raises(ValueError, match="unvollständig"):
        personalize(LEAD, KUNDE, ki, webseiten_text="")

def test_prosa_um_json_herum_wird_toleriert():
    import json as j
    antwort = "Gern! " + j.dumps({"betreff": "B", "mail_1": "M",
                                  "follow_up_1": "F1", "follow_up_2": "F2"}) + " Viel Erfolg!"
    texte = personalize(LEAD, KUNDE, FakeKI(antwort), webseiten_text="")
    assert texte["betreff"] == "B"


AKTUELLE_TEXTE = {
    "betreff": "Alter Betreff",
    "mail_1": "Alter Erstkontakt",
    "follow_up_1": "Altes Follow-up 1",
    "follow_up_2": "Altes Follow-up 2",
}


def test_regenerate_step_erwartet_beim_ersten_text_betreff_und_text():
    ki = FakeKI('{"betreff": "Neue Frage", "text": "Neuer Text"}')

    ergebnis = regenerate_step(
        LEAD, KUNDE, ki, "Wir bauen Rohre.", AKTUELLE_TEXTE, "mail_1"
    )

    assert ergebnis == {"betreff": "Neue Frage", "text": "Neuer Text"}
    assert "Ändere ausschließlich E-Mail 1" in ki.prompts[0]
    assert "Altes Follow-up 2" in ki.prompts[0]


def test_regenerate_step_followup_erwartet_nur_text():
    ki = FakeKI('{"text": "Neue Erinnerung"}')

    ergebnis = regenerate_step(
        LEAD, KUNDE, ki, "", AKTUELLE_TEXTE, "follow_up_1"
    )

    assert ergebnis == {"text": "Neue Erinnerung"}
    assert "Ändere ausschließlich Follow-up 1" in ki.prompts[0]


def test_regenerate_step_lehnt_unvollstaendige_antwort_ab():
    with pytest.raises(ValueError, match="KI-Antwort unvollständig"):
        regenerate_step(
            LEAD, KUNDE, FakeKI('{"text": "ohne Betreff"}'), "",
            AKTUELLE_TEXTE, "mail_1",
        )


def test_regenerate_step_lehnt_unbekannten_schritt_vor_ki_aufruf_ab():
    ki = FakeKI('{"text": "egal"}')

    with pytest.raises(ValueError, match="Unbekannter E-Mail-Schritt"):
        regenerate_step(LEAD, KUNDE, ki, "", AKTUELLE_TEXTE, "mail_4")

    assert ki.prompts == []
