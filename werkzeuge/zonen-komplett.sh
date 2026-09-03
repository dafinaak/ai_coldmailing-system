#!/bin/bash
# Nje zone e tere, nga mbledhja deri te Excel-i.
#
# Perdorimi:  ./werkzeuge/zonen-komplett.sh 36
#
# DY BURIME, si te zonat 32, 33 dhe 34 (vendim i Dafines, 02.09.2026).
# Gelbe Seiten u provua te zona 35 dhe DOLI JASHTE: nga 68 firmat e reja
# mbeten vetem 9 pas filtrit te profilit IT. Vegla mbetet e ndertuar
# (werkzeuge/zonen-gelbeseiten.py) por nuk hyn ne kete zinxhir.
#
# Cka ben, me radhe:
#   1. Google Maps (Apify, paguhet)   - nese vrapimi eshte nisur me pare,
#                                       merret ai i paguari, pa kosto te re
#   2. Overpass/OSM (falas)           - kapercehet nese eshte bere sot
#   3. Filtri i profilit IT mbi te DY burimet veç e veç
#      (pa kete hap firmat dalin ne Excel si "not_checked")
#   4. Eksporti Excel i zones
#
# Ndalet me heren e pare qe nje hap deshton - qe te mos vazhdohet mbi
# nje mbledhje gjysmake dhe te dale nje Excel qe duket i plote por s'eshte.
#
# ASNJE email nuk dergohet. Instantly nuk preket fare.
set -euo pipefail

ZONA="${1:?Duhet numri i zones, p.sh.: ./werkzeuge/zonen-komplett.sh 36}"
cd "$(dirname "$0")/.."
PY=.venv/bin/python
L=laeufe/leadquellen
SOT=$(date +%Y-%m-%d)

echo "########## ZONA $ZONA - 1/4 Google Maps ##########"
$PY werkzeuge/zonen-maps.py --zone="$ZONA" --kufi=110

# Emri i dataset-it del nga run-id-ja e ruajtur, jo nga hamendja.
LAUF_MAPS=$($PY -c "import sys;sys.path.insert(0,'.');from pipeline import zonen;print(zonen.zone('$ZONA')['lauf'])")
DSID=$($PY -c "import json;print(json.load(open('$L/$LAUF_MAPS/apify-run-id.json'))['dataset_id'])")

echo "########## ZONA $ZONA - 2/4 Overpass/OSM (falas) ##########"
# Kontrollohet CDO dosje Overpass e zones, jo vetem ajo e sotme. Me
# vetem daten e sotme, nje rinisje te nesermen krijonte nje dosje te
# dyte me te njejtat firma: baza i merrte te dyja dhe ato te padala
# neper filtrin e profilit dilnin ne Excel si "not_checked".
OVP=$(ls -d "$L/zona$ZONA-overpass-"* 2>/dev/null | head -1 || true)
if [ -n "$OVP" ] && [ -f "$OVP/firmen.json" ]; then
  echo "u be tashme ($(basename "$OVP")) - po kapercehet"
else
  $PY werkzeuge/zonen-overpass.py --zone="$ZONA"
  OVP="$L/zona$ZONA-overpass-$SOT"
fi

echo "########## ZONA $ZONA - 3/4 filtri i profilit IT ##########"
PLZ=$($PY -c "import sys;sys.path.insert(0,'.');from pipeline import zonen;print(zonen.zone('$ZONA')['plz'])")

echo "--- Maps ---"
$PY werkzeuge/zona32-lauf.py --lauf="$LAUF_MAPS" --plz="$PLZ" \
    --dataset="apify-ds-$DSID.json"

if [ -n "$OVP" ] && [ -f "$OVP/firmen.json" ]; then
  echo "--- Overpass ($(basename "$OVP")) ---"
  $PY werkzeuge/zona32-lauf.py --lauf="$(basename "$OVP")" --plz="$PLZ" \
      --firmen="$OVP/firmen.json"
fi

echo "########## ZONA $ZONA - 4/4 Excel ##########"
$PY werkzeuge/zona32-export.py --zone="$ZONA"
