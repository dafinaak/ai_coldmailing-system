import json
from pipeline.personalize import personalisiere_mit_nachbesserung
from pipeline.models import Lead
from pipeline.config import Kunde

KUNDE = Kunde(name="Demo GmbH", zielgruppe={}, angebot="KI-Automatisierung",
              tonalitaet="ruhig", absender="Leonard", follow_up_tage=[3, 7],
              test_empfaenger=["t@example.com"])
LEAD = Lead(first_name="Anna", last_name="Muster", email="anna@firma.de",
            company="Firma GmbH", title="CEO", website="", source="apollo")

# Die KI liefert immer einen vollstaendigen, parsebaren Text - ob er "besteht",
# entscheidet allein der eingeschleuste Pruefer (check). So testen wir die
# Schleife selbst, ohne von KI-Zufall abzuhaengen.
GUTES_JSON = json.dumps({"betreff": "Kurzer Betreff", "mail_1": "M",
                         "follow_up_1": "F1", "follow_up_2": "F2"})


class FakeKI:
    def __init__(self):
        self.prompts = []
    def frage(self, system, prompt):
        self.prompts.append(prompt)
        return GUTES_JSON


def _check_nein_dann_ja():
    """Prueft beim 1. Versuch NEIN (mit Grund), ab dem 2. Versuch JA."""
    zustand = {"n": 0}
    def check(texte, lead, kunde, ki):
        zustand["n"] += 1
        if zustand["n"] == 1:
            return False, "Qualitätskontrolle: NEIN: erfundene Mitarbeiterzahl"
        return True, "bestanden"
    return check


def test_durchgefallener_text_besteht_nach_nachbesserung():
    ki = FakeKI()
    ok, grund, texte, versuche = personalisiere_mit_nachbesserung(
        LEAD, KUNDE, ki, "Wir bauen Rohre.", _check_nein_dann_ja())
    assert ok is True
    assert versuche == 2          # erst im zweiten Anlauf bestanden
    assert texte["betreff"] == "Kurzer Betreff"
    # Der Ablehnungsgrund muss beim zweiten Anlauf im KI-Prompt gelandet sein:
    assert "erfundene Mitarbeiterzahl" in ki.prompts[1]
    assert "NACHBESSERUNG" in ki.prompts[1]
    # Der erste Anlauf lief noch ohne Feedback:
    assert "NACHBESSERUNG" not in ki.prompts[0]


def test_besteht_sofort_kein_zweiter_versuch():
    ki = FakeKI()
    ok, grund, texte, versuche = personalisiere_mit_nachbesserung(
        LEAD, KUNDE, ki, "Text.", lambda *a: (True, "bestanden"))
    assert ok is True and versuche == 1
    assert len(ki.prompts) == 1   # nur einmal geschrieben


def test_bleibt_schlecht_faellt_nach_max_versuchen_zur_nacharbeit():
    ki = FakeKI()
    ok, grund, texte, versuche = personalisiere_mit_nachbesserung(
        LEAD, KUNDE, ki, "Text.", lambda *a: (False, "NEIN: bleibt schlecht"),
        max_versuche=3)
    assert ok is False and versuche == 3
    assert len(ki.prompts) == 3   # dreimal versucht
    # Der letzte Entwurf bleibt erhalten (nicht {}), damit der Mensch ihn sieht:
    assert texte["betreff"] == "Kurzer Betreff"
    assert grund == "NEIN: bleibt schlecht"


def test_unbrauchbare_ki_antwort_gibt_leeren_text_ohne_schleife():
    class LeereKI:
        def frage(self, system, prompt):
            return json.dumps({"betreff": "nur Betreff"})   # unvollstaendig
    ok, grund, texte, versuche = personalisiere_mit_nachbesserung(
        LEAD, KUNDE, LeereKI(), "Text.", lambda *a: (True, "bestanden"))
    assert ok is False and texte == {} and versuche == 1
