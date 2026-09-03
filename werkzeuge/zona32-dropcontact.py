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

# Zone per --zone umschaltbar, damit derselbe Ablauf fuer 32, 33 ...
# gilt statt fest auf eine Zone verdrahtet zu sein.
ZONEN = {
    "32": {"laeufe": ["zona32-herford-2026-08-21",
                      "zona32-overpass-2026-08-21"],
           "lauf": "zona32-dropcontact-2026-08-21"},
    "33": {"laeufe": ["zona33-bielefeld-2026-08-25"],
           "lauf": "zona33-dropcontact-2026-08-28"},
    "34": {"laeufe": ["zona34-kassel-2026-08-28"],
           "lauf": "zona34-dropcontact-2026-08-28"},
    # Zona 35 u mblodh me DY burime, si zona 32 - prandaj ketu duhen te
    # dyja. Me vetem Maps do te binin jashte firmat qe i njeh vetem OSM.
    "35": {"laeufe": ["zona35-giessen-2026-08-28",
                      "zona35-overpass-2026-09-02"],
           "lauf": "zona35-dropcontact-2026-09-02"},
    "36": {"laeufe": ["zona36-fulda-2026-09-01",
                      "zona36-overpass-2026-09-02"],
           "lauf": "zona36-dropcontact-2026-09-02"},
    "37": {"laeufe": ["zona37-goettingen-2026-09-01",
                      "zona37-overpass-2026-09-02"],
           "lauf": "zona37-dropcontact-2026-09-02"},
    "38": {"laeufe": ["zona38-braunschweig-2026-09-01",
                      "zona38-overpass-2026-09-03"],
           "lauf": "zona38-dropcontact-2026-09-03"},
    "39": {"laeufe": ["zona39-magdeburg-2026-09-01",
                      "zona39-overpass-2026-09-03"],
           "lauf": "zona39-dropcontact-2026-09-03"},
}
ZONE = "32"
for _a in sys.argv[1:]:
    if _a.startswith("--zone="):
        ZONE = _a.split("=", 1)[1]
if ZONE not in ZONEN:
    sys.exit(f"Unbekannte Zone {ZONE!r} - bekannt: {', '.join(ZONEN)}")
LAEUFE = ZONEN[ZONE]["laeufe"]
LAUF = PROJEKT / "laeufe/leadquellen" / ZONEN[ZONE]["lauf"]


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


def nach_namen_zuordnen(dc, request_id, anfragen):
    """Rreshtat e nje batch-i te paguar, lidhur me EMER + domain.

    Perdoret kur lista e sotme s'ka me te njejten gjatesi si atehere -
    p.sh. sepse nje firme ka hyre ne listen e bllokimit ne mes. Lidhja me
    numer rendor do te jepte pergjigjen e njeriut te gabuar; lidhja me
    emer ose gjen te njejtin njeri, ose s'gjen asgje.

    Nuk shpenzohet asnje kredit: batch-i eshte paguar, kjo eshte vetem
    marrje e rezultatit."""
    from pipeline.sources.dropcontact import _beste_email, _zusatzfelder

    def kyc(vorname, nachname, website):
        return (str(vorname or "").strip().casefold(),
                str(nachname or "").strip().casefold(),
                domain_von(website))

    zeilen, sipas_domain = {}, {}
    for zeile in dc.zeilen_holen(request_id):
        zeilen[kyc(zeile.get("first_name"), zeile.get("last_name"),
                   zeile.get("website"))] = zeile
        # Ne kete rrjedhe dergohet NJE person per firme, prandaj domain-i
        # e identifikon rreshtin po aq mire sa emri - dhe mban edhe ata
        # ku Dropcontact-i e ktheu emrin pak ndryshe nga sa e derguam
        # ("Hans-Peter" kunder "Hans Peter"). Nese nje domain del dy here,
        # ai s'perdoret: aty s'do te dinim cili rresht i takon kujt.
        d = domain_von(zeile.get("website"))
        if d:
            sipas_domain[d] = None if d in sipas_domain else zeile

    ergebnisse, gjetur, me_domain = [], 0, 0
    for anfrage in anfragen:
        zeile = zeilen.get(kyc(anfrage.get("first_name"),
                               anfrage.get("last_name"),
                               anfrage.get("website")))
        if zeile is None:
            zeile = sipas_domain.get(domain_von(anfrage.get("website")))
            if zeile is not None:
                me_domain += 1
        mail = _beste_email(zeile.get("email", [])) if zeile else None
        if mail:
            mail = {**mail, "felder": _zusatzfelder(zeile)}
            gjetur += 1
        ergebnisse.append(mail)
    log(f"    u lidhen {gjetur} nga {len(anfragen)} kontakte"
        f"{f' ({me_domain} me domain, se emri ndryshonte)' if me_domain else ''}")
    return ergebnisse


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
        nummern = gespeichert["gesendet_nr"]
        log(f"3/5 batch tashme i paguar, po merret sërish: {request_id}")
        if nummern and max(nummern) >= len(anfragen):
            # Lista e sotme eshte me e shkurter se ajo e batch-it: dicka
            # doli jashte ne mes, zakonisht nga lista e bllokimit (zonat
            # 32/33/34 u bene para se te shtoheshin gjashte firmat me
            # 31.08.2026). Numrat e ruajtur s'vlejne me, prandaj rreshtat
            # e paguar lidhen me EMER + domain. Asnje kredit i ri.
            log(f"    lista ka ndryshuar ({len(anfragen)} sot kunder "
                f"{max(nummern) + 1} atehere) - po lidhet me emer")
            return nach_namen_zuordnen(dc, request_id, anfragen)
        gesendet = [(nr, anfragen[nr]) for nr in nummern]
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
            # Gjithcka tjeter qe ktheu Dropcontact-i per kete person:
            # telefoni i tij, LinkedIn, numri i punetoreve, adresa zyrtare.
            # Paguhet me te njejtin kredit si email-i, prandaj hedhja e
            # tyre ishte pagese per te dhena qe i fshinim vete.
            "dropcontact": mail.get("felder") or {},
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
    log(f"ZONA {ZONE} - Hapi 2: Dropcontact + Anrede")
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
    ziel = PROJEKT / f"IT-Liste-Emails-Zona{ZONE}-{stempel}.xlsx"
    aus_lauf(ergebnis_datei, ziel)
    log("=" * 62)
    log(f"DOSJA: {ziel}")
    log("=" * 62)


if __name__ == "__main__":
    main()
