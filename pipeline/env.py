"""Gemeinsames .env-Handling fuer alle CLI-Einstiegspunkte (pipeline.__main__
und pipeline.offer), damit beide dieselbe .env-Datei lesen und bei fehlenden
Pflicht-Variablen dieselbe deutsche Fehlermeldung zeigen."""
import os, sys
from pathlib import Path

def lade_dotenv(pfad: Path = Path(".env")):
    """Liest eine .env-Datei mit einfachen KEY=VALUE-Zeilen ein (keine
    zusaetzliche Abhaengigkeit noetig). Leerzeilen und #-Kommentare werden
    ignoriert. Bereits gesetzte Umgebungsvariablen werden NICHT ueberschrieben
    - eine echte Shell-Variable geht immer vor dem .env-Wert. Werte duerfen
    in einfache oder doppelte Anfuehrungszeichen eingeschlossen sein
    (KEY="abc" -> abc), die dann entfernt werden."""
    pfad = Path(pfad)
    if not pfad.exists():
        return
    for zeile in pfad.read_text(encoding="utf-8").splitlines():
        zeile = zeile.strip()
        if not zeile or zeile.startswith("#") or "=" not in zeile:
            continue
        schluessel, _, wert = zeile.partition("=")
        schluessel, wert = schluessel.strip(), wert.strip()
        if len(wert) >= 2 and wert[0] == wert[-1] and wert[0] in ("'", '"'):
            wert = wert[1:-1]
        if schluessel and schluessel not in os.environ:
            os.environ[schluessel] = wert

def brauche_env(name: str):
    if not os.environ.get(name):
        sys.exit(f"Fehlende Umgebungsvariable: {name}. "
                 f"Bitte in .env eintragen (siehe .env.example).")
