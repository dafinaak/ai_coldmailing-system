# Instantly API v2 – Machbarkeits-Check

Stand: 2026-07-20. Reine Untersuchung, nichts wurde aktiviert, gesendet oder verändert.
Quelle: OpenAPI-Spec `https://api.instantly.ai/openapi/api_v2.json` (developer.instantly.ai)
plus GET-only-Proben gegen das echte Team-Konto (mit dem Key aus `.env`,
`INSTANTLY_API_KEY`, geladen über `pipeline.env.lade_dotenv`).

**Aktueller API-Key:** `GET /api/v2/api-keys` zeigt Scope `all:all` (voller
Zugriff). Für die Untersuchung praktisch – für den produktiven Aufbau später
überlegen, ob ein enger gescoppter Key (z.B. nur `campaigns:update`,
`emails:create`, `accounts:read`) sinnvoller ist, um Fehlbedienung im eigenen
Tool zu begrenzen.

---

## 1. Kampagne im Tool scharf schalten

**Feasible: ja · Aufwand: S**

- `POST /api/v2/campaigns/{id}/activate` (operationId `activateCampaign`) –
  kein Request-Body, nur die Kampagnen-ID im Pfad. Antwort: das komplette
  Campaign-Objekt (Status ist danach direkt sichtbar). Scope:
  `campaigns:update`/`campaigns:all`/`all:update`/`all:all`.
- `POST /api/v2/campaigns/{id}/pause` (operationId `pauseCampaign`) – exakt
  gleiches Muster, gleicher Scope.
- Bonus-Fund: `GET /api/v2/campaigns/{id}/sending-status` liefert eine
  Diagnose, WARUM eine Kampagne gerade nicht sendet. Live getestet, echtes
  Ergebnis: `"status":"campaign_accounts_unhealthy","status_message":"None
  of the sending accounts are healthy, connected, or usable..."` – das ist
  sofort einsatzbereit für eine Vorab-Prüfung, bevor man scharf schaltet.

**GET-Probe:** `GET /api/v2/campaigns` gelistet, 4 Kampagnen im Konto
gefunden mit Status -1 (Kontoproblem), 0 (Draft), 3 (Abgeschlossen), 0
(Draft). Aktivierung selbst NICHT aufgerufen (Sicherheitsregel).

**Risiko:** kein technischer Blocker. Aber: eine der Kampagnen hängt gerade
an einem Konto mit echtem Verbindungsproblem (siehe Punkt 4) – bevor
"scharf schalten" im eigenen Tool gebaut wird, sollte die
Postfach-Gesundheit ohnehin geprüft werden, sonst schaltet man eine
Kampagne scharf, die gar nicht senden kann.

---

## 2. Postfach: Antworten lesen

**Feasible: ja (mit einer Einschränkung bei Bounces) · Aufwand: M**

- Kein separater "Unibox"-Endpoint gefunden (Spec komplett nach `unibox`
  durchsucht – keine eigene Route). `GET /api/v2/emails` (operationId
  `listEmail`) IST das faktische Unibox-Äquivalent: die Antwort-Objekte
  tragen zusätzlich `is_unread`, `is_focused`, `thread_id`, `lead`/
  `lead_id`, `message_id`.
- **Live bestätigt:** `GET /emails` OHNE `campaign_id`-Filter liefert Mails
  über das ganze Konto, nicht nur pro Kampagne. Das eigene Tool nutzt
  aktuell (`web/instantly_leser.py`) immer `campaign_id` – ließe sich also
  auf den vollen Posteingang umstellen, ohne neuen Endpoint zu brauchen.
- **`ue_type` live verifiziert:** unsere automatischen Kampagnen-Mails
  tragen `ue_type=1` ("Sent from campaign") – der bestehende TODO im Code
  dazu kann als bestätigt gelten. `ue_type=2` (Received) und `=3` (manuell
  gesendet) waren im Testkonto nicht vorhanden (keine offene Antwort im
  Konto), daher nur aus dem Schema, nicht live an Empfangsdaten bestätigt.
- **Bounces:** kein eigenes Bounce-Feld/Endpoint auf E-Mail-Ebene gefunden.
  Bounces zeigen sich nur indirekt über `Account.status=-2` ("Soft Bounce
  Error") auf Postfach-Ebene. Für eine granulare Bounce-Liste bräuchte es
  vermutlich eigene Auswertung der Mail-Inhalte/Header – nicht abschließend
  in der Doku belegt, das ist die größte Unbekannte in diesem Block.
- Zusatzfunde (live getestet, funktionieren): `POST
  /api/v2/emails/threads/{thread_id}/mark-as-read`, `GET
  /api/v2/emails/unread/count` (aktuell 0 ungelesen im Konto).

**GET-Probe:** 5 Kampagnen-Mails abgerufen (alle `ue_type=1`), volles
Postfach ohne Filter ebenfalls abgerufen (gleiches Bild, eine Kampagne
aktiv), `unread/count` = 0.

---

## 3. Postfach: Antworten schreiben

**Feasible: ja laut Doku · Aufwand: S–M** (NICHT aufgerufen, nur Doku
geprüft)

- `POST /api/v2/emails/reply` (operationId `replyToEmail`). Body:
  `eaccount` (sendendes Postfach), `reply_to_uuid` (die `id` der
  Original-Mail aus `/emails`), `subject`, `body: {html, text}`, optional
  `cc_address_email_list`, `bcc_address_email_list`,
  `additional_recipients`, `reminder_ts`, `assigned_to`. Scope
  `emails:create`.
- Zusätzlich existiert `POST /api/v2/emails/forward` (operationId
  `forwardEmail`) fürs Weiterleiten, gleiches Payload-Muster.
- Payload selbst ist einfach. Die eigentliche Arbeit ist, den
  Freigabe-Workflow (Mensch bestätigt vor dem Absenden, wie beim jetzigen
  Kampagnen-Versand) im eigenen Tool nachzubauen – nicht der API-Call.

**Risiko:** kein technischer Blocker erkennbar. Vor produktivem Einsatz:
mit einem Test-Postfach und Test-Empfänger prüfen (Regel "nie direkt in
Produktion testen").

---

## 4. Postfächer / Anwärm-Status

**Feasible: ja · Aufwand: S**

`GET /api/v2/accounts` (operationId `listAccount`) liefert je Postfach
u.a.:

- `status`: 1 Active, 2 Paused, 3 Temporarily paused for maintenance
  (automatische Wiederaufnahme), -1 Connection Error, -2 Soft Bounce
  Error, -3 Sending Error
- `warmup_status`: 0 Paused, 1 Active, -1 Banned, -2 Spam Folder Unknown,
  -3 Permanent Suspension
- `stat_warmup_score` (0–100)
- `daily_limit`, `sending_gap`
- `provider_code`: 1 Custom IMAP/SMTP, 2 Google, 3 Microsoft, 4 AWS, 8
  AirMail
- `setup_pending`, `is_managed_account`, `autofix_failed` (null = läuft
  gerade, true = fehlgeschlagen, false = erfolgreich)

**GET-Probe (5 Postfächer):** 4 gesund (`status=1`, `warmup_status=1`,
Score 99–100), 1 mit `status=-1` (Connection Error) UND
`autofix_failed=true` – also ein echtes, gerade bestehendes Problem im
Live-Konto (passt zum "campaign_accounts_unhealthy" Fund aus Punkt 1).

Zusatz-Endpoints laut Doku, nicht aufgerufen: `POST
/accounts/{email}/pause`, `/resume`, `/mark-fixed`, `POST
/accounts/warmup/enable`, `/disable`, `POST /accounts/move`, `GET
/accounts/analytics/daily`.

---

## Überraschungsfund: neues Postfach verbinden geht doch (teilweise) per API

Die ursprüngliche Annahme im Auftrag war, dass eine neue Mailbox nur im
Instantly-UI verbunden werden kann. Laut Doku stimmt das nicht ganz:

- `POST /api/v2/oauth/google/init` bzw. `.../microsoft/init` erzeugen eine
  OAuth-Session inkl. `auth_url`. `GET
  /api/v2/oauth/session/status/{sessionId}` pollt das Ergebnis
  (`pending`/`success`/`error`/`expired`, Session läuft nach 10 Minuten
  ab). Das eigene Tool könnte diesen Ablauf orchestrieren (Link anzeigen,
  Ergebnis abfragen) – aber der Login/die Zustimmung bei Google/Microsoft
  selbst muss der Mensch weiterhin im Browser machen (das ist bei OAuth so
  gewollt, kein Instantly-spezifisches Manko).
- `POST /api/v2/accounts` (operationId `createAccount`) erlaubt zusätzlich
  das direkte Anlegen eines Custom-IMAP/SMTP-Postfachs komplett per API
  (SMTP/IMAP-Zugangsdaten im Payload) – ganz ohne OAuth-Zwischenschritt.
  Funktioniert aber nur für Custom-IMAP/SMTP, nicht für "echtes"
  Google-/Microsoft-Postfach-Onboarding mit deren eigener Absicherung.

---

## Gaps, die weiter ins Instantly-UI zwingen (oder zumindest in einen Browser)

1. **OAuth-Login-Schritt bei Google/Microsoft-Postfächern:** lässt sich
   einbetten/verlinken, aber der eigentliche Login/die Zustimmung passiert
   zwangsläufig in einem Google-/Microsoft-Fenster außerhalb des eigenen
   Tools. Kein Instantly-Gap im engeren Sinn, sondern OAuth-Prinzip – aber
   der Nutzer verlässt für diesen einen Schritt das eigene Tool.
2. **Bounce-Erkennung auf E-Mail-Ebene:** kein sauberes Feld/Endpoint
   gefunden, nur der indirekte Weg über `Account.status=-2`. Für eine
   "diese eine Mail ist ein Bounce"-Anzeige bräuchte es vermutlich eigene
   Interpretation der Mail-Inhalte – nicht abschließend in der Doku
   verifiziert, größte offene Frage in diesem Check.
3. **`ue_type=2`/`=3` (Received/manuell gesendet) nur aus dem Schema
   bestätigt**, nicht an echten Live-Daten, weil im Testkonto aktuell keine
   Antwort vorliegt – sollte vor dem Bau von Punkt 2 mit einer echten
   Test-Antwort noch einmal live geprüft werden.
