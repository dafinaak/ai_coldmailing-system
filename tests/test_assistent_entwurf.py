"""The wizard's saved state.

The promise made to the user is: whatever you typed survives. These
tests hold that promise to the two ways it breaks - losing values
between steps, and a crash landing a half-written file on disk.
"""
import json

import pytest

from pipeline import assistent_entwurf as entwurf


def test_neuer_entwurf_liegt_sofort_auf_der_platte(tmp_path):
    neu = entwurf.anlegen(tmp_path)

    assert (tmp_path / "entwuerfe" / f"{neu['kennung']}.json").exists()
    assert neu["schritt"] == 1
    assert neu["daten"] == {}


def test_werte_ueberleben_den_naechsten_schritt(tmp_path):
    neu = entwurf.anlegen(tmp_path)

    entwurf.schritt_speichern(tmp_path, neu["kennung"], 1,
                              {"name": "IT-Partner", "sprache": "de"})
    entwurf.schritt_speichern(tmp_path, neu["kennung"], 2, {"usp": ["schnell"]})
    geladen = entwurf.laden(tmp_path, neu["kennung"])

    assert geladen["daten"]["name"] == "IT-Partner"      # Schritt 1 noch da
    assert geladen["daten"]["usp"] == ["schnell"]
    assert geladen["schritt"] == 2


def test_zurueckgehen_vergisst_nicht_wie_weit_man_war(tmp_path):
    # Wer von Schritt 4 auf 2 zurueckspringt, soll wieder vorwaerts
    # klicken koennen, ohne alles neu auszufuellen.
    neu = entwurf.anlegen(tmp_path)
    entwurf.schritt_speichern(tmp_path, neu["kennung"], 4, {"a": 1})

    zurueck = entwurf.schritt_speichern(tmp_path, neu["kennung"], 2, {"b": 2})

    assert zurueck["schritt"] == 2
    assert zurueck["hoechster_schritt"] == 4
    assert zurueck["daten"] == {"a": 1, "b": 2}


def test_unbekannter_entwurf_sagt_es_verstaendlich(tmp_path):
    with pytest.raises(FileNotFoundError, match="neu starten"):
        entwurf.schritt_speichern(tmp_path, "gibtsnicht", 1, {})


def test_schritt_ausserhalb_der_sechs_wird_abgelehnt(tmp_path):
    neu = entwurf.anlegen(tmp_path)

    with pytest.raises(ValueError, match="gibt es nicht"):
        entwurf.schritt_speichern(tmp_path, neu["kennung"], 9, {})


def test_kaputter_entwurf_gilt_als_weg_statt_als_fehler(tmp_path):
    neu = entwurf.anlegen(tmp_path)
    (tmp_path / "entwuerfe" / f"{neu['kennung']}.json").write_text("{kaputt")

    assert entwurf.laden(tmp_path, neu["kennung"]) is None


def test_speichern_hinterlaesst_keine_halbe_datei(tmp_path):
    neu = entwurf.anlegen(tmp_path)
    entwurf.schritt_speichern(tmp_path, neu["kennung"], 1, {"x": "y"})

    ordner = tmp_path / "entwuerfe"
    assert list(ordner.glob("*.tmp")) == []
    json.loads((ordner / f"{neu['kennung']}.json").read_text())


def test_entwuerfe_kommen_neueste_zuerst(tmp_path):
    entwurf.anlegen(tmp_path, kennung="20260810-100000")
    entwurf.anlegen(tmp_path, kennung="20260812-100000")
    entwurf.anlegen(tmp_path, kennung="20260811-100000")

    kennungen = [e["kennung"] for e in entwurf.alle(tmp_path)]

    assert kennungen == ["20260812-100000", "20260811-100000", "20260810-100000"]


def test_loeschen_raeumt_auf(tmp_path):
    neu = entwurf.anlegen(tmp_path)

    assert entwurf.loeschen(tmp_path, neu["kennung"]) is True
    assert entwurf.laden(tmp_path, neu["kennung"]) is None
    assert entwurf.loeschen(tmp_path, neu["kennung"]) is False


def test_kennung_kann_keine_fremden_dateien_treffen(tmp_path):
    # "../users.yaml" darf nicht aus dem Entwurfsordner herausfuehren.
    with pytest.raises(ValueError, match="Ungültige"):
        entwurf.laden(tmp_path, "../../")
