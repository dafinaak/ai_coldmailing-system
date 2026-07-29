"""KI-Baustein: schickt System- und User-Prompt an ein Sprachmodell und
liefert den reinen Antworttext zurueck.

Zwei Anbieter werden unterstuetzt, ausgewaehlt an der Schluessel-Weiche in
__init__() - je nachdem, welche Umgebungsvariable gesetzt ist:

- OPENROUTER_API_KEY gesetzt -> OpenRouter (https://openrouter.ai), ein
  Zwischendienst, der viele Modelle (auch Claude) im OpenAI-Chat-Format
  anbietet. Wird per einfachem requests-POST angesprochen (kein SDK noetig),
  gleiches Muster wie pipeline/senders/instantly.py (Bearer-Header, eigene
  Session zum Testen injizierbar).
- sonst ANTHROPIC_API_KEY gesetzt -> direkter Anthropic-SDK-Pfad wie bisher.
- sonst OPENAI_API_KEY gesetzt -> OpenAI direkt (gleicher Chat-Format-Pfad
  wie OpenRouter, nur andere URL; ergaenzt 29.07.2026 als Ersatz fuer den
  ungueltig gewordenen OpenRouter-Zugang). Der Claude-Default wird hier
  auf "gpt-4o-mini" gemappt; ein gesetztes KI_MODELL gilt unveraendert.
- keiner gesetzt -> RuntimeError schon bei der Konstruktion, mit klarer
  deutscher Meldung (kein spaeter, unklarer Fehler erst beim ersten
  frage()-Aufruf).

Modell-Auswahl ueber KI_MODELL (wie bisher), Default "claude-sonnet-5". Auf
dem OpenRouter-Pfad brauchen Modell-Slugs einen Anbieter-Prefix (z.B.
"anthropic/claude-sonnet-5") - fehlt der Slash, wird "anthropic/"
automatisch vorangestellt, damit der bisherige Default weiterhin
funktioniert. Slug gegen die oeffentliche Modell-Liste (GET
https://openrouter.ai/api/v1/models, Stand 2026-07-17) geprueft:
"anthropic/claude-sonnet-5" existiert dort exakt so."""
import os
import requests
import anthropic

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENAI_URL = "https://api.openai.com/v1/chat/completions"
OPENAI_STANDARD_MODELL = "gpt-4o-mini"

class KI:
    def __init__(self, model: str | None = None, session=None):
        modell_roh = model or os.environ.get("KI_MODELL", "claude-sonnet-5")
        openrouter_key = os.environ.get("OPENROUTER_API_KEY")
        anthropic_key = os.environ.get("ANTHROPIC_API_KEY")

        if openrouter_key:
            self.anbieter = "openrouter"
            self.model = modell_roh if "/" in modell_roh else f"anthropic/{modell_roh}"
            self.session = session or requests.Session()
            self.headers = {"Authorization": f"Bearer {openrouter_key}",
                            "Content-Type": "application/json"}
        elif anthropic_key:
            self.anbieter = "anthropic"
            self.model = modell_roh
            self.client = anthropic.Anthropic()  # liest ANTHROPIC_API_KEY
        elif os.environ.get("OPENAI_API_KEY"):
            self.anbieter = "openai"
            # Der projektweite Claude-Default existiert bei OpenAI nicht -
            # gemappt auf das dortige kleine Standard-Modell; ein bewusst
            # gesetztes KI_MODELL bleibt unangetastet.
            self.model = OPENAI_STANDARD_MODELL if not model and \
                not os.environ.get("KI_MODELL") else modell_roh
            self.session = session or requests.Session()
            self.headers = {"Authorization":
                            f"Bearer {os.environ['OPENAI_API_KEY']}",
                            "Content-Type": "application/json"}
        else:
            raise RuntimeError(
                "Kein KI-Schlüssel gefunden: weder OPENROUTER_API_KEY noch "
                "ANTHROPIC_API_KEY noch OPENAI_API_KEY ist gesetzt. Bitte "
                "in .env eintragen (siehe .env.example).")

    def frage(self, system: str, prompt: str) -> str:
        if self.anbieter in ("openrouter", "openai"):
            # 4000 statt 1500: bei Modellen mit eingebautem "Nachdenken"
            # zaehlt das interne Denken mit ins Budget - 1500 fuehrte zu
            # mitten im Satz abgeschnittenen Antworten (Fund 17.07.2026).
            payload = {
                "model": self.model,
                "max_tokens": 4000,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
            }
            url, name = ((OPENROUTER_URL, "OpenRouter")
                         if self.anbieter == "openrouter"
                         else (OPENAI_URL, "OpenAI"))
            antwort = self.session.post(url, headers=self.headers,
                                        json=payload, timeout=60)
            if antwort.status_code >= 400:
                ausschnitt = (getattr(antwort, "text", "") or "")[:200]
                raise RuntimeError(
                    f"{name} antwortet mit {antwort.status_code}: {ausschnitt}")
            return antwort.json()["choices"][0]["message"]["content"]

        antwort = self.client.messages.create(
            model=self.model, max_tokens=4000, system=system,
            messages=[{"role": "user", "content": prompt}])
        return antwort.content[0].text
