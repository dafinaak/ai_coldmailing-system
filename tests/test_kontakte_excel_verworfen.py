"""Aussortierte Adressen muessen ihren Grund tragen, nicht "noch kein Text".

Gefunden am 17.08.2026 an einer echten Mappe: 23 Zeilen im Excel, aber nur
22 Empfaenger in der Freigabe-Tabelle. Die 23. Zeile war Ronny Hohmann - im
Dedupe aussortiert, weil er in einer frueheren, tatsaechlich versendeten
Kampagne schon angeschrieben wurde. In der Mappe stand bei ihm "noch kein
Text", als warte man nur noch auf die KI. Er geht aber bewusst gar nicht
raus.
"""
import json

from pipeline.kontakte_excel import mappe_bauen


def _lauf(tmp_path, *, leads, verworfen=(), fertig=()):
    lauf = tmp_path / "lauf"
    lauf.mkdir()
    (lauf / "leads.json").write_text(json.dumps({"leads": list(leads)}),
                                      encoding="utf-8")
    (lauf / "firmen.json").write_text(json.dumps([]), encoding="utf-8")
    (lauf / "dedupe.json").write_text(
        json.dumps({"behalten": [], "verworfen": list(verworfen)}), encoding="utf-8")
    (lauf / "personalisierung.json").write_text(
        json.dumps({"fertig": list(fertig), "nacharbeit": []}), encoding="utf-8")
    return lauf


def _kontakte(lauf):
    blatt = mappe_bauen(lauf)["Kontakte"]
    kopf = [z.value for z in next(blatt.iter_rows(max_row=1))]
    return [dict(zip(kopf, [z for z in zeile]))
            for zeile in blatt.iter_rows(min_row=2, values_only=True)]


LEAD = {"first_name": "Ronny", "last_name": "Hohmann",
        "email": "ronny.hohmann@ai-lo.de", "company": "Ai-Lo GmbH",
        "website": "https://www.ai-lo.de/"}


def test_aussortierte_zeile_sagt_dass_sie_nicht_rausgeht(tmp_path):
    lauf = _lauf(tmp_path, leads=[LEAD], verworfen=[
        {"email": "ronny.hohmann@ai-lo.de",
         "grund": "bereits in früherem Lauf angeschrieben"}])

    zeile = _kontakte(lauf)[0]

    assert zeile["Text"] == "geht nicht raus"
    assert "bereits in früherem Lauf" in zeile["Hinweis"]


def test_kein_irrefuehrendes_noch_kein_text(tmp_path):
    lauf = _lauf(tmp_path, leads=[LEAD], verworfen=[
        {"email": "ronny.hohmann@ai-lo.de", "grund": "Domain auf Sperrliste"}])

    assert _kontakte(lauf)[0]["Text"] != "noch kein Text"


def test_normaler_kontakt_bleibt_unveraendert(tmp_path):
    lauf = _lauf(tmp_path, leads=[LEAD], fertig=[
        {"email": "ronny.hohmann@ai-lo.de", "betreff": "B", "mail_1": "M"}])

    zeile = _kontakte(lauf)[0]

    assert zeile["Text"] == "fertig"
    assert zeile["Betreff"] == "B"


def test_ohne_dedupe_datei_bleibt_alles_wie_bisher(tmp_path):
    # Alte Laufordner ohne dedupe.json muessen weiter lesbar sein.
    lauf = _lauf(tmp_path, leads=[LEAD])
    (lauf / "dedupe.json").unlink()

    assert _kontakte(lauf)[0]["Text"] == "noch kein Text"
