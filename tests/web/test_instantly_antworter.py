import pytest
import requests
from types import SimpleNamespace
import threading

from web.instantly_antworter import (
    geteilten_antworter,
    InstantlyAntwortAbgelehnt,
    InstantlyAntworter,
    InstantlyAntwortStatusUnklar,
)


class FakeAntwort:
    def __init__(self, status_code=200, daten=None):
        self.status_code = status_code
        self._daten = daten if daten is not None else {"id": "antwort-1"}

    def json(self):
        return self._daten


class FakeSession:
    def __init__(self, antwort=None, fehler=None):
        self.antwort = antwort or FakeAntwort()
        self.fehler = fehler
        self.aufrufe = []

    def post(self, url, **kwargs):
        self.aufrufe.append((url, kwargs))
        if self.fehler is not None:
            raise self.fehler
        return self.antwort


def _antworten(antworter):
    return antworter.antworten(
        eaccount="wir@digitaldiamonds.de",
        reply_to_uuid="mail-1",
        betreff="Re: Anschreiben",
        text="Danke für die Antwort.",
    )


def test_antworten_nutzt_offiziellen_endpunkt_und_genaue_nutzlast():
    session = FakeSession()
    ergebnis = _antworten(InstantlyAntworter("key", session=session))

    assert ergebnis == {"id": "antwort-1"}
    assert session.aufrufe == [(
        "https://api.instantly.ai/api/v2/emails/reply",
        {
            "headers": {
                "Authorization": "Bearer key",
                "Content-Type": "application/json",
            },
            "json": {
                "eaccount": "wir@digitaldiamonds.de",
                "reply_to_uuid": "mail-1",
                "subject": "Re: Anschreiben",
                "body": {"text": "Danke für die Antwort."},
            },
            "timeout": 60,
        },
    )]


def test_http_4xx_ist_sicher_abgelehnt_ohne_antwortinhalt_im_fehler():
    session = FakeSession(
        FakeAntwort(422, {"message": "vertraulicher Inhalt"})
    )
    with pytest.raises(InstantlyAntwortAbgelehnt, match="422") as fehler:
        _antworten(InstantlyAntworter("key", session=session))

    assert "vertraulicher Inhalt" not in str(fehler.value)


@pytest.mark.parametrize("antwort", [
    FakeAntwort(500, {}),
    FakeAntwort(200, {}),
])
def test_serverfehler_oder_unvollstaendiger_erfolg_bleibt_unklar(antwort):
    with pytest.raises(InstantlyAntwortStatusUnklar):
        _antworten(
            InstantlyAntworter("key", session=FakeSession(antwort))
        )


def test_timeout_bleibt_unklar_und_wird_nicht_wiederholt():
    session = FakeSession(
        fehler=requests.exceptions.Timeout("zu langsam")
    )
    with pytest.raises(InstantlyAntwortStatusUnklar):
        _antworten(InstantlyAntworter("key", session=session))

    assert len(session.aufrufe) == 1


def test_ungueltiges_json_im_erfolg_bleibt_unklar():
    class UngueltigeAntwort(FakeAntwort):
        def json(self):
            raise ValueError("kein JSON")

    with pytest.raises(InstantlyAntwortStatusUnklar):
        _antworten(
            InstantlyAntworter(
                "key", session=FakeSession(UngueltigeAntwort())
            )
        )


def test_geteilter_antworter_verwendet_injizierten_testclient_ohne_api_key(
    monkeypatch,
):
    monkeypatch.delenv("INSTANTLY_API_KEY", raising=False)
    fake = object()
    app = SimpleNamespace(state=SimpleNamespace(
        instantly_antworter=fake,
        _instantly_antworter_lock=threading.Lock(),
    ))

    assert geteilten_antworter(app) is fake


def test_geteilter_antworter_bricht_ohne_client_und_api_key_klar_ab(
    monkeypatch,
):
    monkeypatch.delenv("INSTANTLY_API_KEY", raising=False)
    app = SimpleNamespace(state=SimpleNamespace(
        instantly_antworter=None,
        _instantly_antworter_lock=threading.Lock(),
    ))

    with pytest.raises(RuntimeError, match="INSTANTLY_API_KEY"):
        geteilten_antworter(app)
