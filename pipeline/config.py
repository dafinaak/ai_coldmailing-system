from dataclasses import dataclass, field
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
                 sperrliste=daten.get("sperrliste") or [])
