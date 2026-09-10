"""Die zwei Rollen - und zwar wirklich ausprobiert (Phase 3, 08.09.2026).

    coldmail_sync   kern:     SELECT INSERT UPDATE DELETE
                    historie: NUR SELECT und INSERT
    coldmail_read   ueberall: NUR SELECT

Warum coldmail_sync die Historie nicht aendern oder loeschen darf: ein
Fehler im Sync der Phase 6 - eine falsche WHERE-Bedingung reicht - wuerde
sonst Widersprueche wegraeumen. Danach schreiben wir Leuten, die Nein
gesagt haben. Das ist der eine Schaden, den man nicht zuruecknehmen kann,
also nimmt die Datenbank dem Sync die Moeglichkeit ganz weg.

Ein GRANT hinzuschreiben beweist davon nichts. Diese Tests fuehren die
verbotenen Befehle wirklich aus und bestehen nur, wenn Postgres sie mit
InsufficientPrivilege abweist. Geprueft wird genau dieser Fehler, nicht
"irgendein Fehler" - sonst wuerde ein Tippfehler im Tabellennamen als
bestandener Test durchgehen.
"""
import pytest

psycopg = pytest.importorskip("psycopg")

VERBOTEN = psycopg.errors.InsufficientPrivilege

pytestmark = pytest.mark.postgres


def _verboten(db, sql, *args):
    """Fuehrt sql aus und verlangt, dass Postgres es wegen fehlender
    Rechte abweist.

    Das rollback steht in einem finally, und das ist kein Schoenheits-
    fehler: geht das Recht eines Tages doch durch, dann LAEUFT der
    Befehl, pytest.raises schlaegt am Ende des with-Blocks fehl, und ein
    rollback danach wuerde nie erreicht. Die offene Transaktion haelt
    dann ihre Sperren, und das Aufraeumen der Testfirma wartet ewig auf
    sie - die Suite haengt, statt zu scheitern. Ein haengender Test sagt
    niemandem etwas; ein roter sagt alles.
    """
    try:
        with pytest.raises(VERBOTEN):
            with db.cursor() as c:
                c.execute(sql, args or None)
    finally:
        db.rollback()


# --------------------------------------------------------- coldmail_sync

def test_sync_darf_kern_lesen(sync, testfirma):
    with sync.cursor() as c:
        c.execute("SELECT name FROM kern.firma WHERE firma_uid=%s",
                  (testfirma,))
        assert c.fetchone()[0] == "Test GmbH"


def test_sync_darf_kern_schreiben_aendern_und_loeschen(sync):
    """Der Spiegel muss kern neu schreiben duerfen - dort steht nichts,
    was nicht aus master.db wieder herstellbar waere."""
    with sync.cursor() as c:
        c.execute("INSERT INTO kern.firma (firma_uid, kennung, name) "
                  "VALUES ('f-syncprobe', 'sync.example', 'Vorher')")
        c.execute("UPDATE kern.firma SET name='Nachher' "
                  "WHERE firma_uid='f-syncprobe'")
        c.execute("SELECT name FROM kern.firma WHERE firma_uid='f-syncprobe'")
        assert c.fetchone()[0] == "Nachher"
        c.execute("DELETE FROM kern.firma WHERE firma_uid='f-syncprobe'")
        c.execute("SELECT COUNT(*) FROM kern.firma "
                  "WHERE firma_uid='f-syncprobe'")
        assert c.fetchone()[0] == 0
    sync.rollback()


def test_sync_darf_entscheider_und_quelle_schreiben(sync, testfirma):
    with sync.cursor() as c:
        c.execute("INSERT INTO kern.entscheider (firma_uid, name) "
                  "VALUES (%s, 'Wer Auchimmer')", (testfirma,))
        c.execute("INSERT INTO kern.firma_quelle (firma_uid, provider) "
                  "VALUES (%s, 'probe')", (testfirma,))
        c.execute("DELETE FROM kern.entscheider WHERE firma_uid=%s",
                  (testfirma,))
    sync.rollback()


def test_sync_darf_historie_lesen(sync, testfirma):
    with sync.cursor() as c:
        c.execute("SELECT COUNT(*) FROM historie.opt_out WHERE firma_uid=%s",
                  (testfirma,))
        assert c.fetchone()[0] == 1


def test_sync_darf_historie_anhaengen(sync, testfirma):
    """Anhaengen ja - neue Ereignisse muessen ankommen duerfen."""
    with sync.cursor() as c:
        c.execute("INSERT INTO historie.kontakt (firma_uid, nummer, datum) "
                  "VALUES (%s, 5, '2026-09-08')", (testfirma,))
        c.execute("INSERT INTO historie.uebergabe (firma_uid, name, datum) "
                  "VALUES (%s, 'Noch einer', '2026-09-08')", (testfirma,))
        c.execute("INSERT INTO historie.opt_out (firma_uid, email, datum) "
                  "VALUES (%s, 'neu@test.example', '2026-09-08')",
                  (testfirma,))
    sync.rollback()


def test_sync_darf_opt_out_NICHT_loeschen(sync, testfirma):
    """Der Test, um den es hier eigentlich geht."""
    _verboten(sync, "DELETE FROM historie.opt_out WHERE firma_uid=%s",
              testfirma)


def test_sync_darf_opt_out_NICHT_aendern(sync, testfirma):
    _verboten(sync, "UPDATE historie.opt_out SET weg='geaendert' "
                    "WHERE firma_uid=%s", testfirma)


def test_sync_darf_alle_opt_outs_nicht_leerraeumen(sync):
    """Die Form, die ein Programmierfehler wirklich hat: kein WHERE."""
    _verboten(sync, "DELETE FROM historie.opt_out")


@pytest.mark.parametrize("tabelle", ["kontakt", "uebergabe", "opt_out"])
def test_sync_darf_keine_historie_loeschen(sync, tabelle):
    _verboten(sync, f"DELETE FROM historie.{tabelle}")


@pytest.mark.parametrize("tabelle,spalte", [
    ("kontakt", "weg"), ("uebergabe", "notiz"), ("opt_out", "weg")])
def test_sync_darf_keine_historie_aendern(sync, tabelle, spalte):
    _verboten(sync, f"UPDATE historie.{tabelle} SET {spalte}='x'")


def test_sync_darf_die_historie_nicht_abschneiden(sync):
    """TRUNCATE geht am DELETE-Recht vorbei - es haengt am Eigentuemer."""
    _verboten(sync, "TRUNCATE historie.opt_out")


# --------------------------------------------------------- coldmail_read

def test_read_darf_lesen(leser, testfirma):
    with leser.cursor() as c:
        c.execute("SELECT name FROM kern.firma WHERE firma_uid=%s",
                  (testfirma,))
        assert c.fetchone()[0] == "Test GmbH"
        c.execute("SELECT COUNT(*) FROM historie.opt_out WHERE firma_uid=%s",
                  (testfirma,))
        assert c.fetchone()[0] == 1


# Je Tabelle eine Spalte, in die 'x' auch wirklich passt. Sonst koennte
# Postgres schon am Wert scheitern ('x' ist kein Datum) und der Test
# saehe bestanden aus, ohne dass die Rechte je geprueft wurden.
ALLE_TABELLEN = [
    ("kern.firma", "kennung"),
    ("kern.entscheider", "name"),
    ("kern.firma_quelle", "provider"),
    ("historie.kontakt", "weg"),
    ("historie.uebergabe", "notiz"),
    ("historie.opt_out", "weg"),
]


@pytest.mark.parametrize("tabelle,spalte", ALLE_TABELLEN)
def test_read_darf_nichts_aendern(leser, tabelle, spalte):
    _verboten(leser, f"UPDATE {tabelle} SET {spalte}='x'")


@pytest.mark.parametrize("tabelle,spalte", ALLE_TABELLEN)
def test_read_darf_nichts_loeschen(leser, tabelle, spalte):
    _verboten(leser, f"DELETE FROM {tabelle}")


def test_beide_rollen_sehen_die_schema_version(sync, leser):
    """Wer sich verbindet, muss wissen koennen, welchen Stand die
    Datenbank hat - sonst raet der Sync der Phase 6."""
    from tests.postgres.test_schema import AKTUELLE_VERSION
    for db in (sync, leser):
        with db.cursor() as c:
            c.execute("SELECT MAX(version) FROM public.schema_version")
            assert c.fetchone()[0] == AKTUELLE_VERSION


def test_sync_darf_die_schema_version_nicht_umschreiben(sync):
    """Migrationen macht der Eigentuemer, nicht der Sync."""
    _verboten(sync, "UPDATE public.schema_version SET notiz='x'")
    _verboten(sync, "INSERT INTO public.schema_version (version, notiz) "
                    "VALUES (99, 'heimlich')")


def test_read_darf_die_schema_version_nicht_umschreiben(leser):
    _verboten(leser, "UPDATE public.schema_version SET notiz='x'")


def test_read_darf_nichts_einfuegen(leser):
    _verboten(leser, "INSERT INTO kern.firma (firma_uid, kennung) "
                     "VALUES ('f-leser', 'leser.example')")


def test_read_darf_keine_tabellen_anlegen(leser):
    _verboten(leser, "CREATE TABLE kern.heimlich (x int)")
