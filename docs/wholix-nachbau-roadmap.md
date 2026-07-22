# Wholix-Nachbau: Feature-Inventur und Fahrplan

Stand: 22.07.2026 (Phase 1 gebaut und lokal geprüft; siehe Abschnitt 3)

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

Bleibt voll im Scope (Aussehen wie Wholix): alles Übrige, inklusive dem
CRM mit Verkaufs-Stufen (11, 12) und dem vollen Mail-Programm (13–24, über
Weg A — siehe Abschnitt 2). Von 43 Funktionen sind damit 9 gestrichen,
34 bleiben.

---


**Auftrag:** Unser Tool soll eine vollständige Kopie von Wholix werden — gleiche
Bereiche, gleiche Funktionen. Dieses Dokument listet ALLES auf, was Wholix kann,
markiert bei jedem Punkt, wie weit wir schon sind, und macht daraus einen
Baufahrplan. Die Grundsatz-Entscheidung (Kopie ja) steht fest und wird hier
nicht neu aufgemacht.

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
| 39 | Große Status-Tabelle je Empfänger UND je Schritt: Freigabe-Status, Versand-Status, versendet am, Antwort erhalten am, Fehler — für Schritt 1, 2, 3 einzeln | TEILWEISE | Freigeben ja; den Versand- und Antwort-Status je Empfänger und Schritt zeigen wir nicht |
| 40 | Einzelnen Text im Tool bearbeiten (Stift-Symbol) | FEHLT | Bei uns: neu erstellen lassen statt von Hand ändern |
| 41 | Suche, Filter und Mehrfach-Auswahl in der Freigabe-Tabelle | FEHLT | |

### Domain Blacklist (Gesperrte Domains)

| Nr. | Funktion | Stand | Anmerkung |
|---|---|---|---|
| 42 | Gesperrte Domains anzeigen, hinzufügen, entfernen | HABEN WIR | |
| 43 | Zusatzfelder je Sperre (Webseite, Grund, Kommentar) und Platzhalter-Sperren wie `*.bund.de` | FEHLT | |

### Zwischenstand

| Stand | Anzahl |
|---|---|
| HABEN WIR | 10 |
| TEILWEISE | 8 |
| FEHLT | 24 |
| NICHT IM SCOPE | 1 |
| **Gesamt** | **43** |

Kurz gesagt: Kampagnen, Freigabe und Sperrliste — also der Kern, mit dem das
Team heute arbeitet — sind bei uns schon gut abgedeckt, teils strenger als bei
Wholix. Was großflächig fehlt, sind drei Blöcke: das eingebaute
**Mail-Programm** (Nr. 13–24), das **CRM drumherum** (Kontakte mit Stufen,
Leads bearbeiten, Notizen, Anrufe, AI-Chat) und der **Rahmen** (Arbeitsbereiche,
Benutzerverwaltung).

---

## 2. Die eine große Architektur-Frage

Bevor der Fahrplan losgehen kann, braucht es eine Entscheidung. Hier ist sie,
so einfach wie möglich erklärt.

**Was der Netzwerk-Mitschnitt zeigt:** Wholix ist im E-Mail-Bereich ein
echtes, eigenes Mail-Programm. Es meldet sich mit einer Google-/
Microsoft-Anmeldung direkt am Postfach an, lädt alle Ordner und alle Mails auf
den eigenen Server und zeigt sie von dort an. Deshalb kann Wholix Entwürfe,
Junk, Papierkorb, Suche, Markierungen und „neue Mail schreiben" — es sieht
das komplette Postfach, nicht nur den Kampagnen-Verkehr.

**Wie unser Tool heute arbeitet:** Wir lesen über Instantly. Instantly zeigt
uns aber nur, was mit Kampagnen zu tun hat — versendete Kampagnen-Mails und
eingegangene Antworten darauf. Ordner, Entwürfe, Junk, beliebige alte Mails:
davon weiß Instantly nichts. **Ein 1:1-Nachbau des Wholix-Postfachs ist über
Instantly allein nicht möglich.** Wir müssen uns, wie Wholix, direkt mit den
Postfächern verbinden.

Damit gibt es zwei Wege:

**Weg A — Mischbetrieb (direkt lesen, Instantly sendet weiter):**
Wir verbinden dieselben Postfächer zusätzlich direkt mit unserem Tool (die
Google-/Microsoft-Anmeldung, die man einmal pro Postfach durchklickt). Das
Tool liest dann das komplette Postfach und kann auch antworten, weiterleiten
und neue Mails schreiben. Der Kampagnen-Versand samt Anwärmen bleibt bei
Instantly — das läuft, ist bezahlt, und das Anwärmen selbst nachzubauen wäre
ein eigenes Großprojekt. Beides verträgt sich: ein Postfach kann gleichzeitig
mit Instantly und mit unserem Tool verbunden sein.

**Weg B — alles direkt (Instantly ganz ersetzen):**
Wir bauen zusätzlich den Versand selbst: Warteschlange, Tages-Limits,
Sendefenster, Anwärmen, Zustellbarkeits-Pflege. Das ist genau der Teil, bei
dem man am meisten kaputt machen kann (Postfach-Ruf, Spam-Ordner), und er
ersetzt etwas, das heute funktioniert und bezahlt ist. Wholix selbst macht
zwar alles in einem Haus — aber wir müssen das nicht am ersten Tag, um für
das Team 1:1 auszusehen und sich 1:1 zu bedienen.

**Meine Empfehlung: Weg A.** Damit erreichen wir die volle Wholix-Oberfläche
(inklusive komplettem Postfach) und behalten den erprobten Versandmotor.
Weg B bleibt später möglich, ohne dass etwas aus Weg A weggeworfen wird —
das direkte Postfach-Lesen braucht man in beiden Fällen.

**Die Frage an dich, in einem Satz:** Sollen wir die Postfächer direkt mit
unserem Tool verbinden, damit das volle Mail-Programm nachgebaut werden kann,
während Instantly weiter den Kampagnen-Versand und das Anwärmen macht (Weg A) —
oder sollen wir auch den Versand selbst bauen und Instantly ganz ablösen
(Weg B)?

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

| Baustein | Größe | Was es heißt |
|---|---|---|
| Status-Tabelle je Empfänger und Schritt (Nr. 39) | M | Zu jedem Empfänger anzeigen: freigegeben? versendet am? Antwort erhalten? Fehler? — je Schritt 1–3 |
| Einzelnen Text bearbeiten (Nr. 40) | S | Stift-Symbol; Änderung macht die alte Freigabe ungültig (unsere Regel bleibt) |
| Suche, Filter, Mehrfach-Auswahl (Nr. 41) | S | |
| Sperrliste: Grund/Kommentar-Felder + Platzhalter-Sperren (Nr. 43) | S | |

### Phase 3 — Das Mail-Programm (der größte Brocken; braucht die Entscheidung aus Abschnitt 2)

| Baustein | Größe | Was es heißt |
|---|---|---|
| Postfächer direkt verbinden (Google-/Microsoft-Anmeldung) + Status (Nr. 22) | M | Einmal pro Postfach durchklicken; Tool merkt sich den Zugang und zeigt, ob er noch gültig ist |
| Ordner + Mails abgleichen und speichern (Nr. 13, 23) | L | Das Herzstück: alle Ordner und Mails vom Postfach auf unseren Server laden, laufend aktuell halten |
| Mail-Liste + Konversations-Ansicht + Suche + Markierungen (Nr. 15, 19, 20) | M | Die eigentliche Posteingangs-Ansicht wie bei Wholix |
| Antworten / Weiterleiten / Verfassen + Signaturen (Nr. 17, 18, 21) | M | Erst mit Test-Postfach und Test-Empfängern beweisen, dann echt |
| Einheits-Posteingang + Postfach-Wechsel (Nr. 14) | S | Alle Postfächer zusammen oder einzeln |
| „Neu verbinden"-Knopf bei Postfach-Problemen (Nr. 24) | S | |

### Phase 4 — CRM-Ausbau

| Baustein | Größe | Was es heißt |
|---|---|---|
| Leads-Tabelle: mehr Spalten, bearbeiten, anlegen (Nr. 26, 27) | M | Aus unserer Lese-Tabelle eine echte Arbeits-Tabelle machen |
| Kontakte mit Pipelines und Stufen + Karten-Ansicht (Nr. 10, 11, 12) | L | New Lead → Demo → … → Won/Lost, eigene Pipelines, Karten verschieben |
| Notizen (Nr. 28) | S | |
| Anrufe (Nr. 25) | M | Umfang bei Wholix unklar (im Mitschnitt nicht erfasst) — vor dem Bau kurz im Wholix-Konto ansehen |

### Phase 5 — Rahmen und Extras

| Baustein | Größe | Was es heißt |
|---|---|---|
| Benutzerverwaltung mit Einladungen (Nr. 3) | M | Eigene Zugänge je Kollege — auch Voraussetzung für „wer hat was freigegeben" mit echten Namen |
| Zwei-Faktor-Anmeldung (Nr. 4) | S | |
| Arbeitsbereiche (Nr. 2) | M | Mehrere getrennte Bereiche (z.B. je Kunde) in einem Konto |
| Dunkel-Ansicht, Benachrichtigungs-Glocke, Hilfe-Knopf (Nr. 5, 6, 7) | S | |
| AI-Chat (Nr. 8) | L | Mit der KI über Kontakte/Kampagnen reden; Umfang bei Wholix vorher im Konto ansehen |

### Reihenfolge-Logik, kurz

Phase 1 und 2 machen die Bereiche fertig, in denen das Team heute schon
arbeitet — schnellster sichtbarer Fortschritt, kein Risiko. Phase 3 ist der
größte und wichtigste Brocken (das halbe Wholix hängt am Mail-Programm) und
startet, sobald die Frage aus Abschnitt 2 entschieden ist. Phase 4 und 5
machen die Kopie komplett. Bei Anrufen, Notizen und AI-Chat lohnt vor dem Bau
ein kurzer Blick ins laufende Wholix-Konto (und ein zweiter
Netzwerk-Mitschnitt dieser Bereiche), weil der vorhandene Mitschnitt sie
nicht abdeckt.
