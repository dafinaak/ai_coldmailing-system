"""Fill the salutation column ("Anrede") for a checked dispatch list.

One-off helper for the IT-Dienstleister campaign (step 5 of
docs/bauplan-versandstart-it-dienstleister.md). Reads the checked
Excel list, picks one contact person per company and writes the
salutation that Instantly later inserts as {{anrede}}:

    "Herr Meyer"   -> "Guten Tag Herr Meyer,"
    "Frau Kruse"   -> "Guten Tag Frau Kruse,"
    "Malte Ehlers" -> "Guten Tag Malte Ehlers,"   (neutral fallback)

Rule from the build plan: better neutral than wrong. Every first name
that is not clearly male or female stays neutral and is listed on a
separate review sheet.

IMPORTANT - order matters. The salutation has to be built from the
person the data run actually reached, not from the first manager named
on the company website. Those two differ often enough to matter: in the
20-company test run 3 of 18 contacts would have been greeted with the
wrong name, because the reachable address belonged to the second or
third manager. That is why the build plan puts this step AFTER the data
run. Use "aus-lauf" for the real thing; the plain Excel mode below is
only a draft for a list that has no addresses yet.

Usage:
    python -m pipeline.anrede_spalte <eingabe.xlsx> <ausgabe.xlsx>
    python -m pipeline.anrede_spalte aus-lauf <ergebnisse.json> <ziel.xlsx>
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import openpyxl

# First names that are read as female. Everything not listed here and
# not in UNKLAR is treated as male - the list below was checked by hand
# against the actual contacts of this dispatch list.
WEIBLICH = {
    "annika", "beate", "claudia", "frauke", "heike", "inka", "kerstin",
    "melanie", "miryam", "nadine", "natascha", "nina", "patricia",
    "silke", "simone", "ursula",
}

# Unisex or otherwise unclear - these always stay neutral.
UNKLAR = {"alyx", "janis", "kay"}

# Whole words that show the cell holds a role or company, not a person.
# Matched word by word - a substring check would wrongly hit real names
# such as "Hagen" or "Nagel".
KEIN_NAME = {
    "präsident", "praesident", "geschäftsführer", "geschaeftsfuehrer",
    "hochschule", "gmbh", "ag", "vorstand", "inhaber", "e.k.", "kg",
}


def waehle_person(gf_feld: str) -> tuple[str, int]:
    """Return the contact person to address, plus how many were listed."""
    teile = [t.strip() for t in str(gf_feld or "").split(";") if t.strip()]
    if not teile:
        return "", 0
    return teile[0], len(teile)


def baue_anrede(person: str) -> tuple[str, str]:
    """Return (anrede, grund). Empty anrede means: needs a human."""
    wort = person.split()
    if len(wort) < 2:
        return "", "kein vollstaendiger Name"
    woerter = {w.strip(".,").lower() for w in person.split()}
    if woerter & KEIN_NAME:
        return "", "sieht nach Rolle/Firma aus, nicht nach Person"

    vorname = wort[0]
    nachname = " ".join(wort[1:])
    schluessel = vorname.lower().split("-")[0]

    if schluessel in UNKLAR:
        return f"{vorname} {nachname}", "Vorname nicht eindeutig - neutral"
    if schluessel in WEIBLICH:
        return f"Frau {nachname}", "weiblich"
    return f"Herr {nachname}", "maennlich"


def main(eingabe: Path, ausgabe: Path) -> None:
    wb = openpyxl.load_workbook(eingabe)
    ws = wb.worksheets[0]

    kopf = [c.value for c in ws[1]]
    spalte_gf = kopf.index("Geschäftsführer") + 1
    neue_spalte = ws.max_column + 1
    ws.cell(row=1, column=neue_spalte, value="Anrede")
    ws.cell(row=1, column=neue_spalte + 1, value="Anrede-Hinweis")

    pruefen = []
    zaehler = {"Herr": 0, "Frau": 0, "neutral": 0, "offen": 0}

    for zeile in range(2, ws.max_row + 1):
        gf = ws.cell(row=zeile, column=spalte_gf).value
        firma = ws.cell(row=zeile, column=2).value
        if firma is None:
            continue
        person, anzahl = waehle_person(gf)
        anrede, grund = baue_anrede(person)

        hinweis = ""
        if anzahl > 1:
            hinweis = f"{anzahl} Namen im Impressum - angeschrieben wird {person}"
        if not anrede:
            zaehler["offen"] += 1
            hinweis = f"BITTE PRUEFEN: {grund}"
            pruefen.append((firma, gf, grund))
        elif anrede.startswith("Herr "):
            zaehler["Herr"] += 1
        elif anrede.startswith("Frau "):
            zaehler["Frau"] += 1
            pruefen.append((firma, person, "als weiblich eingestuft"))
        else:
            zaehler["neutral"] += 1
            pruefen.append((firma, person, grund))

        ws.cell(row=zeile, column=neue_spalte, value=anrede)
        ws.cell(row=zeile, column=neue_spalte + 1, value=hinweis)

    blatt = wb.create_sheet("Anrede zur Kontrolle")
    blatt.append(["Firma", "Name", "Warum auf dieser Liste"])
    for reihe in pruefen:
        blatt.append(list(reihe))

    wb.save(ausgabe)
    print(f"geschrieben: {ausgabe}")
    print(
        f"Herr: {zaehler['Herr']} | Frau: {zaehler['Frau']} | "
        f"neutral: {zaehler['neutral']} | offen: {zaehler['offen']}"
    )
    print(f"zur Kontrolle vorgelegt: {len(pruefen)}")


def _domain(wert: str) -> str:
    ohne = re.sub(r"^https?://", "", str(wert or "").strip().lower())
    return re.sub(r"^www\.", "", ohne).split("/")[0]


def aus_lauf(ergebnisse: Path, ziel: Path) -> None:
    """Build the salutation from the contact the data run actually found.

    Also collects everything that wants a human glance onto one sheet:
    an uncertain salutation, a collective address with nobody behind it,
    a name the provider reads differently than the website does, and a
    mail domain that is not the company's own.
    """
    daten = json.loads(ergebnisse.read_text(encoding="utf-8"))
    firmen = daten["firmen"] if isinstance(daten, dict) else daten

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Versandfertig"
    ws.append([
        "Nr", "Firma", "Person", "E-Mail", "Anrede", "Hinweis",
        "Telefon", "Webseite",
    ])

    offen = []
    zaehler = {"Herr": 0, "Frau": 0, "neutral": 0, "offen": 0}
    nummer = 0

    for firma in firmen:
        leads = firma.get("leads") or []
        name = firma.get("name")
        if not leads:
            continue
        lead = leads[0]
        person = f"{lead.get('first_name', '')} {lead.get('last_name', '')}".strip()
        mail = lead.get("email", "")
        hinweise = []

        if person:
            anrede, grund = baue_anrede(person)
            if grund != "maennlich":
                hinweise.append(grund)
        else:
            # info@ without a person behind it: nobody can be greeted by
            # name here. A human decides how these are addressed - the
            # empty cell makes the upload refuse them until then.
            anrede = ""
            hinweise.append("BITTE ENTSCHEIDEN: Sammeladresse ohne Person")

        for notiz in lead.get("notizen") or []:
            hinweise.append(str(notiz))

        mail_domain = _domain(mail.split("@")[-1]) if "@" in mail else ""
        firmen_domain = _domain(firma.get("domain") or firma.get("website"))
        if mail_domain and firmen_domain and mail_domain != firmen_domain:
            hinweise.append(
                f"Mail-Domain {mail_domain} weicht von der Webseite "
                f"{firmen_domain} ab")

        hinweis = " | ".join(hinweise)
        if not anrede:
            zaehler["offen"] += 1
        elif anrede.startswith("Herr "):
            zaehler["Herr"] += 1
        elif anrede.startswith("Frau "):
            zaehler["Frau"] += 1
            hinweise.append("als weiblich eingestuft")
        else:
            zaehler["neutral"] += 1

        if hinweise:
            offen.append((name, person or mail, " | ".join(hinweise)))

        nummer += 1
        ws.append([
            nummer, name, person, mail, anrede, hinweis,
            firma.get("telefon"), firma.get("website"),
        ])

    blatt = wb.create_sheet("Zur Kontrolle")
    blatt.append(["Firma", "Person / Adresse", "Warum auf dieser Liste"])
    for reihe in offen:
        blatt.append(list(reihe))

    wb.save(ziel)
    print(f"Kontakte: {nummer} -> {ziel}")
    print(
        f"Herr: {zaehler['Herr']} | Frau: {zaehler['Frau']} | "
        f"neutral: {zaehler['neutral']} | offen: {zaehler['offen']}"
    )
    print(f"zur Kontrolle vorgelegt: {len(offen)}")


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "aus-lauf":
        aus_lauf(Path(sys.argv[2]), Path(sys.argv[3]))
    elif len(sys.argv) == 3:
        main(Path(sys.argv[1]), Path(sys.argv[2]))
    else:
        raise SystemExit(__doc__)
