"""Ein Befehl von `python -m pipeline` muss die Funktion erreichen, die er meint.

Gefunden am 01.10.2026: jede Kampagne, die im Assistenten auf "Fortsetzen"
gestartet wurde, brach sofort ab mit

    UnboundLocalError: cannot access local variable 'lauf'

Grund: main() ruft in einem Zweig die Modulfunktion lauf() auf, und in
einem GANZ ANDEREN Zweig steht ein lokaler Import

    from pipeline.fullenrich_poc import SEED, bericht_text, lauf

Ein Import innerhalb einer Funktion bindet den Namen lokal, und Python
entscheidet lokal-oder-global beim Kompilieren fuer den GESAMTEN
Funktionskoerper. Damit war `lauf` in main() ueberall lokal - auch an der
Stelle, die die Modulfunktion meinte, und die lief nie.

Der Fehler kam am 24.08.2026 mit "Added fullenrich tool" herein und blieb
fuenf Wochen unbemerkt, weil ihn nur der eine Pfad ausloest und die
Fehlermeldung im Web-Interface als "Problem, das wir nicht genauer
benennen koennen" ankam - das Startprotokoll wird danach geloescht.

Der Test prueft nicht den einen Namen, sondern die Regel: kein Befehl darf
von einer lokalen Zuweisung in main() verdeckt werden.
"""
import ast
from pathlib import Path

import pytest

QUELLE = Path(__file__).resolve().parent.parent / "pipeline" / "__main__.py"


def _main_funktion() -> ast.FunctionDef:
    baum = ast.parse(QUELLE.read_text(encoding="utf-8"))
    for knoten in baum.body:
        if isinstance(knoten, ast.FunctionDef) and knoten.name == "main":
            return knoten
    raise AssertionError("pipeline/__main__.py hat kein main()")


def _modulfunktionen() -> set:
    baum = ast.parse(QUELLE.read_text(encoding="utf-8"))
    return {k.name for k in baum.body
            if isinstance(k, (ast.FunctionDef, ast.AsyncFunctionDef))
            and k.name != "main"}


def _lokale_namen(fn: ast.FunctionDef) -> dict:
    """{name: zeile} fuer alles, was main() selbst bindet - Zuweisungen,
    Importe, for-Schleifen, with-as, except-as."""
    namen = {}
    for knoten in ast.walk(fn):
        if isinstance(knoten, ast.Name) and isinstance(knoten.ctx, ast.Store):
            namen.setdefault(knoten.id, knoten.lineno)
        elif isinstance(knoten, (ast.Import, ast.ImportFrom)):
            for alias in knoten.names:
                namen.setdefault((alias.asname or alias.name).split(".")[0],
                                 knoten.lineno)
    return namen


def test_kein_befehl_wird_von_main_lokal_ueberschattet():
    fn = _main_funktion()
    lokal = _lokale_namen(fn)
    verdeckt = {name: zeile for name, zeile in lokal.items()
                if name in _modulfunktionen()}
    assert not verdeckt, (
        "Diese Modulfunktionen werden in main() lokal ueberschattet und sind "
        f"dort nicht mehr aufrufbar: {verdeckt}. Lokale Importe mit "
        "'as' umbenennen.")


def test_der_befehl_lauf_erreicht_die_modulfunktion():
    """Der konkrete Fall vom 01.10.2026."""
    assert "lauf" not in _lokale_namen(_main_funktion()), (
        "'lauf' ist in main() lokal gebunden - der Kampagnenstart laeuft "
        "dann in einen UnboundLocalError.")


def test_der_wachhund_wuerde_den_alten_fehler_sehen():
    """Der Test selbst muss den Fehler erkennen, nicht nur gruen sein."""
    kaputt = ast.parse(
        "def helfer():\n    pass\n"
        "def main():\n"
        "    helfer()\n"
        "    from woanders import helfer\n")
    fn = next(k for k in kaputt.body
              if isinstance(k, ast.FunctionDef) and k.name == "main")
    assert "helfer" in _lokale_namen(fn)
