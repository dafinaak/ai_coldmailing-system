# Instantly als Kontakt-Quelle statt Apollo – Machbarkeits-Check

Stand: 2026-07-21. Reine Untersuchung, nichts wurde gekauft, gesucht oder
angereichert – nur Dokumentation gelesen und lesende (GET-)Proben gegen das
echte Team-Konto gemacht. Quelle: OpenAPI-Spec
`https://api.instantly.ai/openapi/api_v2.json` (developer.instantly.ai) plus
zwei GET-Proben mit dem Key aus `.env` (`INSTANTLY_API_KEY`).

**Frage dahinter:** Apollo-Guthaben ist aufgebraucht. Das Team zahlt Instantly
sowieso schon – hat Instantly eine eigene Kontakt-Datenbank, die Apollo in
Stufe 2 unserer Pipeline ersetzen könnte (aus einer Firma von Google Maps
die passenden Ansprechpartner mit E-Mail finden)?

---

## Kurz-Antwort: Ja, per API nutzbar – aber gerade blockiert, weil kein Guthaben vorhanden ist

Instantly hat eine eigene Lead-Datenbank-Suche ("SuperSearch"), die genau das
kann, was wir von Apollo brauchen: nach Firma (Domain) UND Rolle (Titel)
filtern und Personen mit verifizierter Arbeits-E-Mail liefern. Das Konto
zahlt aber gerade **kein** Guthaben dafür – siehe Punkt 2.

---

## 1. Gibt es eine Lead-Datenbank-Suche (nicht nur Kampagnen-Verwaltung)?

**Ja.** Instantly trennt klar zwischen zwei verschiedenen Dingen, die beide
"leads" heißen:

- `POST /api/v2/leads/*`, `GET /api/v2/leads/list` usw. – das ist nur die
  Verwaltung von Kontakten, die schon in einer unserer Listen/Kampagnen
  liegen (Kontakt anlegen/löschen/verschieben). Das ist NICHT die
  Datenbank-Suche, die wir suchen.
- **`supersearch-enrichment`** – das ist die echte Lead-Datenbank-Suche
  (Instantlys "SuperSearch", Pendant zu Apollos People-Search):
  - `POST /api/v2/supersearch-enrichment/preview-leads-from-supersearch` –
    zeigt Treffer für eine Such-Anfrage an, OHNE sie anzureichern (also ohne
    E-Mail-Adresse zu ziehen). Antwort pro Person: Name, Job-Titel, Ort,
    LinkedIn-Profil, Firmenname – **keine E-Mail**. Entspricht genau Apollos
    "Search"-Schritt (auch dort kommt die E-Mail erst im zweiten Schritt).
  - `POST /api/v2/supersearch-enrichment/count-leads-from-supersearch` –
    liefert nur die Trefferzahl, zum Abschätzen vor dem eigentlichen Suchen.
  - `POST /api/v2/supersearch-enrichment/enrich-leads-from-supersearch` –
    der eigentliche Schritt: sucht Personen zur Anfrage UND reichert sie an
    (u.a. mit `work_email_enrichment` = verifizierte Arbeits-E-Mail). Legt
    die Treffer automatisch in eine neue oder vorhandene Liste. Das ist der
    Schritt, der Guthaben ("Instantly Credits") kostet.
  - Alternativ: `POST /api/v2/supersearch-enrichment/` (an eine bestehende
    Liste/Kampagne hängen) + `POST /api/v2/supersearch-enrichment/run`
    (Anreicherung auslösen) – zweistufige Variante desselben Ergebnisses.

**Such-Filter (`search_filters`), live aus der Doku bestätigt:**
`domains` (Liste von Firmen-Domains), `company_name` (include/exclude),
`title` (include/exclude, z.B. "CEO"/"VP" ausschließen), `location`,
`industry`, `employeeCount` (Größenklassen wie bei Apollo), `look_alike`
(ähnliche Firmen zu einer Vorbild-Domain finden), u.a.

---

## 2. Hat das Team-Konto Guthaben dafür? – Geprüft, per GET, ohne Kosten

**Nein, aktuell 0 Guthaben.** Zwei lesende GET-Aufrufe (keine Kosten, keine
Suche ausgelöst):

- `GET /api/v2/workspace-billing/plan-details` → Konto zahlt den
  "Growth"-Plan (47 $/Monat) für den **E-Mail-Versand** (1000
  Kontakte/Monat-Limit). Das ist ein SEPARATES Guthaben-Töpfchen: unter
  `subscriptions.credits` steht `"plan_name": "Free Trial"`,
  `"total_credits": 100`, **`"available_credits": 0`**. Es wurde also nie
  ein "Instantly Credits"-Plan dazugebucht – der bezahlte Growth-Plan
  deckt nur den Versand ab, nicht die Lead-Suche.
- `GET /api/v2/workspace-billing/subscription-details` bestätigt: nur eine
  aktive Subscription im Konto, die Growth-Outreach-Plan (`pid_g_v2`).
  Keine separate Credits-Subscription.

**Wichtig für die Einordnung:** "Wir zahlen Instantly schon" heißt nicht
automatisch "wir haben SuperSearch-Guthaben" – das ist ein eigener,
zusätzlich zu buchender Baustein.

**Kein Live-Test nötig** für diese Frage – die 0 kam direkt aus der
lesenden Kontostand-Abfrage, kein bezahlter Such-Aufruf war dafür nötig.

**Kosten laut Instantlys eigener Preis-Seite/Hilfe-Center (öffentlich,
nicht Teil der OpenAPI-Doku, daher als Richtwert und nicht letztgültig zu
verstehen):**
- Kleinstes Credits-Paket "Nano" ca. 9 $/Monat für ca. 150 Credits, "Growth
  Credits" ca. 47 $/Monat für ca. 1.500–2.000 Credits, größere Stufen
  darüber.
- Pro gefundener Person mit verifizierter Arbeits-E-Mail: **ca. 1 Credit**,
  wenn Instantly die E-Mail selbst hat, **ca. 2+ Credits**, wenn ein
  Fremd-Anbieter dafür angefragt werden muss. Kein Verbrauch bei "keine
  E-Mail gefunden". Zusätzliche Anreicherung (Firmen-Infos, Technologie,
  News) kostet nochmal separat on top.
- Diese Zahlen kommen von der öffentlichen Preis-Seite/Hilfe-Center, nicht
  aus der API-Doku – vor einer echten Kosten-Kalkulation für den Kunden auf
  instantly.ai/pricing gegenprüfen, Preise ändern sich.

---

## 3. Passt das als Ersatz für unsere Stufe 2 (pro Firma Kontakte finden)?

**Ja, technisch passt es 1:1 auf unseren Ablauf.** Unser Apollo-Modul
(`pipeline/sources/apollo.py`, Funktion `unternehmen_anreichern`) nimmt pro
Firma aus Google Maps (`name`/`domain`) und sucht dazu Kontakte in
gewünschten Rollen mit E-Mail. Instantlys `search_filters.domains` (Liste
von Domains) + `search_filters.title.include` (Rollen-Liste) decken genau
das ab – keine reine "grobe Kriterien-Suche über den ganzen Markt", sondern
pro-Firma-Filterung ist vorgesehen, exakt wie bei Apollo.

Ein Unterschied zu Apollo: Instantlys Ablauf ist zweistufig UND landet
automatisch in einer Liste/Kampagne (`enrich-leads-from-supersearch` legt
eine Liste an) – bei Apollo bekommen wir die Treffer direkt in der
Server-Antwort zurück. Für unser Tool hieße das: entweder nach dem Aufruf
die neu angelegte Liste separat auslesen, oder den zweistufigen Weg
(`supersearch-enrichment/` + `/run` + danach `leads/list` filtern) nutzen.
Beides technisch machbar, aber ein zusätzlicher Umbauschritt gegenüber dem
heutigen direkten Apollo-Aufruf.

---

## 4. Harte Grenzen

- **Größtes Hindernis gerade: kein Guthaben.** Ohne Credits-Plan (mind.
  "Nano" laut Preis-Seite) läuft `enrich-leads-from-supersearch` vermutlich
  in den in der Doku hinterlegten Fehler `402 Payment Required` /
  "Workspace does not have an active paid plan" – nicht live geprüft
  (keine bezahlte Anfrage ausgelöst), aber die Doku sieht diesen Fehlercode
  für genau diesen Fall extra vor.
- **Kein technischer Preis-pro-Anfrage in der API-Doku selbst** – die
  OpenAPI-Spec nennt keine Credit-Kosten pro Aufruf, nur die
  öffentliche Preis-Seite (siehe Punkt 2, als Richtwert).
- `preview-leads-from-supersearch` und `count-leads-from-supersearch`
  liefern laut Beschreibung Ergebnisse "ohne anzureichern" – ob diese zwei
  Lese-Endpunkte selbst Credits kosten, steht nirgends explizit in der
  Doku. Bewusst NICHT live getestet (Sicherheitsregel: keine Kosten
  riskieren) – vor dem produktiven Bau mit einem kleinen gekauften
  Guthaben-Betrag einmal live gegenprüfen.
- Rate-Limits: Doku nennt nur generische `429 Too Many Requests`, keine
  konkrete Zahl gefunden.

---

## Empfehlung

Instantly SuperSearch ist eine **echte Alternative zu Apollo für Stufe 2**
und passt vom Suchmuster her (Domain + Rollen pro Firma) genau auf unseren
Ablauf – kein Kompromiss auf "nur grobe Kriterien-Suche". Aktuell aber
**nicht nutzbar**, weil das Konto 0 SuperSearch-Guthaben hat (das ist ein
separates Zusatz-Produkt zu dem, was schon für den E-Mail-Versand bezahlt
wird). Bevor man produktiv umbaut: mit einem kleinen Guthaben-Kauf
(kleinste Stufe laut Preis-Seite ca. 9 $/Monat) einen echten Test an
1–2 Firmen fahren und dabei prüfen, (a) ob Preview/Count wirklich kostenlos
sind, (b) wie gut die Treffer-/E-Mail-Qualität im Vergleich zu Apollo bei
unseren typischen deutschen Handwerks-/KMU-Zielfirmen ist, (c) den
tatsächlichen Credit-Verbrauch pro Treffer live nachmessen.
