"""Nothing that was paid for may be lost.

A batch is billed the moment Dropcontact accepts it, not when we read the
answer. On 11.08.2026 a batch of 100 people was handed over, took longer
than the wait window, and the run threw the result away - the credits
were gone and the addresses had to be fetched back by hand. These tests
pin the behaviour that prevents a repeat: write the request_id down
before fetching, pick unfetched batches back up on the next start, and
never pay twice for a name already answered.
"""
import json

import pytest

from pipeline.config import Kunde
from pipeline.schnelllauf import Zwischenstand, lauf_ausfuehren
from tests.test_schnelllauf import (
    KUNDE, FakeHunter, FakeImpressum, firma, person,
)


class ZaehlendesDropcontact:
    """Splits handing over from fetching, so a crash can be simulated."""

    def __init__(self, adressen, stirbt_beim_abholen=False):
        self.adressen = adressen
        self.stirbt_beim_abholen = stirbt_beim_abholen
        self.abgegeben, self.abgeholt = [], []
        self._offen = {}
        self._zaehler = 0

    def batch_abgeben(self, anfragen):
        gesendet = [(nr, a) for nr, a in enumerate(anfragen)
                    if a.get("first_name") and a.get("last_name")]
        if not gesendet:
            return None, []
        self._zaehler += 1
        request_id = f"r{self._zaehler}"
        self.abgegeben.append([f"{a['first_name']} {a['last_name']}"
                               for _, a in gesendet])
        self._offen[request_id] = gesendet
        return request_id, gesendet

    def zeilen_holen(self, request_id):
        if self.stirbt_beim_abholen:
            raise RuntimeError("kein Ergebnis")
        return [{"first_name": a["first_name"], "last_name": a["last_name"],
                 "website": a.get("website"),
                 "email": ([{"email": self.adressen[schluessel],
                             "qualification": "nominative@pro"}]
                           if (schluessel := f"{a['first_name']} {a['last_name']}")
                           in self.adressen else [])}
                for _, a in self._offen[request_id]]

    def batch_abholen(self, request_id, gesendet, gesamt=None):
        if self.stirbt_beim_abholen:
            raise RuntimeError("kein Ergebnis")
        self.abgeholt.append(request_id)
        from pipeline.sources.dropcontact import _beste_email
        ergebnisse = [None] * (gesamt if gesamt is not None else len(gesendet))
        for (nr, _), zeile in zip(gesendet, self.zeilen_holen(request_id)):
            ergebnisse[nr] = _beste_email(zeile["email"])
        return ergebnisse


def impressum_fuer(anzahl):
    return FakeImpressum({
        f"f{i}.de": {"personen": [person("Vor", f"Nach{i}")], "mail_domain": None}
        for i in range(anzahl)})


def firmen_fuer(anzahl):
    return [firma(f"F{i}", f"f{i}.de") for i in range(anzahl)]


def test_request_id_steht_auf_der_platte_bevor_abgeholt_wird(tmp_path):
    # Der Kernfall: Abgabe klappt, Abholen scheitert. Die request_id muss
    # den Absturz ueberleben, sonst ist der bezahlte Batch verloren.
    dropcontact = ZaehlendesDropcontact({}, stirbt_beim_abholen=True)

    with pytest.raises(RuntimeError):
        lauf_ausfuehren(firmen_fuer(2), KUNDE, dropcontact, impressum_fuer(2),
                        FakeHunter(), arbeiter=2, lauf_dir=str(tmp_path),
                        fortschritt=lambda _: None)

    gespeichert = json.loads((tmp_path / "zwischenstand.json").read_text())
    assert [a["request_id"] for a in gespeichert["offene_auftraege"]] == ["r1"]


def test_offener_auftrag_wird_beim_neustart_kostenlos_nachgeholt(tmp_path):
    adressen = {"Vor Nach0": "a@f0.de", "Vor Nach1": "b@f1.de"}
    kaputt = ZaehlendesDropcontact(adressen, stirbt_beim_abholen=True)
    with pytest.raises(RuntimeError):
        lauf_ausfuehren(firmen_fuer(2), KUNDE, kaputt, impressum_fuer(2),
                        FakeHunter(), arbeiter=2, lauf_dir=str(tmp_path),
                        fortschritt=lambda _: None)

    # Neustart: derselbe Ordner, jetzt antwortet Dropcontact wieder.
    heil = ZaehlendesDropcontact(adressen)
    heil._offen = kaputt._offen                     # derselbe Auftrag beim Anbieter
    ergebnisse = lauf_ausfuehren(firmen_fuer(2), KUNDE, heil, impressum_fuer(2),
                                 FakeHunter(), arbeiter=2, lauf_dir=str(tmp_path),
                                 fortschritt=lambda _: None)

    assert heil.abgegeben == []                     # nichts neu bezahlt
    assert [e["leads"][0]["email"] for e in ergebnisse] == ["a@f0.de", "b@f1.de"]
    gespeichert = json.loads((tmp_path / "zwischenstand.json").read_text())
    assert gespeichert["offene_auftraege"] == []


def test_gelesene_webseiten_werden_nicht_zweimal_gelesen(tmp_path):
    firmen, adressen = firmen_fuer(2), {"Vor Nach0": "a@f0.de", "Vor Nach1": "b@f1.de"}
    impressum = impressum_fuer(2)
    lauf_ausfuehren(firmen, KUNDE, ZaehlendesDropcontact(adressen), impressum,
                    FakeHunter(), arbeiter=2, lauf_dir=str(tmp_path),
                    fortschritt=lambda _: None)
    assert sorted(impressum.gelesen) == ["f0.de", "f1.de"]

    zweites = impressum_fuer(2)
    lauf_ausfuehren(firmen, KUNDE, ZaehlendesDropcontact(adressen), zweites,
                    FakeHunter(), arbeiter=2, lauf_dir=str(tmp_path),
                    fortschritt=lambda _: None)

    assert zweites.gelesen == []                    # alles aus dem Zwischenstand


def test_bekannte_adresse_wird_nicht_noch_einmal_bezahlt(tmp_path):
    firmen, adressen = firmen_fuer(2), {"Vor Nach0": "a@f0.de", "Vor Nach1": "b@f1.de"}
    lauf_ausfuehren(firmen, KUNDE, ZaehlendesDropcontact(adressen), impressum_fuer(2),
                    FakeHunter(), arbeiter=2, lauf_dir=str(tmp_path),
                    fortschritt=lambda _: None)

    zweites = ZaehlendesDropcontact(adressen)
    ergebnisse = lauf_ausfuehren(firmen, KUNDE, zweites, impressum_fuer(2),
                                 FakeHunter(), arbeiter=2, lauf_dir=str(tmp_path),
                                 fortschritt=lambda _: None)

    assert zweites.abgegeben == []
    assert [e["leads"][0]["email"] for e in ergebnisse] == ["a@f0.de", "b@f1.de"]


def test_gerettete_zeilen_ersparen_die_neue_abfrage(tmp_path):
    # Genau der Handgriff vom 11.08.: die Zeilen eines bezahlten Batches
    # liegen vor und muessen den Lauf entlasten statt neu gekauft zu werden.
    stand = Zwischenstand(str(tmp_path))
    uebernommen = stand.zeilen_uebernehmen([
        {"first_name": "Vor", "last_name": "Nach0", "website": "www.f0.de",
         "email": [{"email": "a@f0.de", "qualification": "nominative@pro"}]}])
    stand.speichern()
    assert uebernommen == 1

    dropcontact = ZaehlendesDropcontact({"Vor Nach1": "b@f1.de"})
    ergebnisse = lauf_ausfuehren(firmen_fuer(2), KUNDE, dropcontact,
                                 impressum_fuer(2), FakeHunter(), arbeiter=2,
                                 lauf_dir=str(tmp_path), fortschritt=lambda _: None)

    assert dropcontact.abgegeben == [["Vor Nach1"]]     # Nach0 nicht neu gekauft
    assert [e["leads"][0]["email"] for e in ergebnisse] == ["a@f0.de", "b@f1.de"]
