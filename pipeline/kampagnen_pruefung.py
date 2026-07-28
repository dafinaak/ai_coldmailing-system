"""Text-Wache fuer Instantly-Kampagnen (Weg-B-Gegenmassnahme, Bauplan
Versandstart 2026-07-28): Bei Weg B stehen die Mail-Texte offen in
Instantly und koennten dort - auch versehentlich - geaendert werden.
Diese Pruefung vergleicht Betreff und Text jeder Stufe mit dem
freigegebenen Stand (Referenz-JSON im Laufordner) und meldet jede
Abweichung, statt dass sie still in den Versand geht.

Aufruf (liest nur, aendert nichts):
    python -m pipeline.kampagnen_pruefung --kampagne <id> \
        --referenz laeufe/plr30-39/kampagne-referenz.json
Mit --referenz-anlegen wird stattdessen der AKTUELLE Instantly-Stand
als neue Referenz gespeichert (nur nach menschlicher Freigabe benutzen).
Benoetigt INSTANTLY_API_KEY in der .env.
"""
import argparse
import json
import os
from pathlib import Path


def referenz_aus_kampagne(kampagne: dict) -> dict:
    """Zieht aus einer Instantly-Kampagne den vergleichbaren Kern:
    Betreff und Text jeder Stufe, in Reihenfolge."""
    schritte = (kampagne.get("sequences") or [{}])[0].get("steps") or []
    return {"stufen": [{"betreff": s["variants"][0]["subject"],
                        "text": s["variants"][0]["body"]}
                       for s in schritte]}


def abweichungen(referenz: dict, kampagne: dict) -> list:
    """Vergleicht den freigegebenen Stand mit der Live-Kampagne.
    Leere Liste = alles unveraendert."""
    soll = referenz["stufen"]
    ist = referenz_aus_kampagne(kampagne)["stufen"]
    meldungen = []
    if len(soll) != len(ist):
        meldungen.append(f"Stufenzahl geaendert: {len(soll)} freigegeben, "
                         f"{len(ist)} in Instantly gefunden")
    for nr, (s, i) in enumerate(zip(soll, ist), start=1):
        if s["betreff"] != i["betreff"]:
            meldungen.append(f"Stufe {nr}: Betreff geaendert "
                             f"(freigegeben: {s['betreff']!r}, "
                             f"jetzt: {i['betreff']!r})")
        if s["text"] != i["text"]:
            meldungen.append(f"Stufe {nr}: Text geaendert")
    return meldungen


def _kampagne_laden(campaign_id: str) -> dict:
    import requests
    antwort = requests.get(
        f"https://api.instantly.ai/api/v2/campaigns/{campaign_id}",
        headers={"Authorization": f"Bearer {os.environ['INSTANTLY_API_KEY']}"},
        timeout=60)
    if antwort.status_code >= 400:
        raise RuntimeError(f"Instantly antwortet mit {antwort.status_code}: "
                           f"{antwort.text[:200]}")
    return antwort.json()


def main(argv=None):
    from pipeline.env import lade_dotenv, brauche_env
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--kampagne", required=True)
    parser.add_argument("--referenz", required=True)
    parser.add_argument("--referenz-anlegen", action="store_true")
    args = parser.parse_args(argv)

    lade_dotenv()
    brauche_env("INSTANTLY_API_KEY")
    kampagne = _kampagne_laden(args.kampagne)
    pfad = Path(args.referenz)

    if args.referenz_anlegen:
        pfad.parent.mkdir(parents=True, exist_ok=True)
        pfad.write_text(json.dumps(referenz_aus_kampagne(kampagne),
                                   ensure_ascii=False, indent=2),
                        encoding="utf-8")
        print(f"Referenz gespeichert: {pfad}")
        return 0

    referenz = json.loads(pfad.read_text(encoding="utf-8"))
    meldungen = abweichungen(referenz, kampagne)
    if not meldungen:
        print("Keine Abweichungen - Kampagnentext entspricht dem "
              "freigegebenen Stand.")
        return 0
    print("ABWEICHUNGEN GEFUNDEN - bitte klaeren, bevor irgendetwas "
          "aktiviert wird:")
    for m in meldungen:
        print(f"- {m}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
