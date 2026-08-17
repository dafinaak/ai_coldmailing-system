# Projekt-Regeln: AI Coldmailing System

> These rules apply on top of the globally installed Agentic Workflow
> core (four phases, the human decides, outward-impact brake). They
> override it only where they explicitly say so.

## Gjuha e punës: shqip (nga 11.08.2026)

Të gjitha shpjegimet, pyetjet dhe përgjigjet ndaj njeriut bëhen në shqip,
me fjalë të thjeshta të përditshme. Ky rregull tash vlen kudo, jo vetëm
këtu — është shënuar edhe te rregullat e përgjithshme. Përjashtim mbetet
Jira: aty shkruhet anglisht, që ta kuptojë tërë ekipi.

Kjo vlen për bisedën dhe për dokumentet e reja. Për gjuhën e vetë kodit
(emrat e funksioneve, komentet, tekstet në ekran) vlen ende vendimi i
mëparshëm: kodi i ri shkruhet në anglisht, kodi i vjetër gjerman
ndërrohet vetëm brenda fazave të rifreskimit — jo me një përkthim të
madh njëherësh.

## Asnjë fushatë nuk niset pa fjalën e Dafinës (nga 17.08.2026)

Asnjë fushatë nuk aktivizohet dhe asnjë email nuk niset pa e thënë
Dafina shprehimisht, çdo herë veç e veç. Kjo vlen për këdo dhe për çdo
mjet: mjetin tonë, Instantly-n drejtpërdrejt, skriptet, gjithçka.

Miratimi i teksteve te tabela nuk është leje për nisje. Dorëzimi i një
fushate te Instantly nuk është nisje — fushata mbetet e fjetur derisa
Dafina të thotë "nise".

Pse u shkrua: më 17.08.2026 doli se fushata "IT-Dienstleister –
Anschreiben" ishte **aktive** dhe kishte dërguar 25 email te firma të
vërteta që nga 14 gushti, pa e ditur askush se ishte nisur. 203 nga
kontaktet e saj ishin të njëjtat me fushatën tonë kryesore — pra ata
njerëz do të kishin marrë të njëjtën ofertë dy herë. U ndal me urdhër
të Dafinës.

Nëse gjendet një fushatë aktive që nuk e ka miratuar ajo: **thuaje
menjëherë** dhe pyet a duhet ndaluar. Mos e nis kurrë vetë; ndalja
bëhet vetëm me fjalën e saj, sepse mund ta ketë nisur dikush tjetër me
qëllim.

## Zuverlässigkeit zuerst

Zuverlässigkeit hat in diesem Projekt höchste Priorität — vor
Sparsamkeit und vor Schnelligkeit. Plane und baue nichts, dessen
Zuverlässigkeit unsicher ist.

Das heißt konkret:

- Das Fundament der Datenbeschaffung sind stabile, bezahlte
  Schnittstellen (z. B. Dropcontact, Hunter), die selbst prüfen und
  verlässlich antworten. Auf die stützt sich das System.
- Selbst gebaute, brüchige Bausteine (z. B. ein Impressum-Scraper mit
  wechselnden Layouts und Wartung bei uns) sind KEIN Fundament. Sie
  dürfen höchstens ein geprüfter Bonus obendrauf sein, auf den sich das
  System nicht verlässt.
- Jede gefundene E-Mail wird vor dem Versand geprüft, damit keine
  Rückläufer den Ruf der Absender-Postfächer beschädigen. Die Prüfung
  ist Teil der Zuverlässigkeit, nicht optional.

## Interface = Wholix-Nachbau

Die Oberfläche soll aussehen und sich bedienen wie Wholix (die 10
Bildschirmfotos im Ordner "wholix interface screenshots" sind die
Vorlage). Es ist ein internes Tool; Instantly bleibt der unsichtbare
Versand-Motor darunter.

Nachgebaut wird der Funktionsumfang laut Fahrplan
(docs/wholix-nachbau-roadmap.md), MINUS der am 22.07.2026 gestrichenen
Funktionen (dort im Abschnitt "Scope-Entscheidungen" gelistet). Nicht
jede Wholix-Funktion ist für ein internes Tool sinnvoll - was gestrichen
ist, wird nicht gebaut.
