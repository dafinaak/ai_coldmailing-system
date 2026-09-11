"""Per-zone source report: which source brought which new companies.

Jira AP-215 (10.09.2026). Oliver's question is which source is worth its
money. For one zone this counts every company once - with the identity
rule of master.db, `(domain or name).lower()` - and says:

    which sources found it       maps, overpass, mailcom ...
    whether we had it before     from an older collection, or from a
                                 LOWER zone - the same order the final
                                 lists use (the lower zone keeps a person)

A company counts for the zone only if one of its zone records has a
postal code. OSM often has none, and its search box is the square of the
whole postal region (zone 35: 120 km radius instead of 48) - so without a
PLZ nothing proves the firm sits in the zone. Those are left out and
counted apart (Dafina, 10.09.2026; the same gate the final lists have).

Read-only: it opens the firmen.json files of the collection folders and
changes nothing.

    zone folders     laeufe/leadquellen/zona<NR>-*/firmen.json
    older ones       every other collection folder, e.g. plr-30-31

Gelbe Seiten folders are never counted: the source is out of the chain
since 04.09.2026 (AGENTS.md). Its data lives in gelbeseiten-arkiv/,
outside laeufe/; the name check here is a second brake, the same one
werkzeuge/zona32-export.py has.

Collections outside the zones count as "before". That is true for all of
them today (plr-30-31 from July, the Germany sample from 19.08.2026). A
collection made after a zone would make its overlap count as known too -
which still means "we had it from elsewhere", not "this source found it".
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from pipeline.dropcontact_register import person_key
from pipeline.guthaben import verbrauch
from pipeline.zonen import PLZ_ORDNER, PROJEKT

_ZONE_FOLDER = re.compile(r"^zona(\d+)-")


def _kennung(company: dict) -> str:
    # Same rule as master_db._kennung(): lowercase, nothing stripped.
    return (company.get("domain") or company.get("name") or "").lower()


def _companies(folder: Path) -> list:
    try:
        data = json.loads((folder / "firmen.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return data if isinstance(data, list) else []


def _collection_folders(leadquellen_dir) -> list:
    root = Path(leadquellen_dir)
    if not root.exists():
        return []
    return sorted(pfad.parent for pfad in root.glob("*/firmen.json")
                  if "gelbeseiten" not in pfad.parent.name)


def _zone_folders(zone: str, leadquellen_dir) -> tuple:
    """(the zone's own collection folders, the earlier ones)."""
    own, earlier = [], []
    for folder in _collection_folders(leadquellen_dir):
        match = _ZONE_FOLDER.match(folder.name)
        if match is None:
            earlier.append(folder)
        elif match.group(1) == zone:
            own.append(folder)
        elif int(match.group(1)) < int(zone):
            earlier.append(folder)
    if not own:
        # A silent zero would read like "the sources found nothing".
        raise ValueError(
            f"Zone {zone}: no collection folder zona{zone}-* with a "
            f"firmen.json in {leadquellen_dir}")
    return own, earlier


def _confirmed(own: list) -> dict:
    """kennung -> True when one of the zone's records gives it a PLZ."""
    confirmed: dict = {}
    for folder in own:
        for company in _companies(folder):
            key = _kennung(company)
            if key:
                # Maps records carry no flag: every one of them had a PLZ
                # from the zone list. Only OSM marks a firm without one.
                confirmed[key] = (confirmed.get(key, False)
                                  or company.get("plz_bestaetigt", True)
                                  is not False)
    return confirmed


def zone_source_report(zone, leadquellen_dir=PLZ_ORDNER) -> dict:
    """Count the companies of one zone per source, known and new apart."""
    zone = str(zone).strip()
    own, earlier = _zone_folders(zone, leadquellen_dir)

    known = set()
    for folder in earlier:
        known.update(key for key in map(_kennung, _companies(folder)) if key)

    sources_of: dict = {}
    for folder in own:
        for company in _companies(folder):
            key = _kennung(company)
            if not key:
                continue
            tags = company.get("quellen") or [company.get("quelle") or "?"]
            sources_of.setdefault(key, set()).update(tags)
    confirmed = _confirmed(own)
    left_out = sum(1 for key in sources_of if not confirmed[key])
    sources_of = {key: tags for key, tags in sources_of.items()
                  if confirmed[key]}

    per_source: dict = {}
    known_before = new_from_several = 0
    for key, tags in sources_of.items():
        is_new = key not in known
        known_before += not is_new
        for tag in tags:
            counts = per_source.setdefault(tag, {
                "found": 0, "only_this_source": 0, "new_only_this_source": 0})
            counts["found"] += 1
            if len(tags) == 1:
                counts["only_this_source"] += 1
                counts["new_only_this_source"] += is_new
        new_from_several += is_new and len(tags) > 1

    return {
        "zone": zone,
        "folders": [folder.name for folder in own],
        "companies": len(sources_of),
        "known_before": known_before,
        "new": len(sources_of) - known_before,
        "left_out_no_postal_code": left_out,
        "sources": dict(sorted(per_source.items())),
        "new_from_several_sources": new_from_several,
    }


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def zone_enrichment_report(zone, leadquellen_dir=PLZ_ORDNER,
                           daten_dir=None) -> dict:
    """From the companies of one zone down to the e-mails, with the cost.

    Jira AP-216. Until 10.09.2026 these numbers were counted by hand.

        companies            proven in the zone - same count as the
                             source report
        eligible             IT profile fits, automation check said "no"
        with_decision_maker  eligible, with a named person and a website:
                             the ones the Dropcontact step may ask about
        asked                people sent in the zone's paid Dropcontact runs
        emails_found         addresses Dropcontact built in those runs
        reused_free          addresses taken over from the register, not paid
        ai_cost_usd          every AI call of the zone (kosten.json) - also
                             for firms that fell out later: it was spent
        credits              what the paid runs cost, from the balance before
                             and after each one (pipeline.guthaben.verbrauch);
                             None when no run's cost is known
        credit_runs_unknown  paid runs whose cost cannot be told - every run
                             from before 10.09.2026, when no balance was kept
    """
    zone = str(zone).strip()
    own, _ = _zone_folders(zone, leadquellen_dir)
    confirmed = _confirmed(own)

    # The same merge as werkzeuge/zona32-dropcontact.py: an empty field is
    # filled from the next source, a filled one is never overwritten.
    merged: dict = {}
    for folder in own:
        for company in _companies(folder):
            key = _kennung(company)
            if not key or not confirmed.get(key):
                continue
            if key not in merged:
                merged[key] = dict(company)
                continue
            for field, value in company.items():
                if not merged[key].get(field) and value:
                    merged[key][field] = value

    eligible = [c for c in merged.values() if c.get("profil_passt")
                and c.get("offers_automation_services") == "no"]
    with_decision_maker = [
        c for c in eligible
        if c.get("website") and (c.get("entscheider") or [{}])[0].get("vorname")
        and (c.get("entscheider") or [{}])[0].get("nachname")]

    ai_cost = sum(float((_read_json(folder / "kosten.json") or {})
                        .get("kosten_usd") or 0) for folder in own)

    asked, paid, reused, known_cost, unknown = 0, set(), set(), [], 0
    for run in sorted(Path(leadquellen_dir).glob(f"zona{zone}-dropcontact-*")):
        request = _read_json(run / "request-id.json")
        if isinstance(request, dict):
            asked += len(request.get("gesendet_nr") or [])
            cost = verbrauch(request.get("request_id"),
                             daten_dir or PROJEKT)
            if cost is None:
                unknown += 1
            else:
                known_cost.append(cost)
        for company in _read_json(run / "ergebnisse.json") or []:
            for lead in company.get("leads") or []:
                if lead.get("email"):
                    key = person_key(lead.get("first_name"),
                                     lead.get("last_name"),
                                     company.get("website"))
                    (reused if company.get("wiederverwendet_aus")
                     else paid).add(key)

    return {
        "zone": zone,
        "companies": sum(1 for ok in confirmed.values() if ok),
        "eligible": len(eligible),
        "with_decision_maker": len(with_decision_maker),
        "asked": asked,
        "emails_found": len(paid),
        "reused_free": len(reused - paid),
        "ai_cost_usd": round(ai_cost, 4),
        "credits": sum(known_cost) if known_cost or not unknown else None,
        "credit_runs_unknown": unknown,
    }


def format_enrichment(report: dict) -> str:
    """The enrichment lines of one zone, for the terminal."""
    if report["credits"] is None:
        credits = "not recorded"
    else:
        credits = str(report["credits"])
        if report["credit_runs_unknown"]:
            credits += (f" (+ {report['credit_runs_unknown']} runs not "
                        f"recorded)")
    lines = [
        f"  enrichment: {report['eligible']} of {report['companies']} "
        f"eligible, {report['with_decision_maker']} with a named decision "
        f"maker, {report['asked']} asked at Dropcontact, "
        f"{report['emails_found']} e-mails paid for, "
        f"{report['reused_free']} reused free",
        f"  cost: AI ${report['ai_cost_usd']:.2f}, Dropcontact credits: "
        f"{credits}",
    ]
    emails = report["emails_found"] + report["reused_free"]
    if emails:
        line = f"  per e-mail: AI ${report['ai_cost_usd'] / emails:.3f}"
        if (report["credits"] is not None and not report["credit_runs_unknown"]
                and report["emails_found"]):
            line += (f", {report['credits'] / report['emails_found']:.1f} "
                     f"credits per paid e-mail")
        lines.append(line)
    return "\n".join(lines)


def format_report(report: dict) -> str:
    """The report as a few plain lines for the terminal."""
    lines = [f"Zone {report['zone']}: {report['companies']} companies - "
             f"{report['new']} new, {report['known_before']} known before"]
    for source, counts in report["sources"].items():
        lines.append(
            f"  {source:<10} found {counts['found']:>4}   "
            f"only this source {counts['only_this_source']:>4}   "
            f"of those new {counts['new_only_this_source']:>4}")
    lines.append(f"  new, found by several sources: "
                 f"{report['new_from_several_sources']}")
    lines.append(f"  left out - no postal code, so not proven in the zone: "
                 f"{report['left_out_no_postal_code']}")
    return "\n".join(lines)
