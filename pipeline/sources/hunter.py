"""Stufe 2a der Lead-Beschaffung: den Entscheider einer Firma finden (Hunter).

Rolle im Ablauf (Weg A, "Zuverlaessigkeit zuerst", siehe AGENTS.md): Wir haben
aus Stufe 1 (Google Maps) nur Firma + Webseite, aber keinen Personennamen.
Hunter ist der SUCHER - es findet aus einer nackten Domain heraus, WER dort
Entscheider ist (Name + Position). Die gefundene Person geht danach an
Dropcontact (Stufe 2b), das daraus die gepruefte persoenliche Mail baut.

Warum Hunter fuer diesen Schritt und nicht Apollo/Dropcontact: Dropcontact
kann aus einer reinen Domain KEINEN unbekannten Entscheider entdecken (es
braucht den Namen als Eingabe). Apollo ist eine reine Kontakt-Datenbank und
bei kleinen deutschen Firmen schwach. Hunters Domain-Suche arbeitet genau von
der Domain aus - das ist unser Fall.

Live-Doku (hunter.io/api-documentation/v2, geprueft 2026-07-22):

Endpunkt "Domain Search":
    GET https://api.hunter.io/v2/domain-search?domain=<domain>&api_key=<KEY>
Auth: api_key als Query-Parameter (alternativ Header "X-API-KEY" oder
"Authorization: Bearer <KEY>" - hier bewusst der Query-Param, wie in der
Doku als Standard gezeigt). Reiner GET-Call.

Genutzte Parameter:
- "domain": die Firmen-Domain (aus Stufe 1 bereits ohne Schema/"www.").
- "type=personal": nur persoenliche Adressen (keine generischen wie info@ -
  die generische Ebene deckt bei uns erst die info@-Regel ganz am Ende ab).
- "limit": Obergrenze der zurueckgelieferten Personen (Default der API 10).

Antwort (data.emails[] - ein Objekt pro gefundener Person), relevante Felder:
  "value" (die E-Mail), "first_name", "last_name", "position", "seniority"
  (junior/senior/executive), "department", "confidence" (0-100),
  "decision_maker" (bool - Hunters fertige Entscheider-Einschaetzung),
  "verification": {"status": valid/invalid/accept_all/...}.
Keine Domain/keine Treffer: HTTP 200 mit data.emails == [] und
meta.results == 0 (kein Fehler - die Firma bleibt dann einfach ohne
Hunter-Treffer und faellt weiter hinten in die info@-Regel).

Credits: gemeinsamer Topf mit Email-Finder/-Verifier; Domain-Suche kostet
1 Credit je gefundener Mail (keine Treffer = keine Credits). Am Live-Konto
gegenpruefen, bevor es ins Mengengeruest einfliesst.
"""
import time
import requests

BASE_URL = "https://api.hunter.io/v2"
DOMAIN_SUCH_URL = f"{BASE_URL}/domain-search"
# Email Verifier (Live-Doku hunter.io/api-documentation/v2, geprueft
# 2026-07-23): GET /v2/email-verifier?email=...&api_key=... Antwort:
# data.status = valid/invalid/accept_all/webmail/disposable/unknown plus
# data.score (0-100). Sonderfaelle laut Doku: HTTP 202 = Pruefung laeuft
# noch (erneut fragen, zaehlt nur als eine Anfrage), HTTP 222 = SMTP-Server
# der Gegenseite antwortete unerwartet (spaeter erneut versuchen). Kosten:
# 0,5 Credits je Pruefung.
PRUEF_URL = f"{BASE_URL}/email-verifier"
STANDARD_LIMIT = 10
# Nur Treffer ab dieser Confidence gelten als brauchbar - ein sehr unsicherer
# Namens-/Mail-Treffer soll nicht als "Entscheider gefunden" durchgehen und
# spaeter eine unsaubere Adresse in den Versand ziehen (Zuverlaessigkeit zuerst).
MIN_CONFIDENCE = 50


def _rang(person: dict) -> tuple:
    """Sortierschluessel: erst Hunters Entscheider-Flag, dann Seniority
    (executive vor senior vor Rest), dann Confidence - so steht der
    wahrscheinlichste Entscheider vorn. Hoeher = besser, daher negiert
    fuer aufsteigende Standard-Sortierung."""
    seniority_rang = {"executive": 2, "senior": 1}.get(person.get("seniority"), 0)
    return (
        0 if person.get("decision_maker") else 1,
        -seniority_rang,
        -(person.get("confidence") or 0),
    )


class HunterSource:
    def __init__(self, api_key, session=None, wartezeit=2.0, max_versuche=3):
        self.api_key = api_key
        self.session = session or requests.Session()
        self.wartezeit = wartezeit
        self.max_versuche = max_versuche

    def _get(self, params: dict, url: str = DOMAIN_SUCH_URL,
             auch_wiederholen: tuple = ()):
        """GET mit einfachem Wiederholen bei 429/5xx (wie ApolloSource): ein
        einzelner Schluckauf der API soll nicht sofort die ganze Firma
        verlieren. Bei 4xx (ausser 429) sofort Fehler - das ist ein echtes
        Problem (falscher Key o.ae.), das lautes Scheitern verdient.
        `auch_wiederholen` ergaenzt endpunkt-eigene Warte-Codes (der
        Email Verifier nutzt 202 = laeuft noch und 222 = SMTP-Problem)."""
        for versuch in range(1, self.max_versuche + 1):
            antwort = self.session.get(url, params=params, timeout=30)
            if antwort.status_code < 400 and antwort.status_code not in auch_wiederholen:
                return antwort
            if (antwort.status_code == 429 or antwort.status_code >= 500
                    or antwort.status_code in auch_wiederholen):
                if versuch < self.max_versuche:
                    time.sleep(self.wartezeit)
                    continue
            raise RuntimeError(
                f"Hunter antwortet mit {antwort.status_code} auf {url}: "
                f"{getattr(antwort, 'text', '')}")
        raise RuntimeError(
            f"Hunter antwortet nach {self.max_versuche} Versuchen weiter mit "
            f"{antwort.status_code} auf {url}")

    def entscheider_finden(self, domain: str, limit: int = STANDARD_LIMIT) -> list:
        """Findet die persoenlichen Kontakte einer Domain und gibt sie nach
        Entscheider-Wahrscheinlichkeit sortiert zurueck. Jeder Eintrag:
        {"first_name", "last_name", "title", "email", "confidence",
        "decision_maker", "verification_status"}. Leere Liste, wenn Hunter
        die Domain nicht kennt oder nur unbrauchbare (zu unsichere/namenlose)
        Treffer hat - dann bleibt die Firma ohne Hunter-Kontakt."""
        if not domain:
            return []
        antwort = self._get({"domain": domain, "api_key": self.api_key,
                             "type": "personal", "limit": limit})
        daten = (antwort.json() or {}).get("data") or {}
        personen = []
        for e in daten.get("emails", []):
            # Ohne Namen ist es fuer eine persoenliche Ansprache wertlos, und
            # ein zu unsicherer Treffer soll gar nicht erst weiterlaufen.
            if not (e.get("first_name") and e.get("last_name")):
                continue
            if (e.get("confidence") or 0) < MIN_CONFIDENCE:
                continue
            personen.append({
                "first_name": e.get("first_name", ""),
                "last_name": e.get("last_name", ""),
                "title": e.get("position", "") or "",
                "email": e.get("value", "") or "",
                "confidence": e.get("confidence") or 0,
                "decision_maker": bool(e.get("decision_maker")),
                "verification_status": (e.get("verification") or {}).get("status", ""),
            })
        personen.sort(key=_rang)
        return personen

    def email_pruefen(self, email: str) -> dict | None:
        """Prueft eine einzelne Adresse ueber Hunters Email Verifier (0,5
        Credits). Gibt {"status", "score"} zurueck (status: valid/invalid/
        accept_all/webmail/disposable/unknown). Zweck in der Kaskade: die
        info@-Rueckfallebene darf laut Projektregel nur GEPRUEFTE Adressen in
        den Versand geben - Ruecklaeufer schaedigen die Absender-Postfaecher.
        202 (laeuft noch) und 222 (SMTP-Problem der Gegenseite) werden mit
        Wartezeit wiederholt und scheitern danach laut."""
        if not email:
            return None
        antwort = self._get({"email": email, "api_key": self.api_key},
                            url=PRUEF_URL, auch_wiederholen=(202, 222))
        daten = (antwort.json() or {}).get("data") or {}
        return {"status": daten.get("status", ""), "score": daten.get("score") or 0}
