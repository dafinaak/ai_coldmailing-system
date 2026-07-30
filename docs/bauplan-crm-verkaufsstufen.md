# Bauplan: CRM mit Verkaufsstufen (Wholix-Nachbau, letzter Scope-Block)

Stand: 2026-07-29 — VON LEONARD FREIGEGEBEN. Bau startet nach dem
Versandstart der Partnerschafts-Kampagne.

## Vorlage (geprüft an den Screenshots, 29.07.2026)

Wholix' Contacts-Ansicht (Screenshot 14.44.20): eine **Stufen-Leiste
mit Zählern** über der Kontaktliste — Chips „All / New Lead / Demo /
Follow up / Proposal / Won / Lost" (+ ein im Bild abgeschnittener
Chip) — plus Suche, Filter und eine Ansicht-Umschaltung. KEIN
Spalten-Board (Kanban); die Stufe ist ein Filter/Attribut des
Kontakts. Der Nachbau folgt dieser Leisten-Logik.

## Entscheidungen (Leonard, 29.07.2026)

1. **Zufluss:** Automatisch, aber NUR wer auf eine Kampagnen-Mail
   geantwortet hat. Kein Massen-Import aller Angeschriebenen.
2. **Stufen:** Wholix-Stufen, deutsch beschriftet:
   Neuer Lead / Demo-Termin / Nachfassen / Angebot / Gewonnen /
   Verloren. (Der abgeschnittene 7. Chip wird ignoriert, bis jemand
   im echten Wholix nachsieht; Start mit den sechs lesbaren.)
3. **Nutzer:** Einzelnutzer (Leonard). Keine Gleichzeitigkeits-Technik.
4. **Speicher:** SQLite-Datenbankdatei im Datenverzeichnis
   (daten_dir/kontakte.db) — die frühere Analyse empfahl das; robust
   und wächst problemlos mit.

5. **Mehrere Kampagnen von Beginn an** (Leonard, 29.07.2026): Das CRM
   deckt von Anfang an mehrere Kampagnen ab. Umsetzung: Jeder Kontakt
   trägt seine Kampagnen-Zuordnung (kommt beim automatischen Zufluss
   mit — die Antwort gehört ja zu einer bestimmten Kampagne). Die
   Kontakte-Seite bekommt von Beginn an eine Kampagnen-Auswahl
   (wie Wholix' Pipeline-Wahl): ein Brett je Kampagne, mit denselben
   sechs Stufen, plus die Ansicht "Alle Kampagnen". Eigene
   Stufen-Sätze je Kampagne werden erst gebaut, wenn eine echte
   Kampagne andere Stufen braucht (dann nur Konfiguration, kein
   Umbau — das Datenmodell trägt es von Tag 1).

## Schritte

### Schritt 1: Datenfundament (SQLite)

Kontakte-Tabelle (Name, Firma, E-Mail, Stufe, Kampagnen-Zuordnung,
angelegt am, Stufe geändert am) mit kleiner Zugriffsschicht,
testgetrieben. Keine Migrations-Maschinerie — eine Tabelle, klar
dokumentiert.

**Nachweis:** Tests grün (anlegen, Stufe wechseln, doppelte E-Mail
wird nicht doppelt angelegt).

### Schritt 2: Automatischer Zufluss der Antwortenden

Baustein, der aus den bereits vorhandenen Antwort-Daten (das Tool
liest Kampagnen-Antworten heute schon für den Postfach-Bereich) neue
Kontakte anlegt: Wer antwortet, erscheint mit Stufe „Neuer Lead",
je E-Mail-Adresse genau einmal. Läuft beim Seitenaufruf bzw. mit dem
bestehenden Abruf-Mechanismus — kein neuer Hintergrund-Dienst.

**Nachweis:** Tests grün + Demo mit Testdaten: simulierte Antwort ->
Kontakt erscheint; zweite Antwort derselben Adresse -> kein Duplikat.

### Schritt 3: Kontakte-Seite im Wholix-Look

Neue Seite „Kontakte": oben die **Kampagnen-Auswahl** (Brett je
Kampagne + "Alle Kampagnen"), darunter die Stufen-Leiste mit Zählern
(Alle + die sechs Stufen, aktive Stufe hervorgehoben; Zähler gelten
für die gewählte Kampagne), darunter die Kontaktliste (Name, Firma,
E-Mail, Stufe, Kampagne), Suche. Stufe wechseln per Auswahlfeld
direkt in der Zeile. Gestaltung nach Screenshot 14.44.20
(Chips-Optik, Zähler, Leerzustand "Keine Kontakte").

**Nachweis:** Bildschirmfotos Desktop + 390 px neben der Vorlage;
kein seitlicher Überlauf; Stufenwechsel sichtbar demonstriert.

### Schritt 4: Verbindung zu Kampagne und Postfach

Vom Kontakt aus ein Klick zum zugehörigen Antwort-Verlauf im
Postfach-Bereich (dort wird geantwortet — das CRM verdoppelt keine
Mail-Funktionen).

**Nachweis:** Klickweg Kontakt -> Verlauf demonstriert.

## Bewusst NICHT gebaut (Scope-Entscheidungen 22.07. + heute)

- Kein Kanban-/Spalten-Board (hat die Vorlage nicht)
- Keine freie Pipeline-Verwaltung ("+ New pipeline"-Knopf): Bretter
  entstehen automatisch aus den Kampagnen, nicht von Hand
- Kein AI-Chat, keine Anrufe, keine Notizen (gestrichen am 22.07.)
- Kein manueller Massen-Import; Einzelkontakt von Hand anlegen ist
  als kleiner "+ Hinzufügen"-Knopf enthalten (Wholix hat ihn auch)

## Risiken

- Antwort-Zuordnung: Die Antwort-Erkennung übernimmt die konservative
  Logik des Postfach-Bereichs (nur eindeutige Zuordnungen). Unklare
  Fälle erzeugen KEINEN Kontakt — lieber einer zu wenig als Müll im
  CRM; der Postfach-Bereich zeigt sie weiterhin.
- Der abgeschnittene 7. Stufen-Chip: falls er im echten Wholix etwas
  Wichtiges ist (z. B. "Postponed"), kostet das Nachrüsten einer
  Stufe eine Zeile Konfiguration, keinen Umbau.

## Fortschritt

- [x] Schritt 1: SQLite-Datenfundament (29.07.: web/crm_speicher.py,
      5 Tests grün — anlegen, Duplikat-Schutz, Stufenwechsel mit
      Zeitstempel, Zähler/Filter je Kampagne, sechs deutsche Stufen)
- [x] Schritt 2: Automatischer Zufluss (29.07.: web/crm_zufluss.py,
      4 Tests grün — nur erhaltene Nachrichten erzeugen Kontakte,
      keine Duplikate, Anreicherung aus lokalen Kontaktdaten,
      Kampagnen-Zuordnung aus der Nachricht)
- [x] Schritt 3: CRM-Seite gebaut (30.07.: Route /crm + Navigation,
      Kampagnen-Brätter, Stufen-Leiste mit Zählern, Suche,
      Stufenwechsel je Zeile, "+ Hinzufügen"; Zufluss an den
      Postfach-Abruf angeschlossen; 641 Tests grün. Offen: Feinschliff
      der Optik gegen die Vorlage + Bildschirmfoto-Nachweis)
- [ ] Schritt 4: Verbindung zu Postfach/Kampagne (Klick vom Kontakt
      zum Antwort-Verlauf)
