#!/usr/bin/env python3
"""MailCom si BURIM SHTESE: firmat IT qe scraping-u i Google Maps s'i gjeti.

Leje: Dafina, 28.08.2026 ("shto firma qe i kem edhe ne mailcom ... qe si
kem gjet me scraping").

Rendi eshte i qellimshem: Maps mbetet baza, MailCom vetem mbush boshllequn.
Firmat e dala ketej NUK hyjne gati ne liste - ato shkruhen ne formatin
tone dhe pastaj kalojne te njejtin filter si te tjerat:

    zona32-lauf.py --firmen=<dosja e ketij skripti> --plz=... --lauf=...

Aty lexohet faqja, gjykohet profili IT, kontrollohet automatizimi dhe
lexohet impressum-i. Perndryshe ne nje liste do te perziheshin dy cilesi
te ndryshme dhe askush s'do ta dinte ciles t'i besoje.

Perdorimi:
    python werkzeuge/mailcom-zonen.py --zone=33
    python werkzeuge/mailcom-zonen.py --zone=34
"""
import glob
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

PROJEKT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJEKT))

QUELLE = Path(os.path.expanduser("~/Downloads/transfer-01a03903"))

ZONEN = {
    "33": {"plz": "plz-liste-oliver-zona33.txt",
           "laeufe": ["zona33-bielefeld-2026-08-25"]},
    "34": {"plz": "plz-liste-oliver-zona34.txt",
           "laeufe": ["zona34-kassel-2026-08-28"]},
    "35": {"plz": "plz-liste-oliver-zona35.txt",
           "laeufe": ["zona35-giessen-2026-08-28"]},
}

# Fjalet qe e bejne nje pershkrim dege kandidat per IT.
IT_WORTE = ("it-", "edv", "computer", "software", "netzwerk", "informat",
            "internet", "rechenzentr", "systemhaus", "daten", "web",
            "digital", "telekom")

# Pershkrime qe i kap fjala me siper por qe s'kane fare te bejne me IT.
# U gjeten duke i shikuar te 63 pershkrimet, jo me hamendje: "ge-WEB-ter"
# eshte rrobe e endur, "Tourist-INFORMAT-ion" eshte zyre turizmi, dhe
# "Freize-IT-" e kap fjala "it-". Buchfuehrung e thote vete ne kllapa se
# eshte PA sherbime te perpunimit te te dhenave.
NICHT_IT = {
    "Herstellung von gewebter Oberbekleidung für Damen und Mädchen",
    "Herstellung von gewebter Oberbekleidung für Herren und Knaben",
    "Herstellung von gewebter Wäsche (ohne Miederwaren)",
    "Weberei",
    "Kammgarnweberei",
    "Touristeninformation",
    "Freizeit- und Campingartikel",
    "Buchführung (ohne Datenverarbeitungsdienste)",
    "Digitaldruck",
}

BRANCHENFELDER = ("BranSuchBez", "Bezeichn_1", "Bezeichn_2", "Bezeichn3")


def log(*teile):
    print(f"[{datetime.now():%H:%M:%S}]", *teile, flush=True)


def domain_von(wert):
    ohne = re.sub(r"^https?://", "", str(wert or "").strip().lower())
    return re.sub(r"^www\.", "", ohne).split("/")[0].split("?")[0]


def name_schluessel(name):
    """Emri i firmes i sheshuar, qe 'Meier GmbH' dhe 'Meier  GmbH & Co. KG'
    te mos numerohen si dy firma te ndryshme."""
    text = str(name or "").casefold()
    for wort in ("gmbh & co. kg", "gmbh & co kg", "gmbh", "mbh", "ohg",
                 "kg", "ag", "e.k.", "ek", "gbr", "ug", "e.v.", "ev"):
        text = text.replace(wort, " ")
    return re.sub(r"[^a-zäöüß0-9]+", "", text)


def ist_it(reihe, i):
    treffer = []
    for feld in BRANCHENFELDER:
        if feld not in i:
            continue
        wert = str(reihe[i[feld]] or "").strip()
        if not wert or wert in NICHT_IT:
            continue
        if any(t in wert.casefold() for t in IT_WORTE):
            treffer.append(wert)
    return treffer


def bekannte_firmen(laeufe):
    """Cka kemi tashme nga scraping-u - sipas domain-it dhe sipas emrit."""
    domains, namen = set(), set()
    for ordner in laeufe:
        pfad = PROJEKT / "laeufe/leadquellen" / ordner / "firmen.json"
        if not pfad.exists():
            log(f"KUJDES: {ordner}/firmen.json s'ekziston ende - "
                f"asgje per te krahasuar prej andej.")
            continue
        for firma in json.loads(pfad.read_text(encoding="utf-8")):
            if firma.get("domain"):
                domains.add(firma["domain"].lower())
            schluessel = name_schluessel(firma.get("name"))
            if schluessel:
                namen.add((schluessel, str(firma.get("plz") or "").strip()))
    return domains, namen


def sammeln(kodet):
    """Nje zeri per firme. MailCom ka nje rresht per person, prandaj disa
    rreshta mund t'i takojne te njejtes firme."""
    import openpyxl

    firmen = {}
    for datei in sorted(glob.glob(str(QUELLE / "*.xlsx"))):
        wb = openpyxl.load_workbook(datei, read_only=True)
        for ws in wb.worksheets:
            zeiger = ws.iter_rows(values_only=True)
            kopf = list(next(zeiger))
            i = {k: n for n, k in enumerate(kopf)}
            if "PLZ" not in i:
                continue
            for reihe in zeiger:
                plz = str(reihe[i["PLZ"]] or "").strip().zfill(5)
                if plz not in kodet:
                    continue
                branchen = ist_it(reihe, i)
                if not branchen:
                    continue

                def wert(feld):
                    return (str(reihe[i[feld]] or "").strip()
                            if feld in i else "")

                name = " ".join(x for x in (wert("Firma1"), wert("Firma2"))
                                if x).strip()
                website = wert("Homepage")
                domain = domain_von(website)
                schluessel = domain or f"{name_schluessel(name)}|{plz}"
                if not schluessel.strip("|"):
                    continue

                eintrag = firmen.setdefault(schluessel, {
                    "name": name,
                    "website": (f"https://{domain}" if domain else ""),
                    "domain": domain,
                    "address": wert("Strasse"),
                    "plz": plz,
                    "ort": wert("Ort"),
                    "telefon": wert("Telefon"),
                    "vorhandene_email": wert("Email"),
                    "gf_name_liste": "",
                    "categories": [],
                    "ausserhalb_region": False,
                    "quellen": ["mailcom"],
                    "quelle": "mailcom",
                    "herkunft_detail": ("MailCom-Firmenadressen2024-25 "
                                        "(liste e blere, 4 dosje)"),
                    "mailcom_personen": [],
                })
                for b in branchen:
                    if b not in eintrag["categories"]:
                        eintrag["categories"].append(b)

                person = " ".join(x for x in (wert("Vorname"),
                                              wert("Nachname")) if x).strip()
                if person:
                    eintrag["mailcom_personen"].append({
                        "name": person,
                        "vorname": wert("Vorname"),
                        "nachname": wert("Nachname"),
                        "position": wert("Position"),
                        "anrede": wert("Anrede"),
                        "titel": wert("Titel"),
                    })
        wb.close()
        log(f"  u lexua: {os.path.basename(datei)} "
            f"(firma deri tash: {len(firmen)})")

    # Emrat e vendimmarresve i japim si ndihmese per lexuesin e impressum-it;
    # ai vendos vete, kjo eshte vetem nje shenje.
    for eintrag in firmen.values():
        eintrag["gf_name_liste"] = ", ".join(
            p["name"] for p in eintrag["mailcom_personen"][:5])
    return firmen


def main():
    zone = None
    for arg in sys.argv[1:]:
        if arg.startswith("--zone="):
            zone = arg.split("=", 1)[1]
    if zone not in ZONEN:
        sys.exit(f"Duhet --zone= nga: {', '.join(ZONEN)}")

    kodet = {r.strip() for r in
             (PROJEKT / "laeufe/leadquellen" / ZONEN[zone]["plz"])
             .read_text(encoding="utf-8").splitlines()
             if r.strip().isdigit() and len(r.strip()) == 5}

    log("=" * 62)
    log(f"MailCom si burim shtese - zona {zone} ({len(kodet)} kode)")
    log("=" * 62)

    firmen = sammeln(kodet)
    log(f"Firma IT te MailCom-it ne zonen {zone}: {len(firmen)}")

    domains, namen = bekannte_firmen(ZONEN[zone]["laeufe"])
    log(f"Firma qe i kemi tashme nga scraping-u: {len(domains)} domain, "
        f"{len(namen)} emra")

    neu, schon = [], []
    for eintrag in firmen.values():
        bekannt = (
            (eintrag["domain"] and eintrag["domain"] in domains)
            or (name_schluessel(eintrag["name"]), eintrag["plz"]) in namen)
        (schon if bekannt else neu).append(eintrag)

    ohne_web = sum(1 for e in neu if not e["website"])
    log(f"  tashme te njohura:  {len(schon)}")
    log(f"  TE REJA:            {len(neu)}")
    log(f"     prej tyre pa faqe interneti: {ohne_web} "
        f"(s'mund te kontrollohen dot)")

    ziel = (PROJEKT / "laeufe/leadquellen"
            / f"mailcom-zona{zone}-neu-{datetime.now():%Y%m%d}.json")
    ziel.write_text(json.dumps(neu, ensure_ascii=False, indent=1),
                    encoding="utf-8")
    log(f"U ruajt: {ziel.name}")
    log("")
    log("Hapi tjeter (kontrolli i njejte si te tjerat):")
    log(f"  .venv/bin/python werkzeuge/zona32-lauf.py \\")
    log(f"      --firmen={ziel} \\")
    log(f"      --plz={ZONEN[zone]['plz']} \\")
    log(f"      --lauf=zona{zone}-mailcom-{datetime.now():%Y-%m-%d}")


if __name__ == "__main__":
    main()
