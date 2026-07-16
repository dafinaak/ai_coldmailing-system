import pytest
from pipeline.sources.apollo import ApolloSource

class FakeResponse:
    def __init__(self, status_code, payload, text=""):
        self.status_code, self._payload, self.text = status_code, payload, text
    def json(self):
        return self._payload

class FakeSession:
    def __init__(self, antworten):
        self.antworten, self.aufrufe = list(antworten), []
    def post(self, url, json=None, headers=None, timeout=None):
        self.aufrufe.append(json)
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
