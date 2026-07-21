import pytest
from pipeline.config import Kunde
from pipeline.sourcing import source_leads, NoOpDrittquelle

class _FakeApify:
    def __init__(self, firmen):
        self._firmen = firmen
    def search(self, suchbegriff, limit):
        return self._firmen[:limit]

class _FakeApollo:
    def __init__(self, ergebnisse_je_domain):
        self._ergebnisse = ergebnisse_je_domain
    def unternehmen_anreichern(self, firma, kontakt_rollen):
        return self._ergebnisse[firma["domain"]]

def _kunde(**overrides):
    basis = dict(name="Demo", zielgruppe={}, angebot="A", tonalitaet="T", absender="Ab",
                 follow_up_tage=[1, 2], test_empfaenger=["t@example.com"],
                 maps_suche="IT-Dienstleister Hannover", kontakt_rollen=["Geschäftsführer"])
    basis.update(overrides)
    return Kunde(**basis)

def _firma(domain, name=None):
    return {"name": name or domain, "website": f"https://{domain}", "domain": domain,
            "address": "", "categories": []}

def test_leads_werden_aus_stufe_2_kontakten_gebaut():
    firmen = [_firma("firma-a.de")]
    apollo_ergebnisse = {"firma-a.de": {
        "kontakte": [{"first_name": "Anna", "last_name": "M",
                      "email": "anna@firma-a.de", "title": "CEO"}],
        "mitarbeiterzahl": 30, "organization_id": "org1"}}
    leads, deckung = source_leads(_kunde(), 10, "apify-key", "apollo-key",
                                  apify_source=_FakeApify(firmen),
                                  apollo_source=_FakeApollo(apollo_ergebnisse))
    assert len(leads) == 1
    lead = leads[0]
    assert lead.email == "anna@firma-a.de"
    assert lead.first_name == "Anna" and lead.company == "firma-a.de"
    assert lead.source == "apollo"
    assert deckung == {"firmen_gesamt": 1, "firmen_mit_kontakt": 1, "quote_prozent": 100.0}

def test_info_at_regel_fuer_kleinfirma_ohne_persoenlichen_kontakt():
    firmen = [_firma("klein.de")]
    apollo_ergebnisse = {"klein.de": {"kontakte": [], "mitarbeiterzahl": 3,
                                      "organization_id": "org2"}}
    leads, deckung = source_leads(_kunde(), 10, "a", "b",
                                  apify_source=_FakeApify(firmen),
                                  apollo_source=_FakeApollo(apollo_ergebnisse))
    assert len(leads) == 1
    assert leads[0].email == "info@klein.de"
    assert leads[0].source == "info@"
    assert deckung["firmen_mit_kontakt"] == 1

def test_keine_info_at_regel_ueber_der_kleinfirmen_grenze():
    firmen = [_firma("gross.de")]
    apollo_ergebnisse = {"gross.de": {"kontakte": [], "mitarbeiterzahl": 4,
                                      "organization_id": "org3"}}
    leads, deckung = source_leads(_kunde(), 10, "a", "b",
                                  apify_source=_FakeApify(firmen),
                                  apollo_source=_FakeApollo(apollo_ergebnisse))
    assert leads == []
    assert deckung == {"firmen_gesamt": 1, "firmen_mit_kontakt": 0, "quote_prozent": 0.0}

def test_keine_info_at_regel_ohne_bekannte_mitarbeiterzahl():
    # Apollo fand ueberhaupt keine Organisation -> mitarbeiterzahl ist None,
    # nicht "0" - die info@-Regel darf nur bei TATSAECHLICH bekannter,
    # kleiner Mitarbeiterzahl greifen, nie als Rate-ins-Blaue.
    firmen = [_firma("unbekannt.de")]
    apollo_ergebnisse = {"unbekannt.de": {"kontakte": [], "mitarbeiterzahl": None,
                                          "organization_id": None}}
    leads, deckung = source_leads(_kunde(), 10, "a", "b",
                                  apify_source=_FakeApify(firmen),
                                  apollo_source=_FakeApollo(apollo_ergebnisse))
    assert leads == []
    assert deckung["firmen_mit_kontakt"] == 0

def test_deckungsquote_beispiel_aus_dem_auftrag_5_firmen_4_mit_kontakt():
    firmen = [_firma(f"f{i}.de") for i in range(5)]
    apollo_ergebnisse = {
        f"f{i}.de": {"kontakte": [{"first_name": "A", "last_name": "B",
                                   "email": f"a@f{i}.de", "title": "CEO"}],
                     "mitarbeiterzahl": 20, "organization_id": f"org{i}"}
        for i in range(4)}
    apollo_ergebnisse["f4.de"] = {"kontakte": [], "mitarbeiterzahl": 50, "organization_id": "org4"}
    leads, deckung = source_leads(_kunde(), 10, "a", "b",
                                  apify_source=_FakeApify(firmen),
                                  apollo_source=_FakeApollo(apollo_ergebnisse))
    assert deckung == {"firmen_gesamt": 5, "firmen_mit_kontakt": 4, "quote_prozent": 80.0}

def test_deckungsquote_ohne_firmen_ist_null_statt_division_durch_null():
    leads, deckung = source_leads(_kunde(), 10, "a", "b",
                                  apify_source=_FakeApify([]), apollo_source=_FakeApollo({}))
    assert leads == []
    assert deckung == {"firmen_gesamt": 0, "firmen_mit_kontakt": 0, "quote_prozent": 0.0}

def test_drittquelle_wird_genutzt_wenn_apollo_nichts_findet():
    firmen = [_firma("dritt.de")]
    apollo_ergebnisse = {"dritt.de": {"kontakte": [], "mitarbeiterzahl": 20,
                                      "organization_id": "org5"}}
    class _FakeDrittquelle:
        def finde_kontakte(self, firma):
            return [{"first_name": "X", "last_name": "Y", "email": "x@dritt.de", "title": "CTO"}]
    leads, deckung = source_leads(_kunde(), 10, "a", "b",
                                  apify_source=_FakeApify(firmen),
                                  apollo_source=_FakeApollo(apollo_ergebnisse),
                                  drittquelle=_FakeDrittquelle())
    assert leads[0].email == "x@dritt.de"
    assert deckung["firmen_mit_kontakt"] == 1

def test_noop_drittquelle_liefert_nie_kontakte():
    assert NoOpDrittquelle().finde_kontakte({"name": "x", "domain": "x.de"}) == []

def test_fehlende_maps_suche_wirft_klaren_deutschen_fehler():
    kunde = _kunde(maps_suche="")
    with pytest.raises(ValueError, match="maps_suche"):
        source_leads(kunde, 10, "a", "b", apify_source=_FakeApify([]), apollo_source=_FakeApollo({}))

def test_fehlende_kontakt_rollen_wirft_klaren_deutschen_fehler():
    kunde = _kunde(kontakt_rollen=[])
    with pytest.raises(ValueError, match="kontakt_rollen"):
        source_leads(kunde, 10, "a", "b", apify_source=_FakeApify([]), apollo_source=_FakeApollo({}))

def test_ohne_injizierte_quellen_werden_die_echten_klassen_mit_den_keys_gebaut():
    # Kein echter Netzwerkaufruf hier - nur pruefen, dass source_leads() ohne
    # apify_source/apollo_source nicht sofort mit TypeError/AttributeError
    # stirbt, weil es versucht ApifyMapsSource/ApolloSource selbst zu bauen.
    # Das eigentliche Netzwerkverhalten ist in test_apify_maps.py/test_apollo.py
    # abgedeckt; hier reicht ein leeres Firmen-Ergebnis ueber einen Fake,
    # der die echten Konstruktor-Signaturen spiegelt (api_key, session=None).
    from pipeline.sources.apify_maps import ApifyMapsSource
    from pipeline.sources.apollo import ApolloSource
    import pipeline.sourcing as sourcing_modul

    aufgerufen_mit = {}
    class _SpionApify(ApifyMapsSource):
        def __init__(self, api_key):
            aufgerufen_mit["apify_key"] = api_key
            self._firmen = []
        def search(self, suchbegriff, limit):
            return self._firmen

    class _SpionApollo(ApolloSource):
        def __init__(self, api_key):
            aufgerufen_mit["apollo_key"] = api_key

    original_apify, original_apollo = sourcing_modul.ApifyMapsSource, sourcing_modul.ApolloSource
    sourcing_modul.ApifyMapsSource, sourcing_modul.ApolloSource = _SpionApify, _SpionApollo
    try:
        leads, deckung = source_leads(_kunde(), 10, "mein-apify-key", "mein-apollo-key")
    finally:
        sourcing_modul.ApifyMapsSource, sourcing_modul.ApolloSource = original_apify, original_apollo

    assert leads == []
    assert deckung == {"firmen_gesamt": 0, "firmen_mit_kontakt": 0, "quote_prozent": 0.0}
    assert aufgerufen_mit == {"apify_key": "mein-apify-key", "apollo_key": "mein-apollo-key"}
