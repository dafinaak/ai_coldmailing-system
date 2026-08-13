"""Der zuletzt gesehene Dropcontact-Guthabenstand.

Die Gefahr hier ist nicht, dass die Zahl fehlt - sondern dass sie
selbstsicher falsch dasteht. Deshalb: nie raten, nie ohne Zeitpunkt,
und ein Schreibfehler darf niemals einen bezahlten Lauf mitreissen.
"""
import json

from pipeline.guthaben import merken, stand
from pipeline.sources.dropcontact import DropcontactSource
from tests.test_dropcontact import FakeResponse, FakeSession


def test_ohne_gesehene_zahl_gibt_es_keine(tmp_path):
    assert stand(tmp_path) is None


def test_gemerkter_stand_kommt_mit_zeitpunkt_zurueck(tmp_path):
    merken(187, tmp_path)

    ergebnis = stand(tmp_path)

    assert ergebnis["credits_left"] == 187
    assert ergebnis["stand_text"] != "unbekannt"


def test_neuer_stand_ersetzt_den_alten(tmp_path):
    merken(200, tmp_path)
    merken(150, tmp_path)

    assert stand(tmp_path)["credits_left"] == 150


def test_unsinnige_werte_werden_nicht_gemerkt(tmp_path):
    merken(None, tmp_path)
    merken("viele", tmp_path)

    assert stand(tmp_path) is None


def test_kaputte_datei_gilt_als_unbekannt(tmp_path):
    merken(100, tmp_path)
    (tmp_path / "dropcontact-guthaben.json").write_text("{kaputt")

    assert stand(tmp_path) is None


def test_keine_halbe_datei(tmp_path):
    merken(100, tmp_path)

    assert list(tmp_path.glob("*.tmp")) == []
    json.loads((tmp_path / "dropcontact-guthaben.json").read_text())


def test_dropcontact_merkt_sich_den_stand_beim_abgeben(tmp_path, monkeypatch):
    # Der Wert kommt als Beiprodukt jeder angenommenen Anfrage - genau so
    # soll er auch eingesammelt werden, ohne eigene Abfrage.
    monkeypatch.chdir(tmp_path)
    session = FakeSession([FakeResponse(200, {
        "error": False, "request_id": "r1", "success": True, "credits_left": 42})])
    quelle = DropcontactSource("key", session=session, batch_wartezeit=0)

    quelle.batch_abgeben([{"first_name": "Anna", "last_name": "Muster",
                           "website": "https://a.de"}])

    assert stand(tmp_path)["credits_left"] == 42


def test_fehlende_zahl_stoert_den_lauf_nicht(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    session = FakeSession([FakeResponse(200, {
        "error": False, "request_id": "r1", "success": True})])
    quelle = DropcontactSource("key", session=session, batch_wartezeit=0)

    request_id, _ = quelle.batch_abgeben([{"first_name": "Anna",
                                           "last_name": "Muster",
                                           "website": "https://a.de"}])

    assert request_id == "r1"
    assert stand(tmp_path) is None
