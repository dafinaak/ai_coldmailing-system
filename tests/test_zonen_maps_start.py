"""Der Start eines bezahlten Maps-Laufs darf an einem 502 nicht sterben -
und darf ihn auch nicht zweimal starten (09.10.2026).

Am 08.10.2026 fiel Zone 63 mit einem 502 aus, am 09.10.2026 Zone 652
(Taunusstein) beim Start. Beide Male stand `mit_wiederholung` daneben:
die Funktion wiederholt nur Timeout und ConnectionError, und der Start
geht ohnehin nicht durch sie, sondern ist ein einzelner POST ohne jede
Wiederholung.

Blind wiederholen darf man einen Start aber nicht: der POST startet
einen bezahlten Lauf, und bei einem 502 kann der Lauf angelegt worden
sein, obwohl die Antwort verloren ging. Darum wird vor jedem zweiten
Versuch gefragt, ob gerade schon ein Lauf dieses Actors entstanden ist.
"""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

PROJEKT = Path(__file__).resolve().parent.parent


class FakeResponse:
    def __init__(self, status_code, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    @property
    def ok(self):
        return self.status_code < 400

    def json(self):
        return self._payload


class FakeRequests:
    """Eine feste Warteschlange an Antworten; jeder Aufruf wird notiert."""

    class Timeout(Exception):
        pass

    class ConnectionError(Exception):
        pass

    def __init__(self, posts, gets=()):
        self._posts, self._gets = list(posts), list(gets)
        self.posts, self.gets = [], []

    def post(self, url, json=None, headers=None, timeout=None):
        self.posts.append(url)
        antwort = self._posts.pop(0)
        if isinstance(antwort, Exception):
            raise antwort
        return antwort

    def get(self, url, headers=None, timeout=None, params=None):
        self.gets.append(url)
        antwort = self._gets.pop(0) if self._gets else FakeResponse(
            200, {"data": {"items": []}})
        if isinstance(antwort, Exception):
            raise antwort
        return antwort


def _werkzeug(tmp_path, fake):
    pfad = PROJEKT / "werkzeuge" / "zonen-maps.py"
    spec = importlib.util.spec_from_file_location("zonen_maps", pfad)
    modul = importlib.util.module_from_spec(spec)
    sys.modules["zonen_maps"] = modul
    spec.loader.exec_module(modul)
    modul.PROJEKT = tmp_path
    modul.requests = fake
    modul.time = type("T", (), {"sleep": staticmethod(lambda s: None)})()
    return modul


ZONE = {"lauf": "zona652-taunusstein-2026-10-09", "stadt": "Taunusstein"}


def test_ein_502_beim_start_wird_wiederholt(tmp_path):
    """Erst 502, dann geht es - der Lauf kommt zustande."""
    fake = FakeRequests(posts=[
        FakeResponse(502, text="502 Bad Gateway"),
        FakeResponse(201, {"data": {"id": "LAUF1",
                                    "defaultDatasetId": "DS1"}}),
    ], gets=[FakeResponse(200, {"data": {"items": []}})])
    modul = _werkzeug(tmp_path, fake)

    run_id = modul.lauf_starten("tok", "652", ZONE, max_usd=4)

    assert run_id == "LAUF1"
    gespeichert = json.loads(
        (tmp_path / "laeufe/leadquellen" / ZONE["lauf"]
         / "apify-run-id.json").read_text(encoding="utf-8"))
    assert gespeichert["run_id"] == "LAUF1"


def test_nach_einem_502_wird_kein_zweiter_lauf_gestartet(tmp_path):
    """Wenn der 502 den Lauf trotzdem angelegt hat, wird dieser genommen.

    Sonst laeuft derselbe Ort zweimal durch den bezahlten Actor und wir
    zahlen ihn doppelt - der Fehler, den die Geld-Regeln verhindern.
    """
    fake = FakeRequests(
        posts=[FakeResponse(502, text="502 Bad Gateway")],
        gets=[FakeResponse(200, {"data": {"items": [
            {"id": "SCHON_DA", "defaultDatasetId": "DS9",
             "status": "RUNNING"}]}})])
    modul = _werkzeug(tmp_path, fake)

    run_id = modul.lauf_starten("tok", "652", ZONE, max_usd=4)

    assert run_id == "SCHON_DA"
    assert len(fake.posts) == 1, "ein zweiter POST wuerde doppelt bezahlen"


def test_eine_echte_absage_wird_nicht_wiederholt(tmp_path):
    """403 oder 400 sind Absagen, keine Stoerungen - sofort laut stoppen.

    Zone 44 bekam am 29.09.2026 ein 403; es noch viermal zu versuchen
    verschleppt nur die Meldung, die der Mensch lesen muss.
    """
    fake = FakeRequests(posts=[FakeResponse(403, text="forbidden")])
    modul = _werkzeug(tmp_path, fake)

    with pytest.raises(SystemExit, match="403"):
        modul.lauf_starten("tok", "652", ZONE, max_usd=4)
    assert len(fake.posts) == 1


def test_ein_netzfehler_beim_start_wird_auch_wiederholt(tmp_path):
    fake = FakeRequests(posts=[
        FakeRequests.ConnectionError("kein Netz"),
        FakeResponse(201, {"data": {"id": "LAUF2",
                                    "defaultDatasetId": "DS2"}}),
    ], gets=[FakeResponse(200, {"data": {"items": []}})])
    modul = _werkzeug(tmp_path, fake)

    assert modul.lauf_starten("tok", "652", ZONE, max_usd=4) == "LAUF2"
