import json
from pathlib import Path
from urllib.parse import urlparse

# Erweiterungspunkt: Hier koennte nach dem Dedupe eine externe
# E-Mail-Verifizierung (z.B. MillionVerifier) haengen. v1 nutzt die
# eingebaute Pruefung von Instantly beim Import.

def _bekannte_emails(kunde_laeufe_dir) -> set:
    bekannte = set()
    for datei in Path(kunde_laeufe_dir).glob("*/leads.json"):
        for eintrag in json.loads(datei.read_text(encoding="utf-8")):
            bekannte.add(eintrag["email"].strip().lower())
    return bekannte

def _gesperrt(lead, sperrliste) -> bool:
    domains = {lead.email.split("@", 1)[-1]}
    if lead.website:
        netloc = urlparse(lead.website).netloc.lower()
        domains.add(netloc[4:] if netloc.startswith("www.") else netloc)
    for muster in sperrliste:
        muster = muster.strip().lower()
        for domain in domains:
            if muster.startswith("*.") and domain.endswith(muster[1:]):
                return True
            if domain == muster:
                return True
    return False

def dedupe(leads, kunde_laeufe_dir, sperrliste=()):
    bekannte = _bekannte_emails(kunde_laeufe_dir)
    gesehen, behalten, verworfen = set(), [], []
    for lead in leads:
        if _gesperrt(lead, sperrliste):
            verworfen.append({"email": lead.email, "grund": "Domain auf Sperrliste"})
        elif lead.email in gesehen:
            verworfen.append({"email": lead.email, "grund": "doppelt in dieser Liste"})
        elif lead.email in bekannte:
            verworfen.append({"email": lead.email,
                              "grund": "bereits in frueherem Lauf angeschrieben"})
        else:
            gesehen.add(lead.email)
            behalten.append(lead)
    return behalten, verworfen
