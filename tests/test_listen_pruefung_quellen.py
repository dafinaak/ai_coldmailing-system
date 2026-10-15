"""Die Listen-Pruefung muss die Listen finden, die es wirklich gibt.

Gefunden am 07.10.2026: Dafina wollte pro Postleitzahl-Dekade nur noch
EINE Sammelliste behalten, also wurden die Einzel-Listen je Zone
geloescht. Die Pruefung sucht aber ausschliesslich nach

    IT-Liste-Emails-Zona<NN>-FERTIG-*.xlsx

und meldete danach seelenruhig "0 Gjetje ne 0 rreshta" - sie hatte
schlicht nichts zu pruefen gefunden. Das ist die gefaehrlichste Form
des Fehlers: das Tor zur Qualitaet stand offen und sagte "alles in
Ordnung".

Zwei Regeln kommen daher hier dazu:
  - gibt es keine Einzel-Listen, werden die Sammellisten je Dekade
    gelesen (pro Dekade die neueste);
  - findet die Pruefung ueberhaupt keine Zeile, ist das ein Fehler und
    kein stilles Gruen.
"""
import importlib.util
from pathlib import Path

import openpyxl
import pytest

PROJEKT = Path(__file__).resolve().parent.parent


def _werkzeug(projekt: Path):
    pfad = PROJEKT / "werkzeuge" / "listen-pruefung.py"
    spec = importlib.util.spec_from_file_location("listen_pruefung", pfad)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    modul.PROJEKT = projekt
    return modul


def _liste(pfad: Path, zeilen=1):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Nr", "Firma", "Person", "Position", "E-Mail", "Anrede",
               "Hinweis", "Telefon (Person)", "Telefon (Firma)", "Webseite",
               "PLZ", "Ort"])
    for i in range(zeilen):
        ws.append([i + 1, "Firma GmbH", "Anna Alt", "", "a@firma.de",
                   "Frau Alt", "", "", "", "https://firma.de", "40210",
                   "Düsseldorf"])
    wb.save(pfad)


def test_einzel_listen_werden_weiter_gefunden(tmp_path):
    """Der alte Weg darf nicht kaputtgehen."""
    _liste(tmp_path / "IT-Liste-Emails-Zona40-FERTIG-20261007-1000.xlsx")
    modul = _werkzeug(tmp_path)
    assert list(modul.listat_e_fundit()) == ["40"]


def test_ohne_einzel_listen_werden_die_sammellisten_gelesen(tmp_path):
    """Der Fall vom 07.10.2026: nur noch eine Liste je Dekade."""
    _liste(tmp_path / "IT-Liste-Emails-Zonat-40-49-20261007-1000.xlsx", 3)
    _liste(tmp_path / "IT-Liste-Emails-Zonat-50-59-20261007-1100.xlsx", 2)
    modul = _werkzeug(tmp_path)
    gefunden = modul.listat_e_fundit()
    assert sorted(gefunden) == ["40-49", "50-59"], gefunden


def test_je_dekade_nur_die_neueste_sammelliste(tmp_path):
    _liste(tmp_path / "IT-Liste-Emails-Zonat-40-49-20261001-0900.xlsx")
    neu = tmp_path / "IT-Liste-Emails-Zonat-40-49-20261007-1500.xlsx"
    _liste(neu)
    modul = _werkzeug(tmp_path)
    assert modul.listat_e_fundit() == {"40-49": str(neu)}


def test_einzel_listen_haben_vorrang(tmp_path):
    """Sind beide da, zaehlen die Einzel-Listen - sonst wuerde dieselbe
    Zeile zweimal geprueft und als Dublette gemeldet."""
    _liste(tmp_path / "IT-Liste-Emails-Zona40-FERTIG-20261007-1000.xlsx")
    _liste(tmp_path / "IT-Liste-Emails-Zonat-40-49-20261007-1000.xlsx")
    modul = _werkzeug(tmp_path)
    assert list(modul.listat_e_fundit()) == ["40"]


def test_plz_wird_gegen_die_ganze_dekade_geprueft(tmp_path):
    """Bei einer Sammelliste heisst die "Zone" 40-49, nicht 40.

    Ohne das verglich die Pruefung die Postleitzahl mit dem Text "40-49",
    fand nie einen Treffer und meldete JEDE Zeile als "PLZ jashte zones" -
    am 07.10.2026 waren das 761 falsche Treffer in 761 Zeilen, die die
    72 echten Funde darunter begraben haetten.
    """
    modul = _werkzeug(tmp_path)
    assert modul.plz_passt_zu_zone("40210", "40-49")
    assert modul.plz_passt_zu_zone("49074", "40-49")
    assert not modul.plz_passt_zu_zone("50667", "40-49")
    assert not modul.plz_passt_zu_zone("39104", "40-49")
    # der alte Weg, eine einzelne Zone, muss weiter gelten
    assert modul.plz_passt_zu_zone("40210", "40")
    assert not modul.plz_passt_zu_zone("41061", "40")


def test_gar_keine_liste_ist_ein_fehler(tmp_path):
    """Kein stilles Gruen: findet die Pruefung nichts, muss sie das sagen."""
    modul = _werkzeug(tmp_path)
    with pytest.raises(SystemExit) as fehler:
        modul.main()
    assert "asnje liste" in str(fehler.value).lower()


def test_ein_und_dreistellige_zonen_behalten_ihren_namen(tmp_path):
    """Eine Liste "Zona8" oder "Zona585" muss als Zone "8" bzw. "585"
    gefunden werden.

    Der Suchmuster liess nur zwei Stellen zu, und der Name wurde aus den
    letzten zwei Zeichen gelesen: "Zona585" waere als Zone "85" gezaehlt
    und jede ihrer Postleitzahlen als "ausserhalb der Zone" gemeldet,
    "Zona8" (Muenchen) als "a8". Einstellige Namen gibt es seit dem
    08.10.2026, dreistellige seit dem 30.09.2026 - und die mittelgrossen
    Staedte vom 09.10.2026 bringen 23 weitere.
    """
    werkzeug = _werkzeug(tmp_path)
    for name in ("IT-Liste-Emails-Zona8-FERTIG-20261010-0900.xlsx",
                 "IT-Liste-Emails-Zona58-FERTIG-20261010-0901.xlsx",
                 "IT-Liste-Emails-Zona585-FERTIG-20261010-0902.xlsx"):
        _liste(tmp_path / name)

    assert sorted(werkzeug.listat_e_fundit()) == ["58", "585", "8"]


def test_vierstellige_zonen_behalten_ihren_namen(tmp_path):
    """Auch vier Stellen muessen als Zonenname durchkommen - sonst wird
    "Zona5012" nicht gefunden und ihre Zeilen nie geprueft. Die zweite
    Runde der mittelgrossen Staedte (09.10.2026) braucht fuenf solche
    Namen, weil zwei Staedte sonst denselben Anfang haetten."""
    werkzeug = _werkzeug(tmp_path)
    for name in ("IT-Liste-Emails-Zona5012-FERTIG-20261010-0900.xlsx",
                 "IT-Liste-Emails-Zona4453-FERTIG-20261010-0901.xlsx"):
        _liste(tmp_path / name)

    assert sorted(werkzeug.listat_e_fundit()) == ["4453", "5012"]
