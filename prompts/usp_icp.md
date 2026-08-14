Lies den folgenden Webseiten-Text einer Firma und leite zwei Dinge ab:

1. **USP** — fünf kurze Aussagen, warum ein Kunde bei dieser Firma kauft.
   Jede Aussage ist eine Zeile von höchstens zehn Wörtern, dazu ein
   erklärender Satz. Keine Superlative, keine Ausrufezeichen, keine
   Werbesprache. Was die Firma wirklich tut, nicht was sie behauptet.

2. **ICP** — der ideale Kundenkreis, in vier Gruppen:
   - `firmografisch`: Branche, Größe, Region der Zielfirmen
   - `technografisch`: eingesetzte Technik oder Systeme, falls erkennbar
   - `verhalten`: Anlässe, an denen so ein Kunde sucht
   - `entscheider`: welche Rolle im Zielunternehmen entscheidet

WICHTIG für den ICP: Beschreibe die Firmen, die DIESE KAMPAGNE anschreibt
— nicht zwangsläufig die Endkunden der Firma. Beides fällt oft auseinander.
Richtet sich die Kampagne an Partner oder Wiederverkäufer, die das Angebot
ihren eigenen Kunden weitergeben, dann beschreibe diese Partner. Was die
Kampagne vorhat, steht unten unter "Zweck dieser Kampagne"; steht dort
nichts, gehe vom normalen Endkunden der Firma aus.

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

Zweck dieser Kampagne (aus Schritt 1 des Formulars):
{kampagnen_zweck}

Webseiten-Text:
{webseiten_text}
