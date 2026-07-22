# Projekt-Regeln: AI Coldmailing System

## Zuverlässigkeit zuerst

Zuverlässigkeit hat in diesem Projekt höchste Priorität — vor
Sparsamkeit und vor Schnelligkeit. Plane und baue nichts, dessen
Zuverlässigkeit unsicher ist.

Das heißt konkret:

- Das Fundament der Datenbeschaffung sind stabile, bezahlte
  Schnittstellen (z. B. Dropcontact, Hunter), die selbst prüfen und
  verlässlich antworten. Auf die stützt sich das System.
- Selbst gebaute, brüchige Bausteine (z. B. ein Impressum-Scraper mit
  wechselnden Layouts und Wartung bei uns) sind KEIN Fundament. Sie
  dürfen höchstens ein geprüfter Bonus obendrauf sein, auf den sich das
  System nicht verlässt.
- Jede gefundene E-Mail wird vor dem Versand geprüft, damit keine
  Rückläufer den Ruf der Absender-Postfächer beschädigen. Die Prüfung
  ist Teil der Zuverlässigkeit, nicht optional.

## Interface = Wholix-Nachbau

Die Oberfläche soll aussehen und sich bedienen wie Wholix (die 10
Bildschirmfotos im Ordner "wholix interface screenshots" sind die
Vorlage). Es ist ein internes Tool; Instantly bleibt der unsichtbare
Versand-Motor darunter.

Nachgebaut wird der Funktionsumfang laut Fahrplan
(docs/wholix-nachbau-roadmap.md), MINUS der am 22.07.2026 gestrichenen
Funktionen (dort im Abschnitt "Scope-Entscheidungen" gelistet). Nicht
jede Wholix-Funktion ist für ein internes Tool sinnvoll - was gestrichen
ist, wird nicht gebaut.
