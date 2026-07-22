from pipeline.run_store import RunStore
from pipeline.report import write_report

def test_bericht_enthaelt_alle_zahlen(tmp_path):
    store = RunStore(tmp_path, "Demo")
    write_report(store, {"gefunden": 10, "verworfen": 3, "personalisiert": 6,
                         "nacharbeit": 1, "gruende_verworfen": ["doppelt: 3"],
                         "ohne_email": 4, "firmen_gesamt": 5, "firmen_mit_kontakt": 4,
                         "deckungsquote_prozent": 80.0})
    text = (store.run_dir / "bericht.md").read_text(encoding="utf-8")
    for wert in ("10", "3", "6", "1", "doppelt", "4"):
        assert wert in text

def test_bericht_enthaelt_firmen_ohne_kontakt_zeile(tmp_path):
    store = RunStore(tmp_path, "Demo")
    write_report(store, {"gefunden": 10, "verworfen": 3, "personalisiert": 6,
                         "nacharbeit": 1, "gruende_verworfen": [], "ohne_email": 4,
                         "firmen_gesamt": 5, "firmen_mit_kontakt": 4,
                         "deckungsquote_prozent": 80.0})
    text = (store.run_dir / "bericht.md").read_text(encoding="utf-8")
    assert "Firmen ohne Kontakt: 4" in text

def test_bericht_enthaelt_deckungsquote_zeile(tmp_path):
    # Beispiel aus dem Auftrag: 5 Firmen, 4 mit Kontakt -> 80%.
    store = RunStore(tmp_path, "Demo")
    write_report(store, {"gefunden": 4, "verworfen": 0, "personalisiert": 4,
                         "nacharbeit": 0, "gruende_verworfen": [], "ohne_email": 1,
                         "firmen_gesamt": 5, "firmen_mit_kontakt": 4,
                         "deckungsquote_prozent": 80.0})
    text = (store.run_dir / "bericht.md").read_text(encoding="utf-8")
    assert "Deckungsquote: 4/5 Firmen mit mindestens einem Kontakt (80.0%)" in text

def test_bericht_enthaelt_firmen_ausgang_aufschluesselung(tmp_path):
    # Die "Firmen ohne Kontakt"-Zahl wird nach dem WARUM aufgeschluesselt und -
    # wichtig fuer den Chef-KPI - persoenliche Entscheider von der reinen
    # info@-Rueckfallebene getrennt.
    store = RunStore(tmp_path, "Demo")
    write_report(store, {"gefunden": 10, "verworfen": 0, "personalisiert": 10,
                         "nacharbeit": 0, "gruende_verworfen": [], "ohne_email": 2,
                         "firmen_gesamt": 10, "firmen_mit_kontakt": 8,
                         "deckungsquote_prozent": 80.0,
                         "firmen_mit_entscheider": 6, "firmen_info_fallback": 2,
                         "firmen_keine_webseite": 1, "firmen_kein_entscheider": 1,
                         "firmen_fehler": 0})
    text = (store.run_dir / "bericht.md").read_text(encoding="utf-8")
    assert ("Firmen-Ausgang: 6 mit persönlichem Entscheider, 2 nur über info@, "
            "1 ohne Webseite, 1 kein Entscheider-Treffer, 0 Fehler") in text

def test_bericht_ohne_ausgang_schluessel_bleibt_abwaertskompatibel(tmp_path):
    # Alte Aufrufer (bzw. Tests), die die neuen Ausgang-Schluessel nicht
    # mitgeben, duerfen nicht mit KeyError scheitern - die Zeile faellt dann
    # auf lauter Nullen zurueck.
    store = RunStore(tmp_path, "Demo")
    write_report(store, {"gefunden": 10, "verworfen": 3, "personalisiert": 6,
                         "nacharbeit": 1, "gruende_verworfen": ["doppelt: 3"],
                         "ohne_email": 4, "firmen_gesamt": 5, "firmen_mit_kontakt": 4,
                         "deckungsquote_prozent": 80.0})
    text = (store.run_dir / "bericht.md").read_text(encoding="utf-8")
    assert ("Firmen-Ausgang: 0 mit persönlichem Entscheider, 0 nur über info@, "
            "0 ohne Webseite, 0 kein Entscheider-Treffer, 0 Fehler") in text
