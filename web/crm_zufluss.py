"""CRM-Zufluss (Bauplan CRM-Verkaufsstufen, Schritt 2): Wer auf eine
Kampagnen-Mail geantwortet hat, wird automatisch als CRM-Kontakt
angelegt - Stufe "neuer_lead", je E-Mail-Adresse genau einmal
(Duplikat-Schutz sitzt im Speicher).

Konservative Regel (Entscheidung 29.07.2026): Ein Kontakt entsteht NUR,
wenn die Konversation mindestens eine ERHALTENE Nachricht enthaelt.
Nur-gesendete Verlaeufe (noch keine Antwort) erzeugen nichts.

Der Baustein ist bewusst rein: Er bekommt die fertig aufbereiteten
Konversationen des Postfach-Bereichs (instantly_leser.
konversationen_aus_email_stand-Format) plus optionale Anreicherung
(lokale Kontaktdaten, sprechende Kampagnen-Namen) und schreibt in den
KontakteSpeicher. Kein Netzwerk, kein eigener Abruf - er haengt sich an
den bestehenden Postfach-Abruf (Verdrahtung in Schritt 3).
"""


def antwortende_uebernehmen(speicher, konversationen, kontakt_info=None,
                            kampagnen_namen=None) -> int:
    """Legt fuer jede Konversation mit erhaltener Nachricht den Absender
    als Kontakt an. Gibt die Anzahl NEU angelegter Kontakte zurueck."""
    kontakt_info = kontakt_info or {}
    kampagnen_namen = kampagnen_namen or {}
    neu = 0
    for konversation in konversationen:
        erhaltene = [n for n in konversation.get("nachrichten") or []
                     if n.get("richtung") == "erhalten"]
        if not erhaltene:
            continue
        email = (konversation.get("kontakt_email") or "").strip().lower()
        if not email:
            continue
        campaign_id = erhaltene[0].get("campaign_id") or ""
        kampagne = kampagnen_namen.get(campaign_id, campaign_id)
        info = kontakt_info.get(email, {})
        if speicher.kontakt_anlegen(email,
                                    name=info.get("name", ""),
                                    firma=info.get("firma", ""),
                                    kampagne=kampagne):
            neu += 1
    return neu
