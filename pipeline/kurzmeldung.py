"""Taegliche Kurzmeldung fuer Oliver (Bauplan Versandstart, Schritt 8):
liest die Kampagnen-Zahlen aus Instantly und formt daraus die fertige
deutsche Kurznachricht zum Verschicken/Kopieren.

Feld-Namen wie in web/instantly_leser.py (dort live verifiziert):
leads_count, emails_sent_count, open_count, reply_count, bounced_count.
Fehlende Werte werden als "unbekannt" gezeigt, nie als erfundene Null
(Projekt-Grundsatz, Live-Fund 22.07.2026: Instantly liefert manchmal
keine Zeile).

Aufruf:
    python -m pipeline.kurzmeldung --kampagne <id>
Benoetigt INSTANTLY_API_KEY in der .env.
"""
import argparse
import os


def _wert(zahlen: dict, feld: str):
    wert = zahlen.get(feld)
    return "unbekannt" if wert is None else str(wert)


def kurzmeldung_text(kampagnen_name: str, zahlen: dict, stand: str) -> str:
    return (
        f"Kurzmeldung Kampagne „{kampagnen_name}“ — Stand {stand}\n"
        f"\n"
        f"- Kontakte in der Kampagne: {_wert(zahlen, 'leads_count')}\n"
        f"- Mails versendet (gesamt): {_wert(zahlen, 'emails_sent_count')}\n"
        f"- davon geöffnet: {_wert(zahlen, 'open_count')}\n"
        f"- geantwortet: {_wert(zahlen, 'reply_count')}\n"
        f"- Rückläufer: {_wert(zahlen, 'bounced_count')}\n")


def main(argv=None):
    from datetime import datetime
    import requests
    from pipeline.env import lade_dotenv, brauche_env
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--kampagne", required=True)
    args = parser.parse_args(argv)
    lade_dotenv()
    brauche_env("INSTANTLY_API_KEY")
    kopf = {"Authorization": f"Bearer {os.environ['INSTANTLY_API_KEY']}"}

    kampagne = requests.get(
        f"https://api.instantly.ai/api/v2/campaigns/{args.kampagne}",
        headers=kopf, timeout=60)
    kampagne.raise_for_status()
    name = kampagne.json().get("name", args.kampagne)

    analytics = requests.get(
        "https://api.instantly.ai/api/v2/campaigns/analytics",
        params={"id": args.kampagne}, headers=kopf, timeout=60)
    analytics.raise_for_status()
    zeilen = analytics.json() or []
    zahlen = zeilen[0] if zeilen else {}

    print(kurzmeldung_text(name, zahlen,
                           stand=datetime.now().strftime("%d.%m.%Y %H:%M")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
