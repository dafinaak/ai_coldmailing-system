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
from pipeline.dropcontact_register import REUSED_SOURCE, load_register, reused_note
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
                    batch: int, fortschritt, register=None) -> list:
    """Ask Dropcontact for a list of people; returns one entry per request.

    All batches are handed over FIRST and written down, then collected.
    Dropcontact works on them side by side, so the long wait happens once
    for all of them instead of once per batch - and a crash in between
    cannot lose them, because the request_ids are already on disk.

    Before that, this run's own cache and then the Dropcontact register
    are asked (Jira AP-216). What the register answers is NOT written to
    the cache: the cache counts as this run's own answers, so a reused
    address would get this run's date and outlive its 90 days.
    """
    ergebnisse: list = [None] * len(anfragen)
    zu_fragen = []
    aus_register = 0
    for nr, anfrage in enumerate(anfragen):
        bekannt, mail = stand.adresse(anfrage)
        if not bekannt and register is not None:
            bekannt, mail = register.reuse(anfrage["first_name"],
                                           anfrage["last_name"],
                                           anfrage.get("website"))
            aus_register += bekannt
        if bekannt:
            ergebnisse[nr] = mail
        else:
            zu_fragen.append((nr, anfrage))

    aus_zwischenstand = len(anfragen) - len(zu_fragen) - aus_register
    if aus_zwischenstand:
        fortschritt(f"  {aus_zwischenstand} Adressen schon bezahlt "
                    f"- aus dem Zwischenstand übernommen.")
    if aus_register:
        fortschritt(f"  {aus_register} people known from earlier runs "
                    f"- not paid for again.")
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
                    batch: int, stand: Zwischenstand, fortschritt,
                    register=None) -> dict:
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
        treffer = _adressen_holen(anfragen, dropcontact, stand, batch,
                                  fortschritt, register)
        for (nr, person), mail in zip(herkunft, treffer):
            if mail:
                if mail.get("reused_from"):
                    quelle, notizen = REUSED_SOURCE, [reused_note(mail)]
                else:
                    quelle = "impressum"
                    notizen = [mail["hinweis"]] if mail.get("hinweis") else []
                kontakte[nr].append({
                    "first_name": person["vorname"],
                    "last_name": person["nachname"],
                    "email": mail["email"], "title": _impressum_titel(person),
                    "source": quelle, "notizen": notizen})


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

    # Ohne persoenliche geprueft Adresse ist die Firma nicht
    # kampagnentauglich (Oliver, Phase 1, 20.08.2026) - gespeichert
    # bleibt alles, was gefunden wurde.
    unfaehig = {"campaign_eligible": False,
                "campaign_ineligibility_reason":
                    "personal_decision_maker_email_missing"
                    if zusatz.get("entscheider") else "no_decision_maker"}

    if not firma.get("domain"):
        ausgang = "kein_entscheider" if firma.get("website") else "keine_webseite"
        return {**firma, **zusatz, **unfaehig, "ausgang": ausgang, "leads": []}

    # Sammeladressen-Regel: info@ wird weiter geprueft und als
    # FIRMEN-INFORMATION festgehalten - sie wird NIE mehr zum
    # Kampagnen-Lead (vorher Ausgang "info_fallback" samt Lead).
    info_email = f"info@{firma['domain']}"
    pruefstatus = None
    if hunter is not None:
        try:
            pruefstatus = (hunter.email_pruefen(info_email) or {}).get("status", "")
        except Exception as fehler:      # noqa: BLE001
            print(f"Firma '{firma.get('name') or firma.get('domain')}' "
                  f"übersprungen (Fehler bei der info@-Prüfung): {fehler}")
            return {**firma, "ausgang": "fehler"}

    eintrag = {**firma, **zusatz, **unfaehig, "leads": []}
    if pruefstatus is None:
        # Kein Pruefer: Adresse bleibt als UNGEPRUEFTE Information stehen
        # (frueher wurde sie hier sogar ungeprueft versendet - Altlast).
        eintrag["info_email"] = info_email
        eintrag["info_pruefstatus"] = "ungeprueft"
        eintrag["ausgang"] = "ohne_persoenliche_mail"
    elif pruefstatus in INFO_OK_STATUS:
        eintrag["info_email"] = info_email
        eintrag["info_pruefstatus"] = pruefstatus
        eintrag["ausgang"] = "ohne_persoenliche_mail"
    else:
        eintrag["info_pruefstatus"] = pruefstatus
        eintrag["ausgang"] = "info_ungueltig"
    return eintrag


def _automatisierung_pruefen(firmen: list, kunde, impressum, fortschritt) -> dict:
    """Ein Urteil je Firma - dieselbe Pflichtregel wie in source_leads.

    Nicht pruefbar (kein KI-Baustein, Schalter aus, Webseite nicht
    lesbar) heisst unsicher, und unsicher heisst: keine Kampagne. Es gibt
    hier keinen Rueckgabewert, der eine Firma ungeprueft durchlaesst.
    """
    from pipeline.automation_klassifikation import (laden as
                                                    klassifikation_laden,
                                                    unsicheres_urteil,
                                                    urteile_je_firma)

    if not firmen:
        return {}
    if not getattr(kunde, "wettbewerber_pruefung", True):
        fortschritt("  Automatisierungs-Prüfung ist in dieser Kundendatei "
                    "abgeschaltet - sie wird NICHT übersprungen: alle "
                    "Firmen gelten als unsicher und kommen in keine "
                    "Kampagne.")
        return {i: unsicheres_urteil("Prüfung abgeschaltet", "pruefung-aus")
                for i in range(len(firmen))}

    try:
        vorwissen = klassifikation_laden(".")
    except Exception:      # noqa: BLE001 - fehlende Datei stoppt nichts
        vorwissen = {}
    urteile = urteile_je_firma(firmen, getattr(impressum, "ki", None),
                               vorwissen=vorwissen, log=fortschritt)
    anbieter = sum(1 for u in urteile.values() if u.get("wettbewerber"))
    unsicher = sum(1 for u in urteile.values() if u.get("unsicher"))
    fortschritt(f"  Automatisierungs-Prüfung: {len(urteile)} Firmen, "
                f"{anbieter} Anbieter, {unsicher} unsicher - beide "
                f"Gruppen bleiben gespeichert, ohne Kampagne.")
    return urteile


def _automation_felder(urteil: dict) -> dict:
    """Die Pruef-Felder am Firmensatz - gleiches Vokabular wie sourcing."""
    from datetime import datetime
    return {
        "offers_automation_services":
            "uncertain" if urteil.get("unsicher")
            else ("yes" if urteil.get("wettbewerber") else "no"),
        "automation_check_reason": urteil.get("belege", ""),
        "automation_check_source": urteil.get("quelle", "webseite+ki"),
        "automation_checked_at": datetime.now().isoformat(timespec="seconds"),
    }


def _ausgeschlossene_firma(firma: dict, urteil: dict) -> dict:
    """Der Firmensatz eines Ausgeschlossenen: markiert, nicht geloescht."""
    unsicher = bool(urteil.get("unsicher"))
    return {**firma, **_automation_felder(urteil),
            "ausgang": "automation_unsicher" if unsicher else "wettbewerber",
            "leads": [],
            "campaign_eligible": False,
            "campaign_ineligibility_reason":
                "automation_uncertain" if unsicher else "automation_provider"}


def lauf_ausfuehren(firmen: list, kunde, dropcontact, impressum, hunter=None,
                    vorhandene=None, arbeiter=16, batch=100, lauf_dir=None,
                    fortschritt=print, register=None) -> list:
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

    # Automatisierungs-Pruefung VOR jedem bezahlten Schritt - genau wie
    # in source_leads. Dieser Weg hatte sie bis 21.08.2026 gar nicht:
    # ueber schnelllauf kam JEDE Firma ungeprueft durch, auch der
    # Wettbewerber. Wer hier ausgeschlossen wird, kostet weder eine
    # Webseiten-Lesung noch ein Dropcontact-Guthaben.
    urteile = _automatisierung_pruefen(offen, kunde, impressum, fortschritt)
    geprueft = [(nr, f) for nr, f in enumerate(offen)
                if not (urteile[nr].get("wettbewerber")
                        or urteile[nr].get("unsicher"))]
    weiter = [f for _, f in geprueft]

    gelesen_teil = _seiten_lesen(weiter, impressum, arbeiter, stand,
                                 fortschritt)
    kontakte_teil = _adressen_bauen(weiter, gelesen_teil, dropcontact,
                                    max_pro_firma, batch, stand, fortschritt,
                                    register)
    # Zurueck auf die Nummern der vollen Liste uebersetzen.
    gelesen = {nr: gelesen_teil.get(j) for j, (nr, _) in enumerate(geprueft)}
    kontakte = {nr: kontakte_teil.get(j) for j, (nr, _) in enumerate(geprueft)}

    neu = {}
    for nr, firma in enumerate(offen):
        urteil = urteile[nr]
        if urteil.get("wettbewerber") or urteil.get("unsicher"):
            neu[_schluessel(firma)] = _ausgeschlossene_firma(firma, urteil)
            continue
        neu[_schluessel(firma)] = {
            **_eintrag_bauen(firma, kontakte.get(nr) or [], gelesen.get(nr),
                             kunde, hunter),
            **_automation_felder(urteil)}
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
        arbeiter=args.arbeiter, batch=args.batch, lauf_dir=args.lauf,
        # Jira AP-216: nobody this project paid for already is paid again.
        # This run's own folder stays out - its cache already covers it.
        register=load_register(Path(__file__).resolve().parent.parent,
                               exclude=[args.lauf]))

    lauf_speichern(args.lauf, ergebnisse, dubletten_finden(firmen))
    z = zusammenfassung(ergebnisse)
    print(f"\nFertig: {z['firmen_gesamt']} Firmen, "
          f"{z['persoenliche_mail']} persönliche Mails "
          f"({z['quote_prozent']} %). Bericht: {args.lauf}/bericht.md")


if __name__ == "__main__":
    main()
