"""Stamm database: a company keeps one id forever.

Decision Dafina, 08.09.2026 (Phase 2). Three databases now, each with a
different promise:

    master.db      rebuilt from the files on every run (DROP + CREATE).
                   `companies.id` is a row number and changes each time.
    historie.db    never deleted - events that happened (opt-out, contact).
    stamm.db       never deleted - the identity of a company.

`firma_uid` is the id an outside system (Oliver's warehouse) may point
at. `companies.id` is not: it moves as soon as a company is added,
dropped or sorted differently.

## The rules

    one kennung = one firma_uid
    NO automatic merging - not by name, not by name + PLZ
    merging happens only by hand, through set_alias()

Why no automatic merging: two firms can share a name and a postal code
and still be two firms. A wrong merge quietly puts one company's people
under another company's roof, and nothing downstream can notice. A
missed merge only costs a duplicate row - visible, and fixable by hand.
That is the trade the strict rule buys.

## Why the uid is a hash and not a counter

The uid is derived from the kennung, so losing stamm.db does not
renumber the world: a fresh database hands out the same ids again. Only
the hand-made aliases would have to be set again - and those are listed
in `aliase()`, so they can be written down.
"""
from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime
from pathlib import Path

DB_NAME = "daten/stamm.db"

# NO DROP. NO DELETE. Same promise as historie_db - and the same guard:
# tests/test_stamm_db.py::test_schema_has_no_drop_and_no_delete.
#
# firma_uid is deliberately NOT unique. A UNIQUE there would look tidy
# and would make set_alias() - the only merge there is - impossible.
_SCHEMA = """
CREATE TABLE IF NOT EXISTS firma_uid (
    kennung TEXT PRIMARY KEY,
    firma_uid TEXT NOT NULL,
    angelegt_am TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS alias (
    kennung TEXT PRIMARY KEY,
    ziel TEXT NOT NULL,
    notiz TEXT NOT NULL DEFAULT '',
    gesetzt_am TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_stamm_uid ON firma_uid(firma_uid);
"""

# A chain a -> b -> c is fine, a runaway chain is not. set_alias refuses
# to build a cycle, so this only ever trips on a database edited by hand.
_MAX_KETTE = 50


def _jetzt() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _normal(kennung: object) -> str:
    """The rule: never clean up MORE than master_db does.

    master_db._kennung() is `(domain or name).lower()` - it lowercases
    and it does NOT strip. So lowercasing here is free (the value
    arrives lowercased anyway, and it spares a human calling set_alias()
    by hand), but stripping is not: 'eq24pay.de ' and 'eq24pay.de' are
    two separate rows in companies, and handing them one firma_uid would
    put two rows under one id. The Phase 6 upsert would then keep
    whichever came last, decided by iteration order.

    Whitespace stays part of the identity. Putting such a pair together
    is a human decision, made with set_alias() (Dafina, 08.09.2026).
    """
    return str(kennung or "").lower()


def _abgeleitet(kennung: str) -> str:
    """The uid a kennung gets when nothing is stored yet."""
    return "f-" + hashlib.sha256(kennung.encode("utf-8")).hexdigest()[:12]


def verbindung(daten_dir) -> sqlite3.Connection:
    """Opens stamm.db and creates it if it is not there yet."""
    pfad = Path(daten_dir) / DB_NAME
    pfad.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(pfad)
    db.row_factory = sqlite3.Row
    db.executescript(_SCHEMA)
    db.commit()
    return db


def _ziel_kennung(db: sqlite3.Connection, kennung: str) -> str:
    """Follows the alias chain to its end: a -> b -> c returns c."""
    start = kennung
    gesehen = {kennung}
    for _ in range(_MAX_KETTE):
        zeile = db.execute("SELECT ziel FROM alias WHERE kennung=?",
                           (kennung,)).fetchone()
        if zeile is None:
            return kennung
        kennung = zeile["ziel"]
        if kennung in gesehen:
            break
        gesehen.add(kennung)
    raise ValueError(
        f"The alias chain starting at '{start}' loops or is too long. "
        f"Look at the alias table in {DB_NAME}.")


def _uid_lesen(db: sqlite3.Connection, kennung: str) -> str:
    """The stored uid of a kennung, else the one derived from it."""
    zeile = db.execute("SELECT firma_uid FROM firma_uid WHERE kennung=?",
                       (kennung,)).fetchone()
    return zeile["firma_uid"] if zeile else _abgeleitet(kennung)


# --------------------------------------------------------------- Schreiben

def uid_fuer(daten_dir, kennung: str) -> str:
    """The firma_uid of a company - created on first sight, then kept.

    This never merges anything. Two kennungen that look alike stay two
    companies until a human says otherwise with set_alias().
    """
    kennung = _normal(kennung)
    if not kennung:
        raise ValueError("uid_fuer needs a kennung")

    db = verbindung(daten_dir)
    try:
        ziel = _ziel_kennung(db, kennung)
        uid = _uid_lesen(db, ziel)
        with db:
            db.execute(
                "INSERT OR IGNORE INTO firma_uid "
                "(kennung, firma_uid, angelegt_am) VALUES (?,?,?)",
                (ziel, uid, _jetzt()))
    finally:
        db.close()
    return uid


def uids_fuer(daten_dir, kennungen) -> dict[str, str]:
    """uid_fuer() for a whole list - one database open, not thousands.

    master_db asks for every company it just compiled, today around
    10.000 of them. Opening and closing stamm.db per company turned a
    rebuild into minutes of file locking for no reason.

    Same rules as uid_fuer(): nothing is merged that a human did not
    merge by hand, and an empty kennung is skipped, never invented.

    The answer is keyed by the string the caller passed in, NOT by the
    cleaned-up one. master_db lowercases its kennung but does not strip
    it, so 'eq24pay.de ' really does turn up in the real run files. A
    caller must find its own key back, otherwise one stray space in one
    file stops the whole rebuild.
    """
    roh_je_kennung: dict[str, list[str]] = {}
    for roh in kennungen:
        kennung = _normal(roh)
        if kennung:
            roh_je_kennung.setdefault(kennung, []).append(roh)
    if not roh_je_kennung:
        return {}

    db = verbindung(daten_dir)
    try:
        ergebnis, neu = {}, []
        jetzt = _jetzt()
        for kennung, rohformen in roh_je_kennung.items():
            ziel = _ziel_kennung(db, kennung)
            uid = _uid_lesen(db, ziel)
            for roh in rohformen:
                ergebnis[roh] = uid
            neu.append((ziel, uid, jetzt))
        with db:
            db.executemany(
                "INSERT OR IGNORE INTO firma_uid "
                "(kennung, firma_uid, angelegt_am) VALUES (?,?,?)", neu)
    finally:
        db.close()
    return ergebnis


def set_alias(daten_dir, kennung: str, ziel_kennung: str,
              notiz: str = "") -> str:
    """Say by hand that two kennungen are the same company.

    The only way two rows ever end up under one firma_uid. `notiz` is
    what makes a merge explainable months later - who decided it, and on
    what grounds. Undo it with alias_loesen().
    """
    kennung, ziel_kennung = _normal(kennung), _normal(ziel_kennung)
    if not kennung or not ziel_kennung:
        raise ValueError("set_alias needs both kennung and ziel_kennung")
    if kennung == ziel_kennung:
        raise ValueError(f"'{kennung}' cannot be an alias of itself.")

    db = verbindung(daten_dir)
    try:
        # Would this close a circle? a -> b and then b -> a would leave
        # no company to point at.
        lauf, gesehen = ziel_kennung, {ziel_kennung}
        for _ in range(_MAX_KETTE):
            zeile = db.execute("SELECT ziel FROM alias WHERE kennung=?",
                               (lauf,)).fetchone()
            if zeile is None:
                break
            lauf = zeile["ziel"]
            if lauf == kennung:
                raise ValueError(
                    f"'{kennung}' -> '{ziel_kennung}' would close a circle: "
                    f"'{ziel_kennung}' already points at '{kennung}'.")
            if lauf in gesehen:
                break
            gesehen.add(lauf)

        with db:
            db.execute(
                "INSERT OR REPLACE INTO alias "
                "(kennung, ziel, notiz, gesetzt_am) VALUES (?,?,?,?)",
                (kennung, ziel_kennung, notiz, _jetzt()))
        ziel = _ziel_kennung(db, kennung)
        uid = _uid_lesen(db, ziel)
        with db:
            # The old row of `kennung` now points at the target's uid, so
            # a reader that never resolves aliases still sees the merge.
            db.execute(
                "INSERT OR IGNORE INTO firma_uid "
                "(kennung, firma_uid, angelegt_am) VALUES (?,?,?)",
                (ziel, uid, _jetzt()))
            db.execute("UPDATE firma_uid SET firma_uid=? WHERE kennung=?",
                       (uid, kennung))
    finally:
        db.close()
    return uid


def alias_loesen(daten_dir, kennung: str) -> bool:
    """Undo one merge. Returns False if there was nothing to undo.

    A merge nobody can undo is a merge nobody dares to make.
    """
    kennung = _normal(kennung)
    if not kennung:
        raise ValueError("alias_loesen needs a kennung")
    pfad = Path(daten_dir) / DB_NAME
    if not pfad.exists():
        return False

    db = verbindung(daten_dir)
    try:
        with db:
            geloescht = db.execute("DELETE FROM alias WHERE kennung=?",
                                   (kennung,)).rowcount
            db.execute("UPDATE firma_uid SET firma_uid=? WHERE kennung=?",
                       (_abgeleitet(kennung), kennung))
    finally:
        db.close()
    return bool(geloescht)


# ------------------------------------------------------------------ Lesen

def alle(daten_dir) -> dict[str, str]:
    """{kennung: firma_uid} for everything stamm.db knows."""
    pfad = Path(daten_dir) / DB_NAME
    if not pfad.exists():
        return {}
    db = verbindung(daten_dir)
    try:
        kennungen = {z["kennung"] for z in db.execute(
            "SELECT kennung FROM firma_uid")}
        kennungen |= {z["kennung"] for z in db.execute(
            "SELECT kennung FROM alias")}
        return {k: _uid_lesen(db, _ziel_kennung(db, k))
                for k in sorted(kennungen)}
    finally:
        db.close()


def aliase(daten_dir) -> dict[str, dict]:
    """Every merge made by hand: {kennung: {ziel, notiz, gesetzt_am}}."""
    pfad = Path(daten_dir) / DB_NAME
    if not pfad.exists():
        return {}
    db = verbindung(daten_dir)
    try:
        return {z["kennung"]: {"ziel": z["ziel"], "notiz": z["notiz"] or "",
                               "gesetzt_am": z["gesetzt_am"]}
                for z in db.execute("SELECT * FROM alias ORDER BY kennung")}
    finally:
        db.close()
