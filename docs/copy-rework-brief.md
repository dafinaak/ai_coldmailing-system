# Copy-Überarbeitung: Auftrag (freigegeben von Leonard, 20.07.2026)

Ziel: Oberfläche für **komplette Anfänger** verständlich. Mittlere
Erklär-Menge auf dem Bildschirm, aber MEHR Erklärung auf dem
Freigabe-Bildschirm (dort werden echte E-Mails ausgelöst). Fachwörter
raus, Alltagssprache, Anrede "du". Neue kurze Einstiegsseite beim ersten
Login.

## Verbindliches Wörterbuch (überall anwenden)

| Alt | Neu |
|---|---|
| Auftrag / Anschreiben-Auftrag | **E-Mail-Runde** ("Ein Schwung fertiger E-Mails für einen Kunden") |
| Knopf "Anschreiben erstellen lassen" | **"E-Mails schreiben lassen"** |
| Karten-Titel "34 Anschreiben für X" | **"E-Mail-Runde für X · 34 Empfänger"** |
| Anschreiben (die einzelne Mail) | **E-Mail** (erste = "erste E-Mail", dann "Nachfass-Mail 1 / 2") |
| Bereich/Nav "Prüfen & Freigeben" | **"Lesen & Freigeben"** |
| freigeben / Freigabe | bleibt "freigeben", ABER überall erklärt: *dein grünes Licht, dass die E-Mails verschickt werden dürfen* |
| aussortiert (Überschrift) | **"durchgefallen – geht nicht raus"** |
| Prüfung / Prüf-KI / "KI-Prüfer:" | **"automatische Qualitätskontrolle" / "Qualitätskontrolle:"** |
| "wartet auf Prüfung" | **"wartet darauf, dass du sie liest"** |
| Kampagne (erste Nennung je Seite) | **"Kampagne (in Instantly)"** |

Unverändert (schon klar genug): Dashboard, Kunden, Kontakte, Postfach,
Gesperrte Domains, Empfänger, Zielgruppe.

## Neue Einstiegsseite "So funktioniert's"

Beim ersten Login automatisch zeigen (pro Nutzer per Cookie
"intro_gesehen" – einmal wegklickbar), danach jederzeit über einen
Seitenleisten-Eintrag "So funktioniert's" wieder erreichbar. Text:

> **So funktioniert Poleposition**
>
> Dieses Werkzeug schreibt für dich Kalt-E-Mails an mögliche neue
> Kunden — für jeden Empfänger einzeln, passend zu seiner Firma.
>
> 1. **Kunde anlegen:** Für wen und mit welchem Angebot geschrieben
>    werden soll.
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

## Freigabe-Bildschirm: eine Zeile mehr Erklärung

Direkt unter der Überschrift, gut sichtbar:

> **Was heißt freigeben?** Dein grünes Licht, dass diese E-Mails
> verschickt werden dürfen. Sie gehen dann — noch pausiert — an
> Instantly; scharf geschaltet werden sie dort von Hand. Ohne deine
> Freigabe passiert nichts.

## Wichtig (nicht vergessen)

- Der Text "KI-Prüfer: <Urteil>" kommt aus pipeline/quality.py (steht
  in nacharbeit-Gründen). Dort auf "Qualitätskontrolle: <Urteil>" ändern
  UND zugehörige Tests/Matcher mitziehen.
- Alle betroffenen Tests (pytest.raises(match=...), Substring-Asserts,
  Template-Asserts) im Gleichschritt anpassen — Suite muss grün bleiben.
- Text-Leitfaden docs/text-leitfaden-interface.md ist die Quelle der
  Wahrheit: dort das Wörterbuch + die neuen Texte eintragen, damit
  spätere Arbeit konsistent bleibt.
