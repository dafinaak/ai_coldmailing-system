"""Der CRM-Zufluss muss das Wort benutzen, das die Daten wirklich tragen.

Gefunden am 17.08.2026: Eine echte Antwort war in Instantly und im
Postfach sichtbar, im CRM aber nicht. Grund: crm_zufluss suchte nach
richtung == "erhalten", web.instantly_leser liefert aber "empfangen".
Die Liste war damit IMMER leer - seit dem ersten Tag wurde kein einziger
Kontakt angelegt, und nichts sah nach einem Fehler aus.

Der alte Test war gruen, weil er dasselbe erfundene Wort benutzte. Diese
Tests hier binden den Zufluss an den echten Erzeuger, damit ein
auseinanderlaufendes Wort sofort auffaellt.
"""
from web.crm_speicher import KontakteSpeicher
from web.crm_zufluss import antwortende_uebernehmen
from web.instantly_leser import konversationen_aus_email_stand


def _speicher(tmp_path):
    return KontakteSpeicher(tmp_path / "kontakte.db",
                            uhr=lambda: "2026-08-17T12:00:00")


# Rohdaten so, wie Instantly sie liefert: ue_type 1 = von uns gesendet,
# ue_type 2 = Antwort des Kontakts.
ROHE_MAILS = {
    "camp-1": {"items": [
        {"id": "1", "ue_type": 1, "campaign_id": "camp-1",
         "eaccount": "wir@example.com", "subject": "Anfrage",
         "timestamp_email": "2026-08-17T08:00:00.000Z",
         "from_address_email": "wir@example.com",
         "to_address_email_list": "chef@firma.de", "body": {"text": "Hallo"}},
        {"id": "2", "ue_type": 2, "campaign_id": "camp-1",
         "eaccount": "wir@example.com", "subject": "Re: Anfrage",
         "timestamp_email": "2026-08-17T09:00:00.000Z",
         "from_address_email": "chef@firma.de",
         "to_address_email_list": "wir@example.com", "body": {"text": "Ja gerne"}},
    ], "erreichbar": True}
}


def test_antwort_aus_echten_instantly_daten_landet_im_crm(tmp_path):
    # Kein selbstgebautes Gespraech: erst durch den echten Leser, dann in
    # den Zufluss - genau der Weg, den die Postfach-Seite geht.
    konversationen = konversationen_aus_email_stand(ROHE_MAILS)
    speicher = _speicher(tmp_path)

    neu = antwortende_uebernehmen(speicher, konversationen,
                                   kampagnen_namen={"camp-1": "Partnerschaft"})

    assert neu == 1
    kontakt, = speicher.kontakte()
    assert kontakt["email"] == "chef@firma.de"
    assert kontakt["kampagne"] == "Partnerschaft"
    assert kontakt["stufe"] == "neuer_lead"


def test_der_leser_nennt_die_richtung_empfangen():
    # Bricht, sobald jemand das Wort auf einer der beiden Seiten aendert.
    konversation, = konversationen_aus_email_stand(ROHE_MAILS)
    richtungen = {n["richtung"] for n in konversation["nachrichten"]}

    assert richtungen == {"gesendet", "empfangen"}


def test_ohne_antwort_kein_kontakt(tmp_path):
    nur_gesendet = {"camp-1": {"items": [ROHE_MAILS["camp-1"]["items"][0]],
                                "erreichbar": True}}
    speicher = _speicher(tmp_path)

    neu = antwortende_uebernehmen(
        speicher, konversationen_aus_email_stand(nur_gesendet))

    assert neu == 0
    assert speicher.kontakte() == []
