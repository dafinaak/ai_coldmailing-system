import pytest
from pipeline.config import Kunde
from pipeline.sourcing import (source_leads, NoOpDrittquelle,
                                _rolle_passt, _kontakte_auswaehlen, _firmenname_saeubern)

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

def test_fehlerhafte_firma_bricht_den_lauf_nicht_ab():
    # Review-Fund: bei ~50 Firmen pro Lauf darf eine einzelne, voruebergehend
    # fehlerhafte Apollo-Anreicherung (401/422/500-nach-Retries als
    # RuntimeError) nicht den kompletten Lauf abbrechen - sonst gehen alle
    # bereits gefundenen Leads verloren UND das schon verbrauchte Apify-/
    # Apollo-Kontingent ist futsch. Firma 2 von 3 fliegt hier, der Lauf muss
    # trotzdem fertig werden, mit Leads fuer Firma 1 und 3.
    firmen = [_firma("f1.de"), _firma("f2.de"), _firma("f3.de")]

    class _FlackerndeApollo:
        def unternehmen_anreichern(self, firma, kontakt_rollen):
            if firma["domain"] == "f2.de":
                raise RuntimeError("Apollo antwortet mit 500 auf https://api.apollo.io/...")
            return {"kontakte": [{"first_name": "A", "last_name": "B",
                                  "email": f"a@{firma['domain']}", "title": "CEO"}],
                    "mitarbeiterzahl": 20, "organization_id": "org"}

    leads, deckung = source_leads(_kunde(), 10, "a", "b",
                                  apify_source=_FakeApify(firmen),
                                  apollo_source=_FlackerndeApollo())

    assert {l.email for l in leads} == {"a@f1.de", "a@f3.de"}
    # f2.de zaehlt weiter zu firmen_gesamt (Nenner der Deckungsquote), aber
    # NICHT zu firmen_mit_kontakt - eine flackernde Firma verschlechtert nur
    # die Zahl, statt den Lauf zu sprengen.
    assert deckung == {"firmen_gesamt": 3, "firmen_mit_kontakt": 2, "quote_prozent": 66.7}

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


# --- Lead-Qualitaets-Fix: Rollen-Synonym-Matcher (_rolle_passt) -----------

def test_managing_director_passt_zu_geschaeftsfuehrer():
    assert _rolle_passt("Managing Director", "Geschäftsführer") is True

def test_head_of_it_passt_zu_it_leiter():
    assert _rolle_passt("Head of IT", "IT-Leiter") is True

def test_unpassender_titel_matcht_weder_geschaeftsfuehrer_noch_it_leiter():
    assert _rolle_passt("Buchhalter", "Geschäftsführer") is False
    assert _rolle_passt("Buchhalter", "IT-Leiter") is False

def test_rolle_ausserhalb_der_synonymtabelle_faellt_auf_teilstring_ab():
    # "Head of Sales" steht in keiner Synonym-Gruppe - trotzdem soll ein
    # Titel, der die Rolle woertlich enthaelt, weiter matchen (generischer
    # Teilstring-Abgleich als Fallback).
    assert _rolle_passt("Head of Sales DACH", "Head of Sales") is True
    assert _rolle_passt("Buchhalter", "Head of Sales") is False


# --- Lead-Qualitaets-Fix: Deckelung + Prioritaet (_kontakte_auswaehlen) ---

def test_fuenf_passende_kontakte_werden_auf_zwei_gedeckelt():
    # Realer Probe-Fund: eine Firma lieferte 5x "Managing Director".
    kontakte = [{"first_name": f"P{i}", "last_name": "X", "email": f"p{i}@f.de",
                 "title": "Managing Director"} for i in range(5)]
    ausgewaehlt = _kontakte_auswaehlen(kontakte, ["Geschäftsführer", "IT-Leiter"], 2)
    assert len(ausgewaehlt) == 2

def test_geschaeftsfuehrer_wird_vor_it_leiter_gewaehlt_bei_deckelung():
    kontakte = [{"first_name": "I", "last_name": "T", "email": "it@f.de", "title": "Head of IT"},
                {"first_name": "G", "last_name": "F", "email": "gf@f.de", "title": "CEO"}]
    ausgewaehlt = _kontakte_auswaehlen(kontakte, ["Geschäftsführer", "IT-Leiter"], 1)
    assert len(ausgewaehlt) == 1
    assert ausgewaehlt[0]["email"] == "gf@f.de"

def test_kontakte_auswaehlen_ohne_treffer_liefert_leere_liste():
    kontakte = [{"first_name": "B", "last_name": "H", "email": "b@f.de", "title": "Buchhalter"}]
    assert _kontakte_auswaehlen(kontakte, ["Geschäftsführer", "IT-Leiter"], 2) == []


# --- Lead-Qualitaets-Fix: kein Rollentreffer -> info@ bzw. Best-Effort-1 --

def test_source_leads_kein_rollentreffer_kleinfirma_nutzt_info_at():
    firmen = [_firma("klein.de")]
    apollo_ergebnisse = {"klein.de": {
        "kontakte": [{"first_name": "B", "last_name": "H", "email": "b@klein.de",
                      "title": "Buchhalter"}],
        "mitarbeiterzahl": 3, "organization_id": "org1", "name": None}}
    leads, deckung = source_leads(_kunde(), 10, "a", "b",
                                  apify_source=_FakeApify(firmen),
                                  apollo_source=_FakeApollo(apollo_ergebnisse))
    assert len(leads) == 1
    assert leads[0].email == "info@klein.de"
    assert leads[0].source == "info@"

def test_source_leads_kein_rollentreffer_grossfirma_nutzt_einen_best_effort_kontakt():
    firmen = [_firma("gross.de")]
    apollo_ergebnisse = {"gross.de": {
        "kontakte": [
            {"first_name": "B", "last_name": "H", "email": "b@gross.de", "title": "Buchhalter"},
            {"first_name": "C", "last_name": "D", "email": "c@gross.de", "title": "Sekretär"},
        ],
        "mitarbeiterzahl": 40, "organization_id": "org2", "name": None}}
    leads, deckung = source_leads(_kunde(), 10, "a", "b",
                                  apify_source=_FakeApify(firmen),
                                  apollo_source=_FakeApollo(apollo_ergebnisse))
    # Bewusst genau EIN Kontakt (der erste von Apollo gelieferte), damit die
    # Firma nicht komplett verloren geht - nicht alle unpassenden Kontakte.
    assert len(leads) == 1
    assert leads[0].email == "b@gross.de"
    assert leads[0].source == "apollo"


# --- Lead-Qualitaets-Fix: Firmenname-Bereinigung (_firmenname_saeubern) ---

def test_firmenname_saeubern_entfernt_suchbegriff_praefix():
    assert (_firmenname_saeubern("IT-Dienstleister Hannover - Ihre Helden",
                                  "IT-Dienstleister Hannover")
            == "Ihre Helden")

def test_firmenname_saeubern_laesst_saubere_namen_unangetastet():
    assert _firmenname_saeubern("Ihre Helden GmbH", "IT-Dienstleister Hannover") == "Ihre Helden GmbH"

def test_firmenname_saeubern_laesst_echten_bindestrich_namen_unangetastet():
    # Der Praefix-Teil ("Müller") hat nichts mit dem Suchbegriff zu tun -
    # konservativ NICHT abschneiden, sonst geht ein echter Firmenname kaputt.
    assert (_firmenname_saeubern("Müller - Schmidt GbR", "IT-Dienstleister Hannover")
            == "Müller - Schmidt GbR")

def test_source_leads_bevorzugt_apollos_kanonischen_namen():
    # Apollo hat die Organisation gefunden und liefert den echten Namen -
    # der wird genutzt, NICHT der (hier sogar verunreinigte) Maps-Titel.
    firmen = [{"name": "IT-Dienstleister Hannover - Ihre Helden",
               "website": "https://ihrehelden.de", "domain": "ihrehelden.de",
               "address": "", "categories": []}]
    apollo_ergebnisse = {"ihrehelden.de": {
        "kontakte": [{"first_name": "Anna", "last_name": "M", "email": "anna@ihrehelden.de",
                      "title": "Geschäftsführerin"}],
        "mitarbeiterzahl": 8, "organization_id": "org3", "name": "Ihre Helden"}}
    leads, _ = source_leads(_kunde(), 10, "a", "b",
                            apify_source=_FakeApify(firmen),
                            apollo_source=_FakeApollo(apollo_ergebnisse))
    assert leads[0].company == "Ihre Helden"

def test_source_leads_faellt_ohne_apollo_organisation_auf_bereinigten_maps_namen_zurueck():
    # Apollo fand KEINE Organisation (name=None) -> Rueckfall auf den
    # bereinigten Google-Maps-Titel statt des rohen (verunreinigten) Titels.
    firmen = [{"name": "IT-Dienstleister Hannover - Ihre Helden",
               "website": "https://ihrehelden.de", "domain": "ihrehelden.de",
               "address": "", "categories": []}]
    apollo_ergebnisse = {"ihrehelden.de": {
        "kontakte": [], "mitarbeiterzahl": 2, "organization_id": None, "name": None}}
    leads, _ = source_leads(_kunde(), 10, "a", "b",
                            apify_source=_FakeApify(firmen),
                            apollo_source=_FakeApollo(apollo_ergebnisse))
    assert leads[0].company == "Ihre Helden"


# --- Ende-zu-Ende: realistische Firma -> <=2 gezielte Leads, sauberer Name -

def test_ende_zu_ende_realistische_firma_liefert_gezielte_leads_mit_sauberem_namen():
    # Nachbildung des Probe-Funds: Google Maps liefert einen verunreinigten
    # Titel, Apollo liefert 5 Kontakte (alle "Managing Director") plus einen
    # echten Organisationsnamen. Erwartung nach dem Fix: hoechstens 2 Leads
    # (Default max_kontakte_pro_firma), gezielt nach Rolle, sauberer Name.
    firmen = [{"name": "IT-Dienstleister Hannover - Ihre Helden",
               "website": "https://ihrehelden.de", "domain": "ihrehelden.de",
               "address": "Musterstr. 1, Hannover", "categories": ["IT-Dienstleister"]}]
    kontakte = [{"first_name": f"P{i}", "last_name": "M", "email": f"p{i}@ihrehelden.de",
                 "title": "Managing Director"} for i in range(5)]
    apollo_ergebnisse = {"ihrehelden.de": {
        "kontakte": kontakte, "mitarbeiterzahl": 8, "organization_id": "org4",
        "name": "Ihre Helden"}}
    kunde = _kunde(kontakt_rollen=["Geschäftsführer", "IT-Leiter"])
    leads, deckung = source_leads(kunde, 10, "a", "b",
                                  apify_source=_FakeApify(firmen),
                                  apollo_source=_FakeApollo(apollo_ergebnisse))
    assert len(leads) <= 2
    assert len(leads) == kunde.max_kontakte_pro_firma
    assert all(l.company == "Ihre Helden" for l in leads)
    assert all(l.title == "Managing Director" for l in leads)
    assert deckung == {"firmen_gesamt": 1, "firmen_mit_kontakt": 1, "quote_prozent": 100.0}
