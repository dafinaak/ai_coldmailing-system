# Bauplan: Versandstart IT-Dienstleister (Sequenz Oliver)

Stand: 2026-07-28 — Entwurf, wartet auf Freigabe
(Umgebaut am 2026-07-28: Anrede kommt jetzt als Schritt 5 nach dem
Datenlauf — Leonards Vorschlag, statt eigenem KI-Modul am Anfang.)

## Ziel und Erfolgskriterium

Die 3-Stufen-Sequenz von Oliver (docs/email-sequenz-it-dienstleister.md)
geht über Instantly an die Ansprechpartner der 319 IT-Dienstleister
(PLR 30-39) raus. Erfolg heißt:

- Jede versendete Adresse ist vorher geprüft (keine ungeprüften
  Adressen im Versand — Schutz der Postfach-Reputation).
- Jede Mail hat eine korrekte Anrede (Herr/Frau Nachname, oder neutrale
  Anrede wo unsicher).
- Die Kampagne startet erst nach Sichtung und Freigabe durch
  Leonard/Oliver.

## Schritte

Jeder Schritt ist einzeln prüfbar und nennt seinen Nachweis.

### Schritt 1: Hunter-Prüfung für info@-Adressen

Der Grosslauf lässt info@-Rückfall-Adressen bisher ungeprüft (gebaut,
als es noch kein Hunter-Konto gab). Jetzt wird die Hunter-Prüfung
angeschlossen. Feste Regel: Was ungeprüft bleibt oder als riskant
eingestuft wird, wird vom Versand ausgeschlossen und im Bericht als
ausgeschlossen gelistet.

**Nachweis:** Bestehende Test-Suite bleibt grün, plus neue Tests für
den Prüf-Schritt; Probelauf mit bekannten guten und schlechten
Test-Adressen.

### Schritt 2: Kampagne in Instantly bauen (bleibt Entwurf)

Die drei Sequenz-Texte einspielen, Wartezeiten setzen (Mail 2 nach
7 Tagen — steht so im Text; Mail 3 nach Olivers Vorgabe),
Absender-Postfächer verknüpfen, [TEST]-Vorsatz raus. Der alte Entwurf
"Partnerschafts-Anfrage_PPA" wird ersetzt. Die Kampagne bleibt
inaktiv — angelegt wird sie ohne einen einzigen Versand.

**GEÄNDERT (Leonards Entscheidung 2026-07-28): Weg B.** Die echten
Mail-Texte stehen sichtbar in den Instantly-Stufen; einzige
Einsetz-Marke ist {{anrede}} (wird pro Kontakt beim Lead-Upload
mitgeliefert). Gegenmaßnahmen zu den bekannten Weg-B-Risiken:

- Leere Anrede ("Guten Tag ,"): Der Lead-Upload weigert sich hart,
  einen Kontakt ohne gefüllte Anrede hochzuladen (Guard + Test).
  Die Anrede-Spalte wird vorher immer gefüllt, notfalls neutral.
- Zusammenbau erst im Versandmoment: Vor der Freigabe geht eine echte
  Testmail an ein eigenes Test-Postfach - wir prüfen das von
  Instantly zusammengesetzte Ergebnis, nicht nur unsere Vorschau.
- Versehentliche Text-Änderungen in Instantly: Vor der Aktivierung
  (und auf Wunsch jederzeit) wird der Kampagnentext gegen das
  Text-Dokument im Projekt verglichen; Abweichungen werden gemeldet.

**Nachweis:** Auszug der angelegten Kampagne (Stufen, Betreffs,
Wartezeiten, Absender, Status "Entwurf").

### Schritt 3: Probelauf klein (ca. 10 Firmen)

Der Datenlauf läuft zuerst über ~10 Firmen aus der Liste, damit wir
die Qualität sehen, bevor das große Guthaben verbraucht wird.

**Nachweis:** Der Bericht des Probelaufs (gefunden / geprüft /
ausgeschlossen, mit Beispielen).

### Schritt 4: Voller Datenlauf (319 Firmen)

Nach Okay zum Probelauf-Ergebnis läuft die komplette Liste durch.
Dauert wegen der Prüfschleifen mehrere Stunden; Wiederanlauf nach
Abbruch ist eingebaut.

**Nachweis:** Abschlussbericht mit Zahlen: wie viele Ansprechpartner
gefunden, wie viele Adressen geprüft-gut, wie viele ausgeschlossen.

### Schritt 5: Anrede-Spalte ergänzen (Leonards Vorschlag, kein KI-Modul)

Nach dem Datenlauf ergänzt Claude einmalig pro Kontakt eine
Anrede-Spalte in der Ergebnisliste — "Herr", "Frau" oder neutral
("Guten Tag Vorname Nachname") bei jeder Unsicherheit (seltener Name,
Initiale, Unisex-Name). Lieber neutral als falsch. Kostet nichts.
Gebaut wird nur die kleine Verkabelung: Der Baustein, der die fertigen
Mail-Texte pro Kontakt zusammensetzt, liest die Anrede aus dieser
Spalte.

Merkposten: Läuft das System später regelmäßig mit neuen Listen ohne
Claude im Ablauf, wird daraus doch ein automatisches Modul — für
diese Kampagne ist die Einmal-Spalte der einfachste zuverlässige Weg.

**Nachweis:** Die komplette Anrede-Spalte (alle Kontakte, nicht nur
Stichprobe) wird vor dem Upload gezeigt.

### Schritt 6: Leads hochladen und Stichprobe zeigen

Die geprüften Kontakte werden in die (weiterhin inaktive) Kampagne
geladen — pro Kontakt mit gefüllter {{anrede}}-Variable (Weg B).
Der Upload verweigert Kontakte ohne Anrede (Guard, testgetrieben).
Danach: 5 Beispiel-Mails zeigen (Anrede eingesetzt) plus eine echte
Testmail von Instantly an ein eigenes Test-Postfach, damit das
zusammengesetzte Ergebnis geprüft ist, bevor jemand Echtes etwas
bekommt.

**Nachweis:** Die 5 Stichproben-Mails + die angekommene Testmail.

### Schritt 7: Freigabe und Start

Leonard/Oliver sichten Kampagne und Stichprobe und geben frei. Erst
dann wird die Kampagne aktiviert. Nach dem ersten Versandtag gibt es
einen kurzen Blick auf die Zahlen (versendet, Rückläufer, Fehler).

**Nachweis:** Versand-Statistik nach Tag 1.

### Schritt 8: Einblick für Oliver (Dashboard, Antworten, Läufe)

Oliver soll sehen, was rausgeht und was zurückkommt — ohne Instantly.
Das Team-Web-Tool kann das (Dashboard + Kampagnen-Zahlen aus Instantly,
Postfach-Bereich für Antworten, Laufmanager für die Datenläufe).
Zu tun: prüfen, ob das Tool auf dem Arbeitsserver läuft (deploy/DEPLOY.md),
Login für Oliver anlegen, ihm Link + Kurzanleitung geben. Außerdem
organisatorisch klären: Wer liest und beantwortet täglich die
Antworten im Postfach-Bereich?

**Nachweis:** Oliver öffnet das Dashboard mit eigenem Login und sieht
die laufende Kampagne.

## Offene Entscheidungen (vor Schritt 2 nötig)

1. ~~Absender-Postfächer~~ **ENTSCHEIDEN (Leonard, 2026-07-28: "nimm
   welches du willst"):** Gewählt: `email@poleposition-automation.online`
   und `einladung@poleposition-automation.email` (aufgewärmt, passen
   thematisch). Anzeigename an beiden auf "Oliver Redschlag" gesetzt
   (war "PolePosition Automation"; keine Kampagne war aktiv).
   Instantly-Signatur bleibt bewusst leer — die Grußformel steht im
   Mail-Text selbst.
2. ~~Abstand Mail 3~~ **ENTSCHIEDEN (Leonard, 2026-07-28):** Mail 3
   kommt 7 Tage nach Mail 2 (= Tag 14 ab Mail 1). In der Kampagne
   hinterlegt; bis zum Start jederzeit änderbar.
3. ~~Versand-Tempo~~ **ENTSCHIEDEN (Leonard, 2026-07-28):** Fest
   20 neue Kontakte pro Tag, bis alle durch sind — keine Erhöhung
   zwischendurch. Bei 319 Kontakten und Versand Mo-Fr heißt das:
   Die erste Mail erreicht den letzten Kontakt nach gut 3 Wochen
   (ca. 16 Versandtage). Die Follow-ups laufen dabei automatisch
   versetzt mit.

## Risiken

- **Kosten:** Der Datenlauf verbraucht Guthaben bei Prospeo,
  Dropcontact und Hunter (319 Firmen). Der kleine Probelauf vorab
  begrenzt das Risiko einer Fehlkonfiguration.
- **Trefferquote:** Gemessen sind 87,5 % auf 16 Firmen — auf 319
  Firmen kann die Quote abweichen. Der Probelauf (Schritt 3) zeigt es
  früh.
- **Anrede-Fehler:** Eine falsche Anrede wirkt schlimmer als eine
  neutrale. Deshalb der Rückfall auf neutral bei jeder Unsicherheit.
- **Dauer:** Dropcontact antwortet langsam (Warteschleifen). Der volle
  Lauf braucht Stunden — eingeplant, Wiederanlauf vorhanden.

## Fortschritt

- [x] Schritt 1: Hunter-Prüfung info@ (2026-07-28: eingebaut, 596 Tests grün,
      Live-Nachweis: valid/invalid korrekt erkannt)
- [x] Schritt 2: Kampagne angelegt (2026-07-28: "Partnerschafts-Anfrage
      IT-Dienstleister PLR 30-39", id e9f33e56-d753-49ce-92c8-b6915808e969,
      Status Entwurf, 2 Absender, Betreffs je Stufe, Abstände 7+7 Tage,
      20/Tag, Mo-Fr 08-19 Uhr; Baukasten dafür um name/absender_emails/
      betreffs erweitert, Tests grün)
- [x] Schritt 3: Probelauf 10 Firmen ABGESCHLOSSEN (28./29.07.:
      **9 persönliche Mails = 90 %**, davon 6 Datenbank + 3
      Impressum-KI über OpenAI; 1 geprüfte info@ (Hunter "valid");
      kommunity.net am 29.07. mit neuem Dropcontact-Konto gelöst.
      Nebenbefunde behoben: OpenRouter-Zugang tot -> OpenAI als
      dritter KI-Anbieter; Prospeo-Konto stillgelegt -> Kaskade
      läuft ohne Prospeo)
- [ ] Schritt 4: Voller Datenlauf 319
- [ ] Schritt 5: Anrede-Spalte ergänzt und gezeigt
- [ ] Schritt 6: Leads hochgeladen + Stichprobe gezeigt
- [ ] Schritt 7: Freigabe + Start + Tag-1-Zahlen
- [ ] Schritt 8: Oliver-Zugang zum Dashboard + Antworten-Zuständigkeit geklärt
