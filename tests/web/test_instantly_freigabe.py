import pytest

from web.instantly_freigabe import freigabe_anzeige, hole_alle_seiten


def test_hole_alle_seiten_folgt_cursor_und_entfernt_doppelte_ids():
    antworten = iter([
        {"items": [{"id": "a"}, {"id": "b"}], "next_starting_after": "seite-2"},
        {"items": [{"id": "b"}, {"id": "c"}], "next_starting_after": None},
    ])
    aufrufe = []

    items = hole_alle_seiten(lambda cursor: aufrufe.append(cursor) or next(antworten))

    assert [i["id"] for i in items] == ["a", "b", "c"]
    assert aufrufe == [None, "seite-2"]


def test_hole_alle_seiten_lehnt_wiederholten_cursor_ab():
    def abruf(cursor):
        return {"items": [{"id": str(cursor)}], "next_starting_after": "gleich"}

    with pytest.raises(RuntimeError, match="Seitenzeiger wiederholt"):
        hole_alle_seiten(abruf)


def test_hole_alle_seiten_hat_feste_obergrenze():
    with pytest.raises(RuntimeError, match="Seitenobergrenze"):
        hole_alle_seiten(
            lambda cursor: {"items": [], "next_starting_after": str(cursor) + "x"},
            max_seiten=2,
        )


def test_antwort_gehoert_nur_bei_einem_einzigen_ausgang_im_thread_zum_schritt():
    leads = [{
        "id": "lead-1", "email": "anna@firma.de", "status": 1,
        "email_reply_count": 1,
    }]
    emails = [
        {"id": "out-1", "lead": "anna@firma.de", "lead_id": "lead-1",
         "thread_id": "thread-1", "ue_type": 1, "step": 1,
         "timestamp_email": "2026-07-22T08:00:00Z"},
        {"id": "in-1", "lead": "anna@firma.de", "lead_id": "lead-1",
         "thread_id": "thread-1", "ue_type": 2,
         "timestamp_email": "2026-07-22T09:00:00Z"},
    ]

    stand = freigabe_anzeige(leads, emails)["anna@firma.de"]

    assert stand["steps"]["mail_1"] == {
        "sent_at": "2026-07-22T08:00:00Z", "replied": True,
    }
    assert stand["overall"]["replied"] is True


def test_live_schrittbezeichner_ordnen_erste_mail_und_antwort_richtig_zu():
    leads = [{"id": "lead-1", "email": "anna@firma.de", "status": 1}]
    emails = [
        {"id": "out-1", "lead": "anna@firma.de", "lead_id": "lead-1",
         "thread_id": "thread-1", "ue_type": 1, "step": "0_0_0",
         "timestamp_email": "2026-07-23T08:09:01Z"},
        {"id": "in-1", "lead": "anna@firma.de",
         "thread_id": "thread-1", "ue_type": 2, "step": "0_0_0",
         "timestamp_email": "2026-07-23T08:10:41Z"},
        {"id": "out-2", "lead": "anna@firma.de",
         "thread_id": "thread-2", "ue_type": 1, "step": "0_1_0",
         "timestamp_email": "2026-07-24T08:09:01Z"},
        {"id": "out-3", "lead": "anna@firma.de",
         "thread_id": "thread-3", "ue_type": 1, "step": "0_2_0",
         "timestamp_email": "2026-07-25T08:09:01Z"},
    ]

    stand = freigabe_anzeige(leads, emails)["anna@firma.de"]

    assert stand["steps"]["mail_1"] == {
        "sent_at": "2026-07-23T08:09:01Z", "replied": True,
    }
    assert stand["steps"]["follow_up_1"]["sent_at"] == "2026-07-24T08:09:01Z"
    assert stand["steps"]["follow_up_2"]["sent_at"] == "2026-07-25T08:09:01Z"


def test_mehrere_ausgaenge_im_thread_lassen_schrittantwort_unbekannt():
    leads = [{"id": "lead-1", "email": "anna@firma.de", "status": 1}]
    emails = [
        {"id": "out-1", "lead_id": "lead-1", "thread_id": "thread-1",
         "ue_type": 1, "step": 1, "timestamp_email": "2026-07-20T08:00:00Z"},
        {"id": "out-2", "lead_id": "lead-1", "thread_id": "thread-1",
         "ue_type": 1, "step": 2, "timestamp_email": "2026-07-21T08:00:00Z"},
        {"id": "in-1", "lead_id": "lead-1", "thread_id": "thread-1",
         "ue_type": 2, "timestamp_email": "2026-07-22T09:00:00Z"},
    ]

    stand = freigabe_anzeige(leads, emails)["anna@firma.de"]

    assert stand["steps"]["mail_1"]["replied"] is None
    assert stand["steps"]["follow_up_1"]["replied"] is None
    assert stand["overall"]["replied"] is True


@pytest.mark.parametrize("status, erwartet", [
    (-1, "bounced"),
    (-2, "unsubscribed"),
    (-3, "skipped"),
])
def test_lead_fehler_bleibt_auf_empfaengerebene(status, erwartet):
    stand = freigabe_anzeige(
        [{"id": "lead-1", "email": "anna@firma.de", "status": status}], []
    )["anna@firma.de"]

    assert stand["overall"]["status"] == erwartet
    assert all(s["sent_at"] is None for s in stand["steps"].values())


def test_ungueltiger_zeitstempel_wird_nicht_angezeigt():
    stand = freigabe_anzeige(
        [{"id": "lead-1", "email": "anna@firma.de", "status": 1}],
        [{"id": "out-1", "lead_id": "lead-1", "ue_type": 1, "step": 1,
          "timestamp_email": "kein-datum"}],
    )["anna@firma.de"]

    assert stand["steps"]["mail_1"]["sent_at"] is None
