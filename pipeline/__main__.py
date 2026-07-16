import argparse, os, sys
from collections import Counter
from pathlib import Path
from pipeline.config import load_kunde
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

def lauf(kunde_pfad: str, limit: int, fortsetzen: str | None):
    kunde = load_kunde(kunde_pfad)
    store = RunStore.resume(fortsetzen) if fortsetzen else RunStore(LAEUFE, kunde.name)
    store.save_step("kunde_pfad", {"pfad": str(kunde_pfad)})
    print(f"Laufordner: {store.run_dir}")

    if not store.step_done("leads"):
        quelle = ApolloSource(os.environ["APOLLO_API_KEY"])
        leads = quelle.search(kunde.zielgruppe, limit)
        store.save_step("leads", [l.__dict__ for l in leads])
    leads = [Lead(**{k: d[k] for k in ("first_name", "last_name", "email",
                                        "company", "title", "website", "source")})
             for d in store.load_step("leads")]

    if not store.step_done("dedupe"):
        behalten, verworfen = dedupe_leads(leads, store.run_dir.parent, kunde.sperrliste)
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
                         "gruende_verworfen": gruende})
    print(f"Vorschau: {store.run_dir / 'freigabe-vorschau.md'}")
    print("Naechster Schritt: pruefen, dann 'python -m pipeline freigeben <laufordner>'")

def freigeben(laufordner: str):
    approve(RunStore.resume(laufordner))
    print("Freigegeben. Senden mit: python -m pipeline senden", laufordner)

def senden(laufordner: str):
    store = RunStore.resume(laufordner)
    if not is_approved(store):
        sys.exit("Keine Freigabe fuer diesen Lauf (FREIGABE.txt fehlt).")
    kunde = load_kunde(store.load_step("kunde_pfad")["pfad"])
    texte = store.load_step("pruefung_ok")
    erlaubt = {e.strip().lower() for e in kunde.test_empfaenger}
    fremde = [t["email"] for t in texte if t["email"] not in erlaubt]
    if fremde:
        sys.exit(f"Abbruch: Empfaenger nicht in Test-Empfaenger-Liste: {fremde}")
    sender = InstantlySender(os.environ["INSTANTLY_API_KEY"])
    campaign_id = sender.create_campaign(kunde, texte)
    store.save_step("versand", {"campaign_id": campaign_id})
    print(f"Kampagne {campaign_id} pausiert angelegt - Aktivierung von Hand in Instantly.")

def main():
    parser = argparse.ArgumentParser(prog="pipeline")
    sub = parser.add_subparsers(dest="befehl", required=True)
    p_lauf = sub.add_parser("lauf")
    p_lauf.add_argument("kunde")
    p_lauf.add_argument("--limit", type=int, default=10)
    p_lauf.add_argument("--fortsetzen", default=None)
    for name in ("freigeben", "senden"):
        p = sub.add_parser(name)
        p.add_argument("laufordner")
    args = parser.parse_args()
    if args.befehl == "lauf":
        lauf(args.kunde, args.limit, args.fortsetzen)
    elif args.befehl == "freigeben":
        freigeben(args.laufordner)
    else:
        senden(args.laufordner)

if __name__ == "__main__":
    main()
