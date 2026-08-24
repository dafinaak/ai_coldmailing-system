#!/usr/bin/env python3
"""Eksport Excel per Zonen 32 (Herford) - Hapi 1.

Nje rresht per kontakt. Firmat pa vendimmarres marrin nje rresht me
fushat e personit bosh, qe asnje firma te mos zhduket nga pamja.

Kolonat jane ato qe i kerkoi Dafina me 21.08.2026, plus fushat e tjera
qe i kemi. Emri i dosjes mban vulen e kohes - asnje eksport i vjeter nuk
mbishkruhet.

Perdorimi:
    python werkzeuge/zona32-export.py            # vetem zona 32
    python werkzeuge/zona32-export.py --alle     # e gjithe baza
"""
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

PROJEKT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJEKT))

PLZ_LISTE = PROJEKT / "laeufe/leadquellen/plz-liste-oliver-zona32.txt"
LAEUFE = [
    PROJEKT / "laeufe/leadquellen/zona32-herford-2026-08-21",
    PROJEKT / "laeufe/leadquellen/zona32-overpass-2026-08-21",
]

KOPF = [
    "Nr",
    "Company", "Website", "PLZ", "PLZ Confirmed", "City", "Street", "Country",
    "Company Phone", "Email (general)",
    "Decision Maker", "Position", "Personal Email",
    "Direct Phone", "Mobile Phone",
    "Source - Company", "Source - Decision Maker", "Source - Email",
    "Source - Phone",
    "Automation Status", "Automation Reason",
    "IT Profile", "IT Profile Reason",
    "Campaign Eligibility", "Ineligibility Reason",
    "Sector", "Categories", "Completeness %", "Checked At",
]

# Ngjyrat: koke e erret, rreshta te alternuar, gjelber/kuq per statusin.
KOPF_FUELL = "FF1F3A56"
GRUEN = "FFDFF0E8"
ROT = "FFF8E3E0"
GELB = "FFF8ECD6"


def plz_der_zone():
    return {r.strip() for r in PLZ_LISTE.read_text(encoding="utf-8").splitlines()
            if r.strip().isdigit() and len(r.strip()) == 5}


def profil_daten():
    """Gjykimi i profilit IT nga dosjet e vrapimeve - nuk ruhet ne baze.
    Kthen edhe listen e firmave qe i takojne zones, qe eksporti te mos
    varet vetem nga kodi postar (OSM shpesh s'e ka fare)."""
    daten = {}
    for lauf in LAEUFE:
        pfad = lauf / "firmen.json"
        if not pfad.exists():
            continue
        for firma in json.loads(pfad.read_text(encoding="utf-8")):
            schluessel = (firma.get("domain") or firma.get("name") or "").lower()
            daten[schluessel] = {
                "passt": firma.get("profil_passt"),
                "grund": firma.get("profil_grund", ""),
                "typ": firma.get("profil_typ", ""),
                "impressum_grund": firma.get("impressum_grund", ""),
                # Mungon vetem te vrapimi i pare (Maps) - aty cdo firme e
                # kishte kodin, prandaj parazgjedhja True.
                "plz_bestaetigt": firma.get("plz_bestaetigt", True),
                "lauf": lauf.name,
            }
    return daten


def bauen(nur_zone=True):
    from pipeline import master_db

    zahlen = master_db.bauen(str(PROJEKT))
    print(f"Baza u rindertua: {zahlen}")

    db = sqlite3.connect(PROJEKT / master_db.DB_NAME)
    db.row_factory = sqlite3.Row
    zone = plz_der_zone()
    profile = profil_daten()

    import openpyxl
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    wb = openpyxl.Workbook()
    blatt = wb.active
    blatt.title = "Zona 32 - Hapi 1"
    blatt.append(KOPF)

    zeilen = firmen = mit_person = 0
    for firma in db.execute("SELECT * FROM companies ORDER BY plz, name"):
        schluessel_firma = (firma["domain"] or firma["name"] or "").lower()
        in_zone = ((firma["plz"] or "") in zone
                   or schluessel_firma in profile)
        if nur_zone and not in_zone:
            continue
        firmen += 1
        quellen = db.execute(
            """SELECT provider, herkunft, collected_at FROM company_sources
               WHERE company_id=? ORDER BY id""", (firma["id"],)).fetchall()
        quelle_firma = "; ".join(
            f"{q['provider']} ({q['herkunft']}, {(q['collected_at'] or '?')[:10]})"
            for q in quellen[:3]) or "?"

        personen = db.execute(
            """SELECT * FROM decision_makers WHERE company_id=?
               ORDER BY id""", (firma["id"],)).fetchall()
        profil = profile.get(schluessel_firma, {})
        if profil.get("passt") is True:
            profil_text = "yes"
        elif profil.get("passt") is False:
            profil_text = "no"
        else:
            profil_text = "not_checked"

        if (firma["plz"] or "") in zone:
            plz_ok = "yes"
        elif profil.get("plz_bestaetigt") is False:
            plz_ok = "no (OSM bbox)"
        else:
            plz_ok = "other branch"

        basis = [
            firmen,
            firma["name"], firma["website"], firma["plz"], plz_ok,
            firma["ort"], firma["strasse"], firma["land"],
            firma["telefon"], firma["email_allgemein"],
        ]
        schwanz = [
            firma["offers_automation_services"],
            (firma["automation_check_reason"] or "")[:300],
            profil_text, (profil.get("grund") or "")[:300],
            "yes" if firma["campaign_eligible"] else "no",
            firma["ineligibility_reason"] or "",
            firma["sektor"], firma["keywords"],
            firma["completeness"], (firma["automation_checked_at"] or "")[:19],
        ]

        if personen:
            mit_person += 1
            for person in personen:
                blatt.append(basis + [
                    person["name"], person["rolle"] or "",
                    person["email"] or "",
                    person["telefon"] or "", "",
                    quelle_firma, person["quelle"] or "",
                    "dropcontact (ende nuk eshte ekzekutuar)"
                    if not person["email"] else person["quelle"],
                    "impressum" if person["telefon"] else "",
                ] + schwanz)
                zeilen += 1
        else:
            blatt.append(basis + [
                "", "", "", "", "",
                quelle_firma, "",
                "", "",
            ] + schwanz)
            zeilen += 1

    # ---------------------------------------------------------- pamja
    koke_fuell = PatternFill("solid", fgColor=KOPF_FUELL)
    for zelle in blatt[1]:
        zelle.font = Font(bold=True, color="FFFFFFFF", size=10)
        zelle.fill = koke_fuell
        zelle.alignment = Alignment(vertical="center", wrap_text=True)
    blatt.row_dimensions[1].height = 30
    blatt.freeze_panes = "A2"
    blatt.auto_filter.ref = blatt.dimensions

    breiten = [5, 34, 32, 8, 14, 16, 26, 12, 18, 26, 22, 22, 26, 18,
               14, 40, 18, 30, 14, 14, 46, 11, 46, 12, 34, 26, 30, 8, 18]
    for nummer, breite in enumerate(breiten[:len(KOPF)], 1):
        blatt.column_dimensions[get_column_letter(nummer)].width = breite

    auto_spalte = KOPF.index("Automation Status") + 1
    eig_spalte = KOPF.index("Campaign Eligibility") + 1
    for nummer in range(2, blatt.max_row + 1):
        wert = blatt.cell(nummer, auto_spalte).value
        farbe = {"no": GRUEN, "yes": ROT, "uncertain": GELB}.get(wert)
        if farbe:
            blatt.cell(nummer, auto_spalte).fill = PatternFill(
                "solid", fgColor=farbe)
        if blatt.cell(nummer, eig_spalte).value == "yes":
            blatt.cell(nummer, eig_spalte).fill = PatternFill(
                "solid", fgColor=GRUEN)
    for nummer in range(1, blatt.max_column + 1):
        blatt.cell(1, nummer).alignment = Alignment(
            vertical="center", wrap_text=True)
        get_column_letter(nummer)

    stempel = datetime.now().strftime("%Y%m%d-%H%M")
    name = ("zona32-herford" if nur_zone else "master-komplett")
    ziel = PROJEKT / f"{name}-hapi1-{stempel}.xlsx"
    wb.save(ziel)
    return ziel, zeilen, firmen, mit_person


if __name__ == "__main__":
    nur_zone = "--alle" not in sys.argv[1:]
    ziel, zeilen, firmen, mit_person = bauen(nur_zone)
    print()
    print(f"DOSJA:            {ziel}")
    print(f"Rreshta:          {zeilen}")
    print(f"Firma:            {firmen}")
    print(f"Firma me person:  {mit_person}")
