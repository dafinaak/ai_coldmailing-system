"""Company master database - a regenerable read model over the run files.

Oliver's spec (19.08.2026) asks for a durable, reusable company master
with provenance, decision-makers, automation classification, campaign
eligibility, completeness and an A-E export. The SAFEST migration for
this codebase is NOT to replace the proven file storage (collections and
run folders are crash-safe, append-only, and covered by the whole test
suite) but to COMPILE it: this module builds `daten/master.db` (SQLite)
from everything on disk. Delete the file - nothing is lost; the next
build recreates it. The files stay the source of truth for runs; the
master is the source of truth for questions ("which companies, how
complete, which are campaign-eligible, and where does each fact come
from").

Tables:
  companies        one row per unique company (domain, else name)
  company_sources  provenance: one row per company and source/run,
                   with the raw record as JSON evidence
  decision_makers  every found leader, priority-sorted, personal and
                   general emails kept apart

Campaign eligibility is STRICT on purpose (spec 16): it requires the
automation check to have run and said "no", a decision-maker, and a
verified personal address. Everything else stays stored with an honest
`ineligibility_reason` - excluded is not deleted.
"""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path

from pipeline.decision_maker import rank_role
from pipeline.firmen_filter import stadt

DB_NAME = "daten/master.db"

_SCHEMA = """
DROP TABLE IF EXISTS companies;
DROP TABLE IF EXISTS company_sources;
DROP TABLE IF EXISTS decision_makers;
CREATE TABLE companies (
    id INTEGER PRIMARY KEY,
    kennung TEXT UNIQUE NOT NULL,
    name TEXT, domain TEXT, website TEXT,
    strasse TEXT, plz TEXT, ort TEXT, bundesland TEXT,
    land TEXT DEFAULT 'Deutschland',
    telefon TEXT, email_allgemein TEXT,
    sektor TEXT, keywords TEXT, beschreibung TEXT, mitarbeiter TEXT,
    ceo_owner TEXT,
    offers_automation_services TEXT DEFAULT 'not_checked',
    automation_check_reason TEXT, automation_checked_at TEXT,
    campaign_eligible INTEGER, ineligibility_reason TEXT,
    completeness INTEGER,
    created_at TEXT, updated_at TEXT, last_enriched_at TEXT
);
CREATE TABLE company_sources (
    id INTEGER PRIMARY KEY,
    company_id INTEGER NOT NULL,
    provider TEXT, herkunft TEXT, collected_at TEXT,
    felder TEXT
);
CREATE TABLE decision_makers (
    id INTEGER PRIMARY KEY,
    company_id INTEGER NOT NULL,
    name TEXT, vorname TEXT, nachname TEXT, rolle TEXT,
    email TEXT, email_art TEXT, telefon TEXT, linkedin TEXT,
    quelle TEXT, status TEXT, bereich TEXT, created_at TEXT
);
"""

# "Rolandstr. 2-3, 30161 Hannover" -> "Rolandstr. 2-3"
_PLZ_SCHWANZ = re.compile(r",?\s*\b\d{5}\b.*$")


def _strasse(adresse: object) -> str:
    text = str(adresse or "").strip()
    return _PLZ_SCHWANZ.sub("", text).strip(" ,") if text else ""


def _kennung(firma: dict) -> str:
    return (firma.get("domain") or firma.get("name") or "").lower()


def _zeit(pfad: Path) -> str:
    try:
        return datetime.fromtimestamp(pfad.stat().st_mtime).isoformat(
            timespec="seconds")
    except OSError:
        return ""


def _sammlungen(daten_dir: Path):
    wurzel = daten_dir / "laeufe" / "leadquellen"
    for pfad in sorted(wurzel.glob("*/firmen.json")) if wurzel.exists() else []:
        yield pfad.parent.name, pfad


def _lauf_ordner(daten_dir: Path):
    wurzel = daten_dir / "laeufe"
    for pfad in sorted(wurzel.glob("*/*/firmen.json")) if wurzel.exists() else []:
        if "leadquellen" in pfad.parts:
            continue
        yield f"{pfad.parent.parent.name}/{pfad.parent.name}", pfad


def _json_liste(pfad: Path) -> list:
    try:
        daten = json.loads(pfad.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return daten if isinstance(daten, list) else []


def _firma_uebernehmen(bekannt: dict, neu: dict) -> None:
    """Leere Felder auffuellen - nie ueberschreiben (Olivers Regel)."""
    for feld in ("name", "website", "domain", "address", "plz", "ort",
                 "telefon", "vorhandene_email", "gf_name_liste"):
        if not bekannt.get(feld) and neu.get(feld):
            bekannt[feld] = neu[feld]
    for kat in neu.get("categories") or []:
        if kat not in bekannt.setdefault("categories", []):
            bekannt["categories"].append(kat)
    # Lauf-Felder (Entscheider, Automatisierung, Ausgang): der NEUERE
    # Lauf gewinnt - er ist der aktuellere Wissensstand. Nur GEFUELLTE
    # Werte gewinnen; ein Lauf ohne Befund loescht keinen alten.
    for feld in ("entscheider", "entscheider_primaer",
                 "offers_automation_services", "automation_check_reason",
                 "automation_checked_at", "campaign_ineligibility_reason",
                 "ausgang", "leads"):
        if neu.get(feld):
            bekannt[feld] = neu[feld]


def _leads_je_firma(lauf_pfad: Path) -> dict:
    """E-Mails aus leads.json des Laufs, nach Firmen-Domain gruppiert."""
    daten = {}
    pfad = lauf_pfad.parent / "leads.json"
    try:
        inhalt = json.loads(pfad.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return daten
    eintraege = inhalt.get("leads") if isinstance(inhalt, dict) else inhalt
    for lead in eintraege or []:
        domain = str(lead.get("email", "")).split("@")[-1].lower()
        daten.setdefault(domain, []).append(lead)
    return daten


def _entscheider_zeilen(firma: dict, leads: list) -> list:
    """Alle Personen einer Firma - aus dem Firmensatz plus Lauf-Leads."""
    zeilen = []
    gesehen = set()
    for person in firma.get("entscheider") or []:
        name = person.get("name") or ""
        if not name or name.lower() in gesehen:
            continue
        gesehen.add(name.lower())
        zeilen.append({
            "name": name, "vorname": person.get("vorname", ""),
            "nachname": person.get("nachname", ""),
            "rolle": person.get("rolle", ""),
            "email": person.get("email", ""),
            "email_art": "persoenlich" if person.get("email") else "",
            "linkedin": person.get("linkedin"),
            "quelle": person.get("quelle", ""),
            "status": person.get("status", "")})
    for lead in leads:
        name = f"{lead.get('first_name', '')} {lead.get('last_name', '')}".strip()
        if lead.get("source") == "info@" or not name:
            continue      # info@ ist keine Person - steht als email_allgemein
        if name.lower() in gesehen:
            for zeile in zeilen:
                if zeile["name"].lower() == name.lower() and not zeile["email"]:
                    zeile["email"] = lead.get("email", "")
                    zeile["email_art"] = "persoenlich"
                    zeile["status"] = zeile["status"] or "mail_geprueft"
            continue
        gesehen.add(name.lower())
        zeilen.append({"name": name, "vorname": lead.get("first_name", ""),
                       "nachname": lead.get("last_name", ""),
                       "rolle": lead.get("title", ""),
                       "email": lead.get("email", ""),
                       "email_art": "persoenlich",
                       "linkedin": None, "quelle": lead.get("source", ""),
                       "status": "mail_geprueft"})
    zeilen.sort(key=lambda z: rank_role(z.get("rolle")))
    return zeilen


def _eligibility(firma: dict, personen: list) -> tuple:
    """(campaign_eligible, grund) - streng nach Olivers Auftrag Punkt 16."""
    automation = firma.get("offers_automation_services") or "not_checked"
    if automation == "yes":
        return 0, "automation_provider"
    if automation == "uncertain":
        return 0, "automation_uncertain"
    if automation == "not_checked":
        return 0, "automation_not_checked"
    if not personen:
        return 0, "no_decision_maker"
    if not any(p.get("email") and p.get("status") == "mail_geprueft"
               for p in personen):
        return 0, "personal_decision_maker_email_missing"
    return 1, ""


def _completeness(firma: dict, personen: list) -> int:
    punkte = (
        bool(firma.get("name")),
        bool(firma.get("plz") or firma.get("ort") or firma.get("address")),
        bool(firma.get("website")),
        bool(firma.get("categories")),
        bool(personen),
        any(p.get("email") for p in personen),
        (firma.get("offers_automation_services") or "not_checked")
        != "not_checked",
    )
    return round(100 * sum(punkte) / len(punkte))


def bauen(daten_dir=".") -> dict:
    """Master-Datenbank frisch aus den Dateien bauen. Gibt Zahlen zurueck."""
    daten_dir = Path(daten_dir)
    firmen: dict = {}
    herkuenfte: dict = {}

    for ordner, pfad in _sammlungen(daten_dir):
        zeit = _zeit(pfad)
        for firma in _json_liste(pfad):
            kennung = _kennung(firma)
            if not kennung:
                continue
            satz = firmen.setdefault(kennung, {"categories": []})
            _firma_uebernehmen(satz, firma)
            quellen = firma.get("quellen") or (
                [firma["quelle"]] if firma.get("quelle") else ["?"])
            for quelle in quellen:
                herkuenfte.setdefault(kennung, []).append(
                    (str(quelle).split("+")[0], f"sammlung:{ordner}", zeit,
                     firma))

    for lauf, pfad in _lauf_ordner(daten_dir):
        zeit = _zeit(pfad)
        leads = _leads_je_firma(pfad)
        for firma in _json_liste(pfad):
            kennung = _kennung(firma)
            if not kennung:
                continue
            satz = firmen.setdefault(kennung, {"categories": []})
            firmen_leads = leads.get(str(firma.get("domain") or "").lower(), [])
            _firma_uebernehmen(satz, {**firma, "leads": firmen_leads})
            herkuenfte.setdefault(kennung, []).append(
                ("lauf", f"lauf:{lauf}", zeit, firma))

    # Pool-Klassifikation (Phase 2, 20.08.2026) einmischen: das dort
    # gespeicherte Automatisierungs-Urteil gilt fuer jede Firma, die aus
    # keinem Lauf ein eigenes (neueres) Urteil mitbringt.
    from pipeline.automation_klassifikation import laden as _klass_laden
    for kennung, urteil in _klass_laden(daten_dir).items():
        satz = firmen.get(kennung)
        if satz is not None and not satz.get("offers_automation_services"):
            for feld in ("offers_automation_services",
                         "automation_check_reason", "automation_checked_at"):
                satz[feld] = urteil.get(feld, "")

    ziel = daten_dir / DB_NAME
    ziel.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(ziel)
    db.executescript(_SCHEMA)
    jetzt = datetime.now().isoformat(timespec="seconds")
    anzahl_personen = 0

    for kennung, firma in firmen.items():
        personen = _entscheider_zeilen(firma, firma.get("leads") or [])
        eligible, grund = _eligibility(firma, personen)
        primaer = firma.get("entscheider_primaer") or {}
        ceo_owner = " - ".join(
            t for t in (primaer.get("name"),
                        primaer.get("rolle")) if t) or firma.get(
                            "gf_name_liste", "")
        allgemein = firma.get("vorhandene_email", "")
        for lead in firma.get("leads") or []:
            if lead.get("source") == "info@":
                allgemein = allgemein or lead.get("email", "")
        cursor = db.execute(
            """INSERT INTO companies (kennung, name, domain, website,
               strasse, plz, ort, telefon, email_allgemein, sektor,
               keywords, ceo_owner, offers_automation_services,
               automation_check_reason, automation_checked_at,
               campaign_eligible, ineligibility_reason, completeness,
               created_at, updated_at, last_enriched_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (kennung, firma.get("name", ""), firma.get("domain", ""),
             firma.get("website", ""), _strasse(firma.get("address")),
             firma.get("plz", ""), stadt(firma), firma.get("telefon", ""),
             allgemein,
             ", ".join(str(k) for k in (firma.get("categories") or [])[:5]),
             ", ".join(str(k) for k in firma.get("categories") or []),
             ceo_owner,
             firma.get("offers_automation_services") or "not_checked",
             firma.get("automation_check_reason", ""),
             firma.get("automation_checked_at", ""),
             eligible, grund, _completeness(firma, personen),
             jetzt, jetzt, firma.get("automation_checked_at") or ""))
        company_id = cursor.lastrowid
        for provider, herkunft, zeit, roh in herkuenfte.get(kennung, []):
            db.execute(
                """INSERT INTO company_sources
                   (company_id, provider, herkunft, collected_at, felder)
                   VALUES (?,?,?,?,?)""",
                (company_id, provider, herkunft, zeit,
                 json.dumps(roh, ensure_ascii=False)))
        for person in personen:
            db.execute(
                """INSERT INTO decision_makers
                   (company_id, name, vorname, nachname, rolle, email,
                    email_art, telefon, linkedin, quelle, status, bereich,
                    created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (company_id, person["name"], person["vorname"],
                 person["nachname"], person["rolle"], person["email"],
                 person["email_art"], "", person["linkedin"],
                 person["quelle"], person["status"], "", jetzt))
            anzahl_personen += 1

    db.commit()
    zahlen = {
        "firmen": len(firmen),
        "entscheider": anzahl_personen,
        "kampagnenfaehig": db.execute(
            "SELECT COUNT(*) FROM companies WHERE campaign_eligible=1"
        ).fetchone()[0],
        "quellen_belege": db.execute(
            "SELECT COUNT(*) FROM company_sources").fetchone()[0],
        "pfad": str(ziel),
    }
    db.close()
    return zahlen


# ------------------------------------------------------------------ Export

KOPF_FIRMEN = [
    "Datenquelle (woher, wann)", "Sektor", "Firma", "Kurzbeschreibung",
    "Auswahl-Stichworte", "Mitarbeiterzahl", "CEO/Inhaber", "Straße",
    "Ort", "PLZ", "Bundesland", "Land", "Tel", "E-Mail (allgemein)",
    "Webseite",
]
_AE = ("A", "B", "C", "D", "E")
KOPF_SYSTEM = ["Automatisierungs-Anbieter", "Kampagnenfähig",
               "Ausschlussgrund", "Vollständigkeit %",
               "Zuletzt angereichert"]


def export_excel(daten_dir=".", ziel=None):
    """Ein Blatt, eine Zeile je Firma, Entscheider A-E (Olivers Spalten)."""
    import openpyxl

    daten_dir = Path(daten_dir)
    bauen(daten_dir)
    db = sqlite3.connect(daten_dir / DB_NAME)
    db.row_factory = sqlite3.Row

    wb = openpyxl.Workbook()
    blatt = wb.active
    blatt.title = "Firmen-Master"
    kopf = list(KOPF_FIRMEN)
    for buchstabe in _AE:
        kopf += [f"{buchstabe}) Bereich", f"{buchstabe}) Name",
                 f"{buchstabe}) Rolle", f"{buchstabe}) Tel",
                 f"{buchstabe}) E-Mail"]
    kopf += KOPF_SYSTEM
    blatt.append(kopf)

    for firma in db.execute("SELECT * FROM companies ORDER BY name"):
        quellen = db.execute(
            """SELECT provider, herkunft, collected_at FROM company_sources
               WHERE company_id=? ORDER BY id""", (firma["id"],)).fetchall()
        datenquelle = "; ".join(
            f"{q['provider']} ({q['herkunft']}, {q['collected_at'] or '?'})"
            for q in quellen[:4]) + (" …" if len(quellen) > 4 else "")
        personen = db.execute(
            """SELECT * FROM decision_makers WHERE company_id=?
               ORDER BY id""", (firma["id"],)).fetchall()
        zeile = [
            datenquelle, firma["sektor"], firma["name"], "", firma["keywords"],
            firma["mitarbeiter"] or "", firma["ceo_owner"], firma["strasse"],
            firma["ort"], firma["plz"], firma["bundesland"] or "",
            firma["land"], firma["telefon"], firma["email_allgemein"],
            firma["website"],
        ]
        for nummer in range(len(_AE)):
            if nummer < len(personen):
                p = personen[nummer]
                zeile += [p["bereich"] or "", p["name"], p["rolle"],
                          p["telefon"] or "", p["email"]]
            else:
                zeile += ["", "", "", "", ""]
        zeile += [firma["offers_automation_services"],
                  "ja" if firma["campaign_eligible"] else "nein",
                  firma["ineligibility_reason"],
                  firma["completeness"], firma["last_enriched_at"]]
        blatt.append(zeile)

    db.close()
    ziel = Path(ziel) if ziel else daten_dir / "firmen-master.xlsx"
    wb.save(ziel)
    return ziel
