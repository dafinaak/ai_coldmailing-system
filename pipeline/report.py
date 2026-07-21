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
              f"- Ohne E-Mail übersprungen: {zahlen['ohne_email']}",
              f"- Verworfen: {zahlen['verworfen']} ({'; '.join(zahlen['gruende_verworfen']) or 'keine'})",
              f"- Personalisiert: {zahlen['personalisiert']}",
              f"- Nacharbeit: {zahlen['nacharbeit']}"]
    (store.run_dir / "bericht.md").write_text("\n".join(zeilen), encoding="utf-8")
