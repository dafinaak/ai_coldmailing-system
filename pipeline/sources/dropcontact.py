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
import re
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


def _guthaben_merken(antwort: dict) -> None:
    """Note the credit count Dropcontact just reported.

    The provider sends "credits_left" with every accepted request, so
    the number is a free by-product of work we are doing anyway. It is
    only ever recorded, never asked for separately.
    """
    if "credits_left" not in (antwort or {}):
        return
    try:
        from pipeline.guthaben import merken
        merken(antwort["credits_left"])
    except Exception:      # noqa: BLE001 - eine Notiz darf nie einen Lauf kosten
        pass


def _vergleichbar(wert) -> str:
    """Names as Dropcontact echoes them back differ in case and spacing."""
    return " ".join(str(wert or "").split()).casefold()


def _nur_domain(website) -> str:
    ohne = re.sub(r"^https?://", "", str(website or "").strip().lower())
    return re.sub(r"^www\.", "", ohne).split("/")[0]


def _pruefe_zuordnung(anfrage: dict, zeile: dict, request_id: str) -> None:
    """Raise if a returned row belongs to a different request than ours.

    Dropcontact echoes the name and the website back, and it edits the
    name freely: it fixes spelling, and with a double first name like
    "Peter-Christoph Haider" it may decide the surname came first and
    swap the two fields. None of that means the row moved.

    A real row shift looks different: the row would carry BOTH a name
    that shares nothing with ours AND a different company website. So a
    row is only rejected when neither the names nor the domain connect
    it to what we sent - hard enough to catch a shift, loose enough not
    to stop the run over a corrected name.
    """
    if not zeile:
        raise RuntimeError(
            f"Dropcontact liefert eine leere Zeile fuer "
            f"{anfrage.get('first_name')} {anfrage.get('last_name')} "
            f"(request_id {request_id}) - Zuordnung unsicher, Abbruch.")

    gefragt = {_vergleichbar(anfrage.get("first_name")),
               _vergleichbar(anfrage.get("last_name"))} - {""}
    zurueck = {_vergleichbar(zeile.get("first_name")),
               _vergleichbar(zeile.get("last_name"))} - {""}
    if not zurueck or (gefragt & zurueck):
        return

    domain_gefragt = _nur_domain(anfrage.get("website"))
    if domain_gefragt and domain_gefragt == _nur_domain(zeile.get("website")):
        return

    raise RuntimeError(
        f"Dropcontact antwortet mit '{zeile.get('first_name')} "
        f"{zeile.get('last_name')}' ({zeile.get('website')}) auf die Anfrage "
        f"zu '{anfrage.get('first_name')} {anfrage.get('last_name')}' "
        f"({anfrage.get('website')}, request_id {request_id}) - weder Name "
        f"noch Domain passen, Abbruch statt falscher Adressen.")


def _namens_hinweis(anfrage: dict, zeile: dict) -> str:
    """Note when the answer carries a different name than we asked about.

    Harmless in itself, but it changes which word the address gets built
    from - "Peter-Christoph Haider" came back as "Haider Peter-Christoph"
    and produced peter@... . Worth a human glance, so it is written down
    rather than smoothed over.
    """
    zurueck = f"{zeile.get('first_name') or ''} {zeile.get('last_name') or ''}".strip()
    gefragt = f"{anfrage.get('first_name') or ''} {anfrage.get('last_name') or ''}".strip()
    if not zurueck or _vergleichbar(zurueck) == _vergleichbar(gefragt):
        return ""
    return (f"Dropcontact führt diese Person als '{zurueck}' statt "
            f"'{gefragt}' - Adresse bitte prüfen")


class DropcontactSource:
    # Standard-Abholfenster ~2 Minuten (12 x 10s): Im Messlauf vom 23.07.2026
    # brauchte Dropcontact fuer 5 von 8 Auftraegen laenger als das alte
    # Fenster von ~26s (6 x 5s) - die Firmen endeten faelschlich als Fehler,
    # obwohl das Ergebnis nur noch nicht fertig war. Lieber laenger warten
    # als eine bezahlte Anreicherung wegwerfen (Zuverlaessigkeit zuerst).
    # Der Batch-Weg braucht ein eigenes, viel groesseres Fenster: ein
    # Auftrag mit 100 Namen war nach den 2 Minuten des Einzelfensters noch
    # nicht fertig und wurde weggeworfen, obwohl er bezahlt war (11.08.2026).
    # 60 x 15s = 15 Minuten. Warten kostet nichts, wegwerfen kostet Credits.
    def __init__(self, api_key, session=None, wartezeit=10.0, max_abfragen=12,
                 batch_wartezeit=15.0, batch_max_abfragen=60):
        self.api_key = api_key
        self.session = session or requests.Session()
        self.wartezeit = wartezeit          # Sekunden zwischen den Abfragen
        self.max_abfragen = max_abfragen    # so oft wird auf das Ergebnis gepollt
        self.batch_wartezeit = batch_wartezeit
        self.batch_max_abfragen = batch_max_abfragen

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

    def email_bauen_viele(self, anfragen: list) -> list:
        """Same job as email_bauen, but for a whole list in ONE request.

        anfragen: [{"first_name","last_name","website","company"}, ...]
        Returns a list of the same length and order, each entry either
        {"email","qualification"} or None - exactly what email_bauen
        returns per person.

        Dropcontact answers a batch in the order it was submitted. Order
        alone is too thin a thread to hang real e-mail addresses on: if
        it ever shifted, every company would be greeted with a stranger's
        address. So each returned row is checked against the name that
        was sent, and a mismatch raises instead of quietly returning the
        wrong person (Projektregel: Zuverlaessigkeit zuerst).
        """
        request_id, gesendet = self.batch_abgeben(anfragen)
        if request_id is None:
            return [None] * len(anfragen)
        return self.batch_abholen(request_id, gesendet, len(anfragen))

    def batch_abgeben(self, anfragen: list) -> tuple:
        """Hand a batch over and return (request_id, gesendet).

        Split off from the fetching half on purpose: the moment this
        returns, the batch is PAID FOR. The caller is expected to write
        the request_id down before fetching, so that a crash or a slow
        answer costs time but never the credits - the same request_id
        can be fetched again later.

        gesendet is [(position in anfragen, anfrage)] for the entries
        that were actually sent; people without a full name cost nothing
        and are skipped.
        """
        gesendet = [
            (nr, a) for nr, a in enumerate(anfragen)
            if a.get("first_name") and a.get("last_name")
        ]
        if not gesendet:
            return None, []

        body = {
            "data": [
                {"first_name": a["first_name"], "last_name": a["last_name"],
                 "company": a.get("company") or "", "website": a.get("website") or ""}
                for _, a in gesendet
            ],
            "siren": False, "language": "de",
        }
        antwort = self.session.post(
            ENRICH_URL, json=body, headers=self._headers, timeout=60)
        if antwort.status_code >= 400:
            raise RuntimeError(
                f"Dropcontact antwortet mit {antwort.status_code} auf {ENRICH_URL}: "
                f"{getattr(antwort, 'text', '')}")
        daten = antwort.json() or {}
        if daten.get("error") or not daten.get("request_id"):
            grund = daten.get("reason") or daten.get("error") or "unbekannt"
            raise RuntimeError(f"Dropcontact lehnt den Batch ab: {grund}")
        _guthaben_merken(daten)
        return daten["request_id"], gesendet

    def batch_abholen(self, request_id: str, gesendet: list,
                      gesamt: int | None = None) -> list:
        """Fetch a handed-over batch and map every row back to its person."""
        zeilen = self.zeilen_holen(request_id)
        if len(zeilen) != len(gesendet):
            raise RuntimeError(
                f"Dropcontact liefert {len(zeilen)} Zeilen fuer "
                f"{len(gesendet)} gesendete Personen (request_id "
                f"{request_id}) - Zuordnung unsicher, Abbruch.")

        ergebnisse: list = [None] * (gesamt if gesamt is not None else len(gesendet))
        for (nr, anfrage), zeile in zip(gesendet, zeilen):
            _pruefe_zuordnung(anfrage, zeile, request_id)
            mail = _beste_email(zeile.get("email", []))
            if mail:
                hinweis = _namens_hinweis(anfrage, zeile)
                if hinweis:
                    mail = {**mail, "hinweis": hinweis}
            ergebnisse[nr] = mail
        return ergebnisse

    def zeilen_holen(self, request_id: str) -> list:
        """Poll until the batch is done and return its raw rows.

        A big batch needs far longer than a single person: 100 names
        took over two minutes, which is why the batch window is counted
        separately and generously. Waiting is cheap; a thrown-away paid
        batch is not.
        """
        url = f"{ENRICH_URL}/{request_id}"
        for abfrage in range(1, self.batch_max_abfragen + 1):
            antwort = self.session.get(url, headers=self._headers, timeout=60)
            if antwort.status_code >= 400:
                raise RuntimeError(
                    f"Dropcontact antwortet mit {antwort.status_code} auf {url}: "
                    f"{getattr(antwort, 'text', '')}")
            daten = antwort.json() or {}
            if daten.get("success") and daten.get("data") is not None:
                return daten["data"]
            if abfrage < self.batch_max_abfragen:
                time.sleep(self.batch_wartezeit)
        raise RuntimeError(
            f"Dropcontact liefert nach {self.batch_max_abfragen} Abfragen kein "
            f"Ergebnis (request_id {request_id}). Der Batch ist bezahlt und "
            f"bleibt abrufbar - mit dieser request_id spaeter erneut abholen.")

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
        _guthaben_merken(daten)
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
