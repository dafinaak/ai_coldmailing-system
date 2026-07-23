import pytest
from pipeline.sources.hunter import HunterSource, DOMAIN_SUCH_URL, MIN_CONFIDENCE


class FakeResponse:
    def __init__(self, status_code, payload, text=""):
        self.status_code, self._payload, self.text = status_code, payload, text
    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, antworten):
        self.antworten, self.params, self.urls = list(antworten), [], []
    def get(self, url, params=None, headers=None, timeout=None):
        self.params.append(params)
        self.urls.append(url)
        return self.antworten.pop(0)


def person(first="Anna", last="Muster", position="Geschäftsführerin",
           value="anna@firma.de", confidence=90, decision_maker=True,
           status="valid", seniority="executive"):
    return {"value": value, "type": "personal", "confidence": confidence,
            "first_name": first, "last_name": last, "position": position,
            "seniority": seniority, "department": "management",
            "decision_maker": decision_maker,
            "verification": {"status": status}}


def domain_antwort(*personen):
    return FakeResponse(200, {"data": {"domain": "firma.de", "organization": "Firma GmbH",
                                       "emails": list(personen)},
                              "meta": {"results": len(personen)}})


def test_findet_entscheider_mit_name_und_titel():
    session = FakeSession([domain_antwort(person())])
    treffer = HunterSource("key", session=session).entscheider_finden("firma.de")
    assert len(treffer) == 1
    t = treffer[0]
    assert t["first_name"] == "Anna" and t["last_name"] == "Muster"
    assert t["title"] == "Geschäftsführerin" and t["email"] == "anna@firma.de"
    assert t["decision_maker"] is True and t["verification_status"] == "valid"
    # Domain und api_key muessen im Aufruf stecken, nur persoenliche Adressen:
    assert session.params[0]["domain"] == "firma.de"
    assert session.params[0]["api_key"] == "key"
    assert session.params[0]["type"] == "personal"


def test_entscheider_steht_vor_normalem_mitarbeiter():
    # Zwei Treffer: ein normaler Mitarbeiter (kein Entscheider) zuerst geliefert,
    # danach die Geschaeftsfuehrerin. Sortierung muss die Entscheiderin nach vorn holen.
    mitarbeiter = person(first="Tom", last="Klein", position="Support",
                         value="tom@firma.de", confidence=95,
                         decision_maker=False, seniority="junior")
    chefin = person(first="Anna", last="Muster", confidence=80)
    session = FakeSession([domain_antwort(mitarbeiter, chefin)])
    treffer = HunterSource("key", session=session).entscheider_finden("firma.de")
    assert [t["first_name"] for t in treffer] == ["Anna", "Tom"]


def test_ueberspringt_treffer_ohne_namen():
    ohne_name = person(first="", last="", value="kontakt@firma.de")
    session = FakeSession([domain_antwort(ohne_name, person())])
    treffer = HunterSource("key", session=session).entscheider_finden("firma.de")
    assert len(treffer) == 1 and treffer[0]["first_name"] == "Anna"


def test_ueberspringt_zu_unsichere_treffer():
    unsicher = person(first="Max", last="Vage", confidence=MIN_CONFIDENCE - 1)
    session = FakeSession([domain_antwort(unsicher)])
    treffer = HunterSource("key", session=session).entscheider_finden("firma.de")
    assert treffer == []


def test_leere_domain_macht_keinen_aufruf():
    session = FakeSession([])
    treffer = HunterSource("key", session=session).entscheider_finden("")
    assert treffer == [] and session.urls == []


def test_kein_treffer_gibt_leere_liste():
    session = FakeSession([domain_antwort()])
    treffer = HunterSource("key", session=session).entscheider_finden("firma.de")
    assert treffer == []


def test_wiederholt_bei_429_dann_erfolg():
    session = FakeSession([FakeResponse(429, {}), domain_antwort(person())])
    treffer = HunterSource("key", session=session, wartezeit=0).entscheider_finden("firma.de")
    assert len(treffer) == 1 and len(session.urls) == 2


def test_4xx_scheitert_laut():
    session = FakeSession([FakeResponse(401, {}, text="Unauthorized")])
    with pytest.raises(RuntimeError) as fehler:
        HunterSource("key", session=session, wartezeit=0).entscheider_finden("firma.de")
    assert "401" in str(fehler.value)


def test_dauerhaft_500_scheitert_nach_versuchen():
    session = FakeSession([FakeResponse(500, {}), FakeResponse(500, {}), FakeResponse(500, {})])
    with pytest.raises(RuntimeError):
        HunterSource("key", session=session, wartezeit=0, max_versuche=3).entscheider_finden("firma.de")
    assert len(session.urls) == 3


# --- Email Verifier (info@-Pruefung der Kaskade) ---------------------------

def pruef_antwort(status="valid", score=100):
    return FakeResponse(200, {"data": {"status": status, "score": score,
                                       "email": "info@firma.de"}})


def test_email_pruefen_liefert_status_und_score():
    session = FakeSession([pruef_antwort()])
    ergebnis = HunterSource("key", session=session).email_pruefen("info@firma.de")
    assert ergebnis == {"status": "valid", "score": 100}
    from pipeline.sources.hunter import PRUEF_URL
    assert session.urls == [PRUEF_URL]
    assert session.params[0] == {"email": "info@firma.de", "api_key": "key"}


def test_email_pruefen_wiederholt_bei_202_laeuft_noch():
    # 202 = "Pruefung laeuft noch, gleich nochmal fragen" (laut Hunter-Doku
    # zaehlt das nur als eine Anfrage).
    session = FakeSession([FakeResponse(202, {}), pruef_antwort("accept_all", 61)])
    ergebnis = HunterSource("key", session=session,
                            wartezeit=0).email_pruefen("info@firma.de")
    assert ergebnis == {"status": "accept_all", "score": 61}
    assert len(session.urls) == 2


def test_email_pruefen_222_smtp_problem_scheitert_nach_versuchen():
    session = FakeSession([FakeResponse(222, {}), FakeResponse(222, {})])
    with pytest.raises(RuntimeError, match="222"):
        HunterSource("key", session=session, wartezeit=0,
                     max_versuche=2).email_pruefen("info@firma.de")


def test_email_pruefen_4xx_scheitert_laut():
    session = FakeSession([FakeResponse(400, {}, text="invalid_email")])
    with pytest.raises(RuntimeError, match="400"):
        HunterSource("key", session=session, wartezeit=0).email_pruefen("info@firma.de")


def test_email_pruefen_ohne_email_macht_keinen_aufruf():
    session = FakeSession([])
    assert HunterSource("key", session=session).email_pruefen("") is None
    assert session.urls == []
