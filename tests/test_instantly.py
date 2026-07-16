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
    assert leads["leads"][0]["email"] == "t@example.com"
    assert leads["leads"][0]["custom_variables"]["mail_1"] == "M"
    assert leads["campaign_id"] == "camp-1"

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
