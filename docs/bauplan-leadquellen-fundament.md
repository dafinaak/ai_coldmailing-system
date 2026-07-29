# Bauplan: Mehrquelliges Lead-Listen-Fundament (Olivers Auftrag 29.07.2026)

Stand: 2026-07-29 — Weg 1 von Leonard freigegeben (jede Quelle ein eigener
Baustein, Fusion mit Dubletten-Erkennung, North Data nur als Bonus).

## Ziel und Erfolgskriterium

Die Lead-Listen sollen künftig selbst gescrapt werden, aus mehreren
Quellen, wiederverwendbar für jede zukünftige Zielgruppe (Suchbegriff +
Gebiet als Konfiguration). Erste Anwendung: IT-Dienstleister PLR 30-39,
vollständiger als die gelieferte 319er-Excel.

Erfolg heißt:

- Eine fusionierte Firmenliste ohne Duplikate (eine Firma = ein Eintrag),
  jede Firma mit Quellen-Vermerk (woher sie stammt).
- Messbar mehr Firmen als die 319er-Liste im selben Gebiet.
- Ausgabe im bekannten firmen.json-Format — die restliche Strecke
  (Entscheider-Suche, Anrede, Kampagne) bleibt unverändert.
- Pro Firma am Ende genau ein Ansprechpartner (macht die bestehende
  Kaskade; bevorzugt persönliche Mail — bereits gebaut).

## Quellen und ihre Rolle

- **Google Maps** (Apify, Actor compass/crawler-google-places): bestehender
  Baustein, bleibt Fundament-Quelle.
- **Gelbe Seiten** (Apify, Dritt-Actor — Auswahl im Bau per Mini-Test):
  neue Fundament-Quelle. Achtung Projektregel: kleine Dritt-Scraper können
  brechen — deshalb ist KEINE Einzelquelle das Fundament, sondern die
  Fusion; fällt eine Quelle aus, läuft der Rest weiter.
- **Overpass / OpenStreetMap** (direkte freie API, kein Apify): neue
  Fundament-Quelle. Abfrage nach Kategorien (z. B. office=it) im
  PLZ-Gebiet.
- **North Data** (Apify, Dritt-Actor): NUR Bonus-Anreicherung obendrauf
  (z. B. Rechtsform/Register-Infos). Das System verlässt sich nicht
  darauf; Ausfall oder Abschaltung ändert nichts am Fundament.

## Schritte

### Schritt 1: Gelbe-Seiten-Baustein

Neuer Quellen-Baustein im Muster von apify_maps.py, testgetrieben.
Actor-Auswahl per Mini-Lauf (1 Suchbegriff, 1 Stadt) über die Kandidaten
aus dem Store; genommen wird der mit brauchbarem Ergebnisformat und
stabilem Lauf.

**Nachweis:** Tests grün + Stichprobe eines Mini-Laufs (Firmen mit Name,
Adresse, Webseite).

### Schritt 2: Overpass-Baustein

Direkte Abfrage der freien Overpass-API (OpenStreetMap): IT-relevante
Kategorien im Suchgebiet, mit Rücksicht auf die Nutzungsregeln (gedrosselt,
mit Wartezeit und Wiederholung). Testgetrieben mit gefakten Antworten.

**Nachweis:** Tests grün + Mini-Abfrage über eine Stadt mit Stichprobe.

### Schritt 3: Fusions-Baustein

Führt die Quellen-Listen zusammen: Duplikat-Erkennung über Domain,
normalisierten Firmennamen und PLZ (nutzt und erweitert die bestehende
Dubletten-Logik). Je Firma bleiben die reichsten Daten stehen (Webseite
schlägt keine Webseite usw.), Quellen werden vermerkt. Erzeugt
firmen.json plus Fusionsbericht: je Quelle gefunden / nach Fusion
einzigartig / Überschneidungen.

**Nachweis:** Tests grün (inkl. kniffliger Fälle: gleiche Firma andere
Schreibweise, gleiche Domain andere Stadt) + Fusionsbericht des
Mini-Laufs.

### Schritt 4: North-Data-Bonus (optional, nach 1-3)

Anreicherungs-Stufe hinter der Fusion, ausfalltolerant: Fehler oder
leere Antworten lassen die Liste unverändert. Vorab kurz prüfen, ob die
Nutzung rechtlich/vertraglich vertretbar ist (Scraper von Dritten).

**Nachweis:** Tests grün + Mini-Lauf; bei Unzuverlässigkeit wird die
Stufe abgeschaltet dokumentiert.

### Schritt 5: Voll-Scrape IT-Dienstleister PLR 30-39

Alle Quellen über das komplette Suchgebiet, Fusion, Bericht mit
Vergleich zur alten 319er-Liste (wie viele bekannt, wie viele neu).

**Nachweis:** Der Fusionsbericht.

### Schritt 6: Übergabe an die bestehende Strecke — in Monats-Paketen

Die neue Liste geht denselben Weg wie bisher geplant (Entscheider-Suche,
Anrede, Kampagne), aber in **Monats-Paketen à ~450 Firmen** (von Leonard
freigegeben 29.07.2026). Grund: Das Dropcontact-Abo hat 500 Credits im
Monat (1 Credit = eine gebaute+geprüfte persönliche Mail), und die
Kampagne verbraucht bei Olivers Tempo (20 neue Kontakte/Tag, Mo-Fr)
ohnehin nur ~440 Kontakte im Monat. Kontakte werden also immer kurz vor
ihrem Versand-Fenster angereichert statt alles vorab.

Priorisierung innerhalb der Pakete: zuerst Firmen mit Webseite UND
Geschäftsführer-Hinweis (höchste Trefferwahrscheinlichkeit), dann mit
Webseite ohne Hinweis, zuletzt ohne Webseite (nur Anruf/Brief-Liste).
Der Datenlauf ist wiederaufnehmbar - das nächste Paket startet einfach
mit demselben Lauf-Ordner, sobald frische Credits da sind.

## Olivers Vorgaben (Nachricht vom 29.07.2026)

- **Ziel-Branche:** IT-Dienstleister, IT-Systemhaus, IT-Service,
  IT-Support.
- **Ausschlüsse:** reiner Computerhandel (Hardware, Software),
  Rechenzentren, reine Elektro-/Leitungs-Installation, Hoster,
  Internet-Dienstleister; außerdem Automations-Dienstleistung.
  -> eigener Ausschluss-Filter in der Fusion (Kategorien + Namens-
  Schlüsselwörter), aussortierte Firmen werden im Bericht gelistet,
  nicht still verworfen.
- **Unternehmensgröße:** alle.
- **Filialisten:** ausschließlich die Zentrale anschreiben — Dubletten-
  Gruppen werden erkannt und die Zentrale gewählt; unklare Fälle
  entscheidet ein Mensch (bestehende Regel).
- **Region: NUR Postleitregionen 30 und 31** (nicht mehr 30-39).
- **Ergebnis-Auswertung:** Gesamtanzahl Kontakte; Anzahl persönliche
  E-Mail-Adressen mit Quote; Liste aller Kontakte OHNE persönliche
  Mail (mit Telefon/Adresse) für andere Methoden bzw. Anruf/Brief.
  Das leistet der bestehende Großlauf-Bericht bereits; er wird um die
  Ausschluss-Liste ergänzt.
- **Impressum-Schritt ist laut Oliver unumgänglich** -> der KI-Schlüssel
  (OpenRouter-Konto, einmalig ~5 € Guthaben) ist damit beschlossene
  Voraussetzung. Einrichten muss ihn ein Mensch mit Zahlungsmittel
  (Leonard) — danach trägt Claude ihn ein und testet ihn.

## Entschiedene Punkte (Leonard/Oliver, 29.07.2026)

- **Alte 319er-Liste:** Ist NICHT mehr die Kampagnen-Basis. Sie dient
  nur noch als Auffüller: Ihre Firmen fließen in die Fusion ein, wo
  sie in der neuen Liste fehlen (Region 30/31; Einträge außerhalb der
  Region fallen durch den PLZ-Filter). Ihre Geschäftsführer-Hinweise
  bleiben dabei erhalten (gf_name_liste, für die Impressum-Prüfung).
- **Dropcontact:** Das neue Konto (Schlüssel vom 29.07.2026 in .env)
  ist das richtige und wird verwendet.
- **Prospeo:** Kein Abo ("klappt nicht") — die Entscheider-Suche läuft
  ohne Prospeo-Abo: Impressum-KI (OpenAI) als Hauptstufe, Hunter-Frei-
  kontingent als Zusatz, geprüfte info@ als Rückfall; das alte
  Prospeo-Gratis-Konto bleibt Bonus, solange sein Limit reicht.

## Kosten

- Apify: Firmen-Konto Starter, 29 $/Monat Budget, aktuell 0 verbraucht.
  Mini-Läufe für die Actor-Auswahl kosten Cent- bis kleine Dollar-Beträge
  aus diesem Budget; der Voll-Scrape wird vor dem Start gegen das
  Restbudget geschätzt (steht im Fusionsbericht).
- Overpass: kostenlos.
- North Data-Actor: Preis je Lauf wird im Mini-Test gemessen, BEVOR
  etwas Größeres läuft.

## Risiken

- Dritt-Scraper (Gelbe Seiten, North Data) können jederzeit brechen —
  abgefedert durch Fusion mehrerer Quellen und Bonus-Status.
- Overpass drosselt bei zu vielen Anfragen — eingebaute Wartezeiten,
  Lauf dauert dafür länger.
- Adress-Daten ohne Webseite: Firmen ohne Domain kann die
  Entscheider-Suche kaum bedienen — der Fusionsbericht weist sie aus.

## Fortschritt

- [x] Schritt 1: Gelbe-Seiten-Baustein (29.07.: Actor plowdata gewählt,
      Mini-Lauf Hannover: 10 Treffer inkl. Telefon/Mail, Kosten 0,018 $)
- [x] Schritt 2: Overpass-Baustein (29.07.: PLZ-Gebiets-Suche lief in
      504-Timeout -> Umbau auf Rechteck-Suche + eigene PLZ-Filterung;
      Live-Nachweis: 132 IT-Firmen in PLR 30/31, 112 mit Webseite)
- [x] Schritt 3: Fusions-Baustein + Ausschluss-Filter (29.07.: Tests
      grün, Gesamt-Suite 615)
- [x] Schritt 4: North-Data-Bonus GESTRICHEN (Leonard, 29.07.2026:
      North Data hat keine E-Mail-Adressen, nur Namen — die Namens-
      Lücke deckt die Impressum-KI; Rest geht über geprüfte info@
      bzw. Anruf/Brief-Liste)
- [x] Schritt 5: Voll-Scrape PLR 30+31 (29.07.: Maps 2.089 + Gelbe
      Seiten 157 + OpenStreetMap 132 + alte Liste 319 Roh ->
      **1.481 einzigartige Firmen** in Region 30/31; 221 Duplikate
      verschmolzen, 900 fremde PLZ raus (u.a. alte 32er-39er),
      95 Oliver-Ausschlüsse gelistet, 224 ohne Webseite; Maps-Lauf
      nach 55 min kontrolliert abgebrochen, Ausbeute war trocken;
      Kosten gesamt ~7 $ von 29 $)
- [ ] Schritt 6: Übergabe an bestehende Strecke (Monats-Paket 1 ~450
      Firmen — als Nächstes dran)
