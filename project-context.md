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
- Phase 2 des Wholix-Nachbaus ist gebaut: Freigabe je Empfänger und
  E-Mail-Schritt, Suche, Filter, Sammelaktionen, einzelne Neuerzeugung,
  vollständige Übergabesperre, lesender Instantly-Stand und die erweiterte
  globale Sperrliste.
- Frische Gesamtkontrolle am 22.07.2026: 518 Tests grün. Einen einzigen
  langen Testprozess beendet das System wiederholt ohne Testfehler und ohne
  Abschlussmeldung; deshalb wurden alle Tests vollständig in sieben frischen
  Blöcken ausgeführt. Die einzige Warnung ist die bekannte
  Starlette-Abkündigung im TestClient.
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
- Die Sichtprüfung für Phase 2 lief nur mit festen lokalen Testdaten. Die
  Nachweise liegen unter `.superpowers/phase-2/`: Freigabeübersicht,
  Prüftabelle, Textdialog, schreibgeschützte Übergabe, Sperrliste sowie beide
  390-px-Ansichten. Auf 390 px gibt es keinen seitlichen Überlauf der ganzen
  Seite; nur die breiten Tabellen scrollen in ihrem eigenen Bereich.
- Der dauerhafte Arbeitsnachweis steht in Jira unter `AP-199` und ist als
  erledigt markiert.
- Kontrollierter End-to-End-Test am 23.07.2026: Eine eigene Instantly-
  Testkampagne hatte genau einen Absender, einen Schritt, Tageslimit eins und
  `ingeborgmarder@gmail.com` als einzigen Empfänger. Die Mail wurde um 10:09
  Uhr zugestellt, die einmalige Testantwort um 10:10 Uhr von Instantly
  übernommen und im eigenen Postfach sichtbar angezeigt. Die Kampagne wurde
  direkt nach dem Versand pausiert.
- Der Live-Test fand und belegte drei Instantly-Abweichungen, die behoben
  wurden: `/leads/list` erwartet den Filter `campaign`, Aktivieren/Pausieren
  darf keinen JSON-Inhaltstyp ohne Inhalt senden und echte E-Mail-Schritte
  kommen als `0_0_0`, `0_1_0`, `0_2_0`. Die Korrekturen sind mit zuerst
  fehlschlagenden Gegentests abgesichert.
- Frische Gesamtkontrolle am 23.07.2026: 520 Tests grün in einem vollständigen
  Lauf. Es bleibt nur die bekannte Starlette-Abkündigungswarnung.
- Der Nachweis zum kontrollierten End-to-End-Test steht in Jira unter
  `AP-200` und ist als erledigt markiert.

## Entscheidungen

- Instantly bleibt der unsichtbare Versand-Motor. Das Tool liest seine Daten
  für die Kampagnenansicht; echte Schreibaktionen sind nicht Teil der
  lokalen Prüfungen.
- Das Gmail-Testkonto dient ausschließlich als ungefährliches Testpostfach.
  Es wird nicht dauerhaft mit dem Tool verbunden. Eine direkte Gmail-
  Anmeldung, gespeicherte Google-Zugänge oder ein dauerhafter Mail-Abgleich
  sind nicht freigegeben.
- Der erfolgreiche End-to-End-Test ändert daran nichts: Gmail war nur
  Empfänger und Absender der manuellen Testantwort. Unser Tool erhielt keinen
  Gmail-Zugang; Versand und Antwortabruf liefen ausschließlich über Instantly.
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
- Die Instantly-Abfrage der Freigabe ist rein lesend und konservativ. Nur bei
  genau einer ausgehenden E-Mail in einem Verlauf wird eine Antwort diesem
  Schritt zugeordnet. Bei mehreren möglichen Schritten bleibt die Zuordnung
  unbekannt, während der belegbare Gesamtstand sichtbar bleibt.
- Nach der Übergabe ist die E-Mail-Runde im Tool schreibgeschützt. Eine
  einzelne Neuerzeugung macht nur den betroffenen Schritt wieder offen.

## Nächste Schritte

- Vor Phase 3 den Postfach-Umfang neu festlegen: Das Test-Gmail darf für
  Testmails verwendet werden, aber nicht dauerhaft an das Tool angebunden
  werden. Die bisher geplante direkte Google-/Microsoft-Verbindung startet
  daher nicht.
- Als schlanke Alternative prüfen: den vorhandenen, nun live bewiesenen
  Instantly-Postfachbereich für Kampagnenantworten beibehalten und danach den
  CRM-Ausbau beginnen.
- Danach bleiben CRM-Rand und die noch offenen Wholix-Funktionen laut Roadmap.
- Schreibende Versand- oder Postfachprüfungen nur mit ausdrücklicher
  Freigabe und Testkonten.
