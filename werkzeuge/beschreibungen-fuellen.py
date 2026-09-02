#!/usr/bin/env python3
"""Fuellt das Feld "Kurz-Beschreibung" aus dem schon gelesenen Webtext.

Olivers DataWarehouse-Liste verlangt es, und es war zu 100% leer. Der
Text liegt bereits in den Laeufen (01-webtext.json) - es wird also NICHTS
neu geladen, nur zusammengefasst. Das ist der ganze Grund, warum das hier
Cent kostet und nicht Euro.

Geschrieben wird in die firmen.json der Laeufe, nicht in master.db - die
wird ohnehin daraus neu gebaut.

Perdorimi:
    python werkzeuge/beschreibungen-fuellen.py --lauf=zona34-kassel-2026-08-28
    python werkzeuge/beschreibungen-fuellen.py --alle
    python werkzeuge/beschreibungen-fuellen.py --alle --limit=20   # prove
"""
import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

PROJEKT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJEKT))

from pipeline.env import lade_dotenv  # noqa: E402

lade_dotenv(PROJEKT / ".env")

import requests  # noqa: E402
from pipeline.beschreibung_llm import beschreiben  # noqa: E402
from pipeline.ki import KI  # noqa: E402

GLEICHZEITIG = 8

# Cmimet e gpt-4.1-mini, USD per 1 milion token - te njejtat si te
# werkzeuge/zona32-lauf.py, qe shifrat te jene te krahasueshme.
PREIS_EIN = 0.40
PREIS_AUS = 1.60


def log(*teile):
    print(f"[{datetime.now():%H:%M:%S}]", *teile, flush=True)


class ZaehlendeSession:
    """Numeron token-at e vertete nga pergjigjja, qe kostoja te jete e
    matur e jo e vleresuar."""

    def __init__(self, echt):
        self._echt = echt
        self.ein = self.aus = self.aufrufe = 0
        self._sperre = threading.Lock()

    def post(self, *args, **kwargs):
        antwort = self._echt.post(*args, **kwargs)
        try:
            nutzung = (antwort.json() or {}).get("usage") or {}
            with self._sperre:
                self.ein += int(nutzung.get("prompt_tokens") or 0)
                self.aus += int(nutzung.get("completion_tokens") or 0)
                self.aufrufe += 1
        except Exception:      # noqa: BLE001 - numerimi s'guxon te thyeje asgje
            pass
        return antwort

    def __getattr__(self, name):
        return getattr(self._echt, name)


def laeufe_waehlen():
    wurzel = PROJEKT / "laeufe/leadquellen"
    gewaehlt, limit, alle = [], None, False
    for arg in sys.argv[1:]:
        if arg.startswith("--lauf="):
            gewaehlt.append(wurzel / arg.split("=", 1)[1])
        elif arg == "--alle":
            alle = True
        elif arg.startswith("--limit="):
            limit = int(arg.split("=", 1)[1])
    if alle:
        gewaehlt = sorted(p.parent for p in wurzel.glob("*/01-webtext.json"))
    if not gewaehlt:
        sys.exit("Duhet --lauf=<emri> ose --alle")
    return gewaehlt, limit


def main():
    laeufe, limit = laeufe_waehlen()
    zaehler = ZaehlendeSession(requests.Session())
    ki = KI(session=zaehler)

    log("=" * 62)
    log(f"Kurz-Beschreibung nga tekstet e ruajtura ({len(laeufe)} vrapime)")
    log("Asnje faqe nuk shkarkohet perseri.")
    log("=" * 62)

    gesamt_neu = 0
    for lauf in laeufe:
        firmen_datei = lauf / "firmen.json"
        webtext_datei = lauf / "01-webtext.json"
        if not (firmen_datei.exists() and webtext_datei.exists()):
            log(f"  {lauf.name}: mungon firmen.json ose 01-webtext.json")
            continue

        firmen = json.loads(firmen_datei.read_text(encoding="utf-8"))
        webtexte = json.loads(webtext_datei.read_text(encoding="utf-8"))

        offen = [f for f in firmen
                 if not f.get("beschreibung")
                 and webtexte.get(f.get("domain") or "")]
        if limit:
            offen = offen[:limit]
        log(f"  {lauf.name}: {len(offen)} firma per te pershkruar")
        if not offen:
            continue

        fertig = [0]
        sperre = threading.Lock()

        def eine(firma):
            text = beschreiben(ki, firma.get("name", ""),
                               webtexte.get(firma.get("domain") or "", ""))
            if text:
                firma["beschreibung"] = text
                firma["beschreibung_quelle"] = "Webseite (KI-Zusammenfassung)"
            with sperre:
                fertig[0] += 1
                if fertig[0] % 100 == 0:
                    log(f"      ... {fertig[0]}/{len(offen)}")

        with ThreadPoolExecutor(max_workers=GLEICHZEITIG) as pool:
            list(pool.map(eine, offen))

        neu = sum(1 for f in offen if f.get("beschreibung"))
        gesamt_neu += neu
        firmen_datei.write_text(
            json.dumps(firmen, ensure_ascii=False, indent=1), encoding="utf-8")
        log(f"      u shkruan: {neu} pershkrime")

    kosten = (zaehler.ein / 1e6 * PREIS_EIN) + (zaehler.aus / 1e6 * PREIS_AUS)
    log("=" * 62)
    log(f"Pershkrime te reja: {gesamt_neu}")
    log(f"KOSTO: {zaehler.aufrufe} thirrje KI, {zaehler.ein:,} token hyrje, "
        f"{zaehler.aus:,} token dalje = {kosten:.4f} USD")
    log("Hapi tjeter: rindertoje bazen qe fusha te mbushet.")
    log("=" * 62)


if __name__ == "__main__":
    main()
