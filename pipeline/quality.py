from pathlib import Path

PROMPT_DATEI = Path(__file__).parent.parent / "prompts" / "pruefer.md"
SYSTEM = "Du bist ein strenger Pruefer fuer B2B-Kaltakquise-Texte."

def _regeln(texte: dict) -> str:
    alle = " ".join(texte.values())
    if "{" in alle or "[" in alle:
        return "Platzhalter im Text übrig"
    if len(texte["betreff"]) > 60:
        return "Betreff länger als 60 Zeichen"
    woerter = len(texte["mail_1"].split())
    if not 40 <= woerter <= 160:
        return f"mail_1 hat {woerter} Wörter (erlaubt 40-160)"
    return ""

def check(texte, lead, kunde, ki):
    fehler = _regeln(texte)
    if fehler:
        return False, fehler
    prompt = PROMPT_DATEI.read_text(encoding="utf-8").format(
        titel=lead.title, firma=lead.company, tonalitaet=kunde.tonalitaet,
        betreff=texte["betreff"], mail_1=texte["mail_1"])
    urteil = ki.frage(SYSTEM, prompt).strip()
    if urteil.upper().startswith("JA"):
        return True, "bestanden"
    return False, f"KI-Prüfer: {urteil}"
