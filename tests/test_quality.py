from pipeline.quality import check
from tests.test_personalize import KUNDE, LEAD, FakeKI

GUT = {"betreff": "Rohrbau und Angebotsprozesse", "mail_1": " ".join(["Wort"] * 80),
       "follow_up_1": "Kurz nachgefasst.", "follow_up_2": "Letzter Anstoss."}

def test_regeln_fangen_platzhalter():
    kaputt = dict(GUT, mail_1="Hallo {anrede_name}, " + " ".join(["Wort"] * 60))
    ok, grund = check(kaputt, LEAD, KUNDE, FakeKI("JA"))
    assert not ok and "Platzhalter" in grund

def test_ki_urteil_nein_faellt_durch():
    ok, grund = check(GUT, LEAD, KUNDE, FakeKI("NEIN: klingt nach Massenmail"))
    assert not ok

def test_alles_gut_besteht():
    ok, _ = check(GUT, LEAD, KUNDE, FakeKI("JA"))
    assert ok
