#!/usr/bin/env python3
"""Process consultants in postal regions 30-39: Google Maps -> Excel.

Usage:
    python werkzeuge/prozessberater-maps.py                 # plan + max cost, pays nothing
    python werkzeuge/prozessberater-maps.py --region=33 --nise   # one region (test)
    python werkzeuge/prozessberater-maps.py --nise          # all regions 30-39
    python werkzeuge/prozessberater-maps.py --excel         # Excel from what is already fetched
    --kufi=N   places per search term and region (default 60) - the cost brake

COST: the actor bills per place found (BRONZE rate 0.003 USD). Without
--nise nothing is started. Search terms, area and the logic of the list
are in pipeline/prozessberater.py.

SAFETY: the run_id is written to disk as soon as a run starts. If the
script dies, the paid results are fetched again with the same id - a
second call never starts a second paid run for the same region.

No email is sent. Instantly is not touched.
"""
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

PROJEKT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJEKT))

from pipeline.env import lade_dotenv  # noqa: E402

lade_dotenv(PROJEKT / ".env")

import requests  # noqa: E402

from pipeline import prozessberater as pb  # noqa: E402

ACTOR = "compass~crawler-google-places"
PREIS_PRO_ORT = 0.003          # BRONZE rate (STARTER plan, since 02.09.2026)
KUFI_STANDARD = 60
ORDNER = PROJEKT / "laeufe/leadquellen/prozessberater-plr30-39"


def log(*teile):
    print(f"[{datetime.now():%H:%M:%S}]", *teile, flush=True)


def eingabe(region, kufi):
    # Same input as the zone tool, only terms and area differ.
    return {
        "searchStringsArray": pb.SEARCH_TERMS,
        "customGeolocation": pb.cells_geojson(pb.region_cells(region)),
        "maxCrawledPlacesPerSearch": kufi,
        "language": "de",
        "searchMatching": "all",
        "website": "allPlaces",
        "skipClosedPlaces": False,
        "scrapePlaceDetailPage": False,
        "scrapeContacts": False,
        "includeWebResults": False,
        "scrapeDirectories": False,
        "maxQuestions": 0,
        "maxReviews": 0,
        "maxImages": 0,
        "maximumLeadsEnrichmentRecords": 0,
        "enableCompetitorAnalysis": False,
    }


def mit_wiederholung(was, url, timeout, versuche=5):
    """A network error must not lose a PAID run (zone 35, 02.09.2026).

    A 5xx from Apify counts as a network error too: on 14.10.2026 one
    "502 Bad Gateway" on a status check ended the whole 30-39 run while
    region 35 kept running, paid, at Apify. The token goes in a header,
    so it never shows up in an error message or a log."""
    for numer in range(1, versuche + 1):
        try:
            antwort = requests.get(url, timeout=timeout, headers=_auth())
            if antwort.status_code < 500 or numer == versuche:
                antwort.raise_for_status()
                return antwort.json()
            gabim = f"HTTP {antwort.status_code}"
        except (requests.Timeout, requests.ConnectionError) as fehler:
            if numer == versuche:
                raise
            gabim = type(fehler).__name__
        log(f"    network error at {was} ({gabim}) - "
            f"try {numer}/{versuche}, waiting {10 * numer}s")
        time.sleep(10 * numer)


def _auth():
    return {"Authorization": f"Bearer {os.environ.get('APIFY_API_KEY', '')}"}


def region_holen(token, region, kufi):
    ordner = ORDNER / f"region-{region}"
    ordner.mkdir(parents=True, exist_ok=True)
    dataset_datei = ordner / "dataset.json"
    if dataset_datei.exists():
        log(f"region {region}: already fetched, nothing paid")
        return
    id_datei = ordner / "apify-run-id.json"
    if id_datei.exists():
        run_id = json.loads(id_datei.read_text(encoding="utf-8"))["run_id"]
        log(f"region {region}: run already paid, fetching again: {run_id}")
    else:
        # The account has a hard monthly limit; a run that crosses it is
        # stopped by Apify halfway, paid but incomplete. Check first.
        grenzen = mit_wiederholung(
            "limits", "https://api.apify.com/v2/users/me/limits",
            timeout=60)["data"]
        rest = (grenzen["limits"]["maxMonthlyUsageUsd"]
                - grenzen["current"]["monthlyUsageUsd"])
        bedarf = len(pb.SEARCH_TERMS) * kufi * PREIS_PRO_ORT
        if rest < bedarf + 1:
            sys.exit(f"region {region}: only {rest:.2f} USD left of the "
                     f"monthly Apify limit, this region may need "
                     f"{bedarf:.2f} - stopped before paying. Regions "
                     f"fetched so far stay; build their list with --excel.")
        log(f"region {region}: {rest:.2f} USD left of the monthly limit")
        log(f"region {region}: starting Apify, {len(pb.SEARCH_TERMS)} terms "
            f"x {kufi} = max ~{len(pb.SEARCH_TERMS) * kufi * PREIS_PRO_ORT:.2f} USD")
        antwort = requests.post(
            f"https://api.apify.com/v2/acts/{ACTOR}/runs",
            json=eingabe(region, kufi), timeout=60, headers=_auth())
        antwort.raise_for_status()
        daten = antwort.json()["data"]
        run_id = daten["id"]
        id_datei.write_text(json.dumps({
            "run_id": run_id, "dataset_id": daten["defaultDatasetId"],
            "kufi": kufi, "zeit": datetime.now().isoformat(timespec="seconds"),
        }, ensure_ascii=False, indent=1), encoding="utf-8")
        log(f"    run_id saved: {run_id}")

    while True:
        lauf = mit_wiederholung(
            "status", f"https://api.apify.com/v2/actor-runs/{run_id}",
            timeout=60)["data"]
        if lauf["status"] not in ("READY", "RUNNING"):
            break
        log(f"    region {region} still running ...")
        time.sleep(30)
    if lauf["status"] != "SUCCEEDED":
        sys.exit(f"region {region}: Apify run ended with {lauf['status']} - "
                 f"{lauf.get('statusMessage')}")
    eintraege = mit_wiederholung(
        "dataset", f"https://api.apify.com/v2/datasets/"
                   f"{lauf['defaultDatasetId']}/items"
                   f"?clean=true&format=json", timeout=300)
    dataset_datei.write_text(json.dumps(eintraege, ensure_ascii=False),
                             encoding="utf-8")
    log(f"region {region}: {len(eintraege)} places, real cost "
        f"{lauf.get('usageTotalUsd')} USD")


def excel_bauen():
    datasets, per_term = {}, []
    for region in pb.REGIONS:
        ordner = ORDNER / f"region-{region}"
        if not (ordner / "dataset.json").exists():
            continue
        eintraege = json.loads((ordner / "dataset.json")
                               .read_text(encoding="utf-8"))
        kufi = json.loads((ordner / "apify-run-id.json")
                          .read_text(encoding="utf-8")).get("kufi", 0)
        datasets[region] = eintraege
        for term in pb.SEARCH_TERMS:
            per_term.append((region, term, sum(
                1 for e in eintraege if e.get("searchString") == term), kufi))
    if not datasets:
        sys.exit("Nothing fetched yet - first run with --nise.")
    rows, counts = pb.build_rows(datasets)
    ziel = (PROJEKT / f"Prozessberater-PLR30-39-Firmen-"
                      f"{datetime.now():%Y%m%d-%H%M}.xlsx")
    pb.write_excel(ziel, rows, counts, per_term)
    log(f"regions in the list: {', '.join(datasets)}")
    log(f"places delivered: {counts['geliefert']}, without PLZ: "
        f"{counts['ohne_plz']}, outside 30-39: {counts['ausserhalb_30_39']}")
    log(f"firms in the list: {counts['firmen']}")
    log(f"Excel: {ziel.name}")


def main():
    regionen, kufi, nise, nur_excel = list(pb.REGIONS), KUFI_STANDARD, False, False
    for arg in sys.argv[1:]:
        if arg.startswith("--region="):
            regionen = [r.strip() for r in arg.split("=", 1)[1].split(",")]
        elif arg.startswith("--kufi="):
            kufi = int(arg.split("=", 1)[1])
        elif arg == "--nise":
            nise = True
        elif arg == "--excel":
            nur_excel = True
        else:
            sys.exit(f"Unknown option: {arg}")
    falsch = [r for r in regionen if r not in pb.REGIONS]
    if falsch:
        sys.exit(f"Only regions 30-39, not: {', '.join(falsch)}")

    if nur_excel:
        excel_bauen()
        return

    log(f"Plan: {len(regionen)} region(s), {len(pb.SEARCH_TERMS)} terms, "
        f"limit {kufi} places per term and region")
    for region in regionen:
        status = ("already fetched"
                  if (ORDNER / f"region-{region}" / "dataset.json").exists()
                  else "")
        log(f"  region {region}: {len(pb.region_cells(region))} cells "
            f"of ~17x17 km  {status}")
    log(f"Max cost: ~{pb.max_cost(len(regionen), len(pb.SEARCH_TERMS), kufi, PREIS_PRO_ORT):.2f} USD "
        f"(if every term hits its limit everywhere - usually less)")
    if not nise:
        log("Nothing started. To start and pay: add --nise")
        return

    token = os.environ.get("APIFY_API_KEY")
    if not token:
        sys.exit("APIFY_API_KEY is missing (no .env on this computer?).")
    for region in regionen:
        region_holen(token, region, kufi)
    excel_bauen()


if __name__ == "__main__":
    main()
