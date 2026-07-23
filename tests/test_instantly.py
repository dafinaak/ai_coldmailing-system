import pytest
from pipeline.senders.instantly import InstantlySender
from tests.test_apollo import FakeSession, FakeResponse
from tests.test_personalize import KUNDE

TEXTE = [{"email": "t@example.com", "betreff": "B", "mail_1": "M",
          "follow_up_1": "F1", "follow_up_2": "F2"}]

def test_legt_pausierte_kampagne_an_und_importiert_leads():
    session = FakeSession([FakeResponse(200, {"id": "camp-1"}),
                           FakeResponse(200, {})])
    sender = InstantlySender("key", session=session)
    campaign_id = sender.create_campaign(KUNDE)
    assert campaign_id == "camp-1"
    sender.import_leads(campaign_id, TEXTE)
    kampagne, leads = session.aufrufe
    # Kein "status"-Feld beim Anlegen (siehe instantly.py) - Kampagne bleibt
    # automatisch im Zustand "Draft", der Text "aktiv" darf im Payload nicht
    # vorkommen.
    assert "aktiv" not in str(kampagne).lower() and "{{mail_1}}" in str(kampagne)
    # Schutz-Voreinstellungen laut Live-Doku vorhanden.
    assert kampagne["daily_limit"] == 20
    schedule = kampagne["campaign_schedule"]["schedules"][0]
    assert schedule["timing"] == {"from": "08:00", "to": "19:00"}
    assert schedule["days"] == {"0": False, "1": True, "2": True, "3": True,
                                 "4": True, "5": True, "6": False}
    # Instantly zaehlt "delay" ab dem Schritt, auf dem er steht, bis zum
    # naechsten Schritt (live verifiziert am 2026-07-17, siehe instantly.py) -
    # bei KUNDE.follow_up_tage=[3, 7] muss Follow-up 1 also 3 Tage nach Mail 1
    # kommen (delay auf Schritt 0) und Follow-up 2 4 weitere Tage danach
    # (delay auf Schritt 1 = 7 - 3), macht in Summe Tag 7 wie in der Config.
    schritte = kampagne["sequences"][0]["steps"]
    assert [s["delay"] for s in schritte] == [3, 4, 0]
    assert leads["leads"][0]["email"] == "t@example.com"
    assert leads["leads"][0]["custom_variables"]["mail_1"] == "M"
    assert leads["campaign_id"] == "camp-1"

def test_verweigert_nicht_aufsteigende_follow_up_tage():
    from dataclasses import replace
    kunde = replace(KUNDE, follow_up_tage=[7, 3])
    sender = InstantlySender("key", session=FakeSession([]))
    with pytest.raises(ValueError, match="follow_up_tage"):
        sender.create_campaign(kunde)
    assert sender.session.aufrufe == []

def test_weigert_sich_ohne_texte():
    sender = InstantlySender("key", session=FakeSession([]))
    try:
        sender.import_leads("camp-1", [])
        assert False, "haette ValueError werfen muessen"
    except ValueError:
        pass
    # Kein Aufruf an Instantly, wenn keine Texte vorliegen.
    assert sender.session.aufrufe == []

def test_kampagnen_fehler_stoppt_den_lauf_laut():
    session = FakeSession([FakeResponse(500, {})])
    sender = InstantlySender("key", session=session)
    with pytest.raises(RuntimeError, match="500"):
        sender.create_campaign(KUNDE)
    # Kein zweiter Aufruf (Lead-Import) nach einem fehlgeschlagenen
    # Kampagnen-Anlegen.
    assert len(session.aufrufe) == 1

def test_lead_import_fehler_stoppt_den_lauf_laut():
    session = FakeSession([FakeResponse(200, {"id": "camp-1"}),
                           FakeResponse(422, {})])
    sender = InstantlySender("key", session=session)
    campaign_id = sender.create_campaign(KUNDE)
    with pytest.raises(RuntimeError, match="422"):
        sender.import_leads(campaign_id, TEXTE)

def test_fehlermeldung_enthaelt_ausschnitt_der_antwort():
    session = FakeSession([FakeResponse(
        500, {}, text="Interner Fehler: Datenbank nicht erreichbar")])
    sender = InstantlySender("key", session=session)
    with pytest.raises(RuntimeError, match="Datenbank nicht erreichbar"):
        sender.create_campaign(KUNDE)


# Baustein 1: Kampagne im Tool scharf schalten/pausieren ---------------------
# Eigene FakeSession (statt der geteilten aus tests.test_apollo), weil hier
# zusaetzlich die genaue URL geprueft wird (Endpunkte laut
# docs/instantly-api-machbarkeit.md #1: POST .../activate bzw. .../pause,
# kein Request-Body) - die geteilte FakeSession zeichnet nur den Payload auf.
class _FakeSessionMitURL:
    def __init__(self, antworten):
        self.antworten, self.aufrufe = list(antworten), []

    def post(self, url, json=None, headers=None, timeout=None):
        self.aufrufe.append((url, json))
        return self.antworten.pop(0)


class _FakeSessionRequestSpy:
    def __init__(self, antwort):
        self.antwort, self.aufrufe = antwort, []

    def post(self, url, **kwargs):
        self.aufrufe.append((url, kwargs))
        return self.antwort


def test_aktivieren_sendet_weder_json_body_noch_json_content_type():
    session = _FakeSessionRequestSpy(
        FakeResponse(200, {"id": "camp-1", "status": 1})
    )
    InstantlySender("key", session=session).aktiviere_kampagne("camp-1")

    _, kwargs = session.aufrufe[0]
    assert "json" not in kwargs
    assert kwargs["headers"] == {"Authorization": "Bearer key"}


def test_aktiviert_kampagne_ruft_activate_endpunkt_ohne_body_auf():
    session = _FakeSessionMitURL([FakeResponse(200, {"id": "camp-1", "status": 1})])
    sender = InstantlySender("key", session=session)
    ergebnis = sender.aktiviere_kampagne("camp-1")
    assert ergebnis is None
    url, payload = session.aufrufe[0]
    assert url == "https://api.instantly.ai/api/v2/campaigns/camp-1/activate"
    assert payload is None


def test_pausiert_kampagne_ruft_pause_endpunkt_ohne_body_auf():
    session = _FakeSessionMitURL([FakeResponse(200, {"id": "camp-1", "status": 2})])
    sender = InstantlySender("key", session=session)
    ergebnis = sender.pausiere_kampagne("camp-1")
    assert ergebnis is None
    url, payload = session.aufrufe[0]
    assert url == "https://api.instantly.ai/api/v2/campaigns/camp-1/pause"
    assert payload is None


def test_aktivieren_fehler_wirft_runtime_error():
    session = _FakeSessionMitURL([FakeResponse(500, {}, text="Server-Fehler")])
    sender = InstantlySender("key", session=session)
    with pytest.raises(RuntimeError, match="500"):
        sender.aktiviere_kampagne("camp-1")


def test_pausieren_fehler_wirft_runtime_error():
    session = _FakeSessionMitURL([FakeResponse(500, {}, text="Server-Fehler")])
    sender = InstantlySender("key", session=session)
    with pytest.raises(RuntimeError, match="500"):
        sender.pausiere_kampagne("camp-1")
