import pytest
from pipeline.sources.gelbe_seiten import GelbeSeitenQuelle
from tests.fakes import FakeSession, FakeResponse


def _eintrag(**extra):
    # Feldnamen wie im Mini-Lauf am 29.07.2026 gegen den echten Actor
    # (plowdata~gelbe-seiten-ppr) beobachtet.
    return {"name": "TORUTEC GmbH",
            "address": "Nikolaistr. 14, 30159 Hannover (Mitte)",
            "phone": "+49511592910",
            "website": "https://torutec.com/it-dienstleister/hannover/",
            "email": "kontakt@torutec.com",
            "industries": ["IT-Dienstleistungen"], **extra}


def test_suche_ruft_actor_und_normalisiert_ins_firmen_format():
    session = FakeSession([FakeResponse(200, [_eintrag()])])
    quelle = GelbeSeitenQuelle("token-1", session=session)
    firmen = quelle.search("IT-Dienstleister", ort="Hannover", max_seiten=2)
    anfrage, = session.aufrufe
    assert anfrage == {"query": "IT-Dienstleister", "location": "Hannover",
                       "maxPages": 2}
    f, = firmen
    assert f["name"] == "TORUTEC GmbH"
    assert f["domain"] == "torutec.com"
    assert f["website"].startswith("https://torutec.com")
    assert f["plz"] == "30159"
    assert f["telefon"] == "+49511592910"
    assert f["vorhandene_email"] == "kontakt@torutec.com"
    assert f["categories"] == ["IT-Dienstleistungen"]
    assert f["quelle"] == "gelbe_seiten"


def test_eintrag_ohne_website_und_ohne_plz_bleibt_nutzbar():
    session = FakeSession([FakeResponse(200, [
        _eintrag(website=None, email=None, address="Irgendwo 1, Hannover")])])
    firmen = GelbeSeitenQuelle("t", session=session).search("x", ort="Hannover")
    f, = firmen
    assert f["website"] == "" and f["domain"] == ""
    assert f["plz"] == "" and f["vorhandene_email"] == ""


def test_http_fehler_stoppt_laut():
    session = FakeSession([FakeResponse(500, {"error": "kaputt"})])
    with pytest.raises(RuntimeError, match="Apify antwortet mit 500"):
        GelbeSeitenQuelle("t", session=session).search("x", ort="Hannover")


def test_unerwartetes_format_stoppt_laut():
    session = FakeSession([FakeResponse(200, {"keine": "liste"})])
    with pytest.raises(RuntimeError, match="keine Liste"):
        GelbeSeitenQuelle("t", session=session).search("x", ort="Hannover")
