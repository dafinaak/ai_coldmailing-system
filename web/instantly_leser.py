"""Liest (nur GET) den Live-Stand von Kampagnen aus Instantly - fuer den
Kampagnen-Bereich (Task 6). Bewusst getrennt von
pipeline.senders.instantly.InstantlySender (nur POST, legt Kampagnen an,
darf niemals aktivieren): ein Ausfall oder eine spaetere Aenderung auf der
Lese-Seite darf den Versand-Pfad nie beruehren, und umgekehrt darf ein
Lese-Fehler den Versand nie verhindern.

Step-0-Live-Doku-Pruefung (Plan-Risiko 2, PFLICHT vor dem Bau): geprueft
am 2026-07-20 gegen die OpenAPI-Spec unter
https://api.instantly.ai/openapi/api_v2.json (dieselbe Quelle, die auch
pipeline/senders/instantly.py fuer den Schreib-Pfad verifiziert hat). Keine
echten API-Aufrufe gemacht (nur die Doku gelesen) - die Felder unten sind
gegen das SCHEMA verifiziert, nicht gegen ein echtes Konto; entsprechend
markierte TODOs bleiben offen.

- GET /api/v2/campaigns/{id} (operationId "getCampaign"): liefert u.a.
  "name" und "status". "status" ist NICHT binaer 0/1 wie im Aufgabenbrief
  vermutet, sondern components.schemas.Campaign.properties.status, ein
  Zahlen-Enum mit x-enumDescriptions: 0=Draft, 1=Active, 2=Paused,
  3=Completed, 4=Running Subsequences, -99=Account Suspended,
  -1=Accounts Unhealthy, -2=Bounce Protect. Da diese Klasse (wie
  InstantlySender) Kampagnen nie per Code aktiviert, ist der Zustand direkt
  nach dem Anlegen immer 0 (Draft) - fuer die Anzeige bedeutet das
  "sendet nichts", genau wie "Paused", deshalb bildet _STATUS_TEXT unten
  sowohl 0 als auch 2 auf "pausiert" ab (siehe Kommentar dort). Die drei
  negativen Sonderzustaende sind dagegen KEIN normales "pausiert" - eine
  Kampagne, die deshalb ruht, hat ein echtes Konto-Problem (Konto gesperrt/
  ungesund/Bounce-Protect ausgeloest), kein absichtlich ruhiger Zustand.
  Review-Fund: wuerden diese still als "pausiert" angezeigt, saehe das
  identisch aus wie eine ganz normale, gewollt pausierte Kampagne - _STATUS_
  TEXT bildet sie deshalb auf einen eigenen, lauten Zustand "kontoproblem"
  ab (siehe web.routen.kampagnen fuer den roten Chip/Hinweis dazu).
- GET /api/v2/campaigns/analytics (Query-Parameter "id" ODER wiederholtes
  "ids", plus "start_date"/"end_date"/"exclude_total_leads_count"): liefert
  eine LISTE (auch bei genau einer angefragten ID); Pflichtfelder je
  Eintrag u.a. "campaign_id", "campaign_status", "emails_sent_count",
  "leads_count", "contacted_count". "emails_sent_count" ist der Live-Zaehler
  fuer "versendet".
- GET /api/v2/campaigns/analytics/steps (Query-Parameter "campaign_id"
  optional, sonst alle Kampagnen): liefert eine LISTE, Pflichtfelder je
  Eintrag "step" (String|null, Beispielwert "1"), "variant", "sent",
  "opened", "replies" u.a. - das ist die Quelle fuer die je-Schritt-Zaehler.
  Da jede unserer Sequenzen genau eine Variante je Schritt hat (siehe
  pipeline.senders.instantly.create_campaign), wird hier nur nach "step"
  aufsummiert (normalerweise also nur ein Eintrag je Schritt).
  # TODO(verifizieren am echten Konto): ob "step" bei uns wirklich "1"/"2"/
  # "3" fuer die drei Sequenz-Schritte ist (0- oder 1-indiziert), ist nur
  # aus dem Beispielwert "1" im Schema abgeleitet, nicht an echten Daten
  # bestaetigt.
  # TODO(verifizieren am echten Konto): ob "campaign_status" in der
  # analytics-Antwort exakt dieselbe Zahlen-Codierung wie Campaign.status
  # verwendet (Schema legt es nahe, exakt gleiche x-enumDescriptions), ist
  # hier nicht live geprueft.

GET /api/v2/emails (fuer Task 9, Postfach) ist ebenfalls in der Spec
verifiziert (operationId "listEmail", Antwort {"items": [Email], ...}) -
wird hier bewusst noch nicht angebunden, das ist Aufgabe von Task 9.

Step-0-Live-Doku-Pruefung fuer Task 9 (Postfach), PFLICHT vor dem Bau:
geprueft am 2026-07-20 gegen dieselbe OpenAPI-Spec wie oben. Keine echten
API-Aufrufe gemacht (nur die Doku gelesen) - Felder unten sind gegen das
SCHEMA verifiziert, nicht gegen ein echtes Konto.

- GET /api/v2/emails (operationId "listEmail"): Query-Parameter u.a.
  "campaign_id" (uuid), "limit" (Zahl, 1-100), "starting_after"
  (Cursor-Paginierung - hier bewusst NICHT genutzt, siehe konversationen():
  ein bounded limit von 100 je Kampagne reicht fuer die Anzeige, mehr
  Seiten zu laden waere ein zweiter, groesserer Umbau) und "sort_order"
  ("asc"/"desc" - hier ungenutzt, es wird nach dem Abruf lokal sortiert).
  Antwort: {"items": [Email], "next_starting_after": str}.
- components.schemas.Email, relevante Felder (Pflichtfelder mit *):
  "id"*, "timestamp_created"* (date-time), "timestamp_email"* (date-time -
  wird hier als "zeit" genutzt, siehe _nachricht_aus_email: naeher am
  tatsaechlichen Versand-/Empfangszeitpunkt als "timestamp_created"),
  "subject"*, "to_address_email_list"* (String, KOMMA-GETRENNT trotz des
  "list" im Namen - laut Schema-Beschreibung "Comma-separated list of
  recipient email addresses"), "from_address_email" (String|null),
  "body"* (Objekt {"text": str, "html": str}, beides optional befuellt),
  "content_preview" (String|null, Fallback wenn body.text leer ist),
  "eaccount"* (unser sendender Account), "campaign_id" (uuid|null),
  "step" (String|null, Beispielwert im Schema ist "step-123" -
  # TODO(verifizieren am echten Konto): NICHT das im Aufgabenbrief
  # vermutete "0_1_0"-Muster; wird hier aktuell nicht ausgewertet, nur
  # roh durchgereicht fuer spaetere Verwendung),
  "ue_type" (Zahlen-Enum|null mit x-enumDescriptions: 1="Sent from
  campaign", 2="Received", 3="Sent", 4="Scheduled" - DAS ist das Feld, das
  gesendet von empfangen unterscheidet, nicht "email_type": letzteres
  existiert nur als FILTER-Query-Parameter auf GET /emails
  ("received"/"sent"/"manual"), nicht als Feld auf dem Email-Objekt selbst).
  # TODO(verifizieren am echten Konto): ob unsere automatischen
  # Kampagnen-Mails wirklich ue_type=1 tragen und eine manuelle Antwort
  # ueber Instantly ue_type=3 (statt z.B. nur 1 fuer alles Ausgehende), ist
  # nur aus den Enum-Beschreibungen abgeleitet, nicht live bestaetigt -
  # siehe _richtung_und_kontakt unten, das beide defensiv als "gesendet"
  # behandelt."""
from __future__ import annotations

from datetime import datetime

import requests

BASIS = "https://api.instantly.ai/api/v2"

# 60 Sekunden Cache je Kampagnen-ID (siehe Modul-Docstring/Plan) - verhindert,
# dass jeder Seitenaufruf sofort wieder alle Kampagnen live abfragt.
CACHE_TTL_SEKUNDEN = 60

# Campaign.status -> Anzeige-Text (siehe Modul-Docstring fuer die Quelle).
# 0 (Draft) und 2 (Paused) werden beide als "pausiert" angezeigt: aus
# Nutzersicht ist der Unterschied irrelevant (in beiden Faellen sendet
# Instantly nichts, und beides ist ein normaler/gewollter Zustand). 4
# (Running Subsequences) zaehlt als "aktiv" (die Kampagne versendet noch).
# Die drei negativen Sonderzustaende (Konto gesperrt/ungesund/Bounce-
# Protect) sind KEIN normales "pausiert" - das Ruhen ist dort ein Fehler,
# keine Absicht, deshalb eigener, lauter Zustand "kontoproblem" statt sie
# still unter "pausiert" verschwinden zu lassen (Review-Fund).
_STATUS_TEXT = {
    0: "pausiert",
    1: "aktiv",
    2: "pausiert",
    3: "abgeschlossen",
    4: "aktiv",
    -99: "kontoproblem",
    -1: "kontoproblem",
    -2: "kontoproblem",
}

# Email.ue_type -> Richtung (siehe Modul-Docstring fuer die Schema-Quelle
# und den TODO zur Live-Verifikation). 1 "Sent from campaign" und 3 "Sent"
# sind beides UNSERE Nachrichten -> "gesendet"; 2 "Received" ist eine
# Antwort des Kontakts -> "empfangen". 4 "Scheduled" ist noch gar nicht
# verschickt und taucht deshalb in _richtung_und_kontakt als eigener Fall
# auf (kein Ereignis, das schon stattgefunden hat - wird ausgeblendet statt
# faelschlich als "gesendet" gezeigt).
_UE_TYPE_GESENDET = {1, 3}
_UE_TYPE_EMPFANGEN = {2}
_UE_TYPE_GEPLANT = {4}


def _parse_zeit(roh: str | None):
    """ISO-8601-Zeitstempel aus der API (z.B. "2026-07-20T09:00:00.000Z")
    zu datetime - defensiv: kaputte/fehlende Werte ergeben None statt
    Absturz (gleiches Prinzip wie web.kontakte: kaputte Einzeldaten
    ueberspringen statt die ganze Seite zu gefaehrden)."""
    if not roh:
        return None
    try:
        return datetime.fromisoformat(roh.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def _richtung_und_kontakt(email: dict) -> tuple[str, str] | None:
    """Bestimmt aus einer rohen Email (siehe Modul-Docstring/Schema) die
    Richtung UND die Kontakt-E-Mail (klein/getrimmt) - oder None, wenn die
    Nachricht nicht anzeigbar ist (geplant/noch nicht verschickt, oder ohne
    auswertbare Adresse). Bei "gesendet" gilt der ERSTE Empfaenger aus
    to_address_email_list (Komma-getrennt, siehe Schema) als Kontakt - fuer
    unsere Kaltakquise-Mails (ein Empfaenger pro Anschreiben) reicht das;
    ein echter Massen-Verteiler waere hier falsch gruppiert, kommt in
    diesem System aber nicht vor."""
    ue_type = email.get("ue_type")
    if ue_type in _UE_TYPE_GEPLANT:
        return None
    if ue_type in _UE_TYPE_EMPFANGEN:
        kontakt = (email.get("from_address_email") or "").strip().lower()
        return ("empfangen", kontakt) if kontakt else None
    # Default (ue_type in _UE_TYPE_GESENDET ODER unbekannt/None): als von
    # uns gesendet behandeln - siehe TODO im Modul-Docstring.
    empfaenger_liste = (email.get("to_address_email_list") or "").split(",")
    kontakt = empfaenger_liste[0].strip().lower() if empfaenger_liste else ""
    return ("gesendet", kontakt) if kontakt else None


def _nachricht_aus_email(email: dict, richtung: str) -> dict | None:
    """Baut aus einer rohen Email + ihrer Richtung eine Anzeige-Nachricht
    ("zeit", "betreff", "text"). Ohne auswertbaren Zeitstempel wird die
    Nachricht ausgeblendet statt unsortierbar mitzulaufen (_parse_zeit
    liefert dann None)."""
    zeit = _parse_zeit(email.get("timestamp_email") or email.get("timestamp_created"))
    if zeit is None:
        return None
    body = email.get("body") or {}
    text = (body.get("text") or "").strip() or (email.get("content_preview") or "").strip()
    return {"richtung": richtung, "zeit": zeit, "betreff": email.get("subject") or "", "text": text}


def konversationen_aus_email_stand(stand_by_id: dict[str, dict]) -> list[dict]:
    """Reine Aufbereitung (kein Netzwerk-Zugriff) - baut aus einem bereits
    abgerufenen emails_stand()-Ergebnis die Konversationsliste: gruppiert
    NACH KONTAKT-E-MAIL ueber ALLE uebergebenen Kampagnen hinweg (nicht je
    Kampagne einzeln - derselbe Kontakt kann in mehreren Kampagnen
    auftauchen, Plan Task 9: "group by contact email"), sortiert die
    Nachrichten je Konversation chronologisch und die Konversationsliste
    selbst nach der juengsten Nachricht zuerst (Plan Task 9). Getrennt von
    InstantlyLeser.konversationen() (siehe dort), damit ein Aufrufer mit
    bereits vorhandenem stand_by_id (z.B. web.routen.postfach, das
    denselben Abruf auch fuer den Live-Stand-Hinweis braucht) nicht ein
    zweites Mal abfragen muss - exakt das Muster aus
    web.routen.kampagnen._stand_fuer / _kampagnen_zeilen_aus_stand."""
    email_zu_konversation: dict[str, dict] = {}
    for eintrag in stand_by_id.values():
        for roh in eintrag.get("items") or []:
            ergebnis = _richtung_und_kontakt(roh)
            if ergebnis is None:
                continue
            richtung, kontakt_email = ergebnis
            nachricht = _nachricht_aus_email(roh, richtung)
            if nachricht is None:
                continue
            konversation = email_zu_konversation.setdefault(
                kontakt_email, {"kontakt_email": kontakt_email, "nachrichten": []})
            konversation["nachrichten"].append(nachricht)

    konversationen = []
    for konversation in email_zu_konversation.values():
        nachrichten = sorted(konversation["nachrichten"], key=lambda m: m["zeit"])
        letzte = nachrichten[-1]
        konversationen.append({
            "kontakt_email": konversation["kontakt_email"],
            "nachrichten": nachrichten,
            "letzte_zeit": letzte["zeit"],
            "betreff": letzte["betreff"],
            "richtung_letzte": letzte["richtung"],
        })
    konversationen.sort(key=lambda k: k["letzte_zeit"], reverse=True)
    return konversationen


class InstantlyLeser:
    """Nur-Lese-Zugriff auf den Instantly-Live-Stand einzelner Kampagnen.

    `jetzt` ist eine injizierbare Uhr (Standard: datetime.now) - Tests
    steuern damit den Cache deterministisch, ohne echte Zeit verstreichen
    zu lassen (gleiches Muster wie die injizierbare `session`)."""

    def __init__(self, api_key, session=None, jetzt=None):
        self.session = session or requests.Session()
        self.headers = {"Authorization": f"Bearer {api_key}"}
        self._jetzt = jetzt or datetime.now
        self._cache: dict[str, dict] = {}
        # Eigener Cache fuer die rohen E-Mails je Kampagne (Task 9,
        # konversationen()/emails_stand()) - bewusst GETRENNT von self._cache
        # oben (Kampagnen-Stand): unterschiedliche Daten je campaign_id,
        # ein gemeinsamer Cache wuerde sich gegenseitig ueberschreiben.
        self._email_cache: dict[str, dict] = {}

    # Hilfsfunktionen --------------------------------------------------

    def _get(self, pfad: str, params: dict):
        antwort = self.session.get(f"{BASIS}{pfad}", headers=self.headers,
                                    params=params, timeout=20)
        if antwort.status_code >= 400:
            raise RuntimeError(
                f"Instantly antwortet mit {antwort.status_code} auf {pfad}")
        return antwort.json()

    def _frisch_genug(self, eintrag: dict) -> bool:
        return (self._jetzt() - eintrag["abgerufen_um"]).total_seconds() < CACHE_TTL_SEKUNDEN

    def _hole_frisch(self, campaign_id: str) -> dict:
        """Ruft die drei GET-Endpunkte fuer genau eine Kampagne ab und baut
        daraus den Anzeige-Datensatz. Wirft weiter (RuntimeError bei
        HTTP-Fehlern, requests.exceptions.RequestException bei Netzwerk-/
        Timeout-Problemen) - kampagnen_stand() faengt das ab."""
        campaign = self._get(f"/campaigns/{campaign_id}", params={})
        status = _STATUS_TEXT.get(campaign.get("status"), "pausiert")
        name = campaign.get("name")

        versendet = None
        antworten = None
        analytics = self._get("/campaigns/analytics", params={"id": campaign_id})
        if analytics:
            versendet = analytics[0].get("emails_sent_count")
            antworten = analytics[0].get("reply_count")

        # je-Schritt-Zaehler nur, wenn die API sie liefert (siehe
        # Modul-Docstring) - eine leere/fehlende Antwort ergibt bewusst eine
        # leere Liste statt eines Fehlers, das Detail-Template zeigt dann
        # einfach keine Fortschrittsbalken statt abzustuerzen.
        schritte_roh = self._get("/campaigns/analytics/steps",
                                  params={"campaign_id": campaign_id}) or []
        summen: dict[str, int] = {}
        for eintrag in schritte_roh:
            schritt = eintrag.get("step")
            if schritt is None:
                continue
            summen[schritt] = summen.get(schritt, 0) + (eintrag.get("sent") or 0)
        schritte = [
            {"schritt": int(schritt) if str(schritt).isdigit() else schritt,
             "versendet": summen[schritt]}
            for schritt in sorted(summen, key=lambda s: (len(str(s)), str(s)))
        ]

        return {"status": status, "name": name, "versendet": versendet,
                "antworten": antworten, "schritte": schritte}

    # Oeffentliche Schnittstelle -----------------------------------------

    def kampagnen_stand(self, campaign_ids: list[str]) -> dict[str, dict]:
        """Liefert je Kampagnen-ID einen Datensatz mit "erreichbar" (bool),
        "status" ("aktiv"/"pausiert"/"abgeschlossen"/None), "name", "versendet"
        (Zahl oder None), "antworten" (Zahl oder None, aus "reply_count"),
        "schritte" (Liste, ggf. leer) und "stand" (Zeitpunkt
        des letzten ERFOLGREICHEN Abrufs, oder None, wenn noch nie einer
        gelang). Fehlertolerant: schlaegt ein Abruf fehl (HTTP-Fehler,
        Timeout, Netzwerkproblem), wird - falls vorhanden - der zuletzt
        bekannte Stand mit "erreichbar": False zurueckgegeben (Seiten zeigen
        dann "Live-Stand gerade nicht erreichbar - Stand von HH:MM" statt
        abzustuerzen); gab es noch nie einen erfolgreichen Abruf, sind die
        Datenfelder None/leer, "stand" bleibt None."""
        ergebnis = {}
        for campaign_id in campaign_ids:
            cache_eintrag = self._cache.get(campaign_id)
            if cache_eintrag is not None and self._frisch_genug(cache_eintrag):
                ergebnis[campaign_id] = {**cache_eintrag["daten"], "erreichbar": True,
                                          "stand": cache_eintrag["abgerufen_um"]}
                continue
            try:
                daten = self._hole_frisch(campaign_id)
            except (requests.exceptions.RequestException, RuntimeError, ValueError, KeyError):
                if cache_eintrag is not None:
                    ergebnis[campaign_id] = {**cache_eintrag["daten"], "erreichbar": False,
                                              "stand": cache_eintrag["abgerufen_um"]}
                else:
                    ergebnis[campaign_id] = {"erreichbar": False, "status": None, "name": None,
                                              "versendet": None, "antworten": None,
                                              "schritte": [], "stand": None}
                continue
            jetzt = self._jetzt()
            self._cache[campaign_id] = {"daten": daten, "abgerufen_um": jetzt}
            ergebnis[campaign_id] = {**daten, "erreichbar": True, "stand": jetzt}
        return ergebnis

    # Postfach (Task 9) --------------------------------------------------

    def _emails_hole_frisch(self, campaign_id: str, limit: int = 100) -> list[dict]:
        """Ein GET auf /emails, begrenzt auf `limit` (Standard 100, siehe
        Modul-Docstring: bewusst OHNE Cursor-Paginierung - ein bounded limit
        je Kampagne reicht fuer die Anzeige). Wirft weiter wie _hole_frisch
        oben - emails_stand() faengt das ab."""
        antwort = self._get("/emails", params={"campaign_id": campaign_id, "limit": limit})
        return (antwort or {}).get("items") or []

    def emails_stand(self, campaign_ids: list[str]) -> dict[str, dict]:
        """Wie kampagnen_stand() (gleiches Cache-/Fehlertoleranz-Muster,
        eigener Cache siehe __init__), aber fuer die ROHEN E-Mails je
        Kampagne statt des Kampagnen-Stands: liefert je campaign_id
        "items" (Liste roher Email-Objekte aus der API, ggf. leer),
        "erreichbar" (bool) und "stand" (Zeitpunkt des letzten erfolgreichen
        Abrufs oder None). Grundlage von konversationen() unten UND von
        web.routen.postfach (fuer den ehrlichen "Live-Stand gerade nicht
        erreichbar"-Hinweis, wiederverwendet ueber
        web.routen.kampagnen._live_stand_hinweis - die Datensatz-Form ist
        absichtlich identisch zu kampagnen_stand()'s Eintraegen, damit diese
        Funktion ohne Anpassung auch hier funktioniert)."""
        ergebnis = {}
        for campaign_id in campaign_ids:
            cache_eintrag = self._email_cache.get(campaign_id)
            if cache_eintrag is not None and self._frisch_genug(cache_eintrag):
                ergebnis[campaign_id] = {"items": cache_eintrag["daten"], "erreichbar": True,
                                          "stand": cache_eintrag["abgerufen_um"]}
                continue
            try:
                items = self._emails_hole_frisch(campaign_id)
            except (requests.exceptions.RequestException, RuntimeError, ValueError, KeyError):
                if cache_eintrag is not None:
                    ergebnis[campaign_id] = {"items": cache_eintrag["daten"], "erreichbar": False,
                                              "stand": cache_eintrag["abgerufen_um"]}
                else:
                    ergebnis[campaign_id] = {"items": [], "erreichbar": False, "stand": None}
                continue
            jetzt = self._jetzt()
            self._email_cache[campaign_id] = {"daten": items, "abgerufen_um": jetzt}
            ergebnis[campaign_id] = {"items": items, "erreichbar": True, "stand": jetzt}
        return ergebnis

    def konversationen(self, campaign_ids: list[str]) -> list[dict]:
        """Bequemlichkeits-Wrapper um emails_stand() + die Modul-Funktion
        konversationen_aus_email_stand() (siehe dort fuer die eigentliche
        Gruppierung/Sortierung) - fuer Aufrufer, die nur die fertige Liste
        brauchen. web.routen.postfach ruft emails_stand() stattdessen
        DIREKT auf (ein Abruf speist dort sowohl die Konversationsliste als
        auch den Live-Stand-Hinweis, siehe emails_stand()-Docstring)."""
        return konversationen_aus_email_stand(self.emails_stand(campaign_ids))
