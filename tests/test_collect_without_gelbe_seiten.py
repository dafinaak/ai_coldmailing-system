"""Gelbe Seiten is out of the collection chain (Dafina, 04.09.2026).

The zone tool dropped it on 04.09.2026, but `python -m pipeline sammeln` -
the command step 3 of the form starts - still asked Gelbe Seiten and paid
Apify for it. These tests run that command with fake sources: no network,
no money. A company that only Gelbe Seiten knows must not show up.
"""
import json

import pytest


def _company(domain, source):
    return {"name": f"Firma {domain}", "website": f"https://{domain}",
            "domain": domain, "plz": "10115", "ort": "Berlin",
            "categories": ["IT-Service"], "quelle": source}


class FakeMaps:
    def __init__(self, api_key):
        pass

    def search_gebiet(self, suchbegriffe, gebiet_geojson, limit_pro_suche,
                      schlaf=None):
        return [_company("maps-firma.de", "maps")]


class FakeOverpass:
    def search(self, praefixe, bbox):
        return [_company("osm-firma.de", "overpass")]


class FakeGelbeSeiten:
    """Stands in for the paid Apify actor and remembers every query."""

    queries = []

    def __init__(self, api_key):
        pass

    def search(self, begriff, ort, seiten=1):
        FakeGelbeSeiten.queries.append((begriff, ort))
        return [_company("gs-firma.de", "gelbe_seiten")]


@pytest.fixture
def project(monkeypatch, tmp_path):
    FakeGelbeSeiten.queries = []
    monkeypatch.setattr("pipeline.sources.apify_maps.ApifyMapsSource",
                        FakeMaps)
    monkeypatch.setattr("pipeline.sources.overpass.OverpassQuelle",
                        FakeOverpass)
    monkeypatch.setattr("pipeline.sources.gelbe_seiten.GelbeSeitenQuelle",
                        FakeGelbeSeiten)
    monkeypatch.setenv("APIFY_API_KEY", "test-key")
    # The command saves into ./laeufe/leadquellen/ of the working folder.
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _collect(project, mode):
    from pipeline.__main__ import sammeln_cli

    if mode == "radius":
        sammeln_cli("Berlin", 10, ["IT-Service"], 50, ordner="t")
    elif mode == "target":
        sammeln_cli("Berlin", 10, ["IT-Service"], 50, ordner="t",
                    ziel_anzahl=5)
    else:
        plz_file = project / "plz.txt"
        plz_file.write_text("10115\n", encoding="utf-8")
        sammeln_cli("", 10, ["IT-Service"], 50, ordner="t",
                    plz_liste_datei=str(plz_file))
    saved = project / "laeufe" / "leadquellen" / "t" / "firmen.json"
    return sorted(f["domain"]
                  for f in json.loads(saved.read_text(encoding="utf-8")))


@pytest.mark.parametrize("mode", ["radius", "target", "plz_list"])
def test_collection_asks_maps_and_osm_but_never_gelbe_seiten(project, mode):
    domains = _collect(project, mode)

    assert domains == ["maps-firma.de", "osm-firma.de"]
    assert FakeGelbeSeiten.queries == []
