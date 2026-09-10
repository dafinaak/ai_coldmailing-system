"""Das Schema des DataWarehouse (Phase 3, 08.09.2026).

Zwei Schemas in EINER Datenbank, nicht zwei Datenbanken:

    kern       firma, entscheider, firma_quelle
    historie   kontakt, uebergabe, opt_out

Getrennt sind sie, damit die Rollen sie verschieden behandeln koennen:
coldmail_sync darf kern umschreiben, historie aber nur lesen und
anhaengen. In einer Datenbank bleiben sie, weil ein JOIN ueber zwei
Datenbanken in Postgres nicht geht - und Oliver will Firma und Historie
zusammen sehen.

`kern.firma.firma_uid` kommt aus stamm.db. Postgres erzeugt sie NIE -
sonst gaebe es zwei Stellen, die IDs vergeben, und die erste
Wiederherstellung haette zwei verschiedene Wahrheiten.
"""
import pytest

psycopg = pytest.importorskip("psycopg")

pytestmark = pytest.mark.postgres


def _eine(db, sql, *args):
    with db.cursor() as c:
        c.execute(sql, args or None)
        zeile = c.fetchone()
    return zeile[0] if zeile else None


def test_die_zwei_schemas_gibt_es(admin):
    with admin.cursor() as c:
        c.execute("SELECT schema_name FROM information_schema.schemata "
                  "WHERE schema_name IN ('kern','historie')")
        gefunden = {z[0] for z in c.fetchall()}
    assert gefunden == {"kern", "historie"}


@pytest.mark.parametrize("schema,tabelle", [
    ("kern", "firma"), ("kern", "entscheider"), ("kern", "firma_quelle"),
    ("historie", "kontakt"), ("historie", "uebergabe"),
    ("historie", "opt_out"),
])
def test_die_tabellen_stehen_im_richtigen_schema(admin, schema, tabelle):
    assert _eine(admin,
                 "SELECT COUNT(*) FROM information_schema.tables "
                 "WHERE table_schema=%s AND table_name=%s",
                 schema, tabelle) == 1


def test_firma_uid_ist_der_primaerschluessel(admin):
    spalten = _eine(admin, """
        SELECT string_agg(a.attname, ',' ORDER BY a.attname)
        FROM pg_index i
        JOIN pg_attribute a ON a.attrelid = i.indrelid
                           AND a.attnum = ANY(i.indkey)
        WHERE i.indrelid = 'kern.firma'::regclass AND i.indisprimary""")
    assert spalten == "firma_uid"


def test_postgres_erzeugt_die_firma_uid_nie(admin):
    """Die ID kommt aus stamm.db. Gaebe es hier einen DEFAULT oder eine
    Identity-Spalte, koennte ein vergessenes Feld beim Sync stillschweigend
    eine erfundene ID anlegen - und die zeigt auf keine echte Firma."""
    with admin.cursor() as c:
        c.execute("""SELECT column_default, is_identity, is_generated
                     FROM information_schema.columns
                     WHERE table_schema='kern' AND table_name='firma'
                       AND column_name='firma_uid'""")
        default, identity, generated = c.fetchone()
    assert default is None
    assert identity == "NO"
    assert generated == "NEVER"


def test_firma_uid_ist_pflicht(admin):
    with pytest.raises(psycopg.errors.NotNullViolation):
        with admin.cursor() as c:
            c.execute("INSERT INTO kern.firma (firma_uid, kennung) "
                      "VALUES (NULL, 'x')")


# ------------------------------------------------- zusammengelegt_in

def test_zusammengelegt_in_zeigt_auf_die_ueberlebende_firma(admin, testfirma):
    """Wird eine Firma per set_alias zusammengelegt, verschwindet ihre uid
    aus der Quelle. Die Zeile hier bleibt trotzdem stehen und sagt, wohin
    sie gewandert ist - sonst haengt ihre Historie ins Leere."""
    from tests.postgres.conftest import TEST_UID_2
    with admin.cursor() as c:
        c.execute("UPDATE kern.firma SET zusammengelegt_in=%s "
                  "WHERE firma_uid=%s", (TEST_UID_2, testfirma))
        c.execute("SELECT zusammengelegt_in FROM kern.firma "
                  "WHERE firma_uid=%s", (testfirma,))
        assert c.fetchone()[0] == TEST_UID_2


def test_zusammengelegt_in_muss_eine_bekannte_firma_sein(admin, testfirma):
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        with admin.cursor() as c:
            c.execute("UPDATE kern.firma SET zusammengelegt_in='f-gibtsnicht' "
                      "WHERE firma_uid=%s", (testfirma,))


def test_zusammengelegt_in_darf_nicht_auf_sich_selbst_zeigen(admin, testfirma):
    """Eine Firma, die in sich selbst zusammengelegt ist, waere eine
    Schleife: wer ihr folgt, kommt nie an."""
    with pytest.raises(psycopg.errors.CheckViolation):
        with admin.cursor() as c:
            c.execute("UPDATE kern.firma SET zusammengelegt_in=firma_uid "
                      "WHERE firma_uid=%s", (testfirma,))


def test_eine_frische_firma_ist_nicht_zusammengelegt(admin, testfirma):
    assert _eine(admin, "SELECT zusammengelegt_in FROM kern.firma "
                        "WHERE firma_uid=%s", testfirma) is None


# ------------------------------------------------------ historie.kontakt

@pytest.mark.parametrize("nummer", [1, 2, 3, 4, 7, 42])
def test_kontakt_nimmt_jede_nummer(admin, testfirma, nummer):
    """In SQLite gilt weiter 1-3 (das bleibt unangetastet). Hier NICHT:
    gespeichert wird jeder Versuch, und die Ansicht der Phase 4 holt die
    ersten drei heraus. Eine Grenze in der Ablage wuerde den vierten
    Kontakt verlieren, statt ihn nur auszublenden."""
    with admin.cursor() as c:
        # Eigene Adresse je Nummer: die Testfirma bringt schon einen
        # Kontakt mit, und kontakt_einmalig laesst denselben Versuch
        # nicht zweimal zu (was sie auch soll).
        c.execute("INSERT INTO historie.kontakt "
                  "(firma_uid, person_email, nummer, datum) "
                  "VALUES (%s,%s,%s,%s) RETURNING nummer",
                  (testfirma, f"nr{nummer}@test.example", nummer,
                   "2026-09-08"))
        assert c.fetchone()[0] == nummer


def test_derselbe_kontakt_bleibt_ein_eintrag(admin, testfirma):
    """Ein Sync darf zweimal laufen, ohne die Historie aufzublaehen."""
    with admin.cursor() as c:
        for _ in range(2):
            c.execute(
                "INSERT INTO historie.kontakt "
                "(firma_uid, person_email, nummer, datum) "
                "VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                (testfirma, "wer@test.example", 9, "2026-09-08"))
        c.execute("SELECT COUNT(*) FROM historie.kontakt "
                  "WHERE firma_uid=%s AND nummer=9", (testfirma,))
        assert c.fetchone()[0] == 1


# -------------------------------------------------------- Fremdschluessel

def test_eine_firma_mit_historie_kann_nicht_geloescht_werden(admin, testfirma):
    """Der eigentliche Schutz: solange Historie an einer Firma haengt,
    laesst die Datenbank das Loeschen nicht zu. Ein Fehler im Sync kann
    einen Widerspruch damit nicht wegraeumen."""
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        with admin.cursor() as c:
            c.execute("DELETE FROM kern.firma WHERE firma_uid=%s",
                      (testfirma,))


def test_opt_out_braucht_firma_oder_email(admin):
    """Ein Widerspruch ohne beides waere ein Eintrag, den niemand
    zuordnen kann - und damit einer, der niemanden schuetzt."""
    with pytest.raises(psycopg.errors.CheckViolation):
        with admin.cursor() as c:
            c.execute("INSERT INTO historie.opt_out (datum) VALUES ('2026-09-08')")


# ------------------------------------------- Historie ohne bekannte Firma

@pytest.mark.parametrize("tabelle", ["kontakt", "uebergabe", "opt_out"])
def test_historie_firma_uid_darf_leer_sein(admin, tabelle):
    """historie.db ist ueber kennung geschluesselt, unabhaengig von
    master.db. Ein Opt-Out kann zu einer Firma gehoeren, die heute gar
    nicht mehr in master steht, und der Fall "nur E-Mail" hat kennung=''
    - da gibt es keine firma_uid, die man einsetzen koennte.

    Waere die Spalte NOT NULL, koennte der Sync der Phase 6 so eine Zeile
    gar nicht erst einfuegen. Das Opt-Out ginge dann nicht durch ein
    DELETE verloren, sondern durch ein INSERT, das scheitert - und weil
    der Sync mit ON CONFLICT DO NOTHING arbeitet, faellt das womoeglich
    niemandem auf. (Vorgabe Dafina, 08.09.2026)
    """
    assert _eine(admin, """
        SELECT is_nullable FROM information_schema.columns
        WHERE table_schema='historie' AND table_name=%s
          AND column_name='firma_uid'""", tabelle) == "YES"


def test_kontakt_ohne_firma_laesst_sich_speichern(admin):
    with admin.cursor() as c:
        c.execute("INSERT INTO historie.kontakt "
                  "(person_email, nummer, datum) VALUES (%s,%s,%s) "
                  "RETURNING id", ("wer@test.example", 1, "2026-09-08"))
        assert c.fetchone()[0]
    admin.rollback()


def test_uebergabe_ohne_firma_laesst_sich_speichern(admin):
    with admin.cursor() as c:
        c.execute("INSERT INTO historie.uebergabe (name, datum) "
                  "VALUES (%s,%s) RETURNING id",
                  ("Ein ColdCaller", "2026-09-08"))
        assert c.fetchone()[0]
    admin.rollback()


@pytest.mark.parametrize("tabelle,spalten,werte", [
    ("kontakt", "person_email, nummer, datum",
     ("doppelt@test.example", 1, "2026-09-08")),
    ("uebergabe", "name, datum", ("Doppelt Gemoppelt", "2026-09-08")),
    ("opt_out", "email, datum", ("doppelt@test.example", "2026-09-08")),
])
def test_ohne_firma_bleibt_derselbe_eintrag_einer(admin, tabelle, spalten,
                                                  werte):
    """NULL <> NULL in einem normalen UNIQUE: ohne NULLS NOT DISTINCT
    waere derselbe Eintrag ohne Firma bei jedem Sync-Lauf eine neue
    Zeile, und die Historie wuechse ins Unendliche."""
    platz = ",".join(["%s"] * len(werte))
    with admin.cursor() as c:
        for _ in range(2):
            c.execute(f"INSERT INTO historie.{tabelle} ({spalten}) "
                      f"VALUES ({platz}) ON CONFLICT DO NOTHING", werte)
        c.execute(f"SELECT COUNT(*) FROM historie.{tabelle} "
                  f"WHERE firma_uid IS NULL")
        assert c.fetchone()[0] == 1
    admin.rollback()


# --------------------------------------------------------- schema_version

# Wird mit JEDER Migration hochgezaehlt. Absichtlich fest verdrahtet:
# wer ein neues Skript in deploy/postgres/ ablegt, muss hier vorbei -
# sonst faellt der Test, und genau das ist der Zweck. Eine Zahl, die
# sich selbst berechnet, wuerde jede vergessene Migration mitdecken.
AKTUELLE_VERSION = 2


def test_es_gibt_eine_schema_version(admin):
    """docker-entrypoint-initdb.d laeuft NUR beim allerersten Start mit
    leerem Volume. Die erste Schema-Aenderung auf dem Server wird also
    ein ALTER von Hand sein. Ohne diese Tabelle bliebe davon keine Spur,
    und niemand koennte sagen, welchen Stand eine Datenbank hat."""
    assert _eine(admin, "SELECT MAX(version) FROM public.schema_version") \
        == AKTUELLE_VERSION


def test_schema_version_haelt_die_geschichte_fest(admin):
    """Jede Migration haengt eine Zeile an - man sieht also nicht nur den
    Stand, sondern auch den Weg dahin."""
    with admin.cursor() as c:
        c.execute("SELECT version, notiz FROM public.schema_version "
                  "ORDER BY version")
        zeilen = c.fetchall()
    assert [z[0] for z in zeilen] == list(range(1, AKTUELLE_VERSION + 1))
    assert all(z[1] for z in zeilen), "jede Version braucht eine Notiz"


def test_dieselbe_version_kann_nicht_zweimal_eingetragen_werden(admin):
    with pytest.raises(psycopg.errors.UniqueViolation):
        with admin.cursor() as c:
            c.execute("INSERT INTO public.schema_version (version, notiz) "
                      "VALUES (1, 'nochmal')")


def test_opt_out_darf_nur_eine_email_haben(admin):
    """Ohne Firma, nur mit Adresse - das kommt vor und muss gehen."""
    with admin.cursor() as c:
        c.execute("INSERT INTO historie.opt_out (email, datum) "
                  "VALUES (%s,%s) RETURNING id",
                  ("frei@test.example", "2026-09-08"))
        assert c.fetchone()[0]
    admin.rollback()
