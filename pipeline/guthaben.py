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
# Jira AP-216: every value ever seen, one line each, only ever appended.
# The latest value alone could not tell what a single run cost.
VERLAUF = "dropcontact-guthaben-verlauf.jsonl"


def _pfad(daten_dir=None) -> Path:
    return Path(daten_dir or ".") / DATEINAME


def verlauf(daten_dir=None) -> list:
    """Every recorded value, oldest first: {"zeit", "credits_left", "request_id"}."""
    try:
        zeilen = (Path(daten_dir or ".") / VERLAUF).read_text(
            encoding="utf-8").splitlines()
    except OSError:
        return []
    eintraege = []
    for zeile in zeilen:
        try:
            eintrag = json.loads(zeile)
        except ValueError:
            continue      # eine halb geschriebene Zeile verdeckt nicht den Rest
        if isinstance(eintrag, dict) and "credits_left" in eintrag:
            eintraege.append(eintrag)
    return eintraege


def verbrauch(request_id, daten_dir=None) -> int | None:
    """Credits the batch `request_id` cost - or None when that cannot be told.

    Dropcontact bills while it works on a batch ("pay on success"), so the
    value seen when a batch is handed over is the balance BEFORE it, and
    the value seen at the next hand-over is the balance after it. The
    difference is what the batch cost. None while no later batch exists,
    and None when the balance went UP in between (credits were bought) -
    an open answer is better than a wrong number.
    """
    eintraege = verlauf(daten_dir)
    for nr, eintrag in enumerate(eintraege):
        if not request_id or eintrag.get("request_id") != request_id:
            continue
        if nr + 1 == len(eintraege):
            return None
        kosten = eintrag["credits_left"] - eintraege[nr + 1]["credits_left"]
        return kosten if kosten >= 0 else None
    return None


def merken(credits_left, daten_dir=None, request_id=None) -> None:
    """Record what the provider just told us. Never raises.

    Called from inside a running job: a failure to write this note must
    not cost a paid batch, so every error is swallowed on purpose.
    """
    try:
        wert = int(credits_left)
    except (TypeError, ValueError):
        return
    jetzt = datetime.now().isoformat(timespec="seconds")
    try:
        pfad = _pfad(daten_dir)
        vorlaeufig = pfad.with_suffix(".json.tmp")
        vorlaeufig.write_text(json.dumps({
            "credits_left": wert,
            "stand": jetzt,
        }, ensure_ascii=False), encoding="utf-8")
        os.replace(vorlaeufig, pfad)
    except OSError:
        pass
    try:
        with open(Path(daten_dir or ".") / VERLAUF, "a", encoding="utf-8") as datei:
            datei.write(json.dumps({"zeit": jetzt, "credits_left": wert,
                                    "request_id": request_id},
                                   ensure_ascii=False) + "\n")
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
