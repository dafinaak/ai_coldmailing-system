"""Eine Firmen-Sammlung im Hintergrund starten und ihren Stand abfragen.

Sammeln dauert Minuten und kostet Geld. Die Oberflaeche muss deshalb
sehen koennen, ob es noch laeuft, fertig ist oder abgebrochen wurde - und
zwar ohne zu raten.

Hier wird nie wirklich gesammelt: statt 'python -m pipeline' laeuft ein
winziges Ersatzprogramm.
"""
import json
import sys
import time
from pathlib import Path

import pytest

from web import sammelmanager


def _warte_auf_ende(job, sekunden=10):
    for _ in range(int(sekunden * 20)):
        if not sammelmanager._laeuft(job):
            return
        time.sleep(0.05)


def _befehl_schreibt_ergebnis(firmen=2):
    """Ersatzprogramm: legt die Zieldatei an, wie es die Sammlung taete."""
    code = (
        "import json,sys,os\n"
        "ordner=sys.argv[sys.argv.index('--ordner')+1]\n"
        "ziel=os.path.join('laeufe','leadquellen',ordner)\n"
        "os.makedirs(ziel,exist_ok=True)\n"
        f"json.dump([{{'name':f'F{{i}}','domain':f'f{{i}}.de'}} for i in range({firmen})],"
        "open(os.path.join(ziel,'firmen.json'),'w'))\n"
        "print('fertig')\n")
    return [sys.executable, "-c", code]


def _befehl_scheitert():
    return [sys.executable, "-c",
            "import sys; print('Apify antwortet mit 402: kein Guthaben');"
            "sys.exit(1)"]


def test_sammlung_laeuft_durch_und_meldet_fertig(tmp_path):
    job = sammelmanager.starte(tmp_path, "k1", "Hannover", 10, ["Webdesigner"],
                                befehl=_befehl_schreibt_ergebnis(3))
    _warte_auf_ende(job)

    stand = sammelmanager.status(tmp_path, "k1")

    assert stand["zustand"] == "fertig"
    assert stand["firmen"] == 3
    assert "3 Firmen" in stand["meldung"]


def test_ergebnis_landet_im_bestand(tmp_path):
    # Der Bestand liest alle Ordner unter laeufe/leadquellen/ - die neue
    # Sammlung muss dort ankommen, ohne dass jemand etwas verschiebt.
    from web.routen.assistent import _firmen_bestand

    job = sammelmanager.starte(tmp_path, "k1", "Hannover", 10, ["Webdesigner"],
                                befehl=_befehl_schreibt_ergebnis(2))
    _warte_auf_ende(job)

    assert len(_firmen_bestand(tmp_path)) == 2


def test_abgebrochene_sammlung_zeigt_den_grund(tmp_path):
    job = sammelmanager.starte(tmp_path, "k1", "Hannover", 10, ["Webdesigner"],
                                befehl=_befehl_scheitert())
    _warte_auf_ende(job)

    stand = sammelmanager.status(tmp_path, "k1")

    assert stand["zustand"] == "fehler"
    assert "402" in stand["meldung"], stand["meldung"]


def test_unbekannte_sammlung_sagt_es_klar(tmp_path):
    stand = sammelmanager.status(tmp_path, "gibtsnicht")

    assert stand["zustand"] == "unbekannt"


def test_ohne_ort_wird_nicht_gestartet(tmp_path):
    with pytest.raises(sammelmanager.SammelFehler, match="Ort"):
        sammelmanager.starte(tmp_path, "k1", "", 10, ["Webdesigner"])


def test_ohne_suchbegriffe_wird_nicht_gestartet(tmp_path):
    with pytest.raises(sammelmanager.SammelFehler, match="Suchbegriffe"):
        sammelmanager.starte(tmp_path, "k1", "Hannover", 10, [])


def test_der_zielordner_steht_vor_dem_start_fest(tmp_path):
    # Auch wenn der Prozess abstuerzt, muss der Aufrufer wissen, wo er
    # haette nachsehen muessen.
    job = sammelmanager.starte(tmp_path, "k1", "Hannover", 10, ["Webdesigner"],
                                befehl=_befehl_scheitert())

    meta = json.loads((job / "meta.json").read_text(encoding="utf-8"))
    assert meta["ziel_ordner"] == "sammlung-k1"
    assert meta["ort"] == "Hannover"


def test_sammlungen_liegen_nicht_bei_den_auftraegen(tmp_path):
    # Sonst meldet das Dashboard sie als angehaltene Auftraege - genau der
    # Fehler, der am 17.08.2026 sieben falsche Warnungen erzeugt hat.
    sammelmanager.starte(tmp_path, "k1", "Hannover", 10, ["Webdesigner"],
                         befehl=_befehl_schreibt_ergebnis(1))

    assert (tmp_path / "sammlungen" / "k1").is_dir()
    laeufe = tmp_path / "laeufe"
    if laeufe.exists():
        assert "k1" not in [p.name for p in laeufe.iterdir()]
