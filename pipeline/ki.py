import os
import anthropic

class KI:
    def __init__(self, model: str | None = None):
        self.model = model or os.environ.get("KI_MODELL", "claude-sonnet-5")
        self.client = anthropic.Anthropic()  # liest ANTHROPIC_API_KEY

    def frage(self, system: str, prompt: str) -> str:
        antwort = self.client.messages.create(
            model=self.model, max_tokens=1500, system=system,
            messages=[{"role": "user", "content": prompt}])
        return antwort.content[0].text
