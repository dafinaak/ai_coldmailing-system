import json, re
from pathlib import Path

PROMPT_DATEI = Path(__file__).parent.parent / "prompts" / "anschreiben.md"
PFLICHT = ["betreff", "mail_1", "follow_up_1", "follow_up_2"]
SYSTEM = "Du bist ein praeziser Texter fuer B2B-Kaltakquise. Antworte nur mit JSON."

def personalize(lead, kunde, ki, webseiten_text: str, feedback: str = "") -> dict:
    prompt = PROMPT_DATEI.read_text(encoding="utf-8").format(
        absender=kunde.absender, kunde_name=kunde.name, angebot=kunde.angebot,
        tonalitaet=kunde.tonalitaet, anrede_name=f"{lead.first_name} {lead.last_name}",
        titel=lead.title, firma=lead.company, webseiten_text=webseiten_text or "(leer)")
    if feedback:
        # Nachbesserung: der strenge Prüfer hat einen vorherigen Entwurf
        # abgelehnt. Der KI genau diesen Grund geben und bitten, NUR das zu
        # beheben - nicht neu erfinden, restliche Regeln bleiben bindend.
        prompt += (
            "\n\nNACHBESSERUNG - der vorige Entwurf wurde von einem strengen "
            "Prüfer abgelehnt mit dieser Begründung:\n"
            f'"{feedback}"\n'
            "Behebe genau diesen Punkt. Erfinde nichts, halte alle obigen "
            "Regeln weiter ein, und ändere den Rest nur, soweit dafür nötig.")
    roh = ki.frage(SYSTEM, prompt)
    treffer = re.search(r"\{.*\}", roh, re.DOTALL)
    try:
        daten = json.loads(treffer.group(0)) if treffer else {}
    except ValueError:
        daten = {}
    if any(not daten.get(k) for k in PFLICHT):
        raise ValueError(f"KI-Antwort unvollständig für {lead.email}")
    return {k: daten[k] for k in PFLICHT}


def personalisiere_mit_nachbesserung(lead, kunde, ki, webseiten_text, check,
                                     max_versuche: int = 3):
    """Schreibt den Text und bessert ihn bei Ablehnung nach, bevor ein Mensch
    ran muss: fällt der Prüfer NEIN, geht der Grund zurück an die KI und der
    Text wird neu geschrieben - bis zu max_versuche mal. Besteht er, ist Schluss;
    besteht er bis zuletzt nicht, kommt der letzte Entwurf samt Grund zur
    Nacharbeit (wie bisher, nur eben erst nach mehreren Versuchen statt sofort).

    Gibt (ok, grund, texte, versuche) zurück. texte ist {} nur, wenn die KI gar
    keinen brauchbaren Text lieferte (personalize scheiterte).
    """
    feedback = ""
    letzte_texte, letzter_grund = {}, "kein Versuch"
    for versuch in range(1, max_versuche + 1):
        try:
            texte = personalize(lead, kunde, ki, webseiten_text, feedback=feedback)
        except ValueError as fehler:
            return False, str(fehler), {}, versuch
        ok, grund = check(texte, lead, kunde, ki)
        if ok:
            return True, grund, texte, versuch
        letzte_texte, letzter_grund, feedback = texte, grund, grund
    return False, letzter_grund, letzte_texte, max_versuche
