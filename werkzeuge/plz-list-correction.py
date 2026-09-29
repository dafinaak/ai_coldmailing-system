#!/usr/bin/env python3
"""Correct the postal code list for zones 40-69 (Dafina, 29.09.2026).

The list that came on 23.09.2026 (daten/plz-liste-oliver-40-69.csv) has
2,096 codes for 35 cities, but most of them do not exist: the ranges were
filled in number by number (Koeln 50667-50998, while Koeln has about 45
codes). A code that does not exist costs nothing - no company sits on it.
The damage is the other way round: real codes of the same cities are
missing (Wuppertal-Vohwinkel, Koeln-Porz, Frankfurt-Hoechst ...), and the
zone rule (AGENTS.md, 10.09.2026) keeps a company out of its zone when
its code is not on the list - silently.

What this does:
  1. Reads the postal code areas from OpenStreetMap (Overpass, free).
     These are delivery areas only - codes with street addresses. The
     answer is kept in daten/osm-postal-codes-40-69.json, so the
     correction can be repeated without the network (--offline).
  2. For every city on the list: the OSM codes carrying the city's name,
     no further than MAX_KM from the city's centre - Germany has several
     Muensters, Langenfelds and Monheims.
  3. Keeps every listed code that exists (in OSM, or in GeoNames for PO
     box and large-customer codes), adds the missing delivery codes, and
     drops only the codes that exist nowhere.

A code of one single company (the Frankfurter Sparkasse has its own) is
not added: no IT service firm sits on it. It is printed, not hidden.

The original list is never touched. Output:
daten/plz-liste-oliver-40-69-corrected.csv - the same three columns plus
"Hinweis" (empty = unchanged, "neu" = was missing, "Sonder-PLZ" = exists,
but as a PO box or large-customer code).

Usage:
    .venv/bin/python werkzeuge/plz-list-correction.py            ask OSM, then correct
    .venv/bin/python werkzeuge/plz-list-correction.py --offline  use the saved OSM answer
    .venv/bin/python werkzeuge/plz-list-correction.py --overpass-json=answer.json
        use a raw Overpass answer fetched some other way - both free servers
        answer 504 when they are busy (29.07. and 29.09.2026)

Nothing is paid, nothing is sent. Instantly is not touched.
"""
import csv
import json
import math
import re
import sys
import unicodedata
from collections import OrderedDict
from pathlib import Path

import requests

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from pipeline.plz_geo import plz_tabelle  # noqa: E402
from pipeline.sources.overpass import KENNUNG, OVERPASS_MIRRORS  # noqa: E402

ORIGINAL = PROJECT / "daten" / "plz-liste-oliver-40-69.csv"
CORRECTED = PROJECT / "daten" / "plz-liste-oliver-40-69-corrected.csv"
OSM_CACHE = PROJECT / "daten" / "osm-postal-codes-40-69.json"

# A city's own codes lie within ~15 km of its centre (Koeln, the widest,
# reaches 13 km). 30 km keeps all of them and still shuts out the
# namesakes, which are hundreds of kilometres away.
MAX_KM = 30

NOTE_NEW = "neu"
NOTE_SPECIAL = "Sonder-PLZ (Postfach/Großkunde)"


def nfc(text) -> str:
    return unicodedata.normalize("NFC", text or "").strip()


def distance_km(a, b) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = (math.sin((lat2 - lat1) / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2)
    return 2 * 6371.0 * math.asin(math.sqrt(h))


def town_of(note: str) -> str:
    """'44149 Dortmund, Stadtteile Dorstfeld ...' -> 'Dortmund, Stadtteile ...'"""
    return re.sub(r"^\d{5}\s*", "", nfc(note))


def names_city(town: str, city: str) -> bool:
    """True when a place name belongs to the city of the list.

    The list writes "Ludwigshafen", OSM "Ludwigshafen am Rhein"; OSM
    writes districts as "Mainz-Kastel" or "Dortmund, Stadtteile ...".
    A bare prefix is not enough: "Essenbach" is not Essen, and
    "Frankfurter Sparkasse" is not Frankfurt."""
    base = city.split(" am ")[0]
    return town == base or any(town.startswith(base + sep)
                               for sep in (" ", ",", "(", "-"))


def read_original() -> "OrderedDict[str, dict]":
    """{city: {"land": ..., "codes": [...]}} in the order of the list."""
    cities = OrderedDict()
    with ORIGINAL.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            code = row["Postleitzahl"].strip()
            if not (len(code) == 5 and code.isdigit()):
                raise ValueError(f"{ORIGINAL.name}: {code!r} is not a postal code")
            city = nfc(row["Stadt/Ort"])
            entry = cities.setdefault(city, {"land": nfc(row["Bundesland"]),
                                             "codes": []})
            entry["codes"].append(code)
    return cities


def osm_query(prefixes) -> str:
    """Every postal code area in Germany whose code starts with one of the
    prefixes - tags only, no shapes, so the answer stays small."""
    return ('[out:json][timeout:180];'
            'area["ISO3166-1"="DE"][admin_level=2]->.de;'
            'relation(area.de)["boundary"="postal_code"]'
            f'["postal_code"~"^({"|".join(sorted(prefixes))})"];'
            'out tags;')


def fetch_osm(prefixes) -> list:
    query = osm_query(prefixes)
    last_error = None
    for url in OVERPASS_MIRRORS:
        try:
            answer = requests.post(url, data={"data": query}, headers=KENNUNG,
                                   timeout=240)
            answer.raise_for_status()
            return areas_of(answer.json()["elements"])
        except (requests.RequestException, ValueError, KeyError) as error:
            last_error = error
            print(f"  {url} failed ({error}) - trying the next one")
    raise SystemExit(f"No Overpass server answered: {last_error}\n"
                     f"The query, to fetch it some other way:\n{query}")


def areas_of(elements) -> list:
    areas = [{"postal_code": e["tags"]["postal_code"].strip(),
              "note": nfc(e["tags"].get("note")),
              "name": nfc(e["tags"].get("name"))}
             for e in elements if e.get("tags", {}).get("postal_code")]
    return sorted(areas, key=lambda a: (a["postal_code"], a["note"], a["name"]))


def osm_towns(areas):
    """({code: {town, ...}}, {code: {town, ...}}) - every name a code
    carries (note and name tag), and the note alone, OSM's main label."""
    towns, note_towns = {}, {}
    for area in areas:
        code = area["postal_code"]
        for text in (area["note"], area["name"]):
            if text:
                towns.setdefault(code, set()).add(town_of(text))
        if area["note"]:
            note_towns.setdefault(code, set()).add(town_of(area["note"]))
    return towns, note_towns


def correct(cities, towns, note_towns, geo):
    """Returns (rows, report). rows: [(code, city, land, note)]."""
    all_listed = {c for entry in cities.values() for c in entry["codes"]}

    # First every city's candidates, then one owner per code: 55246 is
    # "Wiesbaden" in the OSM note and "Mainz-Kostheim" in the name, so it
    # would land in both cities. The note decides, then the nearer centre.
    centres, candidates = {}, {}
    for city, entry in cities.items():
        listed = entry["codes"]
        own = [geo[c] for c in listed if c in geo and names_city(nfc(geo[c]["ort"]), city)]
        if not own:
            own = [geo[c] for c in listed if c in geo]
        centre = (sum(g["lat"] for g in own) / len(own),
                  sum(g["lon"] for g in own) / len(own))
        centres[city] = centre
        prefixes = {c[:2] for c in listed}
        found = set()
        for code, names in towns.items():
            if not any(names_city(t, city) for t in names):
                continue
            if code in geo:
                if distance_km(centre, (geo[code]["lat"], geo[code]["lon"])) > MAX_KM:
                    continue                     # a namesake far away
            elif code[:2] not in prefixes:
                continue                         # no position to check - stay safe
            found.add(code)
        candidates[city] = found

    owners = {}
    for city, found in candidates.items():
        for code in found:
            owners.setdefault(code, []).append(city)
    for code, claimed in owners.items():
        if len(claimed) > 1:
            by_note = [c for c in claimed
                       if any(names_city(t, c) for t in note_towns.get(code, ()))]
            if len(by_note) == 1:
                winner = by_note[0]
            else:
                point = (geo[code]["lat"], geo[code]["lon"])
                winner = min(claimed, key=lambda c: distance_km(centres[c], point))
            for city in claimed:
                if city != winner:
                    candidates[city].discard(code)

    rows, report = [], OrderedDict()
    for city, entry in cities.items():
        listed = entry["codes"]
        kept = [c for c in listed if c in towns]
        special = [c for c in listed if c not in towns and c in geo]
        dropped = [c for c in listed if c not in towns and c not in geo]
        added, single_company = [], []
        for code in sorted(candidates[city] - all_listed):
            geo_name = nfc(geo[code]["ort"]) if code in geo else ""
            # GeoNames names a company when the code belongs to one - add a
            # code only when it names a place (the city, or the OSM town).
            if geo_name and not (names_city(geo_name, city)
                                 or geo_name in towns[code]):
                single_company.append((code, geo_name))
                continue
            added.append(code)

        for code in kept:
            rows.append((code, city, entry["land"], ""))
        for code in special:
            rows.append((code, city, entry["land"], NOTE_SPECIAL))
        for code in added:
            osm_name = "; ".join(sorted(towns[code]))
            rows.append((code, city, entry["land"], f"{NOTE_NEW} (OSM: {osm_name})"))
        report[city] = {"listed": len(listed), "kept": len(kept),
                        "special": special, "added": added,
                        "dropped": len(dropped), "single_company": single_company}
    return sorted(rows), report


def main():
    offline = "--offline" in sys.argv[1:]
    raw = next((a.split("=", 1)[1] for a in sys.argv[1:]
                if a.startswith("--overpass-json=")), None)
    cities = read_original()
    prefixes = {c[:2] for entry in cities.values() for c in entry["codes"]}

    if offline:
        areas = json.loads(OSM_CACHE.read_text(encoding="utf-8"))
        print(f"OSM: {len(areas)} postal code areas from {OSM_CACHE.name}")
    else:
        if raw:
            elements = json.loads(Path(raw).read_text(encoding="utf-8"))["elements"]
            areas = areas_of(elements)
        else:
            areas = fetch_osm(prefixes)
        OSM_CACHE.write_text(json.dumps(areas, ensure_ascii=False, indent=0),
                             encoding="utf-8")
        print(f"OSM: {len(areas)} postal code areas, saved to {OSM_CACHE.name}")

    geo = plz_tabelle()
    rows, report = correct(cities, *osm_towns(areas), geo)
    codes = [row[0] for row in rows]
    if len(codes) != len(set(codes)):
        raise SystemExit("A code landed in two cities - nothing written.")

    with CORRECTED.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Postleitzahl", "Stadt/Ort", "Bundesland", "Hinweis"])
        writer.writerows(rows)

    total = {"listed": 0, "kept": 0, "special": 0, "added": 0, "dropped": 0}
    print(f"{'city':20s} {'listed':>6s} {'kept':>5s} {'special':>7s} "
          f"{'added':>5s} {'dropped':>7s}  added codes")
    for city, r in report.items():
        print(f"{city:20s} {r['listed']:6d} {r['kept']:5d} {len(r['special']):7d} "
              f"{len(r['added']):5d} {r['dropped']:7d}  {' '.join(r['added'])}")
        for code, name in r["single_company"]:
            print(f"{'':20s} not added: {code} belongs to one company ({name})")
        for key in ("listed", "kept", "dropped"):
            total[key] += r[key]
        total["special"] += len(r["special"])
        total["added"] += len(r["added"])
    print(f"{'TOTAL':20s} {total['listed']:6d} {total['kept']:5d} "
          f"{total['special']:7d} {total['added']:5d} {total['dropped']:7d}")
    print(f"Corrected list: {len(rows)} codes -> {CORRECTED.relative_to(PROJECT)}")


if __name__ == "__main__":
    main()
