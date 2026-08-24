#!/usr/bin/env python3
"""Zona 32 - burimi Overpass/OpenStreetMap, i vetem.

Falas dhe pa Apify. Maps dhe Gelbe Seiten NUK thirren fare (maps=None,
gelbe_seiten=None), qe te mos preket buxheti i Apify-t.

Rezultati shkon si dosje e vet te laeufe/leadquellen/, prandaj hyn ne
bazen master me rindertimin e radhes dhe nuk e prek asnje te dhene te
meparshme.
"""
import json
import sys
from datetime import datetime
from pathlib import Path

PROJEKT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJEKT))

from pipeline.env import lade_dotenv  # noqa: E402

lade_dotenv(PROJEKT / ".env")

from pipeline.firmen_sammeln import sammeln_bis_ziel, plz_liste_lesen  # noqa: E402
from pipeline.sources.overpass import OverpassQuelle  # noqa: E402

PLZ_LISTE = PROJEKT / "laeufe/leadquellen/plz-liste-oliver-zona32.txt"
ORDNER = "zona32-overpass-2026-08-21"

DIENSTE = ["IT-Dienstleister", "Computer Services", "IT-Service"]


def log(*teile):
    print(f"[{datetime.now():%H:%M:%S}]", *teile, flush=True)


def main():
    kodet = plz_liste_lesen(str(PLZ_LISTE))
    log(f"Kode postare: {len(kodet)}")
    log("Burimi: VETEM Overpass/OSM. Maps dhe Gelbe Seiten te fikura.")

    firmen, bericht = sammeln_bis_ziel(
        "", 25.0, DIENSTE, 5000,
        maps=None, gelbe_seiten=None,
        overpass=OverpassQuelle(),
        plz_liste=kodet, daten_dir=str(PROJEKT), log=log)

    ziel = PROJEKT / "laeufe/leadquellen" / ORDNER
    ziel.mkdir(parents=True, exist_ok=True)
    (ziel / "firmen.json").write_text(
        json.dumps(firmen, ensure_ascii=False, indent=1), encoding="utf-8")
    (ziel / "sammelbericht.json").write_text(
        json.dumps(bericht, ensure_ascii=False, indent=1), encoding="utf-8")

    log("=" * 60)
    log(f"Overpass gjeti: {len(firmen)} firma brenda {len(kodet)} kodeve")
    log(f"Arsyeja e ndaljes: {bericht.get('grund_ende')}")
    log(f"Gabime burimi: {bericht.get('quellen_fehler')}")
    log(f"U ruajt te: {ziel}")
    log("=" * 60)


if __name__ == "__main__":
    main()
