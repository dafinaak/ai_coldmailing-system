#!/usr/bin/env python3
"""Lista perfundimtare e Zones 32 ne formatin IT-Liste-Emails-FERTIG,
plus kolonat qe i kerkoi Dafina: Position, lokacioni dhe burimi per
cdo fushe.

Merr rezultatin e gatshem te Dropcontact-it (ergebnisse.json) dhe
Anrede-n nga dosja qe e ndertoi anrede_spalte.aus_lauf(), qe teksti i
pershendetjes te jete saktesisht i njejti si te lista e vjeter.
"""
import json
import sys
from datetime import datetime
from pathlib import Path

PROJEKT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJEKT))

from pipeline.anrede_spalte import baue_anrede  # noqa: E402

ZONEN = {
    "32": {"lauf": "zona32-dropcontact-2026-08-21",
           "quellen": ["zona32-herford-2026-08-21",
                       "zona32-overpass-2026-08-21"]},
    "33": {"lauf": "zona33-dropcontact-2026-08-28",
           "quellen": ["zona33-bielefeld-2026-08-25"]},
    "34": {"lauf": "zona34-dropcontact-2026-08-28",
           "quellen": ["zona34-kassel-2026-08-28"]},
    "35": {"lauf": "zona35-dropcontact-2026-08-28",
           "quellen": ["zona35-giessen-2026-08-28"]},
}

# Nga cili mjet erdhi vertet secili vrapim. Kjo shkruhet ne kolonen
# "Quelle - Firma", prandaj duhet te jete e sakte per cdo vrapim - jo e
# hamendesuar nga emri i zones.
QUELLE_FIRMA = {
    "zona32-herford-2026-08-21": "Google Maps (Apify, 21.08.2026)",
    "zona32-overpass-2026-08-21": "Overpass/OSM (21.08.2026)",
    "zona33-bielefeld-2026-08-25": "Google Maps (Apify, 21.08.2026)",
    "zona34-kassel-2026-08-28": "Google Maps (Apify, 28.08.2026)",
    "zona35-giessen-2026-08-28": "Google Maps (Apify, 28.08.2026)",
}
ZONE = "32"
for _a in sys.argv[1:]:
    if _a.startswith("--zone="):
        ZONE = _a.split("=", 1)[1]
if ZONE not in ZONEN:
    sys.exit(f"Unbekannte Zone {ZONE!r}")
LAUF = PROJEKT / "laeufe/leadquellen" / ZONEN[ZONE]["lauf"]

KOPF = [
    "Nr", "Firma", "Person", "Position", "E-Mail", "Anrede", "Hinweis",
    "Telefon (Person)", "Telefon (Firma)", "Webseite", "PLZ", "Ort",
    "Quelle - Firma", "Quelle - Person", "Quelle - Position",
    "Quelle - E-Mail", "Quelle - Telefon",
]

KOPF_FUELL = "FF1F3A56"
GELB = "FFF8ECD6"
GRUEN = "FFDFF0E8"

# Etiketa qe s'jane tituj pune, por fraza ligjore te impressum-it.
NICHT_TITEL = ("vertreten durch", "vertretungsberechtigt", "inhaltlich",
               "verantwortlich f", "dienstanbieter", "veranwortlich")
AUFSICHT = ("aufsichtsrat",)


def rolle_saeubern(rohe_rolle):
    """Kthen (position_e_paster, shenim). Asgje nuk shpiket: nese teksti
    s'eshte titull pune, kolona mbetet bosh dhe arsyeja shkon te Hinweis."""
    text = (rohe_rolle or "").strip()
    niedrig = text.casefold()
    if not text:
        return "", "Position nicht im Impressum genannt"
    if any(a in niedrig for a in AUFSICHT):
        return "", f"Aufsichtsrat ('{text}') - kein Einkaufsentscheider"
    if any(n in niedrig for n in NICHT_TITEL):
        return "", (f"Impressum sagt nur '{text}' - rechtliche Formel, "
                    f"keine Funktionsbezeichnung")
    return text, ""


def firmen_index():
    """Kodi postar, qyteti dhe pozita vijne nga vrapimet e mbledhjes."""
    index = {}
    for ordner in ZONEN[ZONE]["quellen"]:
        pfad = PROJEKT / "laeufe/leadquellen" / ordner / "firmen.json"
        if not pfad.exists():
            continue
        for firma in json.loads(pfad.read_text(encoding="utf-8")):
            index[(firma.get("domain") or firma.get("name") or "").lower()] = {
                "plz": firma.get("plz") or "",
                "ort": firma.get("ort") or "",
                "lauf": ordner,
            }
    return index


def bauen():
    import openpyxl
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    daten = json.loads((LAUF / "ergebnisse.json").read_text(encoding="utf-8"))
    index = firmen_index()

    wb = openpyxl.Workbook()
    blatt = wb.active
    blatt.title = "Versandfertig"
    blatt.append(KOPF)

    # I njejti njeri te dy firma motra do te merrte DY email nga e njejta
    # fushate - pikerisht gabimi qe u ndal me 17.08.2026. Nje person, nje
    # rresht: mbahet ai me pozite te shkruar, perndryshe i pari.
    def person_schluessel(firma):
        lead = (firma.get("leads") or [None])[0] or {}
        return (f"{lead.get('first_name','')} "
                f"{lead.get('last_name','')}").strip().casefold()

    beste = {}
    doppelte = []
    for firma in daten:
        if not (firma.get("leads") or [None])[0]:
            continue
        schluessel = person_schluessel(firma)
        if not schluessel:
            continue
        hat_position = bool(rolle_saeubern(firma.get("rolle"))[0])
        vorher = beste.get(schluessel)
        if vorher is None:
            beste[schluessel] = firma
        elif hat_position and not bool(rolle_saeubern(vorher.get("rolle"))[0]):
            doppelte.append((schluessel, vorher))
            beste[schluessel] = firma
        else:
            doppelte.append((schluessel, firma))
    if doppelte:
        print(f"Persona te dyfishte te hequr: {len(doppelte)}")
        for schluessel, firma in doppelte:
            print(f"    hequr: {firma.get('name')} "
                  f"({(firma.get('leads') or [{}])[0].get('email')})")
    daten = [f for f in daten if f in beste.values()]

    kontrolle = []
    nummer = 0
    ohne_position = 0
    for firma in daten:
        lead = (firma.get("leads") or [None])[0]
        if not lead:
            continue
        nummer += 1
        person = f"{lead.get('first_name','')} {lead.get('last_name','')}".strip()
        anrede, grund = baue_anrede(person)

        position, positions_hinweis = rolle_saeubern(firma.get("rolle"))
        if not position:
            ohne_position += 1

        hinweise = []
        if grund != "maennlich":
            hinweise.append(grund)
        if positions_hinweis:
            hinweise.append(positions_hinweis)
        for notiz in lead.get("notizen") or []:
            hinweise.append(str(notiz))
        hinweis = " | ".join(hinweise)
        if hinweise:
            kontrolle.append((firma.get("name", ""), person, hinweis))

        ort_daten = index.get(
            (firma.get("domain") or firma.get("name") or "").lower(), {})
        quelle_firma = QUELLE_FIRMA.get(ort_daten.get("lauf", ""), "?")

        blatt.append([
            nummer, firma.get("name", ""), person, position,
            lead.get("email", ""), anrede, hinweis,
            firma.get("telefon", ""), firma.get("telefon", ""),
            firma.get("website", ""),
            ort_daten.get("plz", ""), ort_daten.get("ort", ""),
            quelle_firma, "Impressum + KI",
            "Impressum (wörtlich)" if position else "—",
            "Dropcontact (gebaut + verifiziert)",
            "Impressum" if firma.get("telefon") else "—",
        ])

    for zelle in blatt[1]:
        zelle.font = Font(bold=True, color="FFFFFFFF", size=10)
        zelle.fill = PatternFill("solid", fgColor=KOPF_FUELL)
        zelle.alignment = Alignment(vertical="center", wrap_text=True)
    blatt.row_dimensions[1].height = 30
    blatt.freeze_panes = "A2"
    blatt.auto_filter.ref = blatt.dimensions

    breiten = [5, 36, 24, 26, 36, 22, 46, 20, 20, 34, 8, 18,
               30, 18, 22, 32, 14]
    for spalte, breite in enumerate(breiten, 1):
        blatt.column_dimensions[get_column_letter(spalte)].width = breite

    for rreshti in range(2, blatt.max_row + 1):
        zelle = blatt.cell(rreshti, 4)          # Position
        zelle.fill = PatternFill(
            "solid", fgColor=GRUEN if zelle.value else GELB)

    kb = wb.create_sheet("Zur Kontrolle")
    kb.append(["Firma", "Person", "Warum auf dieser Liste"])
    for reihe in kontrolle:
        kb.append(list(reihe))
    for zelle in kb[1]:
        zelle.font = Font(bold=True, color="FFFFFFFF", size=10)
        zelle.fill = PatternFill("solid", fgColor=KOPF_FUELL)
    for spalte, breite in zip("ABC", [36, 26, 90]):
        kb.column_dimensions[spalte].width = breite

    stempel = datetime.now().strftime("%Y%m%d-%H%M")
    ziel = PROJEKT / f"IT-Liste-Emails-Zona{ZONE}-FERTIG-{stempel}.xlsx"
    wb.save(ziel)
    return ziel, nummer, ohne_position, len(kontrolle)


if __name__ == "__main__":
    ziel, rreshta, pa_pozite, kontrolle = bauen()
    print(f"DOSJA:            {ziel}")
    print(f"Rreshta:          {rreshta}")
    print(f"Me pozite:        {rreshta - pa_pozite}")
    print(f"Pa pozite:        {pa_pozite}")
    print(f"Zur Kontrolle:    {kontrolle}")
