import pytest
from pipeline.sources.prospeo import ProspeoSource, SUCH_URL, ANREICHERN_URL


class FakeResponse:
    def __init__(self, status_code, payload, text=""):
        self.status_code, self._payload, self.text = status_code, payload, text
    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, antworten):
        self.antworten, self.urls, self.bodies, self.headers = list(antworten), [], [], []
    def post(self, url, json=None, headers=None, timeout=None):
        self.urls.append(url)
        self.bodies.append(json)
        self.headers.append(headers)
        return self.antworten.pop(0)


def person(pid="p-1", first="Anna", last="Muster", titel="Geschäftsführerin",
           seniority="Founder/Owner"):
    return {"person": {
        "person_id": pid, "first_name": first, "last_name": last,
        "full_name": f"{first} {last}".strip(), "current_job_title": titel,
        "current_job_key": "j-1",
        "job_history": [{"title": titel, "current": True, "job_key": "j-1",
                         "seniority": seniority}],
        "email": {"status": "VERIFIED", "revealed": False},
    }, "company": {"name": "Firma GmbH"}}


def such_antwort(*personen):
    return FakeResponse(200, {"error": False, "free": False,
                              "results": list(personen),
                              "pagination": {"current_page": 1, "per_page": 25,
                                             "total_page": 1, "total_count": len(personen)}})


def anreicherung_antwort(email="anna.muster@firma.de", status="VERIFIED",
                         methode="SMTP", schon_bezahlt=False):
    return FakeResponse(200, {"error": False, "free_enrichment": schon_bezahlt,
                              "person": {"person_id": "p-1",
                                         "email": {"status": status, "revealed": True,
                                                   "email": email,
                                                   "verification_method": methode}}})


def kein_treffer_400():
    return FakeResponse(400, {"error": True, "error_code": "NO_MATCH"})


def test_suche_findet_personen_mit_domain_filter():
    session = FakeSession([such_antwort(person())])
    treffer = ProspeoSource("key", session=session).entscheider_finden("firma.de")
    assert len(treffer) == 1
    t = treffer[0]
    assert t["person_id"] == "p-1"
    assert t["first_name"] == "Anna" and t["last_name"] == "Muster"
    assert t["title"] == "Geschäftsführerin"
    assert t["seniority"] == "Founder/Owner"
    # Aufruf-Form laut Doku: Domain-Vorfilter, X-KEY-Header, JSON.
    assert session.urls == [SUCH_URL]
    assert session.bodies[0]["filters"]["company"]["websites"]["include"] == ["firma.de"]
    assert session.headers[0]["X-KEY"] == "key"
    assert session.headers[0]["Content-Type"] == "application/json"


def test_suche_ohne_domain_macht_keinen_aufruf():
    session = FakeSession([])
    assert ProspeoSource("key", session=session).entscheider_finden("") == []
    assert session.urls == []


def test_suche_ueberspringt_personen_ohne_namen():
    ohne_name = person(pid="p-2", first="", last="")
    session = FakeSession([such_antwort(ohne_name, person())])
    treffer = ProspeoSource("key", session=session).entscheider_finden("firma.de")
    assert len(treffer) == 1 and treffer[0]["person_id"] == "p-1"


def test_suche_kein_treffer_400_no_match_gibt_leere_liste():
    # Prospeo meldet "kein Treffer" als HTTP 400 + NO_MATCH - das ist KEIN
    # technischer Fehler und darf nicht laut scheitern.
    session = FakeSession([kein_treffer_400()])
    assert ProspeoSource("key", session=session).entscheider_finden("firma.de") == []


def test_anreicherung_liefert_gepruefte_mail():
    session = FakeSession([anreicherung_antwort()])
    ergebnis = ProspeoSource("key", session=session).email_anreichern("p-1")
    assert ergebnis == {"email": "anna.muster@firma.de", "status": "VERIFIED",
                        "verification_method": "SMTP", "schon_bezahlt": False}
    assert session.urls == [ANREICHERN_URL]
    # Nur geprüfte Adressen anfordern (Zuverlässigkeit zuerst) und über die
    # person_id aus der Suche anreichern.
    assert session.bodies[0]["only_verified_email"] is True
    assert session.bodies[0]["data"] == {"person_id": "p-1"}


def test_anreicherung_no_match_gibt_none():
    # NO_MATCH heißt hier auch: Person hat keine GEPRÜFTE Mail -> kein Credit,
    # kein Fehler, einfach keine brauchbare Adresse.
    session = FakeSession([kein_treffer_400()])
    assert ProspeoSource("key", session=session).email_anreichern("p-1") is None


def test_anreicherung_ohne_person_id_macht_keinen_aufruf():
    session = FakeSession([])
    assert ProspeoSource("key", session=session).email_anreichern("") is None
    assert session.urls == []


def test_wiederholt_bei_429_dann_erfolg():
    session = FakeSession([FakeResponse(429, {"error": True}), such_antwort(person())])
    treffer = ProspeoSource("key", session=session, wartezeit=0).entscheider_finden("firma.de")
    assert len(treffer) == 1 and len(session.urls) == 2


def test_echter_4xx_fehler_scheitert_laut():
    session = FakeSession([FakeResponse(401, {"error": True, "error_code": "INVALID_API_KEY"},
                                        text="unauthorized")])
    with pytest.raises(RuntimeError) as fehler:
        ProspeoSource("key", session=session, wartezeit=0).entscheider_finden("firma.de")
    assert "401" in str(fehler.value)


def test_error_true_im_200_scheitert_laut():
    # Laut Doku steckt der Fehlerzustand primär im JSON ("error": true) -
    # ein unerwarteter Fehlercode muss laut scheitern, nicht still leer wirken.
    session = FakeSession([FakeResponse(200, {"error": True, "error_code": "INVALID_FILTERS"})])
    with pytest.raises(RuntimeError) as fehler:
        ProspeoSource("key", session=session).entscheider_finden("firma.de")
    assert "INVALID_FILTERS" in str(fehler.value)


def test_dauerhaft_500_scheitert_nach_versuchen():
    session = FakeSession([FakeResponse(500, {}), FakeResponse(500, {}), FakeResponse(500, {})])
    with pytest.raises(RuntimeError):
        ProspeoSource("key", session=session, wartezeit=0,
                      max_versuche=3).entscheider_finden("firma.de")
    assert len(session.urls) == 3
