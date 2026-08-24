#!/usr/bin/env python3
"""Zona 32 - Hapi 2: email-i personal me Dropcontact + kolona Anrede.

Leje: Dafina, 21.08.2026 ("gjej si keto qe i ka gjet me emaila personale
njesoj edhe ti bone", me listen IT-Liste-Emails-FERTIG si model).

Cka ben:
  1. Merr kontaktet nga vrapimet e zones 32 - vetem firmat brenda
     profilit IT dhe me automatizim = "no".
  2. Heq gjithcka qe eshte ne sperrliste-global.yaml PARA se te paguhet.
  3. Dropcontact ne nje batch te vetem: emer + domain -> email personale
     e verifikuar (vetem "nominative@pro").
  4. Ndertimin e Anrede-s dhe te Hinweis-it e bene modulet ekzistuese.
  5. Excel ne formatin e IT-Liste-Emails-FERTIG.

SIGURI: request_id shkruhet ne disk SA MENJEHERE te jepet batch-i. Nese
skripti bie, kreditet nuk humbin - merret perseri me te njejtin id.

ASNJE email nuk dergohet askujt. Instantly nuk preket fare.
"""
import json
import sys
from datetime import datetime
from pathlib import Path

PROJEKT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJEKT))

from pipeline.env import lade_dotenv  # noqa: E402

lade_dotenv(PROJEKT / ".env")

import os  # noqa: E402
from pipeline.anrede_spalte import aus_lauf  # noqa: E402
from pipeline.config import lade_globale_sperrlisten_eintraege  # noqa: E402
from pipeline.sources.dropcontact import DropcontactSource  # noqa: E402

LAEUFE = ["zona32-herford-2026-08-21", "zona32-overpass-2026-08-21"]
LAUF = PROJEKT / "laeufe/leadquellen/zona32-dropcontact-2026-08-21"


def log(*teile):
    print(f"[{datetime.now():%H:%M:%S}]", *teile, flush=True)


def domain_von(wert):
    import re
    ohne = re.sub(r"^https?://", "", str(wert or "").strip().lower())
    return re.sub(r"^www\.", "", ohne).split("/")[0]


def kontakte_sammeln():
    """Nje kontakt per firme: personi me i mire i renditur nga impressum-i."""
    firmen = {}
    for ordner in LAEUFE:
        pfad = PROJEKT / "laeufe/leadquellen" / ordner / "firmen.json"
        if not pfad.exists():
            continue
        for firma in json.loads(pfad.read_text(encoding="utf-8")):
            firmen[(firma.get("domain") or firma.get("name") or "").lower()] = firma

    kontakte = []
    for firma in firmen.values():
        if not firma.get("profil_passt"):
            continue
        if firma.get("offers_automation_services") != "no":
            continue
        personen = firma.get("entscheider") or []
        if not personen or not firma.get("website"):
            continue
        person = personen[0]      # tashme i renditur sipas prioritetit
        if not (person.get("vorname") and person.get("nachname")):
            continue
        kontakte.append({"firma": firma, "person": person})
    return kontakte


def gesperrt_filtern(kontakte):
    """Sperrliste vepron PARA pageses - nje i bllokuar s'guxon te kushtoje."""
    try:
        eintraege = lade_globale_sperrlisten_eintraege(str(PROJEKT))
    except Exception as fehler:      # noqa: BLE001
        log(f"KUJDES: sperrlista s'u lexua dot ({fehler}) - ndalim.")
        raise

    domains = {str(e.get("domain", "")).lower().lstrip("*.")
               for e in eintraege if e.get("domain")}
    frei, blockiert = [], []
    for k in kontakte:
        domain = domain_von(k["firma"].get("website"))
        if any(domain == d or domain.endswith("." + d) for d in domains):
            blockiert.append(k)
        else:
            frei.append(k)
    if blockiert:
        for k in blockiert:
            log(f"    BLLOKUAR: {k['firma'].get('name')} "
                f"({domain_von(k['firma'].get('website'))})")
    log(f"2/5 sperrlista: {len(blockiert)} te bllokuara, {len(frei)} vazhdojne")
    return frei


def dropcontact_laufen(kontakte, dc):
    """Batch i vetem. request_id ruhet menjehere pas dorezimit."""
    LAUF.mkdir(parents=True, exist_ok=True)
    id_datei = LAUF / "request-id.json"

    anfragen = [{
        "first_name": k["person"]["vorname"],
        "last_name": k["person"]["nachname"],
        "website": k["firma"].get("website", ""),
        "company": k["firma"].get("name", ""),
    } for k in kontakte]

    if id_datei.exists():
        gespeichert = json.loads(id_datei.read_text(encoding="utf-8"))
        request_id = gespeichert["request_id"]
        gesendet = [(nr, anfragen[nr]) for nr in gespeichert["gesendet_nr"]]
        log(f"3/5 batch tashme i paguar, po merret sërish: {request_id}")
    else:
        log(f"3/5 po dorezohet batch-i te Dropcontact: {len(anfragen)} persona ...")
        request_id, gesendet = dc.batch_abgeben(anfragen)
        if request_id is None:
            log("    asnje person i vlefshem - ndalim.")
            return [None] * len(anfragen)
        id_datei.write_text(json.dumps({
            "request_id": request_id,
            "gesendet_nr": [nr for nr, _ in gesendet],
            "zeit": datetime.now().isoformat(timespec="seconds"),
        }, ensure_ascii=False, indent=1), encoding="utf-8")
        log(f"    request_id u ruajt: {request_id} "
            f"({len(gesendet)} persona te paguar)")

    log("    po pritet rezultati (batch i madh do disa minuta) ...")
    return dc.batch_abholen(request_id, gesendet, len(anfragen))


def ergebnisse_bauen(kontakte, mails):
    """Formati qe pret anrede_spalte.aus_lauf(): firma me 'leads'."""
    firmen = []
    for kontakt, mail in zip(kontakte, mails):
        firma, person = kontakt["firma"], kontakt["person"]
        if not mail:
            continue
        notizen = []
        if mail.get("hinweis"):
            notizen.append(mail["hinweis"])
        firmen.append({
            "name": firma.get("name", ""),
            "domain": firma.get("domain", ""),
            "website": firma.get("website", ""),
            "telefon": (person.get("telefon") or firma.get("telefon") or ""),
            "plz": firma.get("plz", ""),
            "ort": firma.get("ort", ""),
            "rolle": person.get("rolle", ""),
            "leads": [{
                "first_name": person.get("vorname", ""),
                "last_name": person.get("nachname", ""),
                "email": mail["email"],
                "title": person.get("rolle", ""),
                "source": "dropcontact",
                "notizen": notizen,
            }],
        })
    return firmen


def main():
    log("=" * 62)
    log("ZONA 32 - Hapi 2: Dropcontact + Anrede")
    log("Asnje email nuk dergohet. Instantly i paprekur.")
    log("=" * 62)

    kontakte = kontakte_sammeln()
    log(f"1/5 kontakte te pranueshme: {len(kontakte)}")
    kontakte = gesperrt_filtern(kontakte)

    dc = DropcontactSource(os.environ["DROPCONTACT_API_KEY"])
    mails = dropcontact_laufen(kontakte, dc)
    gefunden = sum(1 for m in mails if m)
    log(f"4/5 email personale te verifikuara: {gefunden} nga {len(kontakte)} "
        f"({100*gefunden/max(1,len(kontakte)):.0f}%)")

    firmen = ergebnisse_bauen(kontakte, mails)
    ergebnis_datei = LAUF / "ergebnisse.json"
    ergebnis_datei.write_text(
        json.dumps(firmen, ensure_ascii=False, indent=1), encoding="utf-8")

    stempel = datetime.now().strftime("%Y%m%d-%H%M")
    ziel = PROJEKT / f"IT-Liste-Emails-Zona32-{stempel}.xlsx"
    aus_lauf(ergebnis_datei, ziel)
    log("=" * 62)
    log(f"DOSJA: {ziel}")
    log("=" * 62)


if __name__ == "__main__":
    main()
