"""Tests fuer web.laufmanager.Laufmanager (Auftraege starten/fortsetzen/
Status lesen) und die zugehoerigen Routen in web/routen/auftraege.py.

Kein Test startet einen echten Netzwerk-Aufruf: `subprocess.Popen` wird ueber
`web.laufmanager.subprocess.Popen` durch ein Fake ersetzt, das nur die
Aufruf-Argumente aufzeichnet und (wo noetig) selbst die Verzeichnis-/
Datei-Wirkung nachbildet, die der echte Unterprozess (RunStore) haette.
`_pid_lebt` wird ueber `web.laufmanager._pid_lebt` fuer die Status-Tests
gefaked, damit kein echter Prozess gestartet/beendet werden muss.

PFLICHT-PRUEFPUNKT (Plan Task 4, Review 17.07.2026): der Unterprozess MUSS
mit cwd=daten_dir gestartet werden, sonst faellt die globale Sperrliste im
falschen Arbeitsverzeichnis leise aus (lade_globale_sperrliste(Path("."))
liest die falsche Datei, findet nichts, gibt aber bewusst [] statt Fehler
zurueck - ein stiller Sicherheits-Bypass). Der Beweis ist zweigeteilt:
  (a) test_starte_verwendet_cwd_gleich_daten_dir zeigt, dass
      Laufmanager.starte() den Unterprozess TATSAECHLICH mit cwd=daten_dir
      aufruft (Fake-Popen-Capture).
  (b) test_pflicht_pipeline_ehrt_globale_sperrliste_bei_cwd_ungleich_code_dir
      zeigt, dass die Pipeline selbst (das Programm, das dieser Unterprozess
      ausfuehrt) bei einem cwd, das NICHT der Code-Ordner ist, die globale
      Sperrliste trotzdem anwendet - getrieben in-process (kein echter
      Unterprozess, kein Netzwerk) mit monkeypatch.chdir(daten_dir) +
      gefaktem source_leads/KI, exakt wie in tests/test_cli.py. Zusammen
      beweisen (a) und (b) den End-zu-Ende-Vertrag, ohne dass ein Test einen
      echten Netzwerk-Unterprozess starten muesste.
"""
import inspect
import json
import sys
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient
from passlib.context import CryptContext

from tests.test_cli import _TEST_KUNDE_YAML
from web import laufmanager
from web.app import create_app
from web.laufmanager import KundeNichtGefunden, LaufBereitsAktiv, Laufmanager, LaufmanagerFehler
from web.routen import auftraege as auftraege_modul

PWD_CONTEXT = CryptContext(schemes=["bcrypt"], deprecated="auto")


class FakeProzess:
    """Ersetzt das von subprocess.Popen(...) zurueckgegebene Prozess-Objekt.
    laeuft=True -> poll() liefert None (Prozess lebt noch); laeuft=False ->
    poll() liefert 0 (sofort beendet, z.B. simulierter Sofort-Abbruch)."""

    def __init__(self, pid: int, laeuft: bool = False):
        self.pid = pid
        self._laeuft = laeuft

    def poll(self):
        return None if self._laeuft else 0


def _kunde_datei(daten_dir: Path, dateiname: str = "test-kunde") -> str:
    (daten_dir / "kunden").mkdir(parents=True, exist_ok=True)
    (daten_dir / "kunden" / f"{dateiname}.yaml").write_text(_TEST_KUNDE_YAML, encoding="utf-8")
    return f"kunden/{dateiname}.yaml"


def _fabriziere_laufordner(daten_dir: Path, *, slug: str = "test-gmbh",
                            ts: str = "20260101-000000", pid=None,
                            leads=None, dedupe=None, personalisierung=None,
                            pruefung_ok=None, freigabe=False, versand_komplett=None,
                            abgelehnt=None, firmen=None,
                            log: str | None = None, meta: dict | None = None) -> Path:
    lauf_dir = daten_dir / "laeufe" / slug / ts
    lauf_dir.mkdir(parents=True)
    if pid is not None:
        (lauf_dir / "pid").write_text(str(pid), encoding="utf-8")
    if leads is not None:
        (lauf_dir / "leads.json").write_text(json.dumps(leads), encoding="utf-8")
    if firmen is not None:
        (lauf_dir / "firmen.json").write_text(json.dumps(firmen), encoding="utf-8")
    if dedupe is not None:
        (lauf_dir / "dedupe.json").write_text(json.dumps(dedupe), encoding="utf-8")
    if personalisierung is not None:
        (lauf_dir / "personalisierung.json").write_text(json.dumps(personalisierung), encoding="utf-8")
    if pruefung_ok is not None:
        (lauf_dir / "pruefung_ok.json").write_text(json.dumps(pruefung_ok), encoding="utf-8")
    if freigabe:
        (lauf_dir / "FREIGABE.txt").write_text("Freigegeben am 2026-07-17\n", encoding="utf-8")
    if versand_komplett is not None:
        (lauf_dir / "versand_komplett.json").write_text(json.dumps(versand_komplett), encoding="utf-8")
    if abgelehnt is not None:
        (lauf_dir / "abgelehnt.json").write_text(json.dumps(abgelehnt), encoding="utf-8")
    if log is not None:
        (lauf_dir / "lauf.log").write_text(log, encoding="utf-8")
    if meta is not None:
        (lauf_dir / "auftrag_meta.json").write_text(json.dumps(meta), encoding="utf-8")
    return lauf_dir


# PFLICHT-PRUEFPUNKT ---------------------------------------------------------

def test_starte_verwendet_cwd_gleich_daten_dir(tmp_path, monkeypatch):
    """(a) siehe Modul-Docstring: Laufmanager.starte() MUSS den Unterprozess
    mit cwd=daten_dir aufrufen."""
    daten_dir = tmp_path
    kunde_datei = _kunde_datei(daten_dir)
    aufrufe = []

    def fake_popen(argv, cwd=None, stdout=None, stderr=None, env=None):
        aufrufe.append({"argv": argv, "cwd": cwd})
        (daten_dir / "laeufe" / "test-gmbh" / "20260101-000000").mkdir(parents=True)
        return FakeProzess(pid=4242, laeuft=False)

    monkeypatch.setattr(laufmanager.subprocess, "Popen", fake_popen)

    manager = Laufmanager(daten_dir)
    lauf_dir = manager.starte(kunde_datei, 25)

    assert len(aufrufe) == 1
    assert aufrufe[0]["cwd"] == str(daten_dir)
    assert aufrufe[0]["argv"][-4:] == ["lauf", kunde_datei, "--limit", "25"]
    assert lauf_dir == daten_dir / "laeufe" / "test-gmbh" / "20260101-000000"


def test_pflicht_pipeline_ehrt_globale_sperrliste_bei_cwd_ungleich_code_dir(tmp_path, monkeypatch):
    """(b) siehe Modul-Docstring: die Pipeline selbst wendet die globale
    Sperrliste an, wenn ihr Arbeitsverzeichnis (cwd) auf ein daten_dir zeigt,
    das NICHT das Projekt-Wurzelverzeichnis (Code-Ordner) ist. Getrieben
    in-process wie tests/test_cli.py::
    test_lauf_globale_sperrliste_blockt_lead_auch_ohne_eigene_kunden_sperrliste
    - bewusst dieselbe Pruefung, hier aber als Teil des PFLICHT-Nachweises
    fuer Task 4 nochmal explizit hinterlegt."""
    import pipeline.__main__ as cli
    import pipeline.run_store as run_store_modul
    from tests.test_cli import _fake_source_leads, _FakeDatetime, _FakeKI

    daten_dir = tmp_path / "ein-datenverzeichnis-das-nicht-der-code-ordner-ist"
    daten_dir.mkdir()
    kunde_datei = daten_dir / "test-kunde.yaml"
    kunde_datei.write_text(_TEST_KUNDE_YAML, encoding="utf-8")
    (daten_dir / "sperrliste-global.yaml").write_text(
        yaml.safe_dump(["firma.de"]), encoding="utf-8")

    monkeypatch.setattr(cli, "source_leads", _fake_source_leads)
    monkeypatch.setattr(cli, "KI", _FakeKI)
    monkeypatch.setattr(run_store_modul, "datetime", _FakeDatetime)
    monkeypatch.setenv("APIFY_API_KEY", "test-key")
    monkeypatch.setenv("HUNTER_API_KEY", "test-key")
    monkeypatch.setenv("DROPCONTACT_API_KEY", "test-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(cli, "LAEUFE", Path("laeufe"))
    monkeypatch.chdir(daten_dir)  # simuliert das cwd, mit dem der Unterprozess laeuft

    cli.lauf(str(kunde_datei.name), 10, None)

    laeufe = sorted((daten_dir / "laeufe" / "test-gmbh").glob("*"))
    assert len(laeufe) == 1
    dedupe_stand = json.loads((laeufe[0] / "dedupe.json").read_text(encoding="utf-8"))
    assert dedupe_stand["behalten"] == []
    assert len(dedupe_stand["verworfen"]) == 2
    assert all(v["grund"] == "Domain auf Sperrliste" for v in dedupe_stand["verworfen"])


# starte() -------------------------------------------------------------------

def test_starte_legt_pid_datei_sperre_und_meta_an(tmp_path, monkeypatch):
    daten_dir = tmp_path
    kunde_datei = _kunde_datei(daten_dir)

    def fake_popen(argv, cwd=None, stdout=None, stderr=None, env=None):
        (daten_dir / "laeufe" / "test-gmbh" / "20260101-000000").mkdir(parents=True)
        return FakeProzess(pid=4242, laeuft=False)

    monkeypatch.setattr(laufmanager.subprocess, "Popen", fake_popen)

    lauf_dir = Laufmanager(daten_dir).starte(kunde_datei, 25)

    assert (lauf_dir / "pid").read_text(encoding="utf-8") == "4242"
    assert (daten_dir / "laeufe" / "test-gmbh" / ".lauf-aktiv").read_text(encoding="utf-8") == "4242"
    meta = json.loads((lauf_dir / "auftrag_meta.json").read_text(encoding="utf-8"))
    assert meta == {"kunde_datei": kunde_datei, "limit": 25}
    assert (lauf_dir / "lauf.log").exists()


def test_starte_verweigert_zweiten_lauf_fuer_gleichen_kunden(tmp_path, monkeypatch):
    daten_dir = tmp_path
    kunde_datei = _kunde_datei(daten_dir)

    def fake_popen(argv, cwd=None, stdout=None, stderr=None, env=None):
        (daten_dir / "laeufe" / "test-gmbh" / "20260101-000000").mkdir(parents=True, exist_ok=True)
        return FakeProzess(pid=4242, laeuft=True)

    monkeypatch.setattr(laufmanager.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(laufmanager, "_pid_lebt", lambda pid: True)

    manager = Laufmanager(daten_dir)
    manager.starte(kunde_datei, 25)

    with pytest.raises(LaufBereitsAktiv, match="läuft gerade schon eine E-Mail-Runde"):
        manager.starte(kunde_datei, 25)


def test_starte_raeumt_verwaiste_sperre_auf_und_startet_neu(tmp_path, monkeypatch):
    daten_dir = tmp_path
    kunde_datei = _kunde_datei(daten_dir)
    (daten_dir / "laeufe" / "test-gmbh").mkdir(parents=True)
    (daten_dir / "laeufe" / "test-gmbh" / ".lauf-aktiv").write_text("999", encoding="utf-8")

    def fake_popen(argv, cwd=None, stdout=None, stderr=None, env=None):
        (daten_dir / "laeufe" / "test-gmbh" / "20260101-000000").mkdir(parents=True, exist_ok=True)
        return FakeProzess(pid=4242, laeuft=False)

    monkeypatch.setattr(laufmanager.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(laufmanager, "_pid_lebt", lambda pid: False)  # 999 ist tot

    lauf_dir = Laufmanager(daten_dir).starte(kunde_datei, 10)
    assert lauf_dir.exists()
    assert (daten_dir / "laeufe" / "test-gmbh" / ".lauf-aktiv").read_text() == "4242"


def test_starte_ohne_bekannten_kunden_wirft_kundenichtgefunden(tmp_path):
    with pytest.raises(KundeNichtGefunden):
        Laufmanager(tmp_path).starte("kunden/gibts-nicht.yaml", 10)


def test_starte_ohne_neuen_laufordner_wirft_fehler_mit_hunter_hinweis(tmp_path, monkeypatch):
    daten_dir = tmp_path
    kunde_datei = _kunde_datei(daten_dir)

    def fake_popen(argv, cwd=None, stdout=None, stderr=None, env=None):
        # Simuliert einen Unterprozess, der SOFORT abbricht (z.B. fehlende
        # Umgebungsvariable) - RunStore legt den Laufordner erst NACH den
        # Env-Pruefungen an, hier entsteht also gar kein Ordner.
        stdout.write(b"Fehlende Umgebungsvariable: HUNTER_API_KEY. "
                     b"Bitte in .env eintragen (siehe .env.example).\n")
        return FakeProzess(pid=1, laeuft=False)

    monkeypatch.setattr(laufmanager.subprocess, "Popen", fake_popen)

    with pytest.raises(LaufmanagerFehler, match="Entscheider-Suche"):
        Laufmanager(daten_dir).starte(kunde_datei, 10)

    # Keine verwaiste temporaere Log-Datei zurueckgelassen.
    reste = list((daten_dir / "laeufe" / "test-gmbh").glob(".*"))
    assert reste == []


# setze_fort() -----------------------------------------------------------

def test_setze_fort_baut_korrekten_befehl_aus_gespeicherter_meta(tmp_path, monkeypatch):
    daten_dir = tmp_path
    lauf_dir = _fabriziere_laufordner(
        daten_dir, meta={"kunde_datei": "kunden/test-kunde.yaml", "limit": 25})
    aufrufe = []

    def fake_popen(argv, cwd=None, stdout=None, stderr=None, env=None):
        aufrufe.append({"argv": argv, "cwd": cwd})
        return FakeProzess(pid=99, laeuft=True)

    monkeypatch.setattr(laufmanager.subprocess, "Popen", fake_popen)

    ergebnis = Laufmanager(daten_dir).setze_fort(lauf_dir)

    assert ergebnis == lauf_dir
    assert aufrufe[0]["cwd"] == str(daten_dir)
    assert aufrufe[0]["argv"][-6:] == [
        "lauf", "kunden/test-kunde.yaml", "--limit", "25", "--fortsetzen", str(lauf_dir)]
    assert (lauf_dir / "pid").read_text() == "99"
    assert (daten_dir / "laeufe" / "test-gmbh" / ".lauf-aktiv").read_text() == "99"


def test_setze_fort_mit_neu_ab_haengt_flag_an(tmp_path, monkeypatch):
    daten_dir = tmp_path
    lauf_dir = _fabriziere_laufordner(
        daten_dir, meta={"kunde_datei": "kunden/test-kunde.yaml", "limit": 25})
    aufrufe = []
    monkeypatch.setattr(
        laufmanager.subprocess, "Popen",
        lambda argv, cwd=None, stdout=None, stderr=None, env=None: (aufrufe.append(argv), FakeProzess(1, True))[1])

    Laufmanager(daten_dir).setze_fort(lauf_dir, neu_ab="dedupe")

    assert aufrufe[0][-2:] == ["--neu-ab", "dedupe"]


def test_setze_fort_faellt_auf_kunde_pfad_json_zurueck_ohne_meta(tmp_path, monkeypatch):
    # Laufordner, der nicht von Laufmanager.starte() stammt (z.B. direkt per
    # CLI erzeugt) - kein auftrag_meta.json, nur das kunde_pfad-Step-File,
    # das die Pipeline selbst schreibt.
    daten_dir = tmp_path
    lauf_dir = daten_dir / "laeufe" / "test-gmbh" / "20260101-000000"
    lauf_dir.mkdir(parents=True)
    (lauf_dir / "kunde_pfad.json").write_text(
        json.dumps({"pfad": "kunden/test-kunde.yaml"}), encoding="utf-8")
    aufrufe = []
    monkeypatch.setattr(
        laufmanager.subprocess, "Popen",
        lambda argv, cwd=None, stdout=None, stderr=None, env=None: (aufrufe.append(argv), FakeProzess(1, True))[1])

    Laufmanager(daten_dir).setze_fort(lauf_dir)

    assert "kunden/test-kunde.yaml" in aufrufe[0]
    assert "--limit" in aufrufe[0]  # Default-Limit greift, kein Absturz


# status() ------------------------------------------------------------------

def test_status_laeuft_wenn_pid_lebt(tmp_path, monkeypatch):
    lauf_dir = _fabriziere_laufordner(tmp_path, pid=123)
    monkeypatch.setattr(laufmanager, "_pid_lebt", lambda pid: True)
    assert Laufmanager(tmp_path).status(lauf_dir)["zustand"] == "laeuft"


def test_status_angehalten_wenn_pid_tot_und_keine_pruefung(tmp_path, monkeypatch):
    lauf_dir = _fabriziere_laufordner(
        tmp_path, pid=123, log="Start\nRuntimeError: Hunter antwortet mit 500 auf https://x\n")
    monkeypatch.setattr(laufmanager, "_pid_lebt", lambda pid: False)
    stand = Laufmanager(tmp_path).status(lauf_dir)
    assert stand["zustand"] == "angehalten"
    assert stand["fehler"]["was"] == "Die Entscheider-Suche hat gerade nicht geantwortet."


def test_status_loescht_sperre_wenn_pid_tot(tmp_path, monkeypatch):
    daten_dir = tmp_path
    lauf_dir = _fabriziere_laufordner(daten_dir, pid=123)
    sperr_pfad = daten_dir / "laeufe" / "test-gmbh" / ".lauf-aktiv"
    sperr_pfad.write_text("123", encoding="utf-8")
    monkeypatch.setattr(laufmanager, "_pid_lebt", lambda pid: False)

    Laufmanager(daten_dir).status(lauf_dir)

    assert not sperr_pfad.exists()


def test_status_erhaelt_fremde_sperre_eines_neueren_lebenden_laufs(tmp_path, monkeypatch):
    # CRITICAL Review-Fund: status() wird fuer JEDEN Laufordner desselben
    # Kunden aufgerufen (Dashboard/Kampagnen/Pruefen iterieren ueber ALLE
    # Laeufe). Ein alter, laengst toter Lauf darf NICHT die Sperrdatei
    # loeschen, wenn die Sperre inzwischen einem NEUEREN, gerade aktiv
    # laufenden Auftrag desselben Kunden gehoert (andere PID) - sonst
    # wuerde jeder Seitenaufruf, der auch den alten Laufordner sieht, den
    # Sperr-Schutz fuer den aktiven neueren Lauf aufheben.
    daten_dir = tmp_path
    alter_lauf = _fabriziere_laufordner(daten_dir, ts="20260101-000000", pid=111)
    sperr_pfad = daten_dir / "laeufe" / "test-gmbh" / ".lauf-aktiv"
    sperr_pfad.write_text("222", encoding="utf-8")  # gehoert dem neueren, lebenden Lauf

    monkeypatch.setattr(laufmanager, "_pid_lebt", lambda pid: pid == 222)

    stand = Laufmanager(daten_dir).status(alter_lauf)

    assert stand["zustand"] == "angehalten"  # 111 ist tot, dieser Lauf ist angehalten
    assert sperr_pfad.exists()
    assert sperr_pfad.read_text(encoding="utf-8") == "222"


def test_status_loescht_sperre_nur_wenn_inhalt_exakt_dieser_pid_entspricht(tmp_path, monkeypatch):
    # Gegenstueck zum obigen Test: bestaetigt, dass der bestehende
    # Aufraeum-Vertrag (Sperre IST dieser tote pid -> loeschen) durch den
    # Fix nicht verloren geht - siehe test_status_loescht_sperre_wenn_pid_tot
    # oben fuer den einfachen Fall, hier zusaetzlich mit zwei Laufordnern.
    daten_dir = tmp_path
    lauf_dir = _fabriziere_laufordner(daten_dir, ts="20260101-000000", pid=123)
    sperr_pfad = daten_dir / "laeufe" / "test-gmbh" / ".lauf-aktiv"
    sperr_pfad.write_text("123", encoding="utf-8")  # Sperre gehoert GENAU diesem toten Lauf
    monkeypatch.setattr(laufmanager, "_pid_lebt", lambda pid: False)

    Laufmanager(daten_dir).status(lauf_dir)

    assert not sperr_pfad.exists()


def test_status_wartet_auf_freigabe(tmp_path, monkeypatch):
    lauf_dir = _fabriziere_laufordner(tmp_path, pid=123, pruefung_ok=[{"email": "a@b.de"}])
    monkeypatch.setattr(laufmanager, "_pid_lebt", lambda pid: False)
    assert Laufmanager(tmp_path).status(lauf_dir)["zustand"] == "wartet_auf_freigabe"


def test_status_freigegeben(tmp_path, monkeypatch):
    lauf_dir = _fabriziere_laufordner(
        tmp_path, pid=123, pruefung_ok=[{"email": "a@b.de"}], freigabe=True)
    monkeypatch.setattr(laufmanager, "_pid_lebt", lambda pid: False)
    assert Laufmanager(tmp_path).status(lauf_dir)["zustand"] == "freigegeben"


def test_status_uebergeben(tmp_path, monkeypatch):
    lauf_dir = _fabriziere_laufordner(
        tmp_path, pid=123, pruefung_ok=[{"email": "a@b.de"}], freigabe=True,
        versand_komplett={"campaign_id": "camp-1"})
    monkeypatch.setattr(laufmanager, "_pid_lebt", lambda pid: False)
    assert Laufmanager(tmp_path).status(lauf_dir)["zustand"] == "uebergeben"


def test_status_abgelehnt(tmp_path, monkeypatch):
    # Carry-Forward aus Task-4-Review (Task 5): abgelehnt.json (geschrieben
    # von web/routen/freigabe.py beim Ablehnen) muss den Zustand "abgelehnt"
    # ergeben, sonst zeigt ein abgelehnter Lauf fuer immer "wartet auf
    # Freigabe" in Kampagnen-/Pruefen-Uebersichten.
    lauf_dir = _fabriziere_laufordner(
        tmp_path, pid=123, pruefung_ok=[{"email": "a@b.de"}],
        abgelehnt={"von": "Lena Hartmann", "am": "17.07.2026, 16:00",
                   "begruendung": "Ton passt nicht"})
    monkeypatch.setattr(laufmanager, "_pid_lebt", lambda pid: False)
    assert Laufmanager(tmp_path).status(lauf_dir)["zustand"] == "abgelehnt"


def test_status_abgelehnt_hat_vorrang_vor_wartet_auf_freigabe(tmp_path, monkeypatch):
    # Ohne abgelehnt.json waere derselbe Laufordner "wartet_auf_freigabe"
    # (pruefung_ok da, keine Freigabe/kein Versand) - abgelehnt.json muss
    # das ueberschreiben, sonst taucht der Lauf weiter in der Warteliste auf.
    lauf_dir = _fabriziere_laufordner(
        tmp_path, pid=123, pruefung_ok=[{"email": "a@b.de"}],
        abgelehnt={"von": "Lena", "am": "17.07.2026", "begruendung": "x"})
    monkeypatch.setattr(laufmanager, "_pid_lebt", lambda pid: False)
    stand = Laufmanager(tmp_path).status(lauf_dir)
    assert stand["zustand"] != "wartet_auf_freigabe"
    assert stand["zustand"] == "abgelehnt"


def test_status_liest_zahlen_aus_step_dateien(tmp_path, monkeypatch):
    lauf_dir = _fabriziere_laufordner(
        tmp_path, pid=123,
        leads={"leads": [{}] * 5, "ohne_email": 2},
        dedupe={"behalten": [{}] * 3, "verworfen": [{"grund": "x"}, {"grund": "y"}]},
        personalisierung={"fertig": [{}] * 2, "nacharbeit": [{}]},
    )
    monkeypatch.setattr(laufmanager, "_pid_lebt", lambda pid: True)
    stand = Laufmanager(tmp_path).status(lauf_dir)
    assert stand["gefunden"] == 5
    assert stand["ohne_email"] == 2
    assert stand["verworfen"] == 2
    assert stand["fertig"] == 2
    assert stand["nacharbeit"] == 1
    assert stand["schritt"] == 5


def test_status_schritt_1_ohne_leads(tmp_path, monkeypatch):
    lauf_dir = _fabriziere_laufordner(tmp_path, pid=1)
    monkeypatch.setattr(laufmanager, "_pid_lebt", lambda pid: True)
    assert Laufmanager(tmp_path).status(lauf_dir)["schritt"] == 1


def test_status_schritt_3_nach_leads_vor_dedupe(tmp_path, monkeypatch):
    lauf_dir = _fabriziere_laufordner(tmp_path, pid=1, leads={"leads": [], "ohne_email": 0})
    monkeypatch.setattr(laufmanager, "_pid_lebt", lambda pid: True)
    assert Laufmanager(tmp_path).status(lauf_dir)["schritt"] == 3


def test_status_generischer_fehlertext_bei_unbekanntem_fehler(tmp_path, monkeypatch):
    lauf_dir = _fabriziere_laufordner(tmp_path, pid=1, log="Start\nIrgendein anderer Absturz: X\n")
    monkeypatch.setattr(laufmanager, "_pid_lebt", lambda pid: False)
    stand = Laufmanager(tmp_path).status(lauf_dir)
    assert "Irgendein anderer Absturz: X" in stand["fehler"]["tu"]
    assert stand["fehler"]["was"] == "Es gab ein Problem, das wir nicht genauer benennen können."


def test_status_akzeptiert_altes_leads_listenformat(tmp_path, monkeypatch):
    lauf_dir = _fabriziere_laufordner(tmp_path, pid=1, leads=[{"email": "a@b.de"}])
    monkeypatch.setattr(laufmanager, "_pid_lebt", lambda pid: True)
    stand = Laufmanager(tmp_path).status(lauf_dir)
    assert stand["gefunden"] == 1
    assert stand["ohne_email"] == 0


# Routen ----------------------------------------------------------------

@pytest.fixture
def daten_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("WEB_SECRET", "test-geheimnis-nur-fuer-tests")
    monkeypatch.setenv("WEB_COOKIE_SECURE", "0")
    nutzer = [{"name": "Lena Hartmann", "passwort_hash": PWD_CONTEXT.hash("richtig123")}]
    (tmp_path / "users.yaml").write_text(yaml.safe_dump(nutzer, allow_unicode=True), encoding="utf-8")
    return tmp_path


@pytest.fixture
def app(daten_dir):
    return create_app(daten_dir)


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def angemeldeter_client(client):
    client.post("/login", data={"name": "Lena Hartmann", "passwort": "richtig123"})
    # Copy-Rework (20.07.2026): siehe tests/web/test_dashboard.py fuer den Grund.
    client.cookies.set("intro_gesehen", "1")
    return client


def test_dialog_verlangt_anmeldung(client):
    antwort = client.get("/auftraege/neu", follow_redirects=False)
    assert antwort.status_code == 303
    assert antwort.headers["location"] == "/login"


def test_dialog_ohne_kunden_zeigt_hinweis(angemeldeter_client):
    antwort = angemeldeter_client.get("/auftraege/neu")
    assert antwort.status_code == 200
    assert "Noch keine Angebote angelegt." in antwort.text


def test_dialog_listet_kunden_und_zeigt_leitfaden_text(angemeldeter_client, daten_dir):
    _kunde_datei(daten_dir)
    antwort = angemeldeter_client.get("/auftraege/neu")
    assert antwort.status_code == 200
    assert "Test GmbH" in antwort.text
    assert "E-Mails schreiben lassen" in antwort.text
    assert "Versendet wird nichts" in antwort.text


def test_start_ohne_kunden_auswahl_zeigt_deutschen_fehler(angemeldeter_client, daten_dir):
    _kunde_datei(daten_dir)
    antwort = angemeldeter_client.post(
        "/auftraege/neu", data={"kunde_dateiname": "", "limit": "25"})
    assert antwort.status_code == 400
    assert "Noch keine Angebote angelegt." in antwort.text


def test_start_redirect_zur_fortschrittsseite(angemeldeter_client, daten_dir, monkeypatch):
    _kunde_datei(daten_dir)

    def fake_popen(argv, cwd=None, stdout=None, stderr=None, env=None):
        (daten_dir / "laeufe" / "test-gmbh" / "20260101-000000").mkdir(parents=True)
        return FakeProzess(pid=555, laeuft=True)

    monkeypatch.setattr(laufmanager.subprocess, "Popen", fake_popen)

    antwort = angemeldeter_client.post(
        "/auftraege/neu", data={"kunde_dateiname": "test-kunde", "limit": "25"},
        follow_redirects=False)
    assert antwort.status_code == 303
    assert antwort.headers["location"] == "/auftraege/test-gmbh/20260101-000000"
    meta = json.loads(
        (daten_dir / "laeufe" / "test-gmbh" / "20260101-000000" / "auftrag_meta.json")
        .read_text(encoding="utf-8"))
    assert meta["gestartet_von"] == "Lena Hartmann"


def test_start_bei_gesperrtem_kunden_zeigt_deutschen_fehler(angemeldeter_client, daten_dir, monkeypatch):
    _kunde_datei(daten_dir)
    (daten_dir / "laeufe" / "test-gmbh").mkdir(parents=True)
    (daten_dir / "laeufe" / "test-gmbh" / ".lauf-aktiv").write_text("123", encoding="utf-8")
    monkeypatch.setattr(laufmanager, "_pid_lebt", lambda pid: True)

    antwort = angemeldeter_client.post(
        "/auftraege/neu", data={"kunde_dateiname": "test-kunde", "limit": "25"})
    assert antwort.status_code == 400
    assert "Für dieses Angebot läuft gerade schon eine E-Mail-Runde." in antwort.text


def test_fortschrittsseite_zeigt_schritte_und_zahlen_waehrend_laeuft(
        angemeldeter_client, daten_dir, monkeypatch):
    _kunde_datei(daten_dir)
    _fabriziere_laufordner(
        daten_dir, pid=999, leads={"leads": [{}] * 4, "ohne_email": 1},
        meta={"kunde_datei": "kunden/test-kunde.yaml", "limit": 25,
              "gestartet_von": "Lena Hartmann", "gestartet_am": "17.07.2026, 10:00"})
    monkeypatch.setattr(laufmanager, "_pid_lebt", lambda pid: True)

    antwort = angemeldeter_client.get("/auftraege/test-gmbh/20260101-000000")
    assert antwort.status_code == 200
    assert "E-Mail-Runde für Test GmbH" in antwort.text
    assert "Das System arbeitet — du musst nichts tun." in antwort.text
    assert "Passende Firmen und Ansprechpartner suchen" in antwort.text
    assert "Jeden Text prüfen: Klingt er persönlich? Stimmt alles?" in antwort.text
    assert ">4<" in antwort.text  # gefunden-Zahl
    assert "von Lena Hartmann" in antwort.text


def test_fortschrittsseite_zeigt_fehlerbox_und_fortsetzen_knopf_bei_angehalten(
        angemeldeter_client, daten_dir, monkeypatch):
    _kunde_datei(daten_dir)
    _fabriziere_laufordner(
        daten_dir, pid=999, log="RuntimeError: Hunter antwortet mit 500 auf https://x\n",
        meta={"kunde_datei": "kunden/test-kunde.yaml", "limit": 25, "gestartet_am": "17.07.2026, 10:00"})
    monkeypatch.setattr(laufmanager, "_pid_lebt", lambda pid: False)

    antwort = angemeldeter_client.get("/auftraege/test-gmbh/20260101-000000")
    assert antwort.status_code == 200
    assert "Angehalten: E-Mail-Runde für Test GmbH" in antwort.text
    assert "Die Entscheider-Suche hat gerade nicht geantwortet." in antwort.text
    assert "Fortsetzen" in antwort.text
    assert 'action="/auftraege/test-gmbh/20260101-000000/fortsetzen"' in antwort.text


def test_fortschrittsseite_zeigt_wartet_seit_text_bei_wartet_auf_freigabe(
        angemeldeter_client, daten_dir, monkeypatch):
    _kunde_datei(daten_dir)
    _fabriziere_laufordner(
        daten_dir, pid=999, pruefung_ok=[{"email": "a@b.de"}],
        meta={"kunde_datei": "kunden/test-kunde.yaml", "limit": 25, "gestartet_am": "17.07.2026, 10:00"})
    monkeypatch.setattr(laufmanager, "_pid_lebt", lambda pid: False)

    antwort = angemeldeter_client.get("/auftraege/test-gmbh/20260101-000000")
    assert antwort.status_code == 200
    assert "Wartet seit" in antwort.text
    assert "darauf, dass du sie liest" in antwort.text
    assert "Jetzt lesen" in antwort.text


def test_fortschrittsseite_404_bei_unbekanntem_lauf(angemeldeter_client):
    antwort = angemeldeter_client.get("/auftraege/nichtvorhanden/20260101-000000")
    assert antwort.status_code == 404


def test_status_json_shape(angemeldeter_client, daten_dir, monkeypatch):
    _fabriziere_laufordner(daten_dir, pid=999)
    monkeypatch.setattr(laufmanager, "_pid_lebt", lambda pid: True)

    antwort = angemeldeter_client.get("/auftraege/test-gmbh/20260101-000000/status.json")
    assert antwort.status_code == 200
    daten = antwort.json()
    assert daten["zustand"] == "laeuft"
    erwartete_felder = {
        "zustand", "schritt", "schritt_label", "gefunden", "ohne_email",
        "verworfen", "fertig", "nacharbeit", "fehler",
        "deckungsquote", "firmen_gesamt", "firmen_mit_kontakt",
        "mit_entscheider", "info_fallback",
    }
    assert erwartete_felder <= set(daten.keys())


def _lauf_mit_deckung(daten_dir):
    # Ein durchgelaufener Auftrag: 3 Firmen, 2 erreicht (1 persoenlich, 1 info@),
    # eine ohne Webseite. Deckung steckt in leads.json, Ausgaenge in firmen.json.
    return _fabriziere_laufordner(
        daten_dir, pid=999,
        leads={"leads": [{"email": "a@f1.de"}, {"email": "info@f2.de"}],
               "deckung": {"firmen_gesamt": 3, "firmen_mit_kontakt": 2, "quote_prozent": 66.7}},
        dedupe={"behalten": [], "verworfen": []},
        personalisierung={"fertig": [{"email": "a@f1.de"}], "nacharbeit": []},
        pruefung_ok=[{"email": "a@f1.de"}],
        firmen=[{"domain": "f1.de", "ausgang": "mit_entscheider"},
                {"domain": "f2.de", "ausgang": "info_fallback"},
                {"domain": "", "ausgang": "keine_webseite"}])


def test_status_liefert_deckung_und_persoenlich_vs_info(daten_dir, monkeypatch):
    lauf_dir = _lauf_mit_deckung(daten_dir)
    monkeypatch.setattr(laufmanager, "_pid_lebt", lambda pid: False)
    stand = Laufmanager(daten_dir).status(lauf_dir)
    assert stand["deckungsquote"] == 66.7
    assert stand["firmen_mit_kontakt"] == 2 and stand["firmen_gesamt"] == 3
    assert stand["mit_entscheider"] == 1 and stand["info_fallback"] == 1


def test_fortschrittsseite_zeigt_persoenlich_vs_info(angemeldeter_client, daten_dir, monkeypatch):
    _lauf_mit_deckung(daten_dir)
    monkeypatch.setattr(laufmanager, "_pid_lebt", lambda pid: False)
    antwort = angemeldeter_client.get("/auftraege/test-gmbh/20260101-000000")
    assert antwort.status_code == 200
    assert "mit persönlichem Entscheider" in antwort.text
    assert "nur über info@" in antwort.text
    assert "von" in antwort.text and "Firmen erreicht" in antwort.text


def test_fortsetzen_route_startet_unterprozess_und_leitet_zurueck(
        angemeldeter_client, daten_dir, monkeypatch):
    lauf_dir = _fabriziere_laufordner(
        daten_dir, pid=999, meta={"kunde_datei": "kunden/test-kunde.yaml", "limit": 25})
    monkeypatch.setattr(laufmanager, "_pid_lebt", lambda pid: False)  # angehalten

    aufrufe = []

    def fake_popen(argv, cwd=None, stdout=None, stderr=None, env=None):
        aufrufe.append(argv)
        return FakeProzess(pid=777, laeuft=True)

    monkeypatch.setattr(laufmanager.subprocess, "Popen", fake_popen)

    antwort = angemeldeter_client.post(
        "/auftraege/test-gmbh/20260101-000000/fortsetzen", follow_redirects=False)
    assert antwort.status_code == 303
    assert antwort.headers["location"] == "/auftraege/test-gmbh/20260101-000000"
    assert "--fortsetzen" in aufrufe[0]
    assert (lauf_dir / "pid").read_text(encoding="utf-8") == "777"


def test_fortsetzen_route_startet_nicht_doppelt_wenn_schon_laeuft(
        angemeldeter_client, daten_dir, monkeypatch):
    _fabriziere_laufordner(
        daten_dir, pid=999, meta={"kunde_datei": "kunden/test-kunde.yaml", "limit": 25})
    monkeypatch.setattr(laufmanager, "_pid_lebt", lambda pid: True)  # laeuft noch

    aufrufe = []
    monkeypatch.setattr(
        laufmanager.subprocess, "Popen",
        lambda *a, **k: (aufrufe.append(1), FakeProzess(1, True))[1])

    antwort = angemeldeter_client.post(
        "/auftraege/test-gmbh/20260101-000000/fortsetzen", follow_redirects=False)
    assert antwort.status_code == 303
    assert aufrufe == []  # kein zweiter Unterprozess


# Reviewer-Fixes Runde 2 -----------------------------------------------------
# (1) Regressionstest fuer den PYTHONPATH-Fix, (2) nicht-blockierende
# Start-/Fortsetzen-Routen, (3) Schritt-5-Anzeige nach Auftrags-Ende,
# (4) Server-seitige Limit-Allowlist.

def test_pythonpath_fix_laesst_echten_unterprozess_pipeline_importieren(tmp_path):
    """(1) Regressionstest fuer web.laufmanager._subprozess_umgebung(): KEIN
    subprocess.Popen-Fake hier - der Unterprozess laeuft wirklich, das ist
    der Sinn des Tests. daten_dir (tmp_path) liegt bewusst AUSSERHALB des
    Repos (wie im Deployment, siehe Plan Task 10), das pipeline-Package ist
    dort nicht auffindbar, wenn PYTHONPATH nicht um die Projekt-Wurzel
    ergaenzt wird.

    Statt eines echten 'lauf'-Aufrufs (bräuchte gueltige API-Keys/Netzwerk)
    ersetzt `befehl` die Pipeline-CLI durch ein Mini-Skript, das nur
    'import pipeline' probiert und eine Erkennungs-Zeile ausgibt - das legt
    keinen Laufordner an, darum landet starte() zuverlässig im "kein
    Laufordner entstanden"-Zweig und meldet die letzte Log-Zeile im
    Fehlertext. Diese letzte Zeile beweist, ob der Import geklappt hat.

    Manuell verifiziert (siehe Report): entfernt man `env=_subprozess_umgebung()`
    aus dem Popen-Aufruf in Laufmanager.starte() (z.B. durch `env=None`
    ersetzt), schlaegt dieser Test fehl, weil die letzte Log-Zeile dann
    'ModuleNotFoundError: No module named 'pipeline'' lautet statt der
    Erkennungs-Zeile."""
    daten_dir = tmp_path
    kunde_datei = _kunde_datei(daten_dir)

    manager = Laufmanager(
        daten_dir,
        befehl=[sys.executable, "-c",
                "import pipeline; print('PYTHONPATH-REGRESSION-OK')"])

    with pytest.raises(LaufmanagerFehler) as exc:
        manager.starte(kunde_datei, 10)

    assert "PYTHONPATH-REGRESSION-OK" in str(exc.value)
    assert "No module named" not in str(exc.value)


def test_start_und_fortsetzen_routen_sind_nicht_async(monkeypatch):
    """(2) manager.starte() pollt bis zu 10s lang SYNCHRON (siehe
    _warte_auf_lauf_dir); manager.setze_fort() spawnt ebenfalls synchron
    einen Unterprozess. Als `async def`-Routen wuerden sie den kompletten
    Event-Loop fuer ALLE gleichzeitigen Nutzer blockieren (worst case 10s
    pro Auftrags-Start). Als normale `def`-Funktionen fuehrt FastAPI sie
    stattdessen in einem Threadpool aus (Starlette-Verhalten fuer
    sync-Endpunkte) - der Event-Loop bleibt frei fuer andere Anfragen."""
    assert not inspect.iscoroutinefunction(auftraege_modul.auftrag_neu_starten)
    assert not inspect.iscoroutinefunction(auftraege_modul.auftrag_fortsetzen)


def test_weitere_blockierende_routen_sind_ebenfalls_nicht_async():
    """IMPORTANT Review-Fund: sechs weitere Routen sind `async def`, tun
    aber blockierende Netzwerkarbeit (Instantly ueber InstantlyLeser/KI ueber
    fetch_text+draft_offer) und wuerden damit den Event-Loop fuer ALLE
    gleichzeitigen Nutzer einfrieren - gleicher Grund/gleiche Loesung wie
    oben (plain `def` statt `async def`, FastAPI fuehrt sie im Threadpool
    aus)."""
    from web.routen import dashboard as dashboard_modul
    from web.routen import kampagnen as kampagnen_modul
    from web.routen import kunden as kunden_modul
    from web.routen import postfach as postfach_modul

    assert not inspect.iscoroutinefunction(dashboard_modul.dashboard)
    assert not inspect.iscoroutinefunction(kampagnen_modul.kampagnen_liste)
    assert not inspect.iscoroutinefunction(kampagnen_modul.kampagne_detail)
    assert not inspect.iscoroutinefunction(postfach_modul.postfach)
    assert not inspect.iscoroutinefunction(kunden_modul.kunde_neu_ableiten)
    assert not inspect.iscoroutinefunction(kunden_modul.kunde_bearbeiten_ableiten)


def test_status_schritt_fertig_ist_5_in_wartet_auf_freigabe(tmp_path, monkeypatch):
    """(3) Ein abgeschlossener Auftrag (alle Step-Dateien vorhanden, wartet
    nur noch auf die Pruefung) muss ALLE 5 Schritte als erledigt zeigen -
    nicht nur 4. schritt (das "aktuelle" 1-5) bleibt bei 5 haengen, sobald
    personalisierung.json existiert; die alte Vorlage zeigte darum fuer
    Schritt 5 selbst nie einen Haken (nr < schritt ist fuer nr=schritt=5
    nie wahr)."""
    lauf_dir = _fabriziere_laufordner(
        tmp_path, pid=123,
        leads={"leads": [{}], "ohne_email": 0},
        dedupe={"behalten": [{}], "verworfen": []},
        personalisierung={"fertig": [{}], "nacharbeit": []},
        pruefung_ok=[{"email": "a@b.de"}],
    )
    monkeypatch.setattr(laufmanager, "_pid_lebt", lambda pid: False)
    stand = Laufmanager(tmp_path).status(lauf_dir)
    assert stand["zustand"] == "wartet_auf_freigabe"
    assert stand["schritt_fertig"] == 5


@pytest.mark.parametrize("zustand_fixture", ["freigegeben", "uebergeben"])
def test_status_schritt_fertig_ist_5_nach_freigabe_und_uebergabe(
        tmp_path, monkeypatch, zustand_fixture):
    kwargs = {"pruefung_ok": [{"email": "a@b.de"}], "freigabe": True}
    if zustand_fixture == "uebergeben":
        kwargs["versand_komplett"] = {"campaign_id": "camp-1"}
    lauf_dir = _fabriziere_laufordner(
        tmp_path, pid=123,
        leads={"leads": [{}], "ohne_email": 0},
        dedupe={"behalten": [{}], "verworfen": []},
        personalisierung={"fertig": [{}], "nacharbeit": []},
        **kwargs,
    )
    monkeypatch.setattr(laufmanager, "_pid_lebt", lambda pid: False)
    stand = Laufmanager(tmp_path).status(lauf_dir)
    assert stand["zustand"] == zustand_fixture
    assert stand["schritt_fertig"] == 5


def test_fortschrittsseite_zeigt_fuenf_haken_wenn_wartet_auf_freigabe(
        angemeldeter_client, daten_dir, monkeypatch):
    _kunde_datei(daten_dir)
    _fabriziere_laufordner(
        daten_dir, pid=999,
        leads={"leads": [{}], "ohne_email": 0},
        dedupe={"behalten": [{}], "verworfen": []},
        personalisierung={"fertig": [{}], "nacharbeit": []},
        pruefung_ok=[{"email": "a@b.de"}],
        meta={"kunde_datei": "kunden/test-kunde.yaml", "limit": 25, "gestartet_am": "17.07.2026, 10:00"})
    monkeypatch.setattr(laufmanager, "_pid_lebt", lambda pid: False)

    antwort = angemeldeter_client.get("/auftraege/test-gmbh/20260101-000000")
    assert antwort.status_code == 200
    assert antwort.text.count("✓") == 5


def test_start_mit_ungueltigem_limit_zeigt_deutschen_fehler_und_startet_nichts(
        angemeldeter_client, daten_dir, monkeypatch):
    """(4) Server-seitige Allowlist: nur 25/40/60 sind gueltig. subprocess.Popen
    wird trotzdem gefaked (Sicherheitsnetz), damit dieser Test auch VOR dem
    Fix (der noch keine Validierung macht) keinen echten Unterprozess
    startet - er beweist die fehlende Validierung ueber den Statuscode/Text,
    nicht ueber einen Absturz."""
    _kunde_datei(daten_dir)
    aufrufe = []
    monkeypatch.setattr(
        laufmanager.subprocess, "Popen",
        lambda *a, **k: (aufrufe.append(1), FakeProzess(1, True))[1])

    antwort = angemeldeter_client.post(
        "/auftraege/neu", data={"kunde_dateiname": "test-kunde", "limit": "99"})

    assert antwort.status_code == 400
    assert "25" in antwort.text and "40" in antwort.text and "60" in antwort.text
    assert aufrufe == []  # kein Unterprozess gestartet


def test_start_mit_nicht_numerischem_limit_zeigt_deutschen_fehler(
        angemeldeter_client, daten_dir, monkeypatch):
    _kunde_datei(daten_dir)
    monkeypatch.setattr(
        laufmanager.subprocess, "Popen",
        lambda *a, **k: pytest.fail("Unterprozess haette nicht starten duerfen"))

    antwort = angemeldeter_client.post(
        "/auftraege/neu", data={"kunde_dateiname": "test-kunde", "limit": "abc"})

    assert antwort.status_code == 400


def test_start_mit_gueltigem_limit_funktioniert_weiterhin(
        angemeldeter_client, daten_dir, monkeypatch):
    _kunde_datei(daten_dir)

    def fake_popen(argv, cwd=None, stdout=None, stderr=None, env=None):
        (daten_dir / "laeufe" / "test-gmbh" / "20260101-000000").mkdir(parents=True)
        return FakeProzess(pid=555, laeuft=True)

    monkeypatch.setattr(laufmanager.subprocess, "Popen", fake_popen)

    antwort = angemeldeter_client.post(
        "/auftraege/neu", data={"kunde_dateiname": "test-kunde", "limit": "40"},
        follow_redirects=False)
    assert antwort.status_code == 303
