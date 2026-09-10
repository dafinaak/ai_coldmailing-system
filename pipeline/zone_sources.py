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

from pipeline.zonen import PLZ_ORDNER

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


def zone_source_report(zone, leadquellen_dir=PLZ_ORDNER) -> dict:
    """Count the companies of one zone per source, known and new apart."""
    zone = str(zone).strip()
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

    known = set()
    for folder in earlier:
        known.update(key for key in map(_kennung, _companies(folder)) if key)

    sources_of: dict = {}
    confirmed: dict = {}
    for folder in own:
        for company in _companies(folder):
            key = _kennung(company)
            if not key:
                continue
            tags = company.get("quellen") or [company.get("quelle") or "?"]
            sources_of.setdefault(key, set()).update(tags)
            # Maps records carry no flag: every one of them had a PLZ from
            # the zone list. Only OSM marks a firm it found without one.
            confirmed[key] = (confirmed.get(key, False)
                              or company.get("plz_bestaetigt", True) is not False)
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
