#!/usr/bin/env python3
"""Fuellt daten/plz-bundesland.json aus dem oeffentlichen PLZ-Register.

Warum getrennt vom Neubau: der Neubau von master.db soll NIE ins Netz
gehen. Sonst haengt eine Datenbank, die wir mehrmals am Tag neu bauen, an
der Verfuegbarkeit eines fremden Dienstes (Projektregel: Zuverlaessigkeit
zuerst). Dieses Werkzeug laeuft einmal und danach nur noch fuer neue
Postleitzahlen.

Kostet nichts - das Register ist oeffentlich und frei.

Perdorimi:
    python werkzeuge/bundesland-fuellen.py            # te gjitha nga baza
    python werkzeuge/bundesland-fuellen.py --zone=34  # vetem nje zone
"""
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

PROJEKT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJEKT))

from pipeline import bundesland  # noqa: E402
from pipeline.master_db import DB_NAME  # noqa: E402


def log(*teile):
    print(f"[{datetime.now():%H:%M:%S}]", *teile, flush=True)


def plz_aus_datenbank():
    pfad = PROJEKT / DB_NAME
    if not pfad.exists():
        sys.exit(f"{DB_NAME} s'ekziston - ndertoje bazen se pari.")
    db = sqlite3.connect(pfad)
    return [r[0] for r in db.execute(
        "SELECT DISTINCT plz FROM companies WHERE plz IS NOT NULL AND plz!=''")]


def plz_aus_zone(nummer):
    pfad = PROJEKT / "laeufe/leadquellen" / f"plz-liste-oliver-zona{nummer}.txt"
    if not pfad.exists():
        sys.exit(f"{pfad.name} s'ekziston.")
    return [r.strip() for r in pfad.read_text(encoding="utf-8").splitlines()
            if r.strip().isdigit() and len(r.strip()) == 5]


def main():
    zone = None
    for arg in sys.argv[1:]:
        if arg.startswith("--zone="):
            zone = arg.split("=", 1)[1]

    kodet = plz_aus_zone(zone) if zone else plz_aus_datenbank()
    log("=" * 62)
    log(f"Bundesland: {len(kodet)} kode postare "
        f"({'zona ' + zone if zone else 'e gjithe baza'})")
    log("Burimi: regjistri publik gjerman i kodeve postare. Falas.")
    log("=" * 62)

    speicher = bundesland.speicher_fuellen(PROJEKT, kodet, log=log)

    gefunden = sum(1 for p in kodet if speicher.get(bundesland.plz_normal(p)))
    laender = {}
    for p in kodet:
        wert = speicher.get(bundesland.plz_normal(p), "")
        if wert:
            laender[wert] = laender.get(wert, 0) + 1

    log("=" * 62)
    log(f"Me Bundesland:  {gefunden} / {len(kodet)}")
    for land, sa in sorted(laender.items(), key=lambda x: -x[1]):
        log(f"    {sa:5}  {land}")
    log(f"U ruajt te:     {bundesland.SPEICHER_NAME}")
    log("Hapi tjeter:    rindertoje bazen qe fusha te mbushet.")
    log("=" * 62)


if __name__ == "__main__":
    main()
