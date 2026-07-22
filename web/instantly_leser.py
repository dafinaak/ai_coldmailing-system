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
- GET /api/v2/accounts/analytics/daily (Query-Parameter "start_date" und
  "end_date"): liefert eine LISTE je Datum und Absenderpostfach mit
  "date", "email_account" und "sent". Der Endpunkt ist konto- statt
  kampagnenbezogen; deshalb werden unten ausschliesslich Zeilen der
  tatsaechlich in Campaign.email_list verwendeten Absender summiert. Ein
  Ausfall dieses Zusatzabrufs macht nur "heute_versendet" unbekannt und
  verwirft nicht die weiterhin erreichbaren Kampagnen-/Schrittwerte.

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
  # behandelt.

Step-0-Live-Doku-Pruefung fuer Baustein 2 (Postfaecher-Ansicht), PFLICHT vor
dem Bau: zusaetzlich zur Doku-Pruefung diesmal ein ECHTER GET-only-Abruf
gegen das Team-Konto (mit dem Key aus .env, keine Aenderung ausgeloest,
siehe docs/instantly-api-machbarkeit.md Punkt 4 fuer den Kontext) am
20.07.2026, weil der Machbarkeits-Check zwei Felder nannte, die die Doku
zwar im Schema fuehrt, die im echten Konto aber gefehlt haben:

- GET /api/v2/accounts (operationId "listAccount"): Antwort
  {"items": [Account], "next_starting_after": str} - genau wie bei
  /emails oben bewusst OHNE Cursor-Paginierung (limit=100 reicht: das
  Team-Konto hatte beim Probe-Abruf 10 Postfaecher).
- components.schemas.Account, hier genutzte Felder: "email"* (String),
  "status"* (Zahlen-Enum, x-enumDescriptions: 1=Active, 2=Paused,
  3=Temporarily paused for maintenance [automatische Wiederaufnahme],
  -1=Connection Error, -2=Soft Bounce Error, -3=Sending Error),
  "warmup_status"* (Zahlen-Enum: 0=Paused, 1=Active, -1=Banned,
  -2=Spam Folder Unknown, -3=Permanent Suspension), "daily_limit"
  (Zahl|null, Schema-Beispiel 100).
- LIVE-BEFUND (weicht von der reinen Schema-Lektuere ab): "daily_limit"
  fehlte bei ALLEN 10 Postfaechern im echten Abruf komplett (kein Schluessel
  im JSON, nicht einmal null) - vermutlich, weil dort nie ein Wert gesetzt
  wurde. postfaecher() unten behandelt das defensiv (.get() ohne Default
  -> None), die Anzeige zeigt dafuer "-" statt eines erfundenen Werts
  (gleiches Prinzip wie dash.KEIN_WERT).
- LIVE-BEFUND: eines der 10 Postfaecher hatte status=-1 (Connection Error)
  UND ein aussagekraeftiges "status_message.e_message" (OAuth-Token
  abgelaufen) - dieses Feld wird hier bewusst NICHT ausgewertet (nur die
  Zahl "status"), ein Freitext aus der API roh auf der Seite auszugeben
  waere weder uebersetzt noch fuer Laien verstaendlich; der Instantly-Link
  fuehrt fuer die Detailsuche dorthin."""
from __future__ import annotations

import os
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

# Account.status -> Anzeige-Text (Baustein 2, siehe Modul-Docstring fuer die
# Live-verifizierte Quelle). 2 (Paused, absichtlich vom Team angehalten) und
# 3 (Temporarily paused for maintenance, Instantly nimmt automatisch wieder
# auf) sind beide ein normaler, nicht-alarmierender Ruhezustand -> "pausiert".
# Die drei negativen Zustaende sind dagegen ein ECHTES Verbindungsproblem
# (Login/Zustellung kaputt, siehe status_message im Modul-Docstring) -> der
# eigene, laute Zustand "verbindungsfehler" (gleiches Prinzip wie
# "kontoproblem" bei Kampagnen oben: nie still unter "pausiert" verstecken).
_POSTFACH_STATUS_TEXT = {
    1: "verbunden",
    2: "pausiert",
    3: "pausiert",
    -1: "verbindungsfehler",
    -2: "verbindungsfehler",
    -3: "verbindungsfehler",
}

# Account.warmup_status -> Anzeige-Text (Baustein 2). 1 (Active) heisst: das
# automatische Aufwaerm-Programm laeuft gerade -> "an"; 0 (Paused) heisst
# ausgeschaltet/pausiert -> "aus". -1/-3 sind ein dauerhaftes Sperr-Problem
# (Banned/Permanent Suspension) -> "gesperrt"; -2 (Spam Folder Unknown) ist
# kein Totalausfall, aber ein unklarer Zustellbarkeits-Zustand -> "problem".
_POSTFACH_WARMUP_TEXT = {
    1: "an",
    0: "aus",
    -1: "gesperrt",
    -2: "problem",
    -3: "gesperrt",
}


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


def _sendefenster_aus_campaign(campaign: dict) -> list[dict]:
    """Uebersetzt die von Instantly gelesenen Sendefenster ohne fehlende
    Angaben zu ergaenzen."""
    ergebnis = []
    for eintrag in (campaign.get("campaign_schedule") or {}).get("schedules") or []:
        timing = eintrag.get("timing") or {}
        ergebnis.append({
            "name": eintrag.get("name"),
            "von": timing.get("from"),
            "bis": timing.get("to"),
            "tage": eintrag.get("days") or {},
            "zeitzone": eintrag.get("timezone"),
        })
    return ergebnis


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
        # Cache fuer postfaecher() (Baustein 2) - anders als die beiden Caches
        # oben NICHT je ID (es gibt keine ID: ein Abruf liefert ALLE
        # Postfaecher des Konto auf einmal), deshalb ein einzelner Slot statt
        # eines dict. None, solange noch nie erfolgreich abgerufen wurde.
        self._postfach_cache: dict | None = None

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

    def _tagesversand_fuer_absender(self, absender: list, heute: str) -> int | None:
        """Liest den konto-weiten Tagesversand und summiert nur die in der
        Kampagne verwendeten Absender. Fehlende Absenderzeilen oder Werte
        bleiben unbekannt; ein Fehler dieses Zusatz-Endpunkts darf den
        uebrigen Kampagnenstand nicht unbrauchbar machen."""
        if not isinstance(absender, list):
            return None
        verwendete_absender = {
            email.strip().casefold()
            for email in absender
            if isinstance(email, str) and email.strip()
        }
        if not verwendete_absender:
            return None
        try:
            tageswerte = self._get("/accounts/analytics/daily", params={
                "start_date": heute, "end_date": heute,
            })
        except (requests.exceptions.RequestException, RuntimeError, ValueError, KeyError):
            return None
        if not isinstance(tageswerte, list):
            return None

        gefunden = set()
        summe = 0
        for zeile in tageswerte:
            if not isinstance(zeile, dict) or zeile.get("date") != heute:
                continue
            email = zeile.get("email_account")
            if not isinstance(email, str):
                continue
            normalisiert = email.strip().casefold()
            if normalisiert not in verwendete_absender:
                continue
            wert = zeile.get("sent")
            if not isinstance(wert, int) or isinstance(wert, bool):
                return None
            gefunden.add(normalisiert)
            summe += wert
        return summe if gefunden == verwendete_absender else None

    def _hole_frisch(self, campaign_id: str) -> dict:
        """Ruft die vier GET-Endpunkte fuer genau eine Kampagne ab und baut
        daraus den Anzeige-Datensatz. Wirft weiter (RuntimeError bei
        HTTP-Fehlern, requests.exceptions.RequestException bei Netzwerk-/
        Timeout-Problemen) - kampagnen_stand() faengt das ab."""
        campaign = self._get(f"/campaigns/{campaign_id}", params={})
        status = _STATUS_TEXT.get(campaign.get("status"), "pausiert")
        name = campaign.get("name")
        absender = campaign.get("email_list") or []

        analytics_eintrag = {}
        analytics = self._get("/campaigns/analytics", params={"id": campaign_id})
        if analytics:
            analytics_eintrag = analytics[0]

        heute = self._jetzt().date().isoformat()
        heute_versendet = self._tagesversand_fuer_absender(absender, heute)

        # je-Schritt-Zaehler nur, wenn die API sie liefert (siehe
        # Modul-Docstring) - eine leere/fehlende Antwort ergibt bewusst eine
        # leere Liste statt eines Fehlers, das Detail-Template zeigt dann
        # einfach keine Fortschrittsbalken statt abzustuerzen.
        schritte_roh = self._get("/campaigns/analytics/steps",
                                  params={"campaign_id": campaign_id}) or []
        summen: dict[str, dict[str, int | None]] = {}
        for eintrag in schritte_roh:
            schritt = eintrag.get("step")
            if schritt is None:
                continue
            summe = summen.setdefault(schritt, {"versendet": 0, "geoeffnet": 0})
            for ausgabe_feld, api_feld in (("versendet", "sent"), ("geoeffnet", "opened")):
                wert = eintrag.get(api_feld)
                if wert is None:
                    summe[ausgabe_feld] = None
                elif summe[ausgabe_feld] is not None:
                    summe[ausgabe_feld] += wert
        schritte = [
            {"schritt": int(schritt) if str(schritt).isdigit() else schritt,
             "versendet": summen[schritt]["versendet"],
             "geoeffnet": summen[schritt]["geoeffnet"]}
            for schritt in sorted(summen, key=lambda s: (len(str(s)), str(s)))
        ]

        erstellt_am = campaign.get("timestamp_created")
        if _parse_zeit(erstellt_am) is None:
            erstellt_am = None

        return {
            "status": status,
            "name": name,
            "erstellt_am": erstellt_am,
            "empfaenger": analytics_eintrag.get("leads_count"),
            "versendet": analytics_eintrag.get("emails_sent_count"),
            "geoeffnet": analytics_eintrag.get("open_count"),
            "antworten": analytics_eintrag.get("reply_count"),
            "unzustellbar": analytics_eintrag.get("bounced_count"),
            "abgeschlossen": analytics_eintrag.get("completed_count"),
            "heute_versendet": heute_versendet,
            "absender": absender,
            "sendefenster": _sendefenster_aus_campaign(campaign),
            "schritte": schritte,
        }

    # Oeffentliche Schnittstelle -----------------------------------------

    def kampagnen_stand(self, campaign_ids: list[str]) -> dict[str, dict]:
        """Liefert je Kampagnen-ID einen Datensatz mit "erreichbar" (bool),
        "status" ("aktiv"/"pausiert"/"abgeschlossen"/None), "name",
        "erstellt_am" (roher ISO-Zeitstempel oder None),
        "empfaenger", "versendet", "geoeffnet", "antworten",
        "unzustellbar", "abgeschlossen" und "heute_versendet" (jeweils
        Zahl oder None), "absender" und "sendefenster" (Listen, ggf. leer),
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
                    ergebnis[campaign_id] = {
                        "erreichbar": False, "status": None, "name": None,
                        "erstellt_am": None,
                        "empfaenger": None, "versendet": None, "geoeffnet": None,
                        "antworten": None, "unzustellbar": None, "abgeschlossen": None,
                        "heute_versendet": None, "absender": [], "sendefenster": [],
                        "schritte": [], "stand": None,
                    }
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

    # Postfaecher-Uebersicht (Baustein 2) ---------------------------------

    def _postfach_aus_account(self, account: dict) -> dict:
        """Baut aus einem rohen Account (siehe Modul-Docstring/Schema) eine
        Anzeige-Zeile. "daily_limit" bleibt None, wenn die API das Feld nicht
        mitschickt (live beobachtet, siehe Modul-Docstring) statt einen Wert
        zu erfinden - die Seite zeigt dann "-" statt einer Zahl."""
        return {
            "email": account.get("email"),
            "status": _POSTFACH_STATUS_TEXT.get(account.get("status"), "unbekannt"),
            "warmup": _POSTFACH_WARMUP_TEXT.get(account.get("warmup_status"), "unbekannt"),
            "daily_limit": account.get("daily_limit"),
        }

    def _postfaecher_hole_frisch(self) -> list[dict]:
        """Ein GET auf /accounts, begrenzt auf limit=100 (siehe
        Modul-Docstring: bewusst OHNE Cursor-Paginierung, das Team-Konto
        hatte beim Probe-Abruf 10 Postfaecher - reicht bei weitem). Wirft
        weiter wie _hole_frisch/_emails_hole_frisch oben - postfaecher()
        faengt das ab."""
        antwort = self._get("/accounts", params={"limit": 100})
        items = (antwort or {}).get("items") or []
        return [self._postfach_aus_account(a) for a in items]

    def postfaecher(self) -> dict:
        """Liefert "postfaecher" (Liste aller Sende-Postfaecher des Konto,
        siehe _postfach_aus_account fuer die Feldform), "erreichbar" (bool)
        und "stand" (Zeitpunkt des letzten ERFOLGREICHEN Abrufs, oder None,
        wenn noch nie einer gelang). Gleiches Cache-/Fehlertoleranz-Muster
        wie kampagnen_stand()/emails_stand() oben (60s, eigener Cache-Slot
        siehe __init__, letzter bekannter Stand bleibt bei einem Ausfall
        sichtbar mit "erreichbar": False) - Seiten zeigen dann "Live-Stand
        gerade nicht erreichbar" statt abzustuerzen (web.routen.kampagnen.
        _live_stand_hinweis erwartet dieselbe Datensatz-Form wie hier, siehe
        dort - dieses Ergebnis passt direkt ohne Anpassung)."""
        cache_eintrag = self._postfach_cache
        if cache_eintrag is not None and self._frisch_genug(cache_eintrag):
            return {"postfaecher": cache_eintrag["daten"], "erreichbar": True,
                     "stand": cache_eintrag["abgerufen_um"]}
        try:
            daten = self._postfaecher_hole_frisch()
        except (requests.exceptions.RequestException, RuntimeError, ValueError, KeyError):
            if cache_eintrag is not None:
                return {"postfaecher": cache_eintrag["daten"], "erreichbar": False,
                         "stand": cache_eintrag["abgerufen_um"]}
            return {"postfaecher": [], "erreichbar": False, "stand": None}
        jetzt = self._jetzt()
        self._postfach_cache = {"daten": daten, "abgerufen_um": jetzt}
        return {"postfaecher": daten, "erreichbar": True, "stand": jetzt}


def geteilten_leser(app) -> InstantlyLeser:
    """Liefert EINEN InstantlyLeser, geteilt ueber ALLE Requests dieser App
    (IMPORTANT Review-Fund: der 60s-Cache oben wirkt nur, wenn wirklich
    dasselbe Objekt wiederverwendet wird - ein frischer InstantlyLeser pro
    Request/Aufruf haette IMMER einen leeren Cache, egal was CACHE_TTL_
    SEKUNDEN sagt). web.app.create_app baut ihn EAGER beim App-Start, wenn
    INSTANTLY_API_KEY zu dem Zeitpunkt schon gesetzt ist; ist er das nicht
    (z.B. Tests, die die Variable erst spaeter setzen), wird er hier beim
    ERSTEN Bedarf gebaut - abgesichert durch app.state._instantly_leser_lock
    gegen einen Race, wenn zwei Requests gleichzeitig als erste ankommen
    (FastAPI/Starlette fuehrt sync-Routen in einem Threadpool aus, siehe
    web.routen.kampagnen/postfach _hole_leser - echte Nebenlaeufigkeit ist
    hier also moeglich, kein theoretisches Risiko)."""
    leser = getattr(app.state, "instantly_leser", None)
    if leser is not None:
        return leser
    with app.state._instantly_leser_lock:
        leser = getattr(app.state, "instantly_leser", None)
        if leser is None:
            leser = InstantlyLeser(os.environ["INSTANTLY_API_KEY"])
            app.state.instantly_leser = leser
        return leser
