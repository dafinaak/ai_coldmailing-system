"""Drafting USP and ICP from a seller's website.

The wizard shows this as a proposal a human corrects. What must not
happen is the opposite of a proposal: a confident half-answer that
looks filled in. So an incomplete draft fails loudly instead.
"""
import json

import pytest

from pipeline.offer import draft_usp_icp


class FakeKI:
    def __init__(self, antwort):
        self.antwort, self.gefragt = antwort, []

    def frage(self, system, prompt):
        self.gefragt.append(prompt)
        return self.antwort


VOLLSTAENDIG = json.dumps({
    "usp": [{"titel": "Feste Ansprechpartner", "erklaerung": "Immer dieselbe Person."},
            {"titel": "Reaktion in zwei Stunden", "erklaerung": "Vertraglich zugesagt."}],
    "icp": {"firmografisch": "Handwerk, 10-50 Mitarbeiter, Region Hannover",
            "technografisch": "Microsoft 365",
            "verhalten": "Nach einem IT-Ausfall",
            "entscheider": "Inhaber"},
})


def test_liest_usp_und_icp_aus_der_antwort():
    ergebnis = draft_usp_icp("Wir betreuen IT für Handwerker.", FakeKI(VOLLSTAENDIG))

    assert ergebnis["usp"][0]["titel"] == "Feste Ansprechpartner"
    assert ergebnis["icp"]["entscheider"] == "Inhaber"
    assert set(ergebnis["icp"]) == {
        "firmografisch", "technografisch", "verhalten", "entscheider"}


def test_der_webseitentext_geht_wirklich_mit():
    ki = FakeKI(VOLLSTAENDIG)

    draft_usp_icp("Wir betreuen IT für Handwerker.", ki)

    assert "Wir betreuen IT für Handwerker." in ki.gefragt[0]


def test_geschwaetz_um_das_json_herum_stoert_nicht():
    ki = FakeKI("Gerne! Hier das Ergebnis:\n" + VOLLSTAENDIG + "\nViel Erfolg.")

    assert draft_usp_icp("text", ki)["usp"]


def test_usp_ohne_titel_zaehlen_nicht():
    ki = FakeKI(json.dumps({
        "usp": [{"titel": "", "erklaerung": "leer"},
                {"titel": "Echt", "erklaerung": "da"}],
        "icp": {"firmografisch": "Handwerk", "technografisch": "",
                "verhalten": "", "entscheider": ""}}))

    ergebnis = draft_usp_icp("text", ki)

    assert [u["titel"] for u in ergebnis["usp"]] == ["Echt"]


def test_leere_antwort_scheitert_laut():
    with pytest.raises(ValueError, match="unvollständig"):
        draft_usp_icp("text", FakeKI("keine Ahnung"))


def test_usp_ohne_icp_scheitert_laut():
    ki = FakeKI(json.dumps({
        "usp": [{"titel": "Schnell", "erklaerung": "sehr"}],
        "icp": {"firmografisch": "", "technografisch": "",
                "verhalten": "", "entscheider": ""}}))

    with pytest.raises(ValueError, match="unvollständig"):
        draft_usp_icp("text", ki)


def test_kaputtes_json_scheitert_laut_statt_halb():
    with pytest.raises(ValueError, match="unvollständig"):
        draft_usp_icp("text", FakeKI('{"usp": [{"titel": "abgeschnitten"'))
