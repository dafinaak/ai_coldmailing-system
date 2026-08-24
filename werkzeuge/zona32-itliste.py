#!/usr/bin/env python3
"""Lista e gatshme "IT-Liste" per Zonen 32, ne formatin e tabeles se
Dafines (Nr / Firma / Person / E-Mail / Anrede / Telefon / Webseite),
plus poziten dhe burimin per çdo fushe.

Dy flete:
  1. "IT-Liste"  - nje rresht per kontakt, vetem firmat e pranueshme
                   qe kane vendimmarres.
  2. "Quellen"   - cili mjet e dha çfare. Kjo eshte pergjigjja per
                   pyetjen "ne cilin mjet te mbeshtetemi ne te ardhmen".

E-Mail mbetet bosh derisa te ekzekutohet Dropcontact - kjo shihet edhe
te flete "Quellen".
"""
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

PROJEKT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJEKT))

LAEUFE = ["zona32-herford-2026-08-21", "zona32-overpass-2026-08-21"]

KOPF = [
    "Nr", "Firma", "Person", "Position", "E-Mail", "Anrede", "Hinweis",
    "Telefon (Person)", "Telefon (Firma)", "Webseite", "PLZ", "Ort",
    "Quelle - Firma", "Quelle - Person", "Quelle - Position",
    "Quelle - E-Mail", "Quelle - Telefon",
    "Automation", "Vollständigkeit %",
]

KOPF_FUELL = "FF1F3A56"
GRUEN = "FFDFF0E8"
GELB = "FFF8ECD6"


def laufdaten():
    firmen = {}
    for ordner in LAEUFE:
        pfad = PROJEKT / "laeufe/leadquellen" / ordner / "firmen.json"
        if not pfad.exists():
            continue
        for firma in json.loads(pfad.read_text(encoding="utf-8")):
            firma["_lauf"] = ordner
            firmen[(firma.get("domain") or firma.get("name") or "").lower()] = firma
    return firmen


def quellenblatt(wb, firmen, zeilen_gesamt, personen_gesamt):
    """Cili mjet e dha çfare - baza per vendimin e ardhshem."""
    from openpyxl.styles import Alignment, Font, PatternFill

    blatt = wb.create_sheet("Quellen")
    blatt.append(["Tool", "Rolle im Ablauf", "Firmen", "Entscheider",
                  "Positionen", "Telefone", "E-Mails", "Kosten (USD)",
                  "Status"])

    maps = [f for f in firmen.values() if f["_lauf"].startswith("zona32-herford")]
    over = [f for f in firmen.values() if "overpass" in f["_lauf"]]
    imp_personen = [p for f in firmen.values() for p in f.get("entscheider") or []
                    if p.get("quelle") == "impressum"]
    imp_rollen = [p for p in imp_personen if (p.get("rolle") or "").strip()]
    imp_tel = [p for p in imp_personen if (p.get("telefon") or "").strip()]

    kosten = 0.0
    for ordner in LAEUFE:
        pfad = PROJEKT / "laeufe/leadquellen" / ordner / "kosten.json"
        if pfad.exists():
            kosten += json.loads(pfad.read_text(encoding="utf-8"))["kosten_usd"]

    rijet = [
        ["Google Maps (Apify)", "Firmensuche + Adresse + Telefon",
         len(maps), 0, 0, sum(1 for f in maps if (f.get("telefon") or "").strip()),
         0, 0.00, "bereits bezahlt (Datensatz 21.08.)"],
        ["Overpass / OSM", "Firmensuche (Lückenfüller)",
         len(over), 0, 0, sum(1 for f in over if (f.get("telefon") or "").strip()),
         0, 0.00, "kostenlos, gelaufen"],
        ["Impressum + KI", "Entscheider, Position, Telefon",
         0, len(imp_personen), len(imp_rollen), len(imp_tel), 0,
         round(kosten, 4), "gelaufen - stärkste Quelle für Personen"],
        ["Dropcontact", "persönliche E-Mail (bauen + prüfen)",
         0, 0, 0, 0, 0, 0.00, "NICHT gelaufen - wartet auf Freigabe"],
        ["Hunter", "E-Mail-Fallback", 0, 0, 0, 0, 0, 0.00,
         "NICHT gelaufen"],
        ["Apollo / Datagma", "Mobilnummern", 0, 0, 0, 0, 0, 0.00,
         "kein Zugang - Test offen"],
        ["Gelbe Seiten", "Firmensuche + allgemeine E-Mail",
         0, 0, 0, 0, 0, 0.00, "NICHT gelaufen - Apify-Budget"],
        ["North Data", "Registrierte Geschäftsführer",
         0, 0, 0, 0, 0, 0.00, "nicht gebaut, kein Konto"],
    ]
    for rreshti in rijet:
        blatt.append(rreshti)

    blatt.append([])
    blatt.append(["SUMME", "", len(firmen), personen_gesamt,
                  len(imp_rollen), len(imp_tel), 0, round(kosten, 4),
                  f"{zeilen_gesamt} Zeilen in der IT-Liste"])

    for zelle in blatt[1]:
        zelle.font = Font(bold=True, color="FFFFFFFF", size=10)
        zelle.fill = PatternFill("solid", fgColor=KOPF_FUELL)
        zelle.alignment = Alignment(vertical="center", wrap_text=True)
    blatt.row_dimensions[1].height = 30
    for spalte, breite in zip("ABCDEFGHI",
                              [24, 38, 10, 12, 12, 11, 10, 13, 40]):
        blatt.column_dimensions[spalte].width = breite
    letzte = blatt.max_row
    for zelle in blatt[letzte]:
        zelle.font = Font(bold=True)
    return blatt


def bauen():
    from pipeline import master_db
    import openpyxl
    from openpyxl.styles import Alignment, Font, PatternFill

    firmen = laufdaten()
    db = sqlite3.connect(PROJEKT / master_db.DB_NAME)
    db.row_factory = sqlite3.Row

    wb = openpyxl.Workbook()
    blatt = wb.active
    blatt.title = "IT-Liste"
    blatt.append(KOPF)

    nummer = 0
    personen_gesamt = 0
    for schluessel, firma in sorted(firmen.items(),
                                    key=lambda x: (x[1].get("plz") or "",
                                                   x[1].get("name") or "")):
        if not firma.get("profil_passt"):
            continue
        if firma.get("offers_automation_services") != "no":
            continue
        personen = firma.get("entscheider") or []
        if not personen:
            continue

        satz = db.execute(
            "SELECT completeness FROM companies WHERE kennung=?",
            (schluessel,)).fetchone()
        vollstaendig = satz["completeness"] if satz else ""
        quelle_firma = ("Google Maps (Apify, 21.08.2026)"
                        if firma["_lauf"].startswith("zona32-herford")
                        else "Overpass/OSM (21.08.2026)")

        for person in personen:
            personen_gesamt += 1
            nummer += 1
            rolle = (person.get("rolle") or "").strip()
            tel_person = (person.get("telefon") or "").strip()
            blatt.append([
                nummer, firma.get("name", ""), person.get("name", ""),
                rolle or "", "", "", "",
                tel_person, firma.get("telefon", ""),
                firma.get("website", ""), firma.get("plz", ""),
                firma.get("ort", ""),
                quelle_firma,
                "Impressum + KI" if person.get("quelle") == "impressum"
                else (person.get("quelle") or ""),
                "Impressum (wörtlich)" if rolle else "",
                "— Dropcontact noch nicht gelaufen —",
                "Impressum" if tel_person else "",
                firma.get("offers_automation_services", ""),
                vollstaendig,
            ])

    for zelle in blatt[1]:
        zelle.font = Font(bold=True, color="FFFFFFFF", size=10)
        zelle.fill = PatternFill("solid", fgColor=KOPF_FUELL)
        zelle.alignment = Alignment(vertical="center", wrap_text=True)
    blatt.row_dimensions[1].height = 30
    blatt.freeze_panes = "A2"
    blatt.auto_filter.ref = blatt.dimensions

    breiten = [5, 36, 24, 26, 30, 20, 14, 20, 20, 32, 8, 18,
               30, 18, 20, 32, 14, 12, 14]
    from openpyxl.utils import get_column_letter
    for spalte, breite in enumerate(breiten, 1):
        blatt.column_dimensions[get_column_letter(spalte)].width = breite

    # E-Mail bosh = e verdhe, qe te duket menjehere se mungon.
    for rreshti in range(2, blatt.max_row + 1):
        if not blatt.cell(rreshti, 5).value:
            blatt.cell(rreshti, 5).fill = PatternFill("solid", fgColor=GELB)
        if blatt.cell(rreshti, 4).value:
            blatt.cell(rreshti, 4).fill = PatternFill("solid", fgColor=GRUEN)

    quellenblatt(wb, firmen, blatt.max_row - 1, personen_gesamt)

    stempel = datetime.now().strftime("%Y%m%d-%H%M")
    ziel = PROJEKT / f"IT-Liste-Zona32-{stempel}.xlsx"
    wb.save(ziel)
    return ziel, blatt.max_row - 1, personen_gesamt


if __name__ == "__main__":
    ziel, zeilen, personen = bauen()
    print(f"DOSJA:    {ziel}")
    print(f"Rreshta:  {zeilen}")
    print(f"Persona:  {personen}")
