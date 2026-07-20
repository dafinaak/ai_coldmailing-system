"""Tests fuer web.wartende (Task 7, Reviewer-Fixes):

1. wartende_anzahl() muss "truly cheap" sein - reine Datei-Existenz-
   Pruefung je Laufordner, KEIN Laufmanager.status() (kein PID-Check via
   os.kill, kein JSON-Parsing). Bewiesen ueber einen Spy auf
   Laufmanager.status (0 Aufrufe) UND ueber einen fabrizierten Mix von
   Laufordnern (nur per Datei-Existenz gebaut, ohne echten Prozess/RunStore).
2. wartende_laeufe() bleibt unveraendert (volle Daten fuer die Routen, die
   sie brauchen) - ein Regressionstest sichert das ab.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient
from passlib.context import CryptContext

from web.app import create_app
from web.laufmanager import Laufmanager
from web.wartende import wartende_anzahl

PWD_CONTEXT = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _mini_lauf(daten_dir: Path, slug: str, ts: str, *, pruefung_ok=True,
               freigabe=False, abgelehnt=False, versand_komplett=False) -> Path:
    """Baut einen Laufordner NUR ueber die vier Marker-Dateien, die
    wartende_anzahl() prueft - bewusst OHNE RunStore/kunde_pfad.json (die
    braucht die schlanke Zaehlung nicht, siehe wartende_anzahl-Docstring)."""
    lauf_dir = daten_dir / "laeufe" / slug / ts
    lauf_dir.mkdir(parents=True)
    if pruefung_ok:
        (lauf_dir / "pruefung_ok.json").write_text("[]", encoding="utf-8")
    if freigabe:
        (lauf_dir / "FREIGABE.txt").write_text("Lena Hartmann", encoding="utf-8")
    if abgelehnt:
        (lauf_dir / "abgelehnt.json").write_text("{}", encoding="utf-8")
    if versand_komplett:
        (lauf_dir / "versand_komplett.json").write_text(
            '{"campaign_id": "camp-x"}', encoding="utf-8")
    return lauf_dir


# wartende_anzahl: Zaehl-Korrektheit ----------------------------------------

def test_wartende_anzahl_ohne_laeufe_ordner(tmp_path):
    assert wartende_anzahl(tmp_path) == 0


def test_wartende_anzahl_zaehlt_nur_echte_wartende(tmp_path):
    _mini_lauf(tmp_path, "demo", "1", pruefung_ok=True)  # wartend
    _mini_lauf(tmp_path, "demo", "2", pruefung_ok=True, freigabe=True)  # freigegeben
    _mini_lauf(tmp_path, "demo", "3", pruefung_ok=True, abgelehnt=True)  # abgelehnt
    _mini_lauf(tmp_path, "demo", "4", pruefung_ok=True, versand_komplett=True)  # uebergeben
    _mini_lauf(tmp_path, "demo", "5", pruefung_ok=False)  # angehalten/laeuft
    _mini_lauf(tmp_path, "moveo", "1", pruefung_ok=True)  # wartend (anderer Kunde)

    assert wartende_anzahl(tmp_path) == 2


def test_wartende_anzahl_ignoriert_dateien_im_kunden_ordner(tmp_path):
    # Eine Nicht-Ordner-Datei direkt unter laeufe/<slug>/ darf nicht crashen.
    (tmp_path / "laeufe" / "demo").mkdir(parents=True)
    (tmp_path / "laeufe" / "demo" / "irgendwas.txt").write_text("x", encoding="utf-8")
    assert wartende_anzahl(tmp_path) == 0


# wartende_anzahl: "truly cheap" - kein Laufmanager.status() ----------------

def test_wartende_anzahl_ruft_laufmanager_status_nicht_auf(tmp_path, monkeypatch):
    _mini_lauf(tmp_path, "demo", "1", pruefung_ok=True)
    _mini_lauf(tmp_path, "moveo", "2", pruefung_ok=True, freigabe=True)

    aufrufe = []
    original = Laufmanager.status

    def spy(self, lauf_dir):
        aufrufe.append(lauf_dir)
        return original(self, lauf_dir)

    monkeypatch.setattr(Laufmanager, "status", spy)

    anzahl = wartende_anzahl(tmp_path)

    assert anzahl == 1
    assert aufrufe == []


def test_badge_pfad_ueber_http_ruft_laufmanager_status_nicht_auf(tmp_path, monkeypatch):
    # End-to-End-Variante des Spy-Tests: eine Seite besuchen, deren eigene
    # Route-Logik status() NICHT braucht (Kunden-Liste) - jeder Aufruf, der
    # trotzdem ankommt, kann nur vom Sidebar-Badge (nav_kontext) kommen.
    monkeypatch.setenv("WEB_SECRET", "test-geheimnis-nur-fuer-tests")
    monkeypatch.setenv("WEB_COOKIE_SECURE", "0")
    nutzer = [{"name": "Lena Hartmann", "passwort_hash": PWD_CONTEXT.hash("richtig123")}]
    (tmp_path / "users.yaml").write_text(yaml.safe_dump(nutzer, allow_unicode=True), encoding="utf-8")
    (tmp_path / "kunden").mkdir()

    _mini_lauf(tmp_path, "demo", "1", pruefung_ok=True)
    # Bewusst OHNE versand_komplett hier: das wuerde eine campaign_id
    # ergeben, und das Dashboard (auf das der Login-Redirect zeigt) wuerde
    # dafuer einen echten InstantlyLeser bauen wollen (kein Fake gesetzt) -
    # fuer DIESEN Test zaehlt nur, dass /kunden selbst status() nicht ruft.
    _mini_lauf(tmp_path, "moveo", "2", pruefung_ok=True, freigabe=True)

    app = create_app(tmp_path)
    client = TestClient(app)
    # Anmeldung VOR dem Spy: der Redirect nach "/" (Dashboard) darf
    # Laufmanager.status() legitim aufrufen (Task 6/7-Aggregation dort) -
    # nur der eigentliche /kunden-Aufruf (dessen Route status() gar nicht
    # kennt) wird ueberwacht.
    client.post("/login", data={"name": "Lena Hartmann", "passwort": "richtig123"})

    aufrufe = []
    original = Laufmanager.status

    def spy(self, lauf_dir):
        aufrufe.append(lauf_dir)
        return original(self, lauf_dir)

    monkeypatch.setattr(Laufmanager, "status", spy)

    antwort = client.get("/kunden")

    assert antwort.status_code == 200
    assert "nav-badge" in antwort.text
    assert ">1<" in antwort.text
    assert aufrufe == []
