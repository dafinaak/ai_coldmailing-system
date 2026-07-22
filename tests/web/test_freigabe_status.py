from datetime import datetime

import pytest

from web.freigabe_status import FreigabeStatusStore, VeralteterStand


TEXTE = [{
    "email": "anna@firma.de",
    "betreff": "Kurze Frage",
    "mail_1": "Hallo Anna",
    "follow_up_1": "Kurze Erinnerung",
    "follow_up_2": "Letzte Nachricht",
}]


def test_initialisiert_feste_id_und_drei_offene_schritte(tmp_path):
    store = FreigabeStatusStore(
        tmp_path,
        jetzt=lambda: datetime(2026, 7, 22, 10, 0),
        id_factory=lambda: "empf-1",
    )

    ansicht = store.ansicht(TEXTE)

    assert ansicht["recipients"][0]["id"] == "empf-1"
    assert ansicht["recipients"][0]["steps"] == {
        "mail_1": {"approved": False, "approved_at": None, "approved_by": None},
        "follow_up_1": {"approved": False, "approved_at": None, "approved_by": None},
        "follow_up_2": {"approved": False, "approved_at": None, "approved_by": None},
    }
    assert (tmp_path / "freigabe-status.json").is_file()


def test_alte_gesamtfreigabe_wird_einmalig_als_bestaetigt_uebernommen(tmp_path):
    store = FreigabeStatusStore(tmp_path, id_factory=lambda: "empf-1")

    ansicht = store.ansicht(
        TEXTE,
        alte_freigabe={"von": "Lena Hartmann", "am": "22.07.2026, 10:00"},
    )

    assert all(s["approved"] for s in ansicht["recipients"][0]["steps"].values())
    assert ansicht["recipients"][0]["steps"]["mail_1"]["approved_by"] == "Lena Hartmann"


def test_textaenderung_macht_nur_einen_schritt_offen(tmp_path):
    store = FreigabeStatusStore(tmp_path, id_factory=lambda: "empf-1")
    start = store.ansicht(TEXTE)
    store.bestaetigungen_setzen(
        TEXTE,
        ["empf-1"],
        actor="Lena",
        approved=True,
        revision=start["revision"],
        step=None,
    )
    geaendert = [{**TEXTE[0], "follow_up_1": "Neue Erinnerung"}]

    ansicht = store.ansicht(geaendert)

    steps = ansicht["recipients"][0]["steps"]
    assert steps["mail_1"]["approved"] is True
    assert steps["follow_up_1"]["approved"] is False
    assert steps["follow_up_2"]["approved"] is True


def test_veraltete_revision_veraendert_nichts(tmp_path):
    store = FreigabeStatusStore(tmp_path, id_factory=lambda: "empf-1")
    start = store.ansicht(TEXTE)
    store.bestaetigungen_setzen(
        TEXTE,
        ["empf-1"],
        actor="Lena",
        approved=True,
        revision=start["revision"],
        step="mail_1",
    )
    stand_nach_erster_aenderung = (tmp_path / "freigabe-status.json").read_bytes()

    with pytest.raises(VeralteterStand):
        store.bestaetigungen_setzen(
            TEXTE,
            ["empf-1"],
            actor="Lena",
            approved=True,
            revision=start["revision"],
            step="follow_up_1",
        )

    assert (tmp_path / "freigabe-status.json").read_bytes() == stand_nach_erster_aenderung


def test_override_ersetzt_nur_gewaehlten_schritt(tmp_path):
    store = FreigabeStatusStore(tmp_path, id_factory=lambda: "empf-1")
    start = store.ansicht(TEXTE)

    store.override_setzen(
        TEXTE,
        "empf-1",
        "mail_1",
        {"betreff": "Neu", "text": "Neuer Erstkontakt"},
        start["revision"],
    )

    assert store.materialisieren(TEXTE) == [{
        **TEXTE[0],
        "betreff": "Neu",
        "mail_1": "Neuer Erstkontakt",
    }]


def test_qa_blockierter_empfaenger_kann_nicht_bestaetigt_werden(tmp_path):
    store = FreigabeStatusStore(tmp_path, id_factory=lambda: "empf-1")
    blockiert = [{**TEXTE[0], "_qa_blocked": True, "_qa_reason": "Betreff zu lang"}]
    start = store.ansicht(blockiert)

    with pytest.raises(ValueError, match="Nacharbeit"):
        store.bestaetigungen_setzen(
            blockiert,
            ["empf-1"],
            actor="Lena",
            approved=True,
            revision=start["revision"],
            step=None,
        )

    assert store.alles_bestaetigt(blockiert) is False
