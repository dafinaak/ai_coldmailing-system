"""Stufe 2b der Lead-Beschaffung: aus einem Namen die gepruefte persoenliche
Mail bauen (Dropcontact).

Rolle im Ablauf (Weg A, "Zuverlaessigkeit zuerst", siehe AGENTS.md): Hunter
(Stufe 2a) hat den Entscheider gefunden - Name + Firma/Webseite. Dropcontact
ist der PRUEFER: aus first_name + last_name + Webseite baut es algorithmisch
die persoenliche Geschaefts-Mail und verifiziert sie gleich mit (Sitz in der
EU, DSGVO-/CNIL-konform, kein gespeicherter Datenbestand). Wir nehmen nur eine
persoenliche, gepruefte Adresse ("nominative@pro") - generische Adressen
(contact@/info@) deckt erst die info@-Regel ganz am Ende ab.

Warum Dropcontact NICHT der Sucher ist: aus einer reinen Domain ohne Namen
liefert es laut Doku nur Firmen-Info ("only_organization_data"), keine Person.
Es braucht den Namen als Eingabe - deshalb steht Hunter davor.

Live-Doku (developer.dropcontact.com, geprueft 2026-07-22):

Asynchron in zwei Schritten. Auth ueber Header "X-Access-Token: <KEY>",
nur application/json.

Schritt 1 - Batch abgeben:
    POST https://api.dropcontact.com/v1/enrich/all
    Body: {"data": [{"first_name","last_name","company","website"}],
           "siren": false, "language": "de"}
    Antwort (noch OHNE Ergebnis):
      {"error": false, "request_id": "...", "success": true, "credits_left": N}

Schritt 2 - per request_id pollen:
    GET https://api.dropcontact.com/v1/enrich/all/<request_id>
    Noch nicht fertig: {"error": false, "reason": "...try again...", "success": false}
    Fertig: {"error": false, "success": true, "data": [{
              "first_name","last_name","full_name",
              "email": [{"email": "...", "qualification": "nominative@pro"}],
              "job","nb_employees", ...}]}

"qualification" hat die Form "local@domain": local ist u.a. "nominative"
(persoenlich, z.B. vorname.nachname@) oder "generic" (contact@/info@); domain
ist "pro" (Firmen-Domain) oder "perso" (gmail o.ae.). Brauchbar als
Entscheider-Mail ist nur "nominative@pro".
"""
import time
import requests

ENRICH_URL = "https://api.dropcontact.com/v1/enrich/all"
# Nur diese Qualifizierung gilt als brauchbare persoenliche Firmen-Mail.
BRAUCHBARE_QUALIFIKATION = "nominative@pro"


def _beste_email(email_liste: list):
    """Waehlt aus Dropcontacts "email"-Liste die erste persoenliche,
    verifizierte Firmen-Adresse (nominative@pro). Gibt das {email,
    qualification}-Dict zurueck oder None, wenn nur generische/private
    Adressen (oder gar keine) dabei sind - dann hat die Firma fuer uns keine
    brauchbare persoenliche Mail und faellt weiter hinten in die info@-Regel."""
    for eintrag in email_liste or []:
        if eintrag.get("qualification") == BRAUCHBARE_QUALIFIKATION and eintrag.get("email"):
            return {"email": eintrag["email"], "qualification": eintrag["qualification"]}
    return None


class DropcontactSource:
    def __init__(self, api_key, session=None, wartezeit=5.0, max_abfragen=6):
        self.api_key = api_key
        self.session = session or requests.Session()
        self.wartezeit = wartezeit          # Sekunden zwischen den Abfragen
        self.max_abfragen = max_abfragen    # so oft wird auf das Ergebnis gepollt

    @property
    def _headers(self):
        return {"Content-Type": "application/json", "X-Access-Token": self.api_key}

    def email_bauen(self, first_name: str, last_name: str, website: str,
                    company: str = "") -> dict | None:
        """Baut aus Name + Webseite die gepruefte persoenliche Mail. Gibt
        {"email", "qualification"} zurueck oder None, wenn keine brauchbare
        persoenliche Adresse gefunden wurde. Wirft RuntimeError nur bei einem
        echten technischen Problem (abgelehnter Request, kein Ergebnis nach
        allen Abfragen) - das faengt die Firmen-Schleife in sourcing.py ab,
        ohne den ganzen Lauf zu reissen."""
        if not (first_name and last_name):
            return None
        request_id = self._abgeben(first_name, last_name, website, company)
        return self._ergebnis_holen(request_id)

    def _abgeben(self, first_name, last_name, website, company) -> str:
        body = {"data": [{"first_name": first_name, "last_name": last_name,
                          "company": company or "", "website": website or ""}],
                "siren": False, "language": "de"}
        antwort = self.session.post(ENRICH_URL, json=body, headers=self._headers, timeout=30)
        if antwort.status_code >= 400:
            raise RuntimeError(
                f"Dropcontact antwortet mit {antwort.status_code} auf {ENRICH_URL}: "
                f"{getattr(antwort, 'text', '')}")
        daten = antwort.json() or {}
        # error==true kommt z.B. bei aufgebrauchten Credits oder falschem Key -
        # das muss laut scheitern (wie der leere Apollo-Account frueher), nicht
        # still als "keine Mail" durchgehen und die Deckungsquote verfaelschen.
        if daten.get("error") or not daten.get("request_id"):
            grund = daten.get("reason") or daten.get("error") or "unbekannt"
            raise RuntimeError(f"Dropcontact lehnt den Batch ab: {grund}")
        return daten["request_id"]

    def _ergebnis_holen(self, request_id: str) -> dict | None:
        url = f"{ENRICH_URL}/{request_id}"
        for abfrage in range(1, self.max_abfragen + 1):
            antwort = self.session.get(url, headers=self._headers, timeout=30)
            if antwort.status_code >= 400:
                raise RuntimeError(
                    f"Dropcontact antwortet mit {antwort.status_code} auf {url}: "
                    f"{getattr(antwort, 'text', '')}")
            daten = antwort.json() or {}
            if daten.get("success") and daten.get("data") is not None:
                zeilen = daten["data"]
                return _beste_email(zeilen[0].get("email", [])) if zeilen else None
            # Noch nicht fertig ("Request not ready yet"): warten und erneut fragen.
            if abfrage < self.max_abfragen:
                time.sleep(self.wartezeit)
        raise RuntimeError(
            f"Dropcontact liefert nach {self.max_abfragen} Abfragen kein Ergebnis "
            f"(request_id {request_id})")
