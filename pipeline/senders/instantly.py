import requests

# Live-Doku (developer.instantly.ai, OpenAPI-Spec unter
# https://api.instantly.ai/openapi/api_v2.json, geprüft 2026-07-16):
#
# Server laut Spec ist "https://api.instantly.ai" (kein separater Host wie
# beim Brief-Entwurf vermutet), Pfade unter "/api/v2/...", Auth per
# "Authorization: Bearer <key>" (securityScheme "ApiKeyAuth", scheme
# "bearer") - das deckt sich mit dem Brief.
#
# POST /api/v2/campaigns (operationId "createCampaign"):
# - Request-Body hat "additionalProperties: false" und KEIN "status"-Feld
#   im Schema. Der Brief-Entwurf wollte "status": "paused" mitschicken -
#   das würde die API mit 400 ablehnen. Neue Kampagnen starten laut
#   Statuswerten in components.schemas.Campaign immer im Zustand
#   "0 = Draft" (Enum-Beschreibung), also inaktiv/inert. Es gibt eigene
#   Endpunkte POST /api/v2/campaigns/{id}/activate und .../pause (siehe
#   guides/api-v1-migration) - diese Klasse ruft NIE "activate" auf, was
#   die geforderte Sicherheitsregel erfüllt ("nie per Code aktiviert").
# - "sequences" ist ein Array, dessen einziges Element ein "steps"-Array
#   ist; jeder Step braucht "type": "email" (einziger erlaubter Wert),
#   "delay" (Zahl, Einheit über "delay_unit", Default "days") und
#   "variants": [{"subject", "body"}] (beides Pflichtfelder je Variante,
#   leerer String ist erlaubt - für Follow-ups reicht das, weil Instantly
#   Antworten im selben Thread ohne neuen Betreff verschickt).
# - "campaign_schedule.schedules[]" braucht "name", "timing" ({"from",
#   "to"} im Format "HH:MM"), "days" (Objekt mit String-Keys "0".."6" als
#   Booleans) und "timezone" (Enum aus ~102 IANA-Zonen).
# - "daily_limit" (Zahl|null) ist die Kampagnen-Voreinstellung "The daily
#   limit for sending emails" - das ist ein Feld auf Kampagnenebene
#   (Summe über alle im Versand befindlichen Postfächer), keine separate
#   Pro-Postfach-Grenze im Create-Payload. Das echte Pro-Postfach-Limit
#   sitzt auf der Account-Ressource (components.schemas.Account.
#   daily_limit, "Daily email sending limit") und wird über eine eigene
#   Accounts-Route gepflegt, die diese Klasse nicht anfasst (sie legt nur
#   die Kampagne an, Postfach-Zuordnung passiert laut Aufgabenbrief von
#   Hand). Bis zur echten Postfach-Zuordnung gilt daily_limit=20 hier als
#   konservative Kampagnen-Obergrenze, die bei genau einem Postfach exakt
#   "20 Mails/Tag pro Postfach" entspricht.
#   # TODO(verifizieren am echten Konto): sobald mehrere Postfächer an die
#   # Kampagne gehängt werden, zusätzlich Account.daily_limit=20 je
#   # Postfach setzen (eigener Endpunkt, hier bewusst nicht abgedeckt).
# - "timezone"-Enum enthält "Europe/Berlin" NICHT (102 Einträge geprüft).
#   "Europe/Belgrade" liegt in derselben CET/CEST-Zeitzonengruppe (gleicher
#   UTC-Versatz, identische EU-Sommerzeit-Regeln) und ist der nächstgelegene
#   gültige Wert.
#   # TODO(verifizieren am echten Konto): am echten Instantly-Konto prüfen,
#   # dass "Europe/Belgrade" die Uhrzeiten tatsächlich wie Berlin behandelt
#   # (sollte laut IANA-Regeln identisch sein, aber am Kalender im
#   # Instantly-UI gegenprüfen).
# - Für die Wochentage im "days"-Objekt gibt es an dieser Stelle im Schema
#   keine Beschreibung. Das strukturgleiche Feld bei
#   components.schemas.InboxPlacementTest.properties.schedule.properties.
#   days dokumentiert ausdrücklich "keys are integers (0-6, 0 = Sunday)".
#   Diese Klasse übernimmt dieselbe Konvention (0=So, 1=Mo, ..., 6=Sa).
#   # TODO(verifizieren am echten Konto): am echten Konto eine Testkampagne
#   # anlegen und im UI prüfen, dass Mo-Fr tatsächlich als Versandtage
#   # markiert sind (Konvention nur per Analogie zu einem anderen Endpunkt
#   # belegt, nicht direkt für campaign_schedule dokumentiert).
#
# POST /api/v2/leads/add (operationId nicht "leads/import" wie im
# Brief-Entwurf, sondern "/api/v2/leads/add"; Beschreibung: "Adds up to
# 1000 leads to either a campaign or a list."):
# - Body: {"campaign_id": <uuid>, "leads": [...]} - "campaign_id" ODER
#   "list_id", hier immer "campaign_id". Jedes Lead-Objekt darf
#   "custom_variables" (Objekt aus string/number/boolean/null-Werten)
#   tragen; die Doku bestätigt ausdrücklich, dass die Kampagne dadurch für
#   alle Leads dieselben Custom-Variablen kennt - das ist der Mechanismus,
#   über den {{betreff}}, {{mail_1}} usw. in den Sequenz-Vorlagen befüllt
#   werden.
# - "verify_leads_on_import" (bool) existiert als Option für die
#   eingebaute Verifizierung. Ob das im Team-Tarif enthalten ist (Risiko 3
#   im Brief), ist eine Tarif-/Kontofrage, keine Doku-Frage - deshalb hier
#   bewusst NICHT gesetzt (Default aus, kein Verifizierungs-Verbrauch ohne
#   ausdrückliche Freigabe).
#   # TODO(verifizieren am echten Konto): klären, ob der Team-Tarif
#   # Lead-Verifizierung enthält, bevor "verify_leads_on_import": true
#   # irgendwo gesetzt wird.
#
# VERIFIZIERT AM LIVE-KONTO (2026-07-17, Kampagne
# 580bdbf7-fe41-43d4-b07d-8460997925f8): "delay" auf einem Sequenz-Schritt
# ist NICHT die Wartezeit VOR diesem Schritt, sondern die Wartezeit NACH
# diesem Schritt, bevor der NÄCHSTE Schritt verschickt wird ("the delay
# configured under Step 1 determines when Step 2 is sent" - Instantly
# Help Center, "Time to Wait Between Steps",
# https://help.instantly.ai/en/articles/7916860-time-to-wait-between-steps).
# Live-Befund bestätigt das: mit der alten Zuordnung (Schritt 0 delay=0,
# Schritt 1 delay=follow_up_tage[0]) kam Follow-up 1 neun Minuten nach
# Mail 1 statt nach follow_up_tage[0] Tagen - weil delay=0 auf Schritt 0
# stand, nicht auf Schritt 1. Die Zuordnung unten ist entsprechend um
# einen Schritt verschoben: Schritt 0 trägt den Delay bis Follow-up 1,
# Schritt 1 trägt den Delay bis Follow-up 2 (als Differenz, siehe unten).
BASIS = "https://api.instantly.ai/api/v2"

class InstantlySender:
    def __init__(self, api_key, session=None):
        self.session = session or requests.Session()
        self.headers = {"Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"}

    def _post(self, url, payload):
        """Postet und scheitert laut statt leise (wie apollo.py, aber ohne
        Wiederholung: ein fehlgeschlagenes Kampagnen-Setup soll den Lauf
        sofort stoppen statt mit unvollstaendigen Daten weiterzumachen -
        der Mensch behebt die Ursache und startet "senden" danach neu)."""
        antwort = self.session.post(url, headers=self.headers, json=payload, timeout=60)
        if antwort.status_code >= 400:
            ausschnitt = (getattr(antwort, "text", "") or "")[:200]
            raise RuntimeError(
                f"Instantly antwortet mit {antwort.status_code} auf {url}: {ausschnitt}")
        return antwort

    def create_campaign(self, kunde) -> str:
        """Legt nur die (pausierte) Kampagne an - ohne Leads. Getrennt von
        import_leads(), damit "senden" nach einem Fehler beim Lead-Import
        nicht versehentlich eine zweite Kampagne anlegt: der Laufordner
        merkt sich die campaign_id nach diesem Schritt und ein
        Wiederanlauf ruft nur noch import_leads() erneut auf."""
        # follow_up_tage=[a, b] bedeutet "Follow-up 1 an Tag a, Follow-up 2 an
        # Tag b" (Gesamtabstand ab Mail 1). Instantly zaehlt "delay" aber ab
        # dem Schritt, auf dem er steht, bis zum naechsten Schritt (siehe
        # Kommentar oben, live verifiziert) - deshalb steht der Delay bis
        # Follow-up 1 auf Schritt 0 (a Tage) und der Delay bis Follow-up 2
        # auf Schritt 1 (b - a Tage, der Rest-Abstand). Schritt 2 hat keinen
        # Nachfolger, sein delay ist folgenlos -> 0.
        a, b = kunde.follow_up_tage[0], kunde.follow_up_tage[1]
        if b <= a:
            raise ValueError(
                f"follow_up_tage muss aufsteigend sein (Tag a < Tag b), "
                f"gefunden: [{a}, {b}]. Bitte kunde.yaml korrigieren.")
        sequenz_schritte = [
            {"type": "email", "delay": a,
             "variants": [{"subject": "{{betreff}}", "body": "{{mail_1}}"}]},
            {"type": "email", "delay": b - a,
             "variants": [{"subject": "", "body": "{{follow_up_1}}"}]},
            {"type": "email", "delay": 0,
             "variants": [{"subject": "", "body": "{{follow_up_2}}"}]},
        ]
        kampagne = {
            "name": f"[TEST] {kunde.name}",
            # Kein "status"-Feld - Kampagne bleibt automatisch "Draft"
            # (inaktiv). Diese Klasse ruft niemals /activate auf.
            "campaign_schedule": {
                "schedules": [{
                    "name": "Mo-Fr 08-19 Europe/Berlin",
                    "timing": {"from": "08:00", "to": "19:00"},
                    # Mo-Fr an, Sa/So aus (0=So ... 6=Sa, siehe Kommentar oben).
                    "days": {"0": False, "1": True, "2": True, "3": True,
                              "4": True, "5": True, "6": False},
                    "timezone": "Europe/Belgrade",
                }],
            },
            "sequences": [{"steps": sequenz_schritte}],
            # Schutz-Voreinstellung: max. 20 Mails/Tag (siehe Kommentar oben
            # zu Kampagnen- vs. Postfach-Ebene).
            "daily_limit": 20,
        }
        antwort = self._post(f"{BASIS}/campaigns", kampagne)
        return antwort.json()["id"]

    def import_leads(self, campaign_id: str, texte_pro_lead):
        """Importiert die Leads in eine bereits angelegte Kampagne. Eigener
        Guard hier (zusaetzlich zum Guard in "senden"), damit ein direkter
        Aufruf dieser Methode nie versehentlich einen leeren Import an
        Instantly schickt."""
        if not texte_pro_lead:
            raise ValueError("Keine freigegebenen Texte - kein Lead-Import.")
        leads = [{"email": t["email"],
                  "custom_variables": {k: t[k] for k in
                                       ("betreff", "mail_1", "follow_up_1", "follow_up_2")}}
                 for t in texte_pro_lead]
        self._post(f"{BASIS}/leads/add", {"campaign_id": campaign_id, "leads": leads})
