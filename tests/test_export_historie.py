"""Der Export zeigt, was in historie.db steht.

Ohne diesen Schritt waeren die drei Feldgruppen aus Olivers Liste zwar
gespeichert, aber fuer niemanden sichtbar. Ausserdem wird hier geprueft,
dass die Beschraenkung auf A-E nichts stillschweigend verschluckt:
gespeichert bleiben alle Entscheider, exportiert werden fuenf, und wenn
es mehr sind, steht die Zahl daneben.
"""
import json

import openpyxl

from pipeline import historie_db as h
from pipeline.master_db import export_excel


def _firmen(tmp_path, firmen):
    ziel = tmp_path / "laeufe" / "leadquellen" / "lauf1"
    ziel.mkdir(parents=True)
    (ziel / "firmen.json").write_text(json.dumps(firmen, ensure_ascii=False),
                                      encoding="utf-8")


def _leer(wert):
    """openpyxl liest eine leere Zelle als None, nicht als leeren Text."""
    return not (wert or "")


def _blatt(tmp_path):
    pfad = export_excel(str(tmp_path), tmp_path / "export.xlsx")
    blatt = openpyxl.load_workbook(pfad).active
    kopf = [c.value for c in blatt[1]]
    zeilen = [dict(zip(kopf, [c.value for c in r]))
              for r in blatt.iter_rows(min_row=2)]
    return kopf, zeilen


def test_kurzbeschreibung_und_mitarbeiter_stehen_im_export(tmp_path):
    """Beide Spalten gab es im Kopf schon, gefuellt wurden sie nie: die
    eine war im Export fest leer, die andere kam gar nicht erst in die
    Datenbank."""
    _firmen(tmp_path, [{
        "name": "A GmbH", "domain": "a.de",
        "beschreibung": "Betreut die IT von Handwerksbetrieben.",
        "mitarbeiter": "10-19"}])
    _, zeilen = _blatt(tmp_path)
    assert zeilen[0]["Kurzbeschreibung"] == \
        "Betreut die IT von Handwerksbetrieben."
    assert zeilen[0]["Mitarbeiterzahl"] == "10-19"


def test_spalten_sind_da(tmp_path):
    _firmen(tmp_path, [{"name": "A GmbH", "domain": "a.de"}])
    kopf, _ = _blatt(tmp_path)
    for spalte in ("Rausgegeben an (Name, Art, Datum)", "1. Kontakt",
                   "2. Kontakt", "3. Kontakt", "Opt-Out (Datum, Weg)",
                   "Weitere Entscheider"):
        assert spalte in kopf


def test_ohne_historie_bleiben_die_spalten_leer(tmp_path):
    _firmen(tmp_path, [{"name": "A GmbH", "domain": "a.de"}])
    _, zeilen = _blatt(tmp_path)
    assert _leer(zeilen[0]["1. Kontakt"])
    assert _leer(zeilen[0]["Opt-Out (Datum, Weg)"])


def test_kontaktversuche_stehen_in_ihren_spalten(tmp_path):
    _firmen(tmp_path, [{"name": "A GmbH", "domain": "a.de"}])
    h.kontakt_eintragen(tmp_path, kennung="a.de", nummer=1,
                        produkt="IT-Wartung", durch_wen="Oliver",
                        weg="E-Mail", resultat="keine Antwort",
                        datum="2026-08-21", absender_email="oliver@uns.de")
    h.kontakt_eintragen(tmp_path, kennung="a.de", nummer=3,
                        produkt="IT-Wartung", durch_wen="Oliver",
                        weg="Telefon", resultat="Termin", datum="2026-09-01")

    _, zeilen = _blatt(tmp_path)
    assert "keine Antwort" in zeilen[0]["1. Kontakt"]
    assert _leer(zeilen[0]["2. Kontakt"])      # der zweite fand nie statt
    assert "Termin" in zeilen[0]["3. Kontakt"]


def test_uebergabe_und_opt_out_stehen_da(tmp_path):
    _firmen(tmp_path, [{"name": "A GmbH", "domain": "a.de"}])
    h.uebergabe_eintragen(tmp_path, kennung="a.de", name="Max Mueller",
                          art_der_person="ColdCaller", datum="2026-08-28")
    h.opt_out_eintragen(tmp_path, domain="a.de", datum="2026-09-01",
                        weg="E-Mail")

    _, zeilen = _blatt(tmp_path)
    assert "Max Mueller" in zeilen[0]["Rausgegeben an (Name, Art, Datum)"]
    assert "2026-09-01" in zeilen[0]["Opt-Out (Datum, Weg)"]


def test_historie_ueberlebt_den_export_neubau(tmp_path):
    """export_excel() baut master.db neu - die Historie muss danach noch
    in derselben Datei stehen."""
    _firmen(tmp_path, [{"name": "A GmbH", "domain": "a.de"}])
    h.opt_out_eintragen(tmp_path, domain="a.de", datum="2026-09-01",
                        weg="E-Mail")
    _blatt(tmp_path)
    _, zeilen = _blatt(tmp_path)               # zweimal exportiert
    assert "2026-09-01" in zeilen[0]["Opt-Out (Datum, Weg)"]


def test_mehr_als_fuenf_entscheider_werden_gezaehlt(tmp_path):
    """Sieben Personen: fuenf in A-E, und die Zahl der uebrigen daneben -
    nichts verschwindet stillschweigend."""
    _firmen(tmp_path, [{
        "name": "Viele GmbH", "domain": "viele.de",
        "entscheider": [{"name": f"Person {n}", "vorname": "P",
                         "nachname": str(n), "rolle": "Geschäftsführer"}
                        for n in range(7)]}])
    _, zeilen = _blatt(tmp_path)
    assert zeilen[0]["E) Name"]                 # A-E sind gefuellt
    assert zeilen[0]["Weitere Entscheider"] == "2"


def test_genau_fuenf_entscheider_ohne_hinweis(tmp_path):
    _firmen(tmp_path, [{
        "name": "Fuenf GmbH", "domain": "fuenf.de",
        "entscheider": [{"name": f"Person {n}", "vorname": "P",
                         "nachname": str(n), "rolle": "Geschäftsführer"}
                        for n in range(5)]}])
    _, zeilen = _blatt(tmp_path)
    assert _leer(zeilen[0]["Weitere Entscheider"])
