"""Einen fertigen Kampagnentext zur Ansicht an die eigene Adresse schicken.

Warum als eigener Hintergrund-Auftrag und nicht direkt im Web-Request:
Instantly nimmt eine Kampagne an, verschickt aber nicht sofort. Am
18.08.2026 gemessen dauerte es 200 Sekunden vom Aktivieren bis zur Mail.
So lange darf keine Seite blockieren - und die Kampagne darf danach auch
nicht aktiv stehenbleiben, sonst haetten wir genau das, was die
Projektregel verbietet: eine laufende Kampagne, die niemand freigegeben
hat. Der Unterauftrag wartet und pausiert selbst.

Aufbau wie bei web.sammelmanager: Job-Ordner mit Auftrag, Protokoll und
Ergebnis; die Seite fragt nur den Stand ab.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from web.laufmanager import _ist_zombie, _subprozess_umgebung, STANDARD_BEFEHL

ORDNER = "ansichts-proben"


class ProbeFehler(RuntimeError):
    """Die Ansichts-Probe konnte nicht gestartet werden."""


def _job_dir(daten_dir, kennung: str) -> Path:
    return Path(daten_dir) / ORDNER / kennung


def starte(daten_dir, kennung: str, *, absender: str, empfaenger: str,
           betreff: str, text: str, verbotene: tuple = (), befehl=None) -> Path:
    """Startet den Versand einer einzelnen Ansichts-Mail.

    verbotene sind die echten Empfaenger der Kampagne. An sie darf diese
    Probe NICHT gehen - sonst bekaeme eine Firma die Mail, ohne dass die
    Runde je freigegeben wurde.
    """
    absender = str(absender or "").strip()
    empfaenger = str(empfaenger or "").strip()
    if not absender:
        raise ProbeFehler("Ohne Absender-Postfach kann nichts verschickt werden.")
    if "@" not in empfaenger:
        raise ProbeFehler("Bitte eine gültige E-Mail-Adresse angeben.")
    if empfaenger.casefold() in {str(v).strip().casefold() for v in verbotene}:
        raise ProbeFehler(
            "Diese Adresse gehört zu einem echten Empfänger dieser Runde. "
            "Eine Ansichts-Probe geht nur an die eigene Adresse.")
    if not str(text or "").strip():
        raise ProbeFehler("Der Text ist leer - da gibt es nichts anzusehen.")

    daten_dir = Path(daten_dir)
    job = _job_dir(daten_dir, kennung)
    job.mkdir(parents=True, exist_ok=True)
    (job / "auftrag.json").write_text(json.dumps({
        "absender": absender, "empfaenger": empfaenger,
        "betreff": betreff, "text": text}, ensure_ascii=False), encoding="utf-8")

    argv = list(befehl or STANDARD_BEFEHL) + [
        "ansichts-probe", str(job.relative_to(daten_dir))]
    log = (job / "lauf.log").open("wb")
    try:
        prozess = subprocess.Popen(
            argv, cwd=str(daten_dir), stdout=log, stderr=subprocess.STDOUT,
            env=_subprozess_umgebung())
    except Exception as fehler:      # noqa: BLE001
        raise ProbeFehler(f"Der Versand konnte nicht starten: {fehler}")
    finally:
        log.close()
    (job / "pid").write_text(str(prozess.pid), encoding="utf-8")
    return job


def status(daten_dir, kennung: str) -> dict:
    """{"zustand", "meldung"} - "laeuft", "fertig", "fehler" oder None."""
    job = _job_dir(Path(daten_dir), kennung)
    if not job.is_dir():
        return {"zustand": None, "meldung": ""}
    ergebnis = job / "ergebnis.json"
    if ergebnis.exists():
        try:
            daten = json.loads(ergebnis.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            daten = {}
        if daten.get("gesendet"):
            return {"zustand": "fertig",
                    "meldung": f"Zur Ansicht an {daten.get('empfaenger')} "
                               f"geschickt."}
        return {"zustand": "fehler",
                "meldung": daten.get("fehler") or "Der Versand ist gescheitert."}
    if _laeuft(job):
        return {"zustand": "laeuft",
                "meldung": "Die Ansichts-Mail wird verschickt - das dauert "
                           "ein paar Minuten."}
    return {"zustand": "fehler",
            "meldung": _letzte_zeile(job / "lauf.log")
                       or "Der Versand ist abgebrochen worden."}


def _laeuft(job: Path) -> bool:
    try:
        pid = int((job / "pid").read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return False
    try:
        fertig, _ = os.waitpid(pid, os.WNOHANG)
        if fertig == pid:
            return False
    except (ChildProcessError, OSError):
        pass
    try:
        os.kill(pid, 0)
    except (ProcessLookupError, PermissionError, OSError):
        return False
    return not _ist_zombie(pid)


def _letzte_zeile(pfad: Path) -> str:
    try:
        zeilen = [z.strip() for z in
                  pfad.read_text(encoding="utf-8", errors="replace").splitlines()
                  if z.strip()]
    except OSError:
        return ""
    return zeilen[-1][:300] if zeilen else ""
