"""Historie-Datenbank: was einmal passiert ist, bleibt.

Entscheidung Dafina, 28.08.2026 (Weg A - zwei getrennte Datenbanken):

    master.db      wird aus den Dateien NEU GEBAUT (DROP + CREATE).
    historie.db    wird NIE geloescht.

Warum getrennte Dateien und nicht nur getrennte Tabellen: der Schutz soll
nicht davon abhaengen, dass jemand beim naechsten Umbau an ein DROP denkt.
Zwei Dateien heisst, der Neubau kann die Historie gar nicht erreichen.

Hier stehen die drei Feldgruppen aus Olivers DataWarehouse-Liste, die sich
nicht berechnen lassen, weil sie Ereignisse sind:

    - Kontakt rausgegeben an ColdCaller/Handelsvertreter
    - 1./2./3. Kontakt (Produkt, durch wen, Weg, Resultat, Datum, Absender)
    - Opt-Out (Datum, auf welchem Weg)

Das Opt-Out ist der Grund, warum es diese Datei ueberhaupt gibt. Geht ein
Widerspruch verloren, schreiben wir jemandem, der Nein gesagt hat.
"""
from __future__ import annotations

import re
import sqlite3
from datetime import datetime
from pathlib import Path

DB_NAME = "daten/historie.db"

# KEIN DROP. Kein DELETE. Wer das aendert, bricht die Zusage dieses Wegs -
# tests/test_historie_db.py::test_schema_enthaelt_kein_drop haelt dagegen.
_SCHEMA = """
CREATE TABLE IF NOT EXISTS coldcaller_uebergabe (
    id INTEGER PRIMARY KEY,
    kennung TEXT NOT NULL,
    name TEXT NOT NULL,
    art_der_person TEXT,
    datum TEXT NOT NULL,
    notiz TEXT,
    erfasst_am TEXT NOT NULL,
    UNIQUE(kennung, name, datum)
);
CREATE TABLE IF NOT EXISTS kontakt_versuch (
    id INTEGER PRIMARY KEY,
    kennung TEXT NOT NULL,
    person_email TEXT NOT NULL DEFAULT '',
    nummer INTEGER NOT NULL,
    produkt TEXT,
    durch_wen TEXT,
    weg TEXT,
    resultat TEXT,
    datum TEXT NOT NULL,
    absender_email TEXT,
    erfasst_am TEXT NOT NULL,
    UNIQUE(kennung, person_email, nummer)
);
CREATE TABLE IF NOT EXISTS opt_out (
    id INTEGER PRIMARY KEY,
    kennung TEXT NOT NULL DEFAULT '',
    email TEXT NOT NULL DEFAULT '',
    datum TEXT NOT NULL,
    weg TEXT,
    notiz TEXT,
    erfasst_am TEXT NOT NULL,
    UNIQUE(kennung, email)
);
CREATE INDEX IF NOT EXISTS idx_uebergabe_kennung
    ON coldcaller_uebergabe(kennung);
CREATE INDEX IF NOT EXISTS idx_kontakt_kennung ON kontakt_versuch(kennung);
CREATE INDEX IF NOT EXISTS idx_optout_kennung ON opt_out(kennung);
"""


def _jetzt() -> str:
    return datetime.now().isoformat(timespec="seconds")


def domain_normal(wert: object) -> str:
    """'https://WWW.Beispiel.de/kontakt' -> 'beispiel.de'.

    Ein Widerspruch darf nicht an der Schreibweise scheitern, deshalb wird
    er in derselben Form abgelegt, die master.db als Kennung benutzt.
    """
    ohne = re.sub(r"^https?://", "", str(wert or "").strip().lower())
    return re.sub(r"^www\.", "", ohne).split("/")[0].split("?")[0]


def verbindung(daten_dir) -> sqlite3.Connection:
    """Oeffnet historie.db und legt sie an, falls es sie noch nicht gibt."""
    pfad = Path(daten_dir) / DB_NAME
    pfad.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(pfad)
    db.row_factory = sqlite3.Row
    db.executescript(_SCHEMA)
    db.commit()
    return db


# --------------------------------------------------------------- Schreiben

def uebergabe_eintragen(daten_dir, kennung: str, name: str, datum: str,
                        art_der_person: str = "", notiz: str = "") -> None:
    """Kontakt wurde an einen ColdCaller/Handelsvertreter rausgegeben."""
    if not (kennung and name and datum):
        raise ValueError("uebergabe braucht kennung, name und datum")
    db = verbindung(daten_dir)
    with db:
        db.execute(
            """INSERT OR IGNORE INTO coldcaller_uebergabe
               (kennung, name, art_der_person, datum, notiz, erfasst_am)
               VALUES (?,?,?,?,?,?)""",
            (domain_normal(kennung) or kennung, name, art_der_person, datum,
             notiz, _jetzt()))
    db.close()


def kontakt_eintragen(daten_dir, kennung: str, nummer: int, datum: str,
                      person_email: str = "", produkt: str = "",
                      durch_wen: str = "", weg: str = "",
                      resultat: str = "", absender_email: str = "") -> None:
    """Ein Kontaktversuch - Olivers "1./2./3. Kontakt".

    Zweimal derselbe Versuch bleibt ein Eintrag: ein Skript darf doppelt
    laufen, ohne die Historie aufzublaehen.
    """
    if nummer not in (1, 2, 3):
        raise ValueError(f"kontakt-nummer muss 1, 2 oder 3 sein, war {nummer}")
    if not (kennung and datum):
        raise ValueError("kontakt braucht kennung und datum")
    db = verbindung(daten_dir)
    with db:
        db.execute(
            """INSERT OR IGNORE INTO kontakt_versuch
               (kennung, person_email, nummer, produkt, durch_wen, weg,
                resultat, datum, absender_email, erfasst_am)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (domain_normal(kennung) or kennung, (person_email or "").lower(),
             nummer, produkt, durch_wen, weg, resultat, datum,
             absender_email, _jetzt()))
    db.close()


def opt_out_eintragen(daten_dir, datum: str, weg: str = "",
                      domain: str = "", email: str = "",
                      notiz: str = "") -> None:
    """Widerspruch: die ganze Firma (domain) oder eine Person (email).

    Beides gleichzeitig ist erlaubt - so wurde am 21.08.2026 auch in der
    Sperrliste verfahren, weil eine Person sperrbar sein muss, ohne dass
    man raten muss, welche Domain gerade gilt.
    """
    domain, email = domain_normal(domain), (email or "").strip().lower()
    if not (domain or email):
        raise ValueError("opt-out braucht domain oder email")
    if not datum:
        raise ValueError("opt-out braucht ein datum")
    db = verbindung(daten_dir)
    with db:
        db.execute(
            """INSERT OR IGNORE INTO opt_out
               (kennung, email, datum, weg, notiz, erfasst_am)
               VALUES (?,?,?,?,?,?)""",
            (domain, email, datum, weg, notiz, _jetzt()))
    db.close()


# ----------------------------------------------------------------- Lesen

def opt_outs(daten_dir) -> list[dict]:
    """Alle Widersprueche, in der Form der Sperrlisten-Eintraege."""
    pfad = Path(daten_dir) / DB_NAME
    if not pfad.exists():
        return []
    db = verbindung(daten_dir)
    zeilen = db.execute(
        "SELECT kennung, email, datum, weg, notiz FROM opt_out "
        "ORDER BY id").fetchall()
    db.close()
    return [{"domain": z["kennung"], "email": z["email"], "datum": z["datum"],
             "weg": z["weg"] or "", "notiz": z["notiz"] or ""} for z in zeilen]


def historie(daten_dir) -> dict:
    """Alles je Firma: {kennung: {uebergaben, kontakte, opt_out}}."""
    pfad = Path(daten_dir) / DB_NAME
    if not pfad.exists():
        return {}
    db = verbindung(daten_dir)
    ergebnis: dict[str, dict] = {}

    def eintrag(kennung):
        return ergebnis.setdefault(
            kennung, {"uebergaben": [], "kontakte": [], "opt_out": None})

    for z in db.execute("SELECT * FROM coldcaller_uebergabe ORDER BY datum, id"):
        eintrag(z["kennung"])["uebergaben"].append({
            "name": z["name"], "art_der_person": z["art_der_person"] or "",
            "datum": z["datum"], "notiz": z["notiz"] or ""})

    for z in db.execute("SELECT * FROM kontakt_versuch ORDER BY nummer, id"):
        eintrag(z["kennung"])["kontakte"].append({
            "nummer": z["nummer"], "person_email": z["person_email"],
            "produkt": z["produkt"] or "", "durch_wen": z["durch_wen"] or "",
            "weg": z["weg"] or "", "resultat": z["resultat"] or "",
            "datum": z["datum"], "absender_email": z["absender_email"] or ""})

    for z in db.execute("SELECT * FROM opt_out WHERE kennung != '' ORDER BY id"):
        eintrag(z["kennung"])["opt_out"] = {
            "datum": z["datum"], "weg": z["weg"] or "",
            "notiz": z["notiz"] or ""}

    db.close()
    return ergebnis
