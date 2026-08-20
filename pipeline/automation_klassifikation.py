"""Pool-Klassifikation: Bietet die Firma selbst Automatisierung an?

Phase 2 (Oliver, 20.08.2026): jede Firma im Bestand bekommt EINMAL das
Automatisierungs-Urteil (webseite + KI, Kriterien in
pipeline.branchen_filter.WETTBEWERBER_SYSTEM):

    yes        bietet selbst Prozess-/KI-Automatisierung als Leistung
    no         normaler IT-Dienstleister
    uncertain  Webseite nicht lesbar oder Befund mehrdeutig - NIE geraten

Das Ergebnis liegt als eigene Datei neben den Sammlungen
(daten/automation-klassifikation.json, je Firma unter ihrer Kennung).
Die Quell-Sammlungen werden NICHT angefasst; die Master-Datenbank und
die Wettbewerber-Pruefung im Kampagnen-Lauf lesen die Datei und sparen
sich damit jeden zweiten KI-Aufruf.

Wiederaufnehmbar: alle 50 Firmen wird gespeichert; ein Abbruch kostet
hoechstens die letzten 50 Urteile. Bereits beurteilte Firmen werden
uebersprungen (mit --neu-pruefen faellt diese Schonung weg).
"""

from __future__ import annotations

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

DATEI = "daten/automation-klassifikation.json"


def _kennung(firma: dict) -> str:
    return (firma.get("domain") or firma.get("name") or "").lower()


def laden(daten_dir=".") -> dict:
    pfad = Path(daten_dir) / DATEI
    if not pfad.exists():
        return {}
    try:
        return json.loads(pfad.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _speichern(daten_dir, stand: dict) -> None:
    pfad = Path(daten_dir) / DATEI
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(json.dumps(stand, ensure_ascii=False, indent=1),
                    encoding="utf-8")


def _bestand(daten_dir) -> list:
    firmen, gesehen = [], set()
    wurzel = Path(daten_dir) / "laeufe" / "leadquellen"
    for pfad in sorted(wurzel.glob("*/firmen.json")) if wurzel.exists() else []:
        try:
            liste = json.loads(pfad.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for firma in liste if isinstance(liste, list) else []:
            kennung = _kennung(firma)
            if kennung and kennung not in gesehen:
                gesehen.add(kennung)
                firmen.append(firma)
    return firmen


def _eintrag(urteil: dict, name: str) -> dict:
    return {
        "name": name,
        "offers_automation_services":
            "uncertain" if urteil.get("unsicher")
            else ("yes" if urteil.get("wettbewerber") else "no"),
        "automation_check_reason": urteil.get("belege", ""),
        "automation_check_source": urteil.get("quelle", "webseite+ki"),
        "automation_checked_at": datetime.now().isoformat(timespec="seconds"),
    }


def klassifizieren(daten_dir=".", ki=None, fetch=None, limit=None,
                   arbeiter=8, neu_pruefen=False, log=print) -> dict:
    """Den ganzen Bestand (oder `limit` Firmen) klassifizieren.

    ki und fetch sind injizierbar (Tests); Standard: der echte
    KI-Baustein und pipeline.website.fetch_text.
    """
    from pipeline.branchen_filter import ist_wettbewerber

    if fetch is None:
        from pipeline.website import fetch_text as fetch
    stand = {} if neu_pruefen else laden(daten_dir)
    offen = [f for f in _bestand(daten_dir)
             if neu_pruefen or _kennung(f) not in stand]
    if limit:
        offen = offen[:limit]
    log(f"Automatisierungs-Klassifikation: {len(offen)} Firmen offen, "
        f"{len(stand)} schon beurteilt.")
    if not offen:
        return stand

    lokal = threading.local()

    def _ki():
        if ki is not None:
            return ki
        eigene = getattr(lokal, "ki", None)
        if eigene is None:
            from pipeline.ki import KI
            eigene = lokal.ki = KI()
        return eigene

    def eine(firma):
        text = ""
        if firma.get("website"):
            try:
                text = fetch(firma["website"], max_zeichen=8000) or ""
            except Exception:      # noqa: BLE001
                text = ""
        if not text.strip():
            # Kein lesbarer Text -> kein Namens-Urteil (Benchmark
            # 20.08.2026): unsicher, gespeichert, keine Kampagne.
            grund = ("keine Webseite hinterlegt" if not firma.get("website")
                     else "Webseite nicht lesbar")
            return _kennung(firma), _eintrag(
                {"unsicher": True, "belege": grund,
                 "quelle": "keine-webseite"}, firma.get("name", ""))
        try:
            urteil = ist_wettbewerber(firma, text, _ki())
        except Exception as fehler:      # noqa: BLE001 - eine kaputte
            # KI-Antwort darf den Pool-Lauf nicht stoppen
            urteil = {"unsicher": True, "belege": f"Fehler: {fehler}"}
        return _kennung(firma), _eintrag(urteil, firma.get("name", ""))

    fertig = 0
    with ThreadPoolExecutor(max_workers=max(1, arbeiter)) as pool:
        for kennung, eintrag in pool.map(eine, offen):
            stand[kennung] = eintrag
            fertig += 1
            if fertig % 50 == 0 or fertig == len(offen):
                _speichern(daten_dir, stand)
                log(f"  beurteilt: {fertig}/{len(offen)}")
    zahlen = {"yes": 0, "no": 0, "uncertain": 0}
    for eintrag in stand.values():
        zahlen[eintrag["offers_automation_services"]] = \
            zahlen.get(eintrag["offers_automation_services"], 0) + 1
    log(f"Stand gesamt: {zahlen['yes']} Anbieter, {zahlen['no']} sauber, "
        f"{zahlen['uncertain']} unsicher -> {Path(daten_dir) / DATEI}")
    return stand
