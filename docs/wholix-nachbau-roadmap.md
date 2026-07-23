# Wholix-Nachbau: Feature-Inventur und Fahrplan

Stand: 22.07.2026 (Phase 1 und 2 gebaut und lokal geprüft; siehe Abschnitt 3)

## Scope-Entscheidungen (22.07.2026)

Nach Durchsicht mit Leonard: nicht jede Wholix-Funktion ist für ein
internes Tool sinnvoll. Bauen wir NICHT (gestrichen):

- Arbeitsbereiche / "My office" (2)
- Zwei-Faktor-Anmeldung (4)
- Hell-/Dunkel-Ansicht (5)
- Benachrichtigungs-Glocke (6)
- Support-Chat-Knopf (7)
- AI-Chat (8)
- Benutzerverwaltung / Kollegen einladen (3) — ein gemeinsamer Zugang bleibt
- Anrufe-Bereich (25)
- Notizen (28)

Nur schlank statt 1:1:

- Kampagnen-Einstellungen im Tool ändern (37) — Link nach Instantly statt Nachbau
- Text einzeln von Hand bearbeiten (40) — wir bleiben bei "neu erzeugen lassen"
- Mail-Bereich (13–24) — nur Kampagnenverläufe lesen, über Instantly auf
  bestehende empfangene Mails antworten und Instantly-Verbindungsprobleme
  sichtbar machen. Kein vollständiges Gmail-/Microsoft-Postfach.

Bleibt voll im Scope (Aussehen wie Wholix): der bisherige Kampagnen- und
Freigabebereich sowie das CRM mit Verkaufs-Stufen (9–12, 26, 27). Die
Inventur unten bleibt als Vergleich mit Wholix vollständig; gebaut wird nur,
was die Scope-Entscheidungen in diesem Abschnitt vorsehen.

**Entscheidung vom 23.07.2026:** Das Gmail-Testkonto ist nur für sichere
Testmails gedacht. Es wird nicht dauerhaft mit dem Tool verbunden. Eine
direkte Gmail-Anmeldung, gespeicherte Google-Zugänge und ein dauerhafter
Mail-Abgleich werden nicht gebaut. Phase 3 wird auf das Instantly-
Kampagnenpostfach verkleinert: Gespräche lesen und über den offiziellen
Instantly-Endpunkt auf eine bestehende empfangene Mail antworten. Freier
Mailversand und ein vollständiges Postfach bleiben außerhalb des Umfangs.

---


**Auftrag:** Unser Tool übernimmt die für das Team sinnvollen Wholix-Bereiche
in gleicher Gestaltung und Bedienlogik. Dieses Dokument listet zum Vergleich
weiterhin ALLES auf, was Wholix kann, markiert bei jedem Punkt den aktuellen
Stand und macht daraus einen Baufahrplan. Die Scope-Entscheidungen oben legen
verbindlich fest, welche Teile bewusst nicht oder nur schlank gebaut werden.

**Quellen:**

- 10 Bildschirmfotos der Wholix-Oberfläche (Ordner „wholix interface
  screenshots" auf dem Schreibtisch).
- Netzwerk-Mitschnitt der Wholix-Web-App (`app.wholix.ai.har`): zeigt, welche
  Daten die Oberfläche vom Wholix-Server holt — also was das Tool wirklich
  tut, auch hinter den Kulissen. Der Mitschnitt deckt vor allem den
  E-Mail-Bereich ab (10 verschiedene Wholix-Schnittstellen gefunden); die
  Antwort-Daten verraten aber auch viel über Kampagnen, Leads, Freigaben und
  Benutzerverwaltung.
- Unser eigenes Tool (Oberfläche, Vorlagen, Instantly-Untersuchung vom
  20.07.2026).

---

## 1. Feature-Inventur

Jede Zeile ist eine Funktion von Wholix. Drei mögliche Stände:

- **HABEN WIR** — gibt es bei uns schon (manchmal anders gelöst, aber gleiches Ergebnis)
- **TEILWEISE** — gibt es bei uns zum Teil; die Lücke steht dabei
- **FEHLT** — gibt es bei uns noch gar nicht

### Rahmen und Konto

| Nr. | Funktion | Stand | Anmerkung |
|---|---|---|---|
| 1 | Anmeldung / Login | HABEN WIR | |
| 2 | Arbeitsbereiche (Umschalter „My office" — mehrere getrennte Bereiche in einem Konto) | FEHLT | |
| 3 | Benutzerverwaltung (Kollegen einladen, sehen wer eingeladen hat, Status je Nutzer) | FEHLT | Bei uns: ein gemeinsamer Zugang |
| 4 | Zwei-Faktor-Anmeldung | FEHLT | |
| 5 | Hell-/Dunkel-Ansicht umschalten | FEHLT | |
| 6 | Benachrichtigungs-Glocke | FEHLT | |
| 7 | Support-Knopf (eingebautes Hilfe-Chat-Fenster) | FEHLT | Für ein internes Tool wäre das schlicht ein „Frag Leonard"-Hinweis |

### AI-Chat

| Nr. | Funktion | Stand | Anmerkung |
|---|---|---|---|
| 8 | AI-Chat-Bereich (mit der KI über die eigenen Daten reden) | FEHLT | Im Mitschnitt nicht erfasst; Umfang bei Wholix daher nur aus dem Menüpunkt bekannt |

### Contacts (Kontakte mit Verkaufs-Stufen)

| Nr. | Funktion | Stand | Anmerkung |
|---|---|---|---|
| 9 | Kontakt-Liste mit Suche und Filter | TEILWEISE | Unsere „Kontakte": nur lesen, Suche ja, Filter nein |
| 10 | Kontakt anlegen und bearbeiten | FEHLT | Bei uns bewusst nur lesend |
| 11 | Verkaufs-Pipelines mit Stufen (New Lead, Demo, Follow up, Proposal, Won, Lost — plus eigene Pipelines anlegen, Zähler je Stufe) | FEHLT | Das ist das eigentliche „CRM" in Wholix |
| 12 | Ansicht umschalten (Tabelle / Karten-Board) | FEHLT | |

### Email (vollwertiges Mail-Programm im Tool)

| Nr. | Funktion | Stand | Anmerkung |
|---|---|---|---|
| 13 | Ordner wie im Mail-Programm: Posteingang, Archiv, Verlauf, Gelöscht, Entwürfe, Junk, Postausgang, Gesendet, Markiert, Wichtig — mit Zählern | FEHLT | |
| 14 | Einheits-Posteingang (alle Postfächer zusammen) + Wechsel auf ein einzelnes Postfach | TEILWEISE | Unser „Postfach" zeigt nur Antworten zu unseren Kampagnen (über Instantly), nicht das ganze Postfach |
| 15 | Mail-Liste (Absender, Betreff, Datum, Anhang-Zeichen, Mehrfach-Auswahl, löschen/archivieren) | FEHLT | |
| 16 | Konversations-Ansicht (Verlauf einer Unterhaltung untereinander) | HABEN WIR | Bei uns je Kampagnen-Kontakt, chronologisch |
| 17 | Antworten / Allen antworten / Weiterleiten / Löschen | FEHLT | Bei uns bisher bewusst verschoben („In Instantly antworten") |
| 18 | Neue Mail verfassen (Compose) | FEHLT | |
| 19 | Suche in Mails + Filter (ungelesen, markiert, wichtig, mit Anhang) | FEHLT | |
| 20 | Markierungen: Stern, Wichtig, gelesen/ungelesen | FEHLT | |
| 21 | Signatur je Postfach | FEHLT | |
| 22 | Postfach direkt per Google-/Microsoft-Anmeldung verbinden + Verbindungs-Status (Token gültig?) | TEILWEISE | Status zeigen wir (über Instantly); Verbinden geht nur in Instantly selbst |
| 23 | Mail-Abgleich: Ordner und Mails vom Postfach laden, auch im Hintergrund | FEHLT | Wholix speichert die Mails auf dem eigenen Server zwischen |
| 24 | Postfach-Warnungen („Handlung nötig", „neu verbinden"-Knopf) | TEILWEISE | Warnung auf dem Dashboard haben wir; einen Reparatur-Knopf nicht |

### Calls (Anrufe)

| Nr. | Funktion | Stand | Anmerkung |
|---|---|---|---|
| 25 | Anrufe-Bereich (Anruf-Liste je Kontakt) | FEHLT | Im Mitschnitt nicht erfasst; Umfang nur aus dem Menüpunkt bekannt |

### Leads

| Nr. | Funktion | Stand | Anmerkung |
|---|---|---|---|
| 26 | Leads-Tabelle: Kampagnen-Zuordnung, Jobtitel, Firma, Firmen-Webseite, E-Mail, Telefon (Büro/Mobil), LinkedIn/Facebook/Twitter; sortierbar, 100 pro Seite | TEILWEISE | Unsere Kontakte-Tabelle hat weniger Spalten und ist nur lesend |
| 27 | Lead bearbeiten (Seitenformular) / anlegen / Mehrfach-Auswahl | FEHLT | |

### Notes (Notizen)

| Nr. | Funktion | Stand | Anmerkung |
|---|---|---|---|
| 28 | Notizen-Bereich (Notizen zu Kontakten festhalten) | FEHLT | Im Mitschnitt nicht erfasst; Umfang nur aus dem Menüpunkt bekannt |

### Email Campaign (Kampagnen)

| Nr. | Funktion | Stand | Anmerkung |
|---|---|---|---|
| 29 | Kampagnen-Übersicht mit Zahlen-Kacheln (gesamt, aktiv, Leads, geöffnet, versendet, Antworten) | HABEN WIR | Übersicht mit Kampagnen, aktiv, Empfänger, geöffnet, versendet, Antworten und unzustellbar; „fehlgeschlagen" bleibt ehrlich „—", weil Instantly keinen verlässlichen Zähler liefert |
| 30 | Kampagne im Tool anlegen | HABEN WIR | Bei uns: „Anschreiben erstellen lassen" (Kunde wählen, Anzahl, los) |
| 31 | Kampagne scharf schalten / pausieren | HABEN WIR | Baustein 1 |
| 32 | Kampagnen-Detail mit Kacheln: Leads, Mails gesamt, versendet, geöffnet, Antworten, fehlgeschlagen, unzustellbar | TEILWEISE | Alle belegten Zahlen sind sichtbar; „fehlgeschlagen" bleibt „—", weil Instantly dafür keinen verlässlichen Zähler liefert |
| 33 | Erstellungs-Fortschritt (Balken: wie viele Anschreiben fertig erzeugt) | HABEN WIR | Unsere Auftrags-Fortschrittsseite |
| 34 | Warteschlangen-Status (Kreis-Diagramm: versendet, wartend, geplant, fehlgeschlagen, unzustellbar, abgebrochen, übersprungen, pausiert) | TEILWEISE | Ring zeigt nur die belegten Gruppen „versendet" und „unzustellbar"; alles andere wird ehrlich als nicht getrennt verfügbar zusammengefasst |
| 35 | Aufschlüsselung je Schritt (Schritt 1–3: x von y versendet) | HABEN WIR | |
| 36 | Tages-Limit und Sendefenster anzeigen („heute 7 von 20", Wochentage, Uhrzeit, Zeitzone, „gerade im Sendefenster") | HABEN WIR | Verbrauch der verwendeten Absender, bekannte Limits und Instantly-Sendefenster werden angezeigt |
| 37 | Kampagnen-Einstellungen im Tool ändern (Mails pro Tag, Signatur, BCC, automatisches Weiterlaufen, automatische Antworten, Start-Zeitplan) | NICHT IM SCOPE | Einstellungen bleiben beim Link nach Instantly; dies ist die Scope-Entscheidung vom 22.07.2026 |

### Email Sequence (Freigabe-Tabelle je Empfänger)

| Nr. | Funktion | Stand | Anmerkung |
|---|---|---|---|
| 38 | Texte je Empfänger lesen und freigeben (Betreff + Text für Anschreiben und Nachfässe) | HABEN WIR | Bei uns sogar strenger: Checkliste vor der Freigabe |
| 39 | Große Status-Tabelle je Empfänger UND je Schritt: Freigabe-Status, Versand-Status, versendet am, Antwort erhalten am, Fehler — für Schritt 1, 2, 3 einzeln | HABEN WIR | Freigabe, Versandzeit und belegbare Antworten werden je Schritt gezeigt. Was Instantly nicht eindeutig einem Schritt zuordnet, bleibt unbekannt |
| 40 | Einzelnen Text im Tool bearbeiten (Stift-Symbol) | HABEN WIR | Im vereinbarten schlanken Umfang: genau einen Schritt neu erzeugen lassen; dadurch wird nur dessen alte Freigabe ungültig |
| 41 | Suche, Filter und Mehrfach-Auswahl in der Freigabe-Tabelle | HABEN WIR | Suche, Statusfilter und Sammelfreigabe arbeiten immer nur innerhalb einer E-Mail-Runde |

### Domain Blacklist (Gesperrte Domains)

| Nr. | Funktion | Stand | Anmerkung |
|---|---|---|---|
| 42 | Gesperrte Domains anzeigen, hinzufügen, entfernen | HABEN WIR | |
| 43 | Zusatzfelder je Sperre (Webseite, Grund, Kommentar) und Platzhalter-Sperren wie `*.bund.de` | HABEN WIR | Alte einfache Einträge bleiben lesbar; neue Einträge werden geprüft und zuverlässig gespeichert |

### Zwischenstand

| Stand | Anzahl |
|---|---|
| HABEN WIR | 14 |
| TEILWEISE | 7 |
| FEHLT | 21 |
| NICHT IM SCOPE | 1 |
| **Gesamt** | **43** |

Kurz gesagt: Kampagnen, Freigabe und Sperrliste — also der Kern, mit dem das
Team heute arbeitet — sind bei uns schon gut abgedeckt, teils strenger als bei
Wholix. Es fehlen noch die vereinbarte Antwortfunktion im schlanken
Instantly-Postfach und das **CRM** mit Kontaktbearbeitung, Verkaufs-Stufen
und Kartenansicht. Die übrigen Wholix-Bereiche sind laut Scope-Entscheidung
bewusst gestrichen.

---

## 2. Architektur-Entscheidung für den Mail-Bereich

Die frühere Frage zwischen direkter Postfach-Anbindung und einem vollständigen
Ersatz von Instantly ist am 23.07.2026 entschieden worden: **Beides wird nicht
gebaut.**

Instantly bleibt der einzige Mail-Zugang und der unsichtbare Versand-Motor.
Unser Tool liest daraus ausschließlich Kampagnenverläufe und darf über den
offiziellen Instantly-Endpunkt auf eine bestehende empfangene Mail antworten.
Damit kann das Team die tägliche Antwortarbeit im eigenen Werkzeug erledigen,
ohne dass wir Gmail-/Microsoft-Zugänge speichern oder eine zweite Mailtechnik
betreiben.

Die Grenze bleibt bewusst sichtbar: Ordner, Entwürfe, Junk, beliebige alte
Mails, freie neue Mails und Postfach-Suche gehören nicht zum System. Der
verbindliche Entwurf für die einzige neue Schreibfunktion steht in
`docs/superpowers/specs/2026-07-23-instantly-antworten-design.md`.

---

## 3. Nachbau-Fahrplan

Die fehlenden und halben Punkte, in sinnvoller Baureihenfolge. Größen:
**S** = wenige Tage, **M** = etwa eine Woche, **L** = mehrere Wochen.

### Phase 1 — Kampagnen-Ansicht auf Wholix-Stand

**Stand 22.07.2026:** Der Funktionsumfang dieser Phase ist gebaut und mit
rein lokalen Testdaten geprüft. Der frische volle Testlauf ergab 461 grüne
Tests und eine bekannte Abkündigungswarnung aus Starlette/TestClient.
Die Desktop- und 390-px-Ansichten von Übersicht und Detail sind sichtbar
geprüft. Bei 390 px liegt die Navigation oben, der Inhalt nutzt die volle
Breite, der Dokumentkörper hat keinen horizontalen Überlauf und nur die
Kampagnentabelle scrollt intern. Keine echte Kampagne, kein Postfach und
keine Instantly-Schreibschnittstelle wurden für die Prüfung benutzt.
Empfängerzahlen stammen in der Anzeige aus Instantly; die Zahl des zuletzt
freigegebenen Laufs bleibt im Detail getrennt erkennbar. Der heutige Versand
wird über die tägliche Konten-Auswertung nur für die verwendeten
Absenderpostfächer summiert. Die Absender werden dabei als Pflichtfilter
übergeben; der angefragte Zeitraum läuft von heute bis zum Folgetag. Fällt
allein diese Auswertung aus, bleiben die anderen Live-Werte sichtbar. Ein
zuletzt bekannter Postfachstand bleibt bei einem späteren Lesefehler ebenfalls
sichtbar und wird klar als solcher gekennzeichnet. Sobald auch nur ein
Kampagnenstatus unbekannt ist, bleibt die zusammengefasste Aktiv-Zahl ebenfalls
unbekannt.

| Baustein | Größe | Was es heißt |
|---|---|---|
| Kacheln „geöffnet / fehlgeschlagen / unzustellbar" in Übersicht und Detail (Nr. 29, 32) | S | **Gebaut.** Belegte Instantly-Zahlen werden angezeigt; „fehlgeschlagen" bleibt bei fehlender verlässlicher Quelle „—" |
| Tages-Limit + Sendefenster anzeigen (Nr. 36) | S | **Gebaut.** Zeigt „Heute x von y", Wochentage, Uhrzeit, Zeitzone und ob das Fenster gerade offen ist; Sendefenster über Mitternacht werden richtig erkannt |
| Warteschlangen-Status als Diagramm (Nr. 34) | M | **Gebaut im belegbaren Umfang.** Der Ring teilt mögliche E-Mails nur in „versendet" und „nicht getrennt verfügbar". „Unzustellbar" steht getrennt darunter, weil diese Instantly-Zahl sich mit „versendet" überschneiden kann |
| Kampagnen-Einstellungen im Tool ändern (Nr. 37) | — | **Nicht bauen.** Einstellungen bleiben beim Link nach Instantly (Scope-Entscheidung vom 22.07.2026) |

### Phase 2 — Freigabe-Tabelle auf Wholix-Stand

**Stand 22.07.2026:** Der Funktionsumfang dieser Phase ist gebaut und mit
festen lokalen Testdaten geprüft. 518 Tests sind grün. Die Gesamtheit wurde
in sieben frischen Testblöcken ausgeführt; einen einzelnen, durchlaufenden
Testprozess beendete das System wiederholt ohne Testfehler und ohne
Abschlussmeldung. Die einzige Warnung ist weiterhin die bekannte
Starlette-Abkündigung im TestClient.

Die Freigabe speichert jeden Empfänger und jeden der drei E-Mail-Schritte
einzeln. Sammelaktionen gelten nur für die gerade geöffnete Runde. Die
Übergabe bleibt gesperrt, solange auch nur ein Schritt offen, nach einer
Neuerzeugung veraltet oder in Nacharbeit ist. Nach der Übergabe ist die
Ansicht schreibgeschützt. Instantly wird für Versand- und Antwortstände nur
lesend abgefragt. Eine Antwort wird nur dann einem einzelnen Schritt
zugeordnet, wenn der Verlauf das eindeutig belegt; sonst bleibt der
Schrittwert unbekannt und nur der belegbare Gesamtstand wird gezeigt.

Die globale Sperrliste speichert Domain, Grund und Kommentar, versteht
Platzhalter wie `*.bund.de`, erkennt Überschneidungen und liest alte einfache
Einträge weiter. Desktop und 390-px-Ansichten von Freigabe und Sperrliste
sind sichtbar geprüft. Bei 390 px liegt die Navigation oben, der
Dokumentkörper hat keinen horizontalen Überlauf und nur die breiten Tabellen
scrollen innerhalb ihres Bereichs. Für diesen Nachweis wurde keine echte
E-Mail versendet und keine Instantly-Schreibschnittstelle benutzt.

| Baustein | Größe | Was es heißt |
|---|---|---|
| Status-Tabelle je Empfänger und Schritt (Nr. 39) | M | **Gebaut.** Freigabe und belegbare Instantly-Stände stehen je Empfänger und Schritt getrennt; unbekannte Werte bleiben sichtbar unbekannt |
| Einzelnen Text bearbeiten (Nr. 40) | S | **Gebaut im vereinbarten Umfang.** Genau einen Schritt neu erzeugen lassen; nur dessen alte Freigabe wird ungültig |
| Suche, Filter, Mehrfach-Auswahl (Nr. 41) | S | **Gebaut.** Suche, Statusfilter und Sammelaktionen bleiben auf eine Runde begrenzt |
| Sperrliste: Grund/Kommentar-Felder + Platzhalter-Sperren (Nr. 43) | S | **Gebaut.** Einschließlich Bearbeiten, Entfernen, Überschneidungsprüfung und alten Einträgen |

### Phase 3 — Schlankes Instantly-Postfach

**Stand 23.07.2026:** Der vorhandene Instantly-Postfachbereich wurde mit
genau einer Testmail und einer Testantwort end-to-end bewiesen. Gmail war
dabei nur das Testziel und wurde nicht an das Tool angebunden. Versand,
Antwortabruf und die sichtbare Konversation liefen über Instantly; die
Testkampagne ist pausiert. Phase 3 ist nun verbindlich verkleinert: Der
vorhandene Verlauf bleibt und erhält als einzige neue Schreibfunktion das
Antworten auf eine bestehende empfangene Instantly-Mail. Die direkte
Google-/Microsoft-Anbindung und das vollständige Mailprogramm entfallen.

| Baustein | Größe | Was es heißt |
|---|---|---|
| Kampagnenverläufe zusammenführen und lesen (Nr. 14–16) | S | **Gebaut und live bewiesen.** Alle sichtbaren Instantly-Kampagnengespräche stehen chronologisch im eigenen Postfach |
| Auf eine bestehende empfangene Mail antworten (Teil von Nr. 17) | S | **Gebaut und live bewiesen.** Eine kontrollierte Antwort aus dem internen Postfach wurde von Instantly bestätigt, im Verlauf angezeigt und an das eigene Gmail-Testkonto zugestellt. Der Versand nutzt eine signierte Kurzfreigabe, atomaren Einmalverbrauch und keine automatische Wiederholung bei unklarem Ausgang |
| Verbindungsprobleme sichtbar machen (Teil von Nr. 22, 24) | S | **Gebaut.** Status und Warnung kommen aus Instantly; Reparatur bleibt über den Link nach Instantly |
| Vollständiges Mailprogramm (Nr. 13, 18–23 und übrige Teile von 14, 15, 17, 24) | — | **Nicht im Scope.** Keine direkte Gmail-/Microsoft-Verbindung, keine Ordner, freien Mails, Suche, Markierungen, Signaturen oder eigene Reparatur |

### Phase 4 — CRM-Ausbau

| Baustein | Größe | Was es heißt |
|---|---|---|
| Leads-Tabelle: mehr Spalten, bearbeiten, anlegen (Nr. 26, 27) | M | Aus unserer Lese-Tabelle eine echte Arbeits-Tabelle machen |
| Kontakte mit Pipelines und Stufen + Karten-Ansicht (Nr. 10, 11, 12) | L | New Lead → Demo → … → Won/Lost, eigene Pipelines, Karten verschieben |

### Reihenfolge-Logik, kurz

Phase 1 und 2 machen die Bereiche fertig, in denen das Team heute schon
arbeitet — schnellster sichtbarer Fortschritt, kein Risiko. Phase 3 ergänzt
nur noch die klar begrenzte Instantly-Antwortfunktion. Danach folgt Phase 4:
Kontakte bearbeiten und zuverlässig durch Verkaufs-Stufen führen. Weitere
Wholix-Bereiche werden nicht gebaut, solange die Scope-Entscheidungen oben
nicht ausdrücklich geändert werden.
