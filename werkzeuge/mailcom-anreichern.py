#!/usr/bin/env python3
"""MailCom als ANREICHERUNG: Mitarbeiterzahl fuer Firmen, die wir schon haben.

Olivers DataWarehouse-Liste hat ein Feld "Anzahl Mitarbeiter". Es war zu
100% leer, obwohl die Angabe seit dem 28.08.2026 auf der Platte liegt:
MailCom hat eine Spalte "Anz_Mitarb". werkzeuge/mailcom-zonen.py hat sie
nur nicht mitgenommen, weil es damals um das Finden neuer Firmen ging.

Dieses Werkzeug geht den umgekehrten Weg: es liest MailCom noch einmal und
traegt Mitarbeiterzahl und Rechtsform in die Firmen ein, die wir BEREITS
haben - egal aus welcher Quelle sie kamen. Getroffen wird ueber die
Domain, sonst ueber Firmenname + Postleitzahl.

Kostet nichts: die vier Excel-Dateien liegen lokal.

Geschrieben wird in die firmen.json der Laeufe, nicht in master.db - die
wird ohnehin daraus neu gebaut.

Perdorimi:
    python werkzeuge/mailcom-anreichern.py            # provë, pa shkruar
    python werkzeuge/mailcom-anreichern.py --schreiben
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


def log(*teile):
    print(f"[{datetime.now():%H:%M:%S}]", *teile, flush=True)


def domain_von(wert):
    ohne = re.sub(r"^https?://", "", str(wert or "").strip().lower())
    return re.sub(r"^www\.", "", ohne).split("/")[0].split("?")[0]


def name_schluessel(name):
    text = str(name or "").casefold()
    for wort in ("gmbh & co. kg", "gmbh & co kg", "gmbh", "mbh", "ohg",
                 "kg", "ag", "e.k.", "ek", "gbr", "ug", "e.v.", "ev"):
        text = text.replace(wort, " ")
    return re.sub(r"[^a-zäöüß0-9]+", "", text)


def unsere_firmen():
    """Alle firmen.json der Laeufe - Pfad, Index und die Firmensaetze."""
    dateien = {}
    for pfad in sorted((PROJEKT / "laeufe/leadquellen").glob("*/firmen.json")):
        try:
            dateien[pfad] = json.loads(pfad.read_text(encoding="utf-8"))
        except (OSError, ValueError) as fehler:
            log(f"KUJDES: {pfad.parent.name} s'u lexua ({fehler})")
    return dateien


def gesucht(dateien):
    """Welche Domains und Name+PLZ suchen wir in MailCom?"""
    domains, namen = {}, {}
    for pfad, firmen in dateien.items():
        for firma in firmen:
            if firma.get("mitarbeiter"):
                continue                       # schon da, nicht ueberschreiben
            domain = domain_von(firma.get("website") or firma.get("domain"))
            if domain:
                domains.setdefault(domain, []).append(firma)
            schluessel = (name_schluessel(firma.get("name")),
                          str(firma.get("plz") or "").strip())
            if schluessel[0]:
                namen.setdefault(schluessel, []).append(firma)
    return domains, namen


def anreichern(domains, namen):
    """Ein Durchgang durch die vier Dateien. Trifft ueber Domain, sonst
    ueber Name + Postleitzahl."""
    import openpyxl

    treffer = 0
    for datei in sorted(glob.glob(str(QUELLE / "*.xlsx"))):
        wb = openpyxl.load_workbook(datei, read_only=True)
        for ws in wb.worksheets:
            zeiger = ws.iter_rows(values_only=True)
            kopf = list(next(zeiger))
            i = {k: n for n, k in enumerate(kopf)}
            if "Anz_Mitarb" not in i:
                continue
            for reihe in zeiger:
                def wert(feld):
                    return (str(reihe[i[feld]] or "").strip()
                            if feld in i else "")

                mitarbeiter = wert("Anz_Mitarb")
                if not mitarbeiter:
                    continue
                plz = wert("PLZ").zfill(5)
                ziele = domains.get(domain_von(wert("Homepage")), [])
                if not ziele:
                    ziele = namen.get(
                        (name_schluessel(" ".join(
                            x for x in (wert("Firma1"), wert("Firma2")) if x)),
                         plz), [])
                for firma in ziele:
                    if firma.get("mitarbeiter"):
                        continue
                    firma["mitarbeiter"] = mitarbeiter
                    if wert("Rechtsform"):
                        firma["rechtsform"] = wert("Rechtsform")
                    firma["mitarbeiter_quelle"] = (
                        "MailCom-Firmenadressen2024-25")
                    treffer += 1
        wb.close()
        log(f"  u lexua: {os.path.basename(datei)} (deri tash {treffer})")
    return treffer


def main():
    schreiben = "--schreiben" in sys.argv[1:]
    log("=" * 62)
    log("MailCom si anije shtese: numri i punonjesve per firmat qe kemi")
    log("PROVE - asgje nuk shkruhet" if not schreiben else "SHKRUHET ne disk")
    log("=" * 62)

    dateien = unsere_firmen()
    firmen_gesamt = sum(len(f) for f in dateien.values())
    domains, namen = gesucht(dateien)
    log(f"Firma ne dosjet e vrapimeve: {firmen_gesamt} "
        f"({len(dateien)} vrapime)")
    log(f"Pa numer punonjesish deri tash: "
        f"{sum(1 for f in dateien.values() for x in f if not x.get('mitarbeiter'))}")

    treffer = anreichern(domains, namen)
    log(f"U gjeten ne MailCom: {treffer}")

    if not schreiben:
        log("")
        log("Kjo ishte vetem prove. Per ta shkruar:")
        log("    python werkzeuge/mailcom-anreichern.py --schreiben")
        return

    for pfad, firmen in dateien.items():
        pfad.write_text(json.dumps(firmen, ensure_ascii=False, indent=1),
                        encoding="utf-8")
    log(f"U shkruan {len(dateien)} dosje firmen.json")
    log("Hapi tjeter: rindertoje bazen qe fusha te mbushet.")


if __name__ == "__main__":
    main()
