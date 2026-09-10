"""Die Ansicht, die Oliver liest (Phase 4, 08.09.2026).

    SELECT * FROM datawarehouse;

46 Spalten, in seiner Reihenfolge, ohne Zutaten.

## Woher die Namen kommen - und warum sie hier trotzdem ausgeschrieben stehen

Kein einziger Spaltenname ist hier erfunden. Alle stammen aus der
vorhandenen Vorgabe: den Kopfzeilen der Excel-Liste in
pipeline/master_db.py (KOPF_FIRMEN + A-E + KOPF_HISTORIE). Das ist
dieselbe Liste, die Oliver heute als Datei bekommt.

Trotzdem steht sie hier ausgeschrieben statt importiert. Waere sie
importiert, verschoebe eine Aenderung an der Excel-Kopfzeile still auch
die Erwartung dieses Tests - der Test koennte gar nicht mehr merken,
dass sich etwas bewegt hat.

Beides zusammen macht test_die_spalten_kommen_aus_der_vorhandenen_vorgabe:
er vergleicht die ausgeschriebene Liste mit der aus master_db.py
berechneten. Weichen sie ab, faellt er - und dann ist zu entscheiden, ob
Excel und Postgres wirklich auseinanderlaufen sollen. Erfinden kann man
so keinen Namen, und stilles Auseinanderlaufen gibt es auch nicht.

Die 46 ist BESTAETIGT: Olivers eigene Feldliste hat genau 46 Eintraege,
und jeder davon hat hier seine Spalte (16 Firmenfelder + 25 fuer A-E +
Rausgegeben + drei Kontakte + Opt-Out).

Bei den NAMEN wurden Olivers Bezeichnungen ueberall dort uebernommen, wo
der Unterschied ein echter ist (Dafina, 08./09.09.2026): Datenquelle ->
Daten-Ursprung, Sektor -> Branche, Auswahl-Stichworte ->
Selektions-Keywords, Webseite -> www, A-E) Bereich -> A-E)
Entscheider-Bereich (fuer welches Produkt), A-E) Rolle -> A-E)
Entscheider-Position. Reine Schreibweisen bleiben, wie sie seit August in
der Excel-Datei stehen.

Dass im A-E-Block nur zwei der fuenf Spalten das Praefix "Entscheider-"
tragen, ist eine bewusste Entscheidung - kein Versehen. Nicht der
Symmetrie wegen angleichen.

Offen ist nur noch, ob Oliver mit den beibehaltenen Namen einverstanden
ist; kommt eine Korrektur, wird sie hier eingetragen - nie
stillschweigend.
"""
import pytest

psycopg = pytest.importorskip("psycopg")

pytestmark = pytest.mark.postgres


SPALTEN = [
    "ID",
    "Daten-Ursprung (woher/von wem, wann)",
    "Branche",
    "Firma",
    "Kurzbeschreibung",
    "Selektions-Keywords",
    "Mitarbeiterzahl",
    "CEO/Inhaber",
    "Straße",
    "Ort",
    "PLZ",
    "Bundesland",
    "Land",
    "Tel",
    "E-Mail (allgemein)",
    "www",
    "A) Entscheider-Bereich (für welches Produkt)", "A) Name",
    "A) Entscheider-Position", "A) Tel", "A) E-Mail",
    "B) Entscheider-Bereich (für welches Produkt)", "B) Name",
    "B) Entscheider-Position", "B) Tel", "B) E-Mail",
    "C) Entscheider-Bereich (für welches Produkt)", "C) Name",
    "C) Entscheider-Position", "C) Tel", "C) E-Mail",
    "D) Entscheider-Bereich (für welches Produkt)", "D) Name",
    "D) Entscheider-Position", "D) Tel", "D) E-Mail",
    "E) Entscheider-Bereich (für welches Produkt)", "E) Name",
    "E) Entscheider-Position", "E) Tel", "E) E-Mail",
    "Rausgegeben an (Name, Art, Datum)",
    "1. Kontakt",
    "2. Kontakt",
    "3. Kontakt",
    "Opt-Out (Datum, Weg)",
]

VORSILBE = "f-dwtest"
UID = f"{VORSILBE}-a"
UID_ZUSAMMEN = f"{VORSILBE}-b"
UID_ZIEL = f"{VORSILBE}-c"


def _aufraeumen(db):
    with db.cursor() as c:
        c.execute("DELETE FROM historie.kontakt WHERE firma_uid LIKE %s",
                  (VORSILBE + "%",))
        c.execute("DELETE FROM historie.uebergabe WHERE firma_uid LIKE %s",
                  (VORSILBE + "%",))
        # Jede Test-Adresse traegt 'dwtest' im Domainnamen, damit ein
        # Muster wirklich alle erwischt. Vorher hing hier
        # '%@dwtest.example', und die Zeile aus dem Fremd-Domain-Test
        # ('...@ganz-woanders.example') blieb liegen - sie hat danach
        # test_ohne_firma_bleibt_derselbe_eintrag_einer umgeworfen.
        # Liegengebliebene Testdaten sind wie ein haengender Test: der
        # Fehler zeigt sich woanders als da, wo er herkommt.
        c.execute("DELETE FROM historie.opt_out "
                  "WHERE firma_uid LIKE %s OR email LIKE %s",
                  (VORSILBE + "%", "%dwtest%"))
        c.execute("DELETE FROM kern.entscheider WHERE firma_uid LIKE %s",
                  (VORSILBE + "%",))
        c.execute("DELETE FROM kern.firma_quelle WHERE firma_uid LIKE %s",
                  (VORSILBE + "%",))
        c.execute("UPDATE kern.firma SET zusammengelegt_in=NULL "
                  "WHERE firma_uid LIKE %s", (VORSILBE + "%",))
        c.execute("DELETE FROM kern.firma WHERE firma_uid LIKE %s",
                  (VORSILBE + "%",))
    db.commit()


class Welt:
    """Kleine Helfer, damit die Tests von Daten handeln, nicht von SQL."""

    def __init__(self, db):
        self.db = db

    def firma(self, uid=UID, kennung="dwtest.example", **felder):
        spalten = ["firma_uid", "kennung"] + list(felder)
        werte = [uid, kennung] + list(felder.values())
        platz = ",".join(["%s"] * len(werte))
        namen = ",".join(f'"{s}"' for s in spalten)
        with self.db.cursor() as c:
            c.execute(f"INSERT INTO kern.firma ({namen}) VALUES ({platz})",
                      werte)
        self.db.commit()
        return uid

    def entscheider(self, anzahl, uid=UID):
        with self.db.cursor() as c:
            for i in range(1, anzahl + 1):
                c.execute(
                    "INSERT INTO kern.entscheider "
                    "(firma_uid, name, rolle, bereich, email, telefon) "
                    "VALUES (%s,%s,%s,%s,%s,%s)",
                    (uid, f"Person {i}", f"Rolle {i}", f"Bereich {i}",
                     f"person{i}@dwtest.example", f"0{i}00-000"))
        self.db.commit()

    def zeile(self, uid=UID):
        with self.db.cursor() as c:
            c.execute('SELECT * FROM datawarehouse WHERE "ID"=%s', (uid,))
            zeile = c.fetchone()
            if zeile is None:
                return None
            namen = [b.name for b in c.description]
        return dict(zip(namen, zeile))

    def alle_ids(self):
        with self.db.cursor() as c:
            c.execute('SELECT "ID" FROM datawarehouse WHERE "ID" LIKE %s',
                      (VORSILBE + "%",))
            return [z[0] for z in c.fetchall()]


@pytest.fixture
def welt(admin):
    _aufraeumen(admin)
    yield Welt(admin)
    admin.rollback()
    _aufraeumen(admin)


# ------------------------------------------------------------- Die Spalten

def test_die_spalten_kommen_aus_der_vorhandenen_vorgabe():
    """Kein Name ist hier erfunden.

    Die Vorgabe ist die Excel-Kopfzeile aus pipeline/master_db.py - die
    Liste, die Oliver heute schon als Datei bekommt. Ansicht und Datei
    muessen dieselben Spalten haben, sonst sagen die zwei Uebergabewege
    Verschiedenes ueber dieselbe Firma.

    Faellt dieser Test, hat jemand die Excel-Kopfzeile geaendert. Dann
    ist zu entscheiden, ob die Ansicht mitgeht - nicht, ob man den Test
    passend macht. Er laeuft ohne Postgres, weil er nur zwei Listen
    vergleicht.
    """
    from pipeline.master_db import KOPF_FIRMEN, KOPF_HISTORIE, _AE

    ae = []
    for buchstabe in _AE:
        ae += [f"{buchstabe}) Entscheider-Bereich (für welches Produkt)",
               f"{buchstabe}) Name",
               f"{buchstabe}) Entscheider-Position", f"{buchstabe}) Tel",
               f"{buchstabe}) E-Mail"]
    vorgabe = list(KOPF_FIRMEN) + ae + list(KOPF_HISTORIE)

    assert SPALTEN == vorgabe


def test_die_ansicht_hat_genau_46_spalten(admin):
    with admin.cursor() as c:
        c.execute("SELECT COUNT(*) FROM information_schema.columns "
                  "WHERE table_name='datawarehouse'")
        assert c.fetchone()[0] == 46


def test_die_spalten_stehen_in_olivers_reihenfolge(admin):
    with admin.cursor() as c:
        c.execute("SELECT column_name FROM information_schema.columns "
                  "WHERE table_name='datawarehouse' ORDER BY ordinal_position")
        assert [z[0] for z in c.fetchall()] == SPALTEN


def test_es_gibt_keine_zusatzspalten(admin):
    """Kein synced_at, kein completeness, kein "Weitere Entscheider" -
    Oliver bekommt seine Tabelle, nicht unsere."""
    with admin.cursor() as c:
        c.execute("SELECT column_name FROM information_schema.columns "
                  "WHERE table_name='datawarehouse'")
        gefunden = {z[0] for z in c.fetchall()}
    assert gefunden - set(SPALTEN) == set()


def test_oliver_kann_sie_ohne_schema_ansprechen(admin):
    """Er tippt SELECT * FROM datawarehouse - ohne Schema davor."""
    with admin.cursor() as c:
        c.execute("SELECT COUNT(*) FROM datawarehouse")
        assert c.fetchone()[0] >= 0


# ------------------------------------------------------------- A bis E

def test_fuenf_entscheider_fuellen_a_bis_e(welt):
    welt.firma()
    welt.entscheider(5)
    zeile = welt.zeile()
    for nummer, buchstabe in enumerate("ABCDE", start=1):
        assert zeile[f"{buchstabe}) Name"] == f"Person {nummer}"
        assert zeile[f"{buchstabe}) Entscheider-Position"] == f"Rolle {nummer}"
        assert zeile[f"{buchstabe}) Entscheider-Bereich (für welches Produkt)"] \
            == f"Bereich {nummer}"
        assert zeile[f"{buchstabe}) E-Mail"] == \
            f"person{nummer}@dwtest.example"


def test_ein_entscheider_fuellt_nur_a(welt):
    welt.firma()
    welt.entscheider(1)
    zeile = welt.zeile()
    assert zeile["A) Name"] == "Person 1"
    for buchstabe in "BCDE":
        for feld in ("Entscheider-Bereich (für welches Produkt)", "Name",
                     "Entscheider-Position", "Tel", "E-Mail"):
            assert zeile[f"{buchstabe}) {feld}"] is None


def test_ohne_entscheider_bleibt_die_firma_trotzdem_stehen(welt):
    """Der wichtigste der drei Faelle: eine Firma ohne gefundene Personen
    darf nicht aus Olivers Tabelle verschwinden."""
    welt.firma(name="Ohne Leute GmbH")
    zeile = welt.zeile()
    assert zeile is not None
    assert zeile["Firma"] == "Ohne Leute GmbH"
    for buchstabe in "ABCDE":
        assert zeile[f"{buchstabe}) Name"] is None


def test_der_sechste_steht_weiter_in_der_tabelle(welt):
    """A-E zeigt fuenf. Der sechste wird nicht geloescht - er wird nur
    nicht gezeigt. Die Ansicht ist eine Sicht, kein Filter auf den Daten."""
    welt.firma()
    welt.entscheider(6)

    zeile = welt.zeile()
    gezeigt = {zeile[f"{b}) Name"] for b in "ABCDE"}
    assert "Person 6" not in gezeigt

    with welt.db.cursor() as c:
        c.execute("SELECT COUNT(*) FROM kern.entscheider WHERE firma_uid=%s",
                  (UID,))
        assert c.fetchone()[0] == 6


# --------------------------------------------------------- Nichts erfinden

def test_fehlende_felder_bleiben_null(welt):
    """Nichts wird gefuellt, nur damit 46 Spalten voll aussehen."""
    welt.firma(land=None)
    zeile = welt.zeile()
    for spalte in ("Mitarbeiterzahl", "Branche", "Land", "Tel",
                   "Kurzbeschreibung", "CEO/Inhaber", "Bundesland",
                   "E-Mail (allgemein)", "www", "Straße"):
        assert zeile[spalte] is None, f"{spalte} wurde erfunden"


def test_entscheider_ohne_telefon_zeigt_null(welt):
    welt.firma()
    with welt.db.cursor() as c:
        c.execute("INSERT INTO kern.entscheider (firma_uid, name) "
                  "VALUES (%s, 'Ohne Telefon')", (UID,))
    welt.db.commit()
    zeile = welt.zeile()
    assert zeile["A) Name"] == "Ohne Telefon"
    assert zeile["A) Tel"] is None
    assert zeile["A) Entscheider-Position"] is None


def test_ohne_historie_bleiben_die_fuenf_spalten_leer(welt):
    welt.firma()
    zeile = welt.zeile()
    for spalte in ("Rausgegeben an (Name, Art, Datum)", "1. Kontakt",
                   "2. Kontakt", "3. Kontakt", "Opt-Out (Datum, Weg)"):
        assert zeile[spalte] is None


# ------------------------------------------------------ Zusammengelegte

def test_zusammengelegte_firmen_kommen_nicht_vor(welt):
    """Sonst saehe Oliver die zusammengelegte Firma UND die ueberlebende -
    genau die Dopplung, gegen die firma_uid gebaut wurde."""
    welt.firma(uid=UID_ZIEL, kennung="ziel.example", name="Ueberlebende GmbH")
    welt.firma(uid=UID_ZUSAMMEN, kennung="alt.example", name="Alte GmbH")
    with welt.db.cursor() as c:
        c.execute("UPDATE kern.firma SET zusammengelegt_in=%s "
                  "WHERE firma_uid=%s", (UID_ZIEL, UID_ZUSAMMEN))
    welt.db.commit()

    ids = welt.alle_ids()
    assert UID_ZIEL in ids
    assert UID_ZUSAMMEN not in ids


# --------------------------------------------------------------- Opt-Out

def test_opt_out_ueber_firma_uid_erscheint(welt):
    welt.firma()
    with welt.db.cursor() as c:
        c.execute("INSERT INTO historie.opt_out (firma_uid, datum, weg) "
                  "VALUES (%s, '2026-09-08', 'E-Mail')", (UID,))
    welt.db.commit()
    assert "2026-09-08" in welt.zeile()["Opt-Out (Datum, Weg)"]


def test_opt_out_nur_mit_email_findet_die_firma_ueber_die_domain(welt):
    """Diese Zeilen haben firma_uid = NULL, mit Absicht (Phase 3): sie
    lassen sich an keine Firma haengen. Ohne den Umweg ueber die Domain
    saehe Oliver so eine Firma als anschreibbar, obwohl dort jemand nein
    gesagt hat. Rein lesend - die Historie wird nicht angefasst."""
    welt.firma(kennung="dwtest.example")
    with welt.db.cursor() as c:
        c.execute("INSERT INTO historie.opt_out (email, datum, weg) "
                  "VALUES (%s, '2026-09-08', 'Antwort')",
                  ("wer@dwtest.example",))
    welt.db.commit()

    text = welt.zeile()["Opt-Out (Datum, Weg)"]
    assert text and "2026-09-08" in text


def test_fremdes_opt_out_faerbt_nicht_auf_andere_firmen_ab(welt):
    """Die Domain muss passen - sonst blockiert ein einziger Widerspruch
    Firmen, die damit nichts zu tun haben."""
    welt.firma(kennung="dwtest.example")
    with welt.db.cursor() as c:
        c.execute("INSERT INTO historie.opt_out (email, datum, weg) "
                  "VALUES (%s, '2026-09-08', 'Antwort')",
                  ("wer@fremd-dwtest.example",))
    welt.db.commit()
    assert welt.zeile()["Opt-Out (Datum, Weg)"] is None


def test_opt_out_der_historie_wird_nicht_veraendert(welt):
    """Der Domain-Abgleich ist reine Anzeige. Die Zeile bleibt, wie sie
    ist - firma_uid bleibt NULL."""
    welt.firma(kennung="dwtest.example")
    with welt.db.cursor() as c:
        c.execute("INSERT INTO historie.opt_out (email, datum) "
                  "VALUES (%s, '2026-09-08')", ("wer@dwtest.example",))
    welt.db.commit()
    welt.zeile()
    with welt.db.cursor() as c:
        c.execute("SELECT firma_uid FROM historie.opt_out WHERE email=%s",
                  ("wer@dwtest.example",))
        assert c.fetchone()[0] is None


# --------------------------------------------------------- Kontaktspalten

def test_die_drei_kontaktspalten_stehen_richtig(welt):
    welt.firma()
    with welt.db.cursor() as c:
        for nummer in (1, 2, 3):
            c.execute("INSERT INTO historie.kontakt "
                      "(firma_uid, nummer, datum, weg, resultat) "
                      "VALUES (%s,%s,%s,%s,%s)",
                      (UID, nummer, "2026-09-08", f"Weg {nummer}",
                       f"Ergebnis {nummer}"))
    welt.db.commit()
    zeile = welt.zeile()
    for nummer in (1, 2, 3):
        assert f"Weg {nummer}" in zeile[f"{nummer}. Kontakt"]


def test_der_vierte_kontakt_bleibt_gespeichert_aber_ungezeigt(welt):
    """In der Ablage gilt keine Grenze (Phase 3). Die Ansicht holt drei
    heraus - verloren geht dabei nichts."""
    welt.firma()
    with welt.db.cursor() as c:
        for nummer in (1, 2, 3, 4):
            c.execute("INSERT INTO historie.kontakt "
                      "(firma_uid, nummer, datum, weg) VALUES (%s,%s,%s,%s)",
                      (UID, nummer, "2026-09-08", f"Weg {nummer}"))
    welt.db.commit()

    zeile = welt.zeile()
    zusammen = " ".join(str(zeile[f"{n}. Kontakt"] or "") for n in (1, 2, 3))
    assert "Weg 4" not in zusammen

    with welt.db.cursor() as c:
        c.execute("SELECT COUNT(*) FROM historie.kontakt WHERE firma_uid=%s",
                  (UID,))
        assert c.fetchone()[0] == 4


def test_rausgegeben_an_zeigt_die_uebergabe(welt):
    welt.firma()
    with welt.db.cursor() as c:
        c.execute("INSERT INTO historie.uebergabe "
                  "(firma_uid, name, art_der_person, datum) "
                  "VALUES (%s,%s,%s,%s)",
                  (UID, "Ein ColdCaller", "Handelsvertreter", "2026-09-08"))
    welt.db.commit()
    text = welt.zeile()["Rausgegeben an (Name, Art, Datum)"]
    assert "Ein ColdCaller" in text and "Handelsvertreter" in text


# ----------------------------------------------------------------- Rechte

def test_coldmail_read_darf_die_ansicht_lesen(leser):
    with leser.cursor() as c:
        c.execute("SELECT COUNT(*) FROM datawarehouse")
        assert c.fetchone()[0] >= 0


def test_coldmail_read_darf_die_ansicht_nicht_beschreiben(leser):
    """Zwei Gruende, und beide werden geprueft.

    Erstens ist die Ansicht ueberhaupt nicht beschreibbar - sie enthaelt
    WITH, also weist Postgres jedes UPDATE ab, egal wer fragt. Zweitens
    hat coldmail_read auch gar kein UPDATE-Recht darauf.

    Postgres meldet den ersten Grund zuerst, deshalb wird das Recht
    getrennt nachgesehen. Sonst haenge der Schutz allein an der Form der
    Abfrage, und eine spaeter vereinfachte Ansicht (ohne WITH) waere
    plotzlich beschreibbar, ohne dass ein Test etwas sagt.
    """
    with pytest.raises(psycopg.Error):
        with leser.cursor() as c:
            c.execute('UPDATE datawarehouse SET "Firma"=%s', ("x",))
    leser.rollback()

    with leser.cursor() as c:
        c.execute("""
            SELECT COALESCE(string_agg(privilege_type, ','), '')
            FROM information_schema.table_privileges
            WHERE table_name='datawarehouse' AND grantee='coldmail_read'""")
        assert c.fetchone()[0] == "SELECT"


def test_coldmail_sync_hat_auf_der_ansicht_nichts_zu_suchen(admin):
    """Der Sync schreibt in die Tabellen darunter und liest hier nichts -
    also bekommt er auch kein Recht (Vorgabe Dafina, 08.09.2026)."""
    with admin.cursor() as c:
        c.execute("""SELECT COUNT(*) FROM information_schema.table_privileges
                     WHERE table_name='datawarehouse'
                       AND grantee='coldmail_sync'""")
        assert c.fetchone()[0] == 0
