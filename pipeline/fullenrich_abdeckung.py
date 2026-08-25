"""FullEnrich-Abdeckungstest - findet FullEnrich ueberhaupt Entscheider?

Auftrag Dafina, 24.08.2026. Die eine Frage, die dieser Test beantwortet:

    Liefert FullEnrich fuer unsere Zielfirmen echte
    CEOs/Geschaeftsfuehrer/Inhaber - oder nur irgendwelche Leute?

Alles andere ist hier bewusst NICHT Gegenstand. Es werden ausschliesslich
zwei Endpunkte aufgerufen:

    POST /company/lookup     0,25 Credits je gefundener Firma
    POST /people/search      0,25 Credits je zurueckgegebener Person

Der teure Endpunkt /contact/enrich/bulk wird in diesem Modul NICHT
importiert und NICHT aufgerufen. Es gibt keinen Codepfad dorthin - das
ist die Sicherung, nicht nur ein Vorsatz.

Grund fuer diesen Zuschnitt: in den bisherigen echten Laeufen hatte
KEINE der zurueckgegebenen Personen einen echten Stellentitel - nur eine
"headline" wie "Digital problem solver". Wenn das in der Breite so
bleibt, waere jede gekaufte Anreicherungs-Credit verloren, weil das
Kosten-Tor ohnehin schliesst. Diese Frage kostet ~19 Credits statt
~1.200.
"""
import csv
import json
import random
import sqlite3
import time
from datetime import datetime
from pathlib import Path

from pipeline.fullenrich_poc import (
    RANG_GRUPPEN, TITEL_VARIANTEN, _aktueller_titel, _domain, _norm,
    firmen_abgleich, log, rang_von_titel)
from pipeline.sources.fullenrich import (
    PREIS_SUCHTREFFER, FullEnrichFehler, FullEnrichSource, KontingentLeer)

DB_DATEI = "daten/fullenrich-abdeckung.db"
AUSWAHL_DATEI = "daten/fullenrich-abdeckung-auswahl.json"
SEED = 20260824

SCHEMA = """
CREATE TABLE IF NOT EXISTS abdeckung_firmen (
    id INTEGER PRIMARY KEY,
    test_run_id TEXT NOT NULL,
    company_id INTEGER,
    company_kennung TEXT,
    company_name TEXT,
    domain TEXT,
    website TEXT,
    ort TEXT,
    automation_status TEXT,
    automation_confidence REAL,
    automation_evidence TEXT,
    automation_source_url TEXT,
    fullenrich_company_found INTEGER,
    fullenrich_company_name TEXT,
    fullenrich_company_domain TEXT,
    company_match_status TEXT,
    company_match_score REAL,
    people_returned INTEGER,
    valid_decision_makers INTEGER,
    api_status TEXT,
    error_message TEXT,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS abdeckung_personen (
    id INTEGER PRIMARY KEY,
    test_run_id TEXT NOT NULL,
    company_id INTEGER,
    company_name TEXT,
    company_domain TEXT,
    person_name TEXT,
    job_title TEXT,
    headline TEXT,
    profile_company TEXT,
    profile_domain TEXT,
    linkedin TEXT,
    rang INTEGER,
    urteil TEXT,
    begruendung TEXT,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS abdeckung_laeufe (
    test_run_id TEXT PRIMARY KEY,
    gestartet_am TEXT, beendet_am TEXT, seed INTEGER,
    firmen INTEGER, guthaben_vorher REAL, guthaben_nachher REAL,
    kennzahlen TEXT
);
"""


# ---------------------------------------------------- Personen beurteilen

def person_beurteilen(person: dict, firma: dict) -> dict:
    """{urteil, begruendung, ...} fuer EINE zurueckgegebene Person.

    urteil: "valid" | "no_job_title" | "unrelated_title" | "company_mismatch"

    Die headline wird NIE als Stellentitel genommen. Sie wird
    mitgefuehrt, damit im Bericht sichtbar ist, was FullEnrich statt
    eines Titels geliefert hat."""
    titel, headline, firmenname, firmen_domain, linkedin = \
        _aktueller_titel(person)
    unsere_domain = _domain(firma.get("domain") or firma.get("website"))
    satz = {
        "person_name": person.get("full_name")
                       or f"{person.get('first_name','')} "
                          f"{person.get('last_name','')}".strip(),
        "job_title": titel,
        "headline": headline,
        "profile_company": firmenname,
        "profile_domain": firmen_domain,
        "linkedin": linkedin,
        "rang": rang_von_titel(titel),
    }

    if firmen_domain and unsere_domain and firmen_domain != unsere_domain:
        satz["urteil"] = "company_mismatch"
        satz["begruendung"] = (
            f"Profil nennt Domain '{firmen_domain}', wir suchen "
            f"'{unsere_domain}'")
        return satz
    if firmenname and _norm(firma.get("name")) and not (
            _norm(firmenname) in _norm(firma.get("name"))
            or _norm(firma.get("name")) in _norm(firmenname)) \
            and not firmen_domain:
        satz["urteil"] = "company_mismatch"
        satz["begruendung"] = (
            f"Profil nennt Firma '{firmenname[:50]}', wir suchen "
            f"'{firma.get('name','')[:50]}'")
        return satz

    if not titel:
        satz["urteil"] = "no_job_title"
        satz["begruendung"] = (
            f"kein Stellentitel im Profil"
            + (f"; FullEnrich liefert nur die headline "
               f"'{headline[:70]}'" if headline else ""))
        return satz
    if satz["rang"] >= len(RANG_GRUPPEN):
        satz["urteil"] = "unrelated_title"
        satz["begruendung"] = (
            f"Titel '{titel}' gehört zu keiner Entscheider-Gruppe")
        return satz

    satz["urteil"] = "valid"
    satz["begruendung"] = (
        f"Stellentitel '{titel}' (Rang {satz['rang']}), Firma passt"
        + (f" über Domain {firmen_domain}" if firmen_domain else
           f" über Namen '{firmenname[:40]}'" if firmenname else ""))
    return satz


# ------------------------------------------------------------- Kennzahlen

def kennzahlen_rechnen(firmen_zeilen: list, personen: list) -> dict:
    def anteil(z, n):
        return round(100.0 * z / n, 1) if n else 0.0

    getestet = len(firmen_zeilen)
    gefunden = [f for f in firmen_zeilen if f["fullenrich_company_found"]]
    nicht_gefunden = [f for f in firmen_zeilen
                      if not f["fullenrich_company_found"]]
    mit_titel = [p for p in personen if (p["job_title"] or "").strip()]
    ohne_titel = [p for p in personen if not (p["job_title"] or "").strip()]
    gueltig = [p for p in personen if p["urteil"] == "valid"]
    unsicher = [p for p in personen if p["urteil"] == "unrelated_title"]
    fremd = [p for p in personen if p["urteil"] == "company_mismatch"]
    firmen_mit = [f for f in firmen_zeilen if f["valid_decision_makers"] > 0]
    firmen_ohne = [f for f in firmen_zeilen if f["valid_decision_makers"] == 0]

    return {
        "companies_tested": getestet,
        "companies_matched": len(gefunden),
        "companies_not_found": len(nicht_gefunden),
        "company_match_rate": anteil(len(gefunden), getestet),
        "total_people_returned": len(personen),
        "people_with_real_job_title": len(mit_titel),
        "people_without_job_title": len(ohne_titel),
        "valid_decision_makers": len(gueltig),
        "uncertain_decision_makers": len(unsicher),
        "company_mismatches": len(fremd),
        "companies_with_valid_dm": len(firmen_mit),
        "companies_without_valid_dm": len(firmen_ohne),
        "valid_dm_rate_per_company": anteil(len(firmen_mit), getestet),
        "valid_dm_rate_among_people": anteil(len(gueltig), len(personen)),
        "no_decision_maker_rate": anteil(len(firmen_ohne), getestet),
    }


def bericht_text(k: dict, guthaben_vorher=None, guthaben_nachher=None) -> str:
    z = ["=" * 56, "FULLENRICH DECISION-MAKER COVERAGE TEST", "=" * 56, "",
         "Nur company/lookup und people/search - KEINE Anreicherung.", "",
         f"1  Companies tested:                 {k['companies_tested']:>6}",
         f"2  Companies matched by FullEnrich:  {k['companies_matched']:>6}"
         f"  {k['company_match_rate']:>5}%",
         f"3  Companies not found:              {k['companies_not_found']:>6}",
         "",
         f"4  Total people returned:            "
         f"{k['total_people_returned']:>6}",
         f"5  People with a real job title:     "
         f"{k['people_with_real_job_title']:>6}",
         f"6  People WITHOUT a job title:       "
         f"{k['people_without_job_title']:>6}",
         "",
         f"7  Valid decision makers:            "
         f"{k['valid_decision_makers']:>6}",
         f"8  Uncertain (unrelated title):      "
         f"{k['uncertain_decision_makers']:>6}",
         f"9  Company mismatches:               "
         f"{k['company_mismatches']:>6}",
         "",
         f"10 Companies with >=1 valid DM:      "
         f"{k['companies_with_valid_dm']:>6}",
         f"11 Companies with ZERO valid DM:     "
         f"{k['companies_without_valid_dm']:>6}",
         "", "-- Rates --",
         f"FullEnrich company match rate:       "
         f"{k['company_match_rate']:>5}%",
         f"Valid DM rate per company:           "
         f"{k['valid_dm_rate_per_company']:>5}%",
         f"Valid DM rate among returned people: "
         f"{k['valid_dm_rate_among_people']:>5}%",
         f"No-decision-maker rate:              "
         f"{k['no_decision_maker_rate']:>5}%"]
    if guthaben_vorher is not None:
        z += ["", "-- Credits --",
              f"Credits before:                     {guthaben_vorher:>7}",
              f"Credits after:                      {guthaben_nachher:>7}",
              f"Credits consumed:                   "
              f"{round(guthaben_vorher - guthaben_nachher, 2):>7}"]
    z.append("=" * 56)
    return "\n".join(z)


# --------------------------------------------------------------- Auswahl

def kandidaten_waehlen(daten_dir=".", anzahl=25, seed=SEED,
                       bereits_angereichert=()) -> list:
    """Deterministische Kandidaten aus master.db.

    Es wird NICHTS geaendert - nur gelesen. Firmen, die schon eine
    FullEnrich-Anreicherung gesehen haben, fallen raus (Auftrag)."""
    from pipeline.master_db import DB_NAME

    pfad = Path(daten_dir) / DB_NAME
    db = sqlite3.connect(pfad)
    db.row_factory = sqlite3.Row
    zeilen = [dict(z) for z in db.execute(
        """SELECT id, kennung, name, domain, website, plz, ort, land,
                  telefon, sektor
           FROM companies
           WHERE TRIM(COALESCE(name,'')) <> ''
             AND TRIM(COALESCE(domain,'')) <> ''
             AND TRIM(COALESCE(website,'')) <> ''
           ORDER BY kennung""")]
    db.close()
    gesperrt = {str(k).lower() for k in bereits_angereichert}
    frei = [z for z in zeilen if z["kennung"].lower() not in gesperrt]
    wuerfel = random.Random(seed)
    wuerfel.shuffle(frei)
    return frei


def stichprobe_bauen(daten_dir=".", anzahl=25, seed=SEED,
                     bereits_angereichert=(), ki=None, ttl_tage=None,
                     max_kandidaten=60, seiten_leser=None) -> dict:
    """Prueft Kandidaten der Reihe nach und nimmt die ersten `anzahl`,
    die die Automatisierungs-Pruefung mit NO bestehen.

    Kostet KEINE FullEnrich-Credits - nur Webseiten-Abrufe und KI."""
    from pipeline import automation_llm
    from pipeline.website_tiefe import STANDARD_TTL_TAGE, seiten_lesen

    ttl_tage = STANDARD_TTL_TAGE if ttl_tage is None else ttl_tage
    leser = seiten_leser or (lambda w: seiten_lesen(
        w, daten_dir, ttl_tage=ttl_tage))

    kandidaten = kandidaten_waehlen(daten_dir, anzahl, seed,
                                    bereits_angereichert)[:max_kandidaten]
    log(f"Kandidaten geprüft: bis zu {len(kandidaten)}, gesucht: {anzahl} "
        f"mit Automatisierung=NO")

    gewaehlt, verworfen = [], {"YES": 0, "UNCERTAIN": 0}
    for firma in kandidaten:
        if len(gewaehlt) >= anzahl:
            break
        seiten = leser(firma.get("website") or firma.get("domain"))
        urteil = automation_llm.klassifizieren(firma, seiten, ki)
        firma["_automation"] = urteil
        firma["_seiten"] = seiten
        if urteil["automation_status"] == "NO":
            gewaehlt.append(firma)
        else:
            verworfen[urteil["automation_status"]] = verworfen.get(
                urteil["automation_status"], 0) + 1
        if (len(gewaehlt) + sum(verworfen.values())) % 10 == 0:
            log(f"    geprüft: {len(gewaehlt) + sum(verworfen.values())}, "
                f"davon NO: {len(gewaehlt)}")

    ziel = Path(daten_dir) / AUSWAHL_DATEI
    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_text(json.dumps({
        "seed": seed, "gesucht": anzahl, "gefunden": len(gewaehlt),
        "verworfen": verworfen,
        "company_ids": [f["id"] for f in gewaehlt],
        "kennungen": [f["kennung"] for f in gewaehlt],
        "erstellt_am": datetime.now().isoformat(timespec="seconds"),
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"Stichprobe steht: {len(gewaehlt)} Firmen mit Automatisierung=NO "
        f"(verworfen: {verworfen})")
    return {"firmen": gewaehlt, "verworfen": verworfen}


def kosten_schaetzen(anzahl_firmen: int, personen_je_firma: float = 2.0) -> dict:
    """Was der Test kostet - nur Suche, keine Anreicherung."""
    lookup = anzahl_firmen * PREIS_SUCHTREFFER
    suche = anzahl_firmen * personen_je_firma * PREIS_SUCHTREFFER
    return {"company_lookups": round(lookup, 2),
            "people_search": round(suche, 2),
            "gesamt": round(lookup + suche, 2),
            "annahme": f"{personen_je_firma} Personen je Firma im Schnitt"}


# ------------------------------------------------------------------ Lauf

def lauf(daten_dir=".", firmen=None, quelle=None, api_key=None,
         max_credits=None) -> dict:
    """Fuehrt den Abdeckungstest aus. NUR lookup + search."""
    import os

    test_run_id = f"fe-abd-{datetime.now():%Y%m%d-%H%M%S}"
    start = time.time()
    firmen = list(firmen or [])
    quelle = quelle or FullEnrichSource(
        api_key or os.environ.get("FULLENRICH_API_KEY"))

    guthaben_vorher = None
    try:
        guthaben_vorher = quelle.guthaben()
        log(f"Guthaben vor dem Test: {guthaben_vorher}")
    except FullEnrichFehler as fehler:
        log(f"Guthaben nicht lesbar: {fehler}")

    db = sqlite3.connect(Path(daten_dir) / DB_DATEI)
    db.executescript(SCHEMA)
    jetzt = datetime.now().isoformat(timespec="seconds")
    db.execute("INSERT OR REPLACE INTO abdeckung_laeufe "
               "(test_run_id, gestartet_am, seed, firmen, guthaben_vorher) "
               "VALUES (?,?,?,?,?)",
               (test_run_id, jetzt, SEED, len(firmen), guthaben_vorher))
    db.commit()

    firmen_zeilen, alle_personen = [], []
    verbraucht = 0.0
    for nummer, firma in enumerate(firmen, 1):
        urteil = firma.get("_automation") or {}
        zeile = {
            "test_run_id": test_run_id,
            "company_id": firma.get("id"),
            "company_kennung": firma.get("kennung", ""),
            "company_name": firma.get("name", ""),
            "domain": _domain(firma.get("domain") or firma.get("website")),
            "website": firma.get("website", ""),
            "ort": firma.get("ort", ""),
            "automation_status": urteil.get("automation_status", ""),
            "automation_confidence": urteil.get("confidence", 0.0),
            "automation_evidence": (urteil.get("evidence") or "")[:400],
            "automation_source_url": urteil.get("source_url", ""),
            "fullenrich_company_found": 0, "fullenrich_company_name": "",
            "fullenrich_company_domain": "", "company_match_status": "",
            "company_match_score": 0.0, "people_returned": 0,
            "valid_decision_makers": 0, "api_status": "", "error_message": "",
            "created_at": jetzt,
        }

        if max_credits is not None and verbraucht >= max_credits:
            zeile["api_status"] = "budget_exhausted"
            firmen_zeilen.append(zeile)
            continue

        try:
            fe_firma = quelle.firma_finden(zeile["domain"])
            if fe_firma:
                verbraucht += PREIS_SUCHTREFFER
                zeile["fullenrich_company_found"] = 1
                zeile["fullenrich_company_name"] = fe_firma.get("name") or ""
                zeile["fullenrich_company_domain"] = _domain(
                    fe_firma.get("domain") or fe_firma.get("website"))

            leute = quelle.personen_suchen(zeile["domain"], TITEL_VARIANTEN)
            verbraucht += PREIS_SUCHTREFFER * len(leute)
            zeile["people_returned"] = len(leute)

            status, punkte, _ = firmen_abgleich(firma, fe_firma, None)
            zeile["company_match_status"] = status
            zeile["company_match_score"] = punkte

            for person in leute:
                satz = person_beurteilen(person, firma)
                satz.update({"test_run_id": test_run_id,
                             "company_id": firma.get("id"),
                             "company_name": firma.get("name", ""),
                             "company_domain": zeile["domain"],
                             "created_at": jetzt})
                alle_personen.append(satz)
                if satz["urteil"] == "valid":
                    zeile["valid_decision_makers"] += 1
            zeile["api_status"] = "ok"
        except KontingentLeer as fehler:
            zeile["api_status"] = "credits_insufficient"
            zeile["error_message"] = str(fehler)[:300]
            firmen_zeilen.append(zeile)
            log(f"ABBRUCH: {fehler}")
            break
        except FullEnrichFehler as fehler:
            zeile["api_status"] = f"error_{fehler.status or 'unknown'}"
            zeile["error_message"] = str(fehler)[:300]
        except Exception as fehler:      # noqa: BLE001
            zeile["api_status"] = "error_unexpected"
            zeile["error_message"] = f"{type(fehler).__name__}: {fehler}"[:300]

        firmen_zeilen.append(zeile)
        if nummer % 5 == 0:
            log(f"    {nummer}/{len(firmen)} Firmen, "
                f"~{verbraucht:.2f} Credits")

    for zeile in firmen_zeilen:
        spalten = list(zeile)
        db.execute(f"INSERT INTO abdeckung_firmen ({','.join(spalten)}) "
                   f"VALUES ({','.join('?' * len(spalten))})",
                   [zeile[s] for s in spalten])
    for satz in alle_personen:
        spalten = list(satz)
        db.execute(f"INSERT INTO abdeckung_personen ({','.join(spalten)}) "
                   f"VALUES ({','.join('?' * len(spalten))})",
                   [satz[s] for s in spalten])

    guthaben_nachher = None
    try:
        guthaben_nachher = quelle.guthaben()
    except FullEnrichFehler:
        pass

    kennzahlen = kennzahlen_rechnen(firmen_zeilen, alle_personen)
    db.execute("UPDATE abdeckung_laeufe SET beendet_am=?, guthaben_nachher=?,"
               " kennzahlen=? WHERE test_run_id=?",
               (datetime.now().isoformat(timespec="seconds"),
                guthaben_nachher,
                json.dumps(kennzahlen, ensure_ascii=False), test_run_id))
    db.commit()
    db.close()

    ziele = exportieren(firmen_zeilen, alle_personen, daten_dir)
    return {"test_run_id": test_run_id, "kennzahlen": kennzahlen,
            "firmen": firmen_zeilen, "personen": alle_personen,
            "guthaben_vorher": guthaben_vorher,
            "guthaben_nachher": guthaben_nachher,
            "geschaetzt_verbraucht": round(verbraucht, 2),
            "exporte": ziele,
            "laufzeit_minuten": round((time.time() - start) / 60, 1)}


def exportieren(firmen_zeilen, personen, daten_dir=".", stempel=None) -> dict:
    stempel = stempel or datetime.now().strftime("%Y%m%d-%H%M")
    basis = Path(daten_dir)
    ziele = {}

    firmen_pfad = basis / f"fullenrich-abdeckung-firmen-{stempel}.csv"
    with firmen_pfad.open("w", newline="", encoding="utf-8") as f:
        if firmen_zeilen:
            schreiber = csv.DictWriter(f, fieldnames=list(firmen_zeilen[0]))
            schreiber.writeheader()
            schreiber.writerows(firmen_zeilen)
    ziele["firmen_csv"] = firmen_pfad

    personen_pfad = basis / f"fullenrich-abdeckung-personen-{stempel}.csv"
    with personen_pfad.open("w", newline="", encoding="utf-8") as f:
        if personen:
            schreiber = csv.DictWriter(f, fieldnames=list(personen[0]))
            schreiber.writeheader()
            schreiber.writerows(personen)
    ziele["personen_csv"] = personen_pfad
    return ziele
