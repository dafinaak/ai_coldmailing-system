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

from datetime import datetime
from pathlib import Path

from pipeline.config import load_kunde
from pipeline.approval import freigabe_info, is_approved
from pipeline.run_store import RunStore
from web.freigabe_status import FreigabeStatusStore, grundtexte_fuer_lauf
from web.laufmanager import Laufmanager, wartet_seit_text


def format_deutsches_datum(iso_text: str | None) -> str | None:
    """Formatiert einen ISO-8601-Zeitstempel (wie ihn pipeline.approval.
    approve() in FREIGABE.txt schreibt, ueber datetime.now().isoformat())
    als deutsches Datum "17.07.2026, 09:33 Uhr" - fuer Laien lesbar statt
    dem rohen "2026-07-17T09:33:00.123456". E-Fix 3 (geteilter Helfer, siehe
    web.routen.kampagnen/web.kontakte). None/leer/nicht parsebar kommt
    UNVERAENDERT zurueck (roh anzeigen ist besser als abzustuerzen oder das
    Feld verschwinden zu lassen)."""
    if not iso_text:
        return iso_text
    try:
        zeitpunkt = datetime.fromisoformat(iso_text)
    except ValueError:
        return iso_text
    return zeitpunkt.strftime("%d.%m.%Y, %H:%M Uhr")


def kunde_fuer(daten_dir, lauf_dir: Path):
    """Laedt den Kunden zu einem Laufordner (ueber kunde_pfad.json). Fix 3
    (Reviewer-Review, Task 7): war bis dahin byte-identisch in
    web.routen.freigabe, web.routen.kampagnen UND hier dupliziert - jetzt
    hier konsolidiert, beide Routen importieren von hier."""
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
                kunde_name = kunde_fuer(daten_dir, lauf_dir).name
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


def pruefbare_laeufe(daten_dir) -> dict[str, list[dict]]:
    """Trennt prüfbare Runden in offene und bereits übergebene Runden."""
    gruppen: dict[str, list[dict]] = {"offen": [], "uebergeben": []}
    manager = Laufmanager(daten_dir)
    laeufe_wurzel = Path(daten_dir) / "laeufe"
    if not laeufe_wurzel.is_dir():
        return gruppen

    kunden_ordner = sorted(
        (p for p in laeufe_wurzel.iterdir() if p.is_dir()), reverse=True
    )
    for kunden_dir in kunden_ordner:
        for lauf_dir in sorted((p for p in kunden_dir.iterdir() if p.is_dir()), reverse=True):
            stand = manager.status(lauf_dir)
            if stand["zustand"] not in {"wartet_auf_freigabe", "freigegeben", "uebergeben"}:
                continue
            warnung = None
            try:
                kunde_name = kunde_fuer(daten_dir, lauf_dir).name
                texte = grundtexte_fuer_lauf(
                    lauf_dir,
                    nacharbeit_einschliessen=stand["zustand"] != "uebergeben",
                )
                store = RunStore.resume(lauf_dir)
                alte_freigabe = freigabe_info(store) if is_approved(store) else None
                status = FreigabeStatusStore(lauf_dir).ansicht(texte, alte_freigabe)
                voll = sum(
                    not e["qa_blocked"]
                    and all(s["approved"] for s in e["steps"].values())
                    for e in status["recipients"]
                )
                nacharbeit = sum(e["qa_blocked"] for e in status["recipients"])
                offen = len(status["recipients"]) - voll - nacharbeit
                empfaenger = len(status["recipients"])
            except (OSError, ValueError, KeyError):
                kunde_name = kunden_dir.name
                empfaenger = voll = offen = nacharbeit = 0
                warnung = "Die Daten dieser E-Mail-Runde sind nicht vollständig lesbar."

            eintrag = {
                "slug": kunden_dir.name,
                "ts": lauf_dir.name,
                "kunde_name": kunde_name,
                "empfaenger": empfaenger,
                "bestaetigt": voll,
                "offen": offen,
                "nacharbeit": nacharbeit,
                "zustand": stand["zustand"],
                "geaendert_text": wartet_seit_text(lauf_dir),
                "warnung": warnung,
            }
            gruppe = "uebergeben" if stand["zustand"] == "uebergeben" else "offen"
            gruppen[gruppe].append(eintrag)
    return gruppen


def _ist_wartend_reine_dateipruefung(lauf_dir: Path) -> bool:
    """Reine Datei-Existenz-Pruefung (kein PID-Check, kein JSON-Parsing) fuer
    den Zustand 'wartet_auf_freigabe' - muss die gleiche Bedeutung wie
    Laufmanager.status() haben (siehe dort: pruefung_ok UND NICHT abgelehnt
    UND NICHT versand_komplett UND NICHT freigegeben -> 'wartet_auf_freigabe'),
    nur OHNE den dortigen Prozess-lebt-Check ('laeuft' gewinnt in
    Laufmanager.status() vor allem anderen). Reviewer-Fix 2 (Task 7): dieser
    Zaehler laeuft auf JEDER Seite mit, ein PID-Check/JSON-Parsing pro
    Laufordner waere hier zu teuer. Bei Drift IMMER Laufmanager.status() als
    Quelle der Wahrheit behandeln und diese Funktion nachziehen."""
    return (
        (lauf_dir / "pruefung_ok.json").exists()
        and not (lauf_dir / "FREIGABE.txt").exists()
        and not (lauf_dir / "abgelehnt.json").exists()
        and not (lauf_dir / "versand_komplett.json").exists()
    )


def wartende_anzahl(daten_dir) -> int:
    """Schlanker Zaehler fuer den Sidebar-Badge (Task 1-Platzhalter, gefuellt
    in Task 7): "truly cheap" (Reviewer-Fix 2) - bewusst OHNE
    Laufmanager.status() (kein PID-Check via os.kill, kein JSON-Parsing der
    Schritt-Dateien), ohne Kunden-Datei-Lesung und ohne jeden Instantly-
    Aufruf - reine Datei-Existenz-Pruefung je Laufordner (siehe
    _ist_wartend_reine_dateipruefung), weil dieser Zaehler auf JEDER Seite
    mitlaeuft (Plan Task 7: 'cheap: filesystem-only count, no Instantly
    calls from the badge')."""
    laeufe_wurzel = Path(daten_dir) / "laeufe"
    if not laeufe_wurzel.is_dir():
        return 0
    anzahl = 0
    for kunden_ordner in laeufe_wurzel.iterdir():
        if not kunden_ordner.is_dir():
            continue
        for lauf_dir in kunden_ordner.iterdir():
            if lauf_dir.is_dir() and _ist_wartend_reine_dateipruefung(lauf_dir):
                anzahl += 1
    return anzahl
