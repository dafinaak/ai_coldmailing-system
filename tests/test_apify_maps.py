import pytest
from pipeline.sources.apify_maps import ApifyMapsSource, ACTOR_ID

class FakeResponse:
    def __init__(self, status_code, payload, text=""):
        self.status_code, self._payload, self.text = status_code, payload, text
    def json(self):
        return self._payload

class FakeSession:
    """Wie das FakeSession-Muster in tests/fakes.py: eine feste Warteschlange
    an Antworten, jeder Aufruf wird protokolliert. Nur .post() noetig, weil der
    genutzte Apify-Endpunkt (run-sync-get-dataset-items) ein einzelner POST ist."""
    def __init__(self, antworten):
        self.antworten, self.aufrufe = list(antworten), []
    def post(self, url, json=None, headers=None, timeout=None):
        self.aufrufe.append({"url": url, "json": json})
        return self.antworten.pop(0)

def eintrag(**overrides):
    """Ein Dataset-Eintrag, wie ihn der Google-Maps-Scraper-Actor liefert
    (bestaetigtes Beispiel aus apify.com/compass/crawler-google-places)."""
    basis = {"title": "IT Muster GmbH", "website": "https://www.it-muster.de/",
             "address": "Musterstr. 1, 30159 Hannover", "categoryName": "IT-Dienstleister"}
    basis.update(overrides)
    return basis

def test_actor_id_ist_der_verifizierte_google_maps_scraper():
    # apify.com/compass/crawler-google-places - Actor-ID im API-Pfad mit
    # Tilde statt Slash (Apify-Konvention).
    assert ACTOR_ID == "compass~crawler-google-places"

def test_mappt_dataset_eintraege_auf_firmen():
    session = FakeSession([FakeResponse(200, [eintrag()])])
    firmen = ApifyMapsSource("key", session=session).search("IT-Dienstleister Hannover", limit=5)
    assert len(firmen) == 1
    firma = firmen[0]
    assert firma["name"] == "IT Muster GmbH"
    assert firma["website"] == "https://www.it-muster.de/"
    assert firma["domain"] == "it-muster.de"
    assert firma["address"] == "Musterstr. 1, 30159 Hannover"
    assert firma["categories"] == ["IT-Dienstleister"]

def test_uebernimmt_categories_liste_wenn_vorhanden():
    session = FakeSession([FakeResponse(
        200, [eintrag(categories=["IT-Dienstleister", "Softwarehaus"])])])
    firmen = ApifyMapsSource("key", session=session).search("x", limit=5)
    assert firmen[0]["categories"] == ["IT-Dienstleister", "Softwarehaus"]

def test_sendet_suchbegriff_und_limit_als_actor_input():
    session = FakeSession([FakeResponse(200, [])])
    ApifyMapsSource("key", session=session).search("IT-Dienstleister Hannover", limit=3)
    gesendet = session.aufrufe[0]["json"]
    assert gesendet["searchStringsArray"] == ["IT-Dienstleister Hannover"]
    assert gesendet["maxCrawledPlacesPerSearch"] == 3

def test_token_und_actor_id_stehen_in_der_url():
    session = FakeSession([FakeResponse(200, [])])
    ApifyMapsSource("mein-token", session=session).search("x", limit=1)
    url = session.aufrufe[0]["url"]
    assert "token=mein-token" in url
    assert ACTOR_ID in url

def test_ohne_website_bleibt_domain_leer():
    session = FakeSession([FakeResponse(200, [eintrag(website="")])])
    firmen = ApifyMapsSource("key", session=session).search("x", limit=1)
    assert firmen[0]["website"] == "" and firmen[0]["domain"] == ""

def test_domain_ohne_www_praefix():
    session = FakeSession([FakeResponse(200, [eintrag(website="https://www.beispiel.de/impressum")])])
    firmen = ApifyMapsSource("key", session=session).search("x", limit=1)
    assert firmen[0]["domain"] == "beispiel.de"

def test_begrenzt_ergebnisse_auf_limit():
    session = FakeSession([FakeResponse(200, [eintrag(), eintrag(), eintrag()])])
    firmen = ApifyMapsSource("key", session=session).search("x", limit=2)
    assert len(firmen) == 2

def test_wirft_fehler_bei_http_fehler():
    session = FakeSession([FakeResponse(500, {}, text="Server-Fehler")])
    with pytest.raises(RuntimeError):
        ApifyMapsSource("key", session=session).search("x", limit=5)
