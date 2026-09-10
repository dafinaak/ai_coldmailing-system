"""stamm.db: a company keeps the same id forever.

Decision Dafina, 08.09.2026 (Phase 2):

    companies.id   changes on every rebuild of master.db - it is a row
                   number, not an identity.
    firma_uid      never changes. It is what an outside system (Oliver's
                   warehouse) is allowed to point at.

The rules this file guards:

    one kennung  = one firma_uid
    NO automatic merging - not by name, not by name + PLZ
    merging happens only by hand, through set_alias()
    stamm.db is persistent: no DROP, no DELETE

Why no automatic merging: two firms can share a name and a postal code
and still be two firms. A wrong merge silently sends one offer to the
wrong company and there is no way to notice it afterwards. A missed
merge only costs a duplicate row, which a human can see and fix.
"""
import sqlite3

import pytest

from pipeline import stamm_db


def test_new_kennung_gets_a_uid(tmp_path):
    uid = stamm_db.uid_fuer(tmp_path, "beispiel.de")
    assert uid


def test_same_kennung_gives_the_same_uid(tmp_path):
    erste = stamm_db.uid_fuer(tmp_path, "beispiel.de")
    zweite = stamm_db.uid_fuer(tmp_path, "beispiel.de")
    assert erste == zweite


def test_uid_survives_a_reopen(tmp_path):
    """The point of the whole file: the id outlives the process."""
    uid = stamm_db.uid_fuer(tmp_path, "beispiel.de")
    assert stamm_db.alle(tmp_path)["beispiel.de"] == uid


def test_different_kennungen_get_different_uids(tmp_path):
    a = stamm_db.uid_fuer(tmp_path, "a.de")
    b = stamm_db.uid_fuer(tmp_path, "b.de")
    assert a != b


def test_same_name_and_plz_are_not_merged(tmp_path):
    """No auto-merge. Two firms may share name and postal code."""
    a = stamm_db.uid_fuer(tmp_path, "mueller-it.de")
    b = stamm_db.uid_fuer(tmp_path, "mueller it gmbh")
    assert a != b


def test_kennung_is_matched_case_insensitively(tmp_path):
    """Safe to do: master_db already lowercases before we ever see it."""
    a = stamm_db.uid_fuer(tmp_path, "Beispiel.DE")
    b = stamm_db.uid_fuer(tmp_path, "beispiel.de")
    assert a == b


def test_a_stray_space_gets_its_own_uid(tmp_path):
    """Decision Dafina, 08.09.2026: stamm_db never cleans up more than
    master_db does.

    master_db._kennung() lowercases but does NOT strip, so 'eq24pay.de '
    and 'eq24pay.de' are two separate rows in companies. If stamm_db
    stripped, both rows would carry ONE firma_uid - two source rows
    under one id, and the Phase 6 upsert would silently keep whichever
    came last, with the winner depending on iteration order.

    So the space stays part of the identity. Putting the two together
    is Dafina's call, through set_alias().
    """
    assert stamm_db.uid_fuer(tmp_path, "eq24pay.de ") != \
        stamm_db.uid_fuer(tmp_path, "eq24pay.de")


def test_empty_kennung_is_refused(tmp_path):
    with pytest.raises(ValueError):
        stamm_db.uid_fuer(tmp_path, "")


def test_uid_is_derived_from_the_kennung(tmp_path):
    """Losing stamm.db must not renumber every company.

    The uid is a hash of the kennung, so a fresh database hands out the
    same ids again. Only the hand-made aliases would have to be redone.
    """
    uid = stamm_db.uid_fuer(tmp_path, "beispiel.de")
    (tmp_path / stamm_db.DB_NAME).unlink()
    assert stamm_db.uid_fuer(tmp_path, "beispiel.de") == uid


def test_schema_has_no_drop_and_no_delete():
    """Same guard as historie_db: this file must never be wiped."""
    schema = stamm_db._SCHEMA.upper()
    assert "DROP" not in schema
    assert "DELETE" not in schema


def test_alle_is_empty_without_a_database(tmp_path):
    assert stamm_db.alle(tmp_path) == {}


def test_uids_fuer_answers_for_a_whole_list(tmp_path):
    """master_db asks for 10.000 companies at once - not one at a time."""
    uids = stamm_db.uids_fuer(tmp_path, ["a.de", "b.de"])
    assert uids == {"a.de": stamm_db.uid_fuer(tmp_path, "a.de"),
                    "b.de": stamm_db.uid_fuer(tmp_path, "b.de")}


def test_uids_fuer_follows_aliases(tmp_path):
    stamm_db.set_alias(tmp_path, "a-alt.de", "a.de")
    uids = stamm_db.uids_fuer(tmp_path, ["a.de", "a-alt.de"])
    assert uids["a-alt.de"] == uids["a.de"]


def test_uids_fuer_ignores_empty_kennungen(tmp_path):
    assert list(stamm_db.uids_fuer(tmp_path, ["", None, "a.de"])) == ["a.de"]


def test_uids_fuer_answers_under_the_key_it_was_given(tmp_path):
    """Real data, 08.09.2026: master.db holds the kennung 'eq24pay.de '.

    Answering under a cleaned-up key means the caller looks up
    'eq24pay.de ' and gets a KeyError - one stray space in one run file
    stops the whole rebuild.
    """
    uids = stamm_db.uids_fuer(tmp_path, ["eq24pay.de ", "A.DE"])
    assert set(uids) == {"eq24pay.de ", "A.DE"}
    assert uids["A.DE"] == stamm_db.uid_fuer(tmp_path, "a.de")


def test_uids_fuer_stores_what_it_handed_out(tmp_path):
    """A uid that is not written down is not stable."""
    uids = stamm_db.uids_fuer(tmp_path, ["a.de", "b.de"])
    assert stamm_db.alle(tmp_path) == uids


# ------------------------------------------------------------- set_alias

def test_set_alias_gives_both_kennungen_one_uid(tmp_path):
    """The only merge there is - and a human has to ask for it."""
    stamm_db.uid_fuer(tmp_path, "8thsense.de")
    stamm_db.uid_fuer(tmp_path, "8thsense")
    ziel = stamm_db.uid_fuer(tmp_path, "8thsense.de")

    stamm_db.set_alias(tmp_path, "8thsense", "8thsense.de")

    assert stamm_db.uid_fuer(tmp_path, "8thsense") == ziel


def test_set_alias_works_for_a_kennung_seen_for_the_first_time(tmp_path):
    ziel = stamm_db.uid_fuer(tmp_path, "8thsense.de")
    stamm_db.set_alias(tmp_path, "8thsense", "8thsense.de")
    assert stamm_db.uid_fuer(tmp_path, "8thsense") == ziel


def test_set_alias_survives_a_reopen(tmp_path):
    ziel = stamm_db.uid_fuer(tmp_path, "8thsense.de")
    stamm_db.set_alias(tmp_path, "8thsense", "8thsense.de")
    assert stamm_db.alle(tmp_path)["8thsense"] == ziel


def test_set_alias_onto_itself_is_refused(tmp_path):
    stamm_db.uid_fuer(tmp_path, "a.de")
    with pytest.raises(ValueError):
        stamm_db.set_alias(tmp_path, "a.de", "a.de")


def test_set_alias_needs_both_sides(tmp_path):
    with pytest.raises(ValueError):
        stamm_db.set_alias(tmp_path, "", "a.de")
    with pytest.raises(ValueError):
        stamm_db.set_alias(tmp_path, "a.de", "")


def test_set_alias_is_recorded_with_a_reason(tmp_path):
    """Who merged what, and why - a merge must be explainable later."""
    stamm_db.uid_fuer(tmp_path, "8thsense.de")
    stamm_db.set_alias(tmp_path, "8thsense", "8thsense.de",
                       notiz="Dafina 08.09.2026: same firm, domain found later")

    eintrag = stamm_db.aliase(tmp_path)["8thsense"]
    assert eintrag["ziel"] == "8thsense.de"
    assert "Dafina" in eintrag["notiz"]


def test_alias_chain_is_followed_to_the_end(tmp_path):
    """a -> b -> c must land on c, not on b."""
    ziel = stamm_db.uid_fuer(tmp_path, "c.de")
    stamm_db.set_alias(tmp_path, "b.de", "c.de")
    stamm_db.set_alias(tmp_path, "a.de", "b.de")
    assert stamm_db.uid_fuer(tmp_path, "a.de") == ziel


def test_alias_cycle_is_refused_without_writing_anything(tmp_path):
    """a -> b and then b -> a would loop forever when resolved.

    Refusing is only half the job: if the row is written first and the
    error comes after, stamm.db is left with a cycle in it and every
    later read of those two companies raises. So the check has to happen
    BEFORE the write, and this test only passes if it does.
    """
    stamm_db.set_alias(tmp_path, "a.de", "b.de")
    with pytest.raises(ValueError):
        stamm_db.set_alias(tmp_path, "b.de", "a.de")

    assert "b.de" not in stamm_db.aliase(tmp_path)
    assert stamm_db.uid_fuer(tmp_path, "a.de")
    assert stamm_db.uid_fuer(tmp_path, "b.de")


def test_alias_loesen_puts_the_kennung_back_on_its_own_uid(tmp_path):
    """A wrong merge has to be undoable, otherwise nobody dares to merge."""
    eigen = stamm_db.uid_fuer(tmp_path, "a.de")
    stamm_db.set_alias(tmp_path, "a.de", "b.de")
    assert stamm_db.uid_fuer(tmp_path, "a.de") != eigen

    stamm_db.alias_loesen(tmp_path, "a.de")
    assert stamm_db.uid_fuer(tmp_path, "a.de") == eigen


def test_nothing_is_merged_without_set_alias(tmp_path):
    """The whole promise in one test: uid_fuer never merges on its own."""
    for kennung in ("mueller it gmbh", "mueller-it.de", "mueller it",
                    "müller it gmbh"):
        stamm_db.uid_fuer(tmp_path, kennung)
    assert len(set(stamm_db.alle(tmp_path).values())) == 4


def test_database_file_is_created_next_to_the_others(tmp_path):
    stamm_db.uid_fuer(tmp_path, "a.de")
    assert (tmp_path / "daten" / "stamm.db").exists()


def test_schema_lets_two_kennungen_share_one_uid(tmp_path):
    """The schema must not forbid what set_alias is for.

    A UNIQUE on firma_uid would look tidy and would make every merge
    impossible. Written as a test so nobody adds it later.
    """
    stamm_db.uid_fuer(tmp_path, "a.de")
    db = sqlite3.connect(tmp_path / stamm_db.DB_NAME)
    geteilt = db.execute(
        "SELECT firma_uid FROM firma_uid WHERE kennung='a.de'").fetchone()[0]
    db.execute("INSERT INTO firma_uid (kennung, firma_uid, angelegt_am) "
               "VALUES ('a-alt.de', ?, '2026-09-08')", (geteilt,))
    db.commit()
    db.close()
