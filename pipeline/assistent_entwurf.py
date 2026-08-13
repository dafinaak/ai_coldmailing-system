"""The half-filled state of the campaign wizard.

The wizard has six steps and the middle one waits minutes for data.
Nobody should lose what they typed because a browser tab closed, a
laptop slept, or the server restarted - so every step writes what it
knows to disk the moment it is submitted, and the wizard is picked up
again from there.

One file per draft under <daten_dir>/entwuerfe/. Written atomically: a
half-written draft that a crash left behind would be worse than none,
because it looks complete.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path

ORDNER = "entwuerfe"
SCHRITTE = 6


def _ordner(daten_dir) -> Path:
    ordner = Path(daten_dir) / ORDNER
    ordner.mkdir(parents=True, exist_ok=True)
    return ordner


def _pfad(daten_dir, kennung: str) -> Path:
    sauber = re.sub(r"[^0-9A-Za-z_-]", "", str(kennung or ""))
    if not sauber:
        raise ValueError("Ungültige Entwurfs-Kennung.")
    return _ordner(daten_dir) / f"{sauber}.json"


def neue_kennung(jetzt: datetime | None = None) -> str:
    return (jetzt or datetime.now()).strftime("%Y%m%d-%H%M%S")


def anlegen(daten_dir, kennung: str | None = None) -> dict:
    """Start a fresh draft and write it straight away."""
    entwurf = {
        "kennung": kennung or neue_kennung(),
        "angelegt": datetime.now().isoformat(timespec="seconds"),
        "schritt": 1,
        "hoechster_schritt": 1,
        "daten": {},
    }
    speichern(daten_dir, entwurf)
    return entwurf


def laden(daten_dir, kennung: str) -> dict | None:
    pfad = _pfad(daten_dir, kennung)
    if not pfad.exists():
        return None
    try:
        return json.loads(pfad.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        # A draft nobody can read is treated as gone rather than as an
        # error page - the wizard then offers a fresh start.
        return None


def speichern(daten_dir, entwurf: dict) -> Path:
    """Write the draft so that it is either fully old or fully new."""
    pfad = _pfad(daten_dir, entwurf["kennung"])
    vorlaeufig = pfad.with_suffix(".json.tmp")
    entwurf["geaendert"] = datetime.now().isoformat(timespec="seconds")
    vorlaeufig.write_text(
        json.dumps(entwurf, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(vorlaeufig, pfad)
    return pfad


def schritt_speichern(daten_dir, kennung: str, schritt: int,
                      werte: dict) -> dict:
    """Store one step's values and remember how far the wizard got."""
    if not 1 <= int(schritt) <= SCHRITTE:
        raise ValueError(f"Schritt {schritt} gibt es nicht (1 bis {SCHRITTE}).")
    entwurf = laden(daten_dir, kennung)
    if entwurf is None:
        raise FileNotFoundError(
            f"Der Entwurf '{kennung}' wurde nicht gefunden. Vermutlich wurde "
            f"er gelöscht - bitte den Assistenten neu starten.")
    entwurf["daten"].update(werte or {})
    entwurf["schritt"] = int(schritt)
    entwurf["hoechster_schritt"] = max(
        entwurf.get("hoechster_schritt", 1), int(schritt))
    speichern(daten_dir, entwurf)
    return entwurf


def alle(daten_dir) -> list:
    """All drafts, newest first - for 'continue where you left off'."""
    entwuerfe = []
    for pfad in _ordner(daten_dir).glob("*.json"):
        entwurf = laden(daten_dir, pfad.stem)
        if entwurf:
            entwuerfe.append(entwurf)
    return sorted(entwuerfe, key=lambda e: e.get("angelegt", ""), reverse=True)


def loeschen(daten_dir, kennung: str) -> bool:
    pfad = _pfad(daten_dir, kennung)
    if not pfad.exists():
        return False
    pfad.unlink()
    return True
