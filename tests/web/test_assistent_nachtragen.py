"""Schritt 5 muss in die schon geschriebene Kundendatei nachgetragen werden.

Gefunden am 17.08.2026 an einer echten Kampagne mit 17 Empfängern: Die
Kundendatei entsteht in Schritt 4 (dort startet die Suche), Schritt 5 wird
erst DANACH ausgefüllt. Die Antworten aus Schritt 5 landeten deshalb nur im
Entwurf - in der Kundendatei standen Postfach und Signatur leer und
versand_modus fest auf "test". Die Kampagne wurde wieder ohne Absender
angelegt, und "Echter Versand" konnte gar nicht ankommen.
"""
from pathlib import Path

import yaml

from web.routen.assistent import _versand_einstellungen_nachtragen

VORHER = {
    "name": "Probe", "webseite": "beispiel.de", "angebot": "A",
    "tonalitaet": "ruhig", "absender": "post@example.com",
    "zielgruppe": {"titel": ["Geschäftsführer"], "region": ["Hannover"],
                   "firmengroesse": ["alle"]},
    "follow_up_tage": [7, 14], "test_empfaenger": ["post@example.com"],
    "versand_postfach": "", "tageslimit": 20, "signatur": "",
    "versand_modus": "test", "maps_suche": "(Assistent 1)",
}

SCHRITT_5 = {
    "versand_postfach": "o.redschlag@poleposition-automation.email",
    "tageslimit": 35, "zeit_von": "09:00", "zeit_bis": "17:00",
    "wochentage": ["mo", "fr"],
    "signatur": "Oliver Redschlag\nPolePosition Automation",
    "versand_modus": "echt",
}


def _vorbereiten(tmp_path, inhalt=None):
    (tmp_path / "kunden").mkdir(parents=True, exist_ok=True)
    pfad = tmp_path / "kunden" / "probe.yaml"
    pfad.write_text(yaml.safe_dump(inhalt if inhalt is not None else VORHER,
                                    allow_unicode=True), encoding="utf-8")
    return pfad


def _nachtragen(tmp_path, werte=None, kunde_datei="kunden/probe.yaml"):
    entwurf = {"kennung": "1", "daten": {"kunde_datei": kunde_datei}}
    _versand_einstellungen_nachtragen(Path(tmp_path), entwurf,
                                       werte if werte is not None else SCHRITT_5)
    pfad = tmp_path / "kunden" / "probe.yaml"
    return yaml.safe_load(pfad.read_text(encoding="utf-8"))


def test_alle_antworten_aus_schritt_5_stehen_danach_drin(tmp_path):
    _vorbereiten(tmp_path)

    inhalt = _nachtragen(tmp_path)

    assert inhalt["versand_postfach"] == "o.redschlag@poleposition-automation.email"
    assert inhalt["tageslimit"] == 35
    assert (inhalt["zeit_von"], inhalt["zeit_bis"]) == ("09:00", "17:00")
    assert inhalt["wochentage"] == ["mo", "fr"]
    assert "PolePosition" in inhalt["signatur"]


def test_echter_versand_kommt_an(tmp_path):
    _vorbereiten(tmp_path)

    assert _nachtragen(tmp_path)["versand_modus"] == "echt"


def test_ohne_ausdrueckliche_wahl_bleibt_es_probe(tmp_path):
    _vorbereiten(tmp_path)

    inhalt = _nachtragen(tmp_path, {**SCHRITT_5, "versand_modus": "vielleicht"})

    assert inhalt["versand_modus"] == "test"


def test_absender_wird_der_name_aus_der_signatur(tmp_path):
    _vorbereiten(tmp_path)

    assert _nachtragen(tmp_path)["absender"] == "Oliver Redschlag"


def test_alles_andere_bleibt_unangetastet(tmp_path):
    _vorbereiten(tmp_path)

    inhalt = _nachtragen(tmp_path)

    assert inhalt["name"] == "Probe"
    assert inhalt["angebot"] == "A"
    assert inhalt["follow_up_tage"] == [7, 14]
    assert inhalt["test_empfaenger"] == ["post@example.com"]
    assert inhalt["maps_suche"] == "(Assistent 1)"


def test_ohne_kundendatei_passiert_nichts(tmp_path):
    # Kein Lauf gestartet -> keine Datei -> kein Absturz.
    entwurf = {"kennung": "1", "daten": {}}
    _versand_einstellungen_nachtragen(Path(tmp_path), entwurf, SCHRITT_5)


def test_fehlende_datei_stuerzt_nicht_ab(tmp_path):
    entwurf = {"kennung": "1", "daten": {"kunde_datei": "kunden/gibtsnicht.yaml"}}
    _versand_einstellungen_nachtragen(Path(tmp_path), entwurf, SCHRITT_5)


def test_datei_bleibt_fuer_die_pipeline_lesbar(tmp_path):
    from pipeline.config import load_kunde

    _vorbereiten(tmp_path)
    _nachtragen(tmp_path)

    kunde = load_kunde(tmp_path / "kunden" / "probe.yaml")
    assert kunde.versand_modus == "echt"
    assert kunde.versand_postfach == "o.redschlag@poleposition-automation.email"
    assert kunde.wochentage == ["mo", "fr"]
