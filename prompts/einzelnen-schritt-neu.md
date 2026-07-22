Du schreibst eine einzelne Nachricht einer bestehenden B2B-E-Mail-Sequenz neu.

Absender: {absender}
Angebot/Firma des Absenders: {kunde_name}
Angebot: {angebot}
Tonalität: {tonalitaet}

Empfänger: {anrede_name}
Rolle: {titel}
Firma: {firma}
Belegbarer Webseiteninhalt:
{webseiten_text}

Aktuelle vollständige Sequenz:
{aktuelle_texte}

Ändere ausschließlich {schritt}. Die anderen Nachrichten sind nur Kontext und
dürfen nicht umgeschrieben werden. Erfinde keine Tatsachen. Verwende keine
Platzhalter.

Antworte ausschließlich als JSON:

- Für E-Mail 1: {{"betreff": "...", "text": "..."}}
- Für ein Follow-up: {{"text": "..."}}
