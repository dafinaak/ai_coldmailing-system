# Antworten im Instantly-Postfach – Entwurf

Stand: 23.07.2026  
Freigegeben von Mehreme am 23.07.2026

## Ziel

Das Team kann im vorhandenen internen Postfach auf eine eingegangene
Kampagnenantwort reagieren, ohne dafür in Instantly wechseln zu müssen.
Instantly bleibt der einzige Mail-Zugang und verschickt die Antwort über das
bereits dort verbundene Absenderpostfach.

Es wird kein Gmail- oder Microsoft-Konto mit unserem Tool verbunden. Unser
Tool erhält und speichert keine Google-/Microsoft-Zugangsdaten.

## Gewählter Weg

Wir erweitern das vorhandene Kampagnenpostfach um genau eine schreibende
Funktion: **auf eine bestehende empfangene Nachricht antworten**.

Instantly stellt dafür den offiziellen Endpunkt
`POST /api/v2/emails/reply` bereit. Er erwartet das bei Instantly verbundene
Absenderpostfach, die Kennung der Nachricht, auf die geantwortet wird, einen
Betreff und den Antworttext:

<https://developer.instantly.ai/api-reference/email/reply-to-an-email>

Dieser Weg ist für das Endziel sinnvoller als eine reine Leseansicht, weil das
Team den täglichen Antwortschritt im eigenen Werkzeug erledigen kann. Er ist
zuverlässiger und deutlich kleiner als ein eigenes vollständiges Mailprogramm,
weil Anmeldung, Zustellung und Mail-Verlauf bei Instantly bleiben.

## Bewusst nicht enthalten

- keine direkte Gmail-/Microsoft-Anmeldung
- kein vollständiger Posteingang mit Ordnern, Entwürfen, Junk oder Papierkorb
- keine neue Mail an eine frei eingegebene Adresse
- kein Weiterleiten, „Allen antworten“, Löschen oder Archivieren
- keine Signaturverwaltung im eigenen Tool
- keine automatische Antwort durch KI
- kein automatischer zweiter Versand nach einem Fehler oder Zeitablauf
- kein CRM-Ausbau in diesem Arbeitspaket

Der CRM-Ausbau ist das nächste eigene Arbeitspaket, sobald diese Antwortfunktion
gebaut und bewiesen ist.

## Bedienung

Die bestehende Postfachseite behält links die Gespräche und rechts den
chronologischen Verlauf.

Unter dem ausgewählten Verlauf erscheint ein Antwortbereich, wenn mindestens
eine empfangene Nachricht mit einer gültigen Instantly-Kennung und einem
bekannten Absenderpostfach vorhanden ist:

1. Ein mehrzeiliges Feld nimmt die Antwort als reinen Text auf.
2. Direkt darüber steht sichtbar, über welches Absenderpostfach gesendet wird.
3. Der Knopf heißt „Antwort endgültig senden“.
4. Ein leerer Text kann nicht versendet werden.
5. Nach erfolgreichem Versand öffnet sich derselbe Verlauf erneut und zeigt
   den klaren Hinweis „Antwort wurde über Instantly gesendet.“
6. Der bisherige Link „In Instantly öffnen“ bleibt als Ausweichweg erhalten.

Fehlen eine Nachrichtenkennung oder das verbundene Absenderpostfach, erscheint
kein funktionsloses Formular. Stattdessen erklärt die Seite, dass die Antwort
für diesen Verlauf nur in Instantly möglich ist.

## Datenfluss

### Lesen

`InstantlyLeser` lädt weiterhin die für unsere Kampagnen sichtbaren Mails.
Die reine Aufbereitung übernimmt zusätzlich folgende belegte Werte aus jedem
Instantly-Eintrag:

- `id`: Kennung der einzelnen Mail
- `eaccount`: das bei Instantly verbundene Absenderpostfach
- `campaign_id`: Kampagne für das gezielte Leeren des Lesecaches

Diese Werte werden nicht frei aus einem Formular übernommen. Die POST-Route
prüft anhand der frisch bekannten Konversation, dass die Zielkennung wirklich
zu einer empfangenen Mail des ausgewählten Kontakts gehört.

### Schreiben

Ein eigener kleiner Baustein `InstantlyAntworter` kapselt ausschließlich den
Antwort-Endpunkt. Seine öffentliche Funktion erhält:

- Absenderpostfach
- Kennung der empfangenen Nachricht
- Betreff
- Antworttext

Die Route erzeugt den Betreff aus der empfangenen Nachricht. Beginnt er noch
nicht mit `Re:`, wird `Re:` einmal vorangestellt. Der Nutzer kann den Betreff
in diesem ersten Umfang nicht verändern.

Nach einem bestätigten HTTP-Erfolg wird nur der betroffene Instantly-Mailcache
verworfen. Der anschließende Seitenaufruf liest den Verlauf frisch. Die
erfolgreiche API-Antwort gilt als Versandnachweis; die Oberfläche erfindet
keinen Erfolg bei einer leeren, fehlerhaften oder abgebrochenen Antwort.

## Schutz vor falschem oder doppeltem Versand

- Nur angemeldete Nutzer erreichen die POST-Route.
- Das GET-Formular enthält eine 15 Minuten gültige, signierte Freigabe für
  genau Kontakt, Zielnachricht und eine einmalige Zufallskennung. Die
  POST-Route prüft diese Signatur.
- Der Server prüft Kontakt, Nachrichtenkennung, Richtung und Absenderpostfach
  erneut gegen den gelesenen Instantly-Verlauf.
- Der Antworttext wird getrimmt, muss mindestens ein sichtbares Zeichen haben
  und darf höchstens 10.000 Zeichen lang sein.
- Unmittelbar vor dem Instantly-Aufruf wird die einmalige Zufallskennung unter
  `postfach-antworten/` im Datenverzeichnis atomar als benutzt gespeichert.
  Ein Doppelklick, erneutes Absenden oder ein zweiter App-Prozess kann dieselbe
  Freigabe dadurch nicht noch einmal verschicken. Eine verbrauchte Freigabe
  wird nie wieder freigeschaltet.
- Netzwerkfehler und Zeitüberschreitungen werden niemals automatisch
  wiederholt. Bei unklarem Ausgang steht auf der Seite, dass zuerst der
  Verlauf in Instantly geprüft werden muss. Dadurch wird keine möglicherweise
  bereits verschickte Antwort blind ein zweites Mal gesendet.
- API-Schlüssel, vollständige Anfrageinhalte und Antworttexte landen nicht in
  Fehlermeldungen oder Protokollen.

## Fehlerverhalten

Bei einem sicheren Fehler vor dem Versand bleibt der eingegebene Text sichtbar
und die Seite erklärt in Alltagssprache, was nicht geklappt hat.

Bei einem Netzwerkfehler während des Versands lautet der Hinweis:
„Der Versandstatus ist unklar. Bitte prüfe den Verlauf in Instantly, bevor du
erneut sendest.“ Es gibt in diesem Zustand keinen automatischen Neuversuch.

Antwortet Instantly mit einer klaren Ablehnung, zeigt die Seite:
„Instantly hat die Antwort nicht angenommen. Es wurde kein erfolgreicher
Versand bestätigt.“

## Technische Grenzen

Dieses Postfach bleibt ein Kampagnenpostfach. Es zeigt und beantwortet nur
Nachrichten, die Instantly in seiner Unibox kennt. Beliebige private oder alte
Mails eines Gmail-/Microsoft-Postfachs sind nicht Teil des Systems.

Mehrere Kampagnen desselben Kontakts werden weiterhin zu einem sichtbaren
Verlauf zusammengeführt. Geantwortet wird immer auf die jüngste empfangene
Nachricht, deren Instantly-Kennung und Absenderpostfach vollständig belegt
sind.

## Prüfung und sichtbarer Nachweis

Der Bau folgt dem bisherigen testgetriebenen Vorgehen:

1. Einheitstests prüfen den genauen Instantly-Endpunkt und die Nutzlast.
2. Routentests prüfen Anmeldung, Signatur, leere/zu lange Texte, manipulierte
   Zielkennungen, sicheren Fehlerzustand und erfolgreichen Umweg zurück zum
   Verlauf.
3. Lesertests prüfen, dass Kennung, Absenderpostfach und Kampagne zuverlässig
   bis zur Route erhalten bleiben.
4. Die vollständige Testsammlung muss grün sein.
5. Eine lokale Sichtprüfung mit festen Testdaten zeigt Antwortfeld,
   Absenderpostfach, Erfolg und Fehler auf breitem und schmalem Bildschirm.

Dabei wird keine echte Mail versendet. Ein späterer Live-Nachweis mit dem
eigenen Testpostfach braucht wegen seiner Wirkung außerhalb des Projekts eine
neue ausdrückliche Freigabe und wird wieder auf genau eine Antwort begrenzt.

## Erfolgskriterium

Das Arbeitspaket ist erst fertig, wenn ein angemeldeter Nutzer im lokalen
Testaufbau eine Antwort auf eine belegte empfangene Instantly-Mail absenden
kann, die Route genau einen korrekten Instantly-Aufruf ausführt, Erfolg und
Fehler ehrlich angezeigt werden und alle automatischen sowie sichtbaren
Prüfungen bestanden sind.
