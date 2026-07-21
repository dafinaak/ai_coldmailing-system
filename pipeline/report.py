def write_report(store, zahlen: dict):
    # "firmen_gesamt"/"firmen_mit_kontakt"/"deckungsquote_prozent" kommen aus
    # der Deckungsquote der 3-stufigen Lead-Beschaffung (Kern-Umbau, siehe
    # pipeline.sourcing.source_leads): Anteil der Google-Maps-Firmen, die am
    # Ende mindestens einen nutzbaren Kontakt (persönlich oder info@) haben -
    # die vom Chef geforderte "mindestens 80%"-Zahl.
    zeilen = ["# Lauf-Bericht", "",
              f"- Gefunden: {zahlen['gefunden']}",
              f"- Deckungsquote: {zahlen['firmen_mit_kontakt']}/{zahlen['firmen_gesamt']} "
              f"Firmen mit mindestens einem Kontakt ({zahlen['deckungsquote_prozent']}%)",
              f"- Firmen ohne Kontakt: {zahlen['ohne_email']}",
              # Outcome-Aufschluesselung (Apollo-422-Fix): trennt die
              # "Firmen ohne Kontakt"-Zahl oben nach dem WARUM auf - vorher
              # steckten "keine Webseite gefunden", "Apollo hat wirklich
              # nichts gefunden" und "technischer Fehler bei der
              # Anreicherung" ununterscheidbar in einer einzigen Zahl, was
              # den echten 422-Bug verschleiert hat. .get(..., 0) haelt
              # diese Zeile abwaertskompatibel zu alten Aufrufern, die diese
              # Schluessel (noch) nicht mitgeben.
              f"- Firmen-Ausgang: {zahlen.get('firmen_mit_kontakt_ausgang', 0)} mit Kontakt, "
              f"{zahlen.get('firmen_keine_webseite', 0)} ohne Webseite, "
              f"{zahlen.get('firmen_apollo_kein_treffer', 0)} kein Apollo-Treffer, "
              f"{zahlen.get('firmen_fehler', 0)} Fehler",
              f"- Verworfen: {zahlen['verworfen']} ({'; '.join(zahlen['gruende_verworfen']) or 'keine'})",
              f"- Personalisiert: {zahlen['personalisiert']}",
              f"- Nacharbeit: {zahlen['nacharbeit']}"]
    (store.run_dir / "bericht.md").write_text("\n".join(zeilen), encoding="utf-8")
