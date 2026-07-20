"""Tests fuer den Produktions-Einstiegspunkt web/main.py (IMPORTANT
Review-Fund: 'uvicorn web.main:app' brauchte bisher gar keinen
Einstiegspunkt). Liest DATEN_DIR aus der Umgebung und baut die App darueber
(web.app.create_app) - ohne DATEN_DIR muss der Import mit einer klaren
deutschen Fehlermeldung abbrechen statt mit einem kryptischen Fehler tief im
Code (gleiches Prinzip wie web.auth.hole_secret fuer WEB_SECRET)."""
from __future__ import annotations

import importlib
import sys

import pytest
from fastapi import FastAPI


def _frisch_importieren(monkeypatch):
    """web.main baut die App auf Modul-Ebene (beim Import) - fuer einen
    zweiten Test mit anderer Umgebung muss das Modul aus sys.modules
    entfernt werden, sonst liefert import_module nur das gecachte alte
    Modul und der Test prueft gar nichts Neues."""
    monkeypatch.delitem(sys.modules, "web.main", raising=False)
    return importlib.import_module("web.main")


def test_web_main_mit_daten_dir_baut_app(tmp_path, monkeypatch):
    monkeypatch.setenv("WEB_SECRET", "test-geheimnis-nur-fuer-tests")
    monkeypatch.setenv("DATEN_DIR", str(tmp_path))
    modul = _frisch_importieren(monkeypatch)
    assert isinstance(modul.app, FastAPI)


def test_web_main_ohne_daten_dir_bricht_klar_ab(monkeypatch):
    monkeypatch.delenv("DATEN_DIR", raising=False)
    with pytest.raises(RuntimeError, match="DATEN_DIR"):
        _frisch_importieren(monkeypatch)
