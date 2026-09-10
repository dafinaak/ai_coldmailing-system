"""master.db carries the stable id, not just the row number.

`companies.id` is handed out by SQLite in insert order. Add one company
at the top of a run file and every id below it shifts. Anything outside
this project that stored such an id is then pointing at the wrong firm -
silently, because the id still exists.

`companies.firma_uid` comes from stamm.db and does not move. That is the
id Oliver's warehouse may keep.

The other half of the promise is what does NOT happen here: master.db
still writes one row per kennung. Two firms with the same name and the
same PLZ stay two rows. They only ever share a uid after a human said so
with stamm_db.set_alias().
"""
import json
import sqlite3

import openpyxl

from pipeline import stamm_db
from pipeline.master_db import DB_NAME, bauen, export_excel


def _lauf(tmp_path, firmen):
    """Writes a collection file, the way master_db expects to find it."""
    ziel = tmp_path / "laeufe" / "leadquellen" / "lauf1"
    ziel.mkdir(parents=True, exist_ok=True)
    (ziel / "firmen.json").write_text(json.dumps(firmen, ensure_ascii=False),
                                      encoding="utf-8")


def _firmen(tmp_path):
    """{kennung: (id, firma_uid)} from the built database."""
    db = sqlite3.connect(tmp_path / DB_NAME)
    db.row_factory = sqlite3.Row
    zeilen = {z["kennung"]: (z["id"], z["firma_uid"])
              for z in db.execute("SELECT id, kennung, firma_uid FROM companies")}
    db.close()
    return zeilen


def _blatt(tmp_path):
    pfad = export_excel(str(tmp_path), tmp_path / "export.xlsx")
    blatt = openpyxl.load_workbook(pfad).active
    kopf = [c.value for c in blatt[1]]
    zeilen = [dict(zip(kopf, [c.value for c in r]))
              for r in blatt.iter_rows(min_row=2)]
    return kopf, zeilen


def test_id_is_the_first_column_of_the_export(tmp_path):
    """Oliver's list starts with "ID" (Dafina, 08.09.2026).

    Excel is what actually gets handed over today. If the uid lives only
    in the database, the two deliveries say different things about the
    same company - which is the exact drift firma_uid exists to end.
    """
    _lauf(tmp_path, [{"name": "A GmbH", "domain": "a.de"}])
    kopf, zeilen = _blatt(tmp_path)

    assert kopf[0] == "ID"
    assert zeilen[0]["ID"] == stamm_db.alle(tmp_path)["a.de"]


def test_export_id_does_not_move_between_runs(tmp_path):
    _lauf(tmp_path, [{"name": "B GmbH", "domain": "b.de"}])
    _, vorher = _blatt(tmp_path)

    _lauf(tmp_path, [{"name": "A GmbH", "domain": "a.de"},
                     {"name": "B GmbH", "domain": "b.de"}])
    _, nachher = _blatt(tmp_path)

    nach_firma = {z["Firma"]: z["ID"] for z in nachher}
    assert nach_firma["B GmbH"] == vorher[0]["ID"]


def test_merged_companies_show_the_same_id_in_the_export(tmp_path):
    _lauf(tmp_path, [{"name": "8thsense GmbH", "domain": "8thsense.de"},
                     {"name": "8thsense GmbH"}])
    bauen(str(tmp_path))
    stamm_db.set_alias(tmp_path, "8thsense gmbh", "8thsense.de")

    _, zeilen = _blatt(tmp_path)
    assert len({z["ID"] for z in zeilen}) == 1


def test_companies_has_a_filled_firma_uid(tmp_path):
    _lauf(tmp_path, [{"name": "A GmbH", "domain": "a.de"}])
    bauen(str(tmp_path))
    assert _firmen(tmp_path)["a.de"][1]


def test_firma_uid_matches_stamm_db(tmp_path):
    _lauf(tmp_path, [{"name": "A GmbH", "domain": "a.de"}])
    bauen(str(tmp_path))
    assert _firmen(tmp_path)["a.de"][1] == stamm_db.alle(tmp_path)["a.de"]


def test_firma_uid_stays_when_companies_id_moves(tmp_path):
    """The reason the whole phase exists.

    A company is added in front of the others, so SQLite hands out
    different row numbers on the rebuild. The row number must change and
    the firma_uid must not - otherwise the uid is just a second row
    number and buys nothing.
    """
    _lauf(tmp_path, [{"name": "B GmbH", "domain": "b.de"},
                     {"name": "C GmbH", "domain": "c.de"}])
    bauen(str(tmp_path))
    vorher = _firmen(tmp_path)

    _lauf(tmp_path, [{"name": "A GmbH", "domain": "a.de"},
                     {"name": "B GmbH", "domain": "b.de"},
                     {"name": "C GmbH", "domain": "c.de"}])
    bauen(str(tmp_path))
    nachher = _firmen(tmp_path)

    for kennung in ("b.de", "c.de"):
        assert nachher[kennung][0] != vorher[kennung][0], \
            f"{kennung}: companies.id sollte sich verschoben haben"
        assert nachher[kennung][1] == vorher[kennung][1], \
            f"{kennung}: firma_uid darf sich NIE verschieben"


def test_a_stray_space_in_a_domain_does_not_stop_the_rebuild(tmp_path):
    """Found on the real data, 08.09.2026: one run file holds the domain
    'eq24pay.de ' with a trailing space. master_db lowercases the
    kennung but does not strip it, so the whole rebuild used to stop
    there with a KeyError."""
    _lauf(tmp_path, [{"name": "EQ24 GmbH", "domain": "eq24pay.de "}])
    bauen(str(tmp_path))
    assert _firmen(tmp_path)["eq24pay.de "][1]


def test_no_two_rows_share_an_id_without_set_alias(tmp_path):
    """The invariant the Phase 6 upsert stands on.

    Every row in companies has its own firma_uid unless a human merged
    them. Two rows under one id would make the upsert keep whichever
    came last, and which one wins would depend on iteration order -
    Oliver would see a row change between syncs for no reason.

    The stray-space pair is in here on purpose: it is the case that used
    to collapse into one id (fixed 08.09.2026).
    """
    _lauf(tmp_path, [
        {"name": "EQ24 A", "domain": "eq24pay.de "},
        {"name": "EQ24 B", "domain": "eq24pay.de"},
        {"name": "Müller IT GmbH", "domain": "mueller-it.de", "plz": "34117"},
        {"name": "Müller IT GmbH", "plz": "34117"},
        {"name": "C GmbH", "domain": "C.DE"},
    ])
    bauen(str(tmp_path))
    zeilen = _firmen(tmp_path)

    uids = [uid for _, uid in zeilen.values()]
    assert len(set(uids)) == len(zeilen), \
        "zwei Zeilen teilen sich eine firma_uid, ohne dass jemand sie " \
        "zusammengelegt hat"


def test_rebuild_does_not_wipe_stamm_db(tmp_path):
    """master.db is dropped and rebuilt - stamm.db must survive that."""
    _lauf(tmp_path, [{"name": "A GmbH", "domain": "a.de"}])
    bauen(str(tmp_path))
    stamm_db.set_alias(tmp_path, "a gmbh", "a.de",
                       notiz="Dafina: same firm, domain found later")

    _lauf(tmp_path, [{"name": "A GmbH", "domain": "a.de"}])
    bauen(str(tmp_path))

    assert stamm_db.aliase(tmp_path)["a gmbh"]["ziel"] == "a.de"


def test_same_name_and_plz_stay_two_rows_with_two_uids(tmp_path):
    """No auto-merge. This is the rule Dafina decided on 08.09.2026."""
    _lauf(tmp_path, [
        {"name": "Müller IT GmbH", "domain": "mueller-it.de", "plz": "34117"},
        {"name": "Müller IT GmbH", "plz": "34117"},
    ])
    bauen(str(tmp_path))
    zeilen = _firmen(tmp_path)

    assert len(zeilen) == 2
    assert zeilen["mueller-it.de"][1] != zeilen["müller it gmbh"][1]


def test_set_alias_makes_the_two_rows_share_one_uid(tmp_path):
    """After the hand-made merge both rows carry the same firma_uid.

    They stay two rows on purpose - master.db mirrors the files, and the
    files really do hold the firm twice. The uid is what tells an outside
    reader they are one company.
    """
    _lauf(tmp_path, [
        {"name": "8thsense GmbH", "domain": "8thsense.de"},
        {"name": "8thsense GmbH"},
    ])
    bauen(str(tmp_path))
    stamm_db.set_alias(tmp_path, "8thsense gmbh", "8thsense.de",
                       notiz="Dafina 08.09.2026: split identity")
    bauen(str(tmp_path))

    zeilen = _firmen(tmp_path)
    assert len(zeilen) == 2
    assert zeilen["8thsense gmbh"][1] == zeilen["8thsense.de"][1]


def test_alias_is_undone_and_the_rows_split_again(tmp_path):
    _lauf(tmp_path, [{"name": "8thsense GmbH", "domain": "8thsense.de"},
                     {"name": "8thsense GmbH"}])
    bauen(str(tmp_path))
    stamm_db.set_alias(tmp_path, "8thsense gmbh", "8thsense.de")
    bauen(str(tmp_path))

    stamm_db.alias_loesen(tmp_path, "8thsense gmbh")
    bauen(str(tmp_path))

    zeilen = _firmen(tmp_path)
    assert zeilen["8thsense gmbh"][1] != zeilen["8thsense.de"][1]
