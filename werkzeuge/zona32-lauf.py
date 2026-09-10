#!/usr/bin/env python3
"""Zona 32 (Herford, 45 kode postare) - Hapi 1 i porosise se Dafines
(21.08.2026).

Cka BEN:
  1. Merr firmat nga dataset-i Apify i paguar tashme (yP1tVCwUcW3bNsSQw,
     prova e ndalur e 21.08) - pa asnje kosto te re.
  2. Filtri i sakte i 45 kodeve postare.
  3. Klasifikimi i profilit IT (rregulla + KI).
  4. Klasifikimi i automatizimit (pool falas -> tekst faqeje + KI).
  5. Per ato qe mbeten: lexon impressum-in dhe nxjerr vendimmarresin
     me poziten e sakte, plus numrin e telefonit qe eshte shtypur aty.
  6. Shkruan firmen.json dhe e rinderton bazen master.

Cka NUK ben (kufij te vene shprehimisht nga Dafina):
  - ASNJE thirrje Dropcontact, Hunter, Apollo, Datagma.
  - ASNJE prekje e Instantly-t ose e fushatave.
  - ASNJE fshirje firmash.

Rinisja eshte e sigurt: cdo faze ruhet ne dosjen e vet dhe nuk perseritet.
"""
import json
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

PROJEKT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJEKT))

from pipeline.env import lade_dotenv  # noqa: E402

lade_dotenv(PROJEKT / ".env")

from pipeline.branchen_filter import firma_bewerten  # noqa: E402
from pipeline.automation_klassifikation import (  # noqa: E402
    urteile_je_firma, laden as pool_laden)
from pipeline.decision_maker import sort_by_priority  # noqa: E402
from pipeline.ki import KI  # noqa: E402
from pipeline.sources.impressum import ImpressumQuelle  # noqa: E402
from pipeline.website import fetch_text  # noqa: E402

DATASET = PROJEKT / ("laeufe/leadquellen/"
                     "apify-ds-yP1tVCwUcW3bNsSQw.json")
PLZ_LISTE = PROJEKT / "laeufe/leadquellen/plz-liste-oliver-zona32.txt"
LAUF = PROJEKT / "laeufe/leadquellen/zona32-herford-2026-08-21"

# Cmimet e gpt-4.1-mini, USD per 1 milion token (faqja e OpenAI-t).
# Shenuar ne raport qe te jete e kontrollueshme.
PREIS_EIN = 0.40
PREIS_AUS = 1.60

GLEICHZEITIG = 8



# --------------------------------------------------------------- ndihmesa

def log(*teile):
    print(f"[{datetime.now():%H:%M:%S}]", *teile, flush=True)


def lesen(name, standard):
    pfad = LAUF / name
    if pfad.exists():
        try:
            return json.loads(pfad.read_text(encoding="utf-8"))
        except ValueError:
            pass
    return standard


def schreiben(name, daten):
    LAUF.mkdir(parents=True, exist_ok=True)
    (LAUF / name).write_text(
        json.dumps(daten, ensure_ascii=False, indent=1), encoding="utf-8")


class ZaehlendeSession:
    """Numeron token-at e vertete nga pergjigjja e OpenAI-t, qe kostoja
    te jete e matur e jo e vleresuar."""

    def __init__(self, echt):
        self._echt = echt
        self.ein = self.aus = self.aufrufe = 0
        self._sperre = threading.Lock()

    def post(self, *args, **kwargs):
        antwort = self._echt.post(*args, **kwargs)
        try:
            nutzung = (antwort.json() or {}).get("usage") or {}
            with self._sperre:
                self.ein += int(nutzung.get("prompt_tokens") or 0)
                self.aus += int(nutzung.get("completion_tokens") or 0)
                self.aufrufe += 1
        except Exception:      # noqa: BLE001 - numerimi s'guxon te thyeje lauf-in
            pass
        return antwort

    def __getattr__(self, name):
        return getattr(self._echt, name)

    @property
    def kosten(self):
        return (self.ein / 1e6) * PREIS_EIN + (self.aus / 1e6) * PREIS_AUS


_PLZ = re.compile(r"\b(\d{5})\b")
# Numra telefoni gjermane si shtypen ne impressum. Kerkohet nje prefiks
# i qarte, qe te mos merren numra fature apo HRB.
_TEL = re.compile(
    r"(?:Tel(?:efon)?\.?|Fon|Phone|Ruf)\s*[:.]?\s*"
    r"(\+?[\d][\d\s()/.\-]{7,24}\d)", re.I)


def plz_von(eintrag):
    kode = str(eintrag.get("postalCode") or "").strip()
    if not kode:
        treffer = _PLZ.search(str(eintrag.get("address") or ""))
        kode = treffer.group(1) if treffer else ""
    return kode


def domain_von(website):
    ohne = re.sub(r"^https?://", "", str(website or "").strip().lower())
    return ohne.split("/")[0].replace("www.", "")


def telefon_aus_impressum(text):
    treffer = _TEL.search(text or "")
    if not treffer:
        return ""
    nummer = re.sub(r"\s{2,}", " ", treffer.group(1)).strip(" .-/")
    ziffern = re.sub(r"\D", "", nummer)
    return nummer if 7 <= len(ziffern) <= 16 else ""


# --------------------------------------------------------- 1. firmat e papra

def firmen_laden(quelle_datei=None):
    fertig = lesen("00-firmen-roh.json", None)
    if fertig:
        log(f"1/6 firmat e papra: {len(fertig)} (nga kontrollpika)")
        return fertig

    # Rruga e dyte: nje firmen.json qe e ka mbledhur nje burim tjeter
    # (p.sh. Overpass). Formati eshte tashme i yni, prandaj vetem
    # kontrollohet kodi postar dhe plotesohet domain-i.
    if quelle_datei:
        kodet = {r.strip() for r in
                 PLZ_LISTE.read_text(encoding="utf-8").splitlines()
                 if r.strip().isdigit() and len(r.strip()) == 5}
        roh = json.loads(Path(quelle_datei).read_text(encoding="utf-8"))
        firmen, gesehen = [], set()
        for f in roh:
            kode = str(f.get("plz") or "").strip()
            # OSM shpesh s'e ka fare kodin postar. Ato mbahen ketu vetem
            # me shenjen "plz_bestaetigt": False - kutia e Overpass-it NUK
            # e garanton zonen, ajo eshte katrori i tere rajonit postar
            # (zona 35: rreze 120 km, zona vete 48). Nga 10.09.2026
            # mbledhja me liste kodesh s'i sjell me fare, dhe porta e zones
            # te zona32-itliste-final.py i mban jashte listave.
            if kode and kode not in kodet:
                continue
            f = dict(f)
            f["plz_bestaetigt"] = bool(kode)
            f["domain"] = f.get("domain") or domain_von(f.get("website"))
            kennung = (f["domain"] or f.get("name") or "").lower()
            if not kennung or kennung in gesehen:
                continue
            gesehen.add(kennung)
            f.setdefault("categories", [])
            f.setdefault("telefon", "")
            f.setdefault("vorhandene_email", "")
            f.setdefault("gf_name_liste", "")
            firmen.append(f)
        schreiben("00-firmen-roh.json", firmen)
        log(f"1/6 firmat e papra: {len(firmen)} nga {quelle_datei}")
        return firmen

    kodet = {r.strip() for r in PLZ_LISTE.read_text(encoding="utf-8").splitlines()
             if r.strip().isdigit() and len(r.strip()) == 5}
    daten = json.loads(DATASET.read_text(encoding="utf-8"))
    firmen, gesehen = [], set()
    for e in daten:
        kode = plz_von(e)
        if kode not in kodet:
            continue
        website = str(e.get("website") or "").strip()
        name = str(e.get("title") or "").strip()
        kennung = (domain_von(website) or name).lower()
        if not kennung or kennung in gesehen:
            continue
        gesehen.add(kennung)
        firmen.append({
            "name": name,
            "website": website,
            "domain": domain_von(website),
            "address": str(e.get("address") or ""),
            "plz": kode,
            "ort": str(e.get("city") or ""),
            "telefon": str(e.get("phone") or ""),
            "vorhandene_email": "",
            "gf_name_liste": "",
            "categories": [k for k in ([e.get("categoryName")]
                                       + list(e.get("categories") or [])) if k],
            "ausserhalb_region": False,
            "quellen": ["maps"],
            "quelle": "maps",
            "herkunft_detail": ("apify-dataset yP1tVCwUcW3bNsSQw "
                                "(google-maps, 21.08.2026)"),
        })
    schreiben("00-firmen-roh.json", firmen)
    log(f"1/6 firmat e papra: {len(firmen)} brenda {len(kodet)} kodeve")
    return firmen


# ------------------------------------------------------- 2. teksti i faqeve

def webtexte_laden(firmen):
    cache = lesen("01-webtext.json", {})
    offen = [f for f in firmen
             if f["website"] and f["domain"] not in cache]
    if offen:
        log(f"2/6 po lexohen {len(offen)} faqe interneti ...")
        sperre = threading.Lock()

        def eine(firma):
            text = ""
            try:
                text = fetch_text(firma["website"], 5000) or ""
            except Exception:      # noqa: BLE001
                text = ""
            with sperre:
                cache[firma["domain"]] = text
            return bool(text)

        with ThreadPoolExecutor(max_workers=GLEICHZEITIG) as pool:
            for nummer, _ in enumerate(pool.map(eine, offen), 1):
                if nummer % 50 == 0:
                    log(f"    ... {nummer}/{len(offen)}")
        schreiben("01-webtext.json", cache)
    lesbar = sum(1 for t in cache.values() if (t or "").strip())
    log(f"2/6 tekst faqeje: {lesbar} te lexueshme nga {len(firmen)} firma")
    return cache


# ------------------------------------------------------ 3. profili IT (KI)

def profil_pruefen(firmen, webtexte, ki):
    urteile = lesen("02-profil.json", {})
    offen = [f for f in firmen if f["domain"] or f["name"]]
    offen = [f for f in offen
             if (f["domain"] or f["name"].lower()) not in urteile]
    if offen:
        log(f"3/6 filtri i profilit IT per {len(offen)} firma ...")
        sperre = threading.Lock()

        def eine(firma):
            schluessel = firma["domain"] or firma["name"].lower()
            text = webtexte.get(firma["domain"], "")
            try:
                urteil = firma_bewerten(firma, text, ki)
            except Exception as fehler:      # noqa: BLE001
                urteil = {"passt": False, "typ": "fehler",
                          "grund": f"Fehler: {fehler}", "quelle": "fehler"}
            with sperre:
                urteile[schluessel] = urteil
            return urteil

        with ThreadPoolExecutor(max_workers=GLEICHZEITIG) as pool:
            for nummer, _ in enumerate(pool.map(eine, offen), 1):
                if nummer % 50 == 0:
                    log(f"    ... {nummer}/{len(offen)}")
                    schreiben("02-profil.json", urteile)
        schreiben("02-profil.json", urteile)
    passt = sum(1 for u in urteile.values() if u.get("passt"))
    log(f"3/6 profil IT (kalimi i pare): {passt} brenda profilit, "
        f"{len(urteile) - passt} jashte")
    return urteile


# Hapi "shansi i dyte" u hoq me 31.08.2026 me urdher te Dafines.
# Ai i kthente brenda zhvilluesit e softuerit sapo faqja e tyre permendte
# edhe mirembajtje IT - dhe pikerisht nga aty hyne kater nga gjashte
# firmat qe ajo i gjeti gabim ne listat 33 dhe 34 (Mibema, GRAPHISOFT,
# elastify, kisocon). Rregulli i ri thote te kunderten: softuer i vet
# do te thote jashte, edhe me mirembajtje. Shih pipeline/branchen_filter.py
# dhe rregullin te AGENTS.md. Skedaret 02b-zweite-chance.json nga rrjedhat
# e vjetra mbeten aty ku jane, si histori.


# ------------------------------------------------- 4. automatizimi (qellimi 4)

def automation_pruefen(firmen, webtexte, ki):
    gespeichert = lesen("03-automation.json", {})
    offen = [f for f in firmen
             if (f["domain"] or f["name"].lower()) not in gespeichert]
    if offen:
        log(f"4/6 kontrolli i automatizimit per {len(offen)} firma ...")
        urteile = urteile_je_firma(
            offen, ki, vorwissen=pool_laden(str(PROJEKT)),
            text_lesen=lambda url: webtexte.get(domain_von(url), ""),
            gleichzeitig=GLEICHZEITIG, log=log)
        for nummer, firma in enumerate(offen):
            schluessel = firma["domain"] or firma["name"].lower()
            gespeichert[schluessel] = urteile.get(nummer) or {
                "wettbewerber": False, "unsicher": True,
                "belege": "pa gjykim", "quelle": "fehlend"}
        schreiben("03-automation.json", gespeichert)
    ja = sum(1 for u in gespeichert.values() if u.get("wettbewerber"))
    unsicher = sum(1 for u in gespeichert.values()
                   if u.get("unsicher") and not u.get("wettbewerber"))
    log(f"4/6 automatizim: {ja} ofrues (jashte), {unsicher} te pasigurt "
        f"(jashte), {len(gespeichert) - ja - unsicher} te pastra")
    return gespeichert


# ---------------------------------------------- 5. impressum (qellimi 2)

def impressum_lesen(kandidaten, ki):
    ergebnisse = lesen("04-impressum.json", {})
    offen = [f for f in kandidaten if f["domain"] not in ergebnisse]
    if not offen:
        log(f"5/6 impressum: {len(ergebnisse)} tashme te lexuara")
        return ergebnisse

    log(f"5/6 po lexohet impressum-i per {len(offen)} firma ...")
    quelle = ImpressumQuelle(ki)
    sperre = threading.Lock()

    def eine(firma):
        satz = {"personen": [], "telefon": "", "grund": ""}
        try:
            text = quelle.impressum_text(firma["website"])
            if not text:
                satz["grund"] = "impressum i palexueshem"
            else:
                satz["telefon"] = telefon_aus_impressum(text)
                gelesen = quelle.entscheider_lesen(
                    text, firma["name"], firma["domain"])
                satz["personen"] = gelesen.get("personen") or []
                if not satz["personen"]:
                    satz["grund"] = "asnje person ne impressum"
        except Exception as fehler:      # noqa: BLE001
            satz["grund"] = f"gabim: {fehler}"
        with sperre:
            ergebnisse[firma["domain"]] = satz
        return satz

    with ThreadPoolExecutor(max_workers=GLEICHZEITIG) as pool:
        for nummer, _ in enumerate(pool.map(eine, offen), 1):
            if nummer % 25 == 0:
                log(f"    ... {nummer}/{len(offen)}")
                schreiben("04-impressum.json", ergebnisse)
    schreiben("04-impressum.json", ergebnisse)
    return ergebnisse


# ------------------------------------------------------- 6. firmen.json

def firmen_json_bauen(firmen, profil, automation, impressum):
    jetzt = datetime.now().isoformat(timespec="seconds")
    fertig = []
    for firma in firmen:
        schluessel = firma["domain"] or firma["name"].lower()
        p = profil.get(schluessel) or {}
        a = automation.get(schluessel) or {}
        satz = dict(firma)

        if a.get("wettbewerber"):
            stufe, grund = "yes", a.get("belege") or "ofron automatizim"
        elif a.get("unsicher"):
            stufe, grund = "uncertain", a.get("belege") or "e pasigurt"
        else:
            stufe, grund = "no", a.get("belege") or "pa automatizim"
        satz["offers_automation_services"] = stufe
        satz["automation_check_reason"] = grund[:400]
        satz["automation_checked_at"] = jetzt
        satz["automation_quelle"] = a.get("quelle", "")

        satz["profil_passt"] = bool(p.get("passt"))
        satz["profil_typ"] = p.get("typ", "")
        satz["profil_grund"] = (p.get("grund") or "")[:300]

        imp = impressum.get(firma["domain"]) or {}
        personen = []
        for person in imp.get("personen") or []:
            voll = f"{person.get('vorname','')} {person.get('nachname','')}".strip()
            if not voll:
                continue
            personen.append({
                "name": voll,
                "vorname": person.get("vorname", ""),
                "nachname": person.get("nachname", ""),
                "rolle": person.get("rolle", ""),
                "email": "",
                "telefon": imp.get("telefon", ""),
                "linkedin": person.get("linkedin"),
                "quelle": "impressum",
                "status": "",
            })
        personen = sort_by_priority(personen)
        satz["entscheider"] = personen
        if personen:
            satz["entscheider_primaer"] = personen[0]
        satz["impressum_grund"] = imp.get("grund", "")

        if not satz["profil_passt"]:
            satz["campaign_ineligibility_reason"] = "profil_nicht_passend"
        elif stufe == "yes":
            satz["campaign_ineligibility_reason"] = "automation_provider"
        elif stufe == "uncertain":
            satz["campaign_ineligibility_reason"] = "automation_uncertain"
        elif not personen:
            satz["campaign_ineligibility_reason"] = "no_decision_maker"
        else:
            satz["campaign_ineligibility_reason"] = (
                "personal_decision_maker_email_missing")
        fertig.append(satz)

    schreiben("firmen.json", fertig)
    log(f"6/6 firmen.json u shkrua: {len(fertig)} firma")
    return fertig


# ------------------------------------------------------------------ main

def main():
    global LAUF
    start = time.time()
    limit = None
    quelle_datei = None
    for arg in sys.argv[1:]:
        if arg.startswith("--limit="):
            limit = int(arg.split("=", 1)[1])
        elif arg.startswith("--lauf="):
            LAUF = PROJEKT / "laeufe/leadquellen" / arg.split("=", 1)[1]
        elif arg.startswith("--firmen="):
            quelle_datei = arg.split("=", 1)[1]
        elif arg.startswith("--plz="):
            # Welche Postleitzahlen-Liste gilt. Ohne das waere der Lauf
            # fest auf Zone 32 verdrahtet.
            globals()["PLZ_LISTE"] = (
                PROJEKT / "laeufe/leadquellen" / arg.split("=", 1)[1])
        elif arg.startswith("--dataset="):
            # Ein anderer Apify-Rohdatensatz (Apify-Format, nicht unseres).
            # Zone 34 kam aus einem eigenen Lauf, nicht aus dem vom 21.08.
            globals()["DATASET"] = (
                PROJEKT / "laeufe/leadquellen" / arg.split("=", 1)[1])
    LAUF.mkdir(parents=True, exist_ok=True)
    log("=" * 62)
    log("ZONA 32 (Herford) - Hapi 1: profil + automatizim + impressum")
    log("PA Dropcontact, PA Hunter, PA Apollo. Instantly i paprekur.")
    log("=" * 62)

    firmen = firmen_laden(quelle_datei)
    if limit:
        firmen = firmen[:limit]
        log(f"    PROVE E VOGEL: vetem {len(firmen)} firmat e para")
    webtexte = webtexte_laden(firmen)

    ki = KI()
    ki.session = ZaehlendeSession(ki.session)
    log(f"    modeli i KI-se: {ki.model} ({ki.anbieter})")

    profil = profil_pruefen(firmen, webtexte, ki)
    automation = automation_pruefen(firmen, webtexte, ki)

    kandidaten = []
    for firma in firmen:
        schluessel = firma["domain"] or firma["name"].lower()
        p = profil.get(schluessel) or {}
        a = automation.get(schluessel) or {}
        if (p.get("passt") and not a.get("wettbewerber")
                and not a.get("unsicher") and firma["website"]):
            kandidaten.append(firma)
    log(f"    firma qe kualifikohen per impressum: {len(kandidaten)}")

    impressum = impressum_lesen(kandidaten, ki)
    firmen_json_bauen(firmen, profil, automation, impressum)

    kosten = {
        "modell": ki.model,
        "ki_aufrufe": ki.session.aufrufe,
        "token_ein": ki.session.ein,
        "token_aus": ki.session.aus,
        "preis_ein_pro_mio_usd": PREIS_EIN,
        "preis_aus_pro_mio_usd": PREIS_AUS,
        "kosten_usd": round(ki.session.kosten, 4),
        "bezahlte_api_ohne_ki": 0,
        "laufzeit_minuten": round((time.time() - start) / 60, 1),
    }
    schreiben("kosten.json", kosten)
    log("=" * 62)
    log(f"KOSTO: {ki.session.aufrufe} thirrje KI, "
        f"{ki.session.ein:,} token hyrje, {ki.session.aus:,} token dalje "
        f"= {kosten['kosten_usd']:.4f} USD")
    log(f"KOHA: {kosten['laufzeit_minuten']} minuta")
    log("=" * 62)


if __name__ == "__main__":
    main()
