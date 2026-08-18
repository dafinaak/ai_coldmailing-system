"""Eine Firmen-Sammlung im Hintergrund starten und ihren Stand abfragen.

Warum getrennt vom Laufmanager: eine Sammlung gehoert zu keinem Kunden und
zu keiner Kampagne. Sie hat keine Freigabe, keinen Versand und keine
Sperre je Kunde - sie holt nur Firmen fuer einen Umkreis. Den Laufmanager
darum zu erweitern haette seine Sperr-Logik verwickelt, die genau eine
Aufgabe hat: verhindern, dass zwei Kampagnen desselben Kunden gleichzeitig
laufen.

Sammeln kostet Geld (die Apify-Aktoren rechnen pro Lauf ab). Gestartet
wird deshalb nur auf ausdruecklichen Wunsch in Schritt 3 des Formulars.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from web.laufmanager import (_ist_zombie, _subprozess_umgebung,
                              STANDARD_BEFEHL)

# Job-Ordner der Sammlungen. Bewusst neben den Entwuerfen und NICHT unter
# laeufe/: dort liegen Auftraege, und eine Sammlung ist keiner (siehe
# web.laufmanager.ist_laufordner).
ORDNER = "sammlungen"


class SammelFehler(RuntimeError):
    """Die Sammlung konnte nicht gestartet werden."""


def _job_dir(daten_dir, kennung: str) -> Path:
    return Path(daten_dir) / ORDNER / kennung


def starte(daten_dir, kennung: str, ort: str, radius_km: float,
           dienste: list, limit_pro_suche: int = 200, befehl=None) -> Path:
    """Startet 'python -m pipeline sammeln ...' als Unterprozess.

    Der Zielordner wird VORGEGEBEN statt hinterher gesucht: so weiss der
    Aufrufer schon vor dem Start, wo das Ergebnis landet, auch wenn der
    Prozess abstuerzt.
    """
    if not ort or not str(ort).strip():
        raise SammelFehler("Ohne Ort kann nicht gesammelt werden.")
    if not dienste:
        raise SammelFehler("Ohne Suchbegriffe kann nicht gesammelt werden.")

    daten_dir = Path(daten_dir)
    job = _job_dir(daten_dir, kennung)
    job.mkdir(parents=True, exist_ok=True)
    ziel_ordner = f"sammlung-{kennung}"

    argv = list(befehl or STANDARD_BEFEHL) + ["sammeln", str(ort),
                           "--radius", str(radius_km),
                           "--limit", str(limit_pro_suche),
                           "--ordner", ziel_ordner]
    for dienst in dienste:
        argv += ["--dienst", str(dienst)]

    (job / "meta.json").write_text(json.dumps({
        "ort": ort, "radius_km": radius_km, "dienste": list(dienste),
        "ziel_ordner": ziel_ordner}, ensure_ascii=False), encoding="utf-8")

    log = (job / "lauf.log").open("wb")
    try:
        prozess = subprocess.Popen(
            argv, cwd=str(daten_dir), stdout=log, stderr=subprocess.STDOUT,
            env=_subprozess_umgebung())
    except Exception as fehler:      # noqa: BLE001
        log.close()
        raise SammelFehler(f"Die Sammlung konnte nicht starten: {fehler}")
    finally:
        log.close()

    (job / "pid").write_text(str(prozess.pid), encoding="utf-8")
    return job


def status(daten_dir, kennung: str) -> dict:
    """{"zustand", "firmen", "ziel_ordner", "meldung"}.

    zustand ist "laeuft", "fertig", "fehler" oder "unbekannt". "fertig"
    heisst: die Zieldatei liegt da - das ist der einzige Beweis, dem wir
    trauen. Ein beendeter Prozess allein sagt nichts darueber, ob er auch
    etwas geschafft hat.
    """
    daten_dir = Path(daten_dir)
    job = _job_dir(daten_dir, kennung)
    if not job.is_dir():
        return {"zustand": "unbekannt", "firmen": None, "ziel_ordner": None,
                "meldung": "Zu dieser Sammlung gibt es nichts."}

    meta = _json_oder_leer(job / "meta.json")
    ziel_ordner = meta.get("ziel_ordner") or ""
    ziel = daten_dir / "laeufe" / "leadquellen" / ziel_ordner / "firmen.json"

    if ziel.exists():
        firmen = _json_oder_leer(ziel, standard=[])
        return {"zustand": "fertig", "firmen": len(firmen),
                "ziel_ordner": ziel_ordner,
                "meldung": f"{len(firmen)} Firmen gesammelt."}

    if _laeuft(job):
        return {"zustand": "laeuft", "firmen": None,
                "ziel_ordner": ziel_ordner,
                "meldung": "Die Firmen werden gerade gesammelt."}

    # Kein Ergebnis, kein laufender Prozess: die letzten Zeilen des
    # Protokolls sagen mehr als ein pauschales "Fehler".
    return {"zustand": "fehler", "firmen": None, "ziel_ordner": ziel_ordner,
            "meldung": _letzte_zeilen(job / "lauf.log")
                       or "Die Sammlung ist abgebrochen worden."}


def _laeuft(job: Path) -> bool:
    """Laeuft der Prozess dieser Sammlung noch?

    Bewusst NICHT web.laufmanager._pid_lebt: das fragt zusaetzlich, ob die
    Prozessnummer zu einem KAMPAGNEN-Lauf gehoert - eine Sammlung erkennt
    es damit nie als lebendig und meldete sie sofort als abgebrochen. Jene
    strenge Pruefung schuetzt die Sperre je Kunde vor wiederverwendeten
    Prozessnummern; hier gibt es keine Sperre, und der echte Beweis ist
    ohnehin die Zieldatei.
    """
    try:
        pid = int((job / "pid").read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return False
    try:
        fertig, _ = os.waitpid(pid, os.WNOHANG)
        if fertig == pid:
            return False
    except (ChildProcessError, OSError):
        pass      # nicht unser Kind (Neustart der Oberflaeche) - weiter unten
    try:
        os.kill(pid, 0)
    except (ProcessLookupError, PermissionError, OSError):
        return False
    return not _ist_zombie(pid)


def _json_oder_leer(pfad: Path, standard=None):
    try:
        return json.loads(pfad.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {} if standard is None else standard


def _letzte_zeilen(pfad: Path, anzahl: int = 3) -> str:
    try:
        zeilen = [z.strip() for z in
                  pfad.read_text(encoding="utf-8", errors="replace").splitlines()
                  if z.strip()]
    except OSError:
        return ""
    return " ".join(zeilen[-anzahl:])[:400]
