"""Der Haupt-Einstieg muss die Impressum-Stufe koennen.

Gefunden im echten Probelauf am 12.08.2026: `python -m pipeline lauf`
reichte den KI-Baustein nie durch, also brach jeder Kunde mit
"impressum" in der anbieter_reihenfolge sofort ab - und genau diese
Stufe ist seit dem Prospeo-Aus unsere Hauptstufe. Der Fehler blieb so
lange unbemerkt, weil die grossen Laeufe ueber pipeline.grosslauf
liefen, nicht ueber diesen Einstieg.
"""
import json
from types import SimpleNamespace

import pytest
import yaml


KUNDE = {
    "name": "Impressum Kunde",
    "zielgruppe": {"titel": ["Geschäftsführer"], "region": ["Hannover"],
                   "firmengroesse": ["alle"]},
    "angebot": "Wir betreuen IT.",
    "tonalitaet": "ruhig",
    "absender": "ich@firma.de",
    "follow_up_tage": [7, 14],
    "test_empfaenger": ["ich@firma.de"],
    "maps_suche": "(Liste)",
    "kontakt_rollen": ["Geschäftsführer"],
    "anbieter_reihenfolge": ["impressum"],
}


@pytest.fixture
def umgebung(tmp_path, monkeypatch):
    for schluessel in ("HUNTER_API_KEY", "DROPCONTACT_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.setenv(schluessel, "test")
    monkeypatch.delenv("APIFY_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "kunden").mkdir()
    (tmp_path / "kunden" / "k.yaml").write_text(
        yaml.safe_dump(KUNDE, allow_unicode=True), encoding="utf-8")
    (tmp_path / "firmen.json").write_text(json.dumps(
        [{"name": "A GmbH", "domain": "a.de", "website": "https://a.de"}]),
        encoding="utf-8")
    return tmp_path


def test_impressum_stufe_bekommt_den_ki_baustein(umgebung, monkeypatch):
    gesehen = {}

    def fake_source_leads(kunde, limit, apify, hunter, dropcontact, **zusatz):
        gesehen.update(zusatz)
        return [], {"firmen_gesamt": 0, "firmen_mit_kontakt": 0,
                    "quote_prozent": 0.0}, []

    monkeypatch.setattr("pipeline.__main__.source_leads", fake_source_leads)
    monkeypatch.setattr("pipeline.__main__.KI", lambda *a, **k: SimpleNamespace())
    from pipeline.__main__ import lauf

    lauf("kunden/k.yaml", 1, None, None, firmen_datei="firmen.json")

    assert "impressum_quelle" in gesehen, (
        "Ohne impressum_quelle bricht die Kaskade sofort ab.")
    assert "apify_source" in gesehen        # feste Liste statt Suche


def test_ohne_impressum_stufe_wird_keine_ki_gebraucht(umgebung, monkeypatch):
    (umgebung / "kunden" / "k.yaml").write_text(yaml.safe_dump(
        {**KUNDE, "anbieter_reihenfolge": ["hunter_dropcontact"]},
        allow_unicode=True), encoding="utf-8")
    gesehen = {}

    def fake_source_leads(kunde, limit, apify, hunter, dropcontact, **zusatz):
        gesehen.update(zusatz)
        return [], {"firmen_gesamt": 0, "firmen_mit_kontakt": 0,
                    "quote_prozent": 0.0}, []

    monkeypatch.setattr("pipeline.__main__.source_leads", fake_source_leads)
    from pipeline.__main__ import lauf

    lauf("kunden/k.yaml", 1, None, None, firmen_datei="firmen.json")

    assert "impressum_quelle" not in gesehen


def test_feste_firmenliste_braucht_keinen_apify_schluessel(umgebung, monkeypatch):
    # Ohne Suchstufe darf ein fehlender APIFY_API_KEY den Lauf nicht
    # aufhalten - sonst blockiert ein ungenutzter Schluessel den Assistenten.
    monkeypatch.setattr(
        "pipeline.__main__.source_leads",
        lambda *a, **k: ([], {"firmen_gesamt": 0, "firmen_mit_kontakt": 0,
                              "quote_prozent": 0.0}, []))
    monkeypatch.setattr("pipeline.__main__.KI", lambda *a, **k: SimpleNamespace())
    from pipeline.__main__ import lauf

    lauf("kunden/k.yaml", 1, None, None, firmen_datei="firmen.json")
