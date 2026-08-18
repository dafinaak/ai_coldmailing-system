"""Postfächer ohne Warmup müssen als fraglich erkennbar sein.

Gemessen am 17.08.2026: Auf DERSELBEN Domain kam von einem Postfach mit
Warmup eine echte Outlook-Antwort an, von einem ohne Warmup nicht. Warmup
läuft nur, wenn ein Postfach auch empfangen kann - ist es aus, ist das
Postfach oft nur zum Senden eingerichtet.

Genau so ist die echte Kampagne mit 277 Empfängern blind geworden: beide
Absender hatten Warmup aus, jede Antwort wäre lautlos verlorengegangen.
Wer im Formular ein Postfach wählt, soll das sehen.
"""
from types import SimpleNamespace

import pytest

from web.routen.assistent import _postfaecher


class FakeLeser:
    def __init__(self, postfaecher):
        self._postfaecher = postfaecher

    def postfaecher(self):
        return {"postfaecher": self._postfaecher, "erreichbar": True}


def _anfrage(leser):
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(
        instantly_leser=leser)))


GUT = {"email": "o.redschlag@marke.email", "status": "verbunden",
       "warmup": "an", "daily_limit": 30}
OHNE_WARMUP = {"email": "einladung@marke.email", "status": "verbunden",
               "warmup": "aus", "daily_limit": 30}
KAPUTT = {"email": "webinar@marke.info", "status": "verbindungsfehler",
          "warmup": "aus", "daily_limit": 30}


def test_postfach_mit_warmup_kommt_ohne_hinweis():
    liste = _postfaecher(_anfrage(FakeLeser([GUT])))

    assert liste == [{"adresse": "o.redschlag@marke.email", "hinweis": ""}]


def test_postfach_ohne_warmup_wird_gewarnt():
    liste = _postfaecher(_anfrage(FakeLeser([OHNE_WARMUP])))

    assert "empfängt vermutlich keine Antworten" in liste[0]["hinweis"]


def test_gute_stehen_vorn():
    liste = _postfaecher(_anfrage(FakeLeser([OHNE_WARMUP, KAPUTT, GUT])))

    assert [p["adresse"] for p in liste] == [
        "o.redschlag@marke.email", "einladung@marke.email", "webinar@marke.info"]


def test_nichts_wird_ausgeblendet():
    # Welches Postfach benutzt wird, entscheidet der Mensch - er soll es
    # nur sehen. Ein verstecktes Postfach waere eine stille Entscheidung.
    liste = _postfaecher(_anfrage(FakeLeser([OHNE_WARMUP, KAPUTT, GUT])))

    assert len(liste) == 3


def test_verbindungsfehler_gilt_auch_als_fraglich():
    liste = _postfaecher(_anfrage(FakeLeser([KAPUTT])))

    assert liste[0]["hinweis"]


def test_kaputte_api_blockiert_das_formular_nicht():
    class TotesLeser:
        def postfaecher(self):
            raise RuntimeError("Instantly antwortet mit 500")

    assert _postfaecher(_anfrage(TotesLeser())) == []


def test_ohne_leser_leere_liste():
    assert _postfaecher(_anfrage(None)) == []
