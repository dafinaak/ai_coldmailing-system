import re
import time
import requests
from urllib.parse import urlparse
from pipeline.models import Lead

# Live-Doku (docs.apollo.io, OpenAPI-Spec-Auszug, geprüft 2026-07-16):
#
# People API Search (docs.apollo.io/reference/people-api-search):
# Base-URL ist https://api.apollo.io/api/v1, der People-Search-Pfad ist
# "/mixed_people/api_search" (nicht "/mixed_people/search" wie im
# Task-Brief-Entwurf). Auth-Header laut Doku "x-api-key" (Groß-/
# Kleinschreibung bei HTTP-Headern egal, daher "X-Api-Key" beibehalten).
# Antwort-Hülle ist bestätigt {"people": [...], "total_entries": ...}.
# Die Doku sagt ausdrücklich: "This endpoint doesn't return email
# addresses or phone numbers." — deshalb der zweite Schritt unten.
#
# Bulk People Enrichment (docs.apollo.io/reference/bulk-people-enrichment):
# Pfad "/people/bulk_match", bis zu 10 Personen pro Aufruf (details[]-Array,
# hier per "id" aus dem Suchtreffer identifiziert). Liefert standardmäßig
# keine privaten E-Mails; der Query-Parameter "reveal_personal_emails=true"
# schaltet das frei (kann Credits kosten, siehe Doku). "reveal_phone_number"
# bleibt aus, weil das einen webhook_url voraussetzt und hier nicht gebraucht
# wird. Antwort-Hülle bestätigt: {"matches": [...], "status": ..., ...},
# jedes Match-Objekt kann "email" sowie ein volles "organization"-Objekt
# (u. a. "website_url") enthalten.
#
# TODO(verifizieren am echten Konto):
# (a) Die Zuordnung in _anreichern() matcht Suchtreffer und bulk_match-
#     Ergebnisse ausschliesslich ueber die Apollo-"id". Laut Doku ist das
#     der vorgesehene Weg, aber ungetestet ist, ob bulk_match bei manchen
#     Personen (z.B. geloeschte/zusammengefuehrte Datensaetze) die id
#     stillschweigend nicht zurueckliefert - dann wuerde dieser Treffer
#     unangereichert durchgereicht und mangels E-Mail spaeter uebersprungen
#     (stiller Unter-Match statt Fehler). Am echten Konto pruefen, ob das
#     vorkommt und ob ein Fallback (z.B. ueber first_name/last_name/
#     organization) noetig ist.
# (b) "reveal_personal_emails=true" kann laut Doku Credits verbrauchen -
#     wie viele pro aufgeloester Person und ob das auch bei einem "kein
#     Treffer/keine E-Mail vorhanden"-Ergebnis abgerechnet wird, ist am
#     echten Konto noch nicht verifiziert. Vor produktivem Einsatz mit
#     echtem Kontingent gegenpruefen, damit ein Lauf nicht ungeplant
#     Credits verbraucht.
#
# Organization Enrichment (docs.apollo.io/reference/organization-enrichment,
# Kern-Umbau Stufe 2, geprueft 2026-07-21):
# Zweck: pro Firma aus Stufe 1 (Google Maps) die Apollo-Organisation finden
# (fuer organization_id + Mitarbeiterzahl, Grundlage der info@-Regel).
# GET .../organizations/enrich?domain=... - Live-Smoke-Test hat die HTTP-
# Methode + URL-Form bestaetigt.
#
# BUG-FIX (Apollo-422, echter 30-Firmen-Lauf, geprueft 2026-07-21): die
# Doku-Seite listet zwar "domain", "linkedin_url", "name" und "website" als
# gleichwertig akzeptierte Felder fuer DIESEN Endpoint - in der Praxis
# antwortet er aber mit HTTP 422 auf JEDE Anfrage, die nur "name" (ohne
# Domain) traegt. Das traf im echten Lauf JEDE Firma ohne Google-Maps-
# Webseite und liess sie faelschlich als "kein Kontakt" durchfallen -
# druckt die Deckungsquote (Chef-Ziel >= 80%) kuenstlich nach unten, obwohl
# Apollo die Firma bei richtiger Anfrage durchaus gefunden haette. Fix:
# "name" geht NIE MEHR an diesen Enrich-Endpoint. Stattdessen nutzt der
# Namens-Fallback jetzt den SUCH-Endpoint (ORGANISATION_SUCH_URL unten),
# der laut Doku eigens fuer Namens-/Teilstring-Suche gedacht ist und bei
# keinem Treffer ganz regulaer mit einer leeren Liste (Status 200) statt
# 422 antwortet - ein "kein Treffer" bleibt also ein echtes "kein Treffer",
# kein getarnter technischer Fehler.
# Kostenhinweis: 1 Apollo-Credit pro TATSAECHLICH gefundener Organisation
# beim Enrich-Aufruf ueber die Domain (0 bei keinem Treffer); der Namens-
# Fallback ueber ORGANISATION_SUCH_URL kostet 1 Credit PRO SEITE NUR wenn
# Ergebnisse zurueckkommen (0 Credits bei keinem Treffer) - siehe
# docs.apollo.io/docs/api-pricing.
#
# Organization Search (docs.apollo.io/reference/organization-search,
# BUG-FIX Apollo-422, geprueft 2026-07-21 direkt gegen Apollos eigene
# OpenAPI-Spec unter docs.apollo.io/reference/organization-search.md, da
# die HTML-Referenzseite die Endpoint-URL nur per JavaScript nachlaedt):
# POST /mixed_companies/search (Basis-URL wie ueberall https://api.apollo.
# io/api/v1). Trotz "in": "query" in der OpenAPI-Spec werden die Felder -
# wie beim bereits verifizierten SUCH_URL (mixed_people/api_search) oben -
# als JSON-Body gesendet, nicht als Query-String. Genutztes Feld:
# "q_organization_name" (Teilstring-Suche, laut Doku z.B. "marketing"
# findet auch "NY Marketing Unlimited"). Antwort-Huelle bestaetigt:
# {"organizations": [...], "accounts": [...], "pagination": {...}}, jedes
# Organisations-Objekt in derselben Form wie beim Enrich-Endpoint (u.a.
# "id", "name", "estimated_num_employees"). Da die Namens-Suche nur ein
# lockerer Teilstring-Abgleich ist (kein exaktes Matching), waehlt
# _beste_namenstreffer() unten den Treffer mit EXAKT uebereinstimmendem
# Namen (case-insensitive), falls vorhanden - sonst den ersten Treffer, der
# der Suche wirklich AEHNELT (_aehnelt_sich).
#
# BUG-FIX (Review-Fund, geprueft 2026-07-21): _beste_namenstreffer fiel
# urspruenglich OHNE Aehnlichkeits-Pruefung auf den ersten Treffer zurueck.
# Weil q_organization_name nur ein Teilstring-Abgleich ist, liefert Apollo
# bei einem generischen Firmennamen routinemaessig eine voellig FREMDE
# Firma (Doku-Beispiel oben: die Suche "marketing" findet auch "NY
# Marketing Unlimited"). Ein blinder erster Treffer haette also fremde
# Firmennamen und fremde Kontakte in den Lauf gezogen UND die
# Deckungsquote unehrlich aufgeblaeht (als "mit_kontakt" gezaehlt, obwohl
# es die falsche Firma war). Fix: _aehnelt_sich() prueft (nach
# Normalisierung: Kleinschreibung, Rechtsform wie "GmbH"/"AG"/"UG"/"GbR"/
# "mbH"/"KG"/"e.K." abgestreift, Satzzeichen weg) auf einen von drei
# Faellen - exakte Uebereinstimmung, einer der Namen steckt vollstaendig
# im anderen, ODER beide teilen sich mindestens ein unterscheidungs-
# kraeftiges Token (kein generisches Wort wie "it"/"service"/"gmbh"/ein
# Staedtename). Findet sich KEIN aehnlicher Treffer, liefert
# _beste_namenstreffer() None - die Firma wird dann korrekt als
# "apollo_kein_treffer" gezaehlt, nie als falscher Match.
BASE_URL = "https://api.apollo.io/api/v1"
SUCH_URL = f"{BASE_URL}/mixed_people/api_search"
ANREICHERUNGS_URL = f"{BASE_URL}/people/bulk_match?reveal_personal_emails=true"
ANREICHERUNGS_BATCH_GROESSE = 10
ORGANISATION_URL = f"{BASE_URL}/organizations/enrich"
ORGANISATION_SUCH_URL = f"{BASE_URL}/mixed_companies/search"
NAMENSSUCHE_TREFFER_PRO_SEITE = 10


def _saubere_domain(wert: str) -> str:
    """Verteidigungslinie GEGEN den Apollo-422-Bug (siehe ORGANISATION_URL-
    Kommentar oben): normalisiert einen Domain-Wert auf eine reine,
    registrierbare Domain - kein Schema, kein "www."-Praefix, kein Pfad,
    kein Port, keine Query/Fragment, keine Gross-/Kleinschreibung. Firmen
    aus apify_maps.ApifyMapsSource kommen zwar schon mit einer via
    _domain_aus_website bereinigten Domain an, aber eine Firma kann auch aus
    einer wiederaufgenommenen/von Hand bearbeiteten firmen.json stammen -
    eine kaputt formatierte Domain (volle URL, Port, Query-String) darf
    niemals selbst der Grund fuer eine Apollo-Ablehnung sein."""
    wert = (wert or "").strip().lower()
    if not wert:
        return ""
    ohne_schema = wert if "//" in wert else f"//{wert}"
    netloc = urlparse(ohne_schema).netloc or ohne_schema.lstrip("/").split("/")[0]
    netloc = netloc.split("@")[-1].split(":")[0]  # evtl. user:pass@ bzw. :port abtrennen
    return netloc[4:] if netloc.startswith("www.") else netloc


# Deutsche/verbreitete Rechtsformen, die vor dem Aehnlichkeits-Vergleich
# abgestreift werden (Review-Fund) - sonst zaehlt "GmbH" faelschlich als
# gemeinsames "unterscheidungskraeftiges" Token zwischen zwei voellig
# verschiedenen Firmen.
_RECHTSFORM_MUSTER = re.compile(
    r"\b(gmbh\s*&\s*co\.?\s*kg|gmbh|mbh|ag|ug|gbr|kg|ohg|e\.?\s*k\.?)\b")

# Woerter, die trotz Uebereinstimmung NICHT als "unterscheidungskraeftiges
# gemeinsames Token" zaehlen (Review-Fund) - sonst waeren z.B. "IT Service
# Hannover" und "Bau Service Hannover GmbH" (teilen sich nur "service"/
# "hannover") faelschlich als aehnlich durchgegangen. Bewusst klein und
# konservativ gehalten (Branchen-Allerweltswoerter + gaengige Grossstaedte);
# eine Firma, die NUR aus einem dieser Woerter besteht, wird ohnehin schon
# durch die Teilstring-Pruefung in _aehnelt_sich abgedeckt.
_GENERISCHE_WOERTER = {
    "it", "service", "services", "dienstleister", "dienstleistungen",
    "consulting", "solutions", "systems", "system", "group", "gruppe",
    "team", "gmbh", "ag", "ug", "gbr", "kg", "mbh", "co", "und", "the",
    "hannover", "berlin", "hamburg", "muenchen", "münchen", "koeln",
    "köln", "frankfurt", "stuttgart", "duesseldorf", "düsseldorf",
    "leipzig", "deutschland", "germany",
}


def _normalisiere_firmenname(name: str) -> str:
    """Bereinigt einen Firmennamen fuer den Aehnlichkeits-Vergleich in
    _aehnelt_sich(): Kleinschreibung, Rechtsform (_RECHTSFORM_MUSTER) weg,
    Satzzeichen weg, doppelte Leerzeichen entfernt."""
    name = (name or "").strip().lower()
    name = _RECHTSFORM_MUSTER.sub(" ", name)
    name = re.sub(r"[^\w\s]", " ", name, flags=re.UNICODE)
    return " ".join(name.split())


def _aehnelt_sich(name_a: str, name_b: str) -> bool:
    """Bug-Fix (Review-Fund): prueft, ob zwei Firmennamen sich WIRKLICH
    aehneln - nicht nur, ob Apollos lockerer Teilstring-Abgleich
    (q_organization_name) sie beide zurueckgeliefert hat. Akzeptiert genau
    drei Faelle (nach _normalisiere_firmenname): (1) exakte
    Uebereinstimmung, (2) einer der normalisierten Namen steckt komplett im
    anderen (z.B. "einsnulleins" in "einsnulleins hannover" - Firma plus
    Standort-/Filial-Zusatz), oder (3) beide teilen sich mindestens ein
    Token, das weder Rechtsform noch ein generisches Allerweltswort ist
    (_GENERISCHE_WOERTER) - z.B. "einsnulleins" in "Einsnulleins IT
    Service" vs. "Einsnulleins Consulting GmbH". Sonst False - bewusst
    konservativ, lieber ein Treffer zu wenig als eine fremde Firma."""
    norm_a, norm_b = _normalisiere_firmenname(name_a), _normalisiere_firmenname(name_b)
    if not norm_a or not norm_b:
        return False
    if norm_a == norm_b or norm_a in norm_b or norm_b in norm_a:
        return True
    tokens_a = set(norm_a.split()) - _GENERISCHE_WOERTER
    tokens_b = set(norm_b.split()) - _GENERISCHE_WOERTER
    return bool(tokens_a & tokens_b)


def _beste_namenstreffer(organisationen: list, gesuchter_name: str):
    """Waehlt aus den Treffern der Namens-Suche (ORGANISATION_SUCH_URL) die
    am besten passende Organisation: Apollo matcht "q_organization_name" nur
    als lockeren Teilstring, daher wird - falls vorhanden - der Treffer mit
    EXAKT uebereinstimmendem Namen (case-insensitive, Rechtsform-unabhaengig)
    bevorzugt, sonst der erste Treffer, der der Suche wirklich AEHNELT
    (_aehnelt_sich). Aehnelt KEIN Treffer der Suche (Review-Fund - Apollos
    Teilstring-Suche liefert bei generischen Namen oft eine voellig fremde
    Firma), liefert diese Funktion None - ein echtes "kein Treffer", NICHT
    ein falscher Match. Eine leere Trefferliste liefert ebenfalls None."""
    if not organisationen:
        return None
    gesucht_norm = _normalisiere_firmenname(gesuchter_name)
    for organisation in organisationen:
        if _normalisiere_firmenname(organisation.get("name") or "") == gesucht_norm:
            return organisation
    for organisation in organisationen:
        if _aehnelt_sich(organisation.get("name") or "", gesuchter_name):
            return organisation
    return None

class ApolloSource:
    def __init__(self, api_key, session=None, wartezeit=5):
        self.api_key = api_key
        self.session = session or requests.Session()
        self.wartezeit = wartezeit
        self.uebersprungen_ohne_email = 0

    def search(self, zielgruppe: dict, limit: int):
        self.uebersprungen_ohne_email = 0
        body = {
            "person_titles": zielgruppe.get("titel", []),
            "person_locations": zielgruppe.get("region", []),
            "organization_num_employees_ranges": zielgruppe.get("firmengroesse", []),
            "per_page": min(limit, 100), "page": 1,
        }
        antwort = self._post_mit_wiederholung(SUCH_URL, body)
        treffer = antwort.json().get("people", [])[:limit]
        angereicherte_treffer = self._anreichern(treffer)

        leads = []
        for p in angereicherte_treffer:
            # Erst nach der Anreicherung über bulk_match kann eine E-Mail
            # vorhanden sein (die Such-Antwort selbst liefert nie eine).
            if not p.get("email"):
                self.uebersprungen_ohne_email += 1
                continue
            org = p.get("organization") or {}
            leads.append(Lead(
                first_name=p.get("first_name", ""),
                # "last_name" ist die Vollform; die Such-Antwort liefert für
                # nicht angereicherte Treffer stattdessen ein
                # "last_name_obfuscated"-Feld (z. B. "Do***e") als
                # Datenschutz-Fallback.
                last_name=p.get("last_name") or p.get("last_name_obfuscated", ""),
                email=p["email"], company=org.get("name", ""), title=p.get("title", ""),
                website=org.get("website_url", ""), source="apollo"))
        return leads

    def unternehmen_anreichern(self, firma: dict, kontakt_rollen: list) -> dict:
        """Stufe 2 der Lead-Beschaffung (Kern-Umbau): zu EINER Firma aus
        Stufe 1 (dict mit mindestens "domain"/"name") Kontakte in den
        gewuenschten Rollen suchen - NICHT die alte kriterien-basierte
        Massensuche in search() oben (die bleibt fuer Rueckwaertskompatibilitaet
        stehen). Liefert immer dieselbe Form zurueck, auch ohne Treffer:
        {"kontakte": [...], "mitarbeiterzahl": int|None, "organization_id": str|None,
        "name": str|None} - "kontakte" ist eine Liste aus {"first_name",
        "last_name", "email", "title"}-Dicts (nur Personen MIT E-Mail nach der
        bulk_match-Anreicherung). "mitarbeiterzahl" traegt Apollos
        "estimated_num_employees" der gefundenen Organisation - Grundlage der
        info@-Regel in pipeline.sourcing, die hier bewusst NICHT entschieden
        wird (dieses Modul kennt keine info@-Regel, nur Apollo-Rohdaten).
        "name" ist Apollos KANONISCHER Organisationsname (Lead-Qualitaets-Fix:
        Google-Maps-Titel sind teils verunreinigt, z.B. "IT-Dienstleister
        Hannover - Ihre Helden" statt "Ihre Helden" - Apollos Organisationsname
        ist die sauberere Quelle und wird von pipeline.sourcing bevorzugt
        genutzt, wenn vorhanden)."""
        organisation = self._organisation_finden(firma)
        if not organisation:
            return {"kontakte": [], "mitarbeiterzahl": None, "organization_id": None, "name": None}
        organization_id = organisation.get("id")
        kontakte = (self._kontakte_fuer_organisation(organization_id, kontakt_rollen)
                    if organization_id else [])
        return {"kontakte": kontakte,
                "mitarbeiterzahl": organisation.get("estimated_num_employees"),
                "organization_id": organization_id,
                "name": organisation.get("name")}

    def _organisation_finden(self, firma: dict):
        """Sucht die Apollo-Organisation zur Firma: zuerst ueber die Domain
        (praeziser, Enrich-Endpoint), bei keinem Treffer ODER ganz ohne
        bekannte Domain als Fallback ueber den Firmennamen - ABER (Apollo-
        422-Fix, siehe ORGANISATION_URL-Kommentar oben) der Namens-Fallback
        geht an den SUCH-Endpoint (_organisation_ueber_namen_suchen), NIE an
        den Enrich-Endpoint, der bei "name" ohne Domain zuverlaessig mit
        422 antwortet."""
        domain = _saubere_domain(firma.get("domain") or "")
        if domain:
            antwort = self._get_mit_wiederholung(ORGANISATION_URL, {"domain": domain})
            organisation = antwort.json().get("organization")
            if organisation:
                return organisation
        name = firma.get("name")
        if name:
            return self._organisation_ueber_namen_suchen(name)
        return None

    def _organisation_ueber_namen_suchen(self, name: str):
        body = {"q_organization_name": name, "page": 1,
                "per_page": NAMENSSUCHE_TREFFER_PRO_SEITE}
        antwort = self._post_mit_wiederholung(ORGANISATION_SUCH_URL, body)
        organisationen = antwort.json().get("organizations") or []
        return _beste_namenstreffer(organisationen, name)

    def _kontakte_fuer_organisation(self, organization_id: str, kontakt_rollen: list) -> list:
        body = {"organization_ids": [organization_id], "person_titles": kontakt_rollen,
                "per_page": 100, "page": 1}
        antwort = self._post_mit_wiederholung(SUCH_URL, body)
        treffer = antwort.json().get("people", [])
        angereicherte_treffer = self._anreichern(treffer)
        kontakte = []
        for p in angereicherte_treffer:
            if not p.get("email"):
                continue
            kontakte.append({
                "first_name": p.get("first_name", ""),
                "last_name": p.get("last_name") or p.get("last_name_obfuscated", ""),
                "email": p["email"], "title": p.get("title", "")})
        return kontakte

    def _anreichern(self, treffer):
        """Reichert Suchtreffer über /people/bulk_match mit E-Mail-Adressen
        (und ggf. vollständigerem Namen/Titel/Website) an. Apollo erlaubt
        maximal 10 Personen pro Aufruf, daher wird in Gruppen aufgeteilt."""
        angereichert = []
        for start in range(0, len(treffer), ANREICHERUNGS_BATCH_GROESSE):
            batch = treffer[start:start + ANREICHERUNGS_BATCH_GROESSE]
            ids = [p["id"] for p in batch if p.get("id")]
            if not ids:
                angereichert.extend(batch)
                continue
            body = {"details": [{"id": pid} for pid in ids]}
            antwort = self._post_mit_wiederholung(ANREICHERUNGS_URL, body)
            matches = {m.get("id"): m for m in antwort.json().get("matches", [])}
            for p in batch:
                match = matches.get(p.get("id"))
                if match:
                    p = {**p, **{k: v for k, v in match.items() if v}}
                angereichert.append(p)
        return angereichert

    def _post_mit_wiederholung(self, url, body):
        return self._mit_wiederholung(url, lambda: self.session.post(
            url, json=body, timeout=30,
            headers={"X-Api-Key": self.api_key, "Content-Type": "application/json"}))

    def _get_mit_wiederholung(self, url, params):
        return self._mit_wiederholung(url, lambda: self.session.get(
            url, params=params, timeout=30, headers={"X-Api-Key": self.api_key}))

    def _mit_wiederholung(self, url, aufruf):
        """Wiederholt nur bei 429 (Rate-Limit) und 5xx (voruebergehende
        Server-Fehler) - beides Faelle, bei denen ein zweiter Versuch
        sinnvoll sein kann. Andere 4xx-Fehler (z.B. 401 falscher Api-Key,
        422 kaputte Anfrage) sind dauerhaft und werden sofort ohne
        Wiederholung als RuntimeError gemeldet. Nach dem letzten
        fehlgeschlagenen Versuch wird nicht mehr gewartet. Gemeinsam fuer
        POST (_post_mit_wiederholung) und GET (_get_mit_wiederholung)
        genutzt, `aufruf` fuehrt den eigentlichen HTTP-Request aus."""
        letzte_antwort = None
        for versuch in range(3):
            antwort = aufruf()
            if antwort.status_code < 400:
                return antwort
            if antwort.status_code != 429 and antwort.status_code < 500:
                raise RuntimeError(f"Apollo antwortet mit {antwort.status_code} auf {url}")
            letzte_antwort = antwort
            if versuch < 2:
                time.sleep(self.wartezeit * (versuch + 1))
        raise RuntimeError(f"Apollo antwortet dauerhaft mit {letzte_antwort.status_code}")
