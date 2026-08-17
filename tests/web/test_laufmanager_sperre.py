"""Die "zurzeit belegt"-Sperre darf nicht ewig kleben bleiben.

Prozessnummern werden vom Betriebssystem wiederverwendet. Am 12.08.2026
trug eine Sperrdatei die Nummer 802 - die gehoerte inzwischen Notion.
Die Sperre galt als aktiv, und fuer diesen Kunden haette nie wieder ein
Lauf starten koennen. Dieselbe Verwechslung liesse auch einen laengst
fertigen Lauf ewig als "laeuft" erscheinen.

Die Pruefung sitzt deshalb in _pid_lebt(): eine Nummer zaehlt nur dann
als lebendiger Lauf, wenn dort auch wirklich einer unserer Laeufe steckt.
"""
import json
import subprocess
import sys

import pytest

from web.laufmanager import (
    LaufBereitsAktiv, Laufmanager, _ist_unser_lauf, _pid_lebt, _sperr_pid,
    _sperre_schreiben,
)

SPERRDATEI = ".lauf-aktiv"


@pytest.fixture
def manager(tmp_path):
    return Laufmanager(tmp_path)


def sperre(manager, slug, pid=None, roh=None):
    pfad = manager.daten_dir / "laeufe" / slug / SPERRDATEI
    pfad.parent.mkdir(parents=True, exist_ok=True)
    if roh is not None:
        pfad.write_text(roh, encoding="utf-8")
    else:
        _sperre_schreiben(pfad, pid)
    return pfad


# --- die eigentliche Verwechslung -------------------------------------

def test_fremdes_programm_mit_derselben_nummer_gilt_nicht_als_unser_lauf(monkeypatch):
    monkeypatch.setattr(
        "web.laufmanager._prozess_befehl",
        lambda pid: "/Applications/Notion.app/Contents/MacOS/Notion")

    assert _ist_unser_lauf(802) is False


def test_unser_lauf_wird_erkannt(monkeypatch):
    monkeypatch.setattr(
        "web.laufmanager._prozess_befehl",
        lambda pid: f"{sys.executable} -m pipeline lauf kunden/k.yaml --limit 25")

    assert _ist_unser_lauf(4711) is True


def test_lebender_fremdprozess_zaehlt_nicht_als_laufend(monkeypatch):
    # Ein echter, lebender Prozess - aber keiner von uns.
    prozess = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        monkeypatch.setattr("web.laufmanager._prozess_befehl",
                            lambda pid: "/Applications/Notion.app/MacOS/Notion")
        assert _pid_lebt(prozess.pid) is False
    finally:
        prozess.kill()
        prozess.wait()


def test_lebender_eigener_lauf_zaehlt_als_laufend(monkeypatch):
    prozess = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        monkeypatch.setattr("web.laufmanager._prozess_befehl",
                            lambda pid: f"{sys.executable} -m pipeline lauf k.yaml")
        assert _pid_lebt(prozess.pid) is True
    finally:
        prozess.kill()
        prozess.wait()


# --- Wirkung auf die Sperre -------------------------------------------

def test_verwaiste_sperre_blockiert_keinen_neuen_lauf(manager, monkeypatch):
    pfad = sperre(manager, "kunde", pid=802)
    monkeypatch.setattr("web.laufmanager._pid_lebt", lambda pid: False)

    manager._pruefe_sperre("kunde")          # darf NICHT werfen

    assert not pfad.exists()                 # und wird aufgeraeumt


def test_echter_laufender_lauf_blockiert_weiterhin(manager, monkeypatch):
    pfad = sperre(manager, "kunde", pid=4711)
    monkeypatch.setattr("web.laufmanager._pid_lebt", lambda pid: True)

    with pytest.raises(LaufBereitsAktiv):
        manager._pruefe_sperre("kunde")

    assert pfad.exists()


# --- Format der Sperrdatei --------------------------------------------

def test_sperre_notiert_pid_und_startzeitpunkt(manager):
    pfad = sperre(manager, "kunde", pid=4711)

    daten = json.loads(pfad.read_text())

    assert daten["pid"] == 4711
    assert daten["gestartet"]      # ohne Zeitpunkt laesst sich nichts einordnen


def test_alte_sperrdatei_mit_nackter_zahl_wird_noch_gelesen(manager):
    # Vor dem 13.08.2026 stand dort nur die Zahl. Solche Dateien liegen
    # noch herum und duerfen nicht als "unlesbar, also frei" gelten.
    pfad = sperre(manager, "kunde", roh="4711")

    assert _sperr_pid(pfad) == 4711


def test_kaputte_sperrdatei_blockiert_nicht(manager):
    pfad = sperre(manager, "kunde", roh="{kaputt")

    manager._pruefe_sperre("kunde")

    assert not pfad.exists()


def test_sperre_wird_nur_fuer_die_eigene_pid_geloest(manager):
    # Sonst raeumt ein alter, toter Lauf die Sperre eines neuen weg.
    pfad = sperre(manager, "kunde", pid=4711)

    manager._sperre_loesen("kunde", nur_wenn_pid=9999)
    assert pfad.exists()

    manager._sperre_loesen("kunde", nur_wenn_pid=4711)
    assert not pfad.exists()
