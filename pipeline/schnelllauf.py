"""Same cascade as grosslauf, but built for a whole list at once.

grosslauf walks the list company by company: read the website, ask
Dropcontact for one person, wait up to two minutes for the answer, next
company. Almost all of that time is spent waiting, which is why 317
companies take hours.

This runner keeps every rule of the cascade and only changes WHEN things
are waited for:

  1. The websites are read in parallel - that part is our own work
     (fetch the page, let the AI read the managers off it) and nothing
     about it needs to happen in order.
  2. Dropcontact is asked ONCE for many people instead of once per
     person, using its batch endpoint.

Credits are spent exactly as before. That is why the Dropcontact part
runs in rounds: round one asks only about each company's FIRST manager,
and only companies still without an address ask about their second, and
so on. Sending every manager at once would be simpler and would quietly
multiply the bill for companies whose first name already worked.

Quality gates are untouched: only "nominative@pro" counts as a personal
address, info@ is still verified through Hunter, and an address that
cannot be verified is dropped rather than sent.

Aufruf:
    python -m pipeline.schnelllauf --firmen <firmen.json> --lauf <ordner>
        [--limit N] [--arbeiter 16] [--batch 100]
"""
from __future__ import annotations

import argparse
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from pipeline.config import Kunde
from pipeline.env import lade_dotenv, brauche_env, brauche_env_eines_von
from pipeline.ki import KI
from pipeline.sources.dropcontact import DropcontactSource
from pipeline.sources.hunter import HunterSource
from pipeline.sources.impressum import ImpressumQuelle
from pipeline.decision_maker import build_entscheider, sort_by_priority
from pipeline.sourcing import (INFO_OK_STATUS, _firmenname_saeubern,
                               _impressum_titel)
from pipeline.grosslauf import (
    _schluessel, dubletten_finden, lauf_laden, lauf_speichern, zusammenfassung,
)

TITEL = "Geschäftsführung (laut Impressum)"
ZWISCHENSTAND = "zwischenstand.json"


def _domain(website: str) -> str:
    """Bare domain of a URL - both sides of a comparison get the same form."""
    ohne = re.sub(r"^https?://", "", str(website or "").strip().lower())
    return re.sub(r"^www\.", "", ohne).split("/")[0]


def _adress_schluessel(vorname: str, nachname: str, website: str) -> str:
    return f"{str(vorname).casefold()}|{str(nachname).casefold()}|{_domain(website)}"


class Zwischenstand:
    """Everything a crash must not destroy.

    Two kinds of work are expensive here and neither may be repeated:
    reading the websites costs time and AI calls, and every Dropcontact
    answer costs a credit. So both are written to disk as soon as they
    exist - the page readings, the addresses already paid for, and the
    request_ids of batches that were handed over but not fetched yet.
    A run that dies mid-way picks all of it back up.
    """

    def __init__(self, lauf_dir=None):
        # Ohne Lauf-Ordner (Tests, Einmal-Aufrufe) wird nichts geschrieben -
        # sonst legt jeder Aufruf eine Datei irgendwo im Projekt ab.
        self.pfad = Path(lauf_dir) / ZWISCHENSTAND if lauf_dir else None
        daten = {}
        if self.pfad and self.pfad.exists():
            try:
                daten = json.loads(self.pfad.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                daten = {}
        self.gelesen = daten.get("gelesen") or {}
        self.adressen = daten.get("adressen") or {}
        self.offene_auftraege = daten.get("offene_auftraege") or []

    def speichern(self):
        if self.pfad is None:
            return
        self.pfad.parent.mkdir(parents=True, exist_ok=True)
        self.pfad.write_text(json.dumps(
            {"gelesen": self.gelesen, "adressen": self.adressen,
             "offene_auftraege": self.offene_auftraege},
            ensure_ascii=False, indent=1), encoding="utf-8")

    def adresse(self, anfrage: dict):
        """Returns (bekannt, mail) - bekannt False means: not paid for yet."""
        schluessel = _adress_schluessel(
            anfrage["first_name"], anfrage["last_name"], anfrage.get("website"))
        if schluessel in self.adressen:
            return True, self.adressen[schluessel]
        return False, None

    def adresse_merken(self, anfrage: dict, mail):
        self.adressen[_adress_schluessel(
            anfrage["first_name"], anfrage["last_name"],
            anfrage.get("website"))] = mail

    def zeilen_uebernehmen(self, zeilen: list) -> int:
        """Take raw Dropcontact rows into the cache (recovering a paid batch)."""
        from pipeline.sources.dropcontact import _beste_email
        neu = 0
        for zeile in zeilen or []:
            if not (zeile.get("first_name") and zeile.get("last_name")):
                continue
            schluessel = _adress_schluessel(
                zeile["first_name"], zeile["last_name"], zeile.get("website"))
            if schluessel not in self.adressen:
                self.adressen[schluessel] = _beste_email(zeile.get("email", []))
                neu += 1
        return neu


def personen_lesen(firma: dict, impressum) -> dict:
    """Read the managers off one company website. Own work, no provider."""
    website = firma.get("website")
    if not website:
        return {"personen": [], "mail_domain": None}
    text = impressum.impressum_text(website)
    if not text:
        return {"personen": [], "mail_domain": None}
    ergebnis = impressum.entscheider_lesen(
        text, firma.get("name", ""), domain=firma.get("domain", ""),
        hinweis_name=firma.get("gf_name_liste", ""))
    # Beste Rolle zuerst (CEO/GF vor Inhaber vor Gruender ...): Runde 1
    # des Adress-Baus gilt dem wahrscheinlichsten Entscheider (Oliver,
    # 19.08.2026, pipeline.decision_maker).
    ergebnis["personen"] = sort_by_priority(ergebnis.get("personen") or [])
    return ergebnis


def _seiten_lesen(firmen: list, impressum, arbeiter: int, stand: Zwischenstand,
                  fortschritt) -> dict:
    """Phase 1 - all websites in parallel, results kept on disk."""
    gelesen: dict = {}
    zu_lesen = []
    for nr, firma in enumerate(firmen):
        gespeichert = stand.gelesen.get(_schluessel(firma))
        if gespeichert is not None:
            gelesen[nr] = gespeichert
        else:
            zu_lesen.append((nr, firma))

    if gelesen:
        fortschritt(f"  {len(gelesen)} Webseiten schon gelesen - übersprungen.")
    if not zu_lesen:
        return gelesen

    fertig = 0

    def eine(nr_firma):
        nr, firma = nr_firma
        try:
            return nr, personen_lesen(firma, impressum)
        except Exception as fehler:      # noqa: BLE001 - stored, not swallowed
            return nr, fehler

    with ThreadPoolExecutor(max_workers=arbeiter) as pool:
        for nr, ergebnis in pool.map(eine, zu_lesen):
            gelesen[nr] = ergebnis
            if not isinstance(ergebnis, Exception):
                stand.gelesen[_schluessel(firmen[nr])] = ergebnis
            fertig += 1
            if fertig % 25 == 0 or fertig == len(zu_lesen):
                fortschritt(f"  Webseiten gelesen: {fertig}/{len(zu_lesen)}")
                stand.speichern()
    stand.speichern()
    return gelesen


def _offene_auftraege_abholen(dropcontact, stand: Zwischenstand, fortschritt):
    """Fetch batches that were paid for but never collected."""
    if not stand.offene_auftraege:
        return
    fortschritt(f"  {len(stand.offene_auftraege)} bezahlte(r) Auftrag/Auftraege "
                f"von vorher - werden zuerst abgeholt (kostet nichts).")
    uebrig = []
    for auftrag in stand.offene_auftraege:
        try:
            zeilen = dropcontact.zeilen_holen(auftrag["request_id"])
        except Exception as fehler:      # noqa: BLE001
            fortschritt(f"  Auftrag {auftrag['request_id']} noch nicht "
                        f"abholbar: {fehler}")
            uebrig.append(auftrag)
            continue
        neu = stand.zeilen_uebernehmen(zeilen)
        fortschritt(f"  Auftrag {auftrag['request_id']}: {neu} Adressen gerettet.")
    stand.offene_auftraege = uebrig
    stand.speichern()


def _adressen_holen(anfragen: list, dropcontact, stand: Zwischenstand,
                    batch: int, fortschritt) -> list:
    """Ask Dropcontact for a list of people; returns one entry per request.

    All batches are handed over FIRST and written down, then collected.
    Dropcontact works on them side by side, so the long wait happens once
    for all of them instead of once per batch - and a crash in between
    cannot lose them, because the request_ids are already on disk.
    """
    ergebnisse: list = [None] * len(anfragen)
    zu_fragen = []
    for nr, anfrage in enumerate(anfragen):
        bekannt, mail = stand.adresse(anfrage)
        if bekannt:
            ergebnisse[nr] = mail
        else:
            zu_fragen.append((nr, anfrage))

    if len(zu_fragen) < len(anfragen):
        fortschritt(f"  {len(anfragen) - len(zu_fragen)} Adressen schon bezahlt "
                    f"- aus dem Zwischenstand übernommen.")
    if not zu_fragen:
        return ergebnisse

    auftraege = []
    for start in range(0, len(zu_fragen), batch):
        teil = zu_fragen[start:start + batch]
        request_id, gesendet = dropcontact.batch_abgeben([a for _, a in teil])
        if request_id is None:
            continue
        stand.offene_auftraege.append(
            {"request_id": request_id, "anzahl": len(gesendet)})
        stand.speichern()          # bezahlt - ab jetzt darf nichts mehr verloren gehen
        auftraege.append((request_id, gesendet, teil))
        fortschritt(f"  Auftrag {request_id} abgegeben ({len(gesendet)} Personen)")

    for request_id, gesendet, teil in auftraege:
        treffer = dropcontact.batch_abholen(request_id, gesendet, len(teil))
        for (nr, anfrage), mail in zip(teil, treffer):
            ergebnisse[nr] = mail
            stand.adresse_merken(anfrage, mail)
        stand.offene_auftraege = [
            a for a in stand.offene_auftraege if a["request_id"] != request_id]
        stand.speichern()
        fortschritt(f"  Auftrag {request_id} abgeholt.")
    return ergebnisse


def _adressen_bauen(firmen: list, gelesen: dict, dropcontact, max_pro_firma: int,
                    batch: int, stand: Zwischenstand, fortschritt) -> dict:
    """Phase 2 - Dropcontact in rounds, one round per manager position."""
    _offene_auftraege_abholen(dropcontact, stand, fortschritt)
    kontakte: dict = {nr: [] for nr in range(len(firmen))}
    runde = 0
    while True:
        anfragen, herkunft = [], []
        for nr, firma in enumerate(firmen):
            daten = gelesen.get(nr)
            if isinstance(daten, Exception) or not daten:
                continue
            if len(kontakte[nr]) >= max_pro_firma:
                continue
            personen = daten.get("personen") or []
            if runde >= len(personen):
                continue
            person = personen[runde]
            mail_domain = daten.get("mail_domain")
            ziel = f"https://{mail_domain}" if mail_domain else firma.get("website")
            anfragen.append({
                "first_name": person["vorname"], "last_name": person["nachname"],
                "website": ziel, "company": firma.get("name", "")})
            herkunft.append((nr, person))
        if not anfragen:
            return kontakte

        runde += 1
        fortschritt(f"  Dropcontact Runde {runde}: {len(anfragen)} Personen")
        treffer = _adressen_holen(anfragen, dropcontact, stand, batch, fortschritt)
        for (nr, person), mail in zip(herkunft, treffer):
            if mail:
                kontakte[nr].append({
                    "first_name": person["vorname"],
                    "last_name": person["nachname"],
                    "email": mail["email"], "title": _impressum_titel(person),
                    "source": "impressum",
                    "notizen": [mail["hinweis"]] if mail.get("hinweis") else []})


def _eintrag_bauen(firma: dict, gefunden: list, gelesen, kunde, hunter) -> dict:
    """Turn one company's outcome into the record grosslauf also writes."""
    if isinstance(gelesen, Exception):
        return {**firma, "ausgang": "fehler"}

    # Gefundene Entscheider MIT Rolle und Rangfolge am Firmensatz halten -
    # auch ohne gepruefte Mail ("ohne_mail"); Eintrag 0 ist der primaere
    # Entscheider (Oliver, 19.08.2026).
    entscheider = build_entscheider((gelesen or {}).get("personen") or [],
                                    gefunden)
    zusatz = ({"entscheider": entscheider,
               "entscheider_primaer": entscheider[0]} if entscheider else {})

    firmenname = _firmenname_saeubern(firma.get("name", ""), kunde.maps_suche)
    if gefunden:
        return {**firma, **zusatz,
                "ausgang": "mit_entscheider", "stufe": "impressum",
                "leads": [{"first_name": k["first_name"], "last_name": k["last_name"],
                           "email": k["email"].strip().lower(), "company": firmenname,
                           "title": k["title"], "website": firma.get("website"),
                           "source": k["source"], "notizen": k.get("notizen") or []}
                          for k in gefunden]}

    if not firma.get("domain"):
        ausgang = "kein_entscheider" if firma.get("website") else "keine_webseite"
        return {**firma, **zusatz, "ausgang": ausgang, "leads": []}

    info_email = f"info@{firma['domain']}"
    pruefstatus = None
    if hunter is not None:
        try:
            pruefstatus = (hunter.email_pruefen(info_email) or {}).get("status", "")
        except Exception as fehler:      # noqa: BLE001
            print(f"Firma '{firma.get('name') or firma.get('domain')}' "
                  f"übersprungen (Fehler bei der info@-Prüfung): {fehler}")
            return {**firma, "ausgang": "fehler"}

    eintrag = {**firma, **zusatz}
    if pruefstatus is not None:
        eintrag["info_pruefstatus"] = pruefstatus
    if pruefstatus is None or pruefstatus in INFO_OK_STATUS:
        eintrag["ausgang"] = "info_fallback"
        eintrag["leads"] = [{"first_name": "", "last_name": "", "email": info_email,
                             "company": firmenname, "title": "",
                             "website": firma.get("website"), "source": "info@",
                             "notizen": []}]
    else:
        eintrag["ausgang"] = "info_ungueltig"
        eintrag["leads"] = []
    return eintrag


def lauf_ausfuehren(firmen: list, kunde, dropcontact, impressum, hunter=None,
                    vorhandene=None, arbeiter=16, batch=100, lauf_dir=None,
                    fortschritt=print) -> list:
    """Run the whole list. Finished companies are skipped, errors retried."""
    alte = {_schluessel(e): e for e in (vorhandene or [])}
    offen = [f for f in firmen
             if (alte.get(_schluessel(f)) or {}).get("ausgang") in (None, "fehler")]
    fortschritt(f"{len(firmen)} Firmen, davon {len(offen)} noch zu tun.")
    stand = Zwischenstand(lauf_dir)
    if not offen:
        _offene_auftraege_abholen(dropcontact, stand, fortschritt)
        return [alte[_schluessel(f)] for f in firmen]

    max_pro_firma = getattr(kunde, "max_kontakte_pro_firma", None) or 1
    gelesen = _seiten_lesen(offen, impressum, arbeiter, stand, fortschritt)
    kontakte = _adressen_bauen(offen, gelesen, dropcontact, max_pro_firma,
                               batch, stand, fortschritt)

    neu = {}
    for nr, firma in enumerate(offen):
        neu[_schluessel(firma)] = _eintrag_bauen(
            firma, kontakte.get(nr) or [], gelesen.get(nr), kunde, hunter)
    return [neu.get(_schluessel(f)) or alte[_schluessel(f)] for f in firmen]


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--firmen", required=True)
    parser.add_argument("--lauf", required=True)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--arbeiter", type=int, default=16)
    parser.add_argument("--batch", type=int, default=100)
    args = parser.parse_args(argv)

    lade_dotenv()
    brauche_env("DROPCONTACT_API_KEY")
    brauche_env("HUNTER_API_KEY")
    brauche_env_eines_von(
        "ANTHROPIC_API_KEY", "OPENROUTER_API_KEY", "OPENAI_API_KEY")

    firmen = json.loads(Path(args.firmen).read_text(encoding="utf-8"))
    if args.limit:
        firmen = firmen[:args.limit]

    # Same shape as grosslauf builds it: only the list-driven fields
    # matter here, the mail-text fields are unused by the cascade.
    kunde = Kunde(name="Großlauf", zielgruppe={}, angebot="-", tonalitaet="-",
                  absender="-", follow_up_tage=[3, 7],
                  test_empfaenger=["test@example.com"],
                  maps_suche="(Liste)",
                  kontakt_rollen=["Geschäftsführer", "Inhaber"],
                  anbieter_reihenfolge=["impressum"])

    ergebnisse = lauf_ausfuehren(
        firmen, kunde,
        DropcontactSource(os.environ["DROPCONTACT_API_KEY"]),
        ImpressumQuelle(KI()),
        HunterSource(os.environ["HUNTER_API_KEY"]),
        vorhandene=lauf_laden(args.lauf),
        arbeiter=args.arbeiter, batch=args.batch, lauf_dir=args.lauf)

    lauf_speichern(args.lauf, ergebnisse, dubletten_finden(firmen))
    z = zusammenfassung(ergebnisse)
    print(f"\nFertig: {z['firmen_gesamt']} Firmen, "
          f"{z['persoenliche_mail']} persönliche Mails "
          f"({z['quote_prozent']} %). Bericht: {args.lauf}/bericht.md")


if __name__ == "__main__":
    main()
