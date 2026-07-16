from datetime import datetime

def write_preview(store, texte_pro_lead, nacharbeit):
    zeilen = [f"# Freigabe-Vorschau",
              f"Fertig personalisiert: {len(texte_pro_lead)} | Nacharbeit: {len(nacharbeit)}", ""]
    for eintrag in texte_pro_lead[:3]:
        zeilen += [f"## {eintrag['email']}", f"Betreff: {eintrag['betreff']}", "",
                   eintrag["mail_1"], "", f"Follow-up 1: {eintrag['follow_up_1']}",
                   f"Follow-up 2: {eintrag['follow_up_2']}", "", "---", ""]
    zeilen.append("Freigeben mit: python -m pipeline freigeben <laufordner>")
    (store.run_dir / "freigabe-vorschau.md").write_text("\n".join(zeilen), encoding="utf-8")

def is_approved(store) -> bool:
    return (store.run_dir / "FREIGABE.txt").exists()

def approve(store):
    (store.run_dir / "FREIGABE.txt").write_text(
        f"Freigegeben am {datetime.now().isoformat()}\n", encoding="utf-8")
