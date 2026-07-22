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
  `444 passed, 1 warning in 77.38s`. Die eine Warnung ist die bekannte
  Starlette-Abkündigung für `httpx` im TestClient.
- Die Sichtprüfung lief nur lokal mit festen Testdaten und ohne
  Instantly-Schlüssel. Desktop und 390-px-Ansichten von Übersicht und Detail
  sind festgehalten. Bei 390 px liegt die Navigation oben; die Übersicht hat
  volle Inhaltsbreite, keinen Dokument-Überlauf und nur die Tabelle scrollt
  intern.

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
- Die neun am 22.07.2026 gestrichenen Wholix-Funktionen bleiben gestrichen;
  insbesondere keine Benutzerverwaltung, Calls, Notizen oder AI-Chat.

## Nächste Schritte

- Phase 2 des Fahrplans planen: Status je Empfänger und je E-Mail-Schritt in
  der Freigabe-Tabelle.
- Spätere Phasen bleiben Mail-Programm, CRM-Rand und die noch offenen
  Wholix-Funktionen laut Roadmap.
- Echte Versand- oder Postfachprüfungen nur mit ausdrücklicher Freigabe und
  Testkonten.
