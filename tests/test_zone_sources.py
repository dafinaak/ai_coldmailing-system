"""Per-zone source report (Jira AP-215, 10.09.2026).

Oliver's question: which source brought which new companies? For one
zone the report counts every company once (same kennung rule as
master.db), says which sources found it, and whether we already had it
before the zone - from an older collection or from a lower zone. That is
the same order the final lists use: the lower zone keeps a person.

The folder tree below is small and built by hand, so every expected
number can be checked by eye.
"""
import json

import pytest

from pipeline.zone_sources import zone_source_report


def _company(name, domain, source, plz_confirmed=True):
    return {"name": name, "domain": domain, "plz": "33602",
            "quelle": source, "quellen": [source],
            "plz_bestaetigt": plz_confirmed}


def _folder(root, name, companies):
    folder = root / name
    folder.mkdir(parents=True)
    (folder / "firmen.json").write_text(json.dumps(companies),
                                        encoding="utf-8")


@pytest.fixture
def leadquellen(tmp_path):
    root = tmp_path / "leadquellen"
    # An older collection from before the zones.
    _folder(root, "plr-30-31", [_company("Alt GmbH", "a.de", "maps")])
    # A lower zone, collected before zone 33.
    _folder(root, "zona32-herford-2026-08-21", [
        _company("B GmbH", "b.de", "maps"),
        _company("C GmbH", "c.de", "maps")])
    # Zone 33 itself: Maps ...
    _folder(root, "zona33-bielefeld-2026-08-25", [
        _company("Alt GmbH", "A.de", "maps"),     # same firm as a.de
        _company("B GmbH", "b.de", "maps"),
        _company("D GmbH", "d.de", "maps"),
        _company("D GmbH", "d.de", "maps"),       # twice in one source
        _company("E GmbH", "e.de", "maps")])
    # ... and OpenStreetMap. OSM often has no postal code: then nothing
    # proves the firm sits in the zone (Dafina, 10.09.2026: left out).
    _folder(root, "zona33-overpass-2026-09-03", [
        _company("B GmbH", "b.de", "overpass"),   # known, two sources
        _company("D GmbH", "d.de", "overpass", plz_confirmed=False),
        _company("F GmbH", "f.de", "overpass"),
        _company("Ohne Webseite", "", "overpass", plz_confirmed=False)])
    # Gelbe Seiten is out of the chain since 04.09.2026 - never counted.
    _folder(root, "zona33-gelbeseiten-2026-09-03",
            [_company("H GmbH", "h.de", "gelbe_seiten")])
    # A higher zone does not make a zone-33 firm "known before".
    _folder(root, "zona34-kassel-2026-08-28",
            [_company("E GmbH", "e.de", "maps")])
    # Dropcontact folders hold e-mail results, not collected firms.
    (root / "zona33-dropcontact-2026-08-28").mkdir()
    (root / "zona33-dropcontact-2026-08-28" / "ergebnisse.json").write_text(
        "[]", encoding="utf-8")
    return root


def test_counts_each_company_once_and_splits_known_from_new(leadquellen):
    report = zone_source_report("33", leadquellen)

    assert report["folders"] == ["zona33-bielefeld-2026-08-25",
                                 "zona33-overpass-2026-09-03"]
    # a, b, d, e, f - the firm without a postal code is not one of them.
    assert report["companies"] == 5
    # a.de from the older collection, b.de from zone 32.
    assert report["known_before"] == 2
    assert report["new"] == 3


def test_says_what_each_source_found_alone_and_new(leadquellen):
    report = zone_source_report("33", leadquellen)

    assert report["sources"] == {
        # found a, b, d, e - alone a, e - new and alone only e
        "maps": {"found": 4, "only_this_source": 2,
                 "new_only_this_source": 1},
        # found b, d, f - alone f, and f is new
        "overpass": {"found": 3, "only_this_source": 1,
                     "new_only_this_source": 1},
    }
    # b.de and d.de were found by both sources; only d.de is new.
    assert report["new_from_several_sources"] == 1


def test_leaves_out_firms_without_a_postal_code_and_counts_them(leadquellen):
    # d.de has no PLZ in OSM, but Maps confirms it, so it stays. The firm
    # without a website has no postal code anywhere in the zone.
    report = zone_source_report("33", leadquellen)

    assert report["left_out_no_postal_code"] == 1


def test_a_zone_without_collection_folders_is_an_error(leadquellen):
    # A silent zero would read like "the sources found nothing".
    with pytest.raises(ValueError):
        zone_source_report("40", leadquellen)
