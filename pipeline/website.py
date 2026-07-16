import re
import requests

def _sichtbarer_text(html: str) -> str:
    html = re.sub(r"(?s)<(script|style|noscript).*?</\1>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", text).strip()

def fetch_text(url: str, max_zeichen: int = 5000) -> str:
    if not url:
        return ""
    try:
        antwort = requests.get(url, timeout=15,
                               headers={"User-Agent": "Mozilla/5.0 (Recherche)"})
        antwort.raise_for_status()
        return _sichtbarer_text(antwort.text)[:max_zeichen]
    except requests.RequestException:
        return ""
