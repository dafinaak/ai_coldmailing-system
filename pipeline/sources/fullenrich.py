"""FullEnrich - Anbieter im Test (POC, 24.08.2026).

FullEnrich ist selbst eine Wasserfall-Plattform: sie fragt nach eigener
Angabe 20+ Datenquellen ab und liefert E-Mails und Telefonnummern
zurueck. Dieser Baustein ist NUR fuer den 100-Firmen-Vergleich gebaut -
Apollo, Hunter und Dropcontact bleiben unangetastet.

Live-Doku (docs.fullenrich.com, geprueft 24.08.2026):

Basis-URL   https://app.fullenrich.com/api/v2
Auth        Header "Authorization: Bearer <KEY>", Content-Type json
Rate-Limit  60 API-Aufrufe pro Minute, ueber ALLE Endpunkte zusammen

Endpunkte, die dieser Baustein nutzt:

1. Firma finden
   POST /company/lookup
   Body: {"domain": "beispiel.de"}   (oder professional_network_url/-id)
   Antwort: bestpassende Firma + Metadaten.

2. Entscheider suchen
   POST /people/search
   Body: {"current_company_domains": ["beispiel.de"],
          "current_position_titles": ["CEO", "Geschaeftsfuehrer", ...],
          "limit": 25}
   Filter-Logik laut Doku: INNERHALB eines Feldes ODER, ZWISCHEN den
   Feldern UND. Also "einer dieser Titel UND diese Firmen-Domain".
   Antwort: {"people": [Person]} - Person traegt full_name,
   first_name, last_name, headline, location, social_profiles und
   employment[] (title, seniority, company, is_current).

3. Kontaktdaten anreichern (asynchron, zwei Schritte)
   POST /contact/enrich/bulk
   Body: {"name": "...", "data": [{"first_name", "last_name",
          "domain", "company_name", "linkedin_url"?,
          "enrich_fields": ["contact.work_emails",
                            "contact.personal_emails", "contact.phones"],
          "custom": {...}}]}
   Antwort: {"enrichment_id": "..."}
   GET /contact/enrich/bulk/<enrichment_id>
   Antwort: {"id","name","status","data":[...],"cost":{"credits":N}}
   status: CREATED | IN_PROGRESS | CANCELED | CREDITS_INSUFFICIENT |
           FINISHED | RATE_LIMIT | UNKNOWN

Kosten laut Doku (Abschnitt "Credits & Testing Tips"): Credits werden
NUR verbraucht, wenn wirklich etwas gefunden wird.
   gefundene E-Mail (Deliverable/High Probability/Catch-all): 1 Credit
   gefundene persoenliche E-Mail:                             3 Credits
   gefundene Mobilnummer:                                    10 Credits

E-Mail-Status: DELIVERABLE | HIGH_PROBABILITY | CATCH_ALL | INVALID |
INVALID_DOMAIN.

WICHTIG fuer die Auswertung: das Phone-Objekt der Antwort traegt nur
"number" und "region" - die API sagt NICHT, ob eine Nummer mobil oder
Festnetz ist. Die Einordnung machen wir selbst an der Vorwahl
(pipeline/fullenrich_poc.py), und der Bericht weist das aus.
"""
import re
import time

import requests

BASIS_URL = "https://app.fullenrich.com/api/v2"
COMPANY_LOOKUP_URL = f"{BASIS_URL}/company/lookup"
PEOPLE_SEARCH_URL = f"{BASIS_URL}/people/search"
ENRICH_BULK_URL = f"{BASIS_URL}/contact/enrich/bulk"
GUTHABEN_URL = f"{BASIS_URL}/account/credits"
SCHLUESSEL_URL = f"{BASIS_URL}/account/keys/verify"

# Was FullEnrich unter den beiden Mail-Arten versteht (Data Dictionary,
# geprueft 24.08.2026) - der Unterschied ist fuer Olivers Anforderung
# entscheidend:
#   work_emails      "Verified professional email", Beispiel
#                    greg@fullenrich.com  -> die GESCHAEFTLICHE Adresse
#   personal_emails  "Verified personal email", Beispiel
#                    greg.demoge@gmail.com -> die PRIVATE Adresse
# Oliver will die personenbezogene GESCHAEFTS-Adresse
# (t.cappelmann@airitsystems.de). Das ist FullEnrichs work_email, NICHT
# deren personal_email. Deshalb wird zusaetzlich geprueft, ob eine
# work_email personenbezogen oder eine Sammeladresse ist.
SAMMEL_PRAEFIXE = (
    "info", "office", "kontakt", "contact", "support", "sales", "service",
    "mail", "email", "hallo", "hello", "team", "buero", "buro", "zentrale",
    "empfang", "anfrage", "post", "webmaster", "admin", "noreply",
    "no-reply", "verwaltung", "sekretariat", "bestellung", "vertrieb",
)

# Laut Doku 60 Aufrufe pro Minute ueber alle Endpunkte. Wir bleiben
# bewusst darunter, damit ein paralleler Lauf nicht ins Limit rennt.
LIMIT_PRO_MINUTE = 60

# Diese Felder wollen wir anreichern lassen - genau die drei aus der Doku.
ENRICH_FELDER = ["contact.work_emails", "contact.personal_emails",
                 "contact.phones"]

# Preise laut Doku, Abschnitt "Credits & Testing Tips" (24.08.2026).
# WICHTIG: auch die SUCHE kostet - 0,25 Credits je zurueckgegebener
# Person oder Firma. Genau deshalb ist SUCH_LIMIT klein: mit dem
# frueheren Standard 25 haette allein die Personensuche bis zu 6,25
# Credits je Firma verbrannt, bevor ueberhaupt etwas angereichert wird.
PREIS_SUCHTREFFER = 0.25
PREIS_MAIL = 1
PREIS_PERSOENLICHE_MAIL = 3
PREIS_MOBIL = 10
SUCH_LIMIT = 10

# Von FullEnrich fest hinterlegter Testkontakt. Kostet laut Doku 0
# Credits - damit laesst sich ein Schluessel pruefen, ohne Guthaben
# anzufassen. Die Daten muessen EXAKT so uebergeben werden.
TESTKONTAKT = {
    "first_name": "Grégoire",
    "last_name": "Démogé",
    "domain": "fullenrich.com",
    "company_name": "FullEnrich",
    "linkedin_url": "https://www.linkedin.com/in/demoge/",
}

# Nur diese E-Mail-Zustaende gelten uns als brauchbar. INVALID und
# INVALID_DOMAIN fliegen raus; CATCH_ALL bleibt drin, wird aber im
# Bericht getrennt ausgewiesen (der Server nimmt dort ALLES an, das ist
# also ein schwaecherer Beleg als DELIVERABLE).
BRAUCHBARE_MAIL_STATUS = ("DELIVERABLE", "HIGH_PROBABILITY", "CATCH_ALL")

_SCHEMA_WEG = re.compile(r"^[a-z]+://", re.I)


def nur_domain(wert) -> str:
    """"https://www.Beispiel.de/impressum" -> "beispiel.de".

    Die Doku will im Feld "domain" die nackte Domain (Beispiel dort:
    anthropic.com). Eine ganze URL waere ein stiller Fehlschlag: der
    Aufruf ginge durch, faende aber nichts."""
    text = _SCHEMA_WEG.sub("", str(wert or "").strip().lower())
    text = text.split("/")[0].split("?")[0].split("#")[0]
    if text.startswith("www."):
        text = text[4:]
    return text.strip().strip(".")
STARKE_MAIL_STATUS = ("DELIVERABLE", "HIGH_PROBABILITY")

# Nur diese HTTP-Codes werden wiederholt: Ratenlimit und Serverfehler.
# 400/401/402/404 aendern sich beim zweiten Versuch nicht.
_WIEDERHOLBAR = (429, 500, 502, 503, 504)

# Endzustaende des Anreicherungs-Auftrags.
FERTIG_STATUS = ("FINISHED", "CANCELED", "CREDITS_INSUFFICIENT")


class FullEnrichFehler(RuntimeError):
    """Ein Aufruf ist fehlgeschlagen. Traegt den HTTP-Code mit, damit der
    Aufrufer 401 (Schluessel falsch) von 429 (Limit) unterscheiden kann."""

    def __init__(self, nachricht, status=None, code=None):
        super().__init__(nachricht)
        self.status = status
        self.code = code


class KontingentLeer(FullEnrichFehler):
    """Guthaben aufgebraucht - weiterlaufen waere sinnlos."""


def _fehlertext(antwort) -> tuple:
    """(text, code) aus einer Fehlerantwort - ohne Header, ohne Schluessel."""
    try:
        daten = antwort.json() or {}
    except Exception:      # noqa: BLE001 - kaputtes JSON ist auch ein Fehler
        return (getattr(antwort, "text", "") or "")[:200], None
    return str(daten.get("message") or daten.get("code") or "")[:200], \
        daten.get("code")


class FullEnrichSource:
    """Duenner Mantel um die drei Endpunkte, die der POC braucht.

    session ist injizierbar, damit die Tests ohne Netz und ohne Credits
    laufen. Der API-Schluessel wird nie geloggt und nie zurueckgegeben.
    """

    def __init__(self, api_key, session=None, *, wartezeit=5.0,
                 max_abfragen=60, limit_pro_minute=LIMIT_PRO_MINUTE,
                 schlafen=time.sleep, jetzt=time.monotonic,
                 max_wiederholungen=3, pause_bei_limit=61.0,
                 pause_bei_serverfehler=2.0):
        if not api_key:
            raise FullEnrichFehler(
                "FULLENRICH_API_KEY fehlt. Bitte in .env eintragen "
                "(siehe .env.example).")
        self._api_key = api_key
        self.session = session or requests.Session()
        self.wartezeit = wartezeit
        self.max_abfragen = max_abfragen
        self.limit_pro_minute = max(1, int(limit_pro_minute))
        self.max_wiederholungen = max(1, int(max_wiederholungen))
        self.pause_bei_limit = pause_bei_limit
        self.pause_bei_serverfehler = pause_bei_serverfehler
        self._schlafen = schlafen
        self._jetzt = jetzt
        self._aufrufe: list = []

    # ------------------------------------------------------------ intern

    @property
    def _headers(self):
        return {"Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json"}

    def _limit_einhalten(self):
        """Hoechstens limit_pro_minute Aufrufe je gleitende Minute.

        Kein fester Schlaf zwischen Aufrufen: gewartet wird nur, wenn das
        Fenster wirklich voll ist. Damit bleibt ein kleiner Lauf schnell
        und ein grosser trotzdem innerhalb des dokumentierten Limits."""
        jetzt = self._jetzt()
        self._aufrufe = [t for t in self._aufrufe if jetzt - t < 60.0]
        if len(self._aufrufe) >= self.limit_pro_minute:
            pause = 60.0 - (jetzt - self._aufrufe[0]) + 0.05
            if pause > 0:
                self._schlafen(pause)
            jetzt = self._jetzt()
            self._aufrufe = [t for t in self._aufrufe if jetzt - t < 60.0]
        self._aufrufe.append(self._jetzt())

    def _pruefen(self, antwort, was):
        code = getattr(antwort, "status_code", 0)
        if code < 400:
            return
        text, fehlercode = _fehlertext(antwort)
        if code == 401:
            raise FullEnrichFehler(
                f"FullEnrich lehnt den Schlüssel ab ({was}): {text}",
                status=code, code=fehlercode)
        if code == 402:
            # Gemessen am 24.08.2026: bei 13,25 Credits antwortete die
            # API auf das Abholen einer Anreicherung mit 402. Das heisst
            # nicht "kaputt", sondern "Guthaben reicht nicht" - und dann
            # hat Weiterlaufen keinen Sinn.
            raise KontingentLeer(
                f"FullEnrich meldet 402 Payment Required ({was}): "
                f"{text or 'Guthaben reicht für diese Anreicherung nicht'}",
                status=code, code=fehlercode)
        if code == 429:
            raise FullEnrichFehler(
                f"FullEnrich-Ratenlimit erreicht ({was}): {text}",
                status=code, code=fehlercode)
        raise FullEnrichFehler(
            f"FullEnrich antwortet mit {code} ({was}): {text}",
            status=code, code=fehlercode)

    def _mit_wiederholung(self, aufruf, was):
        """Begrenzte Wiederholung bei 429 und 5xx.

        Die Doku nennt keine eigene Retry-Empfehlung, nur das Limit von
        60 Aufrufen je Kalenderminute. Deshalb bewusst zurueckhaltend:
        wiederholt wird NUR bei Ratenlimit und Serverfehlern, mit
        wachsender Pause. Bei 401 (Schluessel), 402 (Guthaben) und 400
        (falsche Anfrage) waere Wiederholen sinnlos - das aendert sich
        beim zweiten Versuch nicht."""
        letzter = None
        for versuch in range(1, self.max_wiederholungen + 1):
            antwort = aufruf()
            code = getattr(antwort, "status_code", 0)
            if code < 400 or code not in _WIEDERHOLBAR:
                return antwort
            letzter = antwort
            if versuch < self.max_wiederholungen:
                # 429 heisst laut Doku: das Minutenfenster ist voll. Dann
                # lohnt nur eine Pause bis zum naechsten Fenster.
                pause = (self.pause_bei_limit if code == 429
                         else self.pause_bei_serverfehler * versuch)
                self._schlafen(pause)
        return letzter

    def _post(self, url, body, was):
        def einmal():
            self._limit_einhalten()
            return self.session.post(url, json=body, headers=self._headers,
                                     timeout=60)

        antwort = self._mit_wiederholung(einmal, was)
        self._pruefen(antwort, was)
        return antwort.json() or {}

    # ---------------------------------------------------------- 1. Firma

    def firma_finden(self, domain: str) -> dict | None:
        """POST /company/lookup - beste Treffer-Firma zu einer Domain.

        None, wenn FullEnrich die Firma nicht kennt. Ein 404 gilt hier
        als "nicht gefunden", nicht als Fehler - eine unbekannte Firma
        ist ein normales Ergebnis dieses Tests."""
        domain = nur_domain(domain)
        if not domain:
            return None
        def einmal():
            self._limit_einhalten()
            return self.session.post(COMPANY_LOOKUP_URL,
                                     json={"domain": domain},
                                     headers=self._headers, timeout=60)

        antwort = self._mit_wiederholung(einmal, "company/lookup")
        if getattr(antwort, "status_code", 0) == 404:
            return None
        self._pruefen(antwort, "company/lookup")
        daten = antwort.json() or {}
        # Gemessene Antwortform (echter Aufruf 24.08.2026):
        #   {"companies": [ {id,name,website,domain,description,...} ],
        #    "metadata": {...}}
        # Frueher wurde hier faelschlich ein Einzelobjekt unter "company"
        # erwartet - dadurch fand der Firmen-Abgleich KEIN Feld und jede
        # Firma landete auf "uncertain", obwohl sie sauber gefunden war.
        liste = daten.get("companies")
        if isinstance(liste, list) and liste:
            erste = liste[0]
            return erste if isinstance(erste, dict) else None
        if isinstance(daten.get("company"), dict):
            return daten["company"]
        # Manche Antworten liefern die Firma flach - nur akzeptieren,
        # wenn wirklich Firmenfelder drinstehen, sonst gilt sie als
        # nicht gefunden statt als leerer Treffer.
        if daten.get("domain") or daten.get("name"):
            return daten
        return None

    # -------------------------------------------------------- 2. Personen

    def personen_suchen(self, domain: str, titel: list,
                        limit: int = SUCH_LIMIT) -> list:
        """POST /people/search - Entscheider EINER Firma.

        Die Domain-Einschraenkung ist entscheidend: ohne sie kaeme ein
        beliebiger "CEO" aus der ganzen Datenbank zurueck. Laut Doku
        wirkt sie als UND zu den Titeln."""
        domain = nur_domain(domain)
        if not domain:
            return []
        # Die Filter sind KEINE Listen von Strings, sondern Listen von
        # Objekten {"value", "exact_match", "exclude"}. Eine Liste von
        # Strings quittiert die API mit 400 ("cannot unmarshal string
        # into Go struct field") - Fund im ersten echten Lauf 24.08.2026.
        # Domain exakt (Doku: "Exact match recommended for domains"),
        # Titel bewusst unscharf, damit "Geschäftsführer" auch
        # "Geschäftsführender Gesellschafter" trifft.
        body = {"current_company_domains": [
                    {"value": domain, "exact_match": True}],
                "limit": max(1, min(int(limit), 100))}
        if titel:
            body["current_position_titles"] = [
                {"value": str(t), "exact_match": False} for t in titel]
        daten = self._post(PEOPLE_SEARCH_URL, body, "people/search")
        leute = daten.get("people")
        return list(leute) if isinstance(leute, list) else []

    # ------------------------------------------------------ 3. Kontaktdaten

    def anreicherung_starten(self, eintraege: list, name: str) -> str | None:
        """POST /contact/enrich/bulk - gibt die enrichment_id zurueck.

        Bewusst von der Abholung getrennt: sobald das hier zurueckkommt,
        laeuft der Auftrag. Der Aufrufer soll die ID wegschreiben, damit
        ein Absturz Zeit kostet, aber keine Credits (gleiches Muster wie
        bei Dropcontact)."""
        daten_block = []
        for eintrag in eintraege:
            satz = {
                "first_name": eintrag.get("first_name", ""),
                "last_name": eintrag.get("last_name", ""),
                "domain": eintrag.get("domain", ""),
                "company_name": eintrag.get("company_name", ""),
                "enrich_fields": list(ENRICH_FELDER),
            }
            if eintrag.get("linkedin_url"):
                satz["linkedin_url"] = eintrag["linkedin_url"]
            if eintrag.get("custom"):
                satz["custom"] = eintrag["custom"]
            daten_block.append(satz)
        if not daten_block:
            return None
        antwort = self._post(ENRICH_BULK_URL,
                             {"name": name, "data": daten_block},
                             "contact/enrich/bulk")
        return antwort.get("enrichment_id")

    def guthaben(self) -> float | None:
        """GET /account/credits - aktueller Stand, kostet nichts.

        Damit laesst sich vor und nach einem Lauf messen, was wirklich
        verbraucht wurde - inklusive der Such-Credits, die die
        Anreicherungs-Antwort NICHT mitmeldet."""
        def einmal():
            self._limit_einhalten()
            return self.session.get(GUTHABEN_URL, headers=self._headers,
                                    timeout=30)

        antwort = self._mit_wiederholung(einmal, "account/credits")
        self._pruefen(antwort, "account/credits")
        daten = antwort.json() or {}
        wert = daten.get("balance")
        try:
            return float(wert)
        except (TypeError, ValueError):
            return None

    def schluessel_pruefen(self) -> dict:
        """Prueft den Schluessel mit FullEnrichs eigenem Testkontakt.

        Der kostet laut Doku 0 Credits. Gibt {"ok", "status", "meldung"}
        zurueck - wirft nicht, damit der Aufrufer die Lage sauber
        anzeigen kann statt mit einem Stacktrace abzubrechen."""
        try:
            kennung = self.anreicherung_starten(
                [dict(TESTKONTAKT)], name="Schlüssel-Prüfung (0 Credits)")
        except FullEnrichFehler as fehler:
            return {"ok": False, "status": fehler.status,
                    "meldung": str(fehler)}
        if not kennung:
            return {"ok": False, "status": None,
                    "meldung": "Keine enrichment_id erhalten."}
        return {"ok": True, "status": 200,
                "meldung": f"Schlüssel gültig (Test-Auftrag {kennung}, "
                           f"0 Credits laut FullEnrich-Doku).",
                "enrichment_id": kennung}

    def anreicherung_abholen(self, enrichment_id: str) -> dict:
        """GET /contact/enrich/bulk/<id> - pollt bis zu einem Endzustand.

        CREDITS_INSUFFICIENT wird als eigener Fehler geworfen: dann hat
        weiterlaufen keinen Sinn mehr."""
        url = f"{ENRICH_BULK_URL}/{enrichment_id}"
        letzter = {}
        for versuch in range(1, self.max_abfragen + 1):
            def einmal():
                self._limit_einhalten()
                return self.session.get(url, headers=self._headers,
                                        timeout=60)

            antwort = self._mit_wiederholung(
                einmal, "contact/enrich/bulk (abholen)")
            self._pruefen(antwort, "contact/enrich/bulk (abholen)")
            letzter = antwort.json() or {}
            status = str(letzter.get("status") or "").upper()
            if status == "CREDITS_INSUFFICIENT":
                raise KontingentLeer(
                    "FullEnrich meldet: Guthaben aufgebraucht "
                    "(CREDITS_INSUFFICIENT).", code=status)
            if status in FERTIG_STATUS:
                return letzter
            if versuch < self.max_abfragen:
                self._schlafen(self.wartezeit)
        raise FullEnrichFehler(
            f"FullEnrich liefert nach {self.max_abfragen} Abfragen kein "
            f"Endergebnis (enrichment_id {enrichment_id}, zuletzt "
            f"{letzter.get('status')!r}). Der Auftrag laeuft weiter und "
            f"kann mit derselben ID erneut abgeholt werden.")


# ------------------------------------------------------------ Auswertung

_MOBIL_DE = re.compile(r"^(?:\+49|0049|0)\s*1[5-7]")


def ist_sammeladresse(email: str) -> bool:
    """info@, office@, sales@ ... - keine Person dahinter.

    Auch eine "work_email" kann eine Sammeladresse sein. Fuer Olivers
    Anforderung zaehlt nur die personenbezogene Adresse, deshalb wird
    das getrennt gemessen statt stillschweigend mitgezaehlt."""
    lokal = str(email or "").split("@")[0].strip().casefold()
    if not lokal:
        return False
    # Geprueft wird der GANZE lokale Teil und sein ERSTER Bestandteil:
    # "no-reply" steht als Ganzes in der Liste, "info-de" nur ueber den
    # ersten Bestandteil. "thomas.info" bleibt personenbezogen, weil der
    # erste Bestandteil "thomas" ist.
    if lokal in SAMMEL_PRAEFIXE:
        return True
    return re.split(r"[._\-+]", lokal)[0] in SAMMEL_PRAEFIXE


def telefon_art(nummer: str) -> str:
    """"mobil" | "festnetz" | "unbekannt".

    Die API sagt es NICHT selbst - das Phone-Objekt traegt nur number
    und region. Deutsche Mobilnummern beginnen mit 015x/016x/017x. Alles
    andere Deutsche gilt als Festnetz. Bei allem, was sich nicht sicher
    einordnen laesst (Auslandsnummern, unklare Schreibweisen), wird
    "unbekannt" zurueckgegeben statt geraten - eine falsch als mobil
    ausgewiesene Nummer waere schlimmer als eine offen unbekannte."""
    text = (nummer or "").strip()
    if not text:
        return ""
    kompakt = re.sub(r"[^\d+]", "", text)
    if _MOBIL_DE.match(kompakt):
        return "mobil"
    if kompakt.startswith(("+49", "0049")):
        return "festnetz"
    if kompakt.startswith("0") and not kompakt.startswith("00"):
        # Nationale Schreibweise ohne Landesvorwahl: nur dann Festnetz,
        # wenn es keine Mobilvorwahl ist (oben schon geprueft).
        return "festnetz"
    return "unbekannt"


def beste_mail(eintraege: list, nur_stark: bool = False) -> dict | None:
    """Erste brauchbare Adresse aus einer work_emails/personal_emails-Liste.

    Reihenfolge: DELIVERABLE vor HIGH_PROBABILITY vor CATCH_ALL. INVALID
    und INVALID_DOMAIN werden nie zurueckgegeben."""
    erlaubt = STARKE_MAIL_STATUS if nur_stark else BRAUCHBARE_MAIL_STATUS
    kandidaten = [e for e in (eintraege or [])
                  if isinstance(e, dict) and e.get("email")
                  and str(e.get("status") or "").upper() in erlaubt]
    if not kandidaten:
        return None
    kandidaten.sort(key=lambda e: erlaubt.index(
        str(e.get("status") or "").upper()))
    return kandidaten[0]
