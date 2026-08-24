"""Ohne ausdrückliche menschliche Freigabe geht keine Kampagne los.

Auftrag Dafinas vom 21.08.2026, nachdem zwei Betroffene (Björn Hagen,
Achim Gärtner) Mails bekommen hatten und ihre Streichung verlangten.
Die Projektregel dazu steht seit 17.08.2026 in AGENTS.md - sie stand
aber nur im Text, nicht im Code.

Der Ablauf, den dieses Modul erzwingt:

    Kampagne fertig
      -> PAUSIERT / WARTET AUF FREIGABE
      -> Ein Mensch gibt AUSDRÜCKLICH frei (Name + Zeitpunkt + Kampagne)
      -> erst dann darf aktiviert/gesendet werden

Zwei Dinge, die ausdrücklich NICHT als Freigabe gelten:
  - eine Kampagne anzulegen,
  - Texte freizugeben (das ist die Freigabe der TEXTE, nicht des Versands).

Die Freigabe hängt an der konkreten campaign_id. Eine Freigabe für
Kampagne A erlaubt nichts bei Kampagne B, und eine widerrufene Freigabe
erlaubt gar nichts mehr.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

DATEINAME = "versand-freigabe.json"


class VersandGesperrt(RuntimeError):
    """Es sollte gesendet/aktiviert werden, ohne dass ein Mensch das
    ausdrücklich für genau diese Kampagne freigegeben hat."""


def pfad(lauf_dir) -> Path:
    return Path(lauf_dir) / DATEINAME


def erteilen(lauf_dir, campaign_id: str, nutzer: str,
             bemerkung: str = "") -> dict:
    """Die ausdrückliche Freigabe eines Menschen festhalten.

    Diese Funktion darf NUR aus einer bewussten menschlichen Handlung
    heraus aufgerufen werden (bestätigter Knopf in der Oberfläche, oder
    der eigene CLI-Befehl mit getippter Kampagnen-Kennung). Sie niemals
    "zur Sicherheit" im Ablauf mitlaufen lassen - dann wäre sie keine
    Freigabe mehr, sondern Dekoration.
    """
    if not str(campaign_id or "").strip():
        raise ValueError("Freigabe ohne Kampagnen-Kennung ist keine Freigabe.")
    if not str(nutzer or "").strip():
        raise ValueError("Freigabe ohne Namen ist keine Freigabe.")
    eintrag = {
        "campaign_id": str(campaign_id).strip(),
        "freigegeben_von": str(nutzer).strip(),
        "freigegeben_am": datetime.now().isoformat(timespec="seconds"),
        "bemerkung": str(bemerkung or ""),
        "widerrufen": False,
    }
    ziel = pfad(lauf_dir)
    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_text(json.dumps(eintrag, ensure_ascii=False, indent=1),
                    encoding="utf-8")
    return eintrag


def widerrufen(lauf_dir, nutzer: str) -> dict | None:
    """Eine erteilte Freigabe zurücknehmen. Danach ist wieder gesperrt."""
    eintrag = lesen(lauf_dir)
    if eintrag is None:
        return None
    eintrag["widerrufen"] = True
    eintrag["widerrufen_von"] = str(nutzer or "")
    eintrag["widerrufen_am"] = datetime.now().isoformat(timespec="seconds")
    pfad(lauf_dir).write_text(json.dumps(eintrag, ensure_ascii=False, indent=1),
                              encoding="utf-8")
    return eintrag


def lesen(lauf_dir) -> dict | None:
    ziel = pfad(lauf_dir)
    if not ziel.exists():
        return None
    try:
        eintrag = json.loads(ziel.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        # Eine unlesbare Freigabe ist KEINE Freigabe.
        return None
    return eintrag if isinstance(eintrag, dict) else None


def ist_freigegeben(lauf_dir, campaign_id: str) -> bool:
    eintrag = lesen(lauf_dir)
    if not eintrag or eintrag.get("widerrufen"):
        return False
    if not eintrag.get("freigegeben_von"):
        return False
    return str(eintrag.get("campaign_id") or "") == str(campaign_id or "")


def pruefen(lauf_dir, campaign_id: str) -> dict:
    """Gibt die gültige Freigabe zurück - oder wirft VersandGesperrt.

    Das ist die Form, die im Ablauf benutzt wird: wer nicht freigegeben
    ist, kommt hier nicht vorbei.
    """
    eintrag = lesen(lauf_dir)
    if eintrag is None:
        raise VersandGesperrt(
            f"Kein Versand: für diese Kampagne ({campaign_id}) liegt keine "
            f"Freigabe vor. Eine Kampagne anzulegen ist KEINE Freigabe - "
            f"ein Mensch muss den Versand ausdrücklich freigeben.")
    if eintrag.get("widerrufen"):
        raise VersandGesperrt(
            f"Kein Versand: die Freigabe für {campaign_id} wurde am "
            f"{eintrag.get('widerrufen_am', '?')} widerrufen.")
    if str(eintrag.get("campaign_id") or "") != str(campaign_id or ""):
        raise VersandGesperrt(
            f"Kein Versand: die vorliegende Freigabe gilt für Kampagne "
            f"{eintrag.get('campaign_id')!r}, gesendet werden soll aber "
            f"{campaign_id!r}. Eine Freigabe gilt immer nur für genau "
            f"eine Kampagne.")
    if not eintrag.get("freigegeben_von"):
        raise VersandGesperrt(
            f"Kein Versand: die Freigabe für {campaign_id} nennt keinen "
            f"Menschen, der sie erteilt hat.")
    return eintrag
