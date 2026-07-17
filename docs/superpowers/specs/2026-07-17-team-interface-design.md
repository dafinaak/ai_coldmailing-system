# Design: Team-Interface für das KI-Coldmailing-System

Datum: 17.07.2026
Status: Von Leonard freigegeben (Design-Iteration v1–v4 mit Claude Design;
v4 eingefroren). Bauvorlage: docs/design/Poleposition-v4.dc.html.
Verbindliche Texte: docs/text-leitfaden-interface.md.

## Zweck und Nutzer

Interne Web-Oberfläche, damit das ganze (nicht-technische) Team das
Coldmailing-System bedienen kann — bisher geht das nur per Terminal.
Alle angemeldeten Nutzer haben dieselben Rechte. Zugriff im Browser
übers Internet/Büronetz, geschützt durch Anmeldung.

Erfolgskriterium: Ein nicht-technischer Kollege schafft ohne Anleitung
den kompletten Weg (Kunde anlegen → Anschreiben erstellen lassen →
prüfen → freigeben → Ergebnis verfolgen). Nachweis: begleiteter
Durchlauf mit einem echten Kollegen, Versand nur an Test-Adressen.

## Entstehungsgeschichte (für spätere Leser)

Vier Design-Runden: (1) CRM-artige Kundenliste — im Nutzertest
unverständlich; (2) Aufgaben-Startseite — noch verwirrender; (3)
Prozess-Board — strukturell klar, aber Leonard entschied sich für die
dem Team vertraute Struktur; (4) Wholix-artige Seitenleisten-Struktur
mit unseren Texten — freigegeben. Wichtigste Erkenntnis unterwegs:
Vertrautheit schlägt konzeptionelle Eleganz, und verständliche Sprache
ist wichtiger als Layout (daher der verbindliche Text-Leitfaden).

## Struktur: Seitenleiste mit sieben Bereichen

1. **Dashboard** — Kacheln (Warten auf deine Freigabe [prominent,
   verlinkt], Aktive Kampagnen, Heute versendet, Neue Antworten),
   Liste der wartenden Freigaben mit "Jetzt prüfen", Kampagnen-Liste,
   unübersehbares Banner bei angehaltenen Aufträgen.
2. **Kampagnen** — Tabelle (Name, Kunde, Status, Empfänger, versendet,
   Datum); Detail mit Fortschritt je Sequenz-Schritt (Anschreiben /
   Nachfass 1 / Nachfass 2), Wer-hat-wann-freigegeben, Link "Kampagne
   in Instantly öffnen". Hier wohnt der Knopf "Anschreiben erstellen
   lassen" (Kunde wählen, Anzahl, los).
3. **Prüfen & Freigeben** — mit Zähler-Badge. ENTSCHIEDEN:
   Lesefluss = Empfängerliste links, Lesebereich rechts;
   Freigabe-Geste = Checkliste (drei Punkte abhaken, erst dann wird
   der Freigeben-Knopf aktiv). Pro Empfänger: Name, Firma,
   E-Mail-Adresse, Betreff, Anschreiben, Nachfass 1+2 in voller Länge.
   "Ohne deine Freigabe wird nichts versendet." Wer/Wann-Protokoll.
   Zustand "Die Texte wurden neu erstellt — bitte noch einmal prüfen
   und freigeben." Bereich "Von der Prüfung aussortiert" mit Gründen.
4. **Kontakte** — rein lesende, durchsuchbare Tabelle aller jemals
   angeschriebenen Personen (Name, Firma, E-Mail, Kunde, Kampagne,
   zuletzt kontaktiert). Datenquelle: die Laufordner (leads/pruefung).
5. **Postfach** — rein lesend: pro Kontakt die Konversation (unsere
   gesendeten Mails + eingegangene Antworten, chronologisch), Daten
   über die Instantly-API. Knopf "In Instantly antworten ↗".
   Antworten-Schreiben aus dem Tool ist BEWUSST NICHT in dieser Stufe.
6. **Gesperrte Domains** — globale Liste (gilt für alle Kunden,
   zusätzlich zu den Kunden-Listen; beide zusammen wirken im
   Dubletten-/Sperr-Schritt der Pipeline). NEU im Backend: globale
   Sperrliste als Datei, von der Pipeline mitgelesen.
7. **Kunden** — Formular mit Hilfssatz je Feld (siehe Text-Leitfaden),
   inkl. "Angebot automatisch von der Firmen-Webseite ableiten"
   (füllt nur leere Felder).

## Feste Regeln (unverändert aus dem System)

- Ohne Freigabe kein Versand; Kampagnen entstehen pausiert in
  Instantly, scharf geschaltet wird dort von Hand.
- Neu erzeugte Texte machen alte Freigaben ungültig.
- Test-Adressen-Sperre der Pipeline bleibt; die Oberfläche zeigt den
  Test-Modus ehrlich an ("[TEST]"-Präfix).
- Fehler: laut, überall sichtbar, dreiteiliger Text (was passiert ist /
  was nicht / was tun), Fortsetzen möglich.
- Keine Geheimnisse (API-Schlüssel) in der Oberfläche.
- Alle Texte aus dem Text-Leitfaden, wörtlich.

## Bewusst NICHT in dieser Stufe

- Antworten schreiben/beantworten im Tool (v2, zusammen mit
  Antworten-Erkennung interessiert/nicht interessiert).
- Kontakte bearbeiten (Register ist rein lesend).
- Öffnungs-/Klick-Statistiken über das hinaus, was Instantly liefert.
- Mandanten-/Kundentrennung mit eigenen Logins (internes Team-Tool).

## In der Plan-Phase zu klären

- Wo läuft der Dienst: Server hinter mailingsystem.polepositionautomation.de
  (was läuft auf 178.104.175.42, wer hat Zugang?), HTTPS.
- Anmeldung: einfachste robuste Lösung (gemeinsames Team-Passwort +
  Namenswahl vs. Nutzerliste) — Freigaben brauchen einen echten Namen.
- Instantly-API-Endpunkte für Postfach (emails-Liste inkl. Antworten)
  und Kampagnen-Statistiken: Umfang am echten Konto verifizieren.
- Hintergrund-Ausführung der Läufe im Web-Kontext (Prozess/Queue) und
  Fortschritts-Anzeige (Polling).
- Nebenläufigkeit: zwei Nutzer gleichzeitig (Datei-Sperren?).
