#!/usr/bin/env python3
"""Hapi 0 per cdo zone: gjetja e firmave me Google Maps (Apify).

Pse duhet: vrapimi i paguar me 21.08.2026 perdori nje rreth rreth
Bielefeldit dhe mbuloi vetem zonat 32 e 33. Cdo zone tjeter bie jashte tij
- ne dataset-in e vjeter kishte VETEM 3 firma me kod 34xxx - prandaj i
duhet nje vrapim i vetin.

Perdorimi:
    python werkzeuge/zonen-maps.py --zone=35
    python werkzeuge/zonen-maps.py --zone=35 --kufi=70   # buxhet i ngushte

Leje: Dafina, 28.08.2026 ("po beje c" per zonen 34).

KOSTO: aktori paguhet per vend te gjetur. Tarifa e llogarise sone
(BRONZE) eshte 0.003 USD/vend. Kufiri per kerkim e mban shpenzimin brenda
buxhetit qe ka mbetur - shih KUFI_PER_KERKIM me poshte.

SIGURI: run_id shkruhet ne disk SA MENJEHERE te niset vrapimi. Nese
skripti bie, rezultatet e paguara merren perseri me te njejtin id.

ASNJE email nuk dergohet. Instantly nuk preket fare.
"""
import json
import math
import sys
import time
from datetime import datetime
from pathlib import Path

PROJEKT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJEKT))

from pipeline.env import lade_dotenv  # noqa: E402

lade_dotenv(PROJEKT / ".env")

import os  # noqa: E402
import requests  # noqa: E402

ACTOR = "compass~crawler-google-places"

# Qendra dhe rrezja per cdo zone. Te dyja jane zgjedhur qe rrethi t'i
# mbuloje skajet e zones pa e fryre siperfaqen - sepse cdo vend i gjetur
# jashte zones paguhet njesoj si nje brenda saj.
ZONEN = {
    # Willingen (34508) ne perendim, Bad Karlshafen (34385) ne veri,
    # Neukirchen (34626) ne jug; me i larguari bie rreth 46 km.
    "34": {"mitte": (51.25, 9.25), "radius": 52,
           "plz": "plz-liste-oliver-zona34.txt",
           "lauf": "zona34-kassel-2026-08-28"},
    # Lichtenfels (35104) ne veri, Hungen (35410) ne jug, Breidenbach
    # (35236) ne perendim, Ulrichstein (35327) ne lindje; me i larguari
    # bie rreth 46 km.
    "35": {"mitte": (50.81, 8.83), "radius": 48,
           "plz": "plz-liste-oliver-zona35.txt",
           "lauf": "zona35-giessen-2026-08-28"},
}

# Te njejtat fjale kerkimi si me 21.08.2026, qe zona 34 te mblidhet me te
# njejtin kriter si 32 dhe 33 - perndryshe listat s'do te ishin te
# krahasueshme.
SUCHBEGRIFFE = [
    "IT-Dienstleister", "IT-Service", "Computerservice", "IT-Systemhaus",
    "EDV-Dienstleistungen", "IT-Support", "Netzwerktechnik",
    "Softwareentwicklung", "IT-Sicherheit", "Cloud-Dienstleistungen",
]

# Sa vende lejohen per cdo fjale kerkimi. Ky numer eshte freni i kostos:
# 10 fjale x KUFI = maksimumi i vendeve, dhe cdo vend kushton PREIS_PRO_ORT.
# Vendoset me --kufi= kur buxheti i mbetur eshte i ngushte.
KUFI_PER_KERKIM = 140
PREIS_PRO_ORT = 0.003          # tarifa BRONZE e llogarise sone


def log(*teile):
    print(f"[{datetime.now():%H:%M:%S}]", *teile, flush=True)


def kreis_polygon(lat, lon, radius_km, punkte=24):
    """Rreth i afruar me shume kende, ne formatin GeoJSON qe pret Apify."""
    grad_lat = radius_km / 111.32
    grad_lon = radius_km / (111.32 * math.cos(math.radians(lat)))
    ring = []
    for nummer in range(punkte):
        winkel = 2 * math.pi * nummer / punkte
        ring.append([round(lon + grad_lon * math.cos(winkel), 6),
                     round(lat + grad_lat * math.sin(winkel), 6)])
    ring.append(ring[0])                      # unaza duhet te mbyllet
    return {"type": "Polygon", "coordinates": [ring]}


def eingabe(zone):
    return {
        "searchStringsArray": SUCHBEGRIFFE,
        "customGeolocation": kreis_polygon(*zone["mitte"], zone["radius"]),
        "maxCrawledPlacesPerSearch": KUFI_PER_KERKIM,
        "language": "de",
        "searchMatching": "all",
        "website": "allPlaces",
        "skipClosedPlaces": False,
        # Cdo gje me poshte kushton pa na sjelle asgje: detajet, kontaktet,
        # vleresimet dhe fotot i lexojme vete nga faqja e firmes.
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


def lauf_starten(token, zone):
    lauf_ordner = PROJEKT / "laeufe/leadquellen" / zone["lauf"]
    lauf_ordner.mkdir(parents=True, exist_ok=True)
    id_datei = lauf_ordner / "apify-run-id.json"
    if id_datei.exists():
        gespeichert = json.loads(id_datei.read_text(encoding="utf-8"))
        log(f"vrapimi tashme i paguar, po merret serish: "
            f"{gespeichert['run_id']}")
        return gespeichert["run_id"]

    log(f"po niset Apify: {len(SUCHBEGRIFFE)} fjale x {KUFI_PER_KERKIM} "
        f"vende = max {len(SUCHBEGRIFFE) * KUFI_PER_KERKIM} "
        f"(~{len(SUCHBEGRIFFE) * KUFI_PER_KERKIM * PREIS_PRO_ORT:.2f} USD)")
    antwort = requests.post(
        f"https://api.apify.com/v2/acts/{ACTOR}/runs?token={token}",
        json=eingabe(zone), timeout=60)
    antwort.raise_for_status()
    daten = antwort.json()["data"]
    id_datei.write_text(json.dumps({
        "run_id": daten["id"],
        "dataset_id": daten["defaultDatasetId"],
        "zeit": datetime.now().isoformat(timespec="seconds"),
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"    run_id u ruajt: {daten['id']}")
    return daten["id"]


def warten(token, run_id):
    while True:
        antwort = requests.get(
            f"https://api.apify.com/v2/actor-runs/{run_id}?token={token}",
            timeout=60)
        antwort.raise_for_status()
        daten = antwort.json()["data"]
        if daten["status"] not in ("READY", "RUNNING"):
            return daten
        log(f"    ende duke vrapuar ... ({daten['status']})")
        time.sleep(20)


def holen(token, dataset_id):
    antwort = requests.get(
        f"https://api.apify.com/v2/datasets/{dataset_id}/items"
        f"?token={token}&clean=true&format=json", timeout=300)
    antwort.raise_for_status()
    return antwort.json()


def main():
    global KUFI_PER_KERKIM
    nummer = None
    for arg in sys.argv[1:]:
        if arg.startswith("--zone="):
            nummer = arg.split("=", 1)[1]
        elif arg.startswith("--kufi="):
            KUFI_PER_KERKIM = int(arg.split("=", 1)[1])
    if nummer not in ZONEN:
        sys.exit(f"Duhet --zone= nga: {', '.join(ZONEN)}")
    zone = ZONEN[nummer]

    token = os.environ["APIFY_API_KEY"]
    log("=" * 62)
    log(f"ZONA {nummer} - Hapi 0: gjetja e firmave me Google Maps")
    log("=" * 62)

    run_id = lauf_starten(token, zone)
    lauf = warten(token, run_id)
    log(f"statusi: {lauf['status']} - {lauf.get('statusMessage')}")

    eintraege = holen(token, lauf["defaultDatasetId"])
    ziel = (PROJEKT / "laeufe/leadquellen"
            / f"apify-ds-{lauf['defaultDatasetId']}.json")
    ziel.write_text(json.dumps(eintraege, ensure_ascii=False),
                    encoding="utf-8")

    kodet = {r.strip() for r in
             (PROJEKT / "laeufe/leadquellen" / zone["plz"])
             .read_text(encoding="utf-8").splitlines()
             if r.strip().isdigit() and len(r.strip()) == 5}
    in_zone = sum(1 for e in eintraege
                  if str(e.get("postalCode") or "").strip() in kodet)

    log("=" * 62)
    log(f"Vende gjithsej:     {len(eintraege)}")
    log(f"Brenda zones {nummer}:    {in_zone}")
    log(f"Kosto e vertete:    {lauf.get('usageTotalUsd')} USD")
    log(f"Dataset:            {ziel.name}")
    log("=" * 62)


if __name__ == "__main__":
    main()
