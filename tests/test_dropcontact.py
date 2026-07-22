import pytest
from pipeline.sources.dropcontact import DropcontactSource, ENRICH_URL


class FakeResponse:
    def __init__(self, status_code, payload, text=""):
        self.status_code, self._payload, self.text = status_code, payload, text
    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, antworten):
        self.antworten, self.posts, self.gets, self.urls = list(antworten), [], [], []
    def post(self, url, json=None, headers=None, timeout=None):
        self.posts.append({"url": url, "json": json, "headers": headers})
        self.urls.append(url)
        return self.antworten.pop(0)
    def get(self, url, params=None, headers=None, timeout=None):
        self.gets.append({"url": url, "headers": headers})
        self.urls.append(url)
        return self.antworten.pop(0)


def abgegeben(request_id="r1", credits=25):
    return FakeResponse(200, {"error": False, "request_id": request_id,
                              "success": True, "credits_left": credits})


def noch_nicht_fertig():
    return FakeResponse(200, {"error": False, "success": False,
                              "reason": "Request not ready yet, try again in 30 seconds"})


def fertig(*emails):
    return FakeResponse(200, {"error": False, "success": True,
                              "data": [{"first_name": "Anna", "last_name": "Muster",
                                        "email": list(emails)}]})


def email(wert="anna.muster@firma.de", qualification="nominative@pro"):
    return {"email": wert, "qualification": qualification}


def test_baut_gepruefte_persoenliche_mail():
    session = FakeSession([abgegeben(), fertig(email())])
    ergebnis = DropcontactSource("key", session=session).email_bauen(
        "Anna", "Muster", "https://firma.de", company="Firma GmbH")
    assert ergebnis == {"email": "anna.muster@firma.de", "qualification": "nominative@pro"}
    # Name + Webseite muessen im abgegebenen Batch stehen, Auth im Header:
    assert session.posts[0]["json"]["data"][0]["first_name"] == "Anna"
    assert session.posts[0]["json"]["data"][0]["website"] == "https://firma.de"
    assert session.posts[0]["headers"]["X-Access-Token"] == "key"


def test_pollt_bis_ergebnis_da_ist():
    session = FakeSession([abgegeben(), noch_nicht_fertig(), noch_nicht_fertig(),
                           fertig(email())])
    ergebnis = DropcontactSource("key", session=session, wartezeit=0).email_bauen(
        "Anna", "Muster", "https://firma.de")
    assert ergebnis["email"] == "anna.muster@firma.de"
    assert len(session.gets) == 3          # zweimal "nicht fertig", dann das Ergebnis


def test_generische_mail_gilt_nicht_als_treffer():
    # Dropcontact liefert nur eine generische Adresse - fuer uns keine
    # brauchbare persoenliche Mail, also None (faellt spaeter in die info@-Regel).
    session = FakeSession([abgegeben(), fertig(email("contact@firma.de", "generic@pro"))])
    ergebnis = DropcontactSource("key", session=session).email_bauen(
        "Anna", "Muster", "https://firma.de")
    assert ergebnis is None


def test_nimmt_die_persoenliche_vor_der_generischen():
    session = FakeSession([abgegeben(),
                           fertig(email("contact@firma.de", "generic@pro"),
                                  email("anna.muster@firma.de", "nominative@pro"))])
    ergebnis = DropcontactSource("key", session=session).email_bauen(
        "Anna", "Muster", "https://firma.de")
    assert ergebnis["email"] == "anna.muster@firma.de"


def test_kein_name_kein_aufruf():
    session = FakeSession([])
    ergebnis = DropcontactSource("key", session=session).email_bauen("", "", "https://firma.de")
    assert ergebnis is None and session.urls == []


def test_abgelehnter_batch_scheitert_laut():
    # z.B. aufgebrauchte Credits - muss laut scheitern, nicht still "keine Mail".
    session = FakeSession([FakeResponse(200, {"error": True, "reason": "no credits left"})])
    with pytest.raises(RuntimeError) as fehler:
        DropcontactSource("key", session=session).email_bauen("Anna", "Muster", "https://firma.de")
    assert "no credits" in str(fehler.value)


def test_http_fehler_beim_abgeben_scheitert():
    session = FakeSession([FakeResponse(401, {}, text="Unauthorized")])
    with pytest.raises(RuntimeError) as fehler:
        DropcontactSource("key", session=session).email_bauen("Anna", "Muster", "https://firma.de")
    assert "401" in str(fehler.value)


def test_nie_fertig_scheitert_nach_max_abfragen():
    session = FakeSession([abgegeben(), noch_nicht_fertig(), noch_nicht_fertig()])
    with pytest.raises(RuntimeError):
        DropcontactSource("key", session=session, wartezeit=0,
                          max_abfragen=2).email_bauen("Anna", "Muster", "https://firma.de")
    assert len(session.gets) == 2


def test_leeres_ergebnis_gibt_none():
    # success==true, aber data leer (Dropcontact fand nichts) -> keine Mail, kein Fehler.
    session = FakeSession([abgegeben(), FakeResponse(200, {"error": False, "success": True, "data": []})])
    ergebnis = DropcontactSource("key", session=session).email_bauen(
        "Anna", "Muster", "https://firma.de")
    assert ergebnis is None
