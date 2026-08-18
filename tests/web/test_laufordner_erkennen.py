"""Nicht jeder Ordner unter laeufe/ ist ein Auftrag.

Gefunden am 17.08.2026: Das Dashboard meldete dauerhaft sieben rote
"angehalten - Problem, das wir nicht genauer benennen können". Die meisten
davon waren gar keine Auftraege:

  laeufe/leadquellen/plr-30-31          der gesammelte Firmenbestand
  laeufe/vergleich-anbieter/...         alte Anbieter-Vergleiche
  laeufe/plr30-39/probelauf-10          ein altes Experiment

Weil sie nie "fertig" wurden, fielen sie in den Sammelzustand
"angehalten" - und da es keine lauf.log gab, aus der ein Grund zu lesen
gewesen waere, blieb der Text nichtssagend.
"""
import json

from web.laufmanager import ist_laufordner


def test_ordner_mit_kunde_pfad_ist_ein_auftrag(tmp_path):
    (tmp_path / "kunde_pfad.json").write_text(
        json.dumps({"pfad": "kunden/x.yaml"}), encoding="utf-8")

    assert ist_laufordner(tmp_path)


def test_ordner_mit_auftrag_meta_ist_ein_auftrag(tmp_path):
    (tmp_path / "auftrag_meta.json").write_text(
        json.dumps({"limit": 50}), encoding="utf-8")

    assert ist_laufordner(tmp_path)


def test_firmenbestand_ist_kein_auftrag(tmp_path):
    # So sieht laeufe/leadquellen/plr-30-31 aus.
    (tmp_path / "firmen.json").write_text("[]", encoding="utf-8")
    (tmp_path / "branchenpruefung.json").write_text("{}", encoding="utf-8")

    assert not ist_laufordner(tmp_path)


def test_anbieter_vergleich_ist_kein_auftrag(tmp_path):
    # So sieht laeufe/vergleich-anbieter/... aus.
    (tmp_path / "bericht.md").write_text("# Vergleich", encoding="utf-8")
    (tmp_path / "ergebnisse.json").write_text("{}", encoding="utf-8")

    assert not ist_laufordner(tmp_path)


def test_leerer_ordner_ist_kein_auftrag(tmp_path):
    assert not ist_laufordner(tmp_path)


def test_ordner_der_nur_eine_kampagne_festhaelt_ist_ein_auftrag(tmp_path):
    """So sieht die echte Kampagne mit 277 Empfaengern aus.

    Sie wurde per API angelegt und hier nur verknuepft - kein kunde_pfad,
    kein auftrag_meta. Die erste Fassung dieser Pruefung hat sie deshalb
    aussortiert: die Kampagne verschwand aus der Liste, das Postfach holte
    ihre Antworten nicht mehr, und das CRM blieb leer. Ein Ordner mit
    campaign_id ist IMMER ein Auftrag.
    """
    (tmp_path / "versand_komplett.json").write_text(
        json.dumps({"campaign_id": "camp-1"}), encoding="utf-8")

    assert ist_laufordner(tmp_path)


def test_freigabe_allein_reicht_auch(tmp_path):
    (tmp_path / "FREIGABE.txt").write_text("Freigegeben am ...", encoding="utf-8")

    assert ist_laufordner(tmp_path)


def test_jeder_arbeitsschritt_zaehlt_als_auftrag(tmp_path):
    for name in ("leads.json", "dedupe.json", "personalisierung.json",
                 "pruefung_ok.json", "versand.json", "lauf.log"):
        ordner = tmp_path / name.replace(".", "-")
        ordner.mkdir()
        (ordner / name).write_text("{}", encoding="utf-8")
        assert ist_laufordner(ordner), name


def test_abgebrochener_auftrag_bleibt_ein_auftrag(tmp_path):
    # Ein Lauf, der sofort nach dem Start starb, hat nur kunde_pfad.json -
    # er ist trotzdem ein Auftrag und soll weiter gemeldet werden.
    (tmp_path / "kunde_pfad.json").write_text(
        json.dumps({"pfad": "kunden/x.yaml"}), encoding="utf-8")

    assert ist_laufordner(tmp_path)
