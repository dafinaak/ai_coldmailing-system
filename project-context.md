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
- Der vereinbarte kleine Teil von Phase 3 ist gebaut: Im internen Postfach
  kann das Team auf eine bestehende empfangene Instantly-Mail antworten.
  Das Absenderkonto ist sichtbar und kommt aus den belegten Instantly-Daten.
  Eine 15 Minuten gültige Signatur bindet Kontakt und Mail; ein atomarer
  Einmalverbrauch verhindert wiederholten Versand mit demselben Beleg.
  Bei einem unklaren Ausgang gibt es keine automatische Wiederholung und
  keinen neuen Sendeknopf, bis der Verlauf in Instantly geprüft wurde.
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
- Frische Gesamtkontrolle der Antwortfunktion am 23.07.2026: 550 Tests grün
  in einem vollständigen Lauf. Es bleibt nur dieselbe bekannte
  Starlette/httpx-Abkündigungswarnung.
- Die sichtbare Prüfung nutzte ausschließlich feste lokale Testdaten und
  eine Demo ohne Versandroute. Die Nachweise liegen unter
  `.superpowers/phase_3/`: `postfach-antwort-desktop.png`,
  `postfach-antwort-390.png`, `postfach-antwort-erfolg-desktop.png` und
  `postfach-antwort-unklar-390.png`. Desktop und 390-px-Ansicht haben keinen
  seitlichen Seitenüberlauf; beim unklaren Ausgang bleiben Entwurf und
  Hinweis sichtbar, aber Antwortfeld und Sendeknopf fehlen.
- Für den Bau und die lokale Prüfung wurde keine echte E-Mail versendet und
  kein Gmail-/Microsoft-Zugang eingerichtet oder gespeichert.
- Anbieter-Vergleich vorbereitet (23.07.2026): Bevor der CRM-Ausbau beginnt,
  soll der Datenanbieter für deutsche Kleinfirmen per Messung entschieden
  werden. Dafür ist alles Lokale gebaut und mit Tests belegt (577 Tests grün):
  ein Prospeo-Baustein (`pipeline/sources/prospeo.py`, Suche über die
  Firmen-Domain plus Anreicherung nur geprüfter Mails) und ein
  wiederaufnehmbarer Vergleichs-Läufer (`pipeline/vergleich.py`), der Weg A
  (Apify→Prospeo) und Weg B (Apify→Hunter→Dropcontact) über dieselbe
  Apify-Firmenliste schickt und Bericht + Rohdaten in einen Lauf-Ordner
  schreibt. Achtung Benennung: im älteren Code von `pipeline/sourcing.py`
  heißt Hunter→Dropcontact noch „Weg A"; im Vergleich gilt die neue
  Benennung aus dem Auftrag (Weg A = Prospeo). Es wurde noch keine echte
  Anbieter-Abfrage ausgeführt; es fehlen die Schlüssel PROSPEO_API_KEY,
  HUNTER_API_KEY und DROPCONTACT_API_KEY sowie Leonards Okay für den
  Guthaben-Verbrauch (Gratis-Kontingente laut offiziellen Seiten am
  23.07.2026: Prospeo 100 Credits/Monat, Hunter 50 Credits/Monat,
  Dropcontact 50 Gratis-Credits).
- Kaskade nach Chef-Vorgabe gebaut (23.07.2026, per Leonard übermittelt):
  Google Maps liefert die Firmen (übernommen wird v. a. die Website),
  danach versuchen die Anbieter-Stufen aus `anbieter_reihenfolge` in der
  Kunden-Datei NACHEINANDER den Entscheider mit geprüfter persönlicher
  Mail zu finden („findet Stufe 1 nur 80 von 100, versucht Stufe 2 die
  restlichen 20"); wer übrig bleibt, bekommt info@ — neu: vor der
  Übernahme über Hunters Email Verifier geprüft (invalid/disposable/
  unknown wird verworfen, Ausgang „info_ungueltig"). Der Bericht zählt
  je Stufe, wer geliefert hat (`deckung.je_stufe`), und der
  Vergleichsbericht rechnet die Kombination beider Wege aus
  („Kaskade"-Abschnitt). Standard bleibt einstufig Hunter→Dropcontact,
  bis der Anbieter-Vergleich die Reihenfolge festlegt. 592 Tests grün.
- Messlauf am 23.07.2026 mit echten Gratis-Konten über die 20 echten
  Firmen (IT-Dienstleister Hannover, Liste vom 21.07.): Weg A (Prospeo)
  6 geprüfte persönliche Mails, Weg B (Hunter→Dropcontact) 7; auf den
  16 von beiden geprüften Firmen je 6 (37,5 %), Kombination 8 von 16
  (50 %) — jeder Weg rettet Firmen, die der andere nicht kennt. Keine
  fremden Domains. Vier Firmen blieben bei Weg A offen (Tageslimit des
  Prospeo-Gratis-Kontos), bewusst nicht nachgezogen. Qualitäts-Vorbehalt:
  einige Treffer tragen Titel wie „Product Owner"/„Director" (kein
  Inhaber) — Handprüfung durch Leonard steht aus. Live-Funde behoben:
  Prospeo-„NO_RESULTS" ist kein Fehler, Prospeo drosselt (~45 Suchen/Tag
  frei), Dropcontact braucht bis ~2 Minuten Abholzeit, deutsche
  Titelformen („Geschäftsführender Gesellschafter") und falsche Freunde
  („Product Owner") im Rollen-Abgleich. Ergebnisse liegen unter
  `laeufe/vergleich-anbieter/2026-07-23-prospeo-20-firmen-v2/`
  (bericht.md mit Handprüfungs-Spalte). Echten Credit-Verbrauch in den
  Anbieter-Dashboards gegenprüfen, bevor Preise je Kontakt gerechnet
  werden.
- Kontrollierter Live-Test am 23.07.2026: Das neue Antwortfeld sendete genau
  eine klar gekennzeichnete Testantwort über Instantly von
  `email@seo-poleposition.online` an das eigene Testkonto
  `ingeborgmarder@gmail.com`. Instantly bestätigte den Versand, die
  ausgehende Nachricht erschien direkt im internen Verlauf und Gmail zeigte
  sie um 11:42 Uhr als dritte Nachricht desselben Threads. Gmail war dabei
  nur das Testziel und wurde weiterhin nicht an das Tool angebunden.

- Messung „Impressum-Name → Dropcontact" am 23.07.2026 (Olivers Frage nach
  dem Weg zu 80 %): Bei 6 der 8 Lücken-Firmen stand der Chef-Name im
  Impressum; aus allen 6 Namen baute und prüfte Dropcontact eine
  persönliche Mail (100 %). Neue Gesamtabdeckung 14 von 16 Firmen
  (87,5 %) — über dem 80-%-Ziel. Details und Vorbehalte (Handarbeit,
  JavaScript-Impressum, abweichende Mail-Domains, veraltbare Impressen):
  `laeufe/vergleich-anbieter/2026-07-23-prospeo-20-firmen-v2/impressum-messung.md`.
  Der BAU der Impressum-Stufe ist NICHT begonnen — er braucht Olivers
  Okay (berührt die Projektregel „kein selbst gebautes Fundament") und
  einen abgesegneten Bauplan.

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
- Am 23.07.2026 wurde der verkleinerte Umfang von Phase 3 festgelegt:
  Das interne Postfach darf über den offiziellen Instantly-Endpunkt auf eine
  bestehende empfangene Kampagnenmail antworten. Es gibt weiterhin keine
  direkte Gmail-/Microsoft-Verbindung, keinen freien Mailversand und keinen
  vollständigen Postfach-Abgleich.
- Der Bau und sein Nachweis stehen in Jira unter `AP-201`; die Aufgabe ist
  mit dem vollständigen Test- und Sichtnachweis als erledigt markiert.
- Der testgetriebene Bauplan steht unter
  `docs/superpowers/plans/2026-07-23-instantly-antworten.md` und wurde
  vollständig umgesetzt.
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

- Zuerst den Anbieter-Vergleich abschließen: Konten/Schlüssel für Prospeo,
  Hunter und Dropcontact anlegen, kleinen Apify-Nachschub auf 30–40 Firmen
  holen (eine echte 20er-Liste liegt unter
  `laeufe/demo-gmbh/20260721-145036/firmen.json`), dann
  `python -m pipeline.vergleich` laufen lassen — erst nach Leonards Okay,
  weil dabei Gratis-Guthaben verbraucht wird. Danach Empfehlung geben und
  `docs/datenquellen-strategie.md` plus diese Datei aktualisieren.
- Erst nach der Anbieter-Entscheidung: den CRM-Ausbau als eigenes
  Arbeitspaket entwerfen — zuerst Kontakte zuverlässig durch
  Verkaufsstufen führen.
- Weitere Wholix-Bereiche bleiben gestrichen, solange die Scope-Entscheidungen
  nicht ausdrücklich geändert werden.
- Schreibende Versand- oder Postfachprüfungen nur mit ausdrücklicher
  Freigabe und Testkonten.
