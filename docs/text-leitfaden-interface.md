# Text-Leitfaden für das Team-Interface (verbindliche Texte)

Stand: 20.07.2026 (Copy-Überarbeitung für komplette Anfänger, siehe
docs/copy-rework-brief.md — der Auftrag von Leonard, freigegeben
20.07.2026). Dieser Leitfaden ist die eine Wahrheit für alle Texte
in der Oberfläche. Das Design-Tool und später der Bau übernehmen diese
Texte wörtlich — sie erfinden keine eigenen.

## Copy-Überarbeitung 20.07.2026 — was sich geändert hat

Ziel: Oberfläche für komplette Anfänger verständlich, Anrede "du". Das
Wörterbuch unten (Abschnitt "Wörterbuch: alt → neu") ist entsprechend
aktualisiert; die wichtigsten Änderungen gegenüber dem Stand vom
17.07.2026:

| Alt | Neu |
|---|---|
| Auftrag / Anschreiben-Auftrag | **E-Mail-Runde** ("Ein Schwung fertiger E-Mails für einen Kunden") |
| Knopf "Anschreiben erstellen lassen" | **"E-Mails schreiben lassen"** (kurz auf kleinen Knöpfen: "Schreiben lassen") |
| Karten-Titel "34 Anschreiben für X" | **"E-Mail-Runde für X · 34 Empfänger"** |
| Anschreiben (die einzelne Mail) | **E-Mail** (erste = "erste E-Mail", dann "Nachfass-Mail 1 / 2") |
| Bereich/Nav "Prüfen & Freigeben" | **"Lesen & Freigeben"** |
| freigeben / Freigabe | bleibt "freigeben", ABER überall erklärt: *dein grünes Licht, dass die E-Mails verschickt werden dürfen* — auf dem Freigabe-Bildschirm steht das jetzt gut sichtbar direkt unter der Überschrift (siehe unten) |
| aussortiert (Überschrift) | **"durchgefallen – geht nicht raus"** |
| Prüfung / Prüf-KI / "KI-Prüfer:" | **"automatische Qualitätskontrolle" / "Qualitätskontrolle:"** (pipeline/quality.py) |
| "wartet auf Prüfung" | **"wartet darauf, dass du sie liest"** |
| Kampagne (erste Nennung je Seite) | **"Kampagne (in Instantly)"** |

Neu: eine Einstiegsseite "So funktioniert's" (Route `/so-funktionierts`),
die beim ersten Login automatisch gezeigt wird (Cookie `intro_gesehen`,
einmal wegklickbar, danach jederzeit über die Seitenleiste erreichbar) —
Wortlaut siehe Abschnitt "Einstiegsseite" unten.

## Umbenennung 20.07.2026 — "Kunde" heißt jetzt "Angebot"

Das Werkzeug wird intern genutzt (nicht für externe Kunden) — jeder
Eintrag ist ein internes Anschreib-Setup (Angebot + Zielgruppe +
Tonalität + Absender + Sperrliste + Test-Adressen), nicht ein externer
Kunde. Deshalb heißt der Bereich jetzt überall in der Oberfläche
"Angebot" / "Angebote" statt "Kunde" / "Kunden" (Nav-Label, Überschriften,
Knöpfe, Hilfstexte, Fehlermeldungen). Es bleibt eine Liste — das Team
pflegt mehrere Angebote gleichzeitig.

Namens-Kollision: Ein Eintrag hatte schon ein inneres Feld "Angebot"
(der Angebotstext selbst). Weil der ganze Eintrag jetzt "Angebot" heißt,
bekommt dieses innere Feld das Label **"Angebotstext"** (Hilfssatz bleibt
sinngemäß gleich, nur "der Kunde" wird zu "ihr/euer").

## Das Grundprinzip

**Wir benennen Dinge nach dem, was der Nutzer sieht und tut — nicht
nach dem, was das System innen macht.** Daraus folgen drei Regeln:

1. **Verben auf Knöpfen.** Nicht "Neuer Lauf", sondern "E-Mails
   schreiben lassen". Ein Knopf sagt, was passiert, wenn man drückt.
2. **Kein Wort ohne Bild im Kopf.** Begriffe wie "Lauf" oder
   "Nacharbeit" sind Systemdenken. Der Nutzer kennt: E-Mails,
   Entwürfe, lesen, freigeben, versenden. Nur damit arbeiten wir.
3. **Jede Ansicht beginnt mit einem Satz, der sagt, was sie ist und
   was hier meine Aufgabe ist.** Wer irgendwo hineinspringt, liest
   einen Satz und weiß Bescheid.

## Wörterbuch: alt → neu

Stand 20.07.2026 — ersetzt die Karten-/Knopf-Wortwahl vom 17.07.2026 (siehe
Tabelle oben unter "Copy-Überarbeitung 20.07.2026"). Zusammengeführt in
einer Tabelle:

| Bisher | Verbindlich ab jetzt | Anmerkung |
|---|---|---|
| Lauf / Auftrag / Anschreiben-Auftrag | **"E-Mail-Runde"** — die Karte heißt "E-Mail-Runde für [Name] · [N] Empfänger", z.B. "E-Mail-Runde für MOVEO Personalberatung · 34 Empfänger" | Das abstrakte Behälter-Wort verschwindet aus der Oberfläche. Sammelwort: "E-Mail-Runde" (nicht mehr "Auftrag"). [Name] ist der Name des Angebots. |
| Kunde / Kunden (Bereich) | **"Angebot" / "Angebote"** | Internes Werkzeug, keine externen Kunden — siehe Abschnitt "Umbenennung 20.07.2026" oben. Das innere Feld "Angebot" (Angebotstext) heißt jetzt "Angebotstext". |
| Lauf starten / "Anschreiben erstellen lassen" | **"E-Mails schreiben lassen"** (Kurzform auf kleinen Knöpfen: "Schreiben lassen") | Verb, Ergebnis klar. |
| Lauf fortsetzen | **"Weitermachen, wo es aufgehört hat"** (Kurzform auf kleinen Knöpfen: "Fortsetzen") | |
| Freigabe (Bereich) / "Prüfen & freigeben" | **"Lesen & Freigeben"** | "Freigabe" als Wort bleibt, aber die Aufgabe steht im Titel. Zusätzlich: eine erklärende Zeile "Was heißt freigeben?" direkt unter der Überschrift der Lese-Ansicht — dieser Bildschirm bekommt bewusst MEHR Erklärung als der Rest, weil hier echte E-Mails ausgelöst werden. |
| Sicherheits-Tor | Kein Etikett mehr — stattdessen der Satz: **"Ohne deine Freigabe wird nichts versendet."** | Die Metapher weg, die Aussage bleibt. |
| Freigabe verfallen | **"Die Texte wurden neu erstellt — bitte noch einmal lesen und freigeben."** | Sagt Ursache und Aufgabe in einem. |
| Nacharbeit / "von der Prüfung aussortiert" | **"durchgefallen – geht nicht raus"** | Mit einem Satz daneben: "Du kannst die Texte lesen und den Grund sehen." |
| Anschreiben (die einzelne Mail) | **"E-Mail"** — erste = "erste E-Mail", dann "Nachfass-Mail 1 / 2" | Nur der Sammelbegriff für den Auftrag wird "E-Mail-Runde"; die einzelne Nachricht bleibt "E-Mail". |
| "wartet auf Prüfung" | **"wartet darauf, dass du sie liest"** | |
| Prüfung / Prüf-KI / "KI-Prüfer: …" | **"automatische Qualitätskontrolle"** / **"Qualitätskontrolle: …"** (pipeline/quality.py) | Die menschliche Aufgabe heißt "lesen" (Lesen & Freigeben); "prüfen" bleibt nur für die automatische Qualitätskontrolle der KI. |
| Sperrliste | **"Gesperrte Domains"** + Hilfssatz: "An Firmen mit diesen Internet-Adressen wird nie geschrieben — z.B. eure eigene Firma." | |
| Test-Empfänger | **"Test-Adressen"** + Hilfssatz: "Solange der Test-Modus an ist, gehen Mails nur an diese Adressen — an niemanden sonst." | |
| Am Zug: du / Maschine | **"Jetzt bist du dran: …"** bzw. **"Das System arbeitet — du musst nichts tun."** | |
| Kampagne | **"Kampagne (in Instantly)"** — bei der ersten Nennung je Seite, danach reicht "Kampagne" | Das Wort kennt das Team aus Instantly; alleinstehend bleibt es vage. |

Unverändert (schon klar genug): Dashboard, Kontakte, Postfach,
Gesperrte Domains, Empfänger, Zielgruppe.

## Die vier Spalten des Boards

1. **"Wird vorbereitet"** — Untertitel: "Das System sucht Ansprechpartner und schreibt Entwürfe. Du musst nichts tun."
2. **"Bitte lesen und freigeben"** — Untertitel: "Das ist deine Aufgabe: Texte lesen, dann freigeben oder ablehnen."
3. **"Wird versendet"** — Untertitel: "Instantly verschickt die freigegebenen Mails nach Zeitplan."
4. **"Fertig"** — Untertitel: "Alles versendet. Hier nur noch zum Nachschauen."

Kopfzeile über dem Board: **"Hier siehst du alle E-Mail-Runden.
Sie wandern von links nach rechts. Alles in der zweiten Spalte wartet
auf dich."**

## Eine Karte (Beispiel)

> **E-Mail-Runde für MOVEO Personalberatung · 34 Empfänger**
> gestartet 16. Juli, 14:20 · von Lena
> [Zustandszeile, je nach Spalte:]
> – "Schreibt gerade Texte … (Firma 12 von 34)"
> – "Wartet seit 2 Std. darauf, dass du sie liest" → Knopf: **"Jetzt lesen"**
> – "8 von 34 Mails versendet · läuft seit gestern"
> – Bei Problem, unübersehbar: **"Angehalten: Die Firmen-Datenbank hat
>   nicht geantwortet. Nichts ist verloren."** → Knopf: "Fortsetzen"

## Die Arbeitsschritte in "Wird vorbereitet" (Laiensprache)

1. "Passende Firmen und Ansprechpartner suchen"
2. "E-Mail-Adressen herausfinden"
3. "Doppelte und gesperrte Empfänger aussortieren"
4. "Die Webseite jeder Firma lesen und eine persönliche E-Mail schreiben"
5. "Jeden Text prüfen: Klingt er persönlich? Stimmt alles?" (automatische Qualitätskontrolle)

## Die Lese-und-Freigabe-Ansicht

Kopfsatz: **"Lies die Texte, die gleich im Namen von [Absender]
verschickt werden. Erst wenn du freigibst, geht etwas raus."**

Direkt unter der Überschrift, gut sichtbar (dieser Bildschirm bekommt
bewusst mehr Erklärung als der Rest, weil hier echte E-Mails ausgelöst
werden): **"Was heißt freigeben?"** Dein grünes Licht, dass diese E-Mails
verschickt werden dürfen. Sie gehen dann — noch pausiert — an Instantly;
verschickt wird erst, wenn du die Kampagne mit »Jetzt verschicken«
startest (Baustein 1, siehe unten). Ohne deine Freigabe passiert nichts.

- Pro Empfänger sichtbar: Name, Firma, **E-Mail-Adresse**, dann:
  "Erste E-Mail (geht sofort raus)", "Nachfass-Mail 1 (nach X Tagen)",
  "Nachfass-Mail 2 (nach Y Tagen)".
- Durchgefallene Texte: **"[N] durchgefallen – geht nicht raus"** — Du
  kannst die Texte lesen und den Grund sehen.
- Freigeben-Bereich: "**Freigeben heißt:** Die Texte gehen als Kampagne
  — noch pausiert — an Instantly. Verschickt wird erst, wenn du die
  Kampagne mit »Jetzt verschicken« startest (auf der Kampagnen-Seite).
  Ohne deine Freigabe passiert nichts. Festgehalten wird: freigegeben
  von [Name] am [Datum]."
- Ablehnen: "**Ablehnen heißt:** Nichts wird versendet. Schreib kurz
  dazu, was nicht gepasst hat — das hilft bei der nächsten E-Mail-Runde."

## Kampagne im Tool starten und pausieren (Baustein 1, 20.07.2026)

Die Kampagnen-Detailseite bekommt zwei Knöpfe, wenn Instantly die Kampagne
noch pausiert zeigt bzw. gerade aktiv sendet. Beide sind bewusst KEIN
Ein-Klick-Knopf: erst klappt ein Kasten mit dem ehrlichen Satz auf, dann
bestätigt ein zweiter, eigener Knopf.

- Hinweis auf der Detailseite (statt des alten "... Gestartet wird dort
  von Hand — hier nur zum Nachschauen."): **"Diese Kampagne ist in
  Instantly angelegt, aber noch nicht gestartet."** Darunter: "Noch wurde
  nichts verschickt. Drück unten auf »Jetzt verschicken«, wenn es losgehen
  soll — bis dahin passiert nichts von allein." Der Link "Kampagne in
  Instantly öffnen ↗" bleibt als zweite, unaufdringliche Möglichkeit stehen.
- Knopf **"Jetzt verschicken"** (nur sichtbar, wenn unser Tool die Kampagne
  vollständig angelegt hat UND Instantly sie als pausiert/nicht gestartet
  meldet). Aufgeklappter Bestätigungssatz: **"Wenn du jetzt startest,
  verschickt Instantly die E-Mails dieser Kampagne nach Zeitplan.
  Fortfahren?"** Bestätigungsknopf: "Ja, jetzt verschicken".
- Knopf **"Versand pausieren"** (nur sichtbar, wenn Instantly die Kampagne
  gerade als aktiv meldet). Aufgeklappter Bestätigungssatz: **"Der Versand
  wird angehalten. Schon verschickte E-Mails bleiben unberührt."**
  Bestätigungsknopf: "Ja, pausieren".
- Nach dem Start: **"Gestartet von [Name] am [Datum]"** erscheint in der
  Kopfzeile der Detailseite, neben "Freigegeben von … am …".
- Scheitert der Instantly-Aufruf: **"Instantly hat gerade nicht
  geantwortet. Es ist nichts verloren gegangen — versuch es in ein paar
  Minuten noch einmal."**

## Einstiegsseite "So funktioniert's"

Route `/so-funktionierts`. Wird einem angemeldeten Nutzer beim allerersten
Aufruf von "/" automatisch gezeigt (kein Cookie `intro_gesehen` gesetzt),
danach jederzeit über den Seitenleisten-Eintrag "So funktioniert's"
erreichbar. Text (wörtlich):

> **So funktioniert Poleposition**
>
> Dieses Werkzeug schreibt für dich Kalt-E-Mails an mögliche neue
> Kunden — für jeden Empfänger einzeln, passend zu seiner Firma.
>
> 1. **Angebot anlegen:** Für wen geschrieben werden soll und was ihr
>    anbietet.
> 2. **E-Mail-Runde starten:** Das System sucht passende Firmen, liest
>    deren Webseiten und schreibt die E-Mails von allein.
> 3. **Lesen & freigeben:** Du liest die fertigen E-Mails und gibst dein
>    grünes Licht. Ohne dein Ja wird nichts verschickt.
> 4. **Verschicken:** Erst danach übergibt das System die E-Mails an
>    Instantly, das sie nach Zeitplan verschickt.
>
> Alles, was auf dich wartet, findest du auf dem Dashboard unter
> "Bitte lesen und freigeben".
>
> [Verstanden, los geht's]

## Fehlertexte (Muster)

Immer drei Teile: Was ist passiert (ohne Technik) · Was ist NICHT
passiert (Beruhigung) · Was du tun kannst.

> "Die Firmen-Datenbank hat gerade nicht geantwortet. Es ist nichts
> verloren gegangen — alle bisherigen Ergebnisse sind gespeichert.
> Versuch es in ein paar Minuten mit »Fortsetzen«."

## Angebot-Formular (jedes Feld mit Hilfssatz)

- Name — "So heißt das Angebot überall in diesem Werkzeug."
- Webseite der Firma — "Von hier kann das System das Angebot ableiten."
- Zielgruppe: Jobtitel / Region / Firmengröße — "Wen soll das System
  suchen? Beispiel: Geschäftsführer · Deutschland · 11–50 Mitarbeiter."
- Angebotstext — "Was bietet ihr an? In zwei, drei Sätzen — die KI
  nutzt das für jede Mail."
- Tonalität — "Wie sollen die Mails klingen? Beispiel: ruhig,
  erklärend, keine Superlative."
- Absendername — "Dieser Name steht unter jeder Mail."
- Gesperrte Domains — Hilfssatz siehe Wörterbuch.
- Test-Adressen — Hilfssatz siehe Wörterbuch.

## Anmeldung

- Login-Seite: "Melde dich an, um weiterzumachen." Felder: Name, Passwort.
- Fehlermeldung bei falschen Daten: "Name oder Passwort stimmt nicht."
- Abmelden-Link: "Abmelden".

## Prüffrage für jeden Text

Würde ein neuer Kollege ohne ein einziges erklärendes Gespräch
verstehen, (a) was dieses Ding ist, (b) was er jetzt tun soll,
(c) was passiert, wenn er drückt? Wenn nein: umschreiben.
