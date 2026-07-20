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

def approve(store, name: str | None = None):
    """Schreibt FREIGABE.txt. `name` ist optional (Standard None) fuer
    Abwaertskompatibilitaet mit dem CLI-Aufruf (pipeline.__main__.freigeben),
    der keinen angemeldeten Nutzer kennt; das Web-Interface (Task 5) ruft
    immer mit dem Namen der angemeldeten Person auf, damit spaeter sichtbar
    ist, wer freigegeben hat."""
    zeilen = [f"Freigegeben am {datetime.now().isoformat()}"]
    if name:
        zeilen.append(f"Freigegeben von {name}")
    (store.run_dir / "FREIGABE.txt").write_text("\n".join(zeilen) + "\n", encoding="utf-8")

def freigabe_info(store) -> dict:
    """Liest FREIGABE.txt und gibt {'am': str, 'von': str|None} zurueck -
    fuer die Web-Anzeige ('Freigegeben von X am Y'). Gibt leere Werte
    zurueck, wenn (noch) keine Freigabe existiert, statt zu werfen."""
    pfad = store.run_dir / "FREIGABE.txt"
    if not pfad.exists():
        return {"am": None, "von": None}
    am, von = None, None
    for zeile in pfad.read_text(encoding="utf-8").splitlines():
        if zeile.startswith("Freigegeben am "):
            am = zeile[len("Freigegeben am "):].strip()
        elif zeile.startswith("Freigegeben von "):
            von = zeile[len("Freigegeben von "):].strip()
    return {"am": am, "von": von}
