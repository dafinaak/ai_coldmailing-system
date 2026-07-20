"""Aggregation fuer den Kontakte-Bereich (Task 8): eine rein lesende Sicht
auf ALLE Personen, die je in irgendeinem Laufordner irgendeines Kunden
gefunden wurden - ueber leads.json (Name/Firma/E-Mail), pruefung_ok.json
(welche Texte die Pruefung bestanden haben) und versand_komplett.json
(ob der Lauf tatsaechlich an Instantly uebergeben wurde) hinweg.

Eigenes Leaf-Modul (wie web.wartende/web.laufmanager): haengt nur von der
Pipeline und web.wartende.kunde_fuer ab, nie von web.nav oder einem
web.routen.*-Modul - web.routen.kontakte importiert von hier, ein
umgekehrter Import waere ein Zirkel.

Zwei bewusste Design-Entscheidungen (aus dem Task-Auftrag, hier
dokumentiert statt irgendwo im Code versteckt):

1. "Versanddatum" fuer angeschriebene Kontakte: der Zeitpunkt aus
   FREIGABE.txt (ueber pipeline.approval.freigabe_info, dieselbe Quelle,
   die web.routen.kampagnen fuer 'Freigegeben am' benutzt) - NICHT die
   mtime von versand_komplett.json. Grund: freigabe_info() ist bereits die
   im Rest der App etablierte Quelle fuer "wann ist hier etwas passiert"
   (siehe kampagne_detail.html/kampagnen_liste.html); eine Datei-mtime
   waere eine zweite, leicht abweichende Zeitquelle UND unzuverlaessig
   sobald daten/ einmal kopiert/synchronisiert wird (siehe Deployment-Task
   10: rsync/Backup veraendert mtimes, der Freigabe-Zeitstempel im Datei-
   inhalt bleibt dagegen stabil).
2. "Neuester Eintrag gewinnt" beim Dedupe per E-Mail: gemessen am Lauf-
   Zeitstempel (Ordnername, Format %Y%m%d-%H%M%S aus pipeline.run_store) -
   diese Zahl ist fuer JEDEN Lauf vorhanden (RunStore legt den Ordner
   danach benannt an) und global chronologisch vergleichbar, auch ueber
   Kunden hinweg. Dieselbe Zahl ist auch der Sortier-Schluessel fuer die
   Endliste (neuester Lauf zuerst).
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from pipeline.approval import freigabe_info
from pipeline.run_store import RunStore
from web.wartende import format_deutsches_datum, kunde_fuer


def _leads_eintraege(daten) -> list:
    """Tolerant wie pipeline.dedupe._bekannte_emails: leads.json ist seit
    der 'ohne_email'-Zaehlung ein Objekt {"leads": [...], "ohne_email": n};
    alte Laeufe koennen noch die reine Listenform auf der Platte haben."""
    return daten["leads"] if isinstance(daten, dict) else daten


def _kampagne_label(kunde_name: str, ts: str) -> str:
    """Lokales Label fuer die Spalte KAMPAGNE/AUFTRAG - bewusst ohne
    Instantly-Aufruf (dieses Modul ist Dateisystem-only, siehe Modul-
    Kommentar), deshalb kein echter Kampagnen-Name aus Instantly, sondern
    Kunde + Zeitpunkt des Laufs (fuer Menschen lesbar formatiert, faellt
    bei unerwartetem Ordnernamen ehrlich auf den Rohwert zurueck)."""
    try:
        zeitpunkt = datetime.strptime(ts, "%Y%m%d-%H%M%S")
        formatiert = zeitpunkt.strftime("%d.%m.%Y, %H:%M")
    except ValueError:
        formatiert = ts
    return f"{kunde_name} – {formatiert}"


def _kontakte_aus_lauf(daten_dir, kunden_ordner: Path, lauf_dir: Path,
                        email_zu_eintrag: dict) -> None:
    leads_pfad = lauf_dir / "leads.json"
    if not leads_pfad.exists():
        return  # Lauf noch nicht bis Schritt 1 fertig - keine Kontakte hier

    daten = json.loads(leads_pfad.read_text(encoding="utf-8"))
    eintraege = _leads_eintraege(daten)

    try:
        kunde_name = kunde_fuer(daten_dir, lauf_dir).name
    except (OSError, ValueError, KeyError):
        kunde_name = kunden_ordner.name

    ts = lauf_dir.name
    kampagne = _kampagne_label(kunde_name, ts)

    pruefung_ok_emails: set = set()
    pruefung_pfad = lauf_dir / "pruefung_ok.json"
    if pruefung_pfad.exists():
        pruefung_daten = json.loads(pruefung_pfad.read_text(encoding="utf-8"))
        pruefung_ok_emails = {e["email"].strip().lower() for e in pruefung_daten}

    versand_komplett = (lauf_dir / "versand_komplett.json").exists()
    zuletzt_angeschrieben = None
    if versand_komplett:
        store = RunStore.resume(lauf_dir)
        am = format_deutsches_datum(freigabe_info(store)["am"]) or "unbekanntem Zeitpunkt"
        zuletzt_angeschrieben = f"angeschrieben am {am}"

    for eintrag in eintraege:
        email = (eintrag.get("email") or "").strip().lower()
        if not email:
            continue
        angeschrieben = versand_komplett and email in pruefung_ok_emails
        zuletzt = zuletzt_angeschrieben if angeschrieben else "nur gefunden, nie angeschrieben"
        name = f"{eintrag.get('first_name', '').strip()} {eintrag.get('last_name', '').strip()}".strip()
        kontakt = {
            "name": name,
            "firma": eintrag.get("company", ""),
            "email": email,
            "kunde": kunde_name,
            "kampagne": kampagne,
            "zuletzt": zuletzt,
            "_ts": ts,
        }
        bisher = email_zu_eintrag.get(email)
        if bisher is None or ts >= bisher["_ts"]:
            email_zu_eintrag[email] = kontakt


def sammle_kontakte(daten_dir) -> list[dict]:
    """Aggregiert alle Kontakte aus allen Laeufen aller Kunden. Kaputte
    oder unvollstaendige Laufordner (fehlerhaftes JSON etc.) werden einzeln
    uebersprungen statt die ganze Seite abstuerzen zu lassen - andere,
    intakte Laeufe erscheinen trotzdem."""
    daten_dir = Path(daten_dir)
    laeufe_wurzel = daten_dir / "laeufe"
    if not laeufe_wurzel.is_dir():
        return []

    email_zu_eintrag: dict = {}
    for kunden_ordner in sorted(p for p in laeufe_wurzel.iterdir() if p.is_dir()):
        for lauf_dir in sorted(p for p in kunden_ordner.iterdir() if p.is_dir()):
            try:
                _kontakte_aus_lauf(daten_dir, kunden_ordner, lauf_dir, email_zu_eintrag)
            except (OSError, ValueError, KeyError, TypeError):
                continue  # kaputter/unvollstaendiger Laufordner - ueberspringen

    kontakte = sorted(email_zu_eintrag.values(), key=lambda e: e["_ts"], reverse=True)
    for kontakt in kontakte:
        del kontakt["_ts"]
    return kontakte
