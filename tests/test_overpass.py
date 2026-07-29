import pytest
from pipeline.sources.overpass import OverpassQuelle, BBOX_PLR_30_31
from tests.fakes import FakeSession, FakeResponse


def _antwort(elemente):
    return {"elements": elemente}


def _knoten(**tags):
    alle = {"name": "Nordfalke IT GmbH", "office": "it",
            "website": "https://www.nordfalke-it.de/",
            "phone": "+49 511 123456",
            "email": "info@nordfalke-it.de",
            "addr:postcode": "30159", "addr:city": "Hannover",
            "addr:street": "Beispielweg", "addr:housenumber": "2", **tags}
    return {"type": "node", "id": 1, "lat": 52.3, "lon": 9.7, "tags": alle}


def test_abfrage_nutzt_rechteck_und_normalisiert():
    session = FakeSession([FakeResponse(200, _antwort([_knoten()]))])
    quelle = OverpassQuelle(session=session)
    firmen = quelle.search(plz_praefixe=("30", "31"), bbox=BBOX_PLR_30_31)
    abfrage, = session.aufrufe
    # Rechteck-Suche (schnell) statt PLZ-Gebiets-Suche (504-Timeout,
    # live beobachtet 29.07.2026):
    assert '"office"="it"' in abfrage["data"]
    assert "51.7" in abfrage["data"] and "10.6" in abfrage["data"]
    f, = firmen
    assert f["name"] == "Nordfalke IT GmbH"
    assert f["domain"] == "nordfalke-it.de"
    assert f["plz"] == "30159"
    assert f["telefon"] == "+49 511 123456"
    assert f["vorhandene_email"] == "info@nordfalke-it.de"
    assert f["address"] == "Beispielweg 2, 30159 Hannover"
    assert f["quelle"] == "overpass"


def test_plz_filter_wirft_fremde_raus_und_behaelt_unbekannte():
    im_gebiet = _knoten()
    fremd = _knoten(**{"addr:postcode": "29221"})
    ohne_plz = _knoten()
    del ohne_plz["tags"]["addr:postcode"]
    session = FakeSession([FakeResponse(200, _antwort([im_gebiet, fremd,
                                                      ohne_plz]))])
    firmen = OverpassQuelle(session=session).search(
        plz_praefixe=("30", "31"), bbox=BBOX_PLR_30_31)
    assert len(firmen) == 2                      # 29221 fliegt raus
    assert {f["plz"] for f in firmen} == {"30159", ""}


def test_contact_praefix_felder_werden_gelesen_und_namenlose_verworfen():
    mit_contact = _knoten()
    del mit_contact["tags"]["website"], mit_contact["tags"]["phone"]
    mit_contact["tags"]["contact:website"] = "nordfalke-it.de"
    mit_contact["tags"]["contact:phone"] = "+49 511 9"
    ohne_name = _knoten()
    del ohne_name["tags"]["name"]
    session = FakeSession([FakeResponse(200, _antwort([mit_contact, ohne_name]))])
    firmen = OverpassQuelle(session=session).search(
        plz_praefixe=("30",), bbox=BBOX_PLR_30_31)
    f, = firmen                       # der namenlose Eintrag fliegt raus
    assert f["domain"] == "nordfalke-it.de"
    assert f["telefon"] == "+49 511 9"


def test_ueberlastung_weicht_auf_zweiten_server_aus():
    # 504 live beobachtet am 29.07.2026: derselbe Abruf lief eine Stunde
    # vorher sauber - der Gratis-Dienst ist lastabhaengig. Deshalb:
    # Haupt-Server scheitert -> Ausweich-Server uebernimmt, mit Wartezeit.
    session = FakeSession([FakeResponse(504, {}, text="ueberlastet"),
                           FakeResponse(200, _antwort([_knoten()]))])
    pausen = []
    quelle = OverpassQuelle(session=session, wartezeit=7, schlaf=pausen.append)
    firmen = quelle.search(plz_praefixe=("30",), bbox=BBOX_PLR_30_31)
    assert len(firmen) == 1
    assert len(session.urls) == 2
    assert session.urls[0] != session.urls[1]     # zweiter Versuch = Mirror
    assert pausen == [7]                          # eine Wartezeit dazwischen


def test_abgerissene_verbindung_wird_wie_fehler_wiederholt():
    # Live beobachtet 29.07.2026: ReadTimeout vom Ausweich-Server nach
    # 240s - eine Ausnahme, keine Fehler-Antwort. Muss genauso in die
    # Wiederholung gehen statt den Lauf zu reissen.
    import requests as _requests
    session = FakeSession([_requests.exceptions.ReadTimeout("abgerissen"),
                           FakeResponse(200, _antwort([_knoten()]))])
    quelle = OverpassQuelle(session=session, schlaf=lambda s: None)
    firmen = quelle.search(plz_praefixe=("30",), bbox=BBOX_PLR_30_31)
    assert len(firmen) == 1


def test_nur_abrisse_stoppen_laut_mit_klarer_meldung():
    import requests as _requests
    session = FakeSession([_requests.exceptions.ReadTimeout("langsam")] * 4)
    with pytest.raises(RuntimeError, match="nicht erreichbar"):
        OverpassQuelle(session=session, schlaf=lambda s: None).search(
            plz_praefixe=("30",), bbox=BBOX_PLR_30_31)


def test_dauerhafte_fehler_stoppen_laut():
    session = FakeSession([FakeResponse(429, {"remark": "voll"})] * 4)
    with pytest.raises(RuntimeError, match="Overpass antwortet mit 429"):
        OverpassQuelle(session=session, schlaf=lambda s: None).search(
            plz_praefixe=("30",), bbox=BBOX_PLR_30_31)
    assert len(session.urls) == 4                 # 2 Server x 2 Runden
