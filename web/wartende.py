"""Gemeinsame Logik fuer Laeufe im Zustand "wartet_auf_freigabe" - genutzt
von web.routen.freigabe (die volle Liste mit Name/Wartezeit fuer die
Prüfen&Freigeben-Seite), web.routen.dashboard (dieselbe Liste fuer den
Dashboard-Abschnitt "WARTET AUF DEINE FREIGABE", Task 7) UND web.nav (der
schlanke Zaehler fuer den Sidebar-Badge, der auf JEDER Seite mitlaeuft).

Eigenes Leaf-Modul (statt in web.routen.freigabe, wo die volle Liste vorher
lebte): web.nav wird von so gut wie jedem web.routen.*-Modul importiert
(fuer nav_kontext) - wuerde web.nav umgekehrt aus einem Routen-Modul
importieren, gaebe es einen Zirkel-Import. Dieses Modul haengt selbst nur
von web.laufmanager (ebenfalls ein Leaf-Modul) und der Pipeline ab, nie von
web.nav oder einem web.routen.*-Modul."""
from __future__ import annotations

from pathlib import Path

from pipeline.config import load_kunde
from pipeline.run_store import RunStore
from web.laufmanager import Laufmanager, wartet_seit_text


def _kunde_fuer(daten_dir, lauf_dir: Path):
    store = RunStore.resume(lauf_dir)
    pfad = Path(store.load_step("kunde_pfad")["pfad"])
    if not pfad.is_absolute():
        pfad = Path(daten_dir) / pfad
    return load_kunde(pfad)


def wartende_laeufe(daten_dir) -> list[dict]:
    """Volle Liste der Laeufe im Zustand 'wartet_auf_freigabe' (Kunden-Name,
    Anzahl fertiger/aussortierter Texte, Wartezeit-Text) - Quelle fuer die
    Prüfen&Freigeben-Liste (Task 5) UND das Dashboard (Task 7). Verschoben
    aus web.routen.freigabe._wartende_laeufe (Task 7, siehe Plan-Vorgabe:
    'freigabe routes' waiting-runs logic ... import/refactor it into shared
    use'), Verhalten unveraendert."""
    manager = Laufmanager(daten_dir)
    laeufe_wurzel = Path(daten_dir) / "laeufe"
    eintraege = []
    if not laeufe_wurzel.is_dir():
        return eintraege
    for kunden_ordner in sorted(p for p in laeufe_wurzel.iterdir() if p.is_dir()):
        for lauf_dir in sorted(p for p in kunden_ordner.iterdir() if p.is_dir()):
            stand = manager.status(lauf_dir)
            if stand["zustand"] != "wartet_auf_freigabe":
                continue
            try:
                kunde_name = _kunde_fuer(daten_dir, lauf_dir).name
            except (OSError, ValueError, KeyError):
                kunde_name = kunden_ordner.name
            eintraege.append({
                "slug": kunden_ordner.name,
                "ts": lauf_dir.name,
                "kunde_name": kunde_name,
                "fertig": stand["fertig"],
                "nacharbeit": stand["nacharbeit"],
                "wartet_seit_text": wartet_seit_text(lauf_dir),
            })
    return eintraege


def wartende_anzahl(daten_dir) -> int:
    """Schlanker Zaehler fuer den Sidebar-Badge (Task 1-Platzhalter, gefuellt
    in Task 7): bewusst OHNE Kunden-Datei-Lesung (die braucht wartende_laeufe
    oben nur fuer die Namen) und OHNE jeden Instantly-Aufruf - Dateisystem
    only, siehe Plan Task 7 ('cheap: filesystem-only count, no Instantly
    calls from the badge'), weil dieser Zaehler auf JEDER Seite mitlaeuft."""
    manager = Laufmanager(daten_dir)
    laeufe_wurzel = Path(daten_dir) / "laeufe"
    if not laeufe_wurzel.is_dir():
        return 0
    anzahl = 0
    for kunden_ordner in laeufe_wurzel.iterdir():
        if not kunden_ordner.is_dir():
            continue
        for lauf_dir in kunden_ordner.iterdir():
            if lauf_dir.is_dir() and manager.status(lauf_dir)["zustand"] == "wartet_auf_freigabe":
                anzahl += 1
    return anzahl
