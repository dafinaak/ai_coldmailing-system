"""Automatisierungs-Klassifizierung mit strukturierter Antwort.

Unterschied zum vorhandenen `branchen_filter.ist_wettbewerber()`: der
gibt {wettbewerber, unsicher, belege} zurueck. Hier wird zusaetzlich
verlangt, was der Auftrag vom 24.08.2026 fordert - eine Zahl fuer die
Sicherheit und die QUELLE, also die Seite, auf der der Beleg stand.
Der alte Baustein bleibt unangetastet; die Produktivstrecke benutzt
weiterhin ihn.

Die entscheidende Unterscheidung, an der die Pruefung haengt:

  Automatisierung als LEISTUNG fuer Kunden   -> YES
  Automatisierung im eigenen Haus benutzt    -> NO
  Automatisierung nur als Technologie erwaehnt -> NO
  Industrie-/Gebaeudeautomation (SPS, Maschinen) -> NO, andere Branche
  zu wenig oder widerspruechlicher Text      -> UNCERTAIN

UNCERTAIN ist ein vollwertiges Ergebnis, kein Fehler. Wer nicht klar
beurteilt werden kann, bekommt keine teure Anreicherung.
"""
import json
import re

SYSTEM_PROMPT = """Du prüfst EINE Frage über eine Firma:

VERKAUFT diese Firma Automatisierung selbst als Dienstleistung oder
Produkt an ihre Kunden?

Es geht NICHT darum, ob irgendwo das Wort "Automatisierung" vorkommt.
Es geht darum, ob Automatisierung ein ANGEBOT dieser Firma ist.

Antworte "YES" nur bei belastbaren Hinweisen auf ein solches Angebot:
- Automatisierungs-Beratung
- Workflow-Automatisierung als Dienstleistung
- Geschäftsprozess-Automatisierung als Dienstleistung
- RPA / Robotic Process Automation als Dienstleistung
- KI-Automatisierung, KI-Agenten als Dienstleistung
- Automatisierungs-Umsetzung / -Implementierung für Kunden
- Einführung von Automatisierungs-Plattformen für Kunden
  (n8n, Make, Zapier, Power Automate, Camunda ...)

Antworte "NO" - und das ist wichtig, hier wurde bisher zu oft falsch
"YES" gesagt - bei:
- MANAGED SERVICES. Auch dann, wenn dabei von Prozessoptimierung,
  Effizienz oder standardisierten Abläufen die Rede ist. Managed
  Services sind IT-Betreuung, kein Automatisierungs-Angebot.
- IT-Dienstleistung, die Automatisierung nur INTERN benutzt
  ("wir automatisieren unsere eigenen Abläufe", "automatisiertes
  Monitoring", "automatische Backups")
- SOFTWARE-PRODUKTEN, die Workflow- oder Automatisierungs-FUNKTIONEN
  enthalten, ohne dass die Firma Automatisierung als Leistung verkauft.
  Ein Projektmanagement-, DMS-, ERP- oder Compliance-Produkt mit
  Workflow-Funktion ist NO. Entscheidend ist: wird ein PRODUKT verkauft,
  das eine Funktion hat - oder wird die AUTOMATISIERUNG SELBST als
  Leistung verkauft? Nur das Zweite ist YES.
- Prozessoptimierung ohne ausdrückliches Automatisierungs-Angebot
- INDUSTRIE-Automatisierung: SPS/PLC, Steuerungstechnik, Maschinen-,
  Fertigungs-, Gebäudeautomation - andere Branche, kein Wettbewerber
- reiner IT-Betreuung: Support, Wartung, Netzwerk, Server, Hardware,
  Backup, Cloud-Migration, IT-Sicherheit

Prüfe vor einem "YES" gegen dich selbst: Könnte ein Kunde bei dieser
Firma "Automatisierung" BEAUFTRAGEN? Wenn du das aus dem Text nicht
belegen kannst, ist es kein YES.

Antworte "UNCERTAIN", wenn der Text zu dünn, zu allgemein oder
widersprüchlich ist. Zwinge keinen unklaren Fall in YES oder NO.
Lieber UNCERTAIN als ein falsches Urteil in eine der beiden Richtungen.

Der Text ist in Abschnitte geteilt, jeder beginnt mit "[Quelle: <URL>]".
Gib bei "evidence" ein wörtliches Zitat an und bei "source_url" die URL
des Abschnitts, aus dem das Zitat stammt.

Antworte AUSSCHLIESSLICH mit diesem JSON:
{"automation_status": "YES" | "NO" | "UNCERTAIN",
 "confidence": <Zahl zwischen 0.0 und 1.0>,
 "reason": "<ein Satz, warum>",
 "evidence": "<wörtliches Zitat von der Seite, oder leer>",
 "source_url": "<URL des Abschnitts mit dem Zitat, oder leer>"}"""

GUELTIG = ("YES", "NO", "UNCERTAIN")
_JSON = re.compile(r"\{.*\}", re.S)
_QUELLE = re.compile(r"\[Quelle:\s*([^\]]+)\]")


def unsicher(grund: str, quelle: str = "") -> dict:
    return {"automation_status": "UNCERTAIN", "confidence": 0.0,
            "reason": grund, "evidence": "", "source_url": quelle,
            "quelle": "regel"}


def klassifizieren(firma: dict, seiten_ergebnis: dict, ki) -> dict:
    """{automation_status, confidence, reason, evidence, source_url, quelle}.

    seiten_ergebnis ist die Rueckgabe von website_tiefe.seiten_lesen().
    Ohne lesbaren Text wird NICHT geurteilt - das waere Raten aus dem
    Firmennamen, und genau das hat die Eichung vom 20.08.2026 verboten."""
    status = (seiten_ergebnis or {}).get("status")
    text = (seiten_ergebnis or {}).get("text") or ""

    if status == "keine_webseite":
        return unsicher("Keine Webseite hinterlegt - nicht prüfbar")
    if status == "nicht_erreichbar":
        return unsicher("Webseite nicht erreichbar - nicht prüfbar")
    if status == "leer" or len(text.strip()) < 300:
        return unsicher("Zu wenig lesbarer Text auf der Webseite")
    if ki is None:
        return unsicher("Kein KI-Baustein verfügbar - es wird nicht geraten")

    seiten = ", ".join(s["url"] for s in (seiten_ergebnis.get("seiten") or []))
    prompt = (f"Firma: {firma.get('name', '')}\n"
              f"Webseite: {firma.get('website') or firma.get('domain', '')}\n"
              f"Gelesene Seiten: {seiten}\n\n"
              f"Webseiten-Text:\n{text[:18000]}")
    try:
        antwort = ki.frage(SYSTEM_PROMPT, prompt)
    except Exception as fehler:      # noqa: BLE001
        return unsicher(f"KI-Aufruf fehlgeschlagen: {fehler}")

    treffer = _JSON.search(antwort or "")
    if not treffer:
        return unsicher("KI-Antwort nicht lesbar")
    try:
        daten = json.loads(treffer.group(0))
    except ValueError:
        return unsicher("KI-Antwort war kein gültiges JSON")

    zustand = str(daten.get("automation_status") or "").strip().upper()
    if zustand not in GUELTIG:
        return unsicher(f"Unbekannter Status von der KI: {zustand!r}")

    try:
        sicherheit = float(daten.get("confidence") or 0.0)
    except (TypeError, ValueError):
        sicherheit = 0.0
    sicherheit = max(0.0, min(1.0, sicherheit))

    quelle_url = str(daten.get("source_url") or "").strip()
    # Eine erfundene Quelle ist schlimmer als keine: nur URLs
    # durchlassen, die wirklich gelesen wurden.
    gelesene = {s["url"] for s in (seiten_ergebnis.get("seiten") or [])}
    if quelle_url and quelle_url not in gelesene:
        passend = [u for u in gelesene if quelle_url.rstrip("/") == u.rstrip("/")]
        quelle_url = passend[0] if passend else ""

    return {
        "automation_status": zustand,
        "confidence": round(sicherheit, 2),
        "reason": str(daten.get("reason") or "")[:400],
        "evidence": str(daten.get("evidence") or "")[:600],
        "source_url": quelle_url,
        "quelle": "webseite+ki",
    }


def viele_klassifizieren(firmen: list, seiten_je_firma: dict, ki,
                         gleichzeitig: int = 6, log=print) -> dict:
    """{index: urteil} - jede Firma bekommt ein Urteil, nie ein Loch."""
    from concurrent.futures import ThreadPoolExecutor

    if not firmen:
        return {}

    def eine(paar):
        nummer, firma = paar
        return nummer, klassifizieren(firma, seiten_je_firma.get(nummer), ki)

    urteile = {}
    with ThreadPoolExecutor(
            max_workers=min(max(1, gleichzeitig), len(firmen))) as pool:
        for nummer, urteil in pool.map(eine, list(enumerate(firmen))):
            urteile[nummer] = urteil
    return urteile
