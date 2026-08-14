import json, re, sys
from pathlib import Path
import yaml
from pipeline.env import lade_dotenv, brauche_env_eines_von
from pipeline.website import fetch_text
from pipeline.ki import KI

PROMPT_DATEI = Path(__file__).parent.parent / "prompts" / "angebot.md"
USP_PROMPT_DATEI = Path(__file__).parent.parent / "prompts" / "usp_icp.md"
SYSTEM = ("Du analysierst Firmen-Webseiten und formulierst "
          "Angebots-Beschreibungen. Antworte nur mit JSON.")
FELDER = ["angebot", "tonalitaet"]
ICP_GRUPPEN = ["firmografisch", "technografisch", "verhalten", "entscheider"]

def draft_offer(website_text: str, ki) -> dict:
    prompt = PROMPT_DATEI.read_text(encoding="utf-8").format(
        webseiten_text=website_text or "(leer)")
    roh = ki.frage(SYSTEM, prompt)
    treffer = re.search(r"\{.*\}", roh, re.DOTALL)
    try:
        daten = json.loads(treffer.group(0)) if treffer else {}
    except ValueError:
        daten = {}
    if any(not daten.get(k) for k in FELDER):
        raise ValueError("KI-Entwurf unvollständig")
    return {k: daten[k] for k in FELDER}

def draft_usp_icp(website_text: str, ki, kampagnen_zweck: str = "") -> dict:
    """Read a seller's own website and draft its USP list and ICP groups.

    Step 2 of the campaign wizard shows this as a proposal, never as a
    fact - a human corrects it before anything is sent. Where the page
    says nothing about a point, the prompt asks for an honest "not
    recognisable" rather than an invention, so nobody later builds a
    campaign on a sentence the AI made up.

    kampagnen_zweck carries what step 1 was told the campaign is for.
    Without it the model only ever sees the seller's own page, so it
    describes that seller's usual END customer - which is wrong whenever
    the campaign writes to partners who resell the offer. That happened on
    14.08.2026: a partner campaign came back described as "mid-sized
    companies looking for automation", and every generated email would
    have addressed the reader as the buyer instead of the partner.
    """
    prompt = USP_PROMPT_DATEI.read_text(encoding="utf-8").format(
        webseiten_text=website_text or "(leer)",
        kampagnen_zweck=(kampagnen_zweck or "").strip() or "(nichts angegeben)")
    roh = ki.frage(SYSTEM, prompt)
    treffer = re.search(r"\{.*\}", roh, re.DOTALL)
    try:
        daten = json.loads(treffer.group(0)) if treffer else {}
    except ValueError:
        daten = {}

    usp = []
    for eintrag in daten.get("usp") or []:
        titel = str((eintrag or {}).get("titel") or "").strip()
        if titel:
            usp.append({
                "titel": titel,
                "erklaerung": str(eintrag.get("erklaerung") or "").strip(),
            })
    icp = {g: str((daten.get("icp") or {}).get(g) or "").strip()
           for g in ICP_GRUPPEN}

    if not usp or not any(icp.values()):
        raise ValueError("KI-Entwurf unvollständig")
    return {"usp": usp, "icp": icp}


def uebernehmen(kunde_pfad, entwurf: dict):
    pfad = Path(kunde_pfad)
    daten = yaml.safe_load(pfad.read_text(encoding="utf-8")) or {}
    for feld in FELDER:
        if not daten.get(feld):
            daten[feld] = entwurf[feld]
    pfad.write_text(yaml.safe_dump(daten, allow_unicode=True, sort_keys=False),
                    encoding="utf-8")

def main():
    lade_dotenv()
    if len(sys.argv) < 3:
        print("Aufruf: python -m pipeline.offer <url> <kunde.yaml>")
        sys.exit(1)
    brauche_env_eines_von("ANTHROPIC_API_KEY", "OPENROUTER_API_KEY", "OPENAI_API_KEY")
    url, kunde_pfad = sys.argv[1], sys.argv[2]
    entwurf = draft_offer(fetch_text(url), KI())
    uebernehmen(kunde_pfad, entwurf)
    print("Entwurf eingetragen (nur leere Felder):",
          json.dumps(entwurf, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
