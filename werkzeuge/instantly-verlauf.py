#!/usr/bin/env python3
"""Wer hat bei Instantly was gemacht? - reiner Lese-Blick ins Protokoll.

Gebaut am 21.08.2026, nachdem die Kampagne "IT-Dienstleister -
Anschreiben" zum zweiten Mal aktiv war, ohne dass jemand davon wusste.
Instantly führt ein Protokoll (/api/v2/audit-logs); dieses Skript holt es
und zeigt es lesbar an - mit unserer Uhrzeit, und getrennt danach, ob ein
MENSCH im Browser gehandelt hat oder ein Skript über den API-Schlüssel.

Es wird NUR gelesen. Das Skript ändert nichts, startet nichts, pausiert
nichts und verschickt nichts.

Aufruf:
    python werkzeuge/instantly-verlauf.py                # letzte 14 Tage
    python werkzeuge/instantly-verlauf.py --tage 60
    python werkzeuge/instantly-verlauf.py --kampagne <id>   # nur diese
"""
import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests

from pipeline.env import lade_dotenv

BASIS = "https://api.instantly.ai/api/v2"

# Instantly nennt die Art einer Handlung nur als Zahl. Diese Zuordnung
# ist aus unseren EIGENEN, belegten Handlungen abgeleitet (das Pausieren
# am 21.08.2026 war Typ 11, das Löschen zweier Leads Typ 2). Was wir
# nicht belegen können, bleibt ausdrücklich unbekannt - lieber "Typ 9"
# anzeigen als etwas zu erfinden.
ARTEN = {
    1: "Anmeldung",
    2: "Kontakt gelöscht",
    11: "Kampagne geändert (Start/Pause/Einstellungen)",
}


def hole_protokoll(schluessel: str, tage: int) -> list:
    kopf = {"Authorization": f"Bearer {schluessel}"}
    grenze = datetime.now(timezone.utc) - timedelta(days=tage)
    alle, weiter = [], None
    while True:
        p = {"limit": 100}
        if weiter:
            p["starting_after"] = weiter
        antwort = requests.get(f"{BASIS}/audit-logs", headers=kopf,
                               params=p, timeout=60)
        antwort.raise_for_status()
        daten = antwort.json()
        posten = daten.get("items") or []
        alle += posten
        weiter = daten.get("next_starting_after")
        if not weiter or not posten:
            break
    return [e for e in alle
            if datetime.fromisoformat(e["timestamp"].replace("Z", "+00:00"))
            >= grenze]


def unsere_zeit(zeitstempel: str) -> str:
    """UTC in unsere Uhrzeit (Sommerzeit, +2 Stunden)."""
    roh = datetime.fromisoformat(zeitstempel.replace("Z", "+00:00"))
    return (roh + timedelta(hours=2)).strftime("%d.%m.%Y %H:%M:%S")


def main() -> int:
    zerleger = argparse.ArgumentParser(description=__doc__)
    zerleger.add_argument("--tage", type=int, default=14)
    zerleger.add_argument("--kampagne", default=None,
                          help="nur Einträge zu dieser Kampagnen-Kennung")
    args = zerleger.parse_args()

    lade_dotenv()
    schluessel = os.environ.get("INSTANTLY_API_KEY")
    if not schluessel:
        print("Fehlt: INSTANTLY_API_KEY in der .env")
        return 1

    eintraege = hole_protokoll(schluessel, args.tage)
    if args.kampagne:
        eintraege = [e for e in eintraege
                     if e.get("campaign_id") == args.kampagne]
    eintraege.sort(key=lambda e: e["timestamp"])

    print(f"{len(eintraege)} Einträge aus den letzten {args.tage} Tagen"
          + (f" zur Kampagne {args.kampagne}" if args.kampagne else "")
          + " - Uhrzeiten in unserer Zeit.\n")
    for e in eintraege:
        art = ARTEN.get(e.get("activity_type"),
                        f"Typ {e.get('activity_type')} (unbekannt)")
        wer = ("Skript über den API-Schlüssel" if e.get("from_api")
               else f"MENSCH im Browser (Konto {e.get('user_id')})")
        print(f"{unsere_zeit(e['timestamp'])}  {art}")
        print(f"    {wer}")
        if e.get("campaign_id"):
            print(f"    Kampagne: {e['campaign_id']}")
        print(f"    IP: {e.get('ip_address')}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
