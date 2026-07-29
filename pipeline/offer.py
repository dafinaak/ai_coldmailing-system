import json, re, sys
from pathlib import Path
import yaml
from pipeline.env import lade_dotenv, brauche_env_eines_von
from pipeline.website import fetch_text
from pipeline.ki import KI

PROMPT_DATEI = Path(__file__).parent.parent / "prompts" / "angebot.md"
SYSTEM = ("Du analysierst Firmen-Webseiten und formulierst "
          "Angebots-Beschreibungen. Antworte nur mit JSON.")
FELDER = ["angebot", "tonalitaet"]

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
