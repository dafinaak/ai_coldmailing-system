from dataclasses import dataclass, field
from pathlib import Path
import yaml

PFLICHTFELDER = ["name", "zielgruppe", "angebot", "tonalitaet",
                 "absender", "follow_up_tage", "test_empfaenger"]

@dataclass
class Kunde:
    name: str
    zielgruppe: dict
    angebot: str
    tonalitaet: str
    absender: str
    follow_up_tage: list
    test_empfaenger: list
    sperrliste: list = field(default_factory=list)  # Domains, nie anschreiben
    webseite: str = ""  # Firmen-Webseite, Basis fuer die Angebots-Ableitung im Web-Interface

def load_kunde(path) -> Kunde:
    with open(path, encoding="utf-8") as f:
        daten = yaml.safe_load(f) or {}
    fehlend = [k for k in PFLICHTFELDER if k not in daten]
    if fehlend:
        raise ValueError(f"Pflichtfelder fehlen in {path}: {', '.join(fehlend)}")

    tage = daten["follow_up_tage"]
    if (not isinstance(tage, list) or len(tage) < 2
            or not all(isinstance(t, (int, float)) and not isinstance(t, bool) for t in tage)):
        raise ValueError(
            f"follow_up_tage in {path} muss eine Liste aus mindestens zwei Zahlen sein "
            f"(z.B. [3, 7]), gefunden: {tage!r}")
    if not all(tage[i] < tage[i + 1] for i in range(len(tage) - 1)):
        raise ValueError(
            f"follow_up_tage in {path} muss aufsteigend sortiert sein, jeder Tag also "
            f"spaeter als der vorherige (z.B. [3, 7], nicht [7, 3] oder [3, 3]) - "
            f"gefunden: {tage!r}. Grund: Instantly zaehlt den Abstand jeweils zum "
            f"vorherigen Schritt, aus [a, b] wird also 'Follow-up 1 nach a Tagen, "
            f"Follow-up 2 nach (b - a) weiteren Tagen'.")

    empfaenger = daten["test_empfaenger"]
    if (not isinstance(empfaenger, list) or not empfaenger
            or not all(isinstance(e, str) for e in empfaenger)):
        raise ValueError(
            f"test_empfaenger in {path} muss eine nicht-leere Liste aus E-Mail-Adressen "
            f"(Strings) sein, gefunden: {empfaenger!r}")

    if "sperrliste" in daten and daten["sperrliste"] is not None:
        if not isinstance(daten["sperrliste"], list):
            raise ValueError(
                f"sperrliste in {path} muss, wenn vorhanden, eine Liste sein, "
                f"gefunden: {daten['sperrliste']!r}")

    return Kunde(**{k: daten[k] for k in PFLICHTFELDER},
                 sperrliste=daten.get("sperrliste") or [],
                 webseite=daten.get("webseite") or "")

def lade_globale_sperrliste(daten_dir) -> list:
    """Liest sperrliste-global.yaml aus daten_dir: eine einfache Liste aus
    Domains (Wildcards wie *.bund.de erlaubt, siehe pipeline.dedupe), die
    fuer ALLE Kunden zusaetzlich zu deren eigener sperrliste gilt. Fehlt die
    Datei, gibt es (noch) keine globalen Sperren - das ist kein Fehler."""
    pfad = Path(daten_dir) / "sperrliste-global.yaml"
    if not pfad.exists():
        return []
    inhalt = yaml.safe_load(pfad.read_text(encoding="utf-8")) or []
    if not isinstance(inhalt, list):
        raise ValueError(
            f"sperrliste-global.yaml in {pfad} ist falsch aufgebaut: erwartet wird eine "
            f"einfache Liste von Domains (z.B. '- konkurrent-ki.de'), gefunden wurde "
            f"stattdessen: {type(inhalt).__name__}.")
    return inhalt
