"""Einen fertigen Text zur Ansicht an die eigene Adresse schicken.

Am 18.08.2026 gewünscht: den Text nicht nur im Browser lesen, sondern im
Posteingang sehen - Absender, Betreff, Anrede, so wie ein Geschäftsführer
ihn bekommt.

Zwei Dinge dürfen dabei nie passieren: die Mail darf nicht an einen echten
Empfänger der Runde gehen, und die Hilfs-Kampagne darf nicht aktiv
stehenbleiben (Projektregel vom 17.08.2026 - keine laufende Kampagne ohne
Dafinas Wort).
"""
import json
import sys
import time
from pathlib import Path

import pytest

from web import probe_versand


def _warte(job, sekunden=10):
    for _ in range(int(sekunden * 20)):
        if not probe_versand._laeuft(job):
            return
        time.sleep(0.05)


def _befehl_schreibt_ergebnis(gesendet=True):
    code = (
        "import json,sys,os\n"
        "job=sys.argv[-1]\n"
        "a=json.load(open(os.path.join(job,'auftrag.json')))\n"
        f"json.dump({{'gesendet': {gesendet!r}, 'fehler': '',"
        " 'campaign_id':'c1', 'empfaenger': a['empfaenger']},"
        "open(os.path.join(job,'ergebnis.json'),'w'))\n"
        "print('fertig')\n")
    return [sys.executable, "-c", code]


TEXT = "Guten Tag Herr Wessel, ..."


def test_probe_laeuft_durch_und_meldet_fertig(tmp_path):
    job = probe_versand.starte(
        tmp_path, "k1", absender="o.redschlag@marke.email",
        empfaenger="ich@digitaldiamonds.agency", betreff="Betreff", text=TEXT,
        befehl=_befehl_schreibt_ergebnis())
    _warte(job)

    stand = probe_versand.status(tmp_path, "k1")

    assert stand["zustand"] == "fertig"
    assert "ich@digitaldiamonds.agency" in stand["meldung"]


def test_der_auftrag_traegt_den_echten_text(tmp_path):
    job = probe_versand.starte(
        tmp_path, "k1", absender="o.redschlag@marke.email",
        empfaenger="ich@firma.de", betreff="Betreff", text=TEXT,
        befehl=_befehl_schreibt_ergebnis())

    auftrag = json.loads((job / "auftrag.json").read_text(encoding="utf-8"))
    assert auftrag["text"] == TEXT
    assert auftrag["betreff"] == "Betreff"


def test_an_einen_echten_empfaenger_geht_nichts(tmp_path):
    # Der wichtigste Riegel: sonst bekaeme eine Firma die Mail, ohne dass
    # die Runde je freigegeben wurde.
    with pytest.raises(probe_versand.ProbeFehler, match="echten Empfänger"):
        probe_versand.starte(
            tmp_path, "k1", absender="o.redschlag@marke.email",
            empfaenger="chef@kundenfirma.de", betreff="B", text=TEXT,
            verbotene=("chef@kundenfirma.de", "zwei@firma.de"))


def test_gross_und_kleinschreibung_hilft_nicht_daran_vorbei(tmp_path):
    with pytest.raises(probe_versand.ProbeFehler, match="echten Empfänger"):
        probe_versand.starte(
            tmp_path, "k1", absender="o.redschlag@marke.email",
            empfaenger="Chef@Kundenfirma.DE", betreff="B", text=TEXT,
            verbotene=("chef@kundenfirma.de",))


def test_ohne_gueltige_adresse_startet_nichts(tmp_path):
    with pytest.raises(probe_versand.ProbeFehler, match="gültige"):
        probe_versand.starte(tmp_path, "k1", absender="a@b.de",
                             empfaenger="kein-at-zeichen", betreff="B", text=TEXT)


def test_ohne_absender_startet_nichts(tmp_path):
    with pytest.raises(probe_versand.ProbeFehler, match="Absender"):
        probe_versand.starte(tmp_path, "k1", absender="", empfaenger="ich@firma.de",
                             betreff="B", text=TEXT)


def test_leerer_text_startet_nichts(tmp_path):
    with pytest.raises(probe_versand.ProbeFehler, match="leer"):
        probe_versand.starte(tmp_path, "k1", absender="a@b.de",
                             empfaenger="ich@firma.de", betreff="B", text="   ")


def test_gescheiterter_versand_wird_gemeldet(tmp_path):
    job = probe_versand.starte(
        tmp_path, "k1", absender="a@b.de", empfaenger="ich@firma.de",
        betreff="B", text=TEXT, befehl=_befehl_schreibt_ergebnis(gesendet=False))
    _warte(job)

    assert probe_versand.status(tmp_path, "k1")["zustand"] == "fehler"


def test_ohne_probe_kein_hinweis(tmp_path):
    assert probe_versand.status(tmp_path, "gibtsnicht")["zustand"] is None


def test_proben_liegen_nicht_bei_den_auftraegen(tmp_path):
    # Sonst meldet das Dashboard sie als angehaltene Auftraege.
    probe_versand.starte(tmp_path, "k1", absender="a@b.de",
                         empfaenger="ich@firma.de", betreff="B", text=TEXT,
                         befehl=_befehl_schreibt_ergebnis())

    assert (tmp_path / "ansichts-proben" / "k1").is_dir()
    laeufe = tmp_path / "laeufe"
    assert not laeufe.exists() or "k1" not in [p.name for p in laeufe.iterdir()]
