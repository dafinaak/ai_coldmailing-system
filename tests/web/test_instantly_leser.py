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


# Postfach (Task 9): emails_stand() / konversationen() -----------------------

def _email(campaign_id="camp-1", ue_type=1, to="anna@firma.de", frm=None,
           betreff="Betreff", zeit="2026-07-20T09:00:00.000Z", text="Text der Mail",
           preview=None):
    """Baut eine rohe Email wie die API sie liefert (siehe Modul-Docstring
    von web.instantly_leser fuer die Schema-Quelle) - nur die Felder, die
    konversationen()/emails_stand() tatsaechlich auswerten."""
    return {
        "id": "mail-1", "campaign_id": campaign_id, "ue_type": ue_type,
        "to_address_email_list": to, "from_address_email": frm,
        "subject": betreff, "timestamp_email": zeit, "timestamp_created": zeit,
        "body": {"text": text} if text is not None else {},
        "content_preview": preview, "eaccount": "wir@digitaldiamonds.de",
    }


def test_konversationen_gruppiert_nach_kontakt_und_sortiert_chronologisch():
    session = FakeSession({
        "/emails": FakeResponse(200, {"items": [
            _email(ue_type=1, to="anna@firma.de", betreff="Anschreiben",
                   zeit="2026-07-20T09:00:00.000Z", text="Erstes Anschreiben"),
            _email(ue_type=2, frm="anna@firma.de", betreff="Re: Anschreiben",
                   zeit="2026-07-21T10:00:00.000Z", text="Interessant, mehr dazu?"),
            _email(ue_type=1, to="bob@firma.de", betreff="Anschreiben Bob",
                   zeit="2026-07-19T08:00:00.000Z", text="Anschreiben an Bob"),
        ]}),
    })
    leser = InstantlyLeser("key", session=session)
    konversationen = leser.konversationen(["camp-1"])

    # neueste Konversation zuerst (Annas Antwort vom 21.07. ist die juengste
    # Nachricht ueberhaupt) - Bobs Konversation (19.07.) kommt danach.
    assert [k["kontakt_email"] for k in konversationen] == ["anna@firma.de", "bob@firma.de"]

    anna = konversationen[0]
    assert len(anna["nachrichten"]) == 2
    # chronologisch: das Anschreiben (20.07.) vor der Antwort (21.07.).
    assert [m["richtung"] for m in anna["nachrichten"]] == ["gesendet", "empfangen"]
    assert anna["richtung_letzte"] == "empfangen"
    assert anna["betreff"] == "Re: Anschreiben"  # Betreff der juengsten Nachricht


def test_konversationen_ue_type_2_ist_empfangen_1_und_3_sind_gesendet():
    session = FakeSession({
        "/emails": FakeResponse(200, {"items": [
            _email(ue_type=1, to="anna@firma.de", zeit="2026-07-20T09:00:00.000Z"),
            _email(ue_type=3, to="anna@firma.de", zeit="2026-07-20T09:05:00.000Z"),
            _email(ue_type=2, frm="anna@firma.de", zeit="2026-07-20T09:10:00.000Z"),
        ]}),
    })
    leser = InstantlyLeser("key", session=session)
    konversationen = leser.konversationen(["camp-1"])
    richtungen = [m["richtung"] for m in konversationen[0]["nachrichten"]]
    assert richtungen == ["gesendet", "gesendet", "empfangen"]


def test_konversationen_blendet_geplante_scheduled_mails_aus():
    session = FakeSession({
        "/emails": FakeResponse(200, {"items": [
            _email(ue_type=1, to="anna@firma.de", zeit="2026-07-20T09:00:00.000Z"),
            _email(ue_type=4, to="anna@firma.de", zeit="2026-07-25T09:00:00.000Z"),
        ]}),
    })
    leser = InstantlyLeser("key", session=session)
    konversationen = leser.konversationen(["camp-1"])
    assert len(konversationen[0]["nachrichten"]) == 1


def test_konversationen_nutzt_body_text_und_faellt_auf_content_preview_zurueck():
    session = FakeSession({
        "/emails": FakeResponse(200, {"items": [
            _email(ue_type=1, to="anna@firma.de", text="Volltext da"),
            _email(ue_type=2, frm="anna@firma.de", zeit="2026-07-20T10:00:00.000Z",
                   text=None, preview="Nur eine Vorschau"),
        ]}),
    })
    leser = InstantlyLeser("key", session=session)
    nachrichten = leser.konversationen(["camp-1"])[0]["nachrichten"]
    assert nachrichten[0]["text"] == "Volltext da"
    assert nachrichten[1]["text"] == "Nur eine Vorschau"


def test_konversationen_ueber_mehrere_kampagnen_gruppiert_denselben_kontakt():
    session = FakeSession({
        "/emails": [
            FakeResponse(200, {"items": [
                _email(campaign_id="camp-1", ue_type=1, to="anna@firma.de",
                       zeit="2026-07-10T09:00:00.000Z", betreff="Welle 1"),
            ]}),
            FakeResponse(200, {"items": [
                _email(campaign_id="camp-2", ue_type=1, to="anna@firma.de",
                       zeit="2026-07-20T09:00:00.000Z", betreff="Welle 2"),
            ]}),
        ],
    })
    leser = InstantlyLeser("key", session=session)
    konversationen = leser.konversationen(["camp-1", "camp-2"])
    assert len(konversationen) == 1
    assert len(konversationen[0]["nachrichten"]) == 2


def test_emails_stand_uebergibt_limit_und_campaign_id_als_parameter():
    session = FakeSession({"/emails": FakeResponse(200, {"items": []})})
    leser = InstantlyLeser("key", session=session)
    leser.emails_stand(["camp-1"])
    pfad, params = session.aufrufe[0]
    assert pfad == "/emails"
    assert params == {"campaign_id": "camp-1", "limit": 100}


def test_emails_stand_cache_60_sekunden():
    uhr = {"jetzt": datetime(2026, 7, 20, 10, 0, 0)}
    session = FakeSession({"/emails": FakeResponse(200, {"items": [_email()]})})
    leser = InstantlyLeser("key", session=session, jetzt=lambda: uhr["jetzt"])

    leser.emails_stand(["camp-1"])
    assert len(session.aufrufe) == 1

    uhr["jetzt"] += timedelta(seconds=59)
    stand = leser.emails_stand(["camp-1"])
    assert len(session.aufrufe) == 1  # kein neuer Aufruf
    assert stand["camp-1"]["erreichbar"] is True

    uhr["jetzt"] += timedelta(seconds=2)  # insgesamt 61s
    leser.emails_stand(["camp-1"])
    assert len(session.aufrufe) == 2  # neu abgefragt


def test_emails_stand_api_fehler_ohne_cache_liefert_marker_statt_absturz():
    session = FakeSession({"/emails": FakeResponse(500, {})})
    leser = InstantlyLeser("key", session=session)
    stand = leser.emails_stand(["camp-1"])
    eintrag = stand["camp-1"]
    assert eintrag["erreichbar"] is False
    assert eintrag["items"] == []
    assert eintrag["stand"] is None


def test_emails_stand_ausfall_nach_erfolg_behaelt_letzten_bekannten_stand():
    uhr = {"jetzt": datetime(2026, 7, 20, 9, 0, 0)}
    session = FakeSession({"/emails": FakeResponse(200, {"items": [_email()]})})
    leser = InstantlyLeser("key", session=session, jetzt=lambda: uhr["jetzt"])
    erster = leser.emails_stand(["camp-1"])
    assert erster["camp-1"]["erreichbar"] is True
    assert len(erster["camp-1"]["items"]) == 1

    uhr["jetzt"] += timedelta(seconds=61)
    session.antworten["/emails"] = [FakeResponse(500, {})]
    zweiter = leser.emails_stand(["camp-1"])
    eintrag = zweiter["camp-1"]
    assert eintrag["erreichbar"] is False
    assert len(eintrag["items"]) == 1  # letzter bekannter Stand bleibt sichtbar
    assert eintrag["stand"] == datetime(2026, 7, 20, 9, 0, 0)


def test_konversationen_leere_kampagnenliste_ergibt_leere_liste_ohne_aufruf():
    session = FakeSession({})
    leser = InstantlyLeser("key", session=session)
    assert leser.konversationen([]) == []
    assert session.aufrufe == []


# Postfaecher (Baustein 2): postfaecher() ------------------------------------
#
# Feldnamen live gegen GET /api/v2/accounts geprueft (siehe
# docs/instantly-api-machbarkeit.md Punkt 4 und web.instantly_leser
# Modul-Docstring) - "email", "status", "warmup_status", "daily_limit".

def _account(email="team@firma.de", status=1, warmup_status=1, daily_limit=100):
    account = {"email": email, "status": status, "warmup_status": warmup_status}
    if daily_limit is not None:
        account["daily_limit"] = daily_limit
    return account


def test_postfaecher_parst_verbunden_und_verbindungsfehler():
    session = FakeSession({
        "/accounts": FakeResponse(200, {"items": [
            _account(email="gesund@firma.de", status=1, warmup_status=1, daily_limit=100),
            _account(email="kaputt@firma.de", status=-1, warmup_status=0, daily_limit=None),
        ]}),
    })
    leser = InstantlyLeser("key", session=session)
    stand = leser.postfaecher()
    assert stand["erreichbar"] is True
    assert stand["stand"] is not None
    postfaecher = {p["email"]: p for p in stand["postfaecher"]}
    assert postfaecher["gesund@firma.de"]["status"] == "verbunden"
    assert postfaecher["gesund@firma.de"]["warmup"] == "an"
    assert postfaecher["gesund@firma.de"]["daily_limit"] == 100
    assert postfaecher["kaputt@firma.de"]["status"] == "verbindungsfehler"
    assert postfaecher["kaputt@firma.de"]["warmup"] == "aus"
    assert postfaecher["kaputt@firma.de"]["daily_limit"] is None


@pytest.mark.parametrize("status_zahl,erwartet", [
    (1, "verbunden"), (2, "pausiert"), (3, "pausiert"),
    (-1, "verbindungsfehler"), (-2, "verbindungsfehler"), (-3, "verbindungsfehler"),
])
def test_postfach_status_zahlen_werden_korrekt_uebersetzt(status_zahl, erwartet):
    session = FakeSession({
        "/accounts": FakeResponse(200, {"items": [_account(status=status_zahl)]}),
    })
    leser = InstantlyLeser("key", session=session)
    stand = leser.postfaecher()
    assert stand["postfaecher"][0]["status"] == erwartet


@pytest.mark.parametrize("warmup_zahl,erwartet", [
    (1, "an"), (0, "aus"),
    (-1, "gesperrt"), (-2, "problem"), (-3, "gesperrt"),
])
def test_postfach_warmup_zahlen_werden_korrekt_uebersetzt(warmup_zahl, erwartet):
    session = FakeSession({
        "/accounts": FakeResponse(200, {"items": [_account(warmup_status=warmup_zahl)]}),
    })
    leser = InstantlyLeser("key", session=session)
    stand = leser.postfaecher()
    assert stand["postfaecher"][0]["warmup"] == erwartet


def test_postfaecher_unbekannter_status_wird_nicht_erraten():
    session = FakeSession({
        "/accounts": FakeResponse(200, {"items": [_account(status=99, warmup_status=99)]}),
    })
    leser = InstantlyLeser("key", session=session)
    stand = leser.postfaecher()
    assert stand["postfaecher"][0]["status"] == "unbekannt"
    assert stand["postfaecher"][0]["warmup"] == "unbekannt"


def test_postfaecher_cache_wird_innerhalb_60_sekunden_nicht_erneut_abgefragt():
    uhr = {"jetzt": datetime(2026, 7, 20, 10, 0, 0)}
    session = FakeSession({"/accounts": FakeResponse(200, {"items": [_account()]})})
    leser = InstantlyLeser("key", session=session, jetzt=lambda: uhr["jetzt"])

    leser.postfaecher()
    assert len(session.aufrufe) == 1

    uhr["jetzt"] += timedelta(seconds=59)
    stand = leser.postfaecher()
    assert len(session.aufrufe) == 1  # kein neuer Aufruf
    assert stand["erreichbar"] is True


def test_postfaecher_cache_wird_nach_60_sekunden_neu_abgefragt():
    uhr = {"jetzt": datetime(2026, 7, 20, 10, 0, 0)}
    session = FakeSession({"/accounts": FakeResponse(200, {"items": [_account()]})})
    leser = InstantlyLeser("key", session=session, jetzt=lambda: uhr["jetzt"])

    leser.postfaecher()
    uhr["jetzt"] += timedelta(seconds=61)
    leser.postfaecher()
    assert len(session.aufrufe) == 2


def test_postfaecher_api_fehler_ohne_vorherigen_cache_liefert_marker_statt_absturz():
    session = FakeSession({"/accounts": FakeResponse(500, {})})
    leser = InstantlyLeser("key", session=session)
    stand = leser.postfaecher()
    assert stand["erreichbar"] is False
    assert stand["postfaecher"] == []
    assert stand["stand"] is None


def test_postfaecher_timeout_liefert_marker_statt_absturz():
    import requests

    class KaputteSession:
        def get(self, *a, **k):
            raise requests.exceptions.Timeout("zu langsam")

    leser = InstantlyLeser("key", session=KaputteSession())
    stand = leser.postfaecher()
    assert stand["erreichbar"] is False
    assert stand["postfaecher"] == []


def test_postfaecher_ausfall_nach_erfolg_behaelt_letzten_bekannten_stand():
    uhr = {"jetzt": datetime(2026, 7, 20, 9, 0, 0)}
    session = FakeSession({
        "/accounts": FakeResponse(200, {"items": [_account(email="gesund@firma.de")]}),
    })
    leser = InstantlyLeser("key", session=session, jetzt=lambda: uhr["jetzt"])
    erster = leser.postfaecher()
    assert erster["erreichbar"] is True
    assert len(erster["postfaecher"]) == 1

    uhr["jetzt"] += timedelta(seconds=61)
    session.antworten["/accounts"] = [FakeResponse(500, {})]
    zweiter = leser.postfaecher()
    assert zweiter["erreichbar"] is False
    assert len(zweiter["postfaecher"]) == 1  # letzter bekannter Stand bleibt sichtbar
    assert zweiter["stand"] == datetime(2026, 7, 20, 9, 0, 0)


def test_postfaecher_uebergibt_limit_als_parameter():
    session = FakeSession({"/accounts": FakeResponse(200, {"items": []})})
    leser = InstantlyLeser("key", session=session)
    leser.postfaecher()
    pfad, params = session.aufrufe[0]
    assert pfad == "/accounts"
    assert params == {"limit": 100}
