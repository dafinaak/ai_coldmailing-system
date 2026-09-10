# Projekti: AI Coldmailing System

> Ky dokument u përkthye i tëri nga gjermanishtja në shqip më 01.09.2026, me
> urdhër të Dafinës. Përmbajtja nuk u ndryshua — vetëm gjuha. Origjinali
> gjermanisht kthehet nga git nëse duhet ndonjëherë. Emrat e dosjeve, komandat,
> emrat e fushave të Oliverit dhe emrat e fushatave mbeten ashtu si janë, sepse
> ashtu shkruhen edhe në kod e në Instantly.

## Për çka bëhet fjalë

Mjeti i brendshëm i ekipit e zëvendëson hap pas hapi ndërfaqen e Wholix-it. Të
çon nga oferta dhe kërkimi i lead-eve, te tekstet me AI dhe miratimi, deri te
dërgimi. Instantly mbetet poshtë motori i dërgimit — dërgimi, ngrohja e kutive
postare dhe zbritja në inbox. Fotot e ekranit të Wholix-it janë shembulli për
pamjen dhe përdorimin; sa saktësisht ribëhet, shkruan te
`docs/wholix-nachbau-roadmap.md`.

Besueshmëria vjen para shpejtësisë dhe para kursimit: të dhënat vijnë nga
ndërfaqe të qëndrueshme e të paguara; çdo email kontrollohet para se të niset.
Testet dhe provat e dukshme punojnë me të dhëna prove, kurrë me marrës të
vërtetë.

## Gjendja tash

- **10.09.2026 — Jira AP-215 (mbledhja sipas kodeve postare) e mbyllur.**
  Asnjë commit — gjithçka në working tree.
  - Gelbe Seiten doli edhe nga komanda `python -m pipeline sammeln`, që e
    nis hapi 3 i formularit — deri sot e pyeste ende dhe e paguante te
    Apify. Teksti i formularit u ndreq. Test:
    `tests/test_collect_without_gelbe_seiten.py`. Shih AGENTS.md.
  - **Rregull i ri (Dafina, opsioni A): në zonë hyn vetëm firma me kod
    postar nga lista.** OSM kërkohej në katrorin e tërë rajonit postar
    (zona 35: rreze 120 km, zona 48), dhe firmat e tij pa kod postar
    mbaheshin si "brenda zonës". Tash i heq mbledhja me listë kodesh, porta
    e zonës te `zona32-itliste-final.py` dhe raporti. Shih AGENTS.md.
  - **Listat u rindërtuan:** `IT-Liste-Emails-Zona<NR>-FERTIG-20260910-1121.xlsx`,
    248 kontakte (ishin 268). Krahasuar rresht për rresht me ato të
    04.09: dolën 23 rreshtat pa kod postar në zonën e vet (17 te zona
    35), hynë 3 firma në zonën e duhur (25help te 33, Systemhaus Cramer
    te 34, your admins te 36), 0 qeliza tjera ndryshuan. Listat e 04.09
    mbeten në dosje, të paprekura. Raporti i kontrollit
    `Listen-Pruefbericht-20260904-0939.xlsx` u përket listave të vjetra.
  - Raporti i burimeve për çdo zonë: `pipeline/zone_sources.py`,
    `werkzeuge/zone-source-report.py` (vetëm lexim), hapi 5 i
    `zonen-komplett.sh`. Zonat 32–39 bashkë: 4.908 firma të reja të
    provuara në zonë — Maps vetëm 3.617, MailCom vetëm 929 (zonat 33,
    34), OSM vetëm 198, disa burime bashkë 164; 595 firma pa kod postar
    të lëna jashtë. Numrat e vjetër të `sammelbericht.json` të OSM-it për
    zonat 38/39 ("0 të reja") ishin të gabuar: u numëruan kundrejt asaj
    që ishte në disk atë ditë.
  - E hapur: nëse listat e 04.09 i janë dhënë Oliverit, atij i duhet
    thënë se 23 rreshta dolën (dhe cilët). AP-210 (kontrolli i bazës për
    vendimmarrësit) nuk është bërë; pret fjalën e Dafinës.
  - 1.458 teste jeshile, 90 të kaluara (Postgres, Docker-i i fikur).
- **02–04.09.2026 — Zonat 32–39 të gatshme për Oliverin: 268 kontakte
  me email personal, të kontrolluara.** Skedarët:
  `IT-Liste-Emails-Zona<NR>-FERTIG-20260904-0918.xlsx` (8 lista) dhe
  raporti i kontrollit `Listen-Pruefbericht-20260904-0939.xlsx`.
  - Burimet: Google Maps (245) + Overpass/OSM (23). **Gelbe Seiten u hoq
    nga zinxhiri më 04.09.2026** me urdhër të Dafinës — u provua mbi të
    tetë zonat (~$2 Apify), solli ~560 firma të reja dhe **0 kontakte**.
    Rigjenerimi pa të dha saktësisht të njëjtat 268, që e vërteton. Vegla
    mbetet; të dhënat te `gelbeseiten-arkiv/` jashtë `laeufe/`. Rregulli:
    AGENTS.md.
  - Rigjykimi i profilit (03–04.09): zonat 32–34 ishin gjykuar në gusht me
    rregullin e vjetër + "shansin e dytë". Me rregullin e 31.08 dolën
    jashtë 110 nga 250 rreshta (softuer i vet, siguri, SAP, hosting,
    elektrikë). **Vendim Dafina 03.09: faqja vendos, jo kategoria e
    hartës** — `harter_ausschluss()` s'e hedh më "Softwareentwickler" pa
    gjyq, kategoria shkon si shenjë te AI (`software_hinweis()`). Shih
    AGENTS.md. Vegla: `werkzeuge/listen-nachpruefung.py`.
  - Porta të reja te lista (`zona32-itliste-final.py`): lista e bllokimit
    edhe te porta e fundit (6 firma të bllokuara kishin kaluar), profili
    IT si qëndron sot, dhe dublikata mes zonave (zona me numër më të vogël
    e mban — 22 njerëz dilnin në dy lista). Kontrolli:
    `werkzeuge/listen-pruefung.py` (format, dublikata, faqe të gjalla).
  - Dropcontact: tash lexohen edhe telefoni, LinkedIn, civility,
    Handelsregister (paguhen me të njëjtin kredit; 14 gra dilnin "Herr").
    Dërgimet ruhen me emër — askush s'pyetet dy herë (200 ridërgime kot
    më 03.09). Ngarkimi i krediteve s'u pajtua me "pay on success"
    (411→391 për 7 email) — për t'u parë te konsolla.
  - E hapur: zona 32 pa telefona/LinkedIn nga Dropcontact — batch-i i
    21.08 (`dunhcupmapumfrx`) nuk kthen përgjigje (3 përpjekje); rimerret
    më vonë falas. Për Dafinën për sy: 5 faqe që s'hapen, 5 email me
    domain tjetër nga faqja, 12 firma me seli zyrtare jashtë zonës.
  - Buxhetet 04.09: Apify ~$5.7 nga $19 (cikli deri 01.10, plani STARTER
    në llogarinë e Pole Position), Dropcontact 391 kredite.
  - 1.409 teste jeshile. Asnjë commit — gjithçka në working tree.
- **01.09.2026 — DataWarehouse i Oliverit: 45/45 fushat ekzistojnë dhe
  mbushen vetë.**
  - Katër fusha që ishin bosh u mbushën: Bundesland 93% (`pipeline/bundesland.py`,
    shikim në regjistrin publik të kodeve postare, i ruajtur në
    `daten/plz-bundesland.json` — rindërtimi nuk shkon kurrë në internet),
    Anzahl Mitarbeiter 51% (MailCom, në breza jo si numër i saktë),
    Kurz-Beschreibung 22% (`pipeline/beschreibung_llm.py`, nga webteksti që
    kemi tashmë në disk), Entscheider-Bereich 84% (`pipeline/bereich.py`).
  - CEO/Inhaber u rregullua: 201 firma kishin formula ligjore
    ("Vertreten durch") në vend të emrit. Tash 847 emra të pastër.
  - Blloku 3 (historiku i kontaktimit) u ndërtua si bazë e ndarë:
    `daten/historie.db` me tri tabela. Bosh sepse asnjë fushatë s'është nisur.
  - Gjendja e provuar: 1.387 teste jeshile (vrapim i plotë, 01.09.2026).
  - Mbetet e hapur: gjysma e dytë e fushës "Entscheider-Bereich (für welches
    Produkt)" kërkon një listë produktesh — tash ka vetëm një ofertë.
  - Jira: AP-223.
- Si niset ndërfaqja lokalisht (nga 11.08.2026): `./start-web.sh` te dosja e
  projektit, pastaj http://127.0.0.1:8000. Skripta e lexon `.env` dhe e vendos
  DATEN_DIR te dosja e projektit. Sfondi: `web/main.py` NUK e lexon vetë `.env`
  (atë e bën vetëm pipeline-i përmes `pipeline/env.py`) — pa skriptë, uvicorn
  ndalet me "Fehlende Umgebungsvariable". Për këtë te `.env` rrinë WEB_SECRET
  (nënshkrimi i cookie-t) dhe WEB_COOKIE_SECURE=0 (lokalisht pa HTTPS; te
  serveri aty duhet 1). Hyrja bëhet me `users.yaml` te dosja e projektit (jo në
  repo).
- Repo-ja rri që nga 04.08.2026 në GitHub:
  https://github.com/kkrasnniqi-ket/ai-coldmailing-system (privat, llogaria e
  Ketit). Push-i shkon me llogarinë aktive gh `kkrasnniqi-ket`; autori i
  commit-it është vendosur globalisht te Keti. Çelësat (`.env`), `users.yaml`
  dhe regjistrimet HAR mbeten jashtë me `.gitignore`.
- Pipeline-i i parë dhe ndërfaqja e ekipit janë ndërtuar. Instantly përdoret
  edhe më tej si motor dërgimi.
- Faza 1 e ribërjes së Wholix-it (pamja e fushatave dhe detaji) është ndërtuar:
  vlerat live merren vetëm me lexim nga Instantly, vlerat që mungojnë nuk
  shpiken, dhe lidhja të çon te rregullimet e fushatës në Instantly.
- Faza 2 e ribërjes së Wholix-it është ndërtuar: miratim për çdo marrës dhe çdo
  hap emaili, kërkim, filtra, veprime të grumbulluara, rigjenerim i një teksti
  të vetëm, bllokim i plotë pas dorëzimit, gjendja e Instantly-t vetëm me
  lexim, dhe lista e zgjeruar globale e bllokimit.
- Pjesa e vogël e rënë dakord e Fazës 3 është ndërtuar: te posta e brendshme
  ekipi mund t'i përgjigjet një emaili të marrë nga Instantly. Llogaria
  dërguese duket dhe vjen nga të dhënat e provuara të Instantly-t. Një
  nënshkrim i vlefshëm 15 minuta e lidh kontaktin me emailin; një konsum i
  vetëm dhe atomik pengon dërgimin e përsëritur me të njëjtën provë. Nëse
  përfundimi është i paqartë, nuk ka përsëritje automatike dhe nuk ka buton të
  ri dërgimi derisa historiku të kontrollohet në Instantly.
- Kontroll i plotë i freskët më 22.07.2026: 518 teste jeshile. Një proces të
  vetëm e të gjatë testimi sistemi e mbyllte herë pas here pa gabime dhe pa
  njoftim përfundimtar; prandaj të gjitha testet u ekzekutuan plotësisht në
  shtatë blloqe të freskëta. Paralajmërimi i vetëm është ai i njohuri i
  Starlette te TestClient.
- Kontrolli me sy u bë lokalisht me të dhëna prove të fiksuara. Pamjet desktop
  dhe 390 px të listës dhe detajit janë ruajtur. Në 390 px navigimi rri lart;
  lista ka gjerësinë e plotë të përmbajtjes, pa dalje horizontale të dokumentit,
  dhe vetëm tabela lëviz brenda vetes.
- Më 22.07.2026 Faza 1 u kontrollua edhe vetëm me lexim kundër llogarisë së
  vërtetë të Instantly-t. Të pesë pikat GET të kontrolluara — fushata, treguesit,
  vlerat e hapave, vlerat ditore të llogarive dhe kutitë postare — u përgjigjën
  me HTTP 200; nuk u nxor asnjë emër, adresë a tregues dhe nuk u ndryshua asnjë
  e dhënë. Instantly nuk dha asnjë rresht për ditën e sotme, prandaj mjeti e
  tregon konsumin ditor ndershëm si të panjohur, jo si zero të shpikur.
- Pamja e fushatës përdor numrin e marrësve nga Instantly. Numri i vrapimit të
  fundit të miratuar tregohet veçmas te detaji. Dërgimi i sotëm mblidhet nga
  vlerësimi ditor i llogarive vetëm për kutitë dërguese që përdoren. Dërguesit
  jepen si filtër i detyrueshëm; periudha shkon nga sot deri nesër. Nëse ky
  vlerësim i vetëm bie, vlerat e tjera live nuk bëhen të panjohura.
- Një gjendje e fundit e njohur e kutisë postare mbetet e dukshme edhe kur
  leximi i mëvonshëm dështon, dhe shënohet me kohën e gabimit. Tabela e
  fushatave, mesazhet e gabimit dhe ngjyrat e numrave janë kontrolluar që të
  jenë të kuptueshme edhe me tastierë e me lexues ekrani.
- Kontrolli me sy për Fazën 2 u bë vetëm me të dhëna prove lokale. Provat rrinë
  te `.superpowers/phase-2/`: pamja e miratimeve, tabela e kontrollit, dialogu i
  tekstit, dorëzimi i mbrojtur nga shkrimi, lista e bllokimit dhe të dyja pamjet
  390 px. Në 390 px nuk ka dalje anësore të tërë faqes; vetëm tabelat e gjera
  lëvizin brenda hapësirës së vet.
- Prova e përhershme e punës rri në Jira te `AP-199` dhe është shënuar si e
  kryer.
- Test i kontrolluar nga fillimi në fund më 23.07.2026: një fushatë prove e
  jona në Instantly kishte saktësisht një dërgues, një hap, limit ditor një dhe
  `ingeborgmarder@gmail.com` si të vetmin marrës. Emaili u dorëzua në 10:09,
  përgjigjja e vetme e provës u morr nga Instantly në 10:10 dhe u shfaq te posta
  jonë. Fushata u pauzua menjëherë pas dërgimit.
- Testi live gjeti dhe provoi tri devijime të Instantly-t, që u rregulluan:
  `/leads/list` kërkon filtrin `campaign`, aktivizimi/pauzimi nuk guxon të
  dërgojë lloj-përmbajtje JSON pa përmbajtje, dhe hapat e vërtetë të emailit
  vijnë si `0_0_0`, `0_1_0`, `0_2_0`. Rregullimet janë mbrojtur me teste që në
  fillim dështonin.
- Kontroll i plotë i freskët më 23.07.2026: 520 teste jeshile në një vrapim të
  plotë. Mbetet vetëm paralajmërimi i njohur i Starlette.
- Prova për testin e kontrolluar nga fillimi në fund rri në Jira te `AP-200` dhe
  është shënuar si e kryer.
- Kontroll i plotë i freskët i funksionit të përgjigjes më 23.07.2026: 550 teste
  jeshile në një vrapim të plotë. Mbetet i njëjti paralajmërim i njohur
  Starlette/httpx.
- Kontrolli i dukshëm përdori vetëm të dhëna prove lokale të fiksuara dhe një
  demo pa rrugë dërgimi. Provat rrinë te `.superpowers/phase_3/`:
  `postfach-antwort-desktop.png`, `postfach-antwort-390.png`,
  `postfach-antwort-erfolg-desktop.png` dhe `postfach-antwort-unklar-390.png`.
  Desktop dhe pamja 390 px nuk kanë dalje anësore; kur përfundimi është i
  paqartë, drafti dhe shënimi mbeten të dukshëm, po fusha e përgjigjes dhe
  butoni i dërgimit mungojnë.
- Për ndërtimin dhe kontrollin lokal nuk u dërgua asnjë email i vërtetë dhe nuk
  u lidh e nuk u ruajt asnjë qasje Gmail/Microsoft.
- Krahasimi i ofruesve u përgatit (23.07.2026): para se të fillojë zgjerimi i
  CRM-së, ofruesi i të dhënave për firmat e vogla gjermane duhet vendosur me
  matje. Për këtë u ndërtua gjithçka lokale dhe u mbulua me teste (577 teste
  jeshile): një pjesë Prospeo (`pipeline/sources/prospeo.py`, kërkim mbi
  domain-in e firmës plus pasurim vetëm i emaileve të kontrolluar) dhe një
  vrapues krahasimi i rifillueshëm (`pipeline/vergleich.py`), që Rrugën A
  (Apify→Prospeo) dhe Rrugën B (Apify→Hunter→Dropcontact) i dërgon mbi të
  njëjtën listë firmash nga Apify dhe shkruan raportin plus të dhënat e papërpunuara
  në një dosje vrapimi. Kujdes me emërtimin: te kodi i vjetër i
  `pipeline/sourcing.py` Hunter→Dropcontact quhet ende "Weg A"; te krahasimi
  vlen emërtimi i ri nga porosia (Rruga A = Prospeo). Ende nuk u bë asnjë
  pyetje e vërtetë te ofruesit; mungojnë çelësat PROSPEO_API_KEY,
  HUNTER_API_KEY dhe DROPCONTACT_API_KEY, si dhe okay-i i Leonardit për
  konsumin e kredive (kuotat falas sipas faqeve zyrtare më 23.07.2026: Prospeo
  100 kredite/muaj, Hunter 50 kredite/muaj, Dropcontact 50 kredite falas).
- Kaskada u ndërtua sipas porosisë së shefit (23.07.2026, përcjellë nga
  Leonardi): Google Maps i jep firmat (merret sidomos faqja e internetit),
  pastaj hapat e ofruesve nga `anbieter_reihenfolge` te dosja e klientit
  provojnë NJËRI PAS TJETRIT ta gjejnë vendimmarrësin me email personal të
  kontrolluar ("nëse hapi 1 gjen vetëm 80 nga 100, hapi 2 i provon 20 e
  mbetura"); kush mbetet, merr info@ — e re: para se të merret, kontrollohet me
  Email Verifier të Hunter-it (invalid/disposable/unknown hidhet, përfundimi
  "info_ungueltig"). Raporti numëron për çdo hap kush dha rezultat
  (`deckung.je_stufe`), dhe raporti i krahasimit e llogarit kombinimin e të dy
  rrugëve (pjesa "Kaskade"). Standardi mbetet një hap i vetëm
  Hunter→Dropcontact, derisa krahasimi i ofruesve ta caktojë radhën. 592 teste
  jeshile.
- Vrapim matës më 23.07.2026 me llogari falas të vërteta mbi 20 firma të
  vërteta (ofrues IT në Hannover, lista e 21.07): Rruga A (Prospeo) 6 email
  personalë të kontrolluar, Rruga B (Hunter→Dropcontact) 7; mbi 16 firmat që i
  kontrolluan të dyja, nga 6 secila (37,5%), kombinimi 8 nga 16 (50%) — secila
  rrugë shpëton firma që tjetra nuk i njeh. Asnjë domain i huaj. Katër firma
  mbetën të hapura te Rruga A (limiti ditor i llogarisë falas Prospeo), me
  qëllim nuk u rimorën. Rezervë cilësie: disa gjetje kanë tituj si "Product
  Owner"/"Director" (jo pronar) — kontrolli me dorë nga Leonardi mbetet. Gjetje
  live që u rregulluan: "NO_RESULTS" i Prospeo-s nuk është gabim, Prospeo
  ngadalëson (~45 kërkime/ditë falas), Dropcontact-it i duhen deri ~2 minuta për
  marrje, format gjermane të titujve ("Geschäftsführender Gesellschafter") dhe
  shokët e rremë ("Product Owner") te krahasimi i roleve. Rezultatet rrinë te
  `laeufe/vergleich-anbieter/2026-07-23-prospeo-20-firmen-v2/` (`bericht.md` me
  kolonën e kontrollit me dorë). Konsumi i vërtetë i kredive duhet kontrolluar
  te panelet e ofruesve para se të llogariten çmimet për kontakt.
- Test live i kontrolluar më 23.07.2026: fusha e re e përgjigjes dërgoi
  saktësisht një përgjigje prove qartë të shënuar përmes Instantly-t nga
  `email@seo-poleposition.online` te llogaria jonë e provës
  `ingeborgmarder@gmail.com`. Instantly e konfirmoi dërgimin, mesazhi dalës u
  shfaq menjëherë te historiku i brendshëm dhe Gmail-i e tregoi në 11:42 si
  mesazhin e tretë të të njëjtit thread. Gmail-i ishte vetëm caku i provës dhe
  as atëherë nuk u lidh me mjetin.

- Matja "emri nga impressum → Dropcontact" më 23.07.2026 (pyetja e Oliverit për
  rrugën deri te 80%): te 6 nga 8 firmat me boshllëk, emri i shefit ishte te
  impressum-i; nga të 6 emrat Dropcontact ndërtoi dhe kontrolloi një email
  personal (100%). Mbulimi i ri gjithsej 14 nga 16 firma (87,5%) — mbi cakun
  80%. Detajet dhe rezervat (punë dore, impressum me JavaScript, domain-e
  emaili të ndryshme, impressume që vjetrohen):
  `laeufe/vergleich-anbieter/2026-07-23-prospeo-20-firmen-v2/impressum-messung.md`.
  NDËRTIMI i hapit të impressum-it NUK ka filluar — kërkon okay-in e Oliverit
  (prek rregullin e projektit "asnjë themel i ndërtuar vetë") dhe një plan të
  miratuar.

- Porosia e madhe e Oliverit (24./27.07.2026) është ndërtuar dhe pret vetëm
  çelësat API të llogarive të reja të firmës: hapi i impressum-it (AI lexon
  emrin e shefit, Dropcontact kontrollon; të gjitha rastet e veçanta të vrapimit
  matës si teste), importi i listës (lista 319-she PLR 30–39 rri te
  `laeufe/plr30-39/firmen.json`), skripta e rifillueshme e vrapimit të madh
  (`python -m pipeline.grosslauf`) me njoftim dublikatash dhe raport në formatin
  e Oliverit. Kaskada e vrapimit: prospeo → impressum → info@ (e shënuar si e
  pakontrolluar, kontrolli para dërgimit me llogarinë e ardhshme Hunter të
  x@redschlag.de). Abonimet: Prospeo Starter 49 $ + Dropcontact Starter 29 €,
  karta e Ketit, të miratuara nga Oliveri. 616 teste jeshile, gjendja e
  commit-uar.

- Përgatitja e nisjes së dërgimit më 28.07.2026 (plani:
  `docs/bauplan-versandstart-it-dienstleister.md`, sekuenca 3-hapëshe e
  Oliverit: `docs/email-sequenz-it-dienstleister.md`): të gjithë çelësat API
  rrinë te `.env` dhe punojnë (çelësi i Instantly-t i ri, i testuar; kujdes:
  Cloudflare e bllokon Python-urllib pa shenjë shfletuesi — duket si 403). U
  ndërtua dhe është jeshile (603 teste): kontrolli me Hunter i adresave info@ te
  vrapimi i madh (çelës i detyrueshëm), grupi i ndërtimit të fushatës me emër,
  dërgues e subjekte të vërteta për çdo hap, importi i lead-eve me variablën
  {{anrede}} bashkë me bllokim të fortë kur mungon përshëndetja, roja e tekstit
  (`python -m pipeline.kampagnen_pruefung`, referenca te
  `laeufe/plr30-39/kampagne-referenz.json`). Fushata "Partnerschafts-Anfrage
  IT-Dienstleister PLR 30-39" (id e9f33e56-d753-49ce-92c8-b6915808e969) është
  krijuar si draft joaktiv te Instantly: tekste të vërteta te hapat (Rruga B),
  distanca 7+7 ditë, 20/ditë, hënë–premte 8–19, emri i shfaqur i dërguesit
  "Oliver Redschlag".
- Tekstet e Wholix-it u ruajtën (28.07.2026, porosia e Oliverit e 26.07): të
  gjitha 194 sekuencat (Body 1–3, statusi, 5 përgjigje) plus prompt-i kryesor
  rrinë te `wholix-export/`. Mësim: follow-up-et 2 dhe 3 ishin shabllone të
  fiksuara prompt-i; individualisht gjenerohej vetëm emaili i parë.

- Themeli i burimeve të lead-eve u ndërtua dhe scrape-i i plotë vrapoi
  (29.07.2026, porosia e Oliverit; plani:
  `docs/bauplan-leadquellen-fundament.md`): tri pjesë të reja burimi (Gelbe
  Seiten përmes llogarisë Apify të firmës, OpenStreetMap/Overpass me server
  rezervë, rrjeti i zonave të Google Maps në mënyrë asinkrone) plus pjesa e
  bashkimit me përjashtimet e degëve të Oliverit. Rezultati: **1.481 ofrues IT
  unikë të PLR 30+31** (`laeufe/leadquellen/plr-30-31/`), lista e vjetër 319-she
  vetëm mbushëse (56 të marrë, shënimet për drejtuesit të ruajtura). Kostoja e
  scrape-it ~7 $.
- Gjendja e re e ofruesve (29.07.2026): llogaria Prospeo u ndal gjatë ndryshimit
  të API-së së tyre (çelësi i vdekur, login-i i vdekur) → kaskada vrapon pa
  Prospeo, AI-ja e impressum-it është hapi kryesor. OpenRouter i vdekur → AI-ja
  vrapon me çelësin OpenAI të Leonardit (KI_MODELL=gpt-4.1-mini). Dropcontact:
  llogari e re, 500 kredite/muaj → ndërtimi i adresave në pako mujore prej ~450
  firmash (përputhet me 20/ditë të Oliverit). Hunter falas: 50 kërkime + 100
  kontrolle. North Data u hoq (nuk ka email, vetëm emra).
- Lista përfundimtare e dërgimit është gati (11.08.2026): Oliveri i kishte
  shënuar heqjet e veta te pakoja 450-she ME NGJYRË (kuq) në vend që t'i fshinte
  rreshtat — një eksport CSV i humb ato ngjyra, prandaj duhet gjithmonë .xlsx.
  56 firma të kuqe; 47 prej tyre i kishim nxjerrë tashmë më 30.07 (pajtim),
  9 ishin ende brenda dhe tash dolën. Rezultati:
  `laeufe/leadquellen/plr-30-31/paket-1/versandliste-endgueltig.xlsx` me 320
  rreshta / 317 firma (tri firma rrinë dy herë me dy faqe interneti — CM
  Systemhaus, Veniris, S2-Datentechnik; cila URL vlen, vendoset ende me dorë).
  Veglat e reja për këtë: `pipeline/oliver_markierungen.py` (report / streichen /
  ungesehen) dhe `pipeline/liste_als_json.py`.
- Përshëndetja (Anrede): vegla `pipeline/anrede_spalte.py` është gati (rregulli
  si u planifikua, më mirë neutral se gabim). E RËNDËSISHME, mësuar më
  11.08.2026 në vrapimin e provës: përshëndetja guxon të ndërtohet vetëm PAS
  vrapimit të të dhënave. Nëse ndërtohet nga lista e firmave, merr shefin e PARË
  të përmendur te impressum-i — po vrapimi i të dhënave shpesh arrin dikë tjetër.
  Te 20 firma, kështu 3 kontakte do të kishin emrin e gabuar te përshëndetja
  (IKN: Giffhorn në vend të Kassebom, comNET: Peters në vend të Frings, List +
  Lohr: List në vend të Lohr). Prandaj vlen mënyra
  `anrede_spalte.py aus-lauf <ergebnisse.json>`; kolona e përshëndetjes te
  `versandliste-endgueltig.xlsx` është vetëm draft dhe zëvendësohet.
- Vrapimi i plotë i të dhënave I KRYER (11.08.2026): 317 firma, **214 email
  personalë të kontrolluar (67,5%)**, 65 info@ të kontrolluar, 23 info@ të
  hedhura si të padërgueshëm, 15 të hapura. Tabela e gatshme për dërgim:
  `paket-1/versandfertig-final.xlsx` (279 kontakte, prej tyre 214 me përshëndetje
  gati për dërgim menjëherë; fleta "Zur Kontrolle" mbledh 115 raste për një sy
  njeriu).
  Kuota është nën 90% e vrapimit të provës, dhe kjo është e vërtetë, jo teknike:
  10 firma pa gjetje u kontrolluan sërish duke i çuar një nga një (rruga e
  vjetër) përsëri nëpër Dropcontact — 0 nga 10 dhanë diçka edhe atje. Të parat 20
  ishin firmat e mëdha të listës së vjetër të kuruar; pjesa tjetër janë biznese
  njëpersonëshe që Dropcontact-i thjesht nuk i njeh. Vetë leximi i impressum-it
  vrapoi pastër: 261 nga 263 faqe dhanë një emër.
- Motori i ri `pipeline/schnelllauf.py` (11.08.2026): e njëjta kaskadë, të
  njëjtat kontrolle, po faqet paralelisht dhe Dropcontact në grupe (API-ja e tij
  merr një listë të tërë; ne e kishim përdorur gjithmonë me një emër të vetëm).
  263 firma për ~12 minuta në vend të ~4 orëve. Kreditet mbeten njësoj, sepse
  për çdo raund pyetet vetëm emri i PARË i impressum-it dhe vetëm firmat që
  dolën bosh e kushtojnë të dytin.
  Dy mësime, të dyja të ngulura me teste:
  (1) Një grup është i paguar sapo Dropcontact-i e pranon. Dritarja e vjetër
  2-minutëshe nuk mjaftonte për 100 emra, dhe vrapimi hodhi tutje një grup të
  paguar (u kthye me dorë përmes `request_id`). Tash: dritare e vet 15-minutëshe,
  `request_id` zbret në disk PARA se të merret rezultati, dhe
  `zwischenstand.json` mban faqet e lexuara, adresat e paguara dhe porositë e
  hapura. Në nisjen e radhës u rimorën kështu 103 adresa falas.
  (2) Roja e përputhjes nuk guxon të jetë shumë e ngushtë: Dropcontact-i i
  ndërron emrin dhe mbiemrin ("Peter-Christoph Haider" → "Haider
  Peter-Christoph"). Ndërpritet vetëm kur NUK përputhet AS emri AS domain-i;
  emrat që ndryshojnë shënohen si vërejtje te kontakti.
- Tri vendime për listën e dërgimit (Keti, 11.08.2026):
  (1) Të 65 adresave info@ u shkruhet, me një përshëndetje pa emër. Shablloni i
  emailit është i fiksuar si "Guten Tag {{anrede}}," — aty "Sehr geehrte Damen
  und Herren" nuk hyn, po "zusammen" po. Pra `anrede = "zusammen"` → "Guten Tag
  zusammen,".
  (2) Të 36 domain-et e ndryshme të emailit pranohen pa kontroll me dorë. Ato
  rrinë ende te fleta "Zur Kontrolle", nëse dikush do të shikojë më vonë; më të
  dukshmet janë kleinert-pcservice (gmx.eu, freemailer) dhe Bell (bell.net nga
  një emër i ndarë gabim).
  (3) Të 119 firmat që Oliveri nuk i ka parë kurrë NUK i shkojnë atij paraprakisht.
  96 prej tyre rrinë te lista e dërgimit (78 me email personal) — pra do t'u
  shkruhej pa miratimin e tij. Para aktivizimit, kjo është pika ku Leonardi ose
  Oliveri mund ta vënë re.
- Kontaktet u ngarkuan te Instantly (13.08.2026): të 279 kontaktet nga
  `paket-1/versandfertig-final.xlsx` rrinë te fushata
  `e9f33e56-d753-49ce-92c8-b6915808e969`. Ajo tash quhet
  "Partnerschafts-Anfrage IT-Dienstleister PLR 30-31" (më parë 30-39 — emri
  vinte ende nga lista e vjetër 319-she). Fushata ishte bosh dhe mbetet
  **status 0, pra e fjetur**; nuk u dërgua asgjë. Nga 279 rreshtat e ngarkuar
  Instantly bëri **277**: dy adresat e dyfishta (bergemann@nexave.de dhe
  maik.bandolie@kesolutions.gmbh, secila te dy firma) i bashkoi vetë — askush
  nuk merr dy email. Të 277-tat kanë një {{anrede}} të mbushur.
  Hapat e ardhshëm para aktivizimit: shiko pesë email shembull, dërgo një email
  prove të vërtetë te një kuti e jona, lësho rojën e tekstit, pastaj miratimi
  nga Leonardi/Oliveri.
- Provë e kontrolluar dërgimi (13.08.2026): një fushatë prove e jona
  `7924e36f-e80d-4772-8bd6-e74c19832065` ("[TEST] Zustellprobe PLR 30-31") me
  NJË marrës (d.keqmezi@digitaldiamonds.agency), një hap dhe limit ditor 1
  dërgoi në 11:23 një email të vërtetë nga
  `email@poleposition-automation.online` — subjekti dhe përshëndetja u
  bashkuan saktë nga Instantly. Menjëherë pas kësaj u pauzua (status 2).
  Fushata e vërtetë mbeti e paprekur dhe e fjetur. Para saj vrapoi roja e
  tekstit kundër `laeufe/plr30-39/kampagne-referenz.json`: pa devijime.
- Bllokimi kundër vrapimeve të dyfishta u rregullua (13.08.2026): numrat e
  proceseve i riciklon sistemi operativ — një dosje bllokimi mbante numrin 802,
  që ndërkohë i takonte Notion-it, dhe do ta kishte bllokuar përgjithmonë atë
  klient. `_pid_lebt()` tash kontrollon edhe a fshihet vërtet nën atë numër një
  vrapim "python -m pipeline"; dosja e bllokimit shënon veç kësaj edhe kohën e
  nisjes (dosjet e vjetra me numër të zhveshur mbeten të lexueshme). Prekte jo
  vetëm asistentin, po çdo vrapim dhe edhe pamjen e statusit.
- Kuota e Hunter-it: **kthehet vetë më 02.09.2026** (plani falas, kontrolluar më
  13.08: 50/50 kërkime dhe 100/100 kontrolle të shpenzuara). Nuk bllokon ASGJË
  te dërgimi — të 277 kontaktet te Instantly janë të gjitha të kontrolluara. Të
  prekura janë vetëm 15 firma që do të kishin vetëm një adresë info@ të
  hamendësuar; ato presin shtatorin ose shkojnë përgjithmonë te lista e
  telefonatave/letrave. Dropcontact-i nuk e zëvendëson dot: ai i përgjigjet
  pyetjes "cila është adresa e këtij personi", jo "a ekziston kjo adresë"
  (kontrolluar më 13.08 — për njërën nga 15 firmat nuk dha fare asgjë).
- Kuota e Hunter-it për këtë periudhë faturimi është e shterur (100
  verifikime/muaj, HTTP 429). Prek vetëm adresat info@; të 214 emailet personale
  i kontrollon vetë Dropcontact-i. Të 15 firmat e hapura presin kuotën e re — pa
  kontroll nuk del asgjë.
- Vrapim prove me 20 firma nga lista përfundimtare (11.08.2026): 18 email
  personalë të kontrolluar (90%), 2 info@ të kontrolluar, pa gabime. Dy firmave
  u duhej një provë e dytë (Dropcontact-i nuk u përgjigj në kohë) — vrapimi i
  rifillimit i mori të dyja. Rezultati te `paket-1/probelauf-20/`, tabela e
  gatshme për dërgim te `probelauf-20/versandfertig-20.xlsx`.
- E hapur te Oliveri: 119 firma të listës së dërgimit hynë nga rezerva pas
  kontrollit të tij, ai nuk i ka parë kurrë. Për të rrinë veçmas te
  `paket-1/fuer-oliver-neue-119.xlsx`.
- Gjendja përfundimtare e vrapimit të provës (29.07.2026): 9 nga 10 firma me
  email personal të kontrolluar të shefit (90%), 1 info@ i kontrolluar. U
  ndërtua pjesa e njoftimit të shkurtër për numrat ditorë të Oliverit
  (`python -m pipeline.kurzmeldung`). Vrapimi i emrave (AI-ja e impressum-it mbi
  të gjitha 1.481) është duke vrapuar; rezultati te
  `laeufe/leadquellen/plr-30-31/namenslauf.json`.
- Dokumentimi për Oliverin (19.08.2026 paradite):
  `docs/workflow-documentation.docx` + `docs/workflow-diagram.png` —
  anglisht e thjeshtë, si punon sistemi nga kërkimi deri te dërgimi,
  plus 4 kërkesat e reja të tij me vlerësim. Jira: AP-203 (Done).
  Ia dërgon Dafina vetë. (Shënim: kjo hyrje u shkrua edhe në mëngjes,
  por dosja u kthye diku gjatë ditës në gjendjen e commit-it të vjetër
  — hyrja u rishtua e përmbledhur më 19.08 pasdite.)
- Katër kërkesat e Oliverit TË NDËRTUARA (19.08.2026, plani me hapa e
  prova: `docs/bauplan-kerkesat-oliverit-2026-08-19.md`; 1.049 teste
  të gjelbra):
  (1) PLZ dhe qyteti ndamas kudo — burimet mbushin "ort", fusioni e
  lexon nga adresa një herë në ruajtje; hapi 4 dhe Excel me dy kolona;
  Excel ka edhe kolonën "Rolle"; "Anruf & Brief" tregon personin e
  gjetur edhe pa mail.
  (2) Familjet e shërbimeve (`pipeline/service_categories.py`):
  "Computer Services" = tërë familja IT — NJË hartë për formularin
  (chip "ganze Familie" te hapi 3), numëruesin live, filtrin dhe
  mbledhjen; për scraping me pagesë vetëm ~10 terma të kuruar.
  Përjashtimet e vjetra të Oliverit (hosting/automation/provider)
  mbeten në fuqi — konflikt i shënuar, vendos Oliveri.
  (3) Mbledhja deri-në-cak (`pipeline/firmen_sammeln.sammeln_bis_ziel`):
  numri i hapit 1 = caku; ort bosh = krejt Gjermania si radhë 96
  rajonesh postare; pas çdo rajoni fusion + dedup + numërim; ndalet kur
  arrihet caku ose shterohen burimet; mungesa raportohet me arsye
  (grund_ende, je_gebiet). CLI: `sammeln --ziel N --deutschland`.
  Kufizim i njohur: radhitja e rajoneve përdor numrin e PLZ-ve si
  proxy të dendësisë (Augsburg del i pari, jo Berlini).
  (4) Vendimmarrësit me prioritet (`pipeline/decision_maker.py`):
  CEO/GF → Inhaber → Gründer → Managing Director → drejtues tjetër;
  Impressum-AI kthen edhe rolin (+ LinkedIn vetëm kur shkruan aty);
  te firmen.json ruhen `entscheider` + `entscheider_primaer` EDHE pa
  mail të verifikuar ("ohne_mail"); rradha e parë e Dropcontact shkon
  te rangu më i mirë; firmat pa person mbeten ("kein_entscheider").
  Verifikimi i vërtetë (Deutschland / Computer Services / 100 firma,
  19.08.2026): 4.252 bruto → 3.530 unike (348 dublikata, 374 të
  përjashtuara nga rregullat e Oliverit), 829 qytete; mostra 100 firma:
  67 me vendimmarrës me emër+rol (Impressum-AI, 0 kredite Dropcontact),
  33 pa — mbeten të shënuara. Mësim: limiti i Maps ishte për TERM →
  35× mbi cak; formula u nda me numrin e termave (1.052 teste).
  Rezultatet: `laeufe/leadquellen/sammlung-verifikation-2026-08-19/`.
  Firmat e reja janë tash në bestand të formularit.
- Waterfall + baza master, inkrementi 1 (19.08.2026 mbrëma, specifikimi
  i madh i Oliverit; plani: `docs/bauplan-waterfall-master-db-2026-08-19.md`,
  përmbledhja për ekipin: `docs/waterfall-uebersicht.md`; 1.068 teste):
  (1) prioriteti i roleve NDRYSHUAR sipas radhës së re të Oliverit —
  Inhaber/Owner → CEO → Geschäftsführer/MD → Gründer → tjetër;
  (2) përjashtimi i ofruesve të automatizimit i lidhur në lauf
  (webseite+KI PARA çdo shpenzimi; fusha offers_automation_services etj.;
  firmat mbeten të ruajtura, s'marrin as kredit as telefonatë; formulari
  e ndez vetë me `wettbewerber_pruefung: true` në kunden-file);
  (3) regjistri i ofruesve `pipeline/providers.py` + CLI `anbieter`
  (LinkedIn/Apollo/Clay/North Data të shpallur "nicht implementiert" —
  pa integrime të shpikura); (4) bericht i mbledhjes numëron
  vorher_bekannt/neu kundrejt bestand-it; (5) `pipeline/master_db.py`:
  daten/master.db E RIGJENERUESHME (companies/company_sources/
  decision_makers, plotësia, campaign_eligible i rreptë sipas pikës 16 —
  mbi të dhënat reale 4.969 firma / 5.713 dëshmi / 99 vendimmarrës,
  kampagnenfähig 0 sepse asnjë firmë s'e ka ende kontrollin "no") +
  eksporti Excel me kolonat e Oliverit dhe vendimmarrësit A–E
  (CLI `master-db`, `master-export`). PYETJE E HAPUR: "MailCom" s'ekziston
  askund në projekt — duhet sqarim nga Oliveri; LinkedIn pret vendim
  ToS + qasje; North Data ishte hequr me vendim 29.07.
- FAZA 1 — Rregulli i rreptë i pranueshmërisë së fushatës (20.08.2026
  pasdite, urdhri pas auditimit `docs/audit-oliver-anforderungen-2026-08-20.md`;
  1.069 → **1.080 teste**): Sammeladresat (info@, contact@, office@ ...)
  NUK bëhen më kurrë marrës fushate — as të verifikuara, as (vrima e
  vjetër) të paverifikuara pa verifikues. Ruhen si informacion firme
  (`info_email` + `info_pruefstatus` te firmen.json, ausgang i ri
  "ohne_persoenliche_mail", campaign_eligible=false me arsye
  "personal_decision_maker_email_missing"/"no_decision_maker") dhe firma
  del te fleta "Anruf & Brief". Mbrojtje në 4 shtresa
  (`pipeline/campaign_eligibility.py`): (1) krijimi i lead-it në
  sourcing/schnelllauf/grosslauf (të tre kalojnë nga e njëjta rrugë),
  (2) filtri para tekstit te lauf() (mbron lëshimet e VJETRA të
  rifilluara), (3) dorëzimi `_versand_ausfuehren` filtron + e shënon
  te `versand_ausgeschlossen.json` pa e prekur historikun, (4) porta
  përfundimtare në InstantlySender refuzon ME ZË (përjashtim vetëm
  Ansichts-Probe me `eigene_adresse=True` — dërgim te vetja).
  Deckungsquote numëron tash VETËM kontakte personale; kampanja e vjetër
  e fjetur në Instantly mbetet e paprekur. 17 teste të vjetra u
  përditësuan me sjelljen e re, 11 të reja (10 rastet e detyrës + 1).
  FAZA 2 (klasifikimi i pool-it) PRET MIRATIM.
- FAZA 2 E PËRFUNDUAR (20.08.2026 mbrëma; 1.088 teste): klasifikuesi i
  automatizimit me TRI dalje (yes/no/uncertain) — prompt-i i ri dallon
  automatizimin industrial (SPS/Gebäude → JO konkurrent) dhe produktet
  softuerike nga oferta e vërtetë e automatizimit; faqe e palexueshme =
  uncertain PA thirrje LLM e PA gjykim nga emri; unsicher = i ruajtur,
  jashtë fushate (automation_uncertain), 0 cent. Dy benchmark-e
  100-firmëshe (v1 $0.042 → 4 FP; v2 $0.040 → 0 FP të qarta, 1 kufitar
  inSyca i dokumentuar). POOL-I I PLOTË i klasifikuar
  (`python -m pipeline automation-check`, i rifillueshëm):
  **4.964 firma → 410 yes (8.3%), 2.881 no, 1.673 uncertain**;
  urteil-et te daten/automation-klassifikation.json, ripërdoren nga
  lëshimet e fushatës (0 kosto të dyfishta) dhe nga master.db.
  Pas rindërtimit: **kampagnenfähig 60** (automation no + vendimmarrës
  + email personal i verifikuar); 2.821 "no"-firma presin vetëm
  pasurimin (no_decision_maker). Kosto totale e Fazës 2: ~$1.5 OpenAI.
  Mbetje të njohura: 1.673 uncertain (përmirësohen me render-fallback
  Chrome — inkrement i ardhshëm), 5 not_checked (çelës emri pa domain).
  FAZA 3 (benchmark-u i burimeve) PRET MIRATIM.
- FAZA 3 — benchmark-u i burimeve PJESËRISHT I PËRFUNDUAR (20.08.2026
  natën; artifaktet: `laeufe/vergleich-anbieter/2026-08-20-quellen-benchmark/`):
  mostër fikse 100 firmash nga popullata e saktë (2.821 "no + pa
  vendimmarrës", 74 qytete). Zinxhiri i vetëm i testueshëm me qasjet
  ekzistuese: **Impressum-AI 72/100 me vendimmarrës → Dropcontact 44/72
  email personal të verifikuar = 44 kontakte të përdorshme (44%
  end-to-end)**; kosto 72 kredite (~4,20 €) + ~$0.15 AI ≈ **~10 cent për
  kontakt të përdorshëm**. Validimi manual: 42/44 të saktë (95%), 2 FP
  (MAGNUM person i huaj me domain të huaj; Team VS domain i ndërsjellë)
  — të dy kapen nga shenja ekzistuese "Mail-Domain weicht ab".
  Hunter: i konfirmuar live 429 (kuota deri 02.09). LinkedIn/Apollo/
  Clay/North Data: NOT_CONFIGURED (pa kredenciale — pa teste, pa
  shpikje). Projeksioni për 2.821: ~2.030 emra → **~1.240 kontakte të
  përdorshme** për ~2.030 kredite (≈ 118 € kredite + ~$4 AI). Radha e
  rekomanduar: Bestand → zbulimi (Maps/GS/OSM) → Impressum-AI →
  Dropcontact → Hunter kur rikthehet kuota (falas) → STOP; tool-et-ide
  vetëm me llogari prove + vendim të Oliverit për ~25–30% e mbetur.
  S'u prek asnjë kampanjë/pool/master; kreditet e mbetura ~390.
- Testimi i burimeve, hapi A — falas (20.08.2026, përgjigje ndaj
  email-it të Oliverit "test which sources are useful and in what
  order"; Apollo/Clay etj. i sqaroi si vetëm ide): fusioni raporton tash
  `je_quelle_einzigartig` / `je_quelle_kennt` (kontributi EKSKLUZIV i
  çdo burimi — 1.069 teste). Numrat realë: mbledhja e verifikimit
  3.530 firma → Maps njeh 2.579 (2.511 vetëm ai, 71%), Gelbe Seiten
  729 (711 vetëm ai, 20%), Overpass 292 (239 vetëm ai, 7%) — burimet
  GATI S'MBIVENDOSEN, secili sjell firma që tjetri s'i njeh; krejt
  bestand-i (4.964): 73/15/7% + lista e vjetër 1%. Raporti për Oliverin:
  `docs/source-comparison-report.docx` (anglisht, me planin e matjeve
  B/C dhe pyetjen MailCom). Hapi B (bake-off €-për-kontakt me ~150
  kredite Dropcontact) pret okay të Dafinës; hapi C (North Data/Apollo/
  Clay/LinkedIn mbi të njëjtin kampion) pret llogari + vendim.
- Mbledhje mbi një listë të fiksuar kodesh postare — E NDËRTUAR
  (21.08.2026, kërkesë e Dafinës për zonën 32–39 të Oliverit).
  Deri tash mbledhja dinte vetëm dy mënyra: "vend + rreze" ose "krejt
  Gjermania rajon-për-rajon". E treta tash: një dosje me nga një kod
  postar për rresht.
  - `laeufe/leadquellen/plz-liste-oliver-32-39.txt` — 521 kode.
    KUJDES: kjo dosje s'shkon në git (`laeufe/` është në .gitignore),
    prandaj u fshi një herë pa u vënë re më 21.08 paradite. Lista e
    plotë qëndron edhe në bisedën e asaj dite.
  - `plz_liste_lesen()` në `pipeline/firmen_sammeln.py` e lexon dosjen;
    rreshtat bosh dhe komentet (#) kalohen, çdo rresht tjetër duhet të
    jetë kod pesëshifror — një rresht i shtrembër është gabim, jo
    heshtje, që të mos humbë pa u vënë re një zonë e porositur.
  - `sammeln_bis_ziel(..., plz_liste=[...])` kërkon vetëm në rajonet ku
    bien ato kode dhe mban VETËM firmat që ulen saktësisht mbi një prej
    tyre (fusioni krahason me `startswith`, kodi i plotë pesëshifror =
    përputhje e saktë). Kodi postar fqinj i të njëjtit rajon nuk është i
    porositur, pra bie jashtë.
  - Gelbe Seiten merr emrin e qytetit të rajonit (Bielefeld, Kassel,
    Göttingen ...), jo "Deutschland" — ndryshe do të paguhej shumë e
    gjerë.
  - CLI: `python -m pipeline sammeln --plz-liste <dosja> --dienst
    "Computer Services"`. Me një vend bashkë = gabim. Pa `--ziel` merret
    gjithçka që japin rajonet; raporti e thotë ndershëm
    `grund_ende: quellen_erschoepft`.
  - 1.098 teste jeshile, prej tyre 10 të reja për këtë pjesë.
  - Provë e thatë (pa asnjë burim, pa para): 8 rajone — 38 Braunschweig
    94 kode, 37 Göttingen 86, 34 Kassel 82, 36 Fulda 74, 35 Wetzlar 61,
    33 Bielefeld 55, 32 Herford 45, 39 Magdeburg 24. Vetëm 35033
    (Marburg) s'është në tabelën tonë të koordinatave — pa pasojë, sepse
    rajoni 35 kërkohet me rreze 120 km dhe filtri i saktë e mban firmën
    nëse burimi e sjell.
  - Zona është pothuajse e paprekur: nga 4.969 firma të bazës, vetëm 44
    bien mbi këto 521 kode.
  - Provë e nisur dhe e NDALUR me urdhër të Dafinës (21.08.2026, ~10:16):
    rajoni 33 (Bielefeld, 55 kode) u nis te Apify dhe u ndërpre pas ~7
    minutash. Kosto e vërtetë: **$6.17 për 2.058 rezultate Maps** — pra
    një rajon i vetëm i plotë del rreth $9 dhe të 8 rajonet rreth $72,
    shumë mbi buxhetin 29 $/muaj të llogarisë Apify. Ky është numri i
    matur; vlerësimet e mëparshme (25–40 $) ishin shumë të ulëta.
  - Të dhënat e paguara NUK humbën: dataset-i te Apify
    `yP1tVCwUcW3bNsSQw` (lauf `SBnT7zkcKsCnKFOOz`, ABORTED) i mban
    2.058 rezultatet dhe mund të merren pa paguar sërish.
  - Asnjë mbledhje tjetër nuk niset pa fjalën e Dafinës.
- Kontrolli i automatizimit u bë I DETYRUESHËM (21.08.2026, urdhër i
  Dafinës). Auditi gjeti tri vrima ku kontrolli binte **në heshtje** dhe
  atëherë kalonte çdo firmë, edhe konkurrenti:
  (1) `wettbewerber_pruefung` e kishte parazgjedhjen `false` dhe asnjëra
  nga 17 dosjet te `kunden/` s'e kishte rreshtin — pra atje s'u bë kurrë;
  (2) pa pjesë KI në kaskadë kthehej gjykim bosh; (3) `pipeline/
  schnelllauf.py` — rrugë e tërë ekzekutimi — s'e njihte fare kontrollin.
  Rregulli tash: kush nuk gjykohet qartë si "pa automatizim" është
  `uncertain` dhe nuk hyn në fushatë. AUTOMATION → bllokuar, UNKNOWN →
  bllokuar, NO → vazhdon te kontrollet e tjera.
  - Gjykimi i përbashkët: `urteile_je_firma()` te
    `pipeline/automation_klassifikation.py` — kthen gjykim për ÇDO firmë,
    kurrë vrimë. Radha: pool-i i gatshëm (falas) → tekst faqeje + KI →
    ndryshe `uncertain`.
  - Edhe çelësi i fikur nuk e heq më kontrollin: `false` do të thotë
    "të gjitha të pasigurta", jo "mos kontrollo" — pra zero leads me
    paralajmërim të qartë, jo leads të pakontrolluar.
  - 1.110 teste jeshile (para: 1.098; 12 të reja te
    `tests/test_automation_pflicht.py`).
  - `tests/conftest.py` i ri: për testet e kaskadës vlen "pool-i i ka
    parë të gjitha si të parrezikshme", që ato të testojnë atë për çka
    janë shkruar. Testet e vetë kontrollit e mbishkruajnë këtë.
  - S'u prek asnjë e dhënë firme (`daten/` i pandryshuar), asnjë fushatë
    Instantly, dhe s'u thirr asnjë API me pagesë.
- FUSHATA "IT-Dienstleister – Anschreiben" ISHTE PRAPË AKTIVE
  (21.08.2026, gjetur gjatë hetimit; e njëjta fushatë që u ndal më
  17.08). Kishte 203 kontakte. **U pauzua me urdhrin e Dafinës** më
  21.08 ~11:50 — statusi u verifikua `2 = pauzuar`, dhe tash s'ka asnjë
  fushatë aktive te Instantly (0 nga 12).
  - Kush e riaktivizoi — ZBULUAR nga protokolli i Instantly-t
    (`/api/v2/audit-logs`, 21.08.2026): më **18.08.2026 në 13:25:43**
    një **NJERI në shfletues** (Chrome 151 / macOS, `from_api: false`)
    ndryshoi statusin e pikërisht kësaj fushate. Nuk ishte vegla jonë:
    ajo shkruan gjithmonë `aktiviert.json`, dhe asnjë dosje e tillë nuk
    ekziston; asnjë skedar i projektit nuk e përmend fare këtë ID.
  - Llogaria: `5a7c2fe5-4f60-4e1a-8136-f044224d2ca2` — që është
    **pronari i workspace-it**, e vetmja llogari njeriu në organizatë.
    Prandaj protokolli s'mund ta thotë CILI person ishte: të gjithë
    hyjnë me të njëjtën llogari. Nëse duam përgjegjësi të gjurmueshme,
    duhen llogari të ndara për secilin.
  - Pasoja: pas ndaljes së 17.08 dolën edhe **60 email** (20 më 18.08,
    20 më 19.08, 20 më 20.08). Gjithsej 85 email, 65 persona të kontaktuar.
  - Mjeti për ta parë vetë: `python werkzeuge/instantly-verlauf.py
    --tage 30` (vetëm lexim, s'ndryshon asgjë).
- Björn Hagen dhe Achim Gärtner — kërkesë për heqje (21.08.2026):
  - Përse morën email: fushata u ngarkua nga kalimi i vjetër plr-30-31
    (fund korriku), PARA se të ekzistonte klasifikimi i automatizimit
    (u ekzekutua 20.08 15:36/15:39) dhe kur `wettbewerber_pruefung` ishte
    ende `false` kudo. Pra të dhëna të vjetra, jo anashkalim i logjikës.
  - KUJDES për të ardhmen: të dyja firmat janë të klasifikuara **`no`**
    (jo automatizim) — Nivako si IT-Service, GRTNR.IT si MSSP. Filtri i
    automatizimit NUK do t'i kapte as sot. Mbrojtja e tyre është lista e
    bllokimit, jo klasifikimi.
  - Bllokuar te ne: `sperrliste-global.yaml` — adresat
    `hagen.bjoern@nivako.de`, `achim@grtnr.it` dhe domain-et `nivako.de`,
    `grtnr.it`.
  - Bllokuar te Instantly: të katër vlerat në blocklist-in global, dhe të
    dy leads-at u hoqën nga fushata (203 → 201, verifikuar).
  - Asnjë e dhënë s'u fshi te ne — firma, kontakti dhe historiku mbeten.
- Leja e nisjes u bë E DETYRUESHME NË KOD (21.08.2026):
  `pipeline/versand_freigabe.py` — leje me emër + kohë + fushatë, e
  vlefshme vetëm për një fushatë, e revokueshme. `aktiviere_kampagne()`
  e refuzon aktivizimin pa të. Kjo mbylli rrugën ku prova e pamjes
  (`ansichts-probe`) e aktivizonte fushatën vetë, pa asnjë miratim.
  Krijimi i fushatës dhe miratimi i teksteve NUK janë leje nisjeje.
  Lista e bllokimit tash vepron te porta e fundit para Instantly-t, në
  të tri rrugët e importit — edhe te prova në postën tonë.
  1.124 teste jeshile (para: 1.110; 14 të reja te
  `tests/test_versand_freigabe.py`).
- ZONA 32 (Herford) E PËRFUNDUAR deri te lista me email (21.08.2026,
  porosi e Dafinës mbi 45 kodet postare 32049–32839).
  - **Mbledhja — 542 firma unike.** 497 nga dataset-i Apify i paguar më
    21.08 (`yP1tVCwUcW3bNsSQw`, prova e ndalur për Bielefeld — Herford-i
    binte brenda rrezes, prandaj 525 rezultate ishin tashmë të paguara
    dhe u morën me 0 $). 45 nga Overpass/OSM, mbledhje e freskët falas,
    prej tyre **25 firma që Maps s'i kishte**. Dy kode dolën bosh: 32369
    dhe 32469. Gelbe Seiten dhe North Data NUK rrodhën — buxheti Apify
    ishte 23,83 $ nga 29 $.
  - **Filtrat:** profili IT 193 brenda / 349 jashtë; automatizimi 21
    ofrues dhe 32 të pasigurta jashtë; **140 firma të pranueshme**.
  - **Rikontrolli kufitar u lidh për herë të parë.** `ZWEITE_CHANCE_SYSTEM`
    te `pipeline/branchen_filter.py` ekzistonte që në fillim por përdorej
    vetëm nga testet. Tash rrjedh mbi firmat e hedhura si "prodhues
    softueri / konsulent" dhe **i ktheu 60 firma brenda profilit** (128 →
    188 te vrapimi i Maps). Kusht: së paku 300 shkronja tekst faqeje
    (`MIN_BELEG`) — pa provë s'rikontrollohet, se do të ishte hamendje.
  - **Dropcontact — 86 email nga 114 kontakte (75%).** Kushtoi rreth 89
    kredite neto; Dropcontact-i kthen prapa kreditet e rreshtave pa
    adresë. Mbeten ~319 kredite. `request_id` ruhet në disk sapo
    dorëzohet batch-i, që një ndërprerje të mos i djegë kreditet.
  - **Dedublikim person-nivel:** Frank Ehlers dhe Stephan Schröder dilnin
    secili te dy firma motra — do të kishin marrë dy email nga e njëjta
    fushatë. U hoq nga një. Lista përfundimtare: **84 rreshta**.
  - **Dosjet:** `IT-Liste-Emails-Zona32-FERTIG-20260821-1651.xlsx` (84
    kontakte, formati i Oliverit plus Position, lokacion dhe burim për
    çdo fushë) dhe `zona32-herford-hapi1-20260821-1614.xlsx` (të 542
    firmat me krejt kolonat teknike).
  - **Baza:** 5.494 firma, 244 vendimmarrës, 145 kampanjefähig (84 zona
    32 + 61 të vjetra). KUJDES: email-et e Dropcontact-it në fillim
    mbetën vetëm në Excel — baza ishte rindërtuar para se ai të rrjedhë.
    U rregullua me `werkzeuge/zona32-emails-in-db.py`, që i shkruan
    prapa te dosjet e vrapimit dhe rindërton bazën.
  - **Rregullim i vogël në kod:** `pipeline/master_db.py` e shkruante
    gjithmonë bosh telefonin e personit (kolona ekzistonte, eksporti e
    lexonte, asgjë s'e mbushte). Tash mbushet — 128 nga 144 vendimmarrësit
    e zonës kanë numër. 1.124 teste mbeten jeshile.
  - **Ndarja e burimeve, e matur:** Maps i gjen firmat (497 firma, 468
    telefona, 0 persona). Impressum-i i gjen njerëzit (144 persona, 121
    pozita, 128 telefona, 0 email). Dropcontact-i jep email-et (84). Asnjë
    s'e bën punën e tjetrit — kjo është përgjigjja për pyetjen e Oliverit
    se cilit mjet t'i besojmë.
  - **Vegla:** `werkzeuge/zona32-lauf.py` (mbledhje→filtra→impressum),
    `zona32-overpass.py`, `zona32-dropcontact.py`, `zona32-itliste-final.py`,
    `zona32-export.py`, `zona32-emails-in-db.py`.
  - Instantly i paprekur, asnjë email i dërguar, asnjë fushatë e krijuar.
- Publikimi te serveri U SHTY (21.08.2026, vendim i Dafinës: "lere
  njehere mos e publiko"). Ndërtimi te `deploy/DEPLOY.md` mbetet i
  gatshëm; të dhënat e zonës 32 rrinë vetëm lokalisht.
- **31.08.2026 — filtri i firmave me softuer të vetin.** Dafina gjeti
  gjashtë firma të gabuara në listat 33 e 34 (Mibema, GRAPHISOFT Kassel,
  elastify, netgo tax, BLUVIT, kisocon). Katër kishin hyrë nga hapi
  "shansi i dytë", që i kthente brenda zhvilluesit e softuerit sapo faqja
  përmendte edhe mirëmbajtje IT.
  - Rregulli i ri është te `AGENTS.md` dhe vlen për **të gjitha zonat**,
    edhe të vjetrat: jashtë kush zhvillon/shet softuer të vet, kush ka
    produkt për një degë të ngushtë, partnerët e produkteve të huaja
    (Salesforce, SAP, DATEV) dhe firmat me sigurinë si thelb. Mirëmbajtja
    e Microsoft 365 mbetet brenda.
  - Kodi: `pipeline/branchen_filter.py` ka ndalesën e re të fortë
    `eigene_software` (kategoria e drejtorisë, pa kosto) dhe prompt të
    rishkruar; hapi "shansi i dytë" u hoq nga
    `werkzeuge/zona32-lauf.py`. 1308 teste jeshile.
  - Gjashtë firmat janë te `sperrliste-global.yaml`.
  - Rishikimi i listave 32–34 (241 kontakte): rregulli i fortë heq 61,
    gjykimi i ri do të hiqte edhe 62. **Vendim i Dafinës: u hoqën vetëm
    të 61-tat**, të tjerat mbetën për shqyrtim.
  - **01.09.2026 — heqja u plotësua.** Dafina pyeti çka mbeti brenda dhe
    doli se nga 180 kontaktet vetëm 118 ishin IT klasike; të 62-tat e
    tjera (19 softuer, 18 siguri, 8 tregti, 8 produkt dege, 6 tjetër,
    2 hoster, 1 e paqartë) i hoqi edhe ato. **Listat tash: 40 / 49 /
    29 = 118 kontakte**, të gjitha me email, të numëruara pa vrima.
    Raporti me arsyen e secilës heqje:
    https://claude.ai/code/artifact/d839a897-8ab4-4d27-ac11-ca4a408c7103
  - Instantly u kontrollua vetëm me lexim: listat e zonave nuk janë atje,
    asnjë fushatë nuk është aktive.
  - E hapur: fushata "Partnerschafts-Anfrage IT-Dienstleister PLR 30-31"
    te Instantly ka 277 adresa, po vetëm 4 përputhen me skedarin
    PLR 30-39 që kemi këtu — duket ndërtuar nga një version tjetër i
    listës. Nuk u prek.

## Vendimet

- **08.09.2026 — Faza 2: identiteti i firmës.** Çdo firmë ka `firma_uid`, një
  numër që nuk lëviz kurrë, i ruajtur te `daten/stamm.db` (bazë e përhershme, si
  `historie.db`). Një `kennung` = një `firma_uid`; asgjë nuk bashkohet vetvetiu
  — as me emër, as me emër + PLZ. Bashkimi bëhet vetëm me dorë me
  `stamm_db.set_alias()` dhe zhbëhet me `alias_loesen()`. `companies.id` te
  `master.db` mbetet vetëm numër rreshti dhe nuk guxon të ruhet nga jashtë.
  Dedupe i email-eve nuk u prek — rri te `pipeline/dedupe.py`. Rregulli i plotë
  dhe arsyeja te `AGENTS.md`. `firma_uid` doli edhe si kolona e parë "ID" te
  eksporti Excel, që dorëzimi i sotëm dhe Postgres-i i nesërm të mos tregojnë
  gjëra të ndryshme për të njëjtën firmë. Oliveri duhet njoftuar se pamja e
  tabelës ndryshoi.
- **08.09.2026 — Faza 3: Postgres në Docker, skema dhe rolet.** Ngrihet me
  `docker compose --env-file .env -f deploy/docker-compose.postgres.yml up -d`.
  Porti rri **vetëm te 127.0.0.1** — në server nuk hapet asnjë port derisa të
  vendoset si lidhet Oliveri. Dy skema në një bazë: `kern` (firma, entscheider,
  firma_quelle) dhe `historie` (kontakt, uebergabe, opt_out). `firma_uid` është
  çelësi primar dhe vjen nga `stamm.db`; Postgres nuk e gjeneron kurrë. Dy
  role: `coldmail_sync` (shkruan `kern`, te `historie` vetëm lexon dhe shton) dhe
  `coldmail_read` (vetëm lexon). Kërkesa e Fazës 4 për `zusammengelegt_in` u fut
  që tash te skema, po ashtu `historie.kontakt` pa kufirin 1–3. Pamja
  datawarehouse nuk u ndërtua — ajo mbetet Faza 4.
- **08.09.2026 — Faza 4: pamja `datawarehouse`.** Oliveri lexon
  `SELECT * FROM datawarehouse;` dhe merr 46 kolona në rendin e vet: 16 fusha
  firme + 25 për A–E + "Rausgegeben an" + tri kontakte + opt-out. A–E të
  sheshuara; vendimmarrësi i gjashtë mbetet te `kern.entscheider` po nuk
  shfaqet. Fushat pa burim rrinë NULL — pamja nuk mbush asgjë. Firmat e
  bashkuara (`zusammengelegt_in` i mbushur) nuk dalin fare. Opt-out-i vetëm me
  email gjendet përmes domain-it të email-it kundrejt `kennung` — vetëm lexim,
  historia nuk preket. `coldmail_read` lexon pamjen; `coldmail_sync` nuk ka
  leje mbi të.
- **08./09.09.2026 — emrat e kolonave (Dafina).** Lista e vetë Oliverit
  ("AW: DataWarehouse – Datenbank-Felder") ka saktësisht **46** fusha, pra numri
  është i konfirmuar. Nga emrat u morën ata të tijtë kudo ku dallimi është i
  vërtetë: `Datenquelle (woher, wann)→Daten-Ursprung (woher/von wem, wann)`,
  `Sektor→Branche`, `Auswahl-Stichworte→Selektions-Keywords`, `Webseite→www`,
  `A–E) Bereich→A–E) Entscheider-Bereich (für
  welches Produkt)`, `A–E) Rolle→A–E) Entscheider-Position`. Mbetën si ishin
  dallimet vetëm drejtshkrimore: `Straße` (ai shkruan Strasse),
  `Kurzbeschreibung`, `Mitarbeiterzahl`, `E-Mail (allgemein)`, dhe kokjet e
  shkurtra `1./2./3. Kontakt` — kllapat e gjata te lista e tij përshkruajnë
  përmbajtjen e fushës, nuk janë emra kolonash. Te blloku A–E vetëm dy nga pesë
  kolonat e mbajnë parashtesën "Entscheider-" — zgjedhje e vetëdijshme e
  Dafinës, jo harresë; nuk barazohet për simetri. Ndryshimi preku vetëm kokjen:
  529.516 qeliza të dhënash u krahasuan para/pas, **0 ndryshuan**.
  `(für welches Produkt)` është pjesë e emrit të tij; vlera mbetet ajo e
  `bereich` nga roli — produkt nuk shpiket. Mbetet e hapur vetëm nëse Oliveri
  i pranon emrat që i mbajtëm.
- **Kërkesë për Fazën 4 (skema), e shënuar më 08.09.2026 që të mos harrohet:**
  kur një `firma_uid` zhduket nga burimi sepse u bashkua me `set_alias()`,
  rreshti i tij te Postgres mbetet jetim. Skema duhet ta zgjidhë këtë që tash,
  jo në Fazën 6 kur është vonë. Preferenca: **të mos fshihet**, por të shënohet
  me `zusammengelegt_in` që tregon uid-in mbijetues — fshirja e heq gjurmën,
  kurse shënimi e mban historinë e vjetër të lexueshme.
- Instantly mbetet motori i padukshëm i dërgimit. Mjeti i lexon të dhënat e tij
  për pamjen e fushatave; veprimet e vërteta të shkrimit nuk janë pjesë e
  kontrolleve lokale.
- Llogaria e provës Gmail shërben vetëm si kuti postare prove pa rrezik. Ajo nuk
  lidhet përgjithmonë me mjetin. Një hyrje direkte në Gmail, qasje Google të
  ruajtura ose një krahasim i vazhdueshëm i postës nuk janë të miratuara.
- Testi i suksesshëm nga fillimi në fund nuk e ndryshon këtë: Gmail-i ishte
  vetëm marrësi dhe dërguesi i përgjigjes manuale të provës. Mjeti ynë nuk mori
  asnjë qasje në Gmail; dërgimi dhe marrja e përgjigjes shkuan vetëm përmes
  Instantly-t.
- Më 23.07.2026 u caktua vëllimi i zvogëluar i Fazës 3: posta e brendshme guxon
  t'i përgjigjet, përmes pikës zyrtare të Instantly-t, një emaili fushate që
  është marrë tashmë. Vazhdon të mos ketë lidhje direkte Gmail/Microsoft, as
  dërgim të lirë emailesh, as krahasim të plotë të kutisë postare.
- Ndërtimi dhe prova e tij rrinë në Jira te `AP-201`; detyra është shënuar e
  kryer me provën e plotë të testeve dhe të pamjes.
- Plani i ndërtimit i drejtuar nga testet rri te
  `docs/superpowers/plans/2026-07-23-instantly-antworten.md` dhe u zbatua i
  tëri.
- Rregullimet e fushatës (limiti ditor, dritarja e dërgimit, nënshkrimi dhe
  vlera të ngjashme) nuk ribëhen te mjeti. Rruga për to është lidhja drejt
  Instantly-t.
- Tregohen vetëm fushat e besueshme të Instantly-t. Për "të dështuara" dhe për
  gjendjet e radhës që nuk vijnë të ndara, ndërfaqja nuk tregon asnjë vlerë të
  vlerësuar.
- Instantly dhe vrapimi i miratuar mbeten burime të ndara të dhënash: treguesit
  live dhe radha mbështeten te Instantly; vrapimi lokal tregohet vetëm si vlerë
  krahasimi më vete.
- Unaza e radhës nuk i llogarit të padërgueshmit si grup të vetin. Ajo tregon
  vetëm "të dërguara" dhe pjesën tjetër "jo e ndarë në dispozicion". Të
  padërgueshmit rrinë veçmas poshtë me një shënim mbivendosjeje.
- Numri i përmbledhur i fushatave aktive llogaritet vetëm kur të gjitha fushatat
  e marra parasysh kanë status të njohur.
- Të nëntë funksionet e Wholix-it të hequra më 22.07.2026 mbeten të hequra;
  sidomos pa menaxhim përdoruesish, pa telefonata, pa shënime dhe pa AI-chat.
- Te Faza 2 çdo tabelë kontrolli tregon saktësisht një raund emailesh. Secili
  nga tre hapat konfirmohet veç e veç; disa marrës mund të konfirmohen bashkë.
  Te Instantly shkon edhe më tej vetëm raundi i konfirmuar plotësisht.
- Një tekst i papërshtatshëm nuk përpunohet lirshëm, po rigjenerohet saktësisht
  për atë hap. Gjendjet e panjohura të Instantly-t mbeten të panjohura.
- Lista globale e bllokimit merr arsye dhe koment, si dhe shabllone si
  `*.bund.de`; hyrjet e vjetra të thjeshta YAML mbeten të lexueshme.
- Pyetja te Instantly për miratimin është vetëm lexim dhe konservative. Vetëm
  kur në një histori ka saktësisht një email dalës, një përgjigje i caktohet
  atij hapi. Kur ka disa hapa të mundshëm, caktimi mbetet i panjohur, ndërsa
  gjendja e përgjithshme e provueshme mbetet e dukshme.
- Pas dorëzimit, raundi i emailit është i mbrojtur nga shkrimi te mjeti. Një
  rigjenerim i vetëm e hap sërish vetëm hapin e prekur.

- **Baza rri te Rruga A (Dafina, 01.09.2026).** Baza kryesore `master.db`
  rindërtohet e tëra nga dosjet çdo vrapim (`DROP` + `CREATE`); çdo kolonë
  llogaritet përsëri. Ndryshimet që i bën njeriu nuk rrinë aty — ato rrinë
  te `historie.db`, dosje krejt e ndarë (vendim i mëparshëm i Dafinës,
  28.08.2026).
  Pse: sot askush nuk shkruan me dorë në bazë, çdo kolonë del nga dosjet, dhe
  rindërtimi zgjat 0,3 sekonda për 7.777 firma. Përfitimi u pa po atë ditë —
  një gabim te 201 firma (CEO/Inhaber) u rregullua thjesht duke u rindërtuar.
  Kur duhet rishikuar: kur interface-i të fillojë të shkruajë direkt në bazë.
  Atëherë duhet Rruga B — kolonat ndahen në "të shkruara nga njeriu" dhe "të
  llogaritura nga sistemi", dhe sistemi nuk i prek kurrë të parat. Çmimi i B-së
  që duhet pranuar me vetëdije: një korrigjim i formulës nuk shkon më te
  rreshtat e vjetër. Rruga C (vetëm shtim, pa fshirje) u refuzua.
- Vendimet themelore për CRM-në janë marrë (Leonard, 29.07.2026) — me këtë
  ndërtimi i CRM-së është i zhbllokuar sapo t'i vijë radha: (1) kontaktet
  rrjedhin vetë te CRM-ja, po VETËM kush ka dhënë përgjigje; (2) shkallët e
  shitjes si te Wholix, të etiketuara gjermanisht (të kontrollohen kundër fotove
  të ekranit); (3) përdorues i vetëm Leonardi; (4) ruajtja: një dosje baze
  SQLite te dosja e të dhënave. Fotot e ekranit të Wholix-it rrinë sërish te
  projekti (dosja "wholix interface screenshots", e kopjuar nga desktopi i
  Leonardit).

## Hapat e ardhshëm

### Detyrë e veçantë: tri gjëra PARA Fazës 5 (hapur 08.09.2026)

Sync-u i Fazës 5 do t'i bartë të dhënat ashtu siç janë, prandaj këto
shikohen para tij, jo pas.

1. **833 firma me prejardhje `gelbe_seiten` rrinë ende te `master.db`.**
   Rregulli i 04.09.2026 te `AGENTS.md` thotë se ato të dhëna dolën jashtë
   `laeufe/` pikërisht që ndërtimi i `master.db` të mos i marrë. Nëse i mban
   prapë, atëherë ose rregulli nuk u zbatua plotësisht, ose `master.db` nuk
   është rindërtuar që nga ajo datë, ose ka një rrugë të dytë leximi që nuk
   e ka parasysh askush. Të tria duhen sqaruar para se pasqyra t'ia dërgojë
   ata rreshta Oliverit. Gjetur gjatë matjes së `Mitarbeiterzahl` më
   08.09.2026 (numri vetë nuk varet prej tyre: 49,1 % me gjithçka, 49,9 %
   pa to).
2. **Një test i web-it shkruan në dosjen e vërtetë të projektit**, jo në atë
   të përkohshme. Te `entwuerfe/` ka mbeturina nga 12 gushti e këtej dhe 62
   sosh kanë hyrë në git. Çdo vrapim i suitës lë skedarë të rinj.
3. **Venv-i ka dy vende.** `./.venv/bin/pip` shkruan te
   `/Users/.../Desktop/AI Coldmailing system/.venv/` — projekti u zhvendos në
   `Documents` po venv-i mbeti i lidhur me shtegun e vjetër. Instalimet duhen
   bërë me `./.venv/bin/python -m pip install ...`, ndryshe paketa shkon në
   vend që s'e sheh askush.

### Fazat e Postgres-it

Faza 5 është sync-u (SQLite → Postgres). Vendimi për rreshtat jetimë te
`zusammengelegt_in` është marrë tashmë dhe rri te "Vendimet". Numri 46 i
kolonave pret konfirmimin e Oliverit — teksti i pyetjes iu përgatit Dafinës
më 08.09.2026.

### Nisja e dërgimit

Plani i nisjes së dërgimit (baza tash është lista e RE 1.481-she, jo më e
vjetra 319-she — detajet te të dy planet nën `docs/`):

- Të pritet vrapimi i emrave (është duke vrapuar), pastaj pakoja mujore 1
  (~450 firma me emër të gjetur, të prioritizuara) përmes ndërtimit të adresave
  me Dropcontact — nga aty del vlerësimi i rezultatit për Oliverin (gjithsej,
  kuota, lista e telefonatave/letrave).
- Pastaj të mbushet kolona e përshëndetjes për çdo kontakt (Claude, neutral kur
  ka pasiguri) dhe të paraqitet e plotë për kontroll.
- Kontaktet e kontrolluara me përshëndetje të ngarkohen te fushata
  (`import_leads_mit_anrede`), të tregohen 5 email shembull plus një email prove
  i vërtetë te një kuti postare e jona e provës, dhe të lëshohet roja e tekstit.
- Të aktivizohet vetëm pas miratimit nga Leonardi/Oliveri; pastaj çdo ditë
  njoftimi i shkurtër me numrat te Oliveri (kush është përgjegjës për t'u
  përgjigjur përgjigjeve, të sqarohet para nisjes).
- Më vonë ose paralelisht: zgjerimi i CRM-së të projektohet si pako pune e
  vetën; pjesët e tjera të Wholix-it mbeten të hequra, për sa kohë vendimet e
  vëllimit nuk ndryshohen shprehimisht.
- Kontrollet me shkrim të dërgimit ose të kutisë postare, vetëm me miratim të
  qartë dhe me llogari prove.
