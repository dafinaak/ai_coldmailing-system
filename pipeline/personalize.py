import json, re
from pathlib import Path

PROMPT_DATEI = Path(__file__).parent.parent / "prompts" / "anschreiben.md"
PFLICHT = ["betreff", "mail_1", "follow_up_1", "follow_up_2"]
SYSTEM = "Du bist ein praeziser Texter fuer B2B-Kaltakquise. Antworte nur mit JSON."

def personalize(lead, kunde, ki, webseiten_text: str) -> dict:
    prompt = PROMPT_DATEI.read_text(encoding="utf-8").format(
        absender=kunde.absender, kunde_name=kunde.name, angebot=kunde.angebot,
        tonalitaet=kunde.tonalitaet, anrede_name=f"{lead.first_name} {lead.last_name}",
        titel=lead.title, firma=lead.company, webseiten_text=webseiten_text or "(leer)")
    roh = ki.frage(SYSTEM, prompt)
    treffer = re.search(r"\{.*\}", roh, re.DOTALL)
    try:
        daten = json.loads(treffer.group(0)) if treffer else {}
    except ValueError:
        daten = {}
    if any(not daten.get(k) for k in PFLICHT):
        raise ValueError(f"KI-Antwort unvollstaendig fuer {lead.email}")
    return {k: daten[k] for k in PFLICHT}
