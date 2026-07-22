# Phase 2: Wholix-Freigabe und Sperrliste

**Stand:** 22. Juli 2026  
**Status:** Gestaltung mit dem Nutzer abgestimmt  
**Grundlage:** `docs/wholix-nachbau-roadmap.md` und die Wholix-Bildschirmfotos

## Ziel

Phase 2 macht die Prüfung von E-Mail-Sequenzen übersichtlich und zuverlässig. Eine E-Mail-Runde wird in einer Wholix-ähnlichen Tabelle geprüft. Jede der drei E-Mails pro Empfänger wird einzeln bestätigt. Erst wenn alle vorgesehenen Texte gültig bestätigt sind, darf die komplette Runde an Instantly übergeben werden.

Nach der Übergabe bleibt die Runde in derselben Oberfläche sichtbar. Dort werden belegbare Versand- und Antwortdaten aus Instantly angezeigt. Fehlende oder nicht eindeutig zuordenbare Werte werden als unbekannt angezeigt und nicht geschätzt.

Außerdem wird die Sperrliste zu einer Wholix-ähnlichen Tabelle mit Grund, Kommentar und Platzhalter-Einträgen für ganze Domain-Gruppen ausgebaut.

## Erfolgskriterien

Die Phase ist erfolgreich, wenn:

1. immer genau eine E-Mail-Runde in der Prüftabelle angezeigt wird;
2. jede E-Mail und jedes Follow-up einzeln bestätigt werden kann;
3. der bestätigte Stand nach einem Neuladen erhalten bleibt;
4. eine geänderte E-Mail nur ihre eigene Bestätigung verliert;
5. eine unvollständig bestätigte Runde technisch nicht übergeben werden kann;
6. Mehrfachauswahl und Filter die Prüfung vieler Empfänger beschleunigen;
7. nach der Übergabe nur eindeutig belegbare Instantly-Daten angezeigt werden;
8. die Sperrliste alte Einträge weiterhin versteht und neue Einträge mit Grund und Kommentar speichert;
9. die Oberfläche auf dem Desktop wie die Wholix-Vorlage wirkt und auf schmalen Bildschirmen benutzbar bleibt;
10. automatische Prüfungen sowie Bildschirmfotos mit Testdaten den Ablauf belegen.

## Umfang

### Wird gebaut

- Übersicht unter `/pruefen` mit den Bereichen **Offen** und **Übergeben**
- eine eigene Prüftabelle je E-Mail-Runde
- drei einzeln prüfbare Schritte je Empfänger:
  - E-Mail 1
  - Follow-up 1
  - Follow-up 2
- Suche, Statusfilter und Mehrfachauswahl
- dauerhafte Bestätigung je Empfänger und Schritt
- erneutes Erzeugen genau eines einzelnen Schritts
- endgültige Übergabe nur als vollständige Runde
- Versand- und Antwortanzeige aus Instantly nach der Übergabe
- Sperrliste mit Domain, Grund, Kommentar und Aktionen
- Platzhalter-Einträge wie `*.bund.de`

### Wird nicht gebaut

- keine gemeinsame Tabelle mit Empfängern aus mehreren Runden oder Zielgruppen
- keine teilweise Übergabe einzelner Empfänger oder Schritte an Instantly
- keine teilweise Versendung einer Runde
- keine freie Bearbeitung der Texte von Hand; ein ungeeigneter Text wird neu erzeugt
- keine Schätzung unbekannter Versand-, Antwort- oder Fehlerwerte
- keine echten Testsendungen und keine Änderungen am echten Instantly-Konto während der Entwicklung
- keine weiteren Wholix-Funktionen außerhalb des beschlossenen Fahrplans

## Seiten und Ablauf

### 1. Übersicht `/pruefen`

Die bisherige Übersicht bleibt der Einstieg. Sie erhält zwei klar getrennte Bereiche:

- **Offen:** Runden, die noch geprüft werden oder noch nicht vollständig bestätigt sind
- **Übergeben:** Runden, die vollständig bestätigt und an Instantly übergeben wurden

Jede Karte oder Tabellenzeile gehört genau zu einer Runde und zeigt mindestens:

- Name der Runde
- Zielgruppe
- Anzahl Empfänger
- Fortschritt der Prüfung
- Zustand: offen, in Prüfung, vollständig bestätigt, übergeben oder mit Warnung
- Zeitpunkt der letzten Änderung

Ein Klick öffnet die Tabelle dieser einen Runde. Dadurch werden verschiedene Zielgruppen nie vermischt.

### 2. Prüftabelle einer Runde

Oben stehen vier kompakte Kennzahlen:

- Empfänger insgesamt
- vollständig geprüft
- noch offen
- Nacharbeit nötig

„Nacharbeit nötig“ ist kein bloß noch unbestätigter Text. Dazu zählen nur erkennbare Hindernisse wie ein fehlender Schritt, eine bestehende Qualitätswarnung oder ein technisch unbrauchbarer Inhalt. Ein normaler, noch nicht geprüfter Text zählt als offen.

Darunter stehen:

- Suche nach Name, Firma oder E-Mail-Adresse
- Filter nach Prüfzustand
- Auswahlfeld für sichtbare Zeilen
- Anzahl der ausgewählten Empfänger

Die Tabelle orientiert sich an der breiten Wholix-E-Mail-Sequenz. Die linke Seite bleibt beim waagerechten Rollen stehen und enthält:

- Auswahlfeld
- Empfängername
- Firma
- E-Mail-Adresse

Danach folgen drei gleich aufgebaute Gruppen:

| Gruppe | Inhalt |
| --- | --- |
| E-Mail 1 | kurze Vorschau, „Lesen“, Prüfzustand, Versandzeit, Antwortzustand |
| Follow-up 1 | kurze Vorschau, „Lesen“, Prüfzustand, Versandzeit, Antwortzustand |
| Follow-up 2 | kurze Vorschau, „Lesen“, Prüfzustand, Versandzeit, Antwortzustand |

Vor der Übergabe sind Versandzeit und Antwortzustand leer beziehungsweise `—`. Nach der Übergabe werden sie nur gefüllt, wenn Instantly sie eindeutig belegt.

Am unteren Rand bleibt eine Aktionsleiste sichtbar:

- **Ausgewählte bestätigen:** bestätigt alle noch offenen Schritte der ausgewählten Empfänger
- **Bestätigungen aufheben:** hebt die Bestätigungen aller Schritte der ausgewählten Empfänger auf
- **Runde übergeben:** übergibt die gesamte Runde und ist nur aktiv, wenn alle nötigen Schritte gültig bestätigt sind und keine Sperre besteht

Die Auswahl bezieht sich immer auf Empfängerzeilen. Ein einzelner Schritt wird im Lesebereich bestätigt oder neu erzeugt.

Nach einer erfolgreichen Übergabe ist die Prüfung schreibgeschützt. Bestätigungen können dann nicht mehr geändert und Texte nicht mehr neu erzeugt werden. Die Tabelle dient ab diesem Zeitpunkt nur noch als Versand- und Antwortübersicht.

### 3. Lesebereich für einen Schritt

„Lesen“ öffnet rechts einen Seitenbereich. Darin stehen:

- Empfänger und Firma
- Bezeichnung des Schritts
- Betreff, falls der Schritt einen Betreff hat
- vollständiger E-Mail-Text
- Prüfzustand und Zeitpunkt der letzten Bestätigung
- Aktion **Bestätigen** oder **Bestätigung aufheben**
- Aktion **Neu erzeugen**

Beim erneuten Erzeugen gilt:

- Es wird nur der geöffnete Schritt neu erzeugt.
- Die übrigen zwei Schritte bleiben unverändert und behalten ihre Bestätigung.
- Erst nach erfolgreicher Erzeugung und sicherem Speichern wird die Bestätigung dieses Schritts aufgehoben.
- Schlägt die Erzeugung oder das Speichern fehl, bleiben alter Text und bestehende Bestätigung unverändert.

## Bestätigungsmodell

### Dauerhafter Zustand

Jede Runde erhält eine eigene maschinenlesbare Zustandsdatei, vorgesehen als `freigabe-status.json` im Ordner der Runde. Sie enthält eine Versionsnummer sowie je Empfänger und Schritt:

```json
{
  "version": 1,
  "recipients": {
    "stabile-empfaenger-id": {
      "email_1": {
        "approved": true,
        "approved_at": "2026-07-22T12:00:00Z",
        "approved_by": "lokaler-benutzer",
        "content_hash": "sha256:..."
      },
      "follow_up_1": {},
      "follow_up_2": {}
    }
  }
}
```

Die genaue Empfänger-ID wird aus einer bereits stabil vorhandenen Kennung übernommen. Falls ältere Runden keine solche Kennung haben, wird beim ersten Laden eine feste lokale Kennung erzeugt und gespeichert. Name oder E-Mail-Adresse allein dürfen nicht als veränderliche Speicheradresse dienen.

### Inhaltsabgleich

Für jeden Schritt wird ein Hash aus allen versandrelevanten Inhalten gebildet, insbesondere Betreff und Text. Eine Bestätigung zählt nur, wenn:

- `approved` wahr ist und
- der gespeicherte Hash dem aktuellen Inhalt entspricht.

Bei einer Abweichung wird nur dieser eine Schritt wieder als offen behandelt. Andere Schritte desselben Empfängers bleiben bestätigt, sofern deren Hash weiterhin passt.

### Endgültige Übergabe

Die vorhandene endgültige Freigabe und Instantly-Übergabe bleibt die letzte Schranke. Vor der Übergabe prüft der Server erneut und unabhängig von der Anzeige:

- alle vorgesehenen Empfänger sind vorhanden;
- jeder Empfänger besitzt alle drei vorgesehenen Schritte;
- jeder Schritt hat eine gültige, zum aktuellen Inhalt passende Bestätigung;
- keine Qualitäts- oder Sperrlistenprüfung blockiert die Runde;
- dieselbe Runde wird nicht bereits übergeben;
- die zugrunde liegenden Daten wurden seit dem Laden der Seite nicht unbemerkt verändert.

Erst danach wird die vorhandene Übergabe für die komplette Runde ausgelöst. Die Prüfung und das Setzen des Übergabe-Zustands erfolgen unter der bestehenden Sperre gegen doppelte Übergaben.

## Schutz vor veralteten Seiten und gleichzeitigen Änderungen

Jede ändernde Formularanfrage enthält den zuletzt gesehenen Stand der Runde. Hat sich die Runde inzwischen verändert, wird die Anfrage abgelehnt. Die Oberfläche erklärt in einfachen Worten, dass die Daten neu geladen werden müssen.

Bestehende Schutzmaßnahmen für Formulare, Pfade und Rundenzugriff bleiben für alle neuen Aktionen verbindlich.

Zustandsdateien werden atomar geschrieben: zuerst vollständig in eine neue Datei, danach sicher an die endgültige Stelle verschoben. Eine unterbrochene Speicherung darf keine halbe oder ungültige Datei hinterlassen.

## Instantly-Daten nach der Übergabe

### Datenquellen

Nach der Übergabe werden zwei offizielle Instantly-Schnittstellen verwendet:

- Lead-Liste, gefiltert nach Kampagne: `POST /api/v2/leads/list`
- E-Mail-Liste, gefiltert nach Kampagne: `GET /api/v2/emails`

Die Lead-Liste ist trotz `POST` eine reine Leseabfrage. Sie darf nur in dem begrenzten Abrufweg verwendet werden, der keine Daten verändert.

### Zuordnung

Die lokale Runde wird anhand der gespeicherten Kampagnen- und Empfängerkennungen mit Instantly verbunden. Für jeden Schritt gilt:

- **Versendet** wird nur angezeigt, wenn eine Instantly-E-Mail eindeutig demselben Empfänger, derselben Kampagne und demselben Schritt zugeordnet ist.
- Die Versandzeit stammt direkt aus dem Zeitstempel dieser E-Mail.
- Eine Antwort wird einem einzelnen Schritt nur zugeordnet, wenn Thread- und Schrittdaten dies eindeutig erlauben.
- Ist nur sicher, dass der Empfänger geantwortet hat, aber nicht auf welchen Schritt, wird die Antwort auf Empfängerebene angezeigt und nicht einem geratenen Schritt zugeordnet.
- Rückläufer, Abmeldung oder Überspringen werden auf Empfängerebene angezeigt, außer Instantly liefert einen eindeutigen Bezug zu einem Schritt.
- Widersprüchliche, fehlende oder nicht unterstützte Werte erscheinen als `—` oder als verständliche Warnung.

### Seitennavigation und doppelte Daten

Instantly liefert höchstens 100 Einträge pro Seite. Der Abruf:

- folgt den vorgesehenen Seitenzeigern bis zum Ende;
- entfernt doppelte Einträge anhand stabiler Instantly-Kennungen;
- bricht bei einem wiederholten Seitenzeiger mit einer Warnung ab;
- setzt eine feste Obergrenze, damit ein fehlerhafter Dienst keine Endlosschleife auslöst.

### Ausfälle

Ist Instantly vorübergehend nicht erreichbar:

- bleibt die Runde sichtbar und bedienbar;
- werden vorhandene, zuletzt erfolgreich gelesene Werte mit Abrufzeit angezeigt, sofern ein solcher sicherer Zwischenspeicher vorhanden ist;
- andernfalls stehen die betroffenen Werte auf `—`;
- eine verständliche Meldung erklärt, dass der Live-Stand gerade nicht geladen werden konnte.

Ein Ausfall darf den lokalen Prüfstand nicht beschädigen und darf keine Übergabe wiederholen.

## Sperrliste

### Oberfläche

Die Sperrliste folgt der Wholix-Vorlage und zeigt:

| Spalte | Bedeutung |
| --- | --- |
| Domain | einzelne Domain oder Domain-Gruppe mit Platzhalter |
| Grund | Kunde, Partner, Konkurrent oder Sonstiges |
| Kommentar | freie interne Erklärung |
| Aktionen | bearbeiten oder entfernen |

Beim Hinzufügen werden Domain, Grund und optionaler Kommentar erfasst.

### Schreibweise und Prüfung

Erlaubt sind:

- einzelne Domains wie `beispiel.de`
- Domain-Gruppen wie `*.bund.de`

Nicht erlaubt sind vollständige Internetadressen, Pfade, Leerzeichen oder ungültige Platzhalter. Großschreibung und unnötige abschließende Punkte werden vereinheitlicht.

Vor dem Speichern wird geprüft:

- Ist der Eintrag gültig?
- Gibt es ihn bereits?
- Wird die einzelne Domain bereits von einem vorhandenen Platzhalter abgedeckt?
- Würde ein neuer Platzhalter vorhandene Einträge vollständig abdecken?

Die Oberfläche nennt den Grund einer Ablehnung. Beim letzten Fall wird keine stillschweigende Löschung vorgenommen; der Nutzer sieht den Konflikt und entscheidet später über eine Bereinigung.

### Speicherung und Rückwärtsverträglichkeit

Neue Einträge werden strukturiert gespeichert, zum Beispiel:

```yaml
- domain: "*.bund.de"
  reason: "Kunde"
  comment: "Bestehender Rahmenvertrag"
```

Bestehende einfache Einträge bleiben lesbar:

```yaml
- "beispiel.de"
```

Sie werden in der Oberfläche ohne Grund und Kommentar angezeigt. Beim nächsten gezielten Bearbeiten können sie in das neue Format überführt werden. Die übrige Verarbeitung erhält weiterhin eine einfache, vereinheitlichte Liste der gesperrten Domain-Muster, damit bestehende Prüfungen unverändert zuverlässig arbeiten.

Auch die Sperrliste wird atomar gespeichert.

## Fehlerverhalten

- Fehlt ein Empfänger oder einer seiner drei Texte, erscheint eine Warnung und die Runde kann nicht übergeben werden.
- Schlägt eine einzelne Neuerzeugung fehl, bleiben alter Text und Bestätigung erhalten.
- Ändert sich ein Text erfolgreich, wird nur seine Bestätigung ungültig.
- Eine Anfrage von einer veralteten Seite wird abgewiesen und verlangt ein Neuladen.
- Ein doppelter Übergabeversuch wird durch die bestehende Sperre abgefangen.
- Fehlt nur ein Instantly-Feld, bleiben andere belegte Felder sichtbar.
- Ein Instantly-Ausfall erzeugt keine erfundenen Nullen oder falschen Erfolgsanzeigen.
- Eine alte Sperrlistendatei bleibt ohne vorherige Umwandlung nutzbar.

## Prüfung und Nachweis

### Automatische Prüfungen mit Testdaten

Mindestens geprüft werden:

- Bestätigung eines einzelnen Schritts wird gespeichert und nach Neuladen geladen.
- Mehrere ausgewählte Empfänger können gemeinsam bestätigt werden.
- Das Aufheben mehrerer Bestätigungen funktioniert.
- Eine Inhaltsänderung macht nur den betroffenen Schritt wieder offen.
- Eine fehlgeschlagene Neuerzeugung verändert weder Text noch Bestätigung.
- Eine erfolgreiche Neuerzeugung speichert den neuen Text und hebt nur diese Bestätigung auf.
- Eine unvollständig bestätigte Runde kann auch durch eine direkte Anfrage nicht übergeben werden.
- Eine Anfrage mit einem veralteten Rundenstand wird abgewiesen und verändert keine Daten.
- Eine vollständig bestätigte Runde nutzt den vorhandenen sicheren Übergabeweg genau einmal.
- Suche und Statusfilter liefern die richtigen Zeilen.
- Instantly-Ausfall, unvollständige Antworten, mehrere Seiten, doppelte Einträge und wiederholte Seitenzeiger werden sicher behandelt.
- Versand- und Antwortzustände werden nur bei eindeutiger Zuordnung angezeigt.
- alte und neue Sperrlisteneinträge werden gelesen.
- ungültige, doppelte oder bereits abgedeckte Domain-Muster werden abgelehnt.
- die komplette bestehende Prüfreihe bleibt erfolgreich.

### Sichtbarer Nachweis

Mit eigens erzeugten Testdaten werden Bildschirmfotos erstellt für:

- Übersicht mit offenen und übergebenen Runden
- breite Prüftabelle auf dem Desktop
- geöffneter Lesebereich eines Schritts
- vollständig bestätigte Runde mit aktiver Übergabeaktion
- übergebene Runde mit belegten und unbekannten Instantly-Werten
- Sperrliste mit altem Eintrag, neuem Eintrag und Platzhalter
- schmale Ansicht mit 390 Pixel Breite

Auf kleinen Bildschirmen darf nur die Tabelle waagerecht rollen. Der Rest der Seite darf nicht über die Bildschirmbreite hinausragen. Die Tabelle, Filter und Aktionen müssen mit Tastatur bedienbar und verständlich beschriftet sein.

### Keine Produktionstests

Alle automatischen und sichtbaren Prüfungen verwenden Testdaten und nachgebildete Instantly-Antworten. Ein späterer rein lesender Test mit dem echten Instantly-Konto braucht erneut eine ausdrückliche Freigabe. Echte Empfänger werden nicht angeschrieben.

## Maßgebliche Entscheidungen

- Eine Tabelle zeigt immer genau eine Runde beziehungsweise Zielgruppe.
- Bestätigungen werden pro Empfänger und pro Schritt gespeichert.
- Mehrfachauswahl arbeitet auf Empfängerzeilen und bestätigt deren offene Schritte gesammelt oder hebt deren Bestätigungen gesammelt auf.
- Neu erzeugt wird genau ein Schritt, nicht die ganze Sequenz.
- An Instantly wird nur die vollständig bestätigte Runde übergeben.
- Unbekannte Zustände bleiben sichtbar unbekannt.
- Zuverlässigkeit geht vor Geschwindigkeit und vor einer möglichst großen Funktionsmenge.
