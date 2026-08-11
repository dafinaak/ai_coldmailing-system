"""Read the colour marks Oliver puts on a checked company list.

Oliver does not delete the companies he wants out - he colours their
rows. A CSV export throws those colours away, so this reader needs the
original Excel file (.xlsx).

Two steps, on purpose:

  report  - show which colours exist, how many rows each one covers and
            a few example companies. Nobody has to guess what a colour
            means; we ask Oliver and only then remove anything.

  filter  - write the final list, dropping every row whose colour was
            named as "out".

  streichen - take the companies Oliver marked in one file and remove
            them from a different, newer list of ours. Matching is by
            company name, so it also works when the two lists no longer
            share the same row order or numbering.

  ungesehen - write out the companies of our list that do not appear in
            Oliver's file at all. Those are the ones he never had a
            chance to judge, so they go back to him before any send.

Usage:
    python -m pipeline.oliver_markierungen report <oliver.xlsx>
    python -m pipeline.oliver_markierungen filter <oliver.xlsx> <ziel.xlsx> FARBE [FARBE ...]
    python -m pipeline.oliver_markierungen streichen <oliver.xlsx> FARBE <unsere.xlsx> <ziel.xlsx>
    python -m pipeline.oliver_markierungen ungesehen <oliver.xlsx> <unsere.xlsx> <ziel.xlsx>
"""

from __future__ import annotations

import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

import openpyxl

OHNE_FARBE = {None, "00000000", "FFFFFFFF"}


def zellfarbe(zelle) -> str | None:
    """Return the background colour of a cell, or None if it has none."""
    fuellung = zelle.fill
    if fuellung is None or fuellung.patternType is None:
        return None
    farbe = fuellung.fgColor
    if farbe is None:
        return None
    wert = farbe.rgb if isinstance(farbe.rgb, str) else None
    if wert is None and farbe.theme is not None:
        wert = f"theme-{farbe.theme}-{farbe.tint:.2f}"
    if wert in OHNE_FARBE:
        return None
    return wert


def zeilenfarbe(ws, zeile: int) -> str | None:
    """The colour of a row: the first coloured cell decides."""
    for zelle in ws[zeile]:
        farbe = zellfarbe(zelle)
        if farbe:
            return farbe
    return None


def sammle(ws) -> dict[str | None, list[str]]:
    nach_farbe: dict[str | None, list[str]] = defaultdict(list)
    for zeile in range(2, ws.max_row + 1):
        firma = ws.cell(row=zeile, column=2).value
        if firma is None:
            continue
        nach_farbe[zeilenfarbe(ws, zeile)].append(str(firma))
    return nach_farbe


def report(pfad: Path) -> None:
    wb = openpyxl.load_workbook(pfad)
    for ws in wb.worksheets:
        nach_farbe = sammle(ws)
        gesamt = sum(len(v) for v in nach_farbe.values())
        print(f"\nBlatt \"{ws.title}\" - {gesamt} Firmen")
        if set(nach_farbe) == {None}:
            print("  KEINE Farbmarkierungen gefunden.")
            continue
        for farbe, firmen in sorted(
            nach_farbe.items(), key=lambda p: (p[0] is None, -len(p[1]))
        ):
            name = farbe or "(ohne Farbe)"
            print(f"  {name:24} {len(firmen):4} Firmen")
            for firma in firmen[:5]:
                print(f"       - {firma[:60]}")
            if len(firmen) > 5:
                print(f"       ... und {len(firmen) - 5} weitere")


def filter_raus(pfad: Path, ziel: Path, raus: set[str]) -> None:
    wb = openpyxl.load_workbook(pfad)
    ws = wb.worksheets[0]

    zu_loeschen = [
        zeile
        for zeile in range(2, ws.max_row + 1)
        if ws.cell(row=zeile, column=2).value is not None
        and zeilenfarbe(ws, zeile) in raus
    ]
    vorher = sum(
        1 for z in range(2, ws.max_row + 1) if ws.cell(row=z, column=2).value
    )

    for zeile in reversed(zu_loeschen):
        ws.delete_rows(zeile)

    # Renumber column "Nr" so the final list reads 1..n.
    nummer = 0
    for zeile in range(2, ws.max_row + 1):
        if ws.cell(row=zeile, column=2).value is None:
            continue
        nummer += 1
        ws.cell(row=zeile, column=1, value=nummer)

    wb.save(ziel)
    print(f"vorher: {vorher} | entfernt: {len(zu_loeschen)} | endgueltig: {nummer}")
    print(f"geschrieben: {ziel}")


def _schluessel(name: object) -> str:
    """Company name reduced to something comparable across exports."""
    text = unicodedata.normalize("NFKD", str(name or ""))
    return "".join(z for z in text if z.isprintable()).strip().lower()


def streichen(oliver: Path, farbe: str, unsere: Path, ziel: Path) -> None:
    markiert = {
        _schluessel(f)
        for f in sammle(openpyxl.load_workbook(oliver).worksheets[0])[farbe]
    }

    wb = openpyxl.load_workbook(unsere)
    ws = wb.worksheets[0]

    raus, behalten = [], 0
    for zeile in range(ws.max_row, 1, -1):
        firma = ws.cell(row=zeile, column=2).value
        if firma is None:
            continue
        if _schluessel(firma) in markiert:
            raus.append(str(firma))
            ws.delete_rows(zeile)
        else:
            behalten += 1

    nummer = 0
    for zeile in range(2, ws.max_row + 1):
        if ws.cell(row=zeile, column=2).value is None:
            continue
        nummer += 1
        ws.cell(row=zeile, column=1, value=nummer)

    wb.save(ziel)
    print(f"von Oliver markiert: {len(markiert)}")
    print(f"davon in unserer Liste gefunden und entfernt: {len(raus)}")
    for firma in reversed(raus):
        print(f"     - {firma}")
    print(f"endgueltige Liste: {behalten} Firmen -> {ziel}")


def ungesehen(oliver: Path, unsere: Path, ziel: Path) -> None:
    bekannt = {
        _schluessel(firma)
        for firmen in sammle(openpyxl.load_workbook(oliver).worksheets[0]).values()
        for firma in firmen
    }

    quelle = openpyxl.load_workbook(unsere).worksheets[0]
    kopf = [c.value for c in quelle[1]]

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Von Oliver noch nicht gesehen"
    ws.append(kopf)

    nummer = 0
    for zeile in quelle.iter_rows(min_row=2, values_only=True):
        if zeile[1] is None or _schluessel(zeile[1]) in bekannt:
            continue
        nummer += 1
        ws.append([nummer, *zeile[1:]])

    wb.save(ziel)
    print(f"unserer Liste unbekannt fuer Oliver: {nummer} Firmen -> {ziel}")


if __name__ == "__main__":
    if len(sys.argv) == 5 and sys.argv[1] == "ungesehen":
        ungesehen(Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4]))
    elif len(sys.argv) == 6 and sys.argv[1] == "streichen":
        streichen(Path(sys.argv[2]), sys.argv[3], Path(sys.argv[4]), Path(sys.argv[5]))
    elif len(sys.argv) >= 3 and sys.argv[1] == "report":
        report(Path(sys.argv[2]))
    elif len(sys.argv) >= 5 and sys.argv[1] == "filter":
        filter_raus(Path(sys.argv[2]), Path(sys.argv[3]), set(sys.argv[4:]))
    else:
        raise SystemExit(__doc__)
