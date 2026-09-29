# Postal code list for zones 40–69: what was corrected

29.09.2026

## In short

The list for zones 40–69 names 35 cities (Düsseldorf, Köln, Frankfurt,
Dortmund, Essen, Mannheim and others) with 2,096 postal codes. Most of
those codes do not exist. For Köln, for example, the list contains every
number from 50667 to 50998 and from 51061 to 51148 (366 codes), while
Köln really has about 45.

A code that does not exist costs us nothing, because no company can have
it. The real problem was the other way round: **about 50 real postal
codes of the same cities were missing.** We only take a company into a
zone when its postal code is on the list, so companies there would have
been left out without anyone noticing. Six companies we already have in
our database sit on such codes (Dortmund 44149, Essen 45149 and 45359,
Wuppertal 42369, Leverkusen 51381, Offenbach 63075).

The cities stay exactly the same. Only the codes behind them changed.

| | Codes |
|---|---:|
| On the list we received | 2,096 |
| Kept: real codes with street addresses | 414 |
| Kept: real, but PO box or large-customer codes (harmless) | 63 |
| Removed: exist nowhere | 1,619 |
| Added: real codes of the same cities that were missing | 50 |
| **Corrected list** | **527** |

One real code was not added: 60255 in Frankfurt belongs to a single
company (Frankfurter Sparkasse), so no IT service firm sits on it.

## Added codes

| City | Added |
|---|---|
| Düsseldorf | 40239, 40489, 40599 |
| Mönchengladbach | 41069, 41199, 41236, 41238, 41239 (Rheydt) |
| Wuppertal | 42119, 42289, 42327, 42329, 42349, 42369, 42389, 42399 (Vohwinkel, Cronenberg, Ronsdorf, Langerfeld) |
| Solingen | 42699, 42719 |
| Remscheid | 42899 |
| Dortmund | 44149 |
| Essen | 45149, 45359 |
| Gelsenkirchen | 45899 |
| Duisburg | 47279 |
| Krefeld | 47839 |
| Münster | 48167 |
| Köln | 50679, 50999, 51149 |
| Leverkusen | 51381 |
| Aachen | 52080 |
| Bonn | 53129, 53229 |
| Mainz | 55131, 55252 (Mainz-Kastel) |
| Frankfurt am Main | 60599, 65929, 65931, 65933, 65934, 65936 (Höchst and the west) |
| Offenbach am Main | 63075 |
| Darmstadt | 64297 |
| Wiesbaden | 55246 (Mainz-Kostheim), 65207 |
| Saarbrücken | 66133 |
| Ludwigshafen | 67071 |
| Kaiserslautern | 67663 |
| Mannheim | 68309 |
| Heidelberg | 69126 |

## To decide later, when we get there

- Six codes do not start with the number of their city's zone:
  Frankfurt's west (65929–65936) starts with 65, like Wiesbaden, and
  Mainz-Kostheim (55246) belongs to Wiesbaden but starts with 55. We decide
  which zone they go into when we reach zones 55, 60 and 65.
- Zone 67 holds two cities about 55 km apart (Ludwigshafen and
  Kaiserslautern). One search circle around both would pay for all the
  land in between, so it will get two.

## How it was checked

- Sources: the postal code areas of OpenStreetMap (checked 29.09.2026) and
  the GeoNames postal code register, which the project already uses. A code
  counts as real when one of the two knows it.
- The original list stays unchanged: `daten/plz-liste-oliver-40-69.csv`.
- The corrected list: `daten/plz-liste-oliver-40-69-corrected.csv`, with a
  column "Hinweis" that marks every added code ("neu") and every PO box or
  large-customer code ("Sonder-PLZ").
- The correction can be repeated at any time with
  `werkzeuge/plz-list-correction.py --offline`.
