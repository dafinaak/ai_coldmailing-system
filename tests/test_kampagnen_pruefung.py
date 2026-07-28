import pytest
from pipeline.kampagnen_pruefung import referenz_aus_kampagne, abweichungen


def _kampagne(betreff2="Betreff 2", text2="<p>Text 2</p>"):
    return {"sequences": [{"steps": [
        {"variants": [{"subject": "Betreff 1", "body": "<p>Text 1</p>"}]},
        {"variants": [{"subject": betreff2, "body": text2}]},
    ]}]}


def test_referenz_haelt_betreff_und_text_jeder_stufe_fest():
    referenz = referenz_aus_kampagne(_kampagne())
    assert referenz == {"stufen": [
        {"betreff": "Betreff 1", "text": "<p>Text 1</p>"},
        {"betreff": "Betreff 2", "text": "<p>Text 2</p>"},
    ]}


def test_unveraenderte_kampagne_meldet_keine_abweichung():
    referenz = referenz_aus_kampagne(_kampagne())
    assert abweichungen(referenz, _kampagne()) == []


def test_geaenderter_text_und_betreff_werden_gemeldet():
    referenz = referenz_aus_kampagne(_kampagne())
    meldungen = abweichungen(referenz, _kampagne(betreff2="Neuer Betreff",
                                                 text2="<p>umgeschrieben</p>"))
    assert len(meldungen) == 2
    assert any("Stufe 2" in m and "Betreff" in m for m in meldungen)
    assert any("Stufe 2" in m and "Text" in m for m in meldungen)


def test_geloeschte_stufe_wird_gemeldet():
    referenz = referenz_aus_kampagne(_kampagne())
    halbiert = {"sequences": [{"steps":
                _kampagne()["sequences"][0]["steps"][:1]}]}
    meldungen = abweichungen(referenz, halbiert)
    assert any("Stufen" in m for m in meldungen)
