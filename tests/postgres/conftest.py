"""Gemeinsames Setup fuer die Postgres-Tests (Phase 3, 08.09.2026).

Diese Tests brauchen ein laufendes Postgres:

    docker compose --env-file .env -f deploy/docker-compose.postgres.yml up -d

Ist keines erreichbar, ueberspringen sie sich selbst. Die bestehende
Suite laeuft also unveraendert ohne Docker weiter - SQLite, Pipeline,
Export und web/ merken von diesem ganzen Ordner nichts.
"""
import os
from pathlib import Path

import pytest

psycopg = pytest.importorskip(
    "psycopg", reason="psycopg ist nicht installiert (pip install 'psycopg[binary]')")

# Absichtlich NICHT pipeline.env.lade_dotenv(): das schreibt die ganze
# .env nach os.environ, also auch ANTHROPIC_API_KEY & Co. Damit haetten
# Tests, die "kein Schluessel gesetzt" pruefen, ploetzlich einen - und
# genau das ist hier am 08.09.2026 passiert (test_ki.py und test_cli.py
# fielen um, obwohl sie mit Postgres nichts zu tun haben). Dieser Ordner
# liest deshalb nur seine eigenen drei Werte und fasst os.environ nicht
# an. Dieselben Regeln wie dort: eine echte Shell-Variable gewinnt,
# Anfuehrungszeichen fallen weg.
_BRAUCHT = ("POSTGRES_URL", "POSTGRES_SYNC_URL", "POSTGRES_READ_URL")


def _aus_dotenv() -> dict:
    werte: dict[str, str] = {}
    pfad = Path(__file__).resolve().parents[2] / ".env"
    if not pfad.exists():
        return werte
    for zeile in pfad.read_text(encoding="utf-8").splitlines():
        zeile = zeile.strip()
        if not zeile or zeile.startswith("#") or "=" not in zeile:
            continue
        schluessel, _, wert = zeile.partition("=")
        schluessel, wert = schluessel.strip(), wert.strip()
        if schluessel not in _BRAUCHT:
            continue
        if len(wert) >= 2 and wert[0] == wert[-1] and wert[0] in ("'", '"'):
            wert = wert[1:-1]
        werte[schluessel] = wert
    return werte


_DOTENV = _aus_dotenv()


def _url(name: str) -> str:
    return os.environ.get(name) or _DOTENV.get(name, "")


@pytest.fixture(scope="session")
def postgres_da():
    """Ueberspringt alles, wenn ueberhaupt kein Postgres laeuft.

    Diese eine Stelle entscheidet ueber das Ueberspringen - und sie fragt
    nur, ob die Datenbank da ist. Bekaeme jede Verbindung ihr eigenes
    skip, dann wuerden fehlende Rollen als "uebersprungen" durchgehen,
    und ein uebersprungener Test beweist nichts. Laeuft Postgres, muss
    coldmail_sync sich auch anmelden koennen; kann es das nicht, ist das
    ein Fehler und soll auch einer sein.
    """
    url = _url("POSTGRES_URL")
    if not url:
        pytest.skip("POSTGRES_URL steht nicht in .env (siehe .env.example)")
    try:
        psycopg.connect(url, connect_timeout=3).close()
    except psycopg.OperationalError as fehler:
        pytest.skip(
            "Postgres nicht erreichbar - starten mit: docker compose "
            f"--env-file .env -f deploy/docker-compose.postgres.yml up -d "
            f"({fehler})")


def _verbinden(url_name: str):
    url = _url(url_name)
    assert url, f"{url_name} fehlt in .env (siehe .env.example)"
    # statement_timeout als Reissleine: kein Test darf die Suite
    # anhalten, weil zwei Verbindungen sich gegenseitig sperren. Lieber
    # ein Fehler nach fuenf Sekunden als ein Lauf, der nie endet.
    return psycopg.connect(url, connect_timeout=3,
                           options="-c statement_timeout=5000")


@pytest.fixture
def admin(postgres_da):
    """Der Eigentuemer - darf alles. Nur fuer Aufbau und Aufraeumen."""
    db = _verbinden("POSTGRES_URL")
    try:
        yield db
    finally:
        db.rollback()
        db.close()


@pytest.fixture
def sync(postgres_da):
    """coldmail_sync: kern schreiben, historie nur lesen und anhaengen."""
    db = _verbinden("POSTGRES_SYNC_URL")
    try:
        yield db
    finally:
        db.rollback()
        db.close()


@pytest.fixture
def leser(postgres_da):
    """coldmail_read: ueberall nur lesen."""
    db = _verbinden("POSTGRES_READ_URL")
    try:
        yield db
    finally:
        db.rollback()
        db.close()


TEST_UID = "f-testtesttest"
TEST_UID_2 = "f-testtesttes2"


@pytest.fixture
def testfirma(admin):
    """Eine Firma mit Historie - und danach wieder weg.

    Aufgeraeumt wird in der richtigen Reihenfolge: erst die Historie,
    dann die Firma. Andersherum haelt der Fremdschluessel dagegen, und
    genau das soll er auch.
    """
    with admin.cursor() as c:
        c.execute("DELETE FROM historie.kontakt WHERE firma_uid IN (%s,%s)",
                  (TEST_UID, TEST_UID_2))
        c.execute("DELETE FROM historie.uebergabe WHERE firma_uid IN (%s,%s)",
                  (TEST_UID, TEST_UID_2))
        c.execute("DELETE FROM historie.opt_out WHERE firma_uid IN (%s,%s)",
                  (TEST_UID, TEST_UID_2))
        c.execute("DELETE FROM kern.entscheider WHERE firma_uid IN (%s,%s)",
                  (TEST_UID, TEST_UID_2))
        c.execute("DELETE FROM kern.firma_quelle WHERE firma_uid IN (%s,%s)",
                  (TEST_UID, TEST_UID_2))
        c.execute("UPDATE kern.firma SET zusammengelegt_in=NULL "
                  "WHERE firma_uid IN (%s,%s)", (TEST_UID, TEST_UID_2))
        c.execute("DELETE FROM kern.firma WHERE firma_uid IN (%s,%s)",
                  (TEST_UID, TEST_UID_2))
        c.execute("INSERT INTO kern.firma (firma_uid, kennung, name) "
                  "VALUES (%s,%s,%s), (%s,%s,%s)",
                  (TEST_UID, "test.example", "Test GmbH",
                   TEST_UID_2, "test2.example", "Test Zwei GmbH"))
        c.execute("INSERT INTO historie.opt_out "
                  "(firma_uid, email, datum, weg) VALUES (%s,%s,%s,%s)",
                  (TEST_UID, "nein@test.example", "2026-09-08", "E-Mail"))
        c.execute("INSERT INTO historie.kontakt "
                  "(firma_uid, nummer, datum) VALUES (%s,%s,%s)",
                  (TEST_UID, 1, "2026-09-08"))
        c.execute("INSERT INTO historie.uebergabe "
                  "(firma_uid, name, datum) VALUES (%s,%s,%s)",
                  (TEST_UID, "Ein ColdCaller", "2026-09-08"))
    admin.commit()

    yield TEST_UID

    # Viele Tests hier loesen absichtlich einen Datenbankfehler aus
    # (Fremdschluessel, CHECK). Danach ist die Transaktion abgebrochen
    # und JEDER weitere Befehl scheitert - ohne dieses rollback wuerde
    # das Aufraeumen selbst zum Fehler und die Testfirma bliebe liegen.
    admin.rollback()

    with admin.cursor() as c:
        for tabelle in ("historie.kontakt", "historie.uebergabe",
                        "historie.opt_out", "kern.entscheider",
                        "kern.firma_quelle"):
            c.execute(f"DELETE FROM {tabelle} WHERE firma_uid IN (%s,%s)",
                      (TEST_UID, TEST_UID_2))
        c.execute("UPDATE kern.firma SET zusammengelegt_in=NULL "
                  "WHERE firma_uid IN (%s,%s)", (TEST_UID, TEST_UID_2))
        c.execute("DELETE FROM kern.firma WHERE firma_uid IN (%s,%s)",
                  (TEST_UID, TEST_UID_2))
    admin.commit()
