import argparse, os, sys
from collections import Counter
from pathlib import Path
from pipeline.config import load_kunde, lade_globale_sperrliste
from pipeline.env import lade_dotenv, brauche_env as _brauche_env, brauche_env_eines_von as _brauche_env_eines_von
from pipeline.run_store import RunStore
from pipeline.sourcing import source_leads
from pipeline.dedupe import dedupe as dedupe_leads
from pipeline.website import fetch_text
from pipeline.ki import KI
from pipeline.personalize import personalisiere_mit_nachbesserung
from pipeline.quality import check
from pipeline.approval import write_preview, is_approved, approve
from pipeline.report import write_report
from pipeline.senders.instantly import InstantlySender
from pipeline.models import Lead

LAEUFE = Path("laeufe")

NEU_AB_REIHENFOLGE = ["leads", "dedupe", "personalisierung", "pruefung_ok"]

def _setze_schritte_zurueck(store, ab_schritt: str):
    """Loescht den JSON-Stand von ab_schritt und allen nachgelagerten
    Schritten (Reihenfolge: leads -> dedupe -> personalisierung ->
    pruefung_ok), damit 'lauf --fortsetzen ... --neu-ab ...' diese Schritte
    beim naechsten Durchlauf neu berechnet statt den alten Stand
    wiederzuverwenden. Eine bestehende Freigabe (FREIGABE.txt) wird dabei
    IMMER mitgeloescht: sie bezieht sich auf die alten Texte, und ein
    "senden" nach --neu-ab darf niemals unter einer Freigabe fuer laengst
    ueberholte Inhalte laufen. Der Lauf muss danach erneut geprueft und
    freigegeben werden."""
    start = NEU_AB_REIHENFOLGE.index(ab_schritt)
    for schritt in NEU_AB_REIHENFOLGE[start:]:
        store.delete_step(schritt)
    freigabe_pfad = store.run_dir / "FREIGABE.txt"
    if freigabe_pfad.exists():
        freigabe_pfad.unlink()
        print("Alte Freigabe verworfen (FREIGABE.txt gelöscht) - dieser Lauf "
             "muss nach --neu-ab erneut geprüft und freigegeben werden.")

_LEERE_DECKUNG = {"firmen_gesamt": 0, "firmen_mit_kontakt": 0, "quote_prozent": 0.0}

def lauf(kunde_pfad: str, limit: int, fortsetzen: str | None, neu_ab: str | None = None):
    # Reihenfolge folgt den 3 Stufen der Lead-Beschaffung (Kern-Umbau):
    # Apify (Stufe 1) -> Apollo (Stufe 2) -> KI (Personalisierung, danach).
    _brauche_env("APIFY_API_KEY")
    _brauche_env("APOLLO_API_KEY")
    _brauche_env_eines_von("ANTHROPIC_API_KEY", "OPENROUTER_API_KEY")
    kunde = load_kunde(kunde_pfad)
    store = RunStore.resume(fortsetzen) if fortsetzen else RunStore(LAEUFE, kunde.name)
    if neu_ab:
        _setze_schritte_zurueck(store, neu_ab)
    store.save_step("kunde_pfad", {"pfad": str(kunde_pfad)})
    print(f"Laufordner: {store.run_dir}")

    if not store.step_done("leads"):
        gefunden, deckung, firmen_mit_ausgang = source_leads(
            kunde, limit, os.environ["APIFY_API_KEY"], os.environ["APOLLO_API_KEY"])
        store.save_step("leads", {"leads": [l.__dict__ for l in gefunden], "deckung": deckung})
        # Apollo-422-Fix: Stufe-1-Firmenliste + Pro-Firma-Ausgang separat
        # persistieren (firmen.json), damit ein spaeterer Blick in den
        # Laufordner sauber zeigt, WARUM eine Firma ohne Kontakt blieb -
        # nicht nur DASS sie es tat.
        store.save_step("firmen", firmen_mit_ausgang)
    stand_leads = store.load_step("leads")
    if isinstance(stand_leads, list):
        # Alte Laufordner (vor dem Kern-Umbau) speicherten leads.json als
        # reine Liste bzw. als {"leads": [...], "ohne_email": n} ohne
        # "deckung". --fortsetzen auf so einem Ordner soll trotzdem
        # funktionieren, dann eben ohne echte Deckungsquote im Bericht.
        stand_leads = {"leads": stand_leads, "deckung": dict(_LEERE_DECKUNG)}
    if not stand_leads.get("deckung"):
        stand_leads["deckung"] = dict(_LEERE_DECKUNG)
    leads = [Lead(**{k: d[k] for k in ("first_name", "last_name", "email",
                                        "company", "title", "website", "source")})
             for d in stand_leads["leads"]]

    if not store.step_done("dedupe"):
        # Globale Sperrliste (gilt fuer alle Kunden) + die eigene Liste des
        # Kunden zusammen anwenden (Vereinigung, Reihenfolge egal). Der
        # daten_dir fuer die globale Liste ist hier bewusst der aktuelle
        # Arbeitsordner (Projekt-Wurzel, wo kunden/ und laeufe/ liegen) -
        # wie der Rest der CLI schon cwd-relativ arbeitet (siehe LAEUFE oben).
        globale_sperrliste = lade_globale_sperrliste(Path("."))
        sperrliste = list(set(kunde.sperrliste) | set(globale_sperrliste))
        behalten, verworfen = dedupe_leads(leads, store.run_dir.parent, sperrliste,
                                           aktueller_lauf=store.run_dir)
        store.save_step("dedupe", {"behalten": [l.__dict__ for l in behalten],
                                   "verworfen": verworfen})
    stand = store.load_step("dedupe")

    if not store.step_done("personalisierung"):
        ki, fertig, nacharbeit = KI(), [], []
        for d in stand["behalten"]:
            lead = Lead(**{k: d[k] for k in ("first_name", "last_name", "email",
                                              "company", "title", "website", "source")})
            try:
                webseiten_text = fetch_text(lead.website)
                # Nachbesserungs-Schleife: bei NEIN wird der Text mit dem
                # Prüfer-Grund bis zu 3x neu geschrieben, bevor er zur
                # Nacharbeit fällt (statt sofort auszusortieren).
                ok, grund, texte, _ = personalisiere_mit_nachbesserung(
                    lead, kunde, ki, webseiten_text, check)
            except ValueError as fehler:
                ok, grund, texte = False, str(fehler), {}
            if ok:
                fertig.append({"email": lead.email, **texte})
            else:
                # texte ist {} wenn personalize() selbst schon scheiterte
                # (kein Text erzeugt), sonst der volle Text, den nur check()
                # abgelehnt hat. Wird mitgespeichert, damit die "Von der
                # Pruefung aussortiert"-Ansicht im Web-Interface (Task 5) den
                # abgelehnten Text aufklappbar zeigen kann statt nur den Grund.
                nacharbeit.append({"email": lead.email, "grund": grund, **texte})
        store.save_step("personalisierung", {"fertig": fertig, "nacharbeit": nacharbeit})
    ergebnis = store.load_step("personalisierung")
    store.save_step("pruefung_ok", ergebnis["fertig"])

    write_preview(store, ergebnis["fertig"], ergebnis["nacharbeit"])
    gruende = [f"{g}: {n}" for g, n in
               Counter(v["grund"] for v in stand["verworfen"]).items()]
    deckung = stand_leads["deckung"]
    # Apollo-422-Fix: Ausgang-Aufschluesselung fuer den Bericht aus
    # firmen.json zaehlen - leere Liste (statt KeyError), wenn dieser
    # Laufordner noch aus einer Zeit VOR diesem Fix stammt (kein
    # firmen.json vorhanden, siehe --fortsetzen auf altem Laufordner).
    firmen_stand = store.load_step("firmen") if store.step_done("firmen") else []
    ausgang_zaehlung = Counter(f.get("ausgang") for f in firmen_stand)
    write_report(store, {"gefunden": len(leads), "verworfen": len(stand["verworfen"]),
                         "personalisiert": len(ergebnis["fertig"]),
                         "nacharbeit": len(ergebnis["nacharbeit"]),
                         "gruende_verworfen": gruende,
                         # "ohne_email" ist seit dem Kern-Umbau firmen-, nicht
                         # personenbezogen: die Zahl der Stufe-1-Firmen ganz
                         # ohne nutzbaren Kontakt (persönlich oder info@).
                         "ohne_email": deckung["firmen_gesamt"] - deckung["firmen_mit_kontakt"],
                         "firmen_mit_kontakt_ausgang": ausgang_zaehlung.get("mit_kontakt", 0),
                         "firmen_keine_webseite": ausgang_zaehlung.get("keine_webseite", 0),
                         "firmen_apollo_kein_treffer": ausgang_zaehlung.get("apollo_kein_treffer", 0),
                         "firmen_fehler": ausgang_zaehlung.get("fehler", 0),
                         "firmen_gesamt": deckung["firmen_gesamt"],
                         "firmen_mit_kontakt": deckung["firmen_mit_kontakt"],
                         "deckungsquote_prozent": deckung["quote_prozent"]})
    print(f"Vorschau: {store.run_dir / 'freigabe-vorschau.md'}")
    print("Nächster Schritt: prüfen, dann 'python -m pipeline freigeben <laufordner>'")

def freigeben(laufordner: str):
    # E-Fix 7: Konsistenz mit dem Web-Guard (web.routen.freigabe -
    # ZUSTAND_ERLAUBT_FREIGEBEN schliesst "abgelehnt" aus) - abgelehnt.json
    # muss ein absolutes Veto sein, egal ueber welchen Weg (CLI oder Web)
    # jemand versucht, danach doch noch freizugeben.
    store = RunStore.resume(laufordner)
    if (store.run_dir / "abgelehnt.json").exists():
        sys.exit(
            "Dieser Auftrag wurde abgelehnt - er darf nicht mehr freigegeben werden.")
    approve(store)
    print("Freigegeben. Senden mit: python -m pipeline senden", laufordner)

class SendenFehler(Exception):
    """Fasst die Abbruchgruende von '_versand_ausfuehren' als Exception statt
    sys.exit zusammen, damit dieselbe Kernlogik von zwei Aufrufern genutzt
    werden kann: der CLI (senden(), macht sys.exit(str(fehler)) daraus) und
    der Web-Route web/routen/freigabe.py (Task 5, macht daraus eine deutsche
    Fehlermeldung auf der Seite). Der Test-Empfaenger-Gate darf dadurch an
    genau einer Stelle stehen, nie dupliziert werden."""


def _versand_ausfuehren(store, sender, kunde=None) -> str:
    """Kernlogik von 'senden': Freigabe-/Empfaenger-Gate pruefen, Kampagne
    anlegen (oder eine schon angelegte wiederverwenden) und Leads
    importieren. `sender` ist ein InstantlySender (oder ein Fake mit
    derselben Schnittstelle in Tests/Web) - so bleibt diese Funktion
    unabhaengig davon, WO der API-Key herkommt.

    Sperrt IMMER (auch bei bestehender Freigabe - Review-Fund Task 5), wenn
    abgelehnt.json im Laufordner liegt: Ablehnen muss ein absolutes Veto
    sein, egal ob/wie es zu einer (fehlerhaften oder zeitlich versetzten)
    Freigabe kam. Diese Pruefung sitzt bewusst HIER (statt nur in der
    Web-Route), weil sowohl die CLI (senden()) als auch die Web-Route
    dieselbe Funktion aufrufen - eine Web-only-Sperre waere umgehbar.

    `kunde` ist optional: Standard None laedt ihn selbst ueber den in
    kunde_pfad.json gespeicherten Pfad, der relativ zum Arbeitsverzeichnis
    ist (funktioniert fuer die CLI, die immer mit cwd=daten_dir laeuft, s.
    web/laufmanager.py). Der Web-Aufrufer (web/routen/freigabe.py) laeuft
    dagegen IM SELBEN Prozess wie der Webserver, dessen cwd nicht daten_dir
    ist - er laedt den Kunden deshalb selbst (relativ zu daten_dir aufgeloest)
    und uebergibt ihn hier direkt, statt den Pfad blind nochmal relativ zum
    falschen Arbeitsverzeichnis zu lesen."""
    if (store.run_dir / "abgelehnt.json").exists():
        raise SendenFehler(
            "Dieser Auftrag wurde abgelehnt - es darf nichts versendet werden.")
    if not is_approved(store):
        raise SendenFehler("Keine Freigabe für diesen Lauf (FREIGABE.txt fehlt).")
    if store.step_done("versand_komplett"):
        campaign_id = store.load_step("versand_komplett")["campaign_id"]
        raise SendenFehler(f"Kampagne bereits angelegt: {campaign_id}")
    if kunde is None:
        kunde = load_kunde(store.load_step("kunde_pfad")["pfad"])
    texte = store.load_step("pruefung_ok")
    erlaubt = {e.strip().lower() for e in kunde.test_empfaenger}
    fremde = [t["email"] for t in texte if t["email"] not in erlaubt]
    if fremde:
        raise SendenFehler(f"Abbruch: Empfänger nicht in Test-Empfänger-Liste: {fremde}")
    if not texte:
        raise SendenFehler("Abbruch: keine freigegebenen Texte zum Versenden.")

    if store.step_done("versand"):
        # Kampagne wurde in einem frueheren, abgebrochenen Lauf schon
        # angelegt (z.B. weil der Lead-Import scheiterte) - dieselbe
        # campaign_id wiederverwenden statt eine zweite Kampagne anzulegen.
        # TODO(verifizieren am echten Konto): dedupliziert /leads/add pro
        # Kampagne per E-Mail? Sonst koennen Wiederholungs-Importe nach
        # Teilfehler Leads doppeln.
        campaign_id = store.load_step("versand")["campaign_id"]
    else:
        campaign_id = sender.create_campaign(kunde)
        store.save_step("versand", {"campaign_id": campaign_id})

    sender.import_leads(campaign_id, texte)
    store.save_step("versand_komplett", {"campaign_id": campaign_id})
    return campaign_id


def senden(laufordner: str):
    _brauche_env("INSTANTLY_API_KEY")
    store = RunStore.resume(laufordner)
    sender = InstantlySender(os.environ["INSTANTLY_API_KEY"])
    try:
        campaign_id = _versand_ausfuehren(store, sender)
    except SendenFehler as fehler:
        sys.exit(str(fehler))
    print(f"Kampagne {campaign_id} pausiert angelegt - Aktivierung von Hand in Instantly.")

def main():
    lade_dotenv()
    parser = argparse.ArgumentParser(prog="pipeline")
    sub = parser.add_subparsers(dest="befehl", required=True)
    p_lauf = sub.add_parser("lauf")
    p_lauf.add_argument("kunde")
    p_lauf.add_argument("--limit", type=int, default=10)
    p_lauf.add_argument("--fortsetzen", default=None)
    p_lauf.add_argument("--neu-ab", dest="neu_ab", default=None,
                        choices=["leads", "dedupe", "personalisierung"],
                        help="Nur zusammen mit --fortsetzen: verwirft diesen Schritt und "
                             "alle nachgelagerten, damit sie neu berechnet werden.")
    for name in ("freigeben", "senden"):
        p = sub.add_parser(name)
        p.add_argument("laufordner")
    args = parser.parse_args()
    if args.befehl == "lauf":
        lauf(args.kunde, args.limit, args.fortsetzen, args.neu_ab)
    elif args.befehl == "freigeben":
        freigeben(args.laufordner)
    else:
        senden(args.laufordner)

if __name__ == "__main__":
    main()
