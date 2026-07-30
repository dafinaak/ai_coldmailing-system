import pytest
from web.crm_speicher import KontakteSpeicher, STUFEN


def _speicher(tmp_path, uhr=None):
    return KontakteSpeicher(tmp_path / "kontakte.db",
                            uhr=uhr or (lambda: "2026-07-29T12:00:00"))


def test_kontakt_anlegen_und_lesen(tmp_path):
    s = _speicher(tmp_path)
    neu = s.kontakt_anlegen("m.ehlers@itanix.de", name="Malte Ehlers",
                            firma="ITANIX GmbH", kampagne="partnerschaft-it")
    assert neu is True
    k, = s.kontakte()
    assert k["email"] == "m.ehlers@itanix.de"
    assert k["name"] == "Malte Ehlers"
    assert k["firma"] == "ITANIX GmbH"
    assert k["kampagne"] == "partnerschaft-it"
    assert k["stufe"] == "neuer_lead"          # Einstiegs-Stufe
    assert k["angelegt_am"] == "2026-07-29T12:00:00"


def test_doppelte_email_wird_nicht_doppelt_angelegt(tmp_path):
    # Entscheidung 29.07.: je E-Mail-Adresse genau ein Kontakt.
    s = _speicher(tmp_path)
    assert s.kontakt_anlegen("a@b.de", name="A", firma="B", kampagne="k1")
    assert s.kontakt_anlegen("a@b.de", name="Anders", firma="B", kampagne="k1") is False
    assert len(s.kontakte()) == 1
    assert s.kontakte()[0]["name"] == "A"      # Erstes gewinnt, nichts ueberschrieben


def test_stufe_wechseln_mit_zeitstempel_und_nur_gueltige_stufen(tmp_path):
    zeiten = iter(["2026-07-29T12:00:00", "2026-07-30T09:00:00"])
    s = _speicher(tmp_path, uhr=lambda: next(zeiten))
    s.kontakt_anlegen("a@b.de", name="A", firma="B", kampagne="k1")
    s.stufe_setzen("a@b.de", "angebot")
    k, = s.kontakte()
    assert k["stufe"] == "angebot"
    assert k["stufe_geaendert_am"] == "2026-07-30T09:00:00"
    with pytest.raises(ValueError, match="Unbekannte Stufe"):
        s.stufe_setzen("a@b.de", "raketenstart")


def test_filter_und_zaehler_je_kampagne(tmp_path):
    # Entscheidung 29.07.: mehrere Kampagnen von Beginn an - Brett je
    # Kampagne, Zaehler je Stufe.
    s = _speicher(tmp_path)
    s.kontakt_anlegen("a@x.de", name="A", firma="X", kampagne="partnerschaft")
    s.kontakt_anlegen("b@y.de", name="B", firma="Y", kampagne="partnerschaft")
    s.kontakt_anlegen("c@z.de", name="C", firma="Z", kampagne="seo")
    s.stufe_setzen("b@y.de", "gewonnen")
    assert len(s.kontakte(kampagne="partnerschaft")) == 2
    assert len(s.kontakte(kampagne="partnerschaft", stufe="gewonnen")) == 1
    z = s.zaehler(kampagne="partnerschaft")
    assert z["alle"] == 2
    assert z["neuer_lead"] == 1 and z["gewonnen"] == 1
    assert z["verloren"] == 0
    assert s.zaehler()["alle"] == 3            # ohne Filter: alle Kampagnen


def test_stufen_sind_die_sechs_deutschen_wholix_stufen():
    assert list(STUFEN) == ["neuer_lead", "demo_termin", "nachfassen",
                            "angebot", "gewonnen", "verloren"]
