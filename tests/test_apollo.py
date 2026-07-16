from pipeline.sources.apollo import ApolloSource

class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code, self._payload = status_code, payload
    def json(self):
        return self._payload

class FakeSession:
    def __init__(self, antworten):
        self.antworten, self.aufrufe = list(antworten), []
    def post(self, url, json=None, headers=None, timeout=None):
        self.aufrufe.append(json)
        return self.antworten.pop(0)

PERSON = {"first_name": "Anna", "last_name": "Muster", "email": "anna@firma.de",
          "title": "CEO", "organization": {"name": "Firma GmbH", "website_url": "https://firma.de"}}

def test_mappt_personen_auf_leads():
    session = FakeSession([FakeResponse(200, {"people": [PERSON]})])
    leads = ApolloSource("key", session=session).search({"titel": ["CEO"]}, limit=10)
    assert leads[0].company == "Firma GmbH" and leads[0].source == "apollo"

def test_wiederholt_bei_429():
    session = FakeSession([FakeResponse(429, {}), FakeResponse(200, {"people": [PERSON]})])
    leads = ApolloSource("key", session=session, wartezeit=0).search({}, limit=10)
    assert len(leads) == 1 and len(session.aufrufe) == 2

def test_ueberspringt_leads_ohne_email():
    ohne = dict(PERSON, email=None)
    session = FakeSession([FakeResponse(200, {"people": [ohne]})])
    assert ApolloSource("key", session=session).search({}, limit=10) == []
