import argparse, os, sys
from collections import Counter
from pathlib import Path
from pipeline.config import load_kunde
from pipeline.env import lade_dotenv, brauche_env as _brauche_env
from pipeline.run_store import RunStore
from pipeline.sources.apollo import ApolloSource
from pipeline.dedupe import dedupe as dedupe_leads
from pipeline.website import fetch_text
from pipeline.ki import KI
from pipeline.personalize import personalize
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
        print("Alte Freigabe verworfen (FREIGABE.txt geloescht) - dieser Lauf "
             "muss nach --neu-ab erneut geprueft und freigegeben werden.")

def lauf(kunde_pfad: str, limit: int, fortsetzen: str | None, neu_ab: str | None = None):
    _brauche_env("APOLLO_API_KEY")
    _brauche_env("ANTHROPIC_API_KEY")
    kunde = load_kunde(kunde_pfad)
    store = RunStore.resume(fortsetzen) if fortsetzen else RunStore(LAEUFE, kunde.name)
    if neu_ab:
        _setze_schritte_zurueck(store, neu_ab)
    store.save_step("kunde_pfad", {"pfad": str(kunde_pfad)})
    print(f"Laufordner: {store.run_dir}")

    if not store.step_done("leads"):
        quelle = ApolloSource(os.environ["APOLLO_API_KEY"])
        gefunden = quelle.search(kunde.zielgruppe, limit)
        store.save_step("leads", {"leads": [l.__dict__ for l in gefunden],
                                  "ohne_email": quelle.uebersprungen_ohne_email})
    stand_leads = store.load_step("leads")
    if isinstance(stand_leads, list):
        # Alte Laufordner (vor der "ohne_email"-Zaehlung) speicherten
        # leads.json als reine Liste statt {"leads": [...], "ohne_email": n}.
        # --fortsetzen auf so einem Ordner soll trotzdem funktionieren.
        stand_leads = {"leads": stand_leads, "ohne_email": 0}
    leads = [Lead(**{k: d[k] for k in ("first_name", "last_name", "email",
                                        "company", "title", "website", "source")})
             for d in stand_leads["leads"]]

    if not store.step_done("dedupe"):
        behalten, verworfen = dedupe_leads(leads, store.run_dir.parent, kunde.sperrliste,
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
                texte = personalize(lead, kunde, ki, fetch_text(lead.website))
                ok, grund = check(texte, lead, kunde, ki)
            except ValueError as fehler:
                ok, grund, texte = False, str(fehler), {}
            if ok:
                fertig.append({"email": lead.email, **texte})
            else:
                nacharbeit.append({"email": lead.email, "grund": grund})
        store.save_step("personalisierung", {"fertig": fertig, "nacharbeit": nacharbeit})
    ergebnis = store.load_step("personalisierung")
    store.save_step("pruefung_ok", ergebnis["fertig"])

    write_preview(store, ergebnis["fertig"], ergebnis["nacharbeit"])
    gruende = [f"{g}: {n}" for g, n in
               Counter(v["grund"] for v in stand["verworfen"]).items()]
    write_report(store, {"gefunden": len(leads), "verworfen": len(stand["verworfen"]),
                         "personalisiert": len(ergebnis["fertig"]),
                         "nacharbeit": len(ergebnis["nacharbeit"]),
                         "gruende_verworfen": gruende,
                         "ohne_email": stand_leads["ohne_email"]})
    print(f"Vorschau: {store.run_dir / 'freigabe-vorschau.md'}")
    print("Naechster Schritt: pruefen, dann 'python -m pipeline freigeben <laufordner>'")

def freigeben(laufordner: str):
    approve(RunStore.resume(laufordner))
    print("Freigegeben. Senden mit: python -m pipeline senden", laufordner)

def senden(laufordner: str):
    _brauche_env("INSTANTLY_API_KEY")
    store = RunStore.resume(laufordner)
    if not is_approved(store):
        sys.exit("Keine Freigabe fuer diesen Lauf (FREIGABE.txt fehlt).")
    if store.step_done("versand_komplett"):
        campaign_id = store.load_step("versand_komplett")["campaign_id"]
        sys.exit(f"Kampagne bereits angelegt: {campaign_id}")
    kunde = load_kunde(store.load_step("kunde_pfad")["pfad"])
    texte = store.load_step("pruefung_ok")
    erlaubt = {e.strip().lower() for e in kunde.test_empfaenger}
    fremde = [t["email"] for t in texte if t["email"] not in erlaubt]
    if fremde:
        sys.exit(f"Abbruch: Empfaenger nicht in Test-Empfaenger-Liste: {fremde}")
    if not texte:
        sys.exit("Abbruch: keine freigegebenen Texte zum Versenden.")

    sender = InstantlySender(os.environ["INSTANTLY_API_KEY"])
    if store.step_done("versand"):
        # Kampagne wurde in einem frueheren, abgebrochenen Lauf schon
        # angelegt (z.B. weil der Lead-Import scheiterte) - dieselbe
        # campaign_id wiederverwenden statt eine zweite Kampagne anzulegen.
        # TODO(verifizieren am echten Konto): dedupliziert /leads/add pro
        # Kampagne per E-Mail? Sonst koennen Wiederholungs-Importe nach
        # Teilfehler Leads doppeln.
        campaign_id = store.load_step("versand")["campaign_id"]
        print(f"Kampagne {campaign_id} bereits angelegt - importiere Leads erneut.")
    else:
        campaign_id = sender.create_campaign(kunde)
        store.save_step("versand", {"campaign_id": campaign_id})

    sender.import_leads(campaign_id, texte)
    store.save_step("versand_komplett", {"campaign_id": campaign_id})
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
