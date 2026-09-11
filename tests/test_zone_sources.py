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

from pipeline.zone_sources import zone_enrichment_report, zone_source_report


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


# --- Enrichment per zone (Jira AP-216) -----------------------------------
# From the companies of a zone down to the e-mails, with what it cost.
# Until 10.09.2026 these numbers were counted by hand.


def _firm(domain, profile=True, automation="no", manager=None, plz="33602",
          confirmed=True):
    return {"name": domain, "domain": domain, "website": f"https://{domain}",
            "plz": plz, "plz_bestaetigt": confirmed, "profil_passt": profile,
            "offers_automation_services": automation,
            "entscheider": ([{"vorname": manager[0], "nachname": manager[1]}]
                            if manager else []),
            "quelle": "maps", "quellen": ["maps"]}


@pytest.fixture
def enrichment(tmp_path):
    root = tmp_path / "leadquellen"
    _folder(root, "zona33-bielefeld-2026-08-25", [
        _firm("a.de", manager=("Anna", "Alt")),
        _firm("b.de"),                                    # nobody named
        _firm("c.de", profile=False, manager=("Carl", "Chef")),
        _firm("d.de", automation="yes", manager=("Dora", "Dach")),
        _firm("f.de", manager=("Fritz", "Form"))])
    (root / "zona33-bielefeld-2026-08-25" / "kosten.json").write_text(
        json.dumps({"kosten_usd": 0.30}), encoding="utf-8")
    # OSM, no postal code: not part of the zone, so not counted anywhere.
    _folder(root, "zona33-overpass-2026-09-03", [
        _firm("e.de", plz="", confirmed=False, manager=("Emil", "Eck"))])
    (root / "zona33-overpass-2026-09-03" / "kosten.json").write_text(
        json.dumps({"kosten_usd": 0.20}), encoding="utf-8")
    # A paid batch: two people asked, Anna found.
    paid = root / "zona33-dropcontact-2026-08-28"
    paid.mkdir()
    (paid / "request-id.json").write_text(json.dumps(
        {"request_id": "r1", "gesendet_nr": [0, 1]}), encoding="utf-8")
    (paid / "ergebnisse.json").write_text(json.dumps([
        {"website": "https://a.de", "leads": [
            {"first_name": "Anna", "last_name": "Alt", "email": "anna@a.de"}]}]),
        encoding="utf-8")
    # A later run that only took an address over from the register.
    reused = root / "zona33-dropcontact-2026-09-10"
    reused.mkdir()
    (reused / "ergebnisse.json").write_text(json.dumps([
        {"website": "https://f.de",
         "wiederverwendet_aus": {"lauf": "zona34-dropcontact-2026-08-28",
                                 "datum": "2026-08-28"},
         "leads": [{"first_name": "Fritz", "last_name": "Form",
                    "email": "fritz@f.de"}]}]), encoding="utf-8")
    return root


def _credit_history(daten_dir, *entries):
    from pipeline.guthaben import merken
    for request_id, credits_left in entries:
        merken(credits_left, daten_dir, request_id=request_id)


def test_enrichment_funnel_of_a_zone(enrichment, tmp_path):
    report = zone_enrichment_report("33", enrichment, daten_dir=tmp_path)

    # a, b, c, d, f - the OSM firm without a postal code is not in it.
    assert report["companies"] == 5
    # c fails the IT profile, d offers automation.
    assert report["eligible"] == 3
    assert report["with_decision_maker"] == 2        # a and f
    assert report["asked"] == 2
    assert report["emails_found"] == 1               # Anna, paid for
    assert report["reused_free"] == 1                # Fritz, from the register
    # Every AI call of the zone counts - also for firms that fell out
    # later: the money was spent.
    assert report["ai_cost_usd"] == pytest.approx(0.50)


def test_credits_come_from_the_balance_before_and_after(enrichment, tmp_path):
    _credit_history(tmp_path, ("r1", 391), ("r9", 380))

    report = zone_enrichment_report("33", enrichment, daten_dir=tmp_path)

    assert report["credits"] == 11
    assert report["credit_runs_unknown"] == 0


def test_runs_before_the_balance_was_kept_say_so(enrichment, tmp_path):
    report = zone_enrichment_report("33", enrichment, daten_dir=tmp_path)

    assert report["credits"] is None
    assert report["credit_runs_unknown"] == 1
