Du liest zwei Texte, und sie beschreiben ZWEI VERSCHIEDENE FIRMEN:

**Zweck dieser Kampagne** (aus Schritt 1 des Formulars) sagt, WER
angeschrieben wird — das ist der Empfänger:

{kampagnen_zweck}

**Webseiten-Text** unten beschreibt den ABSENDER, also uns. Er sagt, was
wir anbieten. Er sagt NICHT, wer angeschrieben wird.

Leite daraus zwei Dinge ab:

1. **USP** — fünf kurze Aussagen, warum ein Kunde bei DER FIRMA AUS DEM
   WEBSEITEN-TEXT kauft. Jede Aussage ist eine Zeile von höchstens zehn
   Wörtern, dazu ein erklärender Satz. Keine Superlative, keine
   Ausrufezeichen, keine Werbesprache. Was die Firma wirklich tut, nicht
   was sie behauptet.

2. **ICP** — WER ANGESCHRIEBEN WIRD, in vier Gruppen:
   - `firmografisch`: Branche, Größe, Region der EMPFÄNGER-Firmen
   - `technografisch`: Technik oder Systeme, die die EMPFÄNGER einsetzen
   - `verhalten`: Anlässe, an denen ein EMPFÄNGER auf so ein Angebot eingeht
   - `entscheider`: welche Rolle beim EMPFÄNGER entscheidet

Der ICP kommt aus dem ZWECK, nicht aus dem Webseiten-Text. Steht im Zweck
nichts über die Empfänger, dann — und nur dann — nimm den gewöhnlichen
Endkunden aus dem Webseiten-Text.

Die häufigste Falle: Der Webseiten-Text beschreibt Leistungen für
mittelständische Unternehmen, angeschrieben werden aber IT-Dienstleister,
die diese Leistungen an ihre eigenen Kunden weitergeben. Dann sind die
IT-Dienstleister der ICP — nicht die mittelständischen Unternehmen.

Prüfe deine Antwort einmal gegen diese Frage: Würde die Firma, die ich
unter `firmografisch` beschrieben habe, den Zweck oben als an sich
gerichtet lesen? Wenn nein, ist es der falsche Kreis.

Wenn der Text zu einem Punkt nichts hergibt, schreibe dort ehrlich
"aus der Webseite nicht erkennbar" statt zu raten.

Antworte NUR mit diesem JSON, ohne weiteren Text:

{{
  "usp": [
    {{"titel": "...", "erklaerung": "..."}}
  ],
  "icp": {{
    "firmografisch": "...",
    "technografisch": "...",
    "verhalten": "...",
    "entscheider": "..."
  }}
}}

Webseiten-Text (beschreibt den ABSENDER):
{webseiten_text}
