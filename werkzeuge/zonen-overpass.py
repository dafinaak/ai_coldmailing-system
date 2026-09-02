#!/usr/bin/env python3
"""Cdo zone - burimi Overpass/OpenStreetMap, i vetem.

FALAS. Nuk preket Apify fare: Maps dhe Gelbe Seiten rrijne te fikura
(maps=None, gelbe_seiten=None), pra ky vrapim s'e ha buxhetin.

Zevendeson zona32-overpass.py, qe punonte vetem per zonen 32. Qendra,
rrezja dhe lista postare vijne tash nga pipeline/zonen.py, pra jane te
njejtat qe perdor Maps-i - perndryshe dy burimet do te mblidhnin dy
rrethe te ndryshem dhe krahasimi mes tyre s'do te thoshte asgje.

Perdorimi:
    python werkzeuge/zonen-overpass.py --zone=35

Rezultati shkon si dosje e vet te laeufe/leadquellen/, prandaj hyn ne
bazen master me rindertimin e radhes dhe nuk e prek asnje te dhene te
meparshme.

ASNJE email nuk dergohet. Instantly nuk preket fare.
"""
import json
import sys
from datetime import datetime
from pathlib import Path

PROJEKT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJEKT))

from pipeline.env import lade_dotenv  # noqa: E402

lade_dotenv(PROJEKT / ".env")

from pipeline import zonen  # noqa: E402
from pipeline.firmen_sammeln import sammeln_bis_ziel  # noqa: E402
from pipeline.sources.overpass import OverpassQuelle  # noqa: E402

DIENSTE = ["IT-Dienstleister", "Computer Services", "IT-Service"]

# Nuk ka kufi te vertete: Overpass eshte falas, prandaj merret gjithcka qe
# jep. Numri eshte vetem nje tavan sigurie kunder nje vrapimi te pafund.
ZIEL = 5000


def log(*teile):
    print(f"[{datetime.now():%H:%M:%S}]", *teile, flush=True)


def main():
    nummer = None
    for arg in sys.argv[1:]:
        if arg.startswith("--zone="):
            nummer = arg.split("=", 1)[1]
    if nummer is None:
        sys.exit(f"Duhet --zone= nga: {', '.join(sorted(zonen.ZONEN))}")
    try:
        zone = zonen.zone(nummer)
    except KeyError as gabim:
        sys.exit(str(gabim))

    kodet = zonen.plz_kodes(nummer)
    ordner = f"zona{nummer}-overpass-{datetime.now():%Y-%m-%d}"

    log("=" * 62)
    log(f"ZONA {nummer} ({zone['stadt']}) - Overpass/OpenStreetMap")
    log("=" * 62)
    log(f"Kode postare: {len(kodet)}")
    log("Burimi: VETEM Overpass/OSM. Maps dhe Gelbe Seiten te fikura.")
    log("Kosto: 0 USD - Overpass eshte falas.")

    firmen, bericht = sammeln_bis_ziel(
        "", 25.0, DIENSTE, ZIEL,
        maps=None, gelbe_seiten=None,
        overpass=OverpassQuelle(),
        plz_liste=kodet, daten_dir=str(PROJEKT), log=log)

    ziel = PROJEKT / "laeufe/leadquellen" / ordner
    ziel.mkdir(parents=True, exist_ok=True)
    (ziel / "firmen.json").write_text(
        json.dumps(firmen, ensure_ascii=False, indent=1), encoding="utf-8")
    (ziel / "sammelbericht.json").write_text(
        json.dumps(bericht, ensure_ascii=False, indent=1), encoding="utf-8")

    log("=" * 62)
    log(f"Overpass gjeti: {len(firmen)} firma brenda {len(kodet)} kodeve")
    log(f"Arsyeja e ndaljes: {bericht.get('grund_ende')}")
    log(f"Gabime burimi: {bericht.get('quellen_fehler')}")
    log(f"U ruajt te: {ziel}")
    log("=" * 62)


if __name__ == "__main__":
    main()
