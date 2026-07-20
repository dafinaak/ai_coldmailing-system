"""Tests fuer web.instantly_leser.InstantlyLeser (Task 6): liest den
Live-Stand von Kampagnen aus Instantly (nur GET). Kein echter HTTP-Aufruf -
eine Fake-Session antwortet je nach Pfad, exakt wie FakeSession/FakeResponse
in tests/test_apollo.py fuer den Schreib-Pfad (dort nur .post, hier .get)."""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from web.instantly_leser import InstantlyLeser


class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code, self._payload = status_code, payload

    def json(self):
        return self._payload


class FakeSession:
    """`antworten` bildet einen Pfad-Suffix (z.B. "/campaigns/camp-1") auf
    eine FakeResponse ODER eine Liste von FakeResponses ab (die Liste wird
    der Reihe nach abgearbeitet - fuer Tests, die denselben Pfad mehrfach
    mit unterschiedlichen Antworten treffen, z.B. "erst Fehler, dann ok").
    Pfade ohne Query-Parameter im Schluessel, `aufrufe` zeichnet
    (pfad, params) fuer Assertions auf."""

    def __init__(self, antworten: dict):
        self.antworten = {k: (v if isinstance(v, list) else [v]) for k, v in antworten.items()}
        self.aufrufe = []

    def get(self, url, headers=None, params=None, timeout=None):
        pfad = url.split("/api/v2", 1)[1]
        self.aufrufe.append((pfad, params))
        warteschlange = self.antworten.get(pfad)
        if not warteschlange:
            raise AssertionError(f"Kein Fake fuer Pfad {pfad} hinterlegt.")
        return warteschlange.pop(0) if len(warteschlange) > 1 else warteschlange[0]


def _standard_antworten(campaign_id="camp-1", status=0, name="[TEST] Demo GmbH",
                         emails_sent_count=5):
    return {
        f"/campaigns/{campaign_id}": FakeResponse(200, {"id": campaign_id, "name": name,
                                                         "status": status}),
        "/campaigns/analytics": FakeResponse(200, [{"campaign_id": campaign_id,
                                                     "emails_sent_count": emails_sent_count}]),
        "/campaigns/analytics/steps": FakeResponse(200, [
            {"step": "1", "variant": "A", "sent": 5},
            {"step": "2", "variant": "A", "sent": 2},
        ]),
    }


# Parsen gefakter Antworten ---------------------------------------------

def test_kampagnen_stand_parst_status_name_versendet_und_schritte():
    session = FakeSession(_standard_antworten())
    leser = InstantlyLeser("key", session=session)
    stand = leser.kampagnen_stand(["camp-1"])
    eintrag = stand["camp-1"]
    assert eintrag["erreichbar"] is True
    assert eintrag["status"] == "pausiert"  # status=0 (Draft)
    assert eintrag["name"] == "[TEST] Demo GmbH"
    assert eintrag["versendet"] == 5
    assert eintrag["schritte"] == [{"schritt": 1, "versendet": 5}, {"schritt": 2, "versendet": 2}]
    assert eintrag["stand"] is not None


@pytest.mark.parametrize("status_zahl,erwartet", [
    (0, "pausiert"), (1, "aktiv"), (2, "pausiert"), (3, "abgeschlossen"),
    (4, "aktiv"),
    # Konto-Stoerungen (Account Suspended/Unhealthy/Bounce Protect) sind KEIN
    # normales "pausiert" (das waere absichtlich und harmlos) - sie brauchen
    # einen eigenen, lauten Zustand, damit sie in der Oberflaeche nicht still
    # als "ganz normal pausiert" untergehen (Review-Fund).
    (-99, "kontoproblem"), (-1, "kontoproblem"), (-2, "kontoproblem"),
])
def test_status_zahlen_werden_korrekt_uebersetzt(status_zahl, erwartet):
    session = FakeSession(_standard_antworten(status=status_zahl))
    leser = InstantlyLeser("key", session=session)
    stand = leser.kampagnen_stand(["camp-1"])
    assert stand["camp-1"]["status"] == erwartet


def test_kampagnen_stand_ohne_schritt_daten_liefert_leere_liste_statt_absturz():
    antworten = _standard_antworten()
    antworten["/campaigns/analytics/steps"] = FakeResponse(200, [])
    session = FakeSession(antworten)
    leser = InstantlyLeser("key", session=session)
    stand = leser.kampagnen_stand(["camp-1"])
    assert stand["camp-1"]["schritte"] == []
    assert stand["camp-1"]["erreichbar"] is True


def test_mehrere_kampagnen_ids_werden_einzeln_aufgeloest():
    antworten = {**_standard_antworten("camp-1", name="Kampagne 1"),
                 **_standard_antworten("camp-2", name="Kampagne 2")}
    session = FakeSession(antworten)
    leser = InstantlyLeser("key", session=session)
    stand = leser.kampagnen_stand(["camp-1", "camp-2"])
    assert stand["camp-1"]["name"] == "Kampagne 1"
    assert stand["camp-2"]["name"] == "Kampagne 2"


# Cache -------------------------------------------------------------------

def test_cache_wird_innerhalb_60_sekunden_nicht_erneut_abgefragt():
    uhr = {"jetzt": datetime(2026, 7, 20, 10, 0, 0)}
    session = FakeSession(_standard_antworten())
    leser = InstantlyLeser("key", session=session, jetzt=lambda: uhr["jetzt"])

    leser.kampagnen_stand(["camp-1"])
    erster_aufruf_anzahl = len(session.aufrufe)
    assert erster_aufruf_anzahl == 3  # campaign + analytics + steps

    uhr["jetzt"] += timedelta(seconds=59)
    stand = leser.kampagnen_stand(["camp-1"])
    assert len(session.aufrufe) == erster_aufruf_anzahl  # kein neuer Aufruf
    assert stand["camp-1"]["erreichbar"] is True


def test_cache_wird_nach_60_sekunden_neu_abgefragt():
    uhr = {"jetzt": datetime(2026, 7, 20, 10, 0, 0)}
    session = FakeSession(_standard_antworten())
    leser = InstantlyLeser("key", session=session, jetzt=lambda: uhr["jetzt"])

    leser.kampagnen_stand(["camp-1"])
    erster_aufruf_anzahl = len(session.aufrufe)

    uhr["jetzt"] += timedelta(seconds=61)
    leser.kampagnen_stand(["camp-1"])
    assert len(session.aufrufe) == erster_aufruf_anzahl * 2  # neu abgefragt


def test_stand_zeitpunkt_kommt_von_der_injizierten_uhr():
    fester_zeitpunkt = datetime(2026, 7, 20, 9, 17, 0)
    session = FakeSession(_standard_antworten())
    leser = InstantlyLeser("key", session=session, jetzt=lambda: fester_zeitpunkt)
    stand = leser.kampagnen_stand(["camp-1"])
    assert stand["camp-1"]["stand"] == fester_zeitpunkt


# Fehlertoleranz ------------------------------------------------------------

def test_api_500_liefert_marker_statt_absturz_ohne_vorherigen_cache():
    session = FakeSession({"/campaigns/camp-1": FakeResponse(500, {})})
    leser = InstantlyLeser("key", session=session)
    stand = leser.kampagnen_stand(["camp-1"])
    eintrag = stand["camp-1"]
    assert eintrag["erreichbar"] is False
    assert eintrag["stand"] is None
    assert eintrag["versendet"] is None
    assert eintrag["schritte"] == []


def test_timeout_liefert_marker_statt_absturz():
    import requests

    class KaputteSession:
        def get(self, *a, **k):
            raise requests.exceptions.Timeout("zu langsam")

    leser = InstantlyLeser("key", session=KaputteSession())
    stand = leser.kampagnen_stand(["camp-1"])
    assert stand["camp-1"]["erreichbar"] is False


def test_ausfall_nach_erfolgreichem_abruf_behaelt_letzten_bekannten_stand():
    uhr = {"jetzt": datetime(2026, 7, 20, 9, 0, 0)}
    antworten = _standard_antworten()
    session = FakeSession(antworten)
    leser = InstantlyLeser("key", session=session, jetzt=lambda: uhr["jetzt"])
    erster_stand = leser.kampagnen_stand(["camp-1"])
    assert erster_stand["camp-1"]["erreichbar"] is True
    assert erster_stand["camp-1"]["versendet"] == 5

    # Cache ablaufen lassen, dann faellt die API aus (500 auf allen Pfaden).
    uhr["jetzt"] += timedelta(seconds=61)
    for pfad in list(session.antworten):
        session.antworten[pfad] = [FakeResponse(500, {})]

    zweiter_stand = leser.kampagnen_stand(["camp-1"])
    eintrag = zweiter_stand["camp-1"]
    assert eintrag["erreichbar"] is False
    assert eintrag["versendet"] == 5  # letzter bekannter Stand bleibt sichtbar
    assert eintrag["stand"] == datetime(2026, 7, 20, 9, 0, 0)  # Zeitpunkt des letzten Erfolgs
