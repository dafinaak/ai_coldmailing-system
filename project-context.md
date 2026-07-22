# Projekt: AI Coldmailing System

## Worum es geht

Das interne Team-Tool ersetzt die Wholix-Oberfläche schrittweise. Es führt
von Angebot und Lead-Suche über KI-Texte und Freigabe bis zum Versand.
Instantly bleibt darunter der Versand-Motor für Versand, Anwärmen und
Zustellbarkeit. Die Wholix-Bildschirmfotos sind die Vorlage für Aussehen und
Bedienung; der genaue Umfang steht in `docs/wholix-nachbau-roadmap.md`.

Zuverlässigkeit steht vor Tempo und Kosten: Daten kommen aus stabilen,
bezahlten Schnittstellen; jede E-Mail wird vor Versand geprüft. Tests und
sichtbare Nachweise benutzen Testdaten, niemals echte Empfänger.

## Aktueller Stand

- Die erste Pipeline und das Team-Interface sind gebaut. Instantly wird
  weiter als Versand-Motor genutzt.
- Phase 1 des Wholix-Nachbaus (Kampagnenübersicht und -detail) ist gebaut:
  Live-Werte werden lesend aus Instantly aufbereitet, fehlende Werte werden
  nicht erfunden, und der Link führt zu den Kampagnen-Einstellungen in
  Instantly.
- Frischer voller Testlauf am 22.07.2026:
  `461 passed, 1 warning in 86.39s`. Die eine Warnung ist die bekannte
  Starlette-Abkündigung für `httpx` im TestClient.
- Die Sichtprüfung lief lokal mit festen Testdaten. Desktop und 390-px-
  Ansichten von Übersicht und Detail sind festgehalten. Bei 390 px liegt die
  Navigation oben; die Übersicht hat volle Inhaltsbreite, keinen Dokument-
  Überlauf und nur die Tabelle scrollt intern.
- Am 22.07.2026 wurde Phase 1 zusätzlich rein lesend gegen das echte
  Instantly-Konto geprüft. Die fünf geprüften GET-Endpunkte für Kampagne,
  Kennzahlen, Schrittwerte, Konten-Tageswerte und Postfächer antworteten mit
  HTTP 200; es wurden keine Namen, Adressen oder Kennzahlen ausgegeben und
  keine Daten verändert. Instantly lieferte für den heutigen Tageszeitraum
  keine Zeile, daher zeigt das Tool den Tagesverbrauch zuverlässig als
  unbekannt statt als erfundene Null.
- Die Kampagnenansicht nutzt die Empfängerzahl von Instantly. Die Zahl des
  zuletzt freigegebenen Laufs wird im Detail getrennt gezeigt. Der heutige
  Versand wird aus der täglichen Konten-Auswertung nur für die verwendeten
  Absenderpostfächer summiert. Die Absender werden als Pflichtfilter
  übergeben; der Zeitraum reicht von heute bis zum Folgetag. Ein Ausfall
  dieser einzelnen Auswertung macht die übrigen Live-Werte nicht unbekannt.
- Ein zuletzt bekannter Postfachstand bleibt bei einem späteren Lesefehler
  sichtbar und wird mit der Fehlerzeit gekennzeichnet. Kampagnentabelle,
  Fehlermeldungen und Zahlenfarben sind auch für Tastatur und Lesesoftware
  verständlich geprüft.
- Die Gestaltung für Phase 2 ist mit dem Nutzer abgestimmt und als
  `docs/superpowers/specs/2026-07-22-wholix-freigabe-phase-2-design.md`
  gesichert. Der ausführbare Bauplan liegt unter
  `docs/superpowers/plans/2026-07-22-wholix-freigabe-phase-2.md`; Programmcode
  für Phase 2 wurde noch nicht verändert.

## Entscheidungen

- Instantly bleibt der unsichtbare Versand-Motor. Das Tool liest seine Daten
  für die Kampagnenansicht; echte Schreibaktionen sind nicht Teil der
  lokalen Prüfungen.
- Kampagnen-Einstellungen (Tageslimit, Sendefenster, Signatur und ähnliche
  Werte) werden nicht im Tool nachgebaut. Der Weg dafür ist der Link nach
  Instantly.
- Verlässliche Instantly-Felder werden gezeigt. Für „fehlgeschlagen" und
  nicht getrennt gelieferte Warteschlangen-Zustände zeigt die Oberfläche
  keinen geschätzten Wert.
- Instantly und der freigegebene Lauf bleiben getrennte Datenquellen: Live-
  Kennzahlen und Warteschlange beruhen auf Instantly; der lokale Lauf wird
  nur als eigener Vergleichswert gezeigt.
- Der Warteschlangenring verrechnet Unzustellbare nicht als eigene Gruppe.
  Er zeigt nur „versendet" und den Rest „nicht getrennt verfügbar".
  Unzustellbare stehen mit einem Überschneidungshinweis getrennt darunter.
- Die zusammengefasste Zahl aktiver Kampagnen wird nur berechnet, wenn alle
  berücksichtigten Kampagnen einen bekannten Status haben.
- Die neun am 22.07.2026 gestrichenen Wholix-Funktionen bleiben gestrichen;
  insbesondere keine Benutzerverwaltung, Calls, Notizen oder AI-Chat.
- In Phase 2 zeigt jede Prüftabelle genau eine E-Mail-Runde. Jeder der drei
  Schritte wird einzeln bestätigt; mehrere Empfänger können gesammelt
  bestätigt werden. An Instantly geht weiterhin nur die vollständig
  bestätigte Runde.
- Ein ungeeigneter Text wird nicht frei bearbeitet, sondern genau für diesen
  Schritt neu erzeugt. Unbekannte Instantly-Zustände bleiben unbekannt.
- Die globale Sperrliste erhält Grund und Kommentar sowie Muster wie
  `*.bund.de`; alte einfache YAML-Einträge bleiben lesbar.

## Nächste Schritte

- Den Phase-2-Bauplan freigeben und danach in neun einzeln prüfbaren Aufgaben
  ausführen: Freigabezustand, Rundendaten, sichere Aktionen, einzelne
  Neuerzeugung, Instantly-Lesestand, Prüftabelle, Sperrlisten-Daten,
  Sperrlisten-Oberfläche und Gesamtnachweis.
- Spätere Phasen bleiben Mail-Programm, CRM-Rand und die noch offenen
  Wholix-Funktionen laut Roadmap.
- Schreibende Versand- oder Postfachprüfungen nur mit ausdrücklicher
  Freigabe und Testkonten.
