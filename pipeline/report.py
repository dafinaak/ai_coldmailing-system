def write_report(store, zahlen: dict):
    zeilen = ["# Lauf-Bericht", "",
              f"- Gefunden: {zahlen['gefunden']}",
              f"- Verworfen: {zahlen['verworfen']} ({'; '.join(zahlen['gruende_verworfen']) or 'keine'})",
              f"- Personalisiert: {zahlen['personalisiert']}",
              f"- Nacharbeit: {zahlen['nacharbeit']}"]
    (store.run_dir / "bericht.md").write_text("\n".join(zeilen), encoding="utf-8")
