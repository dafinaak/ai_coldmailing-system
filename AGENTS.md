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

**Saktësim (Dafina, 03.09.2026): faqja vendos, jo kategoria e hartës.**
Kategoria e Google Maps "Softwareentwickler/-hersteller" nuk e nxjerr
një firmë jashtë vetvetiu — Google u jep firmave 4–5 kategori dhe firma
IT klasike shpesh e kanë edhe atë. Vendos teksti i faqes, i gjykuar me
rregullin e mësipërm (softuer i vet = jashtë, edhe me përkrahje).
Kategoria mbetet vetëm si shenjë për gjykuesin. Kjo nuk është "shansi i
dytë" i vjetër — ai përdorte një prompt të butë; ky përdor rregullin e
rreptë. Pse: më 03.09.2026, te rigjykimi i zonave 32–34, kategoria e
hartës vetëm hidhte poshtë 61 firma; faqja e konfirmoi për 49 dhe i
ktheu brenda 12 firma IT të vërteta (Computer live, Deltatec, ELAAX,
IT-HAUS, Klanke, Wulf Systems ...).

## Gelbe Seiten nuk përdoret më (nga 04.09.2026)

Burimet për mbledhjen e firmave janë **Google Maps dhe Overpass/OSM**.
Gelbe Seiten doli nga zinxhiri me urdhër të Dafinës: "nuk na kryen punë".

Pse: u provua mbi të tetë zonat 32–39 më 03.09.2026, me rreth $2 te
Apify. Solli ~560 firma të reja që Maps e Overpass nuk i kishin — dhe
prej tyre **zero** arritën në listat përfundimtare. Thuajse asnjë nuk
kalon profilin IT (te zona 35: 9 nga 68), dhe ato pak që kalojnë,
Dropcontact-i nuk ua gjen email-in personal. Email-at që i kthen vetë
Gelbe Seiten janë kryesisht `info@` — pra jashtë rregullit tonë.

Vegla `werkzeuge/zonen-gelbeseiten.py` mbetet e ndërtuar nëse ndonjëherë
provohet në rajone të tjera, por nuk hyn në zinxhir. Të dhënat e
mbledhura rrijnë te `gelbeseiten-arkiv/`, jashtë `laeufe/`, që as
ndërtimi i `master.db` të mos i marrë.

**Plotësim (10.09.2026):** më 04.09 Gelbe Seiten doli vetëm nga vegla e
zonave. Komanda e përgjithshme `python -m pipeline sammeln` — ajo që e
nis edhe hapi 3 i formularit — e pyeste ende dhe e paguante te Apify.
Tash as ajo nuk e pyet më, dhe formulari shkruan "Google Maps und
OpenStreetMap". E ruan testi `tests/test_collect_without_gelbe_seiten.py`.

## Në zonë hyn vetëm firma me kod postar nga lista (nga 10.09.2026)

Një firmë i takon një zone vetëm nëse një nga burimet e zonës (Maps, OSM,
MailCom) ia jep kodin postar, dhe ai kod është në listën e Oliverit për
atë zonë. Firma pa kod postar nuk hyn — as në listë, as në raportin e
burimeve. Kodi i Handelsregister-it (Dropcontact) nuk vlen si provë:
ai është selia zyrtare, jo zyra që kërkuam.

Ku zbatohet: mbledhja me listë kodesh (`sammeln_bis_ziel` te
`pipeline/firmen_sammeln.py`), porta e zonës te
`werkzeuge/zona32-itliste-final.py` dhe raporti
`pipeline/zone_sources.py`.

Pse u shkrua (vendim i Dafinës, 10.09.2026): OSM kërkohet në katrorin e
tërë rajonit postar (te zona 35 rreze 120 km, kurse zona ka 48), dhe
firmat e tij pa kod postar mbaheshin si "brenda zonës". Te listat e
04.09 dolën kështu 23 rreshta që nuk ishin të provuar në zonën e vet,
disa me kod postar nga Wuppertal, Mainz e Frankfurti. Tre prej tyre
Maps i njeh në një zonë tjetër, dhe tash dalin aty. Çmimi që pranohet:
humbin edhe disa firma që ndoshta janë brenda zonës, po pa kod postar
nuk e dimë.

## Identiteti i firmës: pa bashkim automatik (nga 08.09.2026)

Çdo firmë ka një numër që nuk ndërron kurrë — `firma_uid`. Ai rri te
`daten/stamm.db`, një bazë që nuk fshihet asnjëherë, si `historie.db`.

Rregullat, të vendosura nga Dafina:

- **një `kennung` = një `firma_uid`.** Asgjë nuk bashkohet vetvetiu.
- **Pa bashkim automatik me emër + PLZ.** As me emër, as me emër dhe
  kod postar bashkë.
- **Bashkimi bëhet vetëm me dorë**, përmes `stamm_db.set_alias()`, dhe
  zhbëhet me `stamm_db.alias_loesen()`.
- **`stamm.db` është e përhershme.** Pa `DROP`, pa fshirje — njësoj si
  `historie.db`. E ruan një test:
  `tests/test_stamm_db.py::test_schema_has_no_drop_and_no_delete`.
- **Dedupe i email-eve nuk preket** — ai mbetet aty ku ishte, te
  `pipeline/dedupe.py`. Kjo është punë tjetër.
- **`stamm_db` nuk pastron më shumë se `master_db`.** `master_db._kennung()`
  i bën shkronjat e vogla dhe nuk i heq hapësirat; prandaj `stamm_db` bën
  vetëm shkronjat e vogla. Nëse do t'i hiqte hapësirat, `'eq24pay.de '` dhe
  `'eq24pay.de'` — dy rreshta të ndarë te `companies` — do të merrnin një
  `firma_uid` të vetëm, dhe UPSERT-i i Fazës 6 do ta mbante atë që vjen i
  fundit, varësisht nga rendi i leximit. Oliveri do të shihte një rresht që
  ndryshon pa arsye mes sinkronizimeve. Hapësira mbetet pjesë e identitetit;
  bashkimi bëhet me `set_alias()` si çdo bashkim tjetër.

Rrjedh një premtim që Faza 6 mbështetet mbi të: **asnjë dy rreshta te
`companies` nuk kanë të njëjtin `firma_uid` pa e bashkuar dikush me dorë.**
E ruan `tests/test_master_db_firma_uid.py::test_no_two_rows_share_an_id_without_set_alias`.

**`stamm.db` duhet të ketë kopje ruajtjeje (backup). Kjo nuk është
zgjedhje.** `firma_uid` është hash i `kennung`-ut, prandaj për firmat e
**pabashkuara** ai do të dilte i njëjti edhe pa bazën. Për firmat e
**bashkuara** jo: pas `set_alias()`, "8thsense" mban uid-in e
`8thsense.de` — një lidhje që nuk rrjedh nga kennung-u i vet dhe nuk
llogaritet dot nga asgjë. Nëse `stamm.db` humbet dhe dikush i
"rikthen" uid-at duke rillogaritur hash-et, të gjitha bashkimet
zhbëhen pa u parë nga askush, kurse Postgres-i mbetet i lidhur me uid-e
që s'i prodhon më asnjë llogaritje. Pra humbja e `stamm.db` nuk është e
zhurmshme — është e qetë dhe pjesërisht e gabuar, që është më keq.
Lista e bashkimeve merret me `stamm_db.aliase()`; mbaje të shkruar.

Pse pa bashkim automatik: dy firma mund ta kenë të njëjtin emër dhe të
njëjtin kod postar e prapë të jenë dy firma. Një bashkim i gabuar i fut
njerëzit e një firme nën tjetrën pa u vënë re fare — dhe pastaj oferta
i shkon firmës së gabuar. Një bashkim i humbur kushton vetëm një rresht
të dyfishtë, që njeriu e sheh dhe e ndreq. Prandaj rregulli i rreptë.

`companies.id` te `master.db` **nuk është identitet** — është numër
rreshti dhe lëviz sa herë shtohet a hiqet një firmë. Asnjë sistem
jashtë nuk guxon ta ruajë atë. Ruhet `firma_uid`.

Provuar më 08.09.2026 mbi të dhënat e vërteta: te dy ndërtime me radhë,
të 10.183 `companies.id` ndryshuan dhe **0** `firma_uid` ndryshuan;
10.184 kennung të ndryshme dhanë 10.184 uid të ndryshme — pra zero
bashkime automatike.

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
