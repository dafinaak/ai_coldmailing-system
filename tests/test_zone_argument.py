"""Ein Zonen-Argument ohne `--zone=` darf nicht still Zone 32 bedeuten
(09.10.2026).

Beide Werkzeuge lesen die Zone nur aus `--zone=NN` und stehen sonst auf
`ZONE = "32"`. Wer `werkzeuge/zona32-dropcontact.py 417` aufruft, meint
Zone 417, bekommt aber Zone 32 - ohne ein Wort.

Genau das ist am 09.10.2026 passiert: der Ablauf fuer die 25
mittelgrossen Staedte rief beide Werkzeuge 25- bzw. 50-mal mit einem
nackten Argument auf, jeder Lauf war Zone 32 (Herford), und 21
Dropcontact-Credits gingen fuer eine Zone weg, die seit August fertig
war. Die Listen der neuen Staedte entstanden gar nicht.

Ein nacktes Argument ist immer ein Irrtum: die Werkzeuge nehmen sonst
nur Schalter, die mit `--` beginnen. Also laut abbrechen.
"""
import importlib.util
import sys
from pathlib import Path

import pytest

PROJEKT = Path(__file__).resolve().parent.parent
WERKZEUGE = ("zona32-dropcontact.py", "zona32-itliste-final.py")


def _laden(name, argv):
    pfad = PROJEKT / "werkzeuge" / name
    spec = importlib.util.spec_from_file_location("w_" + name, pfad)
    modul = importlib.util.module_from_spec(spec)
    alt = sys.argv
    sys.argv = ["werkzeug"] + list(argv)
    try:
        spec.loader.exec_module(modul)
    finally:
        sys.argv = alt
    return modul


@pytest.mark.parametrize("name", WERKZEUGE)
def test_nacktes_argument_stoppt_laut(name):
    with pytest.raises(SystemExit) as fehler:
        _laden(name, ["417"])
    assert "--zone=" in str(fehler.value), str(fehler.value)
    assert "417" in str(fehler.value)


@pytest.mark.parametrize("name", WERKZEUGE)
def test_unbekannte_zone_stoppt_auch(name):
    with pytest.raises(SystemExit) as fehler:
        _laden(name, ["--zone=999"])
    assert "999" in str(fehler.value)


@pytest.mark.parametrize("name", WERKZEUGE)
def test_pytest_argumente_stoppen_die_werkzeuge_nicht(name):
    """Die Werkzeuge werden auch IN Tests geladen, und dort steht in
    `sys.argv` der Aufruf von pytest.

    Am 09.10.2026 hat die erste Fassung dieser Sperre jedes Argument ohne
    `--` abgelehnt - also auch "-q" und jeden Testpfad. Zehn Tests, die
    `zona32-itliste-final.py` laden, fielen damit um. Nur reine Ziffern
    sind eine verlorene Zone.
    """
    modul = _laden(name, ["-q", "tests/test_itliste_zonen_dublikate.py::test_x",
                          "--maxfail=1"])
    assert modul.ZONE == "32"
