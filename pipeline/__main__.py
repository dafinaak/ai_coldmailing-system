import argparse, json, os, sys
from collections import Counter
from pathlib import Path
from pipeline.config import load_kunde, lade_globale_sperrliste
from pipeline.env import lade_dotenv, brauche_env as _brauche_env, brauche_env_eines_von as _brauche_env_eines_von
from pipeline.run_store import RunStore
from pipeline.sourcing import source_leads
from pipeline.dedupe import dedupe as dedupe_leads
from pipeline.website import fetch_text
from pipeline.ki import KI
from pipeline.personalize import personalisiere_mit_nachbesserung
from pipeline.quality import check
from pipeline.approval import write_preview, is_approved, approve
from pipeline.report import write_report
from pipeline.senders.instantly import InstantlySender
from pipeline.models import Lead

LAEUFE = Path("laeufe")

NEU_AB_REIHENFOLGE = ["leads", "dedupe", "personalisierung", "pruefung_ok"]

def _setze_schritte_zurueck(store, ab_schritt: str):
    """Loescht den JSON-Stand von ab_schritt und allen nachgelagerten
    Schritten (Reihenfolge: leads -> dedupe -> personalisierung ->
    pruefung_ok), damit 'lauf --fortsetzen ... --neu-ab ...' diese Schritte
    beim naechsten Durchlauf neu berechnet statt den alten Stand
    wiederzuverwenden. Eine bestehende Freigabe (FREIGABE.txt) wird dabei
    IMMER mitgeloescht: sie bezieht sich auf die alten Texte, und ein
    "senden" nach --neu-ab darf niemals unter einer Freigabe fuer laengst
    ueberholte Inhalte laufen. Der Lauf muss danach erneut geprueft und
    freigegeben werden."""
    start = NEU_AB_REIHENFOLGE.index(ab_schritt)
    for schritt in NEU_AB_REIHENFOLGE[start:]:
        store.delete_step(schritt)
    freigabe_pfad = store.run_dir / "FREIGABE.txt"
    if freigabe_pfad.exists():
        freigabe_pfad.unlink()
        print("Alte Freigabe verworfen (FREIGABE.txt gelöscht) - dieser Lauf "
             "muss nach --neu-ab erneut geprüft und freigegeben werden.")

_LEERE_DECKUNG = {"firmen_gesamt": 0, "firmen_mit_kontakt": 0, "quote_prozent": 0.0}

def lauf(kunde_pfad: str, limit: int, fortsetzen: str | None, neu_ab: str | None = None,
         firmen_datei: str | None = None):
    """Ein vollstaendiger Lauf.

    `firmen_datei` ist der Weg des Kampagnen-Assistenten: die Firmen
    stehen dann schon fest (im Assistenten von Hand ausgewaehlt), also
    wird die Suchstufe uebersprungen und die fertige Liste eingespeist.
    Alles danach - Entscheider-Suche, Sperrlisten, Personalisierung,
    Freigabe-Ordner - laeuft unveraendert weiter, damit der Assistent
    keine zweite, schwaecher gepruefte Strecke aufmacht.
    """
    # Reihenfolge folgt den Stufen der Lead-Beschaffung (Kaskade, siehe
    # pipeline.sourcing): Apify (Firmen) -> Anbieter-Stufen laut
    # Kunde.anbieter_reihenfolge (Standard: Hunter findet Entscheider,
    # Dropcontact baut/prueft die Mail; optional Prospeo als eigene Stufe) ->
    # info@-Regel mit Pruefung -> KI (Personalisierung, danach). Der Kunde
    # wird VOR den Env-Checks geladen, weil erst seine anbieter_reihenfolge
    # entscheidet, ob PROSPEO_API_KEY Pflicht ist.
    kunde = load_kunde(kunde_pfad)
    # Ohne Suchstufe kein Apify-Schluessel: eine fertige Firmenliste
    # braucht ihn nicht, und ein Pflichtfeld fuer etwas Ungenutztes
    # wuerde den Assistenten grundlos blockieren.
    if not firmen_datei:
        _brauche_env("APIFY_API_KEY")
    _brauche_env("HUNTER_API_KEY")
    _brauche_env("DROPCONTACT_API_KEY")
    prospeo_noetig = "prospeo" in (kunde.anbieter_reihenfolge or [])
    if prospeo_noetig:
        _brauche_env("PROSPEO_API_KEY")
    _brauche_env_eines_von("ANTHROPIC_API_KEY", "OPENROUTER_API_KEY", "OPENAI_API_KEY")
    store = RunStore.resume(fortsetzen) if fortsetzen else RunStore(LAEUFE, kunde.name)
    if neu_ab:
        _setze_schritte_zurueck(store, neu_ab)
    store.save_step("kunde_pfad", {"pfad": str(kunde_pfad)})
    print(f"Laufordner: {store.run_dir}")

    if not store.step_done("leads"):
        # prospeo_key nur mitgeben, wenn die Kaskade die Stufe auch nutzt -
        # so bleibt der Aufruf fuer den Standardfall unveraendert.
        zusatz = ({"prospeo_key": os.environ["PROSPEO_API_KEY"]}
                  if prospeo_noetig else {})
        if firmen_datei:
            from pipeline.grosslauf import ListenQuelle
            vorgegeben = json.loads(
                Path(firmen_datei).read_text(encoding="utf-8"))
            print(f"Feste Firmenliste: {len(vorgegeben)} Firmen aus {firmen_datei}")
            zusatz["apify_source"] = ListenQuelle(vorgegeben)
        # Die Impressum-Stufe braucht den KI-Baustein. Bisher reichte ihn nur
        # pipeline.grosslauf durch, weshalb ein Lauf ueber diesen Einstieg mit
        # "impressum" in der Reihenfolge sofort abbrach (echter Probelauf
        # 12.08.2026). Seit Prospeo tot ist, ist das unsere HAUPT-Stufe.
        if "impressum" in (kunde.anbieter_reihenfolge or []):
            from pipeline.sources.impressum import ImpressumQuelle
            zusatz["impressum_quelle"] = ImpressumQuelle(KI())
        gefunden, deckung, firmen_mit_ausgang = source_leads(
            kunde, limit, os.environ.get("APIFY_API_KEY", ""),
            os.environ["HUNTER_API_KEY"], os.environ["DROPCONTACT_API_KEY"],
            # Der Laufordner ist der Merkzettel fuer einen abgegebenen,
            # noch nicht abgeholten Dropcontact-Auftrag: stirbt der Lauf
            # in der Wartezeit, sind die Credits sonst verloren.
            lauf_dir=store.run_dir, **zusatz)
        store.save_step("leads", {"leads": [l.__dict__ for l in gefunden], "deckung": deckung})
        # Apollo-422-Fix: Stufe-1-Firmenliste + Pro-Firma-Ausgang separat
        # persistieren (firmen.json), damit ein spaeterer Blick in den
        # Laufordner sauber zeigt, WARUM eine Firma ohne Kontakt blieb -
        # nicht nur DASS sie es tat.
        store.save_step("firmen", firmen_mit_ausgang)
    stand_leads = store.load_step("leads")
    if isinstance(stand_leads, list):
        # Alte Laufordner (vor dem Kern-Umbau) speicherten leads.json als
        # reine Liste bzw. als {"leads": [...], "ohne_email": n} ohne
        # "deckung". --fortsetzen auf so einem Ordner soll trotzdem
        # funktionieren, dann eben ohne echte Deckungsquote im Bericht.
        stand_leads = {"leads": stand_leads, "deckung": dict(_LEERE_DECKUNG)}
    if not stand_leads.get("deckung"):
        stand_leads["deckung"] = dict(_LEERE_DECKUNG)
    leads = [Lead(**{k: d[k] for k in ("first_name", "last_name", "email",
                                        "company", "title", "website", "source")})
             for d in stand_leads["leads"]]

    if not store.step_done("dedupe"):
        # Globale Sperrliste (gilt fuer alle Kunden) + die eigene Liste des
        # Kunden zusammen anwenden (Vereinigung, Reihenfolge egal). Der
        # daten_dir fuer die globale Liste ist hier bewusst der aktuelle
        # Arbeitsordner (Projekt-Wurzel, wo kunden/ und laeufe/ liegen) -
        # wie der Rest der CLI schon cwd-relativ arbeitet (siehe LAEUFE oben).
        globale_sperrliste = lade_globale_sperrliste(Path("."))
        sperrliste = list(set(kunde.sperrliste) | set(globale_sperrliste))
        # alle_kampagnen_dir = laeufe/ (eine Ebene ueber der Kunden-Mappe):
        # ein Empfaenger soll dasselbe Angebot nicht zweimal von uns
        # bekommen, auch nicht aus zwei verschiedenen Kampagnen.
        behalten, verworfen = dedupe_leads(leads, store.run_dir.parent, sperrliste,
                                           aktueller_lauf=store.run_dir,
                                           alle_kampagnen_dir=store.run_dir.parent.parent)
        store.save_step("dedupe", {"behalten": [l.__dict__ for l in behalten],
                                   "verworfen": verworfen})
    stand = store.load_step("dedupe")

    if not store.step_done("personalisierung"):
        fertig, nacharbeit = [], []
        for lead, (ok, grund, texte) in _texte_schreiben(
                stand["behalten"], kunde, check):
            if ok:
                fertig.append({"email": lead.email, **texte})
            else:
                # texte ist {} wenn personalize() selbst schon scheiterte
                # (kein Text erzeugt), sonst der volle Text, den nur check()
                # abgelehnt hat. Wird mitgespeichert, damit die "Von der
                # Pruefung aussortiert"-Ansicht im Web-Interface (Task 5) den
                # abgelehnten Text aufklappbar zeigen kann statt nur den Grund.
                nacharbeit.append({"email": lead.email, "grund": grund, **texte})
        store.save_step("personalisierung", {"fertig": fertig, "nacharbeit": nacharbeit})
    ergebnis = store.load_step("personalisierung")
    store.save_step("pruefung_ok", ergebnis["fertig"])

    write_preview(store, ergebnis["fertig"], ergebnis["nacharbeit"])
    gruende = [f"{g}: {n}" for g, n in
               Counter(v["grund"] for v in stand["verworfen"]).items()]
    deckung = stand_leads["deckung"]
    # Apollo-422-Fix: Ausgang-Aufschluesselung fuer den Bericht aus
    # firmen.json zaehlen - leere Liste (statt KeyError), wenn dieser
    # Laufordner noch aus einer Zeit VOR diesem Fix stammt (kein
    # firmen.json vorhanden, siehe --fortsetzen auf altem Laufordner).
    firmen_stand = store.load_step("firmen") if store.step_done("firmen") else []
    ausgang_zaehlung = Counter(f.get("ausgang") for f in firmen_stand)
    write_report(store, {"gefunden": len(leads), "verworfen": len(stand["verworfen"]),
                         "personalisiert": len(ergebnis["fertig"]),
                         "nacharbeit": len(ergebnis["nacharbeit"]),
                         "gruende_verworfen": gruende,
                         # "ohne_email" ist seit dem Kern-Umbau firmen-, nicht
                         # personenbezogen: die Zahl der Stufe-1-Firmen ganz
                         # ohne nutzbaren Kontakt (persönlich oder info@).
                         "ohne_email": deckung["firmen_gesamt"] - deckung["firmen_mit_kontakt"],
                         "firmen_mit_entscheider": ausgang_zaehlung.get("mit_entscheider", 0),
                         "firmen_info_fallback": ausgang_zaehlung.get("info_fallback", 0),
                         "firmen_keine_webseite": ausgang_zaehlung.get("keine_webseite", 0),
                         "firmen_kein_entscheider": ausgang_zaehlung.get("kein_entscheider", 0),
                         "firmen_fehler": ausgang_zaehlung.get("fehler", 0),
                         "firmen_gesamt": deckung["firmen_gesamt"],
                         "firmen_mit_kontakt": deckung["firmen_mit_kontakt"],
                         "deckungsquote_prozent": deckung["quote_prozent"]})
    print(f"Vorschau: {store.run_dir / 'freigabe-vorschau.md'}")
    print("Nächster Schritt: prüfen, dann 'python -m pipeline freigeben <laufordner>'")

def freigeben(laufordner: str):
    # E-Fix 7: Konsistenz mit dem Web-Guard (web.routen.freigabe -
    # ZUSTAND_ERLAUBT_FREIGEBEN schliesst "abgelehnt" aus) - abgelehnt.json
    # muss ein absolutes Veto sein, egal ueber welchen Weg (CLI oder Web)
    # jemand versucht, danach doch noch freizugeben.
    store = RunStore.resume(laufordner)
    if (store.run_dir / "abgelehnt.json").exists():
        sys.exit(
            "Dieser Auftrag wurde abgelehnt - er darf nicht mehr freigegeben werden.")
    approve(store)
    print("Freigegeben. Senden mit: python -m pipeline senden", laufordner)

class SendenFehler(Exception):
    """Fasst die Abbruchgruende von '_versand_ausfuehren' als Exception statt
    sys.exit zusammen, damit dieselbe Kernlogik von zwei Aufrufern genutzt
    werden kann: der CLI (senden(), macht sys.exit(str(fehler)) daraus) und
    der Web-Route web/routen/freigabe.py (Task 5, macht daraus eine deutsche
    Fehlermeldung auf der Seite). Der Test-Empfaenger-Gate darf dadurch an
    genau einer Stelle stehen, nie dupliziert werden."""


def _versand_ausfuehren(store, sender, kunde=None) -> str:
    """Kernlogik von 'senden': Freigabe-/Empfaenger-Gate pruefen, Kampagne
    anlegen (oder eine schon angelegte wiederverwenden) und Leads
    importieren. `sender` ist ein InstantlySender (oder ein Fake mit
    derselben Schnittstelle in Tests/Web) - so bleibt diese Funktion
    unabhaengig davon, WO der API-Key herkommt.

    Sperrt IMMER (auch bei bestehender Freigabe - Review-Fund Task 5), wenn
    abgelehnt.json im Laufordner liegt: Ablehnen muss ein absolutes Veto
    sein, egal ob/wie es zu einer (fehlerhaften oder zeitlich versetzten)
    Freigabe kam. Diese Pruefung sitzt bewusst HIER (statt nur in der
    Web-Route), weil sowohl die CLI (senden()) als auch die Web-Route
    dieselbe Funktion aufrufen - eine Web-only-Sperre waere umgehbar.

    `kunde` ist optional: Standard None laedt ihn selbst ueber den in
    kunde_pfad.json gespeicherten Pfad, der relativ zum Arbeitsverzeichnis
    ist (funktioniert fuer die CLI, die immer mit cwd=daten_dir laeuft, s.
    web/laufmanager.py). Der Web-Aufrufer (web/routen/freigabe.py) laeuft
    dagegen IM SELBEN Prozess wie der Webserver, dessen cwd nicht daten_dir
    ist - er laedt den Kunden deshalb selbst (relativ zu daten_dir aufgeloest)
    und uebergibt ihn hier direkt, statt den Pfad blind nochmal relativ zum
    falschen Arbeitsverzeichnis zu lesen."""
    if (store.run_dir / "abgelehnt.json").exists():
        raise SendenFehler(
            "Dieser Auftrag wurde abgelehnt - es darf nichts versendet werden.")
    if not is_approved(store):
        raise SendenFehler("Keine Freigabe für diesen Lauf (FREIGABE.txt fehlt).")
    if store.step_done("versand_komplett"):
        campaign_id = store.load_step("versand_komplett")["campaign_id"]
        raise SendenFehler(f"Kampagne bereits angelegt: {campaign_id}")
    if kunde is None:
        kunde = load_kunde(store.load_step("kunde_pfad")["pfad"])
    texte = store.load_step("pruefung_ok")
    # Test-Modus (Vorgabe): nur an die eigenen Test-Adressen. Echt-Modus:
    # an die gefundenen Empfaenger. Der Modus steht in der Kundendatei und
    # wird in Schritt 5 des Formulars bewusst gesetzt - fehlt das Feld,
    # gilt "test" (siehe pipeline.config.Kunde.versand_modus).
    #
    # Vorher gab es diese Unterscheidung nicht: die Liste galt IMMER. Eine
    # im Formular gebaute Kampagne konnte damit nie uebergeben werden, denn
    # man haette jede einzelne Empfaengeradresse von Hand in die Testliste
    # schreiben muessen (gefunden am 14.08.2026 an einer echten Probe).
    if getattr(kunde, "versand_modus", "test") != "echt":
        erlaubt = {e.strip().lower() for e in kunde.test_empfaenger}
        fremde = [t["email"] for t in texte if t["email"].strip().lower() not in erlaubt]
        if fremde:
            raise SendenFehler(
                f"Abbruch: Empfänger nicht in Test-Empfänger-Liste: {fremde}. "
                f"Diese Kampagne steht auf Probe-Versand. Für den echten "
                f"Versand in Schritt 5 des Formulars »Echter Versand« wählen.")
    if not texte:
        raise SendenFehler("Abbruch: keine freigegebenen Texte zum Versenden.")

    if store.step_done("versand"):
        # Kampagne wurde in einem frueheren, abgebrochenen Lauf schon
        # angelegt (z.B. weil der Lead-Import scheiterte) - dieselbe
        # campaign_id wiederverwenden statt eine zweite Kampagne anzulegen.
        # TODO(verifizieren am echten Konto): dedupliziert /leads/add pro
        # Kampagne per E-Mail? Sonst koennen Wiederholungs-Importe nach
        # Teilfehler Leads doppeln.
        campaign_id = store.load_step("versand")["campaign_id"]
    else:
        # Name und Absender-Postfach MUESSEN mit: ohne email_list legt
        # Instantly die Kampagne ohne Absender an - sie kann dann gar nicht
        # senden, und jemand muss das Postfach von Hand nachtragen (gefunden
        # am 14.08.2026). Das Postfach zieht create_campaign selbst aus der
        # Kundendatei; hier bleibt der Name, der im Probe-Modus die alte
        # [TEST]-Vorsilbe behaelt.
        echt = getattr(kunde, "versand_modus", "test") == "echt"
        campaign_id = sender.create_campaign(
            kunde, name=kunde.name if echt else f"[TEST] {kunde.name}")
        store.save_step("versand", {"campaign_id": campaign_id})

    sender.import_leads(campaign_id, texte)
    store.save_step("versand_komplett", {"campaign_id": campaign_id})
    return campaign_id


def senden(laufordner: str):
    _brauche_env("INSTANTLY_API_KEY")
    store = RunStore.resume(laufordner)
    sender = InstantlySender(os.environ["INSTANTLY_API_KEY"])
    try:
        campaign_id = _versand_ausfuehren(store, sender)
    except SendenFehler as fehler:
        sys.exit(str(fehler))
    print(f"Kampagne {campaign_id} pausiert angelegt - Aktivierung von Hand in Instantly.")

# Wie viele Kontakte gleichzeitig Texte bekommen. Niedriger angesetzt als
# bei der Firmensuche: hinter jedem Kontakt stecken mehrere KI-Anfragen
# (Erstfassung plus bis zu drei Nachbesserungen), und die Anbieter drosseln
# frueher als gewoehnliche Webserver.
TEXTE_GLEICHZEITIG = max(1, int(os.environ.get("TEXTE_GLEICHZEITIG", "5")))


def _texte_schreiben(behalten, kunde, check):
    """Texte fuer alle Kontakte schreiben - mehrere gleichzeitig.

    Gemessen am 17.08.2026 an einem echten Lauf: die Adress-Suche brauchte
    3:45, das Texten 3:18 - also die Haelfte der Gesamtzeit. Getextet wurde
    dabei ein Kontakt nach dem anderen, obwohl die Zeit fast vollstaendig
    aus Warten auf die KI besteht.

    Gibt (lead, (ok, grund, texte)) in der Reihenfolge der Eingabe zurueck:
    Bericht und Freigabe-Tabelle sollen nicht davon abhaengen, welcher
    Kontakt zufaellig zuerst fertig wird.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import threading

    felder = ("first_name", "last_name", "email", "company", "title",
              "website", "source")
    leads = [Lead(**{k: d[k] for k in felder}) for d in behalten]
    if not leads:
        return []

    # Jeder Thread bekommt seine eigene KI: die haelt eine HTTP-Sitzung,
    # und die ist fuer gleichzeitige Nutzung nicht ausdruecklich freigegeben.
    lokal = threading.local()

    def ki_fuer_thread():
        eigene = getattr(lokal, "ki", None)
        if eigene is None:
            eigene = KI()
            lokal.ki = eigene
        return eigene

    def einen_text(lead):
        try:
            webseiten_text = fetch_text(lead.website)
            # Nachbesserungs-Schleife: bei NEIN wird der Text mit dem
            # Prüfer-Grund bis zu 3x neu geschrieben, bevor er zur
            # Nacharbeit fällt (statt sofort auszusortieren).
            ok, grund, texte, _ = personalisiere_mit_nachbesserung(
                lead, kunde, ki_fuer_thread(), webseiten_text, check)
            return ok, grund, texte
        except ValueError as fehler:
            return False, str(fehler), {}

    ergebnisse = [None] * len(leads)
    with ThreadPoolExecutor(
            max_workers=min(TEXTE_GLEICHZEITIG, len(leads))) as pool:
        auftraege = {pool.submit(einen_text, lead): i
                     for i, lead in enumerate(leads)}
        for auftrag in as_completed(auftraege):
            i = auftraege[auftrag]
            try:
                ergebnisse[i] = auftrag.result()
            except Exception as fehler:      # noqa: BLE001
                # Ein einzelner Kontakt darf den Lauf nicht mitreissen -
                # gleiche Regel wie bei der Firmensuche.
                print(f"Kontakt {leads[i].email} übersprungen "
                      f"(Fehler beim Texten): {fehler}")
                ergebnisse[i] = (False, f"Fehler beim Texten: {fehler}", {})
    return list(zip(leads, ergebnisse))


def ansichts_probe_cli(job_ordner):
    """Eine einzelne Ansichts-Mail verschicken und danach SELBST pausieren.

    Instantly verschickt nicht sofort: am 18.08.2026 lagen 200 Sekunden
    zwischen Aktivieren und Mail. Deshalb laeuft das hier als eigener
    Auftrag - und deshalb steht am Ende ein Pausieren im finally-Block.
    Eine Kampagne, die niemand freigegeben hat, darf nicht aktiv
    stehenbleiben (Projektregel vom 17.08.2026).
    """
    import time

    from pipeline.senders.instantly import InstantlySender

    job = Path(job_ordner)
    auftrag = json.loads((job / "auftrag.json").read_text(encoding="utf-8"))
    sender = InstantlySender(os.environ["INSTANTLY_API_KEY"])

    class _Probe:
        name = "Ansichts-Probe"
        follow_up_tage = [7, 14]
        versand_postfach = auftrag["absender"]
        tageslimit = 20
        zeit_von = "08:00"
        zeit_bis = "19:00"
        wochentage = ["mo", "di", "mi", "do", "fr"]

    betreff = auftrag.get("betreff") or "Ansichts-Probe"
    print(f"Ansichts-Probe an {auftrag['empfaenger']} über {auftrag['absender']}")
    campaign_id = sender.create_campaign(
        _Probe(), name=f"[TEST] Ansicht {betreff}"[:120],
        absender_emails=[auftrag["absender"]], betreffs=(betreff, "", ""))
    sender.import_leads(campaign_id, [{
        "email": auftrag["empfaenger"], "betreff": betreff,
        "mail_1": auftrag["text"],
        "follow_up_1": "Nicht verwendet - reine Ansichts-Probe.",
        "follow_up_2": "Nicht verwendet - reine Ansichts-Probe."}])

    gesendet, fehler = False, ""
    try:
        from web.instantly_leser import InstantlyLeser

        leser = InstantlyLeser(os.environ["INSTANTLY_API_KEY"])
        sender.aktiviere_kampagne(campaign_id)
        for versuch in range(24):          # 8 Minuten
            time.sleep(20)
            if leser._emails_hole_frisch(campaign_id):
                gesendet = True
                print(f"raus nach {(versuch + 1) * 20}s")
                break
        if not gesendet:
            fehler = "Instantly hat die Mail in acht Minuten nicht verschickt."
    except Exception as f:      # noqa: BLE001
        fehler = str(f)
    finally:
        try:
            sender.pausiere_kampagne(campaign_id)
            print("Kampagne wieder pausiert.")
        except Exception as f:      # noqa: BLE001
            print(f"Pausieren fehlgeschlagen: {f}")
        (job / "ergebnis.json").write_text(json.dumps(
            {"gesendet": gesendet, "fehler": fehler,
             "campaign_id": campaign_id,
             "empfaenger": auftrag["empfaenger"]}, ensure_ascii=False),
            encoding="utf-8")


def sammeln_cli(ort, radius_km, dienste, limit_pro_suche, ordner=None):
    """Firmen fuer einen Umkreis sammeln und als eigenen Ordner ablegen.

    Bewusst ein eigener Befehl und kein Teil von "lauf": Sammeln kostet
    Geld (die Apify-Aktoren rechnen pro Lauf ab) und soll deshalb immer
    eine bewusste Handlung sein - im Formular die Wahl in Schritt 3, hier
    ein ausdruecklich getippter Befehl.

    Der Fortschritt wird laufend ausgegeben, damit man bei einer Sammlung,
    die Minuten dauert, sieht, dass sie lebt.
    """
    from datetime import datetime

    from pipeline.firmen_sammeln import ordnername, sammeln, speichern
    from pipeline.sources.apify_maps import ApifyMapsSource
    from pipeline.sources.gelbe_seiten import GelbeSeitenQuelle
    from pipeline.sources.overpass import OverpassQuelle

    apify_key = os.environ.get("APIFY_API_KEY")
    if not apify_key:
        raise SystemExit(
            "Fehlende Umgebungsvariable: APIFY_API_KEY. Ohne sie koennen "
            "Google Maps und Gelbe Seiten nicht abgefragt werden.")

    print(f"Sammle Firmen: {ort}, {radius_km} km, {', '.join(dienste)}")
    firmen, bericht = sammeln(
        ort, radius_km, dienste,
        maps=ApifyMapsSource(apify_key),
        gelbe_seiten=GelbeSeitenQuelle(apify_key),
        overpass=OverpassQuelle(),
        limit_pro_suche=limit_pro_suche)

    ziel = speichern(".", firmen, bericht,
                     ordner or ordnername(
                         ort, radius_km, datetime.now().strftime("%Y%m%d-%H%M")))
    print(f"Gefunden: {len(firmen)} Firmen")
    print(f"  je Quelle: {bericht.get('je_quelle')}")
    print(f"  fremde PLZ verworfen: {bericht.get('fremde_plz')}")
    if bericht.get("quellen_fehler"):
        print(f"  AUSGEFALLEN: {bericht['quellen_fehler']}")
    print(f"Abgelegt in: {ziel}")
    print("Die Firmen stehen ab sofort im Bestand des Formulars.")


def main():
    lade_dotenv()
    parser = argparse.ArgumentParser(prog="pipeline")
    sub = parser.add_subparsers(dest="befehl", required=True)
    p_lauf = sub.add_parser("lauf")
    p_lauf.add_argument("kunde")
    p_lauf.add_argument("--limit", type=int, default=10)
    p_lauf.add_argument("--fortsetzen", default=None)
    p_lauf.add_argument("--firmen", dest="firmen_datei", default=None,
                        help="JSON mit einer fertigen Firmenliste - dann wird "
                             "nicht gesucht, sondern genau diese Liste benutzt "
                             "(Weg des Kampagnen-Assistenten).")
    p_lauf.add_argument("--neu-ab", dest="neu_ab", default=None,
                        choices=["leads", "dedupe", "personalisierung"],
                        help="Nur zusammen mit --fortsetzen: verwirft diesen Schritt und "
                             "alle nachgelagerten, damit sie neu berechnet werden.")
    p_sammeln = sub.add_parser(
        "sammeln", help="Firmen fuer einen Umkreis frisch sammeln (kostet "
                        "Geld - die Apify-Aktoren rechnen pro Lauf ab).")
    p_sammeln.add_argument("ort", help="Ortsname oder Postleitzahl")
    p_sammeln.add_argument("--radius", type=float, default=25.0)
    p_sammeln.add_argument("--dienst", action="append", dest="dienste",
                           required=True,
                           help="Suchbegriff, mehrfach angebbar")
    p_sammeln.add_argument("--limit", type=int, default=200,
                           help="Obergrenze je Suchbegriff bei Google Maps")
    p_sammeln.add_argument("--ordner", dest="ordner", default=None,
                           help="Name des Zielordners unter laeufe/leadquellen/ "
                                "- ohne Angabe aus Ort, Radius und Zeit gebaut. "
                                "Der Aufrufer (Weboberflaeche) gibt ihn vor, "
                                "damit er das Ergebnis wiederfindet.")

    p_probe = sub.add_parser(
        "ansichts-probe",
        help="Einen fertigen Kampagnentext zur Ansicht an eine eigene "
             "Adresse schicken (Unterauftrag der Weboberflaeche).")
    p_probe.add_argument("job_ordner")

    for name in ("freigeben", "senden"):
        p = sub.add_parser(name)
        p.add_argument("laufordner")
    args = parser.parse_args()
    if args.befehl == "lauf":
        lauf(args.kunde, args.limit, args.fortsetzen, args.neu_ab,
             args.firmen_datei)
    elif args.befehl == "sammeln":
        sammeln_cli(args.ort, args.radius, args.dienste, args.limit, args.ordner)
    elif args.befehl == "ansichts-probe":
        ansichts_probe_cli(args.job_ordner)
    elif args.befehl == "freigeben":
        freigeben(args.laufordner)
    else:
        senden(args.laufordner)

if __name__ == "__main__":
    main()
