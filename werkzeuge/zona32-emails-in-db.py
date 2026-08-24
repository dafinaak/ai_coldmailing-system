#!/usr/bin/env python3
"""I shkruan email-et e Dropcontact-it prapa te dosjet e vrapimit, qe te
hyjne edhe ne bazen master - jo vetem ne Excel.

Pa kete hap, rezultati i paguar rri vetem ne nje dosje Excel dhe baza
nuk e di. Prandaj: cdo person qe mori adrese merr edhe
status "mail_geprueft" dhe burimin "dropcontact".
"""
import json
import sys
from datetime import datetime
from pathlib import Path

PROJEKT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJEKT))

LAEUFE = ["zona32-herford-2026-08-21", "zona32-overpass-2026-08-21"]
ERGEBNISSE = (PROJEKT / "laeufe/leadquellen/zona32-dropcontact-2026-08-21"
              / "ergebnisse.json")


def main():
    daten = json.loads(ERGEBNISSE.read_text(encoding="utf-8"))
    # kennung -> (email, notizen)
    mails = {}
    for firma in daten:
        lead = (firma.get("leads") or [None])[0]
        if not lead or not lead.get("email"):
            continue
        kennung = (firma.get("domain") or firma.get("name") or "").lower()
        mails[kennung] = (lead["email"], lead.get("notizen") or [])
    print(f"Email nga Dropcontact: {len(mails)}")

    jetzt = datetime.now().isoformat(timespec="seconds")
    gesetzt = 0
    for ordner in LAEUFE:
        pfad = PROJEKT / "laeufe/leadquellen" / ordner / "firmen.json"
        if not pfad.exists():
            continue
        firmen = json.loads(pfad.read_text(encoding="utf-8"))
        for firma in firmen:
            kennung = (firma.get("domain") or firma.get("name") or "").lower()
            treffer = mails.get(kennung)
            if not treffer:
                continue
            personen = firma.get("entscheider") or []
            if not personen:
                continue
            email, notizen = treffer
            # Dropcontact u pyet per personin e pare (te renditur me lart).
            person = personen[0]
            person["email"] = email
            person["email_art"] = "persoenlich"
            person["status"] = "mail_geprueft"
            person["email_quelle"] = "dropcontact"
            person["email_geprueft_am"] = jetzt
            if notizen:
                person["email_hinweise"] = notizen
            gesetzt += 1
        pfad.write_text(json.dumps(firmen, ensure_ascii=False, indent=1),
                        encoding="utf-8")
        print(f"  {ordner}: u shkrua")

    print(f"Persona qe moren email ne dosjet e vrapimit: {gesetzt}")

    from pipeline import master_db
    zahlen = master_db.bauen(str(PROJEKT))
    print(f"Baza u rindertua: {zahlen}")


if __name__ == "__main__":
    main()
