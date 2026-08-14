"""Ein Empfaenger darf dasselbe Angebot nicht zweimal von uns bekommen.

Gefunden am 14.08.2026: Der Doppel-Schutz sah nur in die Mappe des eigenen
Kunden. Das Formular legt aber fuer JEDE Kampagne einen neuen Kunden an -
die eigene Vorgeschichte war damit immer leer, und zwei Kampagnen konnten
denselben Geschaeftsfuehrer anschreiben, ohne dass es irgendwo auffiel.
"""
import json

from pipeline.dedupe import dedupe
from pipeline.sourcing import Lead


def _lead(email):
    return Lead(first_name="A", last_name="B", email=email, company="C",
                title="Geschäftsführer", website="https://c.de", source="test")


def _lauf_mit_leads(ordner, *emails):
    ordner.mkdir(parents=True, exist_ok=True)
    (ordner / "leads.json").write_text(
        json.dumps({"leads": [{"email": e} for e in emails]}), encoding="utf-8")
    return ordner


def test_treffer_aus_einer_anderen_kampagne_wird_erkannt(tmp_path):
    laeufe = tmp_path / "laeufe"
    _lauf_mit_leads(laeufe / "kampagne-a" / "20260701", "chef@firma.de")
    neu = laeufe / "kampagne-b" / "20260814"
    neu.mkdir(parents=True)

    behalten, verworfen = dedupe([_lead("chef@firma.de")],
                                 laeufe / "kampagne-b", aktueller_lauf=neu,
                                 alle_kampagnen_dir=laeufe)

    assert behalten == []
    assert verworfen[0]["grund"] == "bereits in früherem Lauf angeschrieben"


def test_eigene_fruehere_laeufe_zaehlen_weiterhin(tmp_path):
    laeufe = tmp_path / "laeufe"
    _lauf_mit_leads(laeufe / "kampagne-a" / "20260701", "chef@firma.de")
    neu = laeufe / "kampagne-a" / "20260814"
    neu.mkdir(parents=True)

    behalten, _ = dedupe([_lead("chef@firma.de")],
                         laeufe / "kampagne-a", aktueller_lauf=neu,
                         alle_kampagnen_dir=laeufe)

    assert behalten == []


def test_der_eigene_laufende_ordner_zaehlt_nicht_als_frueher(tmp_path):
    laeufe = tmp_path / "laeufe"
    neu = _lauf_mit_leads(laeufe / "kampagne-a" / "20260814", "chef@firma.de")

    behalten, _ = dedupe([_lead("chef@firma.de")],
                         laeufe / "kampagne-a", aktueller_lauf=neu,
                         alle_kampagnen_dir=laeufe)

    assert [l.email for l in behalten] == ["chef@firma.de"]


def test_unbekannte_adresse_bleibt(tmp_path):
    laeufe = tmp_path / "laeufe"
    _lauf_mit_leads(laeufe / "kampagne-a" / "20260701", "jemand@anders.de")
    neu = laeufe / "kampagne-b" / "20260814"
    neu.mkdir(parents=True)

    behalten, verworfen = dedupe([_lead("chef@firma.de")],
                                 laeufe / "kampagne-b", aktueller_lauf=neu,
                                 alle_kampagnen_dir=laeufe)

    assert [l.email for l in behalten] == ["chef@firma.de"]
    assert verworfen == []


def test_kaputte_leads_datei_haelt_den_lauf_nicht_auf(tmp_path):
    laeufe = tmp_path / "laeufe"
    kaputt = laeufe / "kampagne-a" / "20260701"
    kaputt.mkdir(parents=True)
    (kaputt / "leads.json").write_text("{kein json", encoding="utf-8")
    neu = laeufe / "kampagne-b" / "20260814"
    neu.mkdir(parents=True)

    behalten, _ = dedupe([_lead("chef@firma.de")],
                         laeufe / "kampagne-b", aktueller_lauf=neu,
                         alle_kampagnen_dir=laeufe)

    assert [l.email for l in behalten] == ["chef@firma.de"]
