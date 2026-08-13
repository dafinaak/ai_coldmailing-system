"""Der zuletzt gesehene Dropcontact-Guthabenstand.

Dropcontact nennt bei jeder angenommenen Anfrage mit, wie viele Credits
noch uebrig sind ("credits_left"). Genau daraus besteht dieser Baustein:
den Wert festhalten, wenn er vorbeikommt, und ihn spaeter anzeigen
koennen. Es gibt hier bewusst KEINE eigene Abfrage beim Anbieter - eine
Zahl, die wir nicht wirklich gesehen haben, waere geraten.

Deshalb wird der Stand immer MIT seinem Zeitpunkt gezeigt: "187 Credits,
Stand 12.08. 16:20" ist ehrlich, "187 Credits" waere es nicht - zwischen
dem Ablesen und dem Anschauen kann ein ganzer Lauf liegen.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

DATEINAME = "dropcontact-guthaben.json"


def _pfad(daten_dir=None) -> Path:
    return Path(daten_dir or ".") / DATEINAME


def merken(credits_left, daten_dir=None) -> None:
    """Record what the provider just told us. Never raises.

    Called from inside a running job: a failure to write this note must
    not cost a paid batch, so every error is swallowed on purpose.
    """
    try:
        wert = int(credits_left)
    except (TypeError, ValueError):
        return
    try:
        pfad = _pfad(daten_dir)
        vorlaeufig = pfad.with_suffix(".json.tmp")
        vorlaeufig.write_text(json.dumps({
            "credits_left": wert,
            "stand": datetime.now().isoformat(timespec="seconds"),
        }, ensure_ascii=False), encoding="utf-8")
        os.replace(vorlaeufig, pfad)
    except OSError:
        pass


def stand(daten_dir=None) -> dict | None:
    """{"credits_left", "stand", "stand_text"} or None if never seen."""
    pfad = _pfad(daten_dir)
    if not pfad.exists():
        return None
    try:
        daten = json.loads(pfad.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if "credits_left" not in daten:
        return None
    daten["stand_text"] = _lesbar(daten.get("stand"))
    return daten


def _lesbar(zeitpunkt: str | None) -> str:
    try:
        return datetime.fromisoformat(str(zeitpunkt)).strftime("%d.%m.%Y, %H:%M")
    except (TypeError, ValueError):
        return "unbekannt"
