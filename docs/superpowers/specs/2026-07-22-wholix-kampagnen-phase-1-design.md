# Wholix-Kampagnenansicht – Entwurf für Phase 1

## Ziel

Die Kampagnenübersicht und die Kampagnendetails sehen aus und bedienen sich
wie die vorhandenen Wholix-Vorlagen. Alle Zahlen stammen aus belegten
Instantly-Feldern oder werden ausdrücklich als nicht verfügbar gezeigt.
Instantly bleibt der Versand-Motor.

## Gewählter Weg

Wir erweitern zuerst `InstantlyLeser` um eine klare, fehlertolerante
Anzeigeform und bauen die Vorlagen anschließend nur gegen diese Anzeigeform.
Das ist zuverlässiger als rohe Instantly-Antworten direkt in Jinja zu
verwenden und einfacher als ein zusätzlicher JavaScript-Datenabruf im
Browser. Der vorhandene 60-Sekunden-Zwischenspeicher und der letzte bekannte
Stand bleiben erhalten.

Nicht gewählt wurden:

- reine Vorlagen-Anpassung: schneller, aber Feldnamen und fehlende Werte
  würden sich durch die Oberfläche ziehen;
- Datenabruf im Browser: lebendiger, aber doppelte Fehlerbehandlung,
  zusätzliche Ladezustände und unnötig mehr Technik.

## Verbindlicher Umfang

### Kampagnenübersicht

- Kopfbereich im Wholix-Muster mit Seitentitel, kurzer Erklärung und der
  vorhandenen Aktion zum Erstellen einer E-Mail-Runde;
- Kennzahlen für Kampagnen, aktive Kampagnen, Empfänger, geöffnet,
  versendet, Antworten, fehlgeschlagen und unzustellbar;
- Suchfeld und Statusfilter für die Kampagnenliste;
- bestehende Läufe in Vorbereitung bleiben sichtbar;
- Tabellenzeilen zeigen Status und die belegten Live-Zahlen;
- Ladefehler zeigen den letzten bekannten Stand mit Zeitpunkt. Ohne früheren
  Stand werden Striche statt erfundener Nullen gezeigt.

### Kampagnendetails

- Kennzahlenleiste nach Wholix für Empfänger, mögliche E-Mails, versendet,
  geöffnet, Antworten, fehlgeschlagen und unzustellbar;
- Kampagnenangaben mit Name, Kennung, Erstellungs-/Freigabeangaben und
  Absendern, soweit Instantly diese Felder liefert;
- vorhandener Erzeugungsstand bleibt erhalten;
- Warteschlangen-Diagramm mit den sicher bekannten Gruppen „versendet“ und
  „unzustellbar“. Der übrige Teil wird als „nicht getrennt verfügbar“
  zusammengefasst, weil Instantly wartend, geplant, übersprungen und
  abgebrochen nicht als vollständige Kampagnenzähler liefert;
- Fortschritt je E-Mail-Schritt bleibt sichtbar und übernimmt zusätzlich die
  belegten Öffnungszahlen;
- Bereich „Tageslimit und Sendefenster“ mit heutigem Versand der verwendeten
  Absender, bekannten Tageslimits, Wochentagen, Uhrzeit und Zeitzone;
- ein klarer Hinweis zeigt, ob der aktuelle Zeitpunkt im Sendefenster liegt;
- Kampagnen-Einstellungen werden nicht im Tool geändert. Der vorhandene Link
  zu Instantly ist der einzige Einstellungsweg (Scope-Entscheidung vom
  22.07.2026).

## Verlässliche Datenregeln

- `open_count` ist die Zahl für „geöffnet“.
- `bounced_count` ist die Zahl für „unzustellbar“.
- Instantly dokumentiert keinen vollständigen Zähler für
  „fehlgeschlagene E-Mails“. Die Kachel wird deshalb mit einem Strich und dem
  Hinweis „Instantly liefert keinen verlässlichen Zähler“ angezeigt.
- `emails_sent_count`, `reply_count`, `leads_count` und `completed_count`
  werden nur als die Bedeutung angezeigt, die Instantly selbst beschreibt.
- Die Schrittstatistik verwendet `sent` und `opened` aus
  `/campaigns/analytics/steps`.
- Das Sendefenster kommt aus `campaign_schedule.schedules` der Kampagne.
- Tageslimits kommen aus den verwendeten Instantly-Postfächern. Fehlt ein
  Limit, wird es nicht als Null gerechnet.
- Der heutige Versand kommt aus `/accounts/analytics/daily` und wird als
  Verbrauch der Absender-Postfächer bezeichnet, nicht als ausschließlich
  dieser Kampagne zugerechnet.
- Aus unbekannten Feldern werden keine Werte geschätzt. `None` bleibt in der
  Oberfläche „—“.

## Aufbau und Dateien

- `web/instantly_leser.py`: Instantly-Antworten lesen, prüfen, vereinheitlichen
  und zwischenspeichern;
- `web/routen/kampagnen.py`: Listen- und Detailwerte für die Anzeige
  zusammenstellen, ohne eigene HTTP-Aufrufe;
- `web/templates/kampagnen_liste.html`: Wholix-nahe Übersicht;
- `web/templates/kampagne_detail.html`: Wholix-nahe Detailansicht;
- `web/static/stil.css`: Kampagnenkarten, Tabelle, Diagramm, Sendefenster und
  kleine Bildschirmbreiten;
- `tests/web/test_instantly_leser.py`: Feldübersetzung, fehlende Felder,
  Zwischenspeicher und Ausfälle;
- `tests/web/test_kampagnen.py`: sichtbare Inhalte, Filter, Striche bei
  unbekannten Werten und bestehende Aktionen.

## Gestaltung

Die Bildschirmfotos sind die feste Vorlage. Die Kampagnenseiten verwenden
Wholix' ruhige weiße Fläche, sehr helle graue Linien, abgerundete Karten,
orange Hauptaktionen sowie sparsame Statusfarben. Typografie, Abstände und
Tabellendichte folgen den Vorlagen; es wird keine neue eigene Stilrichtung
erfunden. Die auffälligste Form ist die Kampagnen-Detailfläche mit der
Kennzahlenleiste und dem Warteschlangenring.

Die Oberfläche bleibt mit Tastatur bedienbar, zeigt sichtbare Fokusrahmen und
ordnet Karten und Tabellen auf schmalen Bildschirmen untereinander an.

## Fehler- und Leerzustände

- kein Live-Abruf, aber Zwischenspeicher vorhanden: Werte bleiben sichtbar,
  dazu „Live-Stand gerade nicht erreichbar“ mit Uhrzeit;
- kein Live-Abruf und kein Zwischenspeicher: Striche und ein sachlicher
  Hinweis, keine Nullen;
- keine Kampagnen: bestehender Leerzustand mit der Aktion zum Erstellen einer
  E-Mail-Runde;
- fehlendes Tageslimit oder Sendefenster: „Nicht in Instantly hinterlegt“;
- ungültige oder unvollständige Zeitangaben: kein Absturz, Status
  „Sendefenster nicht vollständig hinterlegt“.

## Prüfung und sichtbarer Nachweis

1. Jede neue Datenregel bekommt zuerst einen fehlschlagenden Test.
2. Jede neue Oberflächenregel bekommt zuerst einen fehlschlagenden Web-Test.
3. Danach läuft die vollständige Python-Sammlung mit
   `python -m pytest -q`.
4. Die Kampagnenseiten werden lokal ausschließlich mit Testdaten geöffnet.
5. Übersicht und Detailansicht werden als Bildschirmfoto mit den Wholix-
   Vorlagen verglichen.

## Nicht Teil dieser Phase

- Freigabe-Tabelle, CRM-Ausbau und vollständiges Mail-Programm;
- Änderungen am Daten-Motor unter `pipeline/`;
- echte Postfächer verbinden oder echte E-Mails senden;
- Kampagnen-Einstellungen in unserem Tool ändern;
- die neun am 22.07.2026 gestrichenen Wholix-Funktionen.
