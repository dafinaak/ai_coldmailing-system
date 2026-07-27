# Datenquellen-Strategie: Persönliche E-Mail-Adressen für deutsche Firmen

## 0. Ergebnis-Update (27.07.2026): gemessen statt recherchiert

Die Empfehlung unten (Kaskade selbst bauen) wurde umgesetzt und mit echten
Firmen gemessen. Der Stand, der jetzt gilt:

- **Gemessener Vergleich** (20 echte IT-Dienstleister Hannover, je 16
  auswertbar): Prospeo allein 6/16, Hunter→Dropcontact allein 6/16,
  Kombination 8/16 (50 %) — keiner reicht allein, die Kaskade ist bestätigt.
  Details: `laeufe/vergleich-anbieter/2026-07-23-prospeo-20-firmen-v2/`.
- **Der Namens-Engpass ist der Kern:** Die Anbieter kennen Angestellte
  (LinkedIn-Quellen), aber oft nicht die Inhaber kleiner Firmen. Deren Name
  steht im Impressum. Messung „Impressum-Name → Dropcontact": 6 von 8
  Lücken-Firmen hatten den Namen im Impressum, alle 6 ergaben eine geprüfte
  persönliche Mail → **Gesamtabdeckung 14/16 = 87,5 %.**
- **Produktiv-Kaskade** (gebaut, `Kunde.anbieter_reihenfolge`):
  `prospeo` → `impressum` (KI liest NUR Namen, Dropcontact baut/prüft die
  Mail — Projektregel bleibt gewahrt) → geprüfte info@-Regel. Hunter dient
  nur noch als info@-Prüfer (Gratis-Kontingent reicht dafür).
- **Gebuchtes Setup** (Oliver, 27.07.2026): Prospeo Starter 49 $/M.
  (2.000 Credits) + Dropcontact Starter 29 €/M. (500 Credits), monatlich
  kündbar, Firmen-Konten. Kapazität grob 1.000 Firmen/Monat.
- **Klarstellung zu Instantly SuperSearch:** Die Formulierung „wir zahlen
  Instantly ohnehin" unten meint NUR das Versand-Abo. SuperSearch-Credits
  sind NICHT enthalten und würden extra kosten — SuperSearch hat also
  keinen Kostenvorteil gegenüber anderen Anbietern und bleibt gestrichen.
- Apollo ist vollständig entfernt (Code und Tests) — die Kaskade ersetzt es.

Die Recherche unten bleibt als Begründung und Marktübersicht stehen.

---

Stand: Juli 2026. Recherche mit aktuellen Anbieter-Seiten und Vergleichstests.
Alle Preise sind die zum Recherche-Zeitpunkt veröffentlichten Zahlen — Anbieter
ändern Preise laufend, vor Vertragsabschluss immer nochmal auf der
Anbieter-Seite prüfen. Wo Zahlen geschätzt oder nur auf Anfrage erhältlich
sind, steht das dabei.

---

## 1. Worum es geht

Unsere Pipeline: Google Maps (über Apify) findet die Firmen — vor allem
kleine und lokale deutsche Betriebe. Danach brauchen wir zu jeder Firma die
richtige Ansprechperson (Geschäftsführer, IT-Leiter usw.) **mit persönlicher,
geprüfter E-Mail-Adresse** (nicht info@). Ziel: Zehntausende geprüfte
Adressen pro Monat, dauerhaft. Versand läuft weiter über Instantly. Die
Apollo-Testguthaben sind aufgebraucht.

**Die zentrale Erkenntnis vorweg:** Es gibt nicht die eine Datenbank, die
das für kleine deutsche Firmen löst. Amerikanische Datenbanken kennen genau
die Firmen nicht, die Google Maps uns liefert. Der verlässliche Weg ist eine
**Kaskade** (Fachwort: Waterfall): mehrere Quellen nacheinander fragen, bis
eine die Adresse liefert. Und die erste, beste Quelle ist bei kleinen
deutschen Firmen oft **die eigene Webseite der Firma** — kostenlos.

---

## 2. Bestätigt: Apollo passt nicht zu unserer Zielgruppe

Die Vermutung stimmt und lässt sich belegen:

- Apollo hat über 270 Mio. Kontakte, aber überwiegend aus englischsprachigen
  Märkten. Deutsche Kleinbetriebe, lokale Dienstleister und Familienfirmen
  fehlen weitgehend
  (https://anilead.io/en/blog/apollo-alternative-deutschland).
- Ein deutscher Test bescheinigt Apollo: solide bei Mittelstand ab ca. 50
  Mitarbeitern, ungenau bei sehr kleinen (<20 Mitarbeiter) und lokalen
  Firmen; E-Mail-Trefferquote in DACH realistisch nur 55–65 % (in den USA
  90 %+) (https://www.grundwerk.digital/tools/apollo).
- Auch der Marktüberblick "Germany B2B Data Landscape 2026" kommt zum selben
  Schluss: für deutsche Kleinfirmen sind US-Datenbanken die falsche Quelle
  (https://syncgtm.com/blog/best-b2b-database-germany).

Google Maps ist stark genau bei den Firmen, bei denen Apollo schwach ist.
Ein weiterer Apollo-Vertrag löst unser Problem also nicht. Apollo kann
höchstens als eine Stufe in der Kaskade dienen — für die etwas größeren
Firmen, die zufällig drin sind.

**Wichtige zweite Erkenntnis:** Für Kleinstbetriebe (Handwerker, lokale
Dienstleister mit 1–10 Leuten) ist *keine* Kontaktdatenbank gut. Was aber
funktioniert: Diese Firmen haben eine Webseite mit **Impressum** — in
Deutschland Pflicht, und dort steht der Geschäftsführer mit Namen, oft mit
direkter E-Mail. Aus Name + Firmen-Domain lässt sich die persönliche Adresse
zudem maschinell herleiten und prüfen (genau das machen Hunter und
Dropcontact). Die Domain haben wir aus Google Maps schon.

---

## 3. Anbieter-Vergleich

Kurzerklärung der Spalten: "API" = kann unser System automatisch pro Firma
anfragen (Domain + Rolle rein, E-Mail raus). "Kaskaden-tauglich" = eignet
sich als eine Stufe in einer Kette aus mehreren Quellen.

| Anbieter | API | DACH-Abdeckung (kleine Firmen) | Kosten im Maßstab (Zehntausende/Monat) | DSGVO-Haltung | Kaskaden-tauglich |
|---|---|---|---|---|---|
| **Hunter.io** (FR) | Ja, alle Bezahlpläne | Gut bei Firmen mit eigener Webseite, schwächer unter 50 MA ohne Web-Präsenz | Scale: 25.000 Credits für 299 $/M. (209 $/M. jährlich) ≈ 0,8–1,2 ct/Suche; größere Mengen als Einmal-Pakete oder Enterprise (https://hunter.io/pricing) | EU-Firma (Frankreich), nur öffentliche Quellen, quellentransparent | **Ja, sehr gut** |
| **Dropcontact** (FR) | Ja (ab Business-Stufe) | Gut, wenn Name + Domain vorliegen — errechnet und prüft Adressen live, keine gekaufte Datenbank | Stufen per Schieberegler bis 150.000 Credits/M., z. B. Growth ab 120 €/M.; Einstieg ca. 24 €/1.000 Credits; Enterprise ab 200.000/M. auf Anfrage — grob 2–3 ct/Kontakt, Credits übertragbar (https://www.dropcontact.com/pricing) | **DSGVO-Vorzeigefall**: keine gespeicherte Personendatenbank, alles wird live errechnet | **Ja, sehr gut** |
| **Instantly SuperSearch** | Ja — eigene API-Endpunkte (SuperSearch Enrichment) (https://developer.instantly.ai/api/v2/supersearchenrichment) | LinkedIn-lastige 450-Mio-Datenbank, bei deutschen Kleinstfirmen eher dünn (unbestätigt, testen) | Hyper: 197 $/M. für 10.000 Credits, größere Pakete bis 200.000; 1–2 Credits pro geprüfter E-Mail ≈ 2–4 ct (https://instantly.ai/blog/supersearch-website-visitor-roi-cost-per-lead/) | US-Anbieter, klassische Datenbank | Ja — und wir zahlen Instantly schon |
| **Prospeo** (FR) | Ja, ab 39 $/M. | Ordentlich bei Firmen mit Domain; Vorsicht: Credits werden auch bei Nicht-Treffern verbraucht | ca. 1 ct/E-Mail; Basic 39 $/1.000 Credits, größere Stufen verfügbar (https://prospeo.io/pricing, Detailpreise teils nur im Konto sichtbar — Schätzung) | US/FR-Mix, Datenbank + Live-Suche | Ja, als günstige Zusatzstufe |
| **Snov.io** | Ja (REST-API, Webhooks) | International breit, DACH-Kleinfirmen nicht Schwerpunkt | Pro S: 99 $/M. für 5.000 Credits (1 Credit = 1 E-Mail); Ultra ab 200.000 Credits auf Anfrage, mit Credit-Übertrag (https://snov.io/pricing) | US-Anbieter | Ja |
| **Apollo.io** | Ja, aber Personensuche-API braucht Master-Key = Organization-Plan (~119–149 $/Nutzer/M., min. 3 Nutzer) (https://docs.apollo.io/docs/api-pricing) | **Schwach bei deutschen Kleinfirmen** (siehe Abschnitt 2) | Basic 59 $/M.; "unbegrenzte" E-Mail-Credits mit Fair-Use-Deckel (~250/Tag); echte API-Mengen = Organization + Zusatzpakete (https://www.warmly.ai/p/blog/apollo-pricing) | US-Datenhändler, DSGVO-Beschwerden bekannt | Nur als Stufe für größere Firmen |
| **Lusha** | Ja, aber erst ab Pro/Scale-Plan | US/Israel-lastig, DACH-Kleinfirmen schwach | Premium: ~300 $/M. für 3.400 Credits ≈ 9 ct/E-Mail — im Zehntausender-Maßstab unbezahlbar (https://www.lusha.com/pricing/) | US/IL-Datenhändler | Technisch ja, preislich nein |
| **Cognism** (UK) | Ja (Enterprise) | **Stark in DACH** — laut Tests 30–50 % mehr Treffer als Apollo/ZoomInfo in UK/DACH/Nordics; Fokus aber Mittelstand+, nicht Kleinstbetriebe | Nur auf Anfrage; reale Abschlüsse ~15.000–30.000 $/Jahr (https://www.cleanlist.ai/blog/2026-03-19-cognism-pricing-guide) — vertriebsgesteuert | GDPR-bewusst, EU-Fokus, eigene Compliance-Prüfungen | Ja, aber teuerste Option |
| **Dealfront** (ehem. Echobot, DE) | Teilweise — APIs vorhanden, Kontaktdaten-Zugriff vertriebsgesteuert | **Beste deutsche Firmenabdeckung** (Handelsregister-Quellen, 60 Mio.+ EU-Firmen); persönliche E-Mails aber nur, wo öffentlich auffindbar (https://www.dealfront.com/connect/) | Einstieg ab 99–165 €/M. (Besucher-Erkennung); Kontaktdaten-Pakete nur auf Anfrage (https://saleshive.com/vendors/dealfront) | **DSGVO-first, deutsche Wurzeln (Karlsruhe)**, transparente Quellen | Ja — v. a. als Quelle für Firmen + Entscheider-Namen |
| **Clay** (US, Plattform) | Ja (ist selbst eine Kaskaden-Plattform über 100+ Quellen) | So gut wie die Quellen, die man darin bucht | Launch 185 $/M. (10.000 Credits), Growth 495 $/M. (25.000); Kaskade über 2 Quellen ≈ 2,3 Credits pro gefundener E-Mail → bei 20.000 E-Mails/M. schnell 1.000–2.000 $+/M. (https://www.cleanlist.ai/blog/2026-03-12-clay-pricing-changes-2026) | US-Plattform, Daten fließen durch Drittland | Ist selbst die Kaskade |
| **ContactOut** | Nur im Custom-Plan (~2.000–4.000 $/Jahr) | US/Recruiting-lastig; "unbegrenzt" heißt real max. 2.000 E-Mails/M. | Deckel zu niedrig für unseren Maßstab (https://www.bookyourdata.com/blog/contactout-pricing) | US-Anbieter | Nein (Mengendeckel) |
| **Datagma** (FR) | Ja | Stärke sind Handynummern, nicht E-Mails ("kein starker E-Mail-Finder", Trefferquote 70–80 % nur bei US/West-EU-Standardfällen) (https://www.saleshandy.com/blog/datagma-pricing/) | ab 39–49 $/M. für 1.000 Credits | EU-Anbieter, Live-Abfrage statt Datenbank | Als E-Mail-Stufe eher nicht |

---

## 4. Kaskade (Waterfall): ja — aber selbst gebaut

**Ist die Kaskade der richtige Ansatz?** Ja. Keine Einzelquelle erreicht bei
deutschen Kleinfirmen 80 % Abdeckung. Zwei bis drei Quellen nacheinander
gefragt heben die Trefferquote deutlich, weil jede Quelle andere Firmen
kennt bzw. andere Methoden nutzt (Datenbank vs. Live-Herleitung aus
Name + Domain). Genau dieses Muster verkauft Clay als Produkt.

**Weg A — Clay als fertige Kaskaden-Plattform:**

- Schnell startklar, 100+ Quellen per Klick, kein eigener Code.
- Aber: bei 20.000–30.000 E-Mails/Monat landet man bei grob 1.000–2.500 $
  monatlich (Growth-Plan 495 $ reicht rechnerisch nur für ~10.000 gefundene
  E-Mails bei 2-Quellen-Kaskade), weil Clay auf jede Quelle einen
  Credit-Aufschlag legt.
- Und: Clay ist eine weitere Plattform mit eigener Oberfläche, eigenem
  Credit-System, eigener Abhängigkeit. Das widerspricht unserem
  Nordstern "eine eigene Plattform, ein System".

**Weg B — Kaskade im eigenen System (Empfehlung):**

- Unsere Plattform hat die Mehr-Quellen-Architektur schon; jede neue Quelle
  ist ein weiterer Baustein mit API-Anbindung.
- Wir zahlen bei jedem Anbieter den direkten Preis ohne
  Plattform-Aufschlag — bei gleicher Menge grob die Hälfte bis ein Drittel
  der Clay-Kosten.
- Volle Kontrolle: Reihenfolge, Ausgaben-Deckel pro Quelle, eigene
  Prüf-Logik, alles im eigenen Dashboard sichtbar.
- Aufwand: pro Quelle eine überschaubare Anbindung (die Instantly-Anbindung
  existiert ja schon als Muster). Realistisch wenige Bausteine Arbeit, kein
  Großprojekt.

**Fazit Kaskade: selbst bauen.** Clay lohnt sich für Teams ohne eigene
Technik — wir haben die Technik schon.

---

## 5. Empfehlung: der eine nachhaltige Weg

**"Deutsche-Domain-Kaskade": Impressum zuerst, dann zwei EU-Anbieter — als
Stufen in unserer eigenen Plattform.**

Konkreter Aufbau, in dieser Reihenfolge pro Firma aus Google Maps:

1. **Stufe 0 — Webseite/Impressum der Firma selbst (kostenlos).**
   Die Domain kommt aus Apify/Google Maps. Ein eigener Scraper liest
   Impressum und Kontaktseite: Geschäftsführer-Name steht dort per Gesetz,
   oft samt direkter E-Mail. Das ist bei Kleinstfirmen die beste Quelle
   überhaupt — und kostet nur Rechenzeit. (Für Entscheider-Namen ergänzend
   denkbar: Handelsregister-Daten, z. B. später über Dealfront.)
2. **Stufe 1 — Hunter.io API.** Domain rein, gefundene/hergeleitete Adressen
   samt Rolle und Prüfstatus raus. Scale-Plan: 25.000 Credits für
   299 $/M. (209 $/M. bei Jahreszahlung), größere Einmal-Pakete zukaufbar
   (https://hunter.io/pricing).
3. **Stufe 2 — Dropcontact API.** Bekommt Name + Firma/Domain (Name haben
   wir aus Stufe 0) und errechnet + prüft die persönliche Adresse live.
   EU-Anbieter, sauberste DSGVO-Story am Markt, Credits verfallen nicht
   (https://www.dropcontact.com/pricing). Volumen per Schieberegler bis
   150.000 Credits/Monat.
4. **Stufe 3 (optional) — Instantly SuperSearch API als Auffangnetz.**
   Wir zahlen Instantly ohnehin; die SuperSearch-Enrichment-API ist
   vorhanden (https://developer.instantly.ai/api/v2/supersearchenrichment).
   Erst im Testlauf prüfen, ob sie bei unseren Kleinfirmen überhaupt
   Treffer bringt.
5. **Immer am Schluss: Prüfung.** Jede Adresse, egal aus welcher Stufe,
   nochmal verifizieren (Hunter-Verifier: 0,5 Credits, oder unser
   bestehender Prüf-Baustein), bevor sie an Instantly geht. Das schützt
   die Zustellbarkeit — unser wertvollstes Gut.

**Budgetrahmen (grob, bei ~20.000–40.000 Anfragen/Monat):**

- Hunter Scale: ~210–300 $/M.
- Dropcontact (Growth, mittlere Schieberegler-Stufe): ~120–450 €/M. je nach
  Menge (genaue Stufe im Konto konfigurierbar — Zahl ist eine Spanne, keine
  Zusage)
- Instantly-Credits nach Bedarf: 0–200 $/M.
- **Summe: rund 400–900 €/Monat.** Zum Vergleich: derselbe Ausstoß über
  Clay ≈ 1.000–2.500 $/M., über Cognism ≈ 1.300–2.500 €/M. (Jahresvertrag).

**Zweitplatzierter / späterer Ausbau:** Dealfront (ehemals Echobot,
Karlsruhe). Beste deutsche Firmen- und Entscheider-Abdeckung über
Handelsregister-Quellen, DSGVO-first (https://www.dealfront.com/connect/).
Preis für Kontaktdaten ist aber vertriebsgesteuert (Gespräch nötig) und
persönliche E-Mails liefern sie nur, wo öffentlich auffindbar. Sinnvoll als
Stufe 0b, wenn die Kaskade läuft und wir merken, dass uns Entscheider-Namen
fehlen. Cognism wäre die Enterprise-Variante davon — stark in DACH, aber ab
~15.000 $/Jahr und auf Mittelstand+ ausgerichtet, nicht auf unsere
Kleinstfirmen.

**Warum dieser Weg:** Er nutzt die strukturelle Stärke unserer Zielgruppe
(Impressumspflicht + eigene Domains) statt gegen die strukturelle Schwäche
der US-Datenbanken anzukaufen. Er ist mit zwei EU-Anbietern
DSGVO-freundlich aufgestellt. Er skaliert per Schieberegler statt per
Vertriebsgespräch. Und er landet komplett in unserer eigenen Plattform —
kein zweites Tool, kein Wholix-Ersatz durch den nächsten Fremdkasten.

**Erster Schritt zum Beweis (bevor Geld fließt):** 500 Firmen aus einer
echten Apify-Liste durch einen Testlauf schicken — Stufe 0 als Prototyp,
Hunter und Dropcontact im Gratis-/Kleinstplan (50 bzw. 50 Credits frei).
Gemessen wird: Wie viel Prozent der Firmen bekommen eine geprüfte
persönliche Adresse? Erst wenn die Quote überzeugt, die großen Pläne buchen.

---

## 6. Ehrliche Anmerkung: Recht (keine Rechtsberatung)

Das muss auf den Tisch, gerade bei Zehntausenden E-Mails an deutsche
Empfänger:

- **UWG § 7:** E-Mail-Werbung ohne vorherige ausdrückliche Einwilligung gilt
  in Deutschland als "unzumutbare Belästigung" — **auch im B2B**, eine
  generelle Firmenkunden-Ausnahme gibt es (anders als beim Telefon) nicht
  (https://www.datenschutz-notizen.de/zulaessigkeit-von-kaltakquise-massnahmen-ein-leitfaden-1650471/,
  https://www.cegtec.net/wissen/kaltakquise-b2b-email-rechtslage/).
- **DSGVO** ist die zweite, getrennte Frage: Das *Verarbeiten* von
  B2B-Kontaktdaten lässt sich auf berechtigtes Interesse stützen — aber eine
  DSGVO-konforme Datenquelle macht den *Versand* nicht erlaubt
  (https://overloop.com/blog/de/b2b-cold-email-germany-gdpr-compliance.html).
- **Reale Risiken:** Abmahnungen (durch Mitbewerber oder
  Wettbewerbsverbände, typisch einige hundert bis wenige tausend Euro pro
  Fall plus Unterlassungserklärung), Beschwerden bei Datenschutzbehörden,
  Bußgelder (theoretisch hoch, praktisch bei B2B-Kaltmail selten), und —
  wirtschaftlich am spürbarsten — Spam-Einstufung und ruinierte
  Absender-Reputation. Je größer das Volumen, desto sichtbarer wird man.
- **Was das Risiko senkt (nicht beseitigt):** eng zugeschnittene Zielgruppen
  mit klarem sachlichem Bezug zum Angebot; wenige, kurze, individuell
  formulierte Erst-Mails statt Massenserien; sofortiger, einfacher
  Widerspruchsweg und sauber gepflegte Sperrliste; Datensparsamkeit
  (Nicht-Antworter nach kurzer Frist löschen); Dokumentation der
  Interessenabwägung; deutsche/EU-Datenquellen statt US-Datenhändler; und
  als rechtlich sicherer Kanal daneben: Telefon, denn B2B-Kaltanrufe sind
  bei mutmaßlichem Interesse erlaubt
  (https://www.nexsale-consulting.de/wissen/kaltakquise-b2b-email-erlaubt/).
- **Klartext:** Kalte B2B-Massen-E-Mail an deutsche Empfänger bewegt sich
  rechtlich in einer Grauzone bis Verbotszone. Viele machen es, das
  Durchsetzungsrisiko pro einzelner Mail ist klein — aber es ist ein
  Geschäftsrisiko, das der Inhaber bewusst tragen muss, keine Formalie.
  Für eine belastbare Einschätzung: Anwalt für Wettbewerbs-/Datenschutzrecht.

---

## 7. Quellen (Auswahl)

- Apollo-DACH-Schwäche: https://anilead.io/en/blog/apollo-alternative-deutschland, https://www.grundwerk.digital/tools/apollo, https://syncgtm.com/blog/best-b2b-database-germany
- Apollo-Preise/API: https://www.warmly.ai/p/blog/apollo-pricing, https://docs.apollo.io/docs/api-pricing
- Hunter: https://hunter.io/pricing
- Dropcontact: https://www.dropcontact.com/pricing, https://salesdorado.com/en/automation/review-dropcontact/
- Instantly SuperSearch: https://instantly.ai/blog/supersearch-website-visitor-roi-cost-per-lead/, https://developer.instantly.ai/api/v2/supersearchenrichment
- Cognism: https://www.cleanlist.ai/blog/2026-03-19-cognism-pricing-guide, https://www.growthtechspotlight.com/tools/cognism
- Dealfront: https://www.dealfront.com/connect/, https://derrick-app.com/tools/dealfront-review
- Clay: https://www.cleanlist.ai/blog/2026-03-12-clay-pricing-changes-2026, https://www.landbase.com/blog/clay-pricing
- Lusha: https://www.lusha.com/pricing/
- Snov.io: https://snov.io/pricing
- Prospeo: https://prospeo.io/pricing, https://woodpecker.co/blog/prospeo/
- ContactOut: https://www.bookyourdata.com/blog/contactout-pricing
- Datagma: https://www.saleshandy.com/blog/datagma-pricing/
- Recht: https://overloop.com/blog/de/b2b-cold-email-germany-gdpr-compliance.html, https://www.datenschutz-notizen.de/zulaessigkeit-von-kaltakquise-massnahmen-ein-leitfaden-1650471/, https://www.cegtec.net/wissen/kaltakquise-b2b-email-rechtslage/, https://www.nexsale-consulting.de/wissen/kaltakquise-b2b-email-erlaubt/
