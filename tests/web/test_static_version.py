"""Cache-Busting fuer das Stylesheet (Fund 30.07.2026).

Anlass: Nach einem Deployment lieferte Cloudflare das ALTE stil.css noch
Stunden weiter aus (cf-cache-status HIT, max-age 14400) - im Browser
sahen Layout-Fixes deshalb nach "nichts geaendert" aus, obwohl Server
und Container die neue Datei hatten. Loesung: Die Stylesheet-Adresse
traegt eine Versions-Kennung, die sich mit dem Datei-Inhalt aendert.
"""
from __future__ import annotations

import re

import pytest
import yaml
from fastapi.testclient import TestClient
from passlib.context import CryptContext

from web.app import create_app, stil_version

PWD_CONTEXT = CryptContext(schemes=["bcrypt"], deprecated="auto")


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("WEB_SECRET", "test-geheimnis-nur-fuer-tests")
    monkeypatch.setenv("WEB_COOKIE_SECURE", "0")
    nutzer = [{"name": "Lena Hartmann",
               "passwort_hash": PWD_CONTEXT.hash("richtig123")}]
    (tmp_path / "users.yaml").write_text(
        yaml.safe_dump(nutzer, allow_unicode=True), encoding="utf-8")
    return TestClient(create_app(tmp_path))


def test_stylesheet_adresse_traegt_eine_versions_kennung(client):
    antwort = client.get("/login")
    treffer = re.search(r'stil\.css\?v=([0-9a-f]{6,})', antwort.text)
    assert treffer, "Stylesheet-Adresse ohne ?v=... - Cloudflare würde alt ausliefern"


def test_version_ist_stabil_und_haengt_am_inhalt():
    eine = stil_version()
    assert eine == stil_version()          # gleicher Inhalt -> gleiche Kennung
    assert re.fullmatch(r"[0-9a-f]{6,}", eine)


def test_version_aendert_sich_wenn_das_stylesheet_sich_aendert(tmp_path):
    datei = tmp_path / "stil.css"
    datei.write_text("a { color: red }", encoding="utf-8")
    vorher = stil_version(datei)
    datei.write_text("a { color: blue }", encoding="utf-8")
    assert stil_version(datei) != vorher


def test_fehlende_datei_liefert_eine_kennung_statt_abzustuerzen(tmp_path):
    assert stil_version(tmp_path / "gibt-es-nicht.css")
