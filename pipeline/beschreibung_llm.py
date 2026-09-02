"""Kurz-Beschreibung einer Firma aus dem schon gelesenen Webtext.

Olivers DataWarehouse-Liste hat ein Feld "Kurz-Beschreibung". Es war zu
100% leer. Der Text der Firmen-Webseite liegt aber bereits auf der Platte
- die Laeufe speichern ihn in 01-webtext.json - es muss also nichts neu
geladen werden, nur zusammengefasst.

Regeln, die hier wichtiger sind als eine huebsche Formulierung:

  - Ein Satz, hoechstens 200 Zeichen. Das Feld ist eine Kurz-Beschreibung,
    keine Firmengeschichte.
  - NUR was auf der Seite steht. Keine Vermutungen ueber Groesse, Qualitaet
    oder Kundschaft - das Feld landet bei Oliver und muss stimmen.
  - Kein Werbeton. "Fuehrender Anbieter" ist die Selbstbeschreibung der
    Firma, keine Tatsache.
  - Zu wenig Text -> leer. Ein erfundener Satz ist schlechter als ein
    leeres Feld.
"""
from __future__ import annotations

# Unter dieser Textlaenge ist eine Seite praktisch unlesbar (Cookie-Banner,
# reines Menue) und jede Zusammenfassung waere geraten. Derselbe Gedanke
# wie MIN_BELEG bei der Automatisierungs-Pruefung.
MIN_TEXT = 300

# So viel Text bekommt das Modell. Der Anfang einer Firmenseite sagt, was
# die Firma tut; weiter unten kommen Impressum und Rechtstexte, die nichts
# beitragen und nur Tokens kosten.
MAX_TEXT = 1500

MAX_LAENGE = 200

SYSTEM_PROMPT = (
    "Du fasst zusammen, was eine Firma laut ihrer eigenen Webseite tut. "
    "Antworte mit EINEM deutschen Satz, hoechstens 200 Zeichen. "
    "Nenne nur, was im Text steht: Taetigkeit, Leistungen, Branche. "
    "Keine Werbesprache, keine Bewertung, keine Vermutungen ueber Groesse "
    "oder Kundschaft. Wenn der Text zu wenig hergibt, antworte genau mit: "
    "UNKLAR"
)


def _saeubern(antwort: str) -> str:
    """Ein Satz, ohne Anfuehrungszeichen, hoechstens MAX_LAENGE Zeichen."""
    text = " ".join(str(antwort or "").split()).strip().strip('"').strip()
    if not text or text.upper().startswith("UNKLAR"):
        return ""
    if len(text) > MAX_LAENGE:
        # Lieber am letzten Satzende abschneiden als mitten im Wort.
        schnitt = text[:MAX_LAENGE]
        punkt = schnitt.rfind(". ")
        text = (schnitt[:punkt + 1] if punkt > 60
                else schnitt.rsplit(" ", 1)[0] + " …")
    return text


def beschreiben(ki, name: str, webtext: str) -> str:
    """Ein Satz zu dieser Firma - oder leer, wenn der Text zu duenn ist."""
    text = (webtext or "").strip()
    if len(text) < MIN_TEXT:
        return ""
    prompt = (f"Firma: {name}\n\n"
              f"Text der Webseite:\n{text[:MAX_TEXT]}")
    try:
        return _saeubern(ki.frage(SYSTEM_PROMPT, prompt))
    except Exception:                    # noqa: BLE001
        # Ein Ausfall darf den Lauf nicht abbrechen - das Feld bleibt leer
        # und kann beim naechsten Durchgang nachgeholt werden.
        return ""
