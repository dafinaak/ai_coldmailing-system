import pytest
from pipeline.sources.apollo import (ApolloSource, ORGANISATION_URL, ORGANISATION_SUCH_URL,
                                      _saubere_domain, _beste_namenstreffer)

class FakeResponse:
    def __init__(self, status_code, payload, text=""):
        self.status_code, self._payload, self.text = status_code, payload, text
    def json(self):
        return self._payload

class FakeSession:
    def __init__(self, antworten):
        self.antworten, self.aufrufe, self.urls = list(antworten), [], []
    def post(self, url, json=None, headers=None, timeout=None):
        self.aufrufe.append(json)
        self.urls.append(url)
        return self.antworten.pop(0)
    def get(self, url, params=None, headers=None, timeout=None):
        self.aufrufe.append(params)
        self.urls.append(url)
        return self.antworten.pop(0)

def treffer(pid, **overrides):
    """Ein Suchtreffer, wie ihn /mixed_people/api_search liefert: ohne E-Mail."""
    basis = {"id": pid, "first_name": "Anna", "last_name": "Muster", "title": "CEO",
              "organization": {"name": "Firma GmbH", "website_url": "https://firma.de"}}
    basis.update(overrides)
    return basis

def match(pid, **overrides):
    """Ein Anreicherungs-Treffer, wie ihn /people/bulk_match liefert: mit E-Mail."""
    basis = {"id": pid, "email": "anna@firma.de", "first_name": "Anna", "last_name": "Muster",
              "title": "CEO", "organization": {"name": "Firma GmbH", "website_url": "https://firma.de"}}
    basis.update(overrides)
    return basis

def test_mappt_personen_auf_leads():
    session = FakeSession([
        FakeResponse(200, {"people": [treffer("p1")]}),
        FakeResponse(200, {"matches": [match("p1")]}),
    ])
    leads = ApolloSource("key", session=session).search({"titel": ["CEO"]}, limit=10)
    assert leads[0].company == "Firma GmbH" and leads[0].source == "apollo"
    assert leads[0].email == "anna@firma.de"

def test_wiederholt_bei_429():
    session = FakeSession([
        FakeResponse(429, {}),
        FakeResponse(200, {"people": [treffer("p1")]}),
        FakeResponse(200, {"matches": [match("p1")]}),
    ])
    leads = ApolloSource("key", session=session, wartezeit=0).search({}, limit=10)
    assert len(leads) == 1 and len(session.aufrufe) == 3

def test_ueberspringt_leads_ohne_email():
    session = FakeSession([
        FakeResponse(200, {"people": [treffer("p1")]}),
        # bulk_match findet zwar eine Übereinstimmung, liefert aber keine E-Mail
        # zurück (z. B. weil Apollo für diese Person keine private E-Mail hat).
        FakeResponse(200, {"matches": [{"id": "p1", "first_name": "Anna"}]}),
    ])
    assert ApolloSource("key", session=session).search({}, limit=10) == []

def test_kein_retry_bei_401():
    session = FakeSession([FakeResponse(401, {"error": "unauthorized"})])
    with pytest.raises(RuntimeError):
        ApolloSource("key", session=session, wartezeit=0).search({}, limit=10)
    assert len(session.aufrufe) == 1  # kein zweiter Versuch bei einem 4xx-Fehler

def test_zaehlt_uebersprungene_leads_ohne_email():
    session = FakeSession([
        FakeResponse(200, {"people": [treffer("p1"), treffer("p2")]}),
        # p1 findet eine E-Mail, p2 bleibt ohne Treffer in bulk_match.
        FakeResponse(200, {"matches": [match("p1")]}),
    ])
    quelle = ApolloSource("key", session=session)
    leads = quelle.search({}, limit=10)
    assert len(leads) == 1
    assert quelle.uebersprungen_ohne_email == 1

def firma(**overrides):
    """Eine Firma, wie sie Stufe 1 (pipeline.sources.apify_maps) liefert."""
    basis = {"name": "Firma GmbH", "website": "https://firma.de", "domain": "firma.de",
             "address": "", "categories": []}
    basis.update(overrides)
    return basis

def organisation(**overrides):
    """Eine Apollo-Organisation, wie sie /organizations/enrich liefert."""
    basis = {"id": "org1", "name": "Firma GmbH", "website_url": "https://firma.de",
             "estimated_num_employees": 25}
    basis.update(overrides)
    return basis

def test_unternehmen_anreichern_findet_kontakte_ueber_domain():
    session = FakeSession([
        FakeResponse(200, {"organization": organisation()}),  # GET enrich ueber Domain
        FakeResponse(200, {"people": [treffer("p1")]}),        # POST people search
        FakeResponse(200, {"matches": [match("p1")]}),          # POST bulk_match
    ])
    ergebnis = ApolloSource("key", session=session).unternehmen_anreichern(firma(), ["CEO"])
    assert ergebnis["kontakte"] == [{"first_name": "Anna", "last_name": "Muster",
                                     "email": "anna@firma.de", "title": "CEO"}]
    assert ergebnis["mitarbeiterzahl"] == 25
    assert ergebnis["organization_id"] == "org1"
    # Lead-Qualitaets-Fix: der kanonische Apollo-Organisationsname wird
    # mitgeliefert, damit pipeline.sourcing ihn statt eines evtl.
    # verunreinigten Google-Maps-Titels nutzen kann.
    assert ergebnis["name"] == "Firma GmbH"
    # Erster Aufruf (GET) fragte ueber die Domain an, nicht ueber den Namen.
    assert session.urls[0] == ORGANISATION_URL
    assert session.aufrufe[0] == {"domain": "firma.de"}


# --- Bug-Fix (Apollo-422): Firmen ohne Domain (bzw. Domain ohne Treffer)
# muessen ueber den SUCH-Endpoint (ORGANISATION_SUCH_URL) gefunden werden,
# NIEMALS ueber den Enrich-Endpoint mit "name" - der antwortet in der Praxis
# zuverlaessig mit 422 auf jede namens-basierte Anfrage ohne Domain, siehe
# apollo.py-Kommentar. Das war der real beobachtete Bug: Firmen ohne
# Google-Maps-Webseite fielen dadurch faelschlich als "kein Kontakt" durch.

def test_unternehmen_anreichern_firma_ohne_domain_nutzt_namenssuche_statt_enrich_mit_name():
    firma_ohne_domain = {"name": "Firma GmbH", "website": "", "domain": "",
                         "address": "", "categories": []}
    session = FakeSession([
        FakeResponse(200, {"organizations": [organisation()]}),  # POST Namens-Suche
        FakeResponse(200, {"people": [treffer("p1")]}),           # POST people search
        FakeResponse(200, {"matches": [match("p1")]}),             # POST bulk_match
    ])
    ergebnis = ApolloSource("key", session=session).unternehmen_anreichern(
        firma_ohne_domain, ["CEO"])
    assert ergebnis["organization_id"] == "org1"
    assert ergebnis["kontakte"][0]["email"] == "anna@firma.de"
    # Der einzige Aufruf zur Organisations-Suche ging an den SUCH-Endpoint
    # (mixed_companies/search), NICHT an ORGANISATION_URL (organizations/
    # enrich) - der haette bei "name" ohne Domain mit 422 geantwortet.
    assert session.urls[0] == ORGANISATION_SUCH_URL
    assert session.aufrufe[0]["q_organization_name"] == "Firma GmbH"

def test_unternehmen_anreichern_faellt_bei_domain_ohne_treffer_auf_namenssuche_zurueck():
    session = FakeSession([
        FakeResponse(200, {"organization": None}),               # GET ueber Domain: kein Treffer
        FakeResponse(200, {"organizations": [organisation()]}),   # POST Namens-Suche: Treffer
        FakeResponse(200, {"people": []}),                        # POST people search: keine Treffer
    ])
    ergebnis = ApolloSource("key", session=session).unternehmen_anreichern(firma(), ["CEO"])
    assert ergebnis["organization_id"] == "org1"
    assert ergebnis["kontakte"] == []
    assert session.urls[0] == ORGANISATION_URL
    assert session.aufrufe[0] == {"domain": "firma.de"}
    assert session.urls[1] == ORGANISATION_SUCH_URL
    assert session.aufrufe[1]["q_organization_name"] == "Firma GmbH"

def test_unternehmen_anreichern_ohne_organisation_liefert_leeres_ergebnis():
    session = FakeSession([
        FakeResponse(200, {"organization": None}),      # GET ueber Domain: kein Treffer
        FakeResponse(200, {"organizations": []}),        # POST Namens-Suche: kein Treffer (kein 422!)
    ])
    ergebnis = ApolloSource("key", session=session).unternehmen_anreichern(firma(), ["CEO"])
    assert ergebnis == {"kontakte": [], "mitarbeiterzahl": None, "organization_id": None, "name": None}

def test_organisation_finden_ohne_domain_und_ohne_namen_liefert_none_ohne_aufruf():
    firma_ohne_beides = {"name": "", "website": "", "domain": "", "address": "", "categories": []}
    session = FakeSession([])  # jeder Aufruf wuerde IndexError werfen
    ergebnis = ApolloSource("key", session=session).unternehmen_anreichern(
        firma_ohne_beides, ["CEO"])
    assert ergebnis == {"kontakte": [], "mitarbeiterzahl": None, "organization_id": None, "name": None}
    assert session.aufrufe == []


# --- Bug-Fix (Apollo-422): messy Domain-Werte muessen VOR dem Apollo-Aufruf
# auf eine reine Domain bereinigt werden - eine kaputt formatierte Domain
# (volle URL, "www.", Pfad, Port, Query) darf nie selbst der Grund fuer
# einen 422 sein.

def test_saubere_domain_entfernt_schema_www_pfad_port_und_query():
    faelle = {
        "https://www.Firma.de/impressum/": "firma.de",
        "WWW.FIRMA.DE": "firma.de",
        "firma.de:8080/pfad": "firma.de",
        "firma.de?ref=xyz": "firma.de",
        "  https://firma.de  ".strip(): "firma.de",
        "": "",
    }
    for messy, sauber in faelle.items():
        assert _saubere_domain(messy) == sauber, messy

def test_unternehmen_anreichern_bereinigt_messy_domain_vor_dem_apollo_aufruf():
    firma_messy = firma(domain="https://www.Firma.de/impressum/")
    session = FakeSession([
        FakeResponse(200, {"organization": organisation()}),
        FakeResponse(200, {"people": []}),
    ])
    ApolloSource("key", session=session).unternehmen_anreichern(firma_messy, ["CEO"])
    assert session.aufrufe[0] == {"domain": "firma.de"}


# --- Bug-Fix (Apollo-422): Namens-Suche liefert oft mehrere Teilstring-
# Treffer - der EXAKTE Namens-Treffer (case-insensitive) muss bevorzugt
# werden, nicht einfach blind der erste.

def test_beste_namenstreffer_bevorzugt_exakten_namen_vor_dem_ersten_treffer():
    treffer_liste = [{"id": "org-falsch", "name": "Firma GmbH Nord"},
                      {"id": "org-richtig", "name": "Firma GmbH"}]
    assert _beste_namenstreffer(treffer_liste, "Firma GmbH")["id"] == "org-richtig"

def test_beste_namenstreffer_faellt_ohne_exakten_treffer_auf_erste_aehnliche_zurueck():
    # Beide Treffer "aehneln" der Suche (teilen das unterscheidungskraeftige
    # Token "firma"), keiner ist exakt - dann zaehlt die Apollo-Reihenfolge.
    treffer_liste = [{"id": "org-erster", "name": "Firma GmbH Nord"},
                      {"id": "org-zweiter", "name": "Firma GmbH Sued"}]
    assert _beste_namenstreffer(treffer_liste, "Firma GmbH")["id"] == "org-erster"

def test_beste_namenstreffer_ohne_treffer_liefert_none():
    assert _beste_namenstreffer([], "Firma GmbH") is None


# --- Review-Fund (MUSS vor dem Live-Re-Run behoben sein): _beste_namenstreffer
# fiel bisher OHNE Aehnlichkeits-Pruefung auf den ERSTEN Treffer zurueck.
# Apollos "q_organization_name" ist nur ein lockerer Teilstring-Abgleich -
# bei einem generischen Firmennamen liefert das routinemaessig eine
# VOELLIG FREMDE Firma. Deren kanonischer Name haette den Lead-Firmennamen
# ueberschrieben UND deren Kontakte waeren als "mit_kontakt" gezaehlt worden -
# eine unehrlich aufgeblasene Deckungsquote UND falsche Kontakte im Lauf.
# Fix: ein Treffer wird nur akzeptiert, wenn er der Suche wirklich
# "aehnelt" (siehe _aehnelt_sich) - sonst lieber KEIN Treffer
# (apollo_kein_treffer) als ein falscher.

def test_beste_namenstreffer_akzeptiert_aehnlichen_namen_mit_rechtsform_unterschied():
    # "Bindt Systems" (Suche) vs. "Bindt Systems GmbH" (Apollo-Treffer) -
    # nach Abstreifen der Rechtsform ein EXAKTER Match.
    treffer_liste = [{"id": "org1", "name": "Bindt Systems GmbH"}]
    ergebnis = _beste_namenstreffer(treffer_liste, "Bindt Systems")
    assert ergebnis is not None and ergebnis["id"] == "org1"

def test_beste_namenstreffer_akzeptiert_namen_als_praefix():
    # "einsnulleins" (Suche) steckt vollstaendig in "einsnulleins Hannover" -
    # klarer Fall von "eine Firma erweitert um einen Standortzusatz".
    treffer_liste = [{"id": "org1", "name": "einsnulleins Hannover"}]
    ergebnis = _beste_namenstreffer(treffer_liste, "einsnulleins")
    assert ergebnis is not None and ergebnis["id"] == "org1"

def test_beste_namenstreffer_lehnt_voellig_fremde_firma_ab():
    # Der Kern-Review-Fund: "IT Service" (Suche, sehr generisch) matcht bei
    # Apollos Teilstring-Suche auch "NY Marketing Unlimited" (Beispiel aus
    # der Apollo-Doku fuer q_organization_name) - die beiden Namen haben
    # NICHTS gemeinsam. Das darf NIE als Treffer durchgehen.
    treffer_liste = [{"id": "org-fremd", "name": "NY Marketing Unlimited"}]
    assert _beste_namenstreffer(treffer_liste, "IT Service") is None

def test_beste_namenstreffer_case_insensitiv_bei_exaktem_treffer():
    treffer_liste = [{"id": "org1", "name": "FIRMA GMBH"}]
    ergebnis = _beste_namenstreffer(treffer_liste, "firma gmbh")
    assert ergebnis is not None and ergebnis["id"] == "org1"

def test_beste_namenstreffer_lehnt_nur_generische_gemeinsame_woerter_ab():
    # "IT Service Hannover" und "Bau Service Hannover GmbH" teilen sich nur
    # generische Woerter (service/hannover) - kein unterscheidungskraeftiges
    # gemeinsames Token, also kein Treffer.
    treffer_liste = [{"id": "org-fremd", "name": "Bau Service Hannover GmbH"}]
    assert _beste_namenstreffer(treffer_liste, "IT Service Hannover") is None

def test_beste_namenstreffer_akzeptiert_gemeinsames_unterscheidungskraeftiges_token():
    # "Einsnulleins IT Service" und "Einsnulleins Consulting GmbH" teilen
    # sich das unterscheidungskraeftige Token "einsnulleins" (weder
    # Rechtsform noch generisches Wort) - das darf als Treffer durchgehen,
    # obwohl keiner der Namen im anderen als Teilstring steckt.
    treffer_liste = [{"id": "org1", "name": "Einsnulleins Consulting GmbH"}]
    ergebnis = _beste_namenstreffer(treffer_liste, "Einsnulleins IT Service")
    assert ergebnis is not None and ergebnis["id"] == "org1"

def test_organisation_ueber_namen_suchen_liefert_kein_treffer_statt_fremdfirma():
    # Ende-zu-Ende auf Session-Ebene: ein Apollo-Suchtreffer, der der
    # gesuchten Firma nicht aehnelt, darf unternehmen_anreichern() NICHT als
    # gefundene Organisation durchreichen - sonst wird die Firma faelschlich
    # als "mit_kontakt" gezaehlt und der Lead traegt den falschen Firmennamen.
    firma_ohne_domain = {"name": "IT Service", "website": "", "domain": "",
                         "address": "", "categories": []}
    session = FakeSession([
        FakeResponse(200, {"organizations": [{"id": "org-fremd",
                                              "name": "NY Marketing Unlimited"}]}),
    ])
    ergebnis = ApolloSource("key", session=session).unternehmen_anreichern(
        firma_ohne_domain, ["CEO"])
    assert ergebnis == {"kontakte": [], "mitarbeiterzahl": None,
                        "organization_id": None, "name": None}
    # Kein zweiter Aufruf (People-Suche) - es gab ja keine Organisation.
    assert len(session.aufrufe) == 1

def test_unternehmen_anreichern_nutzt_kontakt_rollen_als_person_titles():
    session = FakeSession([
        FakeResponse(200, {"organization": organisation()}),
        FakeResponse(200, {"people": []}),
    ])
    ApolloSource("key", session=session).unternehmen_anreichern(
        firma(), ["Geschäftsführer", "IT-Leiter"])
    people_search_body = session.aufrufe[1]
    assert people_search_body["person_titles"] == ["Geschäftsführer", "IT-Leiter"]
    assert people_search_body["organization_ids"] == ["org1"]

def test_reichert_treffer_in_batches_von_10_an():
    treffer_liste = [treffer(f"p{i}") for i in range(12)]
    session = FakeSession([
        FakeResponse(200, {"people": treffer_liste}),
        FakeResponse(200, {"matches": [match(f"p{i}") for i in range(10)]}),
        FakeResponse(200, {"matches": [match(f"p{i}") for i in range(10, 12)]}),
    ])
    leads = ApolloSource("key", session=session).search({}, limit=12)
    assert len(leads) == 12
    # 1 Such-Aufruf + 2 Anreicherungs-Aufrufe (10 IDs + 2 IDs)
    assert len(session.aufrufe) == 3
    erste_anreicherung, zweite_anreicherung = session.aufrufe[1], session.aufrufe[2]
    assert len(erste_anreicherung["details"]) == 10
    assert len(zweite_anreicherung["details"]) == 2
