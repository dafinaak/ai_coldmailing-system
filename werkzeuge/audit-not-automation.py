#!/usr/bin/env python3
"""Audit: stimmt "keine Automatisierung" bei den 2.881 Firmen?

Auftrag Dafinas vom 21.08.2026. Anlass: Nivako steht auf "no", verkauft
auf seiner Leistungsseite aber ausdrücklich n8n-Workflows und KI - die
Startseite erwähnt davon nichts. Verdacht: der Klassifikator liest NUR
die Startseite (pipeline.website.fetch_text holt genau eine Seite und
folgt keinem Link).

Dieses Skript prüft genau das nach, ohne irgendetwas zu verändern:
  1. feste Zufallsstichprobe (Startwert 20260821) aus dem "no"-Bestand,
  2. je Firma Startseite PLUS die Leistungs-/Lösungs-Unterseiten,
  3. Suche nach Begriffen für GESCHÄFTSprozess-Automatisierung, mit
     Textumfeld - damit ein Mensch das Umfeld lesen kann statt einem
     Treffer auf das blosse Wort zu vertrauen.

Es wird NUR gelesen: keine KI, keine bezahlte Schnittstelle, keine
Änderung an master.db, an Klassifikationen oder an Kampagnen.
"""
import json
import os
import random
import re
import sqlite3
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urljoin, urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests

from pipeline.website import _sichtbarer_text

STARTWERT = 20260821
UMFANG = 100
ZIEL = Path("laeufe/audit-not-automation-2026-08-21")

# Begriffe, die auf GESCHÄFTSprozess-Automatisierung als LEISTUNG deuten.
# Bewusst eng: "Automatisierung" allein steht NICHT drin, sonst fängt der
# Filter jede Firma mit "automatische Backups" ein.
SIGNALE = re.compile(
    r"(prozess[-\s]?automatis|geschäftsprozess|business process|"
    r"workflow[-\s]?automat|workflow-automatis|\bRPA\b|robotic process|"
    r"hyperautomation|\bn8n\b|zapier|make\.com|power[-\s]automate|"
    r"ki[-\s]?automatis|ai[-\s]?automat|ki[-\s]?agent|ai[-\s]?agent|"
    r"chatbot|automatisierungsberat|automatisierungslös|"
    r"abläufe automatis|prozesse automatis|abläufe zu automatis|"
    r"vorgänge automatis|low[-\s]?code|no[-\s]?code|\bBPM\b|"
    r"dokumentenmanagement|dms\b|digitale prozesse)", re.I)

# Wörter, die einen Treffer als INDUSTRIE-Automatisierung entlarven -
# die ist laut Zieldefinition ausdrücklich NICHT gemeint.
INDUSTRIE = re.compile(
    r"(\bSPS\b|\bPLC\b|steuerungstechnik|maschinenbau|fertigungsautomat|"
    r"anlagenbau|gebäudeautomat|prozessleittechnik|schaltschrank|"
    r"industrieautomat|robotik|antriebstechnik|sensorik)", re.I)

UNTERSEITEN = re.compile(
    r"(leistung|service|dienstleistung|angebot|lösung|loesung|produkt|"
    r"was-wir|kompetenz|portfolio|digitalisierung|automatisierung|"
    r"beratung|consulting|software|it-service|unternehmen)", re.I)


def hole(url: str, max_zeichen: int = 12000):
    try:
        a = requests.get(url, timeout=12,
                         headers={"User-Agent": "Mozilla/5.0 (Recherche)"})
        a.raise_for_status()
        return a.text, _sichtbarer_text(a.text)[:max_zeichen]
    except requests.RequestException:
        return "", ""


def unterseiten_finden(html: str, basis: str, hoechstens: int = 6) -> list:
    """Links, die nach Leistungs-/Lösungsseiten aussehen - gleiche Domain."""
    heim = urlparse(basis).netloc.lower().removeprefix("www.")
    gefunden, gesehen = [], set()
    for treffer in re.finditer(r'href=["\']([^"\']+)["\']', html, re.I):
        roh = treffer.group(1)
        if roh.startswith(("mailto:", "tel:", "#", "javascript:")):
            continue
        voll = urljoin(basis, roh)
        if urlparse(voll).netloc.lower().removeprefix("www.") != heim:
            continue
        pfad = urlparse(voll).path.lower()
        if not pfad or pfad == "/" or not UNTERSEITEN.search(pfad):
            continue
        voll = voll.split("#")[0]
        if voll in gesehen:
            continue
        gesehen.add(voll)
        gefunden.append(voll)
        if len(gefunden) >= hoechstens:
            break
    return gefunden


def umfeld(text: str, treffer) -> str:
    a, b = max(0, treffer.start() - 180), min(len(text), treffer.end() + 180)
    return " ".join(text[a:b].split())


def eine_firma(firma: dict) -> dict:
    seite = firma.get("website") or ""
    if not seite:
        return {**firma, "status": "keine_webseite", "funde": [], "seiten": 0}
    html, text = hole(seite)
    if not text.strip():
        return {**firma, "status": "startseite_unlesbar", "funde": [],
                "seiten": 0}

    texte = {seite: text}
    for unter in unterseiten_finden(html, seite):
        _, t = hole(unter, max_zeichen=10000)
        if t.strip():
            texte[unter] = t

    funde = []
    for url, t in texte.items():
        for m in SIGNALE.finditer(t):
            u = umfeld(t, m)
            funde.append({"url": url, "wort": m.group(0), "umfeld": u,
                          "industrie_naehe": bool(INDUSTRIE.search(u))})
    return {**firma, "status": "geprueft", "seiten": len(texte),
            "funde": funde}


def main() -> int:
    db = sqlite3.connect("daten/master.db")
    db.row_factory = sqlite3.Row
    pool = [dict(r) for r in db.execute(
        "SELECT kennung, name, domain, website, automation_check_reason "
        "FROM companies WHERE offers_automation_services='no' "
        "ORDER BY kennung")]
    db.close()
    print(f"Grundgesamtheit 'no': {len(pool)} Firmen")

    zufall = random.Random(STARTWERT)
    stichprobe = zufall.sample(pool, min(UMFANG, len(pool)))
    ZIEL.mkdir(parents=True, exist_ok=True)
    (ZIEL / "stichprobe.json").write_text(
        json.dumps({"startwert": STARTWERT, "umfang": len(stichprobe),
                    "grundgesamtheit": len(pool),
                    "firmen": stichprobe}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    print(f"Stichprobe gezogen (Startwert {STARTWERT}): {len(stichprobe)}")

    ergebnisse = []
    with ThreadPoolExecutor(max_workers=10) as p:
        for nr, e in enumerate(p.map(eine_firma, stichprobe), 1):
            ergebnisse.append(e)
            if nr % 10 == 0:
                print(f"  {nr}/{len(stichprobe)} geprüft")

    (ZIEL / "befunde.json").write_text(
        json.dumps(ergebnisse, ensure_ascii=False, indent=1),
        encoding="utf-8")
    mit = sum(1 for e in ergebnisse if e["funde"])
    print(f"\nfertig. Firmen mit mindestens einem Signal: {mit}"
          f" von {len(ergebnisse)}")
    print(f"abgelegt in {ZIEL}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
