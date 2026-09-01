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

## Kush nuk hyn në listë: firmat me softuer të vetin (nga 31.08.2026)

Ne i shkruajmë vetëm firmave që **mirëmbajnë IT-në e firmave tjera si
shërbim** — rrjeta, server, kompjuterë, përkrahje, managed services.

Jashtë mbeten, edhe nëse në faqe shkruajnë se bëjnë përkrahje IT:

- firmat që zhvillojnë ose shesin **softuer të vetin** (zhvillues,
  prodhues, shitës softueri, edhe kur ofrojnë mirëmbajtje për produktin
  e vet)
- firmat me produkt për **një degë të ngushtë** (p.sh. softuer për
  kancelari tatimore, softuer për kisha, CAD)
- **partnerët e produkteve të huaja** (Salesforce, SAP, DATEV e të
  ngjashme) — aty puna është rreth produktit, jo mirëmbajtje e vazhdueshme
- firmat ku **thelbi i ofertës është siguria** (pentest, ISO 27001,
  NIS-2, ISB/CISO i jashtëm), edhe kur përmendin "Managed IT" anash

Mbetet brenda: mirëmbajtja e Microsoft 365 dhe e vendeve të punës në
cloud — ajo është punë IT normale, jo produkt i huaj.

Rregulli vlen për **të gjitha zonat** — për ato që do t'i bëjmë dhe
njësoj për ato që i kemi bërë më herët. Kur rregulli ndryshon, listat e
gatshme rishikohen sipas tij; nuk mbetet asgjë e vjetër e pandryshuar
vetëm se ka dalë para se ta shkruanim rregullin.

Pse u shkrua: më 31.08.2026 Dafina gjeti gjashtë firma të tilla në
tabelat e zonave 33 dhe 34 (Mibema, GRAPHISOFT Kassel, elastify,
netgo tax, BLUVIT, kisocon). Katër prej tyre kishin hyrë nga hapi
"shansi i dytë" te `pipeline/branchen_filter.py`, që i kthen brenda
zhvilluesit e softuerit nëse ofrojnë edhe përkrahje — pikërisht ata që
nuk i duam. Të gjashtat janë në `sperrliste-global.yaml`.

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
