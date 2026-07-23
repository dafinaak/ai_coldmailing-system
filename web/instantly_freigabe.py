"""Konservative Übersetzung des Instantly-Stands für die Freigabetabelle."""
from __future__ import annotations

from datetime import datetime
from typing import Callable


SCHRITT_VON_API = {1: "mail_1", 2: "follow_up_1", 3: "follow_up_2"}
GESENDET_TYPEN = {1, 3}
EMPFANGEN_TYPEN = {2}
LEAD_FEHLER = {-1: "bounced", -2: "unsubscribed", -3: "skipped"}


def hole_alle_seiten(
    abruf: Callable[[str | None], dict], *, max_seiten: int = 100
) -> list[dict]:
    """Liest begrenzt alle Cursor-Seiten und entfernt belegte Duplikate."""
    if max_seiten < 1:
        raise ValueError("Die Seitenobergrenze muss mindestens 1 sein.")
    cursor = None
    bekannte_cursor: set[str] = set()
    bekannte_ids: set[str] = set()
    ergebnis: list[dict] = []

    for _ in range(max_seiten):
        antwort = abruf(cursor)
        if not isinstance(antwort, dict) or not isinstance(antwort.get("items"), list):
            raise RuntimeError("Instantly liefert eine unerwartete Seitenstruktur.")
        for item in antwort["items"]:
            if not isinstance(item, dict):
                raise RuntimeError("Instantly liefert einen ungültigen Listeneintrag.")
            item_id = item.get("id")
            if item_id:
                item_id = str(item_id)
                if item_id in bekannte_ids:
                    continue
                bekannte_ids.add(item_id)
            ergebnis.append(item)

        naechster = antwort.get("next_starting_after")
        if naechster in (None, ""):
            return ergebnis
        naechster = str(naechster)
        if naechster in bekannte_cursor:
            raise RuntimeError("Instantly-Seitenzeiger wiederholt sich.")
        bekannte_cursor.add(naechster)
        cursor = naechster

    raise RuntimeError("Instantly-Seitenobergrenze wurde erreicht.")


def _int_oder_none(wert) -> int | None:
    try:
        return int(wert)
    except (TypeError, ValueError):
        return None


def _schritt_von_api(wert) -> str | None:
    """Versteht alte 1-basierte Werte und das live gelieferte 0_1_0-Format."""
    nummer = _int_oder_none(wert)
    if nummer in SCHRITT_VON_API:
        return SCHRITT_VON_API[nummer]
    if not isinstance(wert, str):
        return None
    teile = wert.strip().split("_")
    if len(teile) != 3 or teile[0] != "0" or not all(t.isdigit() for t in teile):
        return None
    return SCHRITT_VON_API.get(int(teile[1]) + 1)


def _zeit_oder_none(wert) -> tuple[datetime, str] | None:
    if not isinstance(wert, str) or not wert.strip():
        return None
    try:
        geparst = datetime.fromisoformat(wert.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return geparst, wert


def _leerer_empfaenger(*, lead_present: bool) -> dict:
    return {
        "lead_present": lead_present,
        "steps": {
            schritt: {"sent_at": None, "replied": None}
            for schritt in SCHRITT_VON_API.values()
        },
        "overall": {"replied": None, "status": None},
    }


def _reply_count(lead: dict) -> int | None:
    for feld in ("email_reply_count", "reply_count"):
        wert = lead.get(feld)
        if isinstance(wert, int) and not isinstance(wert, bool) and wert >= 0:
            return wert
    return None


def freigabe_anzeige(leads: list[dict], emails: list[dict]) -> dict[str, dict]:
    """Ordnet nur eindeutig belegbare Instantly-Werte Empfängern zu."""
    ergebnis: dict[str, dict] = {}
    email_nach_lead_id: dict[str, str] = {}

    for lead in leads:
        if not isinstance(lead, dict):
            continue
        email = str(lead.get("email") or "").strip().lower()
        if not email:
            continue
        eintrag = ergebnis.setdefault(email, _leerer_empfaenger(lead_present=True))
        eintrag["lead_present"] = True
        lead_id = lead.get("id")
        if lead_id:
            email_nach_lead_id[str(lead_id)] = email
        status = _int_oder_none(lead.get("status"))
        eintrag["overall"]["status"] = LEAD_FEHLER.get(status)
        antworten = _reply_count(lead)
        if antworten is not None:
            eintrag["overall"]["replied"] = antworten > 0

    threads: dict[tuple[str, str], dict[str, list[dict]]] = {}
    versandzeiten: dict[tuple[str, str], tuple[datetime, str]] = {}

    for email_objekt in emails:
        if not isinstance(email_objekt, dict):
            continue
        lead_wert = email_objekt.get("lead")
        email = lead_wert.strip().lower() if isinstance(lead_wert, str) else ""
        if not email and email_objekt.get("lead_id") is not None:
            email = email_nach_lead_id.get(str(email_objekt["lead_id"]), "")
        if not email:
            continue
        eintrag = ergebnis.setdefault(email, _leerer_empfaenger(lead_present=False))

        typ = _int_oder_none(email_objekt.get("ue_type"))
        schritt = _schritt_von_api(email_objekt.get("step"))
        zeit = _zeit_oder_none(email_objekt.get("timestamp_email"))
        if typ in GESENDET_TYPEN and schritt and zeit:
            key = (email, schritt)
            if key not in versandzeiten or zeit[0] < versandzeiten[key][0]:
                versandzeiten[key] = zeit
                eintrag["steps"][schritt]["sent_at"] = zeit[1]

        thread_id = email_objekt.get("thread_id")
        if thread_id:
            thread = threads.setdefault((email, str(thread_id)), {"out": [], "in": []})
            if typ in GESENDET_TYPEN:
                thread["out"].append({"step": schritt})
            elif typ in EMPFANGEN_TYPEN:
                thread["in"].append(email_objekt)
        if typ in EMPFANGEN_TYPEN:
            eintrag["overall"]["replied"] = True

    for (email, _thread_id), thread in threads.items():
        if not thread["in"] or len(thread["out"]) != 1:
            continue
        schritt = thread["out"][0]["step"]
        if schritt:
            ergebnis[email]["steps"][schritt]["replied"] = True

    return ergebnis
