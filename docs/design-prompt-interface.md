# Design-Prompt: Team-Oberfläche für unser KI-Coldmailing-System

Entwirf das Interface für ein internes Web-Werkzeug. Du bist frei in
Gestaltung, Aufbau, Anmutung und Interaktionsmustern — unten stehen nur
die Idee, das Ziel, die Inhalte und die Regeln, die das Design
respektieren muss. Wie es aussieht und sich anfühlt, entscheidest du.

## Die Idee

Wir sind eine kleine Agentur für KI-Automatisierung. Wir haben ein
System gebaut, das Kaltakquise-E-Mails stark personalisiert erstellt:
Es sucht passende Firmen-Ansprechpartner aus einer Datenbank, liest die
Webseite jeder einzelnen Firma und schreibt daraus ein individuelles
Anschreiben plus zwei Nachfass-Mails. Verschickt wird über ein externes
Versand-Tool (Instantly). Bisher wird das System über Terminal-Befehle
bedient — das können nur Techniker. Das neue Interface soll es dem
ganzen Team zugänglich machen.

## Das Ziel

Ein nicht-technischer Team-Kollege schafft ohne Anleitung und ohne
Hilfe den kompletten Weg: Kunden anlegen → Lauf starten → Texte lesen →
freigeben → Ergebnis verfolgen. Wenn eine Stelle Erklärung braucht, ist
das Design dort noch nicht fertig.

## Die Nutzer

Internes Team, wenige Personen, alle gleichberechtigt, deutschsprachig,
nicht technisch. Sie arbeiten am Desktop-Browser. Sie kennen den
Fachkontext (Vertrieb, Kaltakquise), aber keine Terminals, kein JSON,
keine API-Begriffe. Sprache der Oberfläche: Deutsch, einfache Wörter,
keine Technik-Begriffe ("Lauf gestartet", nicht "Pipeline execution").

## Die vier Bereiche (Zweck und Muss-Inhalte, keine Layout-Vorgaben)

1. **Kunden.** Liste aller Kunden. Kunde anlegen/bearbeiten mit den
   Feldern: Name, Zielgruppe (Jobtitel, Region, Firmengröße), Angebot
   (Fließtext), Tonalität, Absendername, Domain-Sperrliste (Domains, die
   nie angeschrieben werden, mit Platzhalter-Unterstützung wie
   *.bund.de), Test-Empfänger-Liste. Es gibt eine Funktion "Angebot
   automatisch von der Firmen-Webseite ableiten" — sie füllt die Felder
   Angebot und Tonalität als Vorschlag vor, überschreibt aber nie, was
   ein Mensch schon eingetragen hat.
2. **Lauf starten.** Kunde wählen, gewünschte Lead-Anzahl, Start. Ein
   Lauf dauert mehrere Minuten und durchläuft sichtbare Schritte:
   Leads suchen → E-Mail-Adressen ermitteln → Dubletten und gesperrte
   Domains aussortieren → Webseiten lesen und Texte schreiben →
   Qualitätsprüfung. Der Nutzer muss jederzeit sehen: wo steht der
   Lauf, was ist schiefgegangen (in verständlichem Deutsch), was kam
   heraus (Zahlen: gefunden / ohne E-Mail übersprungen / aussortiert
   mit Grund / fertig personalisiert / Nacharbeit). Ein abgebrochener
   Lauf kann fortgesetzt werden, ohne dass Ergebnisse verloren gehen.
3. **Freigabe.** Der wichtigste Bereich. Zeigt zu einem Lauf ALLE
   erstellten Texte vollständig: pro Empfänger Betreff, Anschreiben,
   Nachfass-Mail 1, Nachfass-Mail 2 — das sind längere deutsche
   E-Mail-Texte, die bequem lesbar sein müssen. Dazu die Zahlen des
   Laufs und die Nacharbeit-Liste (Texte, die die automatische Prüfung
   abgelehnt hat, mit Begründung). Zwei Handlungen: Freigeben oder
   Ablehnen. Freigeben ist eine bewusste, schwer versehentlich
   auslösbare Handlung; festgehalten wird, wer wann freigegeben hat.
4. **Ergebnisse.** Pro Kunde: vergangene Läufe mit ihren Berichten, und
   für übergebene Kampagnen der Live-Status aus dem Versand-Tool
   (aktiv/pausiert, wie viele Mails verschickt) plus ein Absprung-Link
   ins Versand-Tool. Diese Ansicht ist rein lesend.

## Regeln und Logik, die das Design nicht verletzen darf

- **Ohne ausdrückliche menschliche Freigabe verlässt keine einzige Mail
  das System.** Der Freigabe-Schritt darf nicht überspringbar oder
  versteckt sein; er ist das Sicherheits-Tor und darf sich auch so
  anfühlen.
- Nach einer Freigabe wird die Kampagne im Versand-Tool **pausiert**
  angelegt; das Scharfschalten passiert bewusst im Versand-Tool, nicht
  in unserem Interface. Das Interface soll diesen Übergabepunkt ehrlich
  zeigen ("liegt jetzt pausiert in Instantly"), nicht verschleiern.
- Wird ein Lauf nach einer Freigabe verändert oder neu gerechnet,
  verfällt die alte Freigabe automatisch — neue Texte heißen neue
  Freigabe. Das Design muss diesen Zustand ("Freigabe verfallen —
  bitte neu prüfen") klar unterscheidbar machen.
- Ein Zugangsschutz mit Anmeldung ist vorhanden; alle angemeldeten
  Nutzer haben dieselben Rechte.
- Fehler externer Dienste (Datenbank, KI, Versand-Tool) stoppen den
  Lauf laut und sichtbar — nie stilles Weiterlaufen. Der Nutzer sieht,
  was er tun kann (später erneut versuchen, Lauf fortsetzen).
- Geheimnisse (API-Schlüssel) tauchen in der Oberfläche nirgends auf.

## Realistische Inhalte für den Entwurf

Nutze realistisch lange deutsche Beispieltexte (Anschreiben ~80–120
Wörter, Nachfass-Mails ~40–80 Wörter), echte wirkende Firmennamen und
eine Nacharbeit-Liste mit Begründungen wie "Prüf-KI: klingt nach
Massenmail" — das Design muss mit echten Textmengen funktionieren,
nicht mit Lorem ipsum.

## Was wir von dir brauchen

Entwürfe der vier Bereiche inklusive der wichtigen Zustände: leer
(noch kein Kunde/Lauf), Lauf in Arbeit, Lauf mit Fehlern, Vorschau vor
Freigabe, Freigabe verfallen, Kampagne übergeben. Das Ergebnis soll
sich als schlichte Web-App umsetzen lassen (Server-Seiten, kein
App-Store, kein Mobile-First nötig — Desktop zuerst).
