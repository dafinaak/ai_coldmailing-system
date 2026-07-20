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
wird hier bewusst noch nicht angebunden, das ist Aufgabe von Task 9."""
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
