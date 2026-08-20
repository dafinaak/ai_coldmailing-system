# Projekt: AI Coldmailing System

## Worum es geht

Das interne Team-Tool ersetzt die Wholix-Oberfläche schrittweise. Es führt
von Angebot und Lead-Suche über KI-Texte und Freigabe bis zum Versand.
Instantly bleibt darunter der Versand-Motor für Versand, Anwärmen und
Zustellbarkeit. Die Wholix-Bildschirmfotos sind die Vorlage für Aussehen und
Bedienung; der genaue Umfang steht in `docs/wholix-nachbau-roadmap.md`.

Zuverlässigkeit steht vor Tempo und Kosten: Daten kommen aus stabilen,
bezahlten Schnittstellen; jede E-Mail wird vor Versand geprüft. Tests und
sichtbare Nachweise benutzen Testdaten, niemals echte Empfänger.

## Aktueller Stand

- Interface lokal starten (seit 11.08.2026): `./start-web.sh` im
  Projektordner, dann http://127.0.0.1:8000. Das Skript liest die .env und
  setzt DATEN_DIR auf den Projektordner. Hintergrund: web/main.py liest die
  .env selbst NICHT (nur die Pipeline tut das über pipeline/env.py) — ohne
  das Skript bricht uvicorn mit "Fehlende Umgebungsvariable" ab. In der .env
  stehen dafür WEB_SECRET (Cookie-Signatur) und WEB_COOKIE_SECURE=0 (lokal
  ohne HTTPS; auf dem Server gehört dort 1 hin). Anmeldung über users.yaml
  im Projektordner (nicht im Repo).
- Das Repo liegt seit dem 04.08.2026 auf GitHub:
  https://github.com/kkrasnniqi-ket/ai-coldmailing-system (privat, Konto
  von Keti). Push läuft über das aktive gh-Konto `kkrasnniqi-ket`;
  Commit-Autor ist global auf Keti eingestellt. Schlüssel (.env),
  users.yaml und HAR-Mitschnitte bleiben per .gitignore draußen.
- Die erste Pipeline und das Team-Interface sind gebaut. Instantly wird
  weiter als Versand-Motor genutzt.
- Phase 1 des Wholix-Nachbaus (Kampagnenübersicht und -detail) ist gebaut:
  Live-Werte werden lesend aus Instantly aufbereitet, fehlende Werte werden
  nicht erfunden, und der Link führt zu den Kampagnen-Einstellungen in
  Instantly.
- Phase 2 des Wholix-Nachbaus ist gebaut: Freigabe je Empfänger und
  E-Mail-Schritt, Suche, Filter, Sammelaktionen, einzelne Neuerzeugung,
  vollständige Übergabesperre, lesender Instantly-Stand und die erweiterte
  globale Sperrliste.
- Der vereinbarte kleine Teil von Phase 3 ist gebaut: Im internen Postfach
  kann das Team auf eine bestehende empfangene Instantly-Mail antworten.
  Das Absenderkonto ist sichtbar und kommt aus den belegten Instantly-Daten.
  Eine 15 Minuten gültige Signatur bindet Kontakt und Mail; ein atomarer
  Einmalverbrauch verhindert wiederholten Versand mit demselben Beleg.
  Bei einem unklaren Ausgang gibt es keine automatische Wiederholung und
  keinen neuen Sendeknopf, bis der Verlauf in Instantly geprüft wurde.
- Frische Gesamtkontrolle am 22.07.2026: 518 Tests grün. Einen einzigen
  langen Testprozess beendet das System wiederholt ohne Testfehler und ohne
  Abschlussmeldung; deshalb wurden alle Tests vollständig in sieben frischen
  Blöcken ausgeführt. Die einzige Warnung ist die bekannte
  Starlette-Abkündigung im TestClient.
- Die Sichtprüfung lief lokal mit festen Testdaten. Desktop und 390-px-
  Ansichten von Übersicht und Detail sind festgehalten. Bei 390 px liegt die
  Navigation oben; die Übersicht hat volle Inhaltsbreite, keinen Dokument-
  Überlauf und nur die Tabelle scrollt intern.
- Am 22.07.2026 wurde Phase 1 zusätzlich rein lesend gegen das echte
  Instantly-Konto geprüft. Die fünf geprüften GET-Endpunkte für Kampagne,
  Kennzahlen, Schrittwerte, Konten-Tageswerte und Postfächer antworteten mit
  HTTP 200; es wurden keine Namen, Adressen oder Kennzahlen ausgegeben und
  keine Daten verändert. Instantly lieferte für den heutigen Tageszeitraum
  keine Zeile, daher zeigt das Tool den Tagesverbrauch zuverlässig als
  unbekannt statt als erfundene Null.
- Die Kampagnenansicht nutzt die Empfängerzahl von Instantly. Die Zahl des
  zuletzt freigegebenen Laufs wird im Detail getrennt gezeigt. Der heutige
  Versand wird aus der täglichen Konten-Auswertung nur für die verwendeten
  Absenderpostfächer summiert. Die Absender werden als Pflichtfilter
  übergeben; der Zeitraum reicht von heute bis zum Folgetag. Ein Ausfall
  dieser einzelnen Auswertung macht die übrigen Live-Werte nicht unbekannt.
- Ein zuletzt bekannter Postfachstand bleibt bei einem späteren Lesefehler
  sichtbar und wird mit der Fehlerzeit gekennzeichnet. Kampagnentabelle,
  Fehlermeldungen und Zahlenfarben sind auch für Tastatur und Lesesoftware
  verständlich geprüft.
- Die Sichtprüfung für Phase 2 lief nur mit festen lokalen Testdaten. Die
  Nachweise liegen unter `.superpowers/phase-2/`: Freigabeübersicht,
  Prüftabelle, Textdialog, schreibgeschützte Übergabe, Sperrliste sowie beide
  390-px-Ansichten. Auf 390 px gibt es keinen seitlichen Überlauf der ganzen
  Seite; nur die breiten Tabellen scrollen in ihrem eigenen Bereich.
- Der dauerhafte Arbeitsnachweis steht in Jira unter `AP-199` und ist als
  erledigt markiert.
- Kontrollierter End-to-End-Test am 23.07.2026: Eine eigene Instantly-
  Testkampagne hatte genau einen Absender, einen Schritt, Tageslimit eins und
  `ingeborgmarder@gmail.com` als einzigen Empfänger. Die Mail wurde um 10:09
  Uhr zugestellt, die einmalige Testantwort um 10:10 Uhr von Instantly
  übernommen und im eigenen Postfach sichtbar angezeigt. Die Kampagne wurde
  direkt nach dem Versand pausiert.
- Der Live-Test fand und belegte drei Instantly-Abweichungen, die behoben
  wurden: `/leads/list` erwartet den Filter `campaign`, Aktivieren/Pausieren
  darf keinen JSON-Inhaltstyp ohne Inhalt senden und echte E-Mail-Schritte
  kommen als `0_0_0`, `0_1_0`, `0_2_0`. Die Korrekturen sind mit zuerst
  fehlschlagenden Gegentests abgesichert.
- Frische Gesamtkontrolle am 23.07.2026: 520 Tests grün in einem vollständigen
  Lauf. Es bleibt nur die bekannte Starlette-Abkündigungswarnung.
- Der Nachweis zum kontrollierten End-to-End-Test steht in Jira unter
  `AP-200` und ist als erledigt markiert.
- Frische Gesamtkontrolle der Antwortfunktion am 23.07.2026: 550 Tests grün
  in einem vollständigen Lauf. Es bleibt nur dieselbe bekannte
  Starlette/httpx-Abkündigungswarnung.
- Die sichtbare Prüfung nutzte ausschließlich feste lokale Testdaten und
  eine Demo ohne Versandroute. Die Nachweise liegen unter
  `.superpowers/phase_3/`: `postfach-antwort-desktop.png`,
  `postfach-antwort-390.png`, `postfach-antwort-erfolg-desktop.png` und
  `postfach-antwort-unklar-390.png`. Desktop und 390-px-Ansicht haben keinen
  seitlichen Seitenüberlauf; beim unklaren Ausgang bleiben Entwurf und
  Hinweis sichtbar, aber Antwortfeld und Sendeknopf fehlen.
- Für den Bau und die lokale Prüfung wurde keine echte E-Mail versendet und
  kein Gmail-/Microsoft-Zugang eingerichtet oder gespeichert.
- Anbieter-Vergleich vorbereitet (23.07.2026): Bevor der CRM-Ausbau beginnt,
  soll der Datenanbieter für deutsche Kleinfirmen per Messung entschieden
  werden. Dafür ist alles Lokale gebaut und mit Tests belegt (577 Tests grün):
  ein Prospeo-Baustein (`pipeline/sources/prospeo.py`, Suche über die
  Firmen-Domain plus Anreicherung nur geprüfter Mails) und ein
  wiederaufnehmbarer Vergleichs-Läufer (`pipeline/vergleich.py`), der Weg A
  (Apify→Prospeo) und Weg B (Apify→Hunter→Dropcontact) über dieselbe
  Apify-Firmenliste schickt und Bericht + Rohdaten in einen Lauf-Ordner
  schreibt. Achtung Benennung: im älteren Code von `pipeline/sourcing.py`
  heißt Hunter→Dropcontact noch „Weg A"; im Vergleich gilt die neue
  Benennung aus dem Auftrag (Weg A = Prospeo). Es wurde noch keine echte
  Anbieter-Abfrage ausgeführt; es fehlen die Schlüssel PROSPEO_API_KEY,
  HUNTER_API_KEY und DROPCONTACT_API_KEY sowie Leonards Okay für den
  Guthaben-Verbrauch (Gratis-Kontingente laut offiziellen Seiten am
  23.07.2026: Prospeo 100 Credits/Monat, Hunter 50 Credits/Monat,
  Dropcontact 50 Gratis-Credits).
- Kaskade nach Chef-Vorgabe gebaut (23.07.2026, per Leonard übermittelt):
  Google Maps liefert die Firmen (übernommen wird v. a. die Website),
  danach versuchen die Anbieter-Stufen aus `anbieter_reihenfolge` in der
  Kunden-Datei NACHEINANDER den Entscheider mit geprüfter persönlicher
  Mail zu finden („findet Stufe 1 nur 80 von 100, versucht Stufe 2 die
  restlichen 20"); wer übrig bleibt, bekommt info@ — neu: vor der
  Übernahme über Hunters Email Verifier geprüft (invalid/disposable/
  unknown wird verworfen, Ausgang „info_ungueltig"). Der Bericht zählt
  je Stufe, wer geliefert hat (`deckung.je_stufe`), und der
  Vergleichsbericht rechnet die Kombination beider Wege aus
  („Kaskade"-Abschnitt). Standard bleibt einstufig Hunter→Dropcontact,
  bis der Anbieter-Vergleich die Reihenfolge festlegt. 592 Tests grün.
- Messlauf am 23.07.2026 mit echten Gratis-Konten über die 20 echten
  Firmen (IT-Dienstleister Hannover, Liste vom 21.07.): Weg A (Prospeo)
  6 geprüfte persönliche Mails, Weg B (Hunter→Dropcontact) 7; auf den
  16 von beiden geprüften Firmen je 6 (37,5 %), Kombination 8 von 16
  (50 %) — jeder Weg rettet Firmen, die der andere nicht kennt. Keine
  fremden Domains. Vier Firmen blieben bei Weg A offen (Tageslimit des
  Prospeo-Gratis-Kontos), bewusst nicht nachgezogen. Qualitäts-Vorbehalt:
  einige Treffer tragen Titel wie „Product Owner"/„Director" (kein
  Inhaber) — Handprüfung durch Leonard steht aus. Live-Funde behoben:
  Prospeo-„NO_RESULTS" ist kein Fehler, Prospeo drosselt (~45 Suchen/Tag
  frei), Dropcontact braucht bis ~2 Minuten Abholzeit, deutsche
  Titelformen („Geschäftsführender Gesellschafter") und falsche Freunde
  („Product Owner") im Rollen-Abgleich. Ergebnisse liegen unter
  `laeufe/vergleich-anbieter/2026-07-23-prospeo-20-firmen-v2/`
  (bericht.md mit Handprüfungs-Spalte). Echten Credit-Verbrauch in den
  Anbieter-Dashboards gegenprüfen, bevor Preise je Kontakt gerechnet
  werden.
- Kontrollierter Live-Test am 23.07.2026: Das neue Antwortfeld sendete genau
  eine klar gekennzeichnete Testantwort über Instantly von
  `email@seo-poleposition.online` an das eigene Testkonto
  `ingeborgmarder@gmail.com`. Instantly bestätigte den Versand, die
  ausgehende Nachricht erschien direkt im internen Verlauf und Gmail zeigte
  sie um 11:42 Uhr als dritte Nachricht desselben Threads. Gmail war dabei
  nur das Testziel und wurde weiterhin nicht an das Tool angebunden.

- Messung „Impressum-Name → Dropcontact" am 23.07.2026 (Olivers Frage nach
  dem Weg zu 80 %): Bei 6 der 8 Lücken-Firmen stand der Chef-Name im
  Impressum; aus allen 6 Namen baute und prüfte Dropcontact eine
  persönliche Mail (100 %). Neue Gesamtabdeckung 14 von 16 Firmen
  (87,5 %) — über dem 80-%-Ziel. Details und Vorbehalte (Handarbeit,
  JavaScript-Impressum, abweichende Mail-Domains, veraltbare Impressen):
  `laeufe/vergleich-anbieter/2026-07-23-prospeo-20-firmen-v2/impressum-messung.md`.
  Der BAU der Impressum-Stufe ist NICHT begonnen — er braucht Olivers
  Okay (berührt die Projektregel „kein selbst gebautes Fundament") und
  einen abgesegneten Bauplan.

- Olivers Großauftrag (24./27.07.2026) ist gebaut und wartet nur noch auf
  die API-Schlüssel der neuen Firmen-Konten: Impressum-Stufe (KI liest
  Chef-Namen, Dropcontact prüft; alle Messlauf-Sonderfälle als Tests),
  Listen-Import (319er-Liste PLR 30–39 liegt unter
  `laeufe/plr30-39/firmen.json`), wiederaufnehmbares Großlauf-Skript
  (`python -m pipeline.grosslauf`) mit Dubletten-Meldung und Bericht im
  Oliver-Format. Kaskade des Laufs: prospeo → impressum → info@
  (ungeprüft markiert, Prüfung vor Versand über künftiges
  Hunter-Firmenkonto von x@redschlag.de). Abos: Prospeo Starter 49 $ +
  Dropcontact Starter 29 €, Kets Karte, von Oliver freigegeben.
  616 Tests grün, Stand committet.

- Versandstart-Vorbereitung am 28.07.2026 (Bauplan:
  `docs/bauplan-versandstart-it-dienstleister.md`, Olivers 3-Stufen-Sequenz:
  `docs/email-sequenz-it-dienstleister.md`): Alle API-Schlüssel liegen in
  der `.env` und funktionieren (Instantly-Schlüssel neu, getestet; Achtung:
  Cloudflare blockt Python-urllib ohne Browser-Kennung — sieht aus wie 403).
  Gebaut und grün (603 Tests): Hunter-Prüfung der info@-Adressen im
  Großlauf (Pflicht-Schlüssel), Kampagnen-Baukasten mit echtem Namen/
  Absendern/Betreffs je Stufe, Lead-Import mit {{anrede}}-Variable samt
  harter Sperre gegen fehlende Anreden, Text-Wache
  (`python -m pipeline.kampagnen_pruefung`, Referenz unter
  `laeufe/plr30-39/kampagne-referenz.json`). Die Kampagne
  „Partnerschafts-Anfrage IT-Dienstleister PLR 30-39"
  (id e9f33e56-d753-49ce-92c8-b6915808e969) ist als inaktiver Entwurf in
  Instantly angelegt: echte Texte in den Stufen (Weg B), Abstände 7+7 Tage,
  20/Tag, Mo–Fr 8–19 Uhr, Absender-Anzeigename „Oliver Redschlag".
- Wholix-Anschreiben gesichert (28.07.2026, Olivers Auftrag vom 26.07.):
  alle 194 Sequenzen (Body 1–3, Status, 5 Antworten) plus Master-Prompt
  liegen unter `wholix-export/`. Erkenntnis: Follow-ups 2/3 waren feste
  Prompt-Vorlagen, individuell generiert wurde nur Mail 1.

- Leadquellen-Fundament gebaut und Voll-Scrape gelaufen (29.07.2026,
  Olivers Auftrag; Bauplan: `docs/bauplan-leadquellen-fundament.md`):
  Drei neue Quellen-Bausteine (Gelbe Seiten via Apify-Firmenkonto,
  OpenStreetMap/Overpass mit Ausweich-Server, Google-Maps-Gebietsraster
  asynchron) plus Fusions-Baustein mit Olivers Branchen-Ausschlüssen.
  Ergebnis: **1.481 einzigartige IT-Dienstleister der PLR 30+31**
  (`laeufe/leadquellen/plr-30-31/`), alte 319er-Liste nur noch
  Auffüller (56 übernommen, GF-Hinweise erhalten). Scrape-Kosten ~7 $.
- Anbieter-Lage neu (29.07.2026): Prospeo-Konto bei deren API-Umbau
  stillgelegt (Schlüssel tot, Login tot) -> Kaskade läuft ohne Prospeo,
  Impressum-KI ist Hauptstufe. OpenRouter tot -> KI läuft über Leonards
  OpenAI-Schlüssel (KI_MODELL=gpt-4.1-mini). Dropcontact: neues Konto,
  500 Credits/Monat -> Adress-Bau in Monats-Paketen à ~450 Firmen
  (passt zu Olivers 20/Tag). Hunter frei: 50 Suchen + 100 Prüfungen.
  North Data gestrichen (hat keine E-Mails, nur Namen).
- Endgültige Versandliste steht (11.08.2026): Oliver hatte seine
  Streichungen im 450er-Paket FARBLICH markiert (rot) statt Zeilen zu
  löschen — ein CSV-Export verliert diese Farben, deshalb braucht es
  immer die .xlsx. 56 rote Firmen; 47 davon hatten wir am 30.07. schon
  aussortiert (Einigkeit), 9 waren noch drin und sind jetzt raus.
  Ergebnis: `laeufe/leadquellen/plr-30-31/paket-1/versandliste-endgueltig.xlsx`
  mit 320 Zeilen / 317 Firmen (drei Firmen stehen doppelt mit zwei
  Webseiten — CM Systemhaus, Veniris, S2-Datentechnik; welche URL gilt,
  ist noch von Hand zu entscheiden). Werkzeuge dafür neu:
  `pipeline/oliver_markierungen.py` (report / streichen / ungesehen) und
  `pipeline/liste_als_json.py`.
- Anrede: Werkzeug `pipeline/anrede_spalte.py` steht (Regel wie geplant,
  lieber neutral als falsch). WICHTIG, am 11.08.2026 im Probelauf
  gelernt: Die Anrede darf erst NACH dem Datenlauf gebaut werden. Wird
  sie aus der Firmenliste gebaut, nimmt sie den ERSTEN im Impressum
  genannten Chef - der Datenlauf erreicht aber oft einen anderen. Bei
  20 Firmen hätten so 3 Kontakte den falschen Namen in der Anrede
  gehabt (IKN: Giffhorn statt Kassebom, comNET: Peters statt Frings,
  List + Lohr: List statt Lohr). Deshalb gilt der Modus
  `anrede_spalte.py aus-lauf <ergebnisse.json>`; die Anrede-Spalte in
  `versandliste-endgueltig.xlsx` ist nur ein Entwurf und wird ersetzt.
- Voller Datenlauf FERTIG (11.08.2026): 317 Firmen, **214 persönliche
  geprüfte Mails (67,5 %)**, 65 geprüfte info@, 23 info@ als nicht
  zustellbar verworfen, 15 offen. Versandfertige Tabelle:
  `paket-1/versandfertig-final.xlsx` (279 Kontakte, davon 214 mit
  Anrede sofort versandfertig; Blatt "Zur Kontrolle" sammelt 115
  Fälle für einen menschlichen Blick).
  Die Quote liegt unter den 90 % des Probelaufs, und das ist echt, nicht
  technisch: 10 Firmen ohne Treffer wurden gegengeprüft, indem sie
  einzeln (alter Weg) noch einmal durch Dropcontact liefen - 0 von 10
  lieferten auch dort etwas. Die ersten 20 waren die grossen Firmen der
  alten kuratierten Liste; der Rest sind Ein-Personen-Betriebe, die
  Dropcontact schlicht nicht kennt. Das Impressum-Lesen selbst lief
  sauber: 261 von 263 Webseiten gaben einen Namen her.
- Neuer Motor `pipeline/schnelllauf.py` (11.08.2026): gleiche Kaskade,
  gleiche Prüfungen, aber Webseiten parallel und Dropcontact im Batch
  (dessen API nimmt eine ganze Liste; wir haben sie immer mit genau
  einem Namen benutzt). 263 Firmen in ~12 Minuten statt ~4 Stunden.
  Credits bleiben gleich, weil je Runde nur der ERSTE Impressum-Name
  gefragt wird und nur leer ausgegangene Firmen den zweiten kosten.
  Zwei Lehren, beide mit Tests festgenagelt:
  (1) Ein Batch ist bezahlt, sobald Dropcontact ihn annimmt. Das alte
  2-Minuten-Fenster reichte für 100 Namen nicht, der Lauf warf einen
  bezahlten Batch weg (per request_id von Hand zurückgeholt). Jetzt:
  eigenes 15-Minuten-Fenster, request_id landet VOR dem Abholen auf der
  Platte, und `zwischenstand.json` hält gelesene Webseiten, bezahlte
  Adressen und offene Aufträge fest. Beim nächsten Start wurden so 103
  Adressen gratis nachgeholt.
  (2) Die Zuordnungs-Wache darf nicht zu eng sein: Dropcontact dreht
  Vor- und Nachnamen ("Peter-Christoph Haider" -> "Haider
  Peter-Christoph"). Abgebrochen wird nur, wenn WEDER Name NOCH Domain
  passen; abweichende Namen werden als Hinweis am Kontakt vermerkt.
- Drei Entscheidungen zur Versandliste (Keti, 11.08.2026):
  (1) Die 65 info@-Adressen werden angeschrieben, mit einer Anrede ohne
  Namen. Das Mail-Muster steht fest als "Guten Tag {{anrede}}," - dort
  passt "Sehr geehrte Damen und Herren" nicht hinein, "zusammen" schon.
  Also `anrede = "zusammen"` -> "Guten Tag zusammen,".
  (2) Die 36 abweichenden Mail-Domains werden ohne Handprüfung
  akzeptiert. Sie stehen weiter im Blatt "Zur Kontrolle", falls später
  doch jemand draufschauen will; auffällig sind vor allem
  kleinert-pcservice (gmx.eu, Freemailer) und Bell (bell.net aus einem
  falsch geteilten Namen).
  (3) Die 119 Firmen, die Oliver nie gesehen hat, gehen NICHT vorab zu
  ihm. 96 davon stehen in der Versandliste (78 mit persönlicher Mail) -
  sie würden also ohne seine Freigabe angeschrieben. Vor der Aktivierung
  ist das der Punkt, an dem es Leonard/Oliver auffallen kann.
- Kontakte in Instantly geladen (13.08.2026): Die 279 Kontakte aus
  `paket-1/versandfertig-final.xlsx` liegen in der Kampagne
  `e9f33e56-d753-49ce-92c8-b6915808e969`. Sie heißt jetzt
  "Partnerschafts-Anfrage IT-Dienstleister PLR 30-31" (vorher 30-39 -
  der Name stammte noch aus der alten 319er-Liste). Die Kampagne war
  leer und ist weiterhin **Status 0, also schlafend**; es wurde nichts
  versendet. Instantly hat aus den 279 hochgeladenen Zeilen **277**
  gemacht: die beiden doppelten Adressen (bergemann@nexave.de und
  maik.bandolie@kesolutions.gmbh, je zwei Firmen) hat es selbst
  zusammengeführt - niemand bekommt zwei Mails. Alle 277 tragen eine
  gefüllte {{anrede}}.
  Nächste Schritte vor dem Aktivieren: fünf Beispiel-Mails ansehen,
  echte Testmail an ein eigenes Postfach, Text-Wache laufen lassen,
  danach Freigabe durch Leonard/Oliver.
- Kontrollierte Zustellprobe (13.08.2026): Eine eigene Test-Kampagne
  `7924e36f-e80d-4772-8bd6-e74c19832065` ("[TEST] Zustellprobe PLR
  30-31") mit EINEM Empfänger (d.keqmezi@digitaldiamonds.agency), einem
  Schritt und Tageslimit 1 hat um 11:23 Uhr eine echte Mail von
  `email@poleposition-automation.online` verschickt - Betreff und
  Anrede von Instantly korrekt zusammengesetzt. Direkt danach pausiert
  (Status 2). Die echte Kampagne blieb dabei unberührt und schlafend.
  Vorher lief die Text-Wache gegen `laeufe/plr30-39/kampagne-referenz.json`:
  keine Abweichungen.
- Sperre gegen Doppel-Läufe repariert (13.08.2026): Prozessnummern
  werden vom Betriebssystem wiederverwendet - eine Sperrdatei trug die
  Nummer 802, die inzwischen Notion gehörte, und hätte diesen Kunden
  dauerhaft blockiert. `_pid_lebt()` prüft jetzt zusätzlich, ob unter
  der Nummer wirklich ein "python -m pipeline"-Lauf steckt; die
  Sperrdatei notiert außerdem den Startzeitpunkt (alte Dateien mit
  nackter Zahl bleiben lesbar). Betraf nicht nur den Assistenten,
  sondern jeden Lauf und auch die Status-Anzeige.
- Hunter-Kontingent: **stellt sich am 02.09.2026 von selbst zurück**
  (Free-Plan, am 13.08. geprüft: 50/50 Suchen und 100/100 Prüfungen
  verbraucht). Es blockiert NICHTS am Versand - die 277 Kontakte in
  Instantly sind alle geprüft. Betroffen sind nur 15 Firmen, die
  ausschließlich eine selbst geratene info@-Adresse hätten; die warten
  bis September oder gehen dauerhaft auf die Anruf/Brief-Liste.
  Dropcontact kann das nicht ersetzen: es beantwortet "wie lautet die
  Adresse dieser Person", nicht "existiert diese Adresse" (am 13.08.
  gegengeprüft - für eine der 15 Firmen lieferte es gar nichts).
- Hunter-Kontingent für diesen Abrechnungszeitraum ist aufgebraucht
  (100 Verifikationen/Monat, HTTP 429). Betrifft nur info@-Adressen;
  die 214 persönlichen Mails prüft Dropcontact selbst. Die 15 offenen
  Firmen warten auf neues Kontingent - ungeprüft geht nichts raus.
- Probelauf 20 Firmen aus der endgültigen Liste (11.08.2026):
  18 persönliche geprüfte Mails (90 %), 2 geprüfte info@, keine Fehler.
  Zwei Firmen brauchten einen zweiten Anlauf (Dropcontact antwortete
  nicht rechtzeitig) - der Wiederaufnahme-Lauf holte beide nach.
  Ergebnis unter `paket-1/probelauf-20/`, versandfertige Tabelle in
  `probelauf-20/versandfertig-20.xlsx`.
- Offen bei Oliver: 119 Firmen der Versandliste kamen nach seiner
  Prüfung aus der Reserve dazu, er hat sie nie gesehen. Sie liegen für
  ihn getrennt in `paket-1/fuer-oliver-neue-119.xlsx`.
- Probelauf-Endstand (29.07.2026): 9 von 10 Firmen mit persönlicher,
  geprüfter Chef-Mail (90 %), 1 geprüfte info@. Kurzmeldungs-Baustein
  für Olivers tägliche Zahlen gebaut (`python -m pipeline.kurzmeldung`).
  Namens-Lauf (Impressum-KI über alle 1.481) läuft; Ergebnis unter
  `laeufe/leadquellen/plr-30-31/namenslauf.json`.
- Dokumentimi për Oliverin (19.08.2026 paradite):
  `docs/workflow-documentation.docx` + `docs/workflow-diagram.png` —
  anglisht e thjeshtë, si punon sistemi nga kërkimi deri te dërgimi,
  plus 4 kërkesat e reja të tij me vlerësim. Jira: AP-203 (Done).
  Ia dërgon Dafina vetë. (Shënim: kjo hyrje u shkrua edhe në mëngjes,
  por dosja u kthye diku gjatë ditës në gjendjen e commit-it të vjetër
  — hyrja u rishtua e përmbledhur më 19.08 pasdite.)
- Katër kërkesat e Oliverit TË NDËRTUARA (19.08.2026, plani me hapa e
  prova: `docs/bauplan-kerkesat-oliverit-2026-08-19.md`; 1.049 teste
  të gjelbra):
  (1) PLZ dhe qyteti ndamas kudo — burimet mbushin "ort", fusioni e
  lexon nga adresa një herë në ruajtje; hapi 4 dhe Excel me dy kolona;
  Excel ka edhe kolonën "Rolle"; "Anruf & Brief" tregon personin e
  gjetur edhe pa mail.
  (2) Familjet e shërbimeve (`pipeline/service_categories.py`):
  "Computer Services" = tërë familja IT — NJË hartë për formularin
  (chip "ganze Familie" te hapi 3), numëruesin live, filtrin dhe
  mbledhjen; për scraping me pagesë vetëm ~10 terma të kuruar.
  Përjashtimet e vjetra të Oliverit (hosting/automation/provider)
  mbeten në fuqi — konflikt i shënuar, vendos Oliveri.
  (3) Mbledhja deri-në-cak (`pipeline/firmen_sammeln.sammeln_bis_ziel`):
  numri i hapit 1 = caku; ort bosh = krejt Gjermania si radhë 96
  rajonesh postare; pas çdo rajoni fusion + dedup + numërim; ndalet kur
  arrihet caku ose shterohen burimet; mungesa raportohet me arsye
  (grund_ende, je_gebiet). CLI: `sammeln --ziel N --deutschland`.
  Kufizim i njohur: radhitja e rajoneve përdor numrin e PLZ-ve si
  proxy të dendësisë (Augsburg del i pari, jo Berlini).
  (4) Vendimmarrësit me prioritet (`pipeline/decision_maker.py`):
  CEO/GF → Inhaber → Gründer → Managing Director → drejtues tjetër;
  Impressum-AI kthen edhe rolin (+ LinkedIn vetëm kur shkruan aty);
  te firmen.json ruhen `entscheider` + `entscheider_primaer` EDHE pa
  mail të verifikuar ("ohne_mail"); rradha e parë e Dropcontact shkon
  te rangu më i mirë; firmat pa person mbeten ("kein_entscheider").
  Verifikimi i vërtetë (Deutschland / Computer Services / 100 firma,
  19.08.2026): 4.252 bruto → 3.530 unike (348 dublikata, 374 të
  përjashtuara nga rregullat e Oliverit), 829 qytete; mostra 100 firma:
  67 me vendimmarrës me emër+rol (Impressum-AI, 0 kredite Dropcontact),
  33 pa — mbeten të shënuara. Mësim: limiti i Maps ishte për TERM →
  35× mbi cak; formula u nda me numrin e termave (1.052 teste).
  Rezultatet: `laeufe/leadquellen/sammlung-verifikation-2026-08-19/`.
  Firmat e reja janë tash në bestand të formularit.
- Waterfall + baza master, inkrementi 1 (19.08.2026 mbrëma, specifikimi
  i madh i Oliverit; plani: `docs/bauplan-waterfall-master-db-2026-08-19.md`,
  përmbledhja për ekipin: `docs/waterfall-uebersicht.md`; 1.068 teste):
  (1) prioriteti i roleve NDRYSHUAR sipas radhës së re të Oliverit —
  Inhaber/Owner → CEO → Geschäftsführer/MD → Gründer → tjetër;
  (2) përjashtimi i ofruesve të automatizimit i lidhur në lauf
  (webseite+KI PARA çdo shpenzimi; fusha offers_automation_services etj.;
  firmat mbeten të ruajtura, s'marrin as kredit as telefonatë; formulari
  e ndez vetë me `wettbewerber_pruefung: true` në kunden-file);
  (3) regjistri i ofruesve `pipeline/providers.py` + CLI `anbieter`
  (LinkedIn/Apollo/Clay/North Data të shpallur "nicht implementiert" —
  pa integrime të shpikura); (4) bericht i mbledhjes numëron
  vorher_bekannt/neu kundrejt bestand-it; (5) `pipeline/master_db.py`:
  daten/master.db E RIGJENERUESHME (companies/company_sources/
  decision_makers, plotësia, campaign_eligible i rreptë sipas pikës 16 —
  mbi të dhënat reale 4.969 firma / 5.713 dëshmi / 99 vendimmarrës,
  kampagnenfähig 0 sepse asnjë firmë s'e ka ende kontrollin "no") +
  eksporti Excel me kolonat e Oliverit dhe vendimmarrësit A–E
  (CLI `master-db`, `master-export`). PYETJE E HAPUR: "MailCom" s'ekziston
  askund në projekt — duhet sqarim nga Oliveri; LinkedIn pret vendim
  ToS + qasje; North Data ishte hequr me vendim 29.07.
- FAZA 1 — Rregulli i rreptë i pranueshmërisë së fushatës (20.08.2026
  pasdite, urdhri pas auditimit `docs/audit-oliver-anforderungen-2026-08-20.md`;
  1.069 → **1.080 teste**): Sammeladresat (info@, contact@, office@ ...)
  NUK bëhen më kurrë marrës fushate — as të verifikuara, as (vrima e
  vjetër) të paverifikuara pa verifikues. Ruhen si informacion firme
  (`info_email` + `info_pruefstatus` te firmen.json, ausgang i ri
  "ohne_persoenliche_mail", campaign_eligible=false me arsye
  "personal_decision_maker_email_missing"/"no_decision_maker") dhe firma
  del te fleta "Anruf & Brief". Mbrojtje në 4 shtresa
  (`pipeline/campaign_eligibility.py`): (1) krijimi i lead-it në
  sourcing/schnelllauf/grosslauf (të tre kalojnë nga e njëjta rrugë),
  (2) filtri para tekstit te lauf() (mbron lëshimet e VJETRA të
  rifilluara), (3) dorëzimi `_versand_ausfuehren` filtron + e shënon
  te `versand_ausgeschlossen.json` pa e prekur historikun, (4) porta
  përfundimtare në InstantlySender refuzon ME ZË (përjashtim vetëm
  Ansichts-Probe me `eigene_adresse=True` — dërgim te vetja).
  Deckungsquote numëron tash VETËM kontakte personale; kampanja e vjetër
  e fjetur në Instantly mbetet e paprekur. 17 teste të vjetra u
  përditësuan me sjelljen e re, 11 të reja (10 rastet e detyrës + 1).
  FAZA 2 (klasifikimi i pool-it) PRET MIRATIM.
- FAZA 2 E PËRFUNDUAR (20.08.2026 mbrëma; 1.088 teste): klasifikuesi i
  automatizimit me TRI dalje (yes/no/uncertain) — prompt-i i ri dallon
  automatizimin industrial (SPS/Gebäude → JO konkurrent) dhe produktet
  softuerike nga oferta e vërtetë e automatizimit; faqe e palexueshme =
  uncertain PA thirrje LLM e PA gjykim nga emri; unsicher = i ruajtur,
  jashtë fushate (automation_uncertain), 0 cent. Dy benchmark-e
  100-firmëshe (v1 $0.042 → 4 FP; v2 $0.040 → 0 FP të qarta, 1 kufitar
  inSyca i dokumentuar). POOL-I I PLOTË i klasifikuar
  (`python -m pipeline automation-check`, i rifillueshëm):
  **4.964 firma → 410 yes (8.3%), 2.881 no, 1.673 uncertain**;
  urteil-et te daten/automation-klassifikation.json, ripërdoren nga
  lëshimet e fushatës (0 kosto të dyfishta) dhe nga master.db.
  Pas rindërtimit: **kampagnenfähig 60** (automation no + vendimmarrës
  + email personal i verifikuar); 2.821 "no"-firma presin vetëm
  pasurimin (no_decision_maker). Kosto totale e Fazës 2: ~$1.5 OpenAI.
  Mbetje të njohura: 1.673 uncertain (përmirësohen me render-fallback
  Chrome — inkrement i ardhshëm), 5 not_checked (çelës emri pa domain).
  FAZA 3 (benchmark-u i burimeve) PRET MIRATIM.
- Testimi i burimeve, hapi A — falas (20.08.2026, përgjigje ndaj
  email-it të Oliverit "test which sources are useful and in what
  order"; Apollo/Clay etj. i sqaroi si vetëm ide): fusioni raporton tash
  `je_quelle_einzigartig` / `je_quelle_kennt` (kontributi EKSKLUZIV i
  çdo burimi — 1.069 teste). Numrat realë: mbledhja e verifikimit
  3.530 firma → Maps njeh 2.579 (2.511 vetëm ai, 71%), Gelbe Seiten
  729 (711 vetëm ai, 20%), Overpass 292 (239 vetëm ai, 7%) — burimet
  GATI S'MBIVENDOSEN, secili sjell firma që tjetri s'i njeh; krejt
  bestand-i (4.964): 73/15/7% + lista e vjetër 1%. Raporti për Oliverin:
  `docs/source-comparison-report.docx` (anglisht, me planin e matjeve
  B/C dhe pyetjen MailCom). Hapi B (bake-off €-për-kontakt me ~150
  kredite Dropcontact) pret okay të Dafinës; hapi C (North Data/Apollo/
  Clay/LinkedIn mbi të njëjtin kampion) pret llogari + vendim.

## Entscheidungen

- Instantly bleibt der unsichtbare Versand-Motor. Das Tool liest seine Daten
  für die Kampagnenansicht; echte Schreibaktionen sind nicht Teil der
  lokalen Prüfungen.
- Das Gmail-Testkonto dient ausschließlich als ungefährliches Testpostfach.
  Es wird nicht dauerhaft mit dem Tool verbunden. Eine direkte Gmail-
  Anmeldung, gespeicherte Google-Zugänge oder ein dauerhafter Mail-Abgleich
  sind nicht freigegeben.
- Der erfolgreiche End-to-End-Test ändert daran nichts: Gmail war nur
  Empfänger und Absender der manuellen Testantwort. Unser Tool erhielt keinen
  Gmail-Zugang; Versand und Antwortabruf liefen ausschließlich über Instantly.
- Am 23.07.2026 wurde der verkleinerte Umfang von Phase 3 festgelegt:
  Das interne Postfach darf über den offiziellen Instantly-Endpunkt auf eine
  bestehende empfangene Kampagnenmail antworten. Es gibt weiterhin keine
  direkte Gmail-/Microsoft-Verbindung, keinen freien Mailversand und keinen
  vollständigen Postfach-Abgleich.
- Der Bau und sein Nachweis stehen in Jira unter `AP-201`; die Aufgabe ist
  mit dem vollständigen Test- und Sichtnachweis als erledigt markiert.
- Der testgetriebene Bauplan steht unter
  `docs/superpowers/plans/2026-07-23-instantly-antworten.md` und wurde
  vollständig umgesetzt.
- Kampagnen-Einstellungen (Tageslimit, Sendefenster, Signatur und ähnliche
  Werte) werden nicht im Tool nachgebaut. Der Weg dafür ist der Link nach
  Instantly.
- Verlässliche Instantly-Felder werden gezeigt. Für „fehlgeschlagen" und
  nicht getrennt gelieferte Warteschlangen-Zustände zeigt die Oberfläche
  keinen geschätzten Wert.
- Instantly und der freigegebene Lauf bleiben getrennte Datenquellen: Live-
  Kennzahlen und Warteschlange beruhen auf Instantly; der lokale Lauf wird
  nur als eigener Vergleichswert gezeigt.
- Der Warteschlangenring verrechnet Unzustellbare nicht als eigene Gruppe.
  Er zeigt nur „versendet" und den Rest „nicht getrennt verfügbar".
  Unzustellbare stehen mit einem Überschneidungshinweis getrennt darunter.
- Die zusammengefasste Zahl aktiver Kampagnen wird nur berechnet, wenn alle
  berücksichtigten Kampagnen einen bekannten Status haben.
- Die neun am 22.07.2026 gestrichenen Wholix-Funktionen bleiben gestrichen;
  insbesondere keine Benutzerverwaltung, Calls, Notizen oder AI-Chat.
- In Phase 2 zeigt jede Prüftabelle genau eine E-Mail-Runde. Jeder der drei
  Schritte wird einzeln bestätigt; mehrere Empfänger können gesammelt
  bestätigt werden. An Instantly geht weiterhin nur die vollständig
  bestätigte Runde.
- Ein ungeeigneter Text wird nicht frei bearbeitet, sondern genau für diesen
  Schritt neu erzeugt. Unbekannte Instantly-Zustände bleiben unbekannt.
- Die globale Sperrliste erhält Grund und Kommentar sowie Muster wie
  `*.bund.de`; alte einfache YAML-Einträge bleiben lesbar.
- Die Instantly-Abfrage der Freigabe ist rein lesend und konservativ. Nur bei
  genau einer ausgehenden E-Mail in einem Verlauf wird eine Antwort diesem
  Schritt zugeordnet. Bei mehreren möglichen Schritten bleibt die Zuordnung
  unbekannt, während der belegbare Gesamtstand sichtbar bleibt.
- Nach der Übergabe ist die E-Mail-Runde im Tool schreibgeschützt. Eine
  einzelne Neuerzeugung macht nur den betroffenen Schritt wieder offen.

- CRM-Grundsatzentscheidungen getroffen (Leonard, 29.07.2026) — damit
  ist der CRM-Bau entsperrt, sobald er drankommt: (1) Kontakte fließen
  automatisch ins CRM, aber NUR wer geantwortet hat; (2) Verkaufsstufen
  wie Wholix, deutsch beschriftet (gegen die Screenshots prüfen);
  (3) Einzelnutzer Leonard; (4) Speicher: SQLite-Datenbankdatei im
  Datenverzeichnis. Die Wholix-Screenshots liegen wieder im Projekt
  (Ordner "wholix interface screenshots", von Leonards Desktop kopiert).

## Nächste Schritte

Fahrplan Versandstart (Basis ist jetzt die NEUE 1.481er-Liste, nicht
mehr die alte 319er — Details in beiden Bauplänen unter `docs/`):

- Namens-Lauf abwarten (läuft), dann Monats-Paket 1 (~450 Firmen mit
  gefundenem Namen, priorisiert) durch den Dropcontact-Adress-Bau —
  daraus Olivers Ergebnis-Auswertung (Gesamt, Quote, Anruf/Brief-Liste).
- Danach Anrede-Spalte je Kontakt füllen (Claude, neutral bei Unsicherheit)
  und komplett zur Kontrolle vorlegen.
- Geprüfte Kontakte mit Anrede in die Kampagne laden
  (`import_leads_mit_anrede`), 5 Beispiel-Mails plus echte Testmail an ein
  eigenes Test-Postfach zeigen, Text-Wache laufen lassen.
- Erst nach Freigabe durch Leonard/Oliver aktivieren; danach täglich
  Kurzmeldung mit den Zahlen an Oliver (Zuständigkeit für das Beantworten
  der Antworten vor dem Start klären).
- Später/parallel: CRM-Ausbau als eigenes Arbeitspaket entwerfen; weitere
  Wholix-Bereiche bleiben gestrichen, solange die Scope-Entscheidungen
  nicht ausdrücklich geändert werden.
- Schreibende Versand- oder Postfachprüfungen nur mit ausdrücklicher
  Freigabe und Testkonten.
