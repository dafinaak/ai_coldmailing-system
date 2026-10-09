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

- **09.10.2026 — RAJONI 80-86 (Bavaria): 76 kontakte, 4 zona.**
  `IT-Liste-Emails-Zonat-80-89-20261009-0941.xlsx`. **Gjithsej tash 974
  kontakte në gjashtë dosje**, 974 email të ndryshëm, zero dublikata.
  - **I tërë rajoni ka vetëm katër qytete me >= 4 kode:** München (82),
    Augsburg (15), Ingolstadt (5), Rosenheim (4). Dhjetëshet **82 dhe 84
    s'kanë asnjë** - fshatra. Prandaj dolën 4 zona, jo 10.
  - **Mynihu është zona "8", jo "80".** Kodet e tij shtrihen nëpër 80xxx,
    81xxx dhe 85xxx; emri i zonës duhet të jetë fillimi i çdo kodi.
    Dha **55 kontakte nga 78 të pyetur (71%)** - zona më e pasur e tërë
    projektit, me 84 vendimmarrës.
  - Augsburg 15, Rosenheim 6, Ingolstadt **0** (2 persona, asnjë email).
  - Baza: **22.810 firma, 2.244 vendimmarrës, 994 kampagnenfähig.**
  - **Apify: cikli mbylli me 47,92 $** (kufiri 19 → 46 → 48 me fjalën e
    Dafinës, pastaj prapë 19 $). Kreditet: **1.402** - blerja e 1.500-ve
    kishte hyrë; leximi i 08.10 ishte thjesht para saj.
- **09.10.2026 — Tri gabime të miat në një ditë, të tria rreth kufijve.**
  - **Kufijtë e ngushtë e prenë Augsburg-un dy herë** (1,20 dhe 1,50 $).
    Një vrapim i prerë shënohet i paplotë dhe duhet bërë prapë, pra
    paguhet dy herë. Herën e tretë nuk pagova: dy dataset-et e paguara
    kishin **419 vende në 14 nga 15 kodet**, mbulim i mirë, dhe zinxhirin
    e vazhdova mbi to. Kushtoi 2,7 $ kot. **Mësimi, i shkruar edhe te
    komentet e `pipeline/zonen.py`: kufiri i ngushtë nuk kursen asgjë.**
  - **Mbledhësi i dhjetëshes e humbi Mynihun në heshtje.** `newest_per_zone()`
    kërkonte emra zonash dyshifrorë, dhe `80 <= int("8") <= 89` është
    false - pra dosja 80-89 doli me **21 kontakte në vend të 76**, pa u
    ankuar. U ndreq: një emër zone është prefiks kodesh, dhe njëshifrori
    mbulon tërë dhjetëshen. E ruan
    `tests/test_zone_lists.py::test_einstellige_zone_gehoert_in_ihre_dekade`.
  - Të dyja janë e njëjta rrënjë: **diçka dështon pa u ankuar.** Është e
    treta javë radhazi (OSM-ja me 504, kontrolli me 0 rreshta, tash ky).
- **08.10.2026 — RAJONI 70-79 (Baden-Württemberg): 145 kontakte, 10 zona.**
  `IT-Liste-Emails-Zonat-70-79-20261008-1128.xlsx`. **Gjithsej tash 898
  kontakte në pesë dosje** (30-39: 248, 40-49: 257, 50-59: 113, 60-69: 135,
  70-79: 145), **898 email të ndryshëm — asnjë dublikatë**.
  - **NUK është porosi e Oliverit.** Lista e tij mbaron te 69. Këtë e
    kërkoi Dafina më 08.10. Kodet dolën nga `daten/plz-liste-70-79.csv`,
    nxjerrë nga tabela gjermane e kodeve — pra çdo kod ekziston vërtet.
  - **Rregull i ri për qytetet:** rrethi mbulon vetëm kodet brenda **10 km**
    nga qendra. Tabela i quan "Karlsruhe" edhe qyteza si Bruchsal-i, 17,9 km
    larg; pa këtë rregull rrethi do të ishte 20 km dhe do të paguante
    1.266 km² në vend të 295. Kodet e lëna jashtë janë shënuar te çdo listë.
  - **42 kode u matën me OSM para se të caktohej ndonjë rreth.** 15 koordinata
    ishin të ngjeshura te qendra e qytetit dhe u ndreqën; 25 dolën kuti
    postare pa zonë; dhe **2 përputheshin me kode të huaja** — 76110 ra
    584 km larg (Francë), 79093 plot 9.380 km (Meksikë). Ato dy i lashë
    jashtë; pa kontroll do të kishin prishur rrathët e Karlsruhe-s e
    Freiburg-ut.
  - **Kodet e kutive postare u lanë jashtë listave** (ndryshe nga 40-69, ku
    i kishte porositur Oliveri). Arsyeja: s'kanë zonë në hartë, pra Maps
    s'i kthen dot, dhe koordinatat e tyre janë të pasakta — testi e kapi
    te 71029 (zyrë tatimore) që binte 13,4 km jashtë rrethit.
  - **Rendimenti është më i ulët se te 40-69.** Karlsruhe: 620 firma → 38
    brenda profilit (6%), kurse Këlni jepte 11%. Heilbronn: 235 firma → 8
    me person → **5 kontakte**. Duket se rajoni ka shumë firma softueri e
    inxhinierie (Bosch, SAP e rrethina), të cilat rregulli ynë i nxjerr
    jashtë — ne duam mirëmbajtës IT, jo prodhues.
  - Kontakte për zonë: Karlsruhe 22, Freiburg 19, Stuttgart 18, Offenburg
    18, Göppingen/Aalen 17, Ludwigsburg/Böblingen 17, Tübingen 12,
    Konstanz 11, Pforzheim 6, Heilbronn 5.
  - Baza: **21.852 firma, 2.094 vendimmarrës, 917 kampagnenfähig.**
  - **Apify: cikli mbylli me 39,60 $** (kufiri u ngrit 19 → 44 $ me fjalën
    e Dafinës, pastaj u kthye në 19 $). Rajoni kushtoi ~13,8 $, pra rreth
    20,6 $ shtesë mbi abonimin për tërë ciklin. Kreditet: **58** — mezi
    mjaftuan; 80-86 nuk niset dot pa rimbushje.
- **07.10.2026 — TË 20 ZONAT E POROSITURA JANË KRYER. 753 kontakte në
  katër dosje, një për çdo dhjetëshe.**

| dosja | zonat | kontakte |
|---|---|---|
| `IT-Liste-Emails-Zonat-30-39-20261007-1108.xlsx` | 32–39 | 248 |
| `IT-Liste-Emails-Zonat-40-49-20260930-1511.xlsx` | 40–49 | 257 |
| `IT-Liste-Emails-Zonat-50-59-20261007-1053.xlsx` | 50–55 | 113 |
| `IT-Liste-Emails-Zonat-60-69-20261007-1456.xlsx` | 60–69 | 135 |

  Dafina kërkoi **vetëm një dosje për dhjetëshe**; listat zonë-për-zonë
  u fshinë (81 skedarë, shumica në git, pra të rikthyeshme).
  **Kujdes: kjo fshirje prishi dy porta sigurie** — shih dy shënimet e
  mëposhtme. Të dyja u ndreqën, po mësimi mbetet: këto dy vegla lexonin
  listat zonë-për-zonë, dhe pa to **kalonin në heshtje**.
  - **Dhjetëshja 60–69, tetë zona, 135 kontakte.** Frankfurt 39→35,
    Mannheim 30→29, Saarbrücken 18, Wiesbaden 22→21, Darmstadt 14,
    Ludwigshafen/Kaiserslautern 8→7, Heidelberg 7→6, Offenbach 5.
    Apify 12,9 $, AI 2,6 $. Cikli mbylli me **25,84 $** (19 abonimi +
    6,84 shtesë, me fjalën e Dafinës; kufiri u kthye në 19 $).
  - **Zona 65 dhe 67 morën nga dy rrathë**, se qytetet e tyre janë larg:
    65 → 1.521 km² me një rreth kundrejt **325** me dy; 67 → **4.072**
    kundrejt **187** (qytetet 48 km larg). Pa këtë do të ishin paguar
    gati 5.000 km² hartë boshe.
  - **Tabela e koordinatave ishte seriozisht e gabuar te Saarbrücken e
    Mannheim.** Tetë kode të 66-ës dhe katër të 68-ës rrinin te një pikë
    e vetme, 0,5 dhe 1,9 km nga qendra; me OSM dolën deri **9,0** dhe
    **9,5 km**. Me rrezet e vjetra **pesë kode nuk do të kërkoheshin
    fare**. U ndreqën 12 koordinata dhe u shtuan 2 që mungonin (60312,
    60315); rrezet u bënë 10,8 dhe 9,7 km.
  - **Offenbach-u u shpëtua nga një 502 i Apify-t.** Vegla jonë u rrëzua
    ndërsa pyeste për gjendjen e vrapimit; vrapimi vetë vazhdoi dhe
    mbaroi me 301 vende (0,90 $). U mor dataset-i i tij në vend që të
    rinisej — pa pagesë të dytë. **E metë e mbetur:** funksioni
    `mit_wiederholung()` te `werkzeuge/zonen-maps.py` nuk e riprovon
    502-shin, edhe pse quhet "me riprovë". Duhet ndrequr.
  - **OSM dështoi në heshtje dy herë** (zonat 51 e 63, gabim 504): ktheu
    0 firma dhe zinxhiri vazhdoi pa u ankuar. Riprovat dhanë 18 dhe 1
    firmë. Rregulli: kur raporti thotë `overpass found 0`, kontrollo
    regjistrin për 504 dhe provoje prapë — është falas.
- **07.10.2026 — Fshirja e listave zonë-për-zonë i la dy porta të verbra.**
  - **Kontrolli i listave** (`werkzeuge/listen-pruefung.py`) lexonte
    vetëm `...ZonaNN-FERTIG-*.xlsx`. Pas fshirjes raportoi "0 gjetje në
    0 rreshta" — porta e cilësisë tha "në rregull" pa kontrolluar asgjë.
    Tash lexon edhe dosjet e dhjetësheve, dhe **një vrapim pa asnjë
    listë është gabim, jo gjelbërim i heshtur**.
    E ruan `tests/test_listen_pruefung_quellen.py` (6 teste).
  - **Rregulli "një njeri, një email" mes zonave** te
    `werkzeuge/zona32-itliste-final.py` lexonte po ato skedarë. Pa ta,
    dhjetëshja 60–69 doli me **nëntë njerëz që rrinin tashmë** te 30–39
    ose 40–49 (IT-HAUS, Ratiodata, Concat, Medialine, H&G, C.B.C.,
    Compose IT, KPC, implement-IT). Ata do të kishin marrë të njëjtën
    ofertë dy herë — gabimi i 17.08.2026. U nxor te
    `kontakte_kleinerer_zonen()`, që lexon të dyja format; te dosja e
    dhjetëshes vendos **kodi postar i rreshtit**, jo emri i skedarit,
    që një zonë të mos i fshijë rreshtat e vet.
    E ruan `tests/test_itliste_zonen_dublikate.py` (4 teste).
- **07.10.2026 — DHJETËSHJA 50–59 E PLOTË: 113 kontakte në një dosje të
  vetme.** `IT-Liste-Emails-Zonat-50-59-20261007-1053.xlsx`.
  Lista e Oliverit ka vetëm pesë zona në këtë dhjetëshe — 50, 51, 52, 53
  dhe 55. **54, 56, 57, 58, 59 nuk janë fare në porosi** (zero kode te të
  dyja listat). Po t'i donim ndonjëherë: 54 = Trier (115 kode), 56 =
  Koblenz e Neuwied (172), 57 = Siegen e Olpe (66), 58 = Hagen, Witten,
  Lüdenscheid, Iserlohn (69), 59 = Hamm, Arnsberg, Lippstadt (85) —
  gjithsej 507 kode, rajone me shumë fshatra, pra si zona 49.
  - **Zona 53 (Bonn), 20 kode → 18 kontakte.** Një rreth 9,5 km.
    Maps 1,81 $, AI 0,44 $. 458 firma (422 të reja), 32 brenda profilit,
    28 me person; OSM dha 32 firma. Dropcontact: 24 të pyetur,
    **18 email (75%)** plus 3 falas, 2 catch-all. Tre dolën në zona më
    të vogla.
  - **Zona 55 (Mainz, Wiesbaden), 13 kode → 24 kontakte.** Një rreth i
    vetëm 7,2 km mbulon të dyja qytetet — qendrat janë vetëm 4,5 km larg,
    pra një rreth i dytë do të paguante të njëjtin truall dy herë.
    Maps 1,34 $, AI 0,33 $. 329 firma (301 të reja), 43 brenda profilit,
    35 me person; OSM dha 20. Dropcontact: 32 të pyetur,
    **24 email (75%)** plus 2 falas, 3 catch-all.
  - **Ndreqje te tabela e koordinatave:** 55118 dhe 55127 rrinin te e
    njëjta pikë (qendra e Mainz-it) dhe **nuk ishin Sonder-PLZ** — pra
    kode të vërteta me koordinatë të ngjeshur. U maten me OSM: 55127
    është vërtet **4,7 km** nga qendra, jo 1,2. Brenda rrethit bien
    gjithsesi, po koordinatat u ndreqën që kontrollet të mos gënjejnë.
  - Baza: **16.362 firma, 1.616 vendimmarrës, 642 kampagnenfähig.**
  - Kontrolli: 8 gjetje te zonat 53 e 55, **të gjitha të provuara si të
    padëmshme**. Gjashtë janë e njëjta firmë me dy domain. SysTrust:
    email-i te `amcm.de`, dhe ajo faqe e përmend vetë "systrust" — firma
    të lidhura, si COMASSIST/ACS. CebiCon: faqja s'u hap për ne, po
    domain-i ka server web dhe **server poste te Hornetsecurity**, pra
    firma është gjallë. `Listen-Pruefbericht-20261007-1055.xlsx`.
  - Testet: **1.461 kaluan, asnjë nuk ra.**
  - **Apify: 12,77 nga 19 $** — krejt brenda abonimit. Kreditet: 371.
- **07.10.2026 — Zonat 50, 51 dhe 52 (pjesa e parë e asaj dite).**
  - **Zona 50 (Köln), 48 kode → 41 kontakte.** Dy rrathë: qyteti 11 km dhe
    Chorweiler 3,5 km — tri kode bien deri 12 km në veri, dhe një rreth i
    vetëm 14,3 km do të paguante 642 km² hartë në vend të 412. Tri kode
    (50919, 50960, 50962) janë **Sonder-PLZ**: s'kanë zonë në hartë, pra
    nuk e drejtojnë rrethin, po mbeten në listë. Maps 2,75 $, AI 0,68 $.
    669 firma (616 të reja), 73 brenda profilit, 59 me person.
    Dropcontact: 56 të pyetur, **41 email (73%)** plus 3 falas, 4 catch-all.
    Tre persona dolën tashmë në zona më të vogla.
  - **Zona 51 (Köln-Lindja, Leverkusen), 23 kode → 16 kontakte.** Dy
    rrathë: 10 km dhe 5,5 km. Maps 2,73 $ (shih më poshtë), AI 0,43 $.
    441 firma, 40 brenda profilit, 31 me person. Dropcontact: 26 të
    pyetur, **16 email (62%)** plus 4 falas, 2 catch-all; një person u
    kapërcye se domain-i i tij dihej catch-all. Katër dolën në zona më
    të vogla.
  - **Zona 52 (Aachen), 10 kode → 14 kontakte.** Një rreth 8 km.
    Maps 1,63 $, AI 0,45 $. 441 firma (413 të reja), 22 brenda profilit,
    19 me person. Dropcontact: 19 të pyetur, **14 email (74%)**.
  - Baza: **15.639 firma, 1.532 vendimmarrës, 601 kampagnenfähig.**
  - Kontrolli i listave: **zona 50 zero gjetje**; 51 dhe 52 nga një, të
    dyja të provuara si të padëmshme (softservice.de hapet normalisht —
    ishte ndalesë e çastit; sobex.de dhe sobex-network.de japin faqen e
    njëjtë). `Listen-Pruefbericht-20261007-1013.xlsx`.
  - **Apify: 9,62 nga 19 $**, pra brenda abonimit, **pa asnjë dollar
    shtesë**. Cikli i ri (2 tetor – 1 nëntor) filloi nga zero.
- **07.10.2026 — Dy mësime nga zonat 50–52, që vlejnë për çdo zonë tjetër.**
  - **Kufiri i parave për vrapim e shënon zonën si të paplotë.** Zona 51
    ra në kufirin 2,50 $ që i vura; vegla e riemërtoi `apify-run-id.json`
    në `apify-run-id-e-paplote.json` dhe zinxhiri u ndal. U rivrapua e
    plotë me 4 $, dhe **834 vendet e paguara të provës së parë u lidhën
    si `maps_dazu`** që të mos shkonin dëm. Mësimi: mos vër kufi aq të
    ngushtë sa të pritet vrapimi — buxheti i Apify-t paguhet gjithsesi
    me abonim, pra kursimi aty nuk kursen para, veç lë punë përgjysmë.
  - **Një burim falas mund të dështojë në heshtje.** OSM-ja e zonës 51
    ktheu **0 firma** sepse serveri dha gabim 504. Zinxhiri vazhdoi pa
    u ankuar. Riprova e thjeshtë dha **18 firma**, prej tyre 3 brenda
    profilit. Nga tash: kur raporti i burimeve tregon `overpass found 0`,
    kontrollo regjistrin për 504/timeout dhe provoje prapë — është falas.
- **30.09.2026 — Zona 49 (Osnabrück e qytezat) e gatshme: 17 kontakte.**
  **Kjo zonë nuk është te lista e Oliverit** — as origjinali i 23.09 as
  lista e ndrequr nuk kanë asnjë kod 49xxx. U bë me kërkesën e Dafinës.
  - Zona 49 e plotë ka 119 kode nëpër Emsland e Osnabrücker Land,
    kryesisht fshatra. Dafina zgjodhi "Osnabrück + qytezat e mëdha": 22
    kode, pesë rrathë — Osnabrück 8 km, Melle 3, Ibbenbüren 3,
    Cloppenburg 4,7, Lingen 3. Gjithsej 354 km².
  - Jashtë mbeti **49195 (Bad Laer)**: tabela e kodeve e quan
    "Osnabrück", po bie 20,5 km nga qendra — fshat i rrethit, jo i
    qytetit. **Nordhorn-i nuk hyn fare te zona 49** (është 485xx).
  - Maps **1,37 $** (kufi i fortë 3 $ për vrapimin), AI 0,43 $. 412 firma
    (380 të reja), 34 brenda profilit, 28 me person, 0 të lëna jashtë për
    mungesë kodi postar.
  - Dropcontact: 25 të pyetur, **17 email (68%)** plus 2 falas, 0
    catch-all. Kreditet 121 → **96**.
  - Lista: 17 kontakte, 10 me pozitë (2 dolën se ishin tashmë në një zonë
    më të vogël). Kontrolli: **zero gjetje**.
  - Excel-i i përbashkët 40–49: **258 kontakte**
    (`IT-Liste-Emails-Zonat-40-49-20260930-1333.xlsx`).
  - Baza: **14.212 firma, 1.397 vendimmarrës, 531 kampagnenfähig.**
  - **Apify:** kufiri 19 → 33 $ me fjalën e Dafinës, dhe u kthye në 19 $
    sapo mbaroi Maps-i. Cikli mbylli me **30,68 $** = 19 $ abonimi +
    11,68 $ shtesë. Deri më 2 tetor nuk shpenzohet më asgjë.
- **30.09.2026 — Zona 48 (Münster) e gatshme: 23 kontakte, plus dy cepat
  e mbetur.**
  - **Zona 48:** 13 kode, një rreth 8 km. Maps **1,46 $**, AI 0,48 $.
    482 firma (437 të reja), 38 brenda profilit, 33 me person, 0 të lëna
    jashtë për mungesë kodi postar. Dropcontact: 28 të pyetur, **22 email
    (79%)** plus 4 falas, 1 catch-all. Lista: 23 kontakte (3 dolën se
    ishin tashmë në një zonë më të vogël).
  - **Dy cepat** (vendim i Dafinës, 30.09): u bënë si dy mini-zona me
    kodin e vet — `414` (Neuss-Uedesheim) dhe `452` (Essen-Kettwig) —
    që të paguhej vetëm cepi, jo tërë zona prapë. Maps 0,17 $ bashkë
    (Uedesheim 9 vende, Kettwig 46), AI 0,05 $.
    - Uedesheim: 1 firmë brenda profilit, 1 person i pyetur, **1 email**
      → zona 41 shkoi 20 → **21**.
    - Kettwig: 5 firma brenda profilit, po të 4 personat i kishim tashmë
      te regjistri — **zero kredite, zero kontakte të reja**. Zona 45
      mbeti 36.
    - Rezultatet shkojnë vetvetiu te listat e zonave 41 e 45, sepse
      dosjet e Dropcontact-it quhen `zona41-dropcontact-cep-...` dhe
      `zona45-dropcontact-cep-...`.
  - Excel-i i përbashkët 40–49: **241 kontakte**
    (`IT-Liste-Emails-Zonat-40-49-20260930-1151.xlsx`).
  - **Apify:** kufiri 19 → 30 $ me fjalën e Dafinës; gjatë vrapimit doli
    se kishin mbetur vetëm 0,9 $, prandaj ajo e ngriti në 32 $ që vrapimi
    të mos pritej në mes. Pas punës u kthye në **19 $**. Cikli: 29,31 $.
- **30.09.2026 — Zona 47 (Duisburg, Krefeld) e gatshme: 38 kontakte.**
  Lista: `IT-Liste-Emails-Zona47-FERTIG-20260930-0946.xlsx`; Excel-i i
  përbashkët: `IT-Liste-Emails-Zonat-40-49-20260930-0946.xlsx`
  (**217 kontakte**).
  - **Apify:** Dafina tha "ngrije sot në 29 $": kufiri 19 → 29 $, vrapimi,
    pastaj prapë 19 $ (i verifikuar). Maps kushtoi **2,25 $**; shtatori
    mbylli me **27,68 $**. Nisja u prit 2,5 minuta pas ngritjes, prandaj
    kësaj radhe s'pati 403.
  - 39 kode (Duisburg 28, Krefeld 11). **Tre rrathë:** Duisburg 11 km,
    Duisburg-Walsum 4 km, Krefeld 8 km. Rrethi i vogël mbi Walsum u shtua
    sepse 47178 bie 12,1 km nga qendra — një rreth i vetëm 14 km do të
    paguante 816 km² hartë në vend të 631. `maps_dazu`: 56 vende tashmë
    të paguara nga zona 40.
  - Maps solli 428 firma, OSM 9. Gjithsej **433 firma** (409 të reja),
    60 brenda profilit, 53 me person me emër, **0 të lëna jashtë për
    mungesë kodi postar**. AI 0,42 $ + 0,01 $ (OSM).
  - Dropcontact: 49 të pyetur, **38 email (78%)** plus 2 falas nga
    regjistri; 4 adresa catch-all të paguara që nuk dërgohen. Kreditet
    187 → **138**.
  - Lista: 38 kontakte, 27 me pozitë. Dy vetë dolën se ishin tashmë në një
    zonë më të vogël (Janhsen, Bagala).
  - Kontrolli: 5 gjetje, të gjitha të shpjeguara. Tri janë e njëjta firmë
    me `.com` dhe `.de` (pace-IT, BOVIIT, ITDISTA). INCAS: email-i te
    `incas.com`, faqja `it-systemhaus.de` — impressum-i e tregon Roland
    Janke si përfaqësues, pra e njëjta firmë. COMASSIST: Florian Bems
    është drejtues i COMASSIST (HRB Krefeld 12606) po email-in e ka te
    `acs-systemhaus.de`; impressum-i i ACS (HRB Dresden 27843) i ka **të
    njëjtët dy drejtues**, pra firma motër dhe adresa është vërtet e tij.
    Del vetëm një herë te baza. `Listen-Pruefbericht-20260930-0948.xlsx`.
  - Baza: **13.377 firma, 1.322 vendimmarrës, 491 kampagnenfähig.**
  - Testet: 1.518 kaluan, 90 u kapërcyen, asnjë nuk ra.
- **29.09.2026 — Tabela e koordinatave i vinte disa kode te qendra e
  qytetit; dy zona kishin mbetur me nje cep te pakerkuar.**
  `pipeline/daten/plz_koordinaten.csv` ka 10.813 kode, po **725 prej tyre
  (6%) ndajne nje pike me nje kod tjeter** — aty tabela vendos qendren e
  qytetit ne vend te qendres se kodit. Testi i rrathëve e beson ate
  tabele, prandaj nje kod i larget dukej "brenda" edhe kur s'ishte.
  - Doli te zona 47: 47178 (Walsum) rrinte te tabela 1,0 km nga qendra e
    Duisburgut, kurse ne te vertete eshte **12,1 km** larg. Kontrolli u
    be me kufijte e kodeve postare te OSM.
  - U maten te 24 kodet e tilla te zonave tashme te kryera: **22 ishin
    brenda gjithsesi**, dy jo — **41470** (Neuss-Uedesheim) 0,7 km jashte
    dhe **45219** (Essen-Kettwig) 0,4 km jashte. Pra nje cep i vogel i
    ketyre dy kodeve nuk u kerkua fare; firmat atje mund te mungojne te
    listat e zonave 41 dhe 45.
  - U ndreqen gjashte koordinata me vlerat e OSM-se (47138, 47178, 47179,
    47199, 41470, 45219) dhe u zgjeruan dy rrathe: Neuss 5,5 → 7 km,
    Essen 10 → 11,5 km. Kjo e ben konfigurimin te sakte per nje vrapim te
    ardhshem; listat e sotme nuk ndryshojne vetvetiu.
  - **Pyetje e hapur per Dafinen:** a duam nje vrapim te vogel Maps vetem
    per ata dy cepa (rreth 0,3–0,5 $), apo i lem ashtu.
- **29.09.2026 — Lista bashkonte dy rreshta te njejte per te njejtin njeri.**
  Kur nje zone ka dy dosje Dropcontact-i, rreshtat e njejte dilnin dy here:
  filtri i fundit i krahasonte me `==` (`f in beste.values()`), jo me
  identitet, keshtu qe te dy kopjet e njejta e kalonin porten. Do te thoshte
  dy email te njejtit njeri nga e njejta fushate — pikerisht gabimi i ndaluar
  me 17.08.2026. U nxor ne funksionin `ohne_doppelte_personen()` dhe u ndreq;
  e ruan `tests/test_itliste_doppelte_personen.py` (5 teste, te provuara edhe
  me gabimin e vjeter te futur prapa qellimisht).
- **29.09.2026 — U gjykuan firmat e mbetura pa gjykim te zonat 40–45.**
  Dafina tha "po beje". Ishin **66** firma që s'kishin kaluar kurrë nëpër
  rregullin e profilit IT. Të 66-at vijnë nga **Gelbe Seiten**, nga dy
  mbledhje të vjetra (`sammlung-verifikation-2026-08-19` dhe `plr-30-31`),
  pra para se Gelbe Seiten të dilte nga zinxhiri më 04.09 — nuk është
  rrjedhje e re.
  - 11 prej tyre s'kanë fare faqe interneti, prandaj nuk gjykohen dot
    (faqja vendos) dhe mbeten `not_checked`.
  - 55 u gjykuan: **5 brenda profilit, 50 jashtë.** Kosto **0,03 $**
    (59 thirrje KI). Vrapimi: `laeufe/leadquellen/zonat40-45-nachtrag-2026-09-29`.
  - Nga të 5-at: `in-data` mbetet jashtë se kontrolli i automatizimit e
    la të pasigurt, `Computer Service Studio` s'ka njeri me emër. Mbeten
    **3 firma me 4 njerëz** pa email: Ingo Marcel Hoenen (COMPUTATRUM,
    40668 Meerbusch), Florian Müller (44267 Dortmund), Bernd Gierden dhe
    Jens Müller (BITNET EDV, 45279 Essen). Asnjëri nuk është pyetur kurrë
    te Dropcontact-i dhe asnjë domain nuk është catch-all — pra 4 kredite
    nëse pyeten. **Pritet fjala e Dafinës.**
  - Baza pas gjykimit: pa gjykim 66 → **11**, vendimmarrës 1.255 → 1.259,
    kampagnenfähig mbetet 449 (email të rinj s'ka ende).
  - Edhe një herë e njëjta gjë që doli më 04.09: nga 55 firma Gelbe
    Seiten, 5 kalojnë profilin dhe zero sjellin kontakt pa pagesë të re.
- **29.09.2026 — Zona 45 (Essen, Gelsenkirchen) e gatshme: 36 kontakte.**
  Lista: `IT-Liste-Emails-Zona45-FERTIG-20260929-1516.xlsx`; Excel-i i
  përbashkët: `IT-Liste-Emails-Zonat-40-49-20260929-1517.xlsx` (177 kontakte).
  - **Apify:** Dafina tha "po, sot": kufiri 19 → 27 $, vrapimi, pastaj
    prapë 19 $ (i verifikuar). Nisja e parë u refuzua sërish me 403,
    sepse kufiri i ri nuk kishte hyrë ende në fuqi; pas dy minutash e
    gjysmë u nis. Shtatori mbyllet me **25,42 $**, pra 6,42 $ mbi 19 $.
  - 45 kode (Essen 32, Gelsenkirchen 13). Dy rrathë: Essen 10 km,
    Gelsenkirchen 9,5. Një rreth i vetëm do të kërkonte 17 km dhe do të
    paguante 816 km² hartë në vend të 598, pjesën më të madhe jashtë
    zonës. `maps_dazu`: 40 vende tashmë të paguara (30 nga zona 40, 10
    nga zona 44).
  - Maps: 799 vende për **2,40 $**, 564 brenda zonës (71%). OSM 22.
    Gjithsej 599 firma (551 të reja), 72 të pranueshme, 54 me
    vendimmarrës. AI 0,58 $ (1.036 thirrje).
  - Dropcontact: 49 të pyetur, **35 email (71%)** plus 5 falas nga
    regjistri; 6 adresa catch-all të paguara që nuk dërgohen (fleta
    "Bezahlt, nicht versandfähig"). Kreditet 220 → 189 te leximi i
    fundit; batch-i i vogël i raundit 2 numërohet te pyetja e radhës.
  - Lista: 36 kontakte, 19 me pozitë. Katër persona dolën se janë tashmë
    në zona më të vogla (Kovtun, Block, Faktorov, Homann).
  - Kontrolli: 3 gjetje, të gjitha email me një domain të dytë të së
    njëjtës firmë (boesner.eu/.biz, systemhausruhr.de/shr.nrw,
    b-technics.com/.de) — asgjë për të ndrequr.
    `Listen-Pruefbericht-20260929-1519.xlsx`.
  - Baza: 12.968 firma, 1.255 vendimmarrës, **449** kampanjefähig.
  - **Rendi i hapave — rindërtimi i bazës bëhet i fundit.** Më 29.09 e
    rindërtova bazën 15:12, kurse Dropcontact-i i zonës 45 shkroi 15:16.
    Prandaj baza tregoi vetëm 1 email për zonën 45 (dhe 414 kampanjefähig)
    derisa u rindërtua prapë: tash 36 dhe 449. Lista ishte e saktë gjithë
    kohën. `zonen-komplett.sh` mbaron te raporti i burimeve; Dropcontact-i,
    lista dhe `python -m pipeline master-db` bëhen pas tij, me atë radhë.
- **29.09.2026 — Zona 44 (Dortmund, Bochum) e gatshme: 28 kontakte.**
  Zona 43 nuk ekziston: asnjë kod postar gjerman s'fillon me 43 (as
  regjistri, as lista e Oliverit). Lista:
  `IT-Liste-Emails-Zona44-FERTIG-20260929-1430.xlsx`; Excel-i i përbashkët:
  `IT-Liste-Emails-Zonat-40-49-20260929-1431.xlsx` (141 kontakte).
  - **Apify:** Dafina tha "po, sot": kufiri 19 → 24 $, kërkimi, pastaj
    prapë 19 $ (i verifikuar). Nisja e parë u refuzua me 403, pa asnjë
    vrapim e pa pagesë. Me gjasë kufiri i ri s'kishte hyrë ende në fuqi,
    sepse kishte kaluar vetëm një minutë; pas dy minutash u nis.
    Shtatori mbyllet me **23,02 $**, pra 4,02 $ mbi 19 $ (zonat 42 e 44).
  - **Siguria:** gabimi 403 e shkroi çelësin e Apify-t në log, sepse
    `zonen-maps.py` e dërgonte në URL. Tash çelësi shkon në header, dhe
    refuzimi shkruan arsyen e Apify-t. Log-u u mbishkrua. Çelësi u shfaq
    edhe në bisedë — Dafina vendos a ndërrohet. E hapur: e njëjta gjë
    (çelësi në URL) te `pipeline/sources/apify_maps.py` dhe
    `pipeline/sources/gelbe_seiten.py`.
  - 49 kode (katër kode të veçanta brenda qyteteve mbetën). Rrathët:
    Dortmund 11 km, Bochum 8,5. Maps: 865 vende për **2,60 $**, 685 brenda
    zonës (79%); 5 nga 10 fjalë e prekën kufirin 110. OSM 53. Gjithsej 706
    firma (651 të reja), 48 të pranueshme, 45 me vendimmarrës. AI 0,70 $.
  - Dropcontact: 28 email nga 42 (67%) + 2 falas (zonat 33, 35); kreditet
    262 → **231** = 28 email + 3 catch-all. Peter Hansemann drejton dy
    firma (ICN, adcon) me dy adresa — u pyetën të dyja sipas rregullit
    (emrat e firmave s'kanë gjë të përbashkët), te lista mbeti një.
  - Lista: 28 kontakte; Dexter McGinnis (Concat) doli se është te zona
    33. Kontrolli: 3 email me domain tjetër të së njëjtës firmë, asgjë
    tjetër. **13 nga 28 rreshta s'e kanë qytetin** (Maps-i s'e dha).
  - Baza: 12.417 firma, 1.199 vendimmarrës, 387 kampanjefähig.
- **29.09.2026 — Zona 42 (Wuppertal, Solingen, Remscheid) e gatshme: 41
  kontakte.** Lista: `IT-Liste-Emails-Zona42-FERTIG-20260929-1402.xlsx`;
  Excel-i i përbashkët tash: `IT-Liste-Emails-Zonat-40-49-20260929-1403.xlsx`
  (113 kontakte: 52 + 20 + 41).
  - **Buxheti i Apify-t:** kishin mbetur 0,62 $ deri më 01.10. Dafina
    zgjodhi "sot, me kufi më të lartë": kufiri mujor u ngrit përmes API-së
    nga 19 $ në 23 $, dhe pas kërkimit u kthye në 19 $ (i verifikuar).
    Harxhimi i shtatorit: 20,43 $, pra 1,43 $ mbi 19 $. Tetori nis më 02.10
    me 19 $.
  - 37 kode. 42895 u la jashtë: kodi i vetë bankës Volksbank
    Remscheid-Solingen, që regjistri e vendos 78 km larg. Tre rrathë:
    Wuppertal 10 km, Solingen 6, Remscheid 6. `maps_dazu`: vendet e
    zonës 40 (108 në këtë zonë, 14 prej tyre s'i gjeti kërkimi i ri).
  - Maps: 682 vende për **2,05 $**, 576 brenda zonës (84%); vetëm 3 nga
    10 fjalë e prekën kufirin 110. OSM 21 firma. Gjithsej 589 firma (567
    të reja), 72 të pranueshme, 60 me vendimmarrës. AI 0,58 $.
  - Dropcontact: 40 email nga 58 (69%) + 2 falas. Kreditet 311 → **262**
    = 40 email + 9 catch-all (domain-e të reja, tash të mbajtura mend).
  - Lista: 41 kontakte; Björn Stange (Medialine) doli se është te zona
    40. **13 nga 41** janë mbi kode që mungonin te lista origjinale
    (Cronenberg, Ronsdorf, Langerfeld, Solingen-Ohligs/Wald).
  - Kontrolli: 7 email me domain tjetër të së njëjtës firmë, Schorn IT
    u përgjigj me HTTP 500. Asnjë dublikatë.
    `Listen-Pruefbericht-20260929-1402.xlsx`.
  - Për sy: Datenzeit GmbH (Datenschutz — siguria si thelb?), SIDL
    (IT + Solar).
  - Baza: 11.766 firma, 1.151 vendimmarrës, 347 kampanjefähig.
- **29.09.2026 — Një Excel për çdo dhjetëshe zonash, në një fletë.**
  Dafina: "me i bo ne nje list te vetme ... prej 40 deri 49 ne nje excel
  pastaj per 50 deri 59 tjetrin"; pasi pa një fletë për zonë: "boni kejt te
  nje sheet mos i ndaj hiq". `werkzeuge/zonen-sammelliste.py` (logjika te
  `pipeline/zone_lists.py`) merr listën përfundimtare më të re të secilës
  zonë dhe shkruan `IT-Liste-Emails-Zonat-40-49-<koha>.xlsx`: një fletë
  "Versandfertig", zonat njëra pas tjetrës, kolonat saktësisht si te listat
  e zonave, në fund kolona "Zona", "Nr" numëron pa ndërprerje.
  - Vetëm kontaktet që dërgohen. Adresat catch-all ("Bezahlt, nicht
    versandfähig") dhe "Zur Kontrolle" mbeten te listat e zonave, që një
    adresë e padërgueshme të mos rrijë mes atyre që dërgohen; shënimet e
    kontrollit janë gjithsesi te kolona "Hinweis".
  - Ndalet nëse i njëjti person del te dy zona, ose nëse një listë zone ka
    kolona të tjera. Listat e zonave nuk preken.
  - Sot: `IT-Liste-Emails-Zonat-40-49-20260929-1323.xlsx`, 72 kontakte
    (zona 40: 52, zona 41: 20), të gjitha me email të ndryshëm, rreshtat
    saktësisht ata të listave të zonave. 50–59 dhe 60–69 dalin kur të ketë
    lista.
  - Lëshohet prapë pas çdo zone të re (`zonen-sammelliste.py 40`); del
    skedar i ri me vulën e kohës.
  - 5 teste të reja (`tests/test_zone_lists.py`).
- **29.09.2026 — Dropcontact-i paguhet vetëm për atë që përdoret.**
  Dafina: "mos te paguj dropcontact per rreshtat pa email". Doli se
  personi pa email s'kushton gjë (kredita kthehet vetë — e thotë edhe
  dokumentacioni i tyre, "Pay on Success"). Kushtonin dy gjëra: adresat
  **catch-all**, që Dropcontact-i i llogarit si të gjetura e ne s'i
  dërgojmë (8 te zona 40), dhe i njëjti person i pyetur dy herë, sepse
  firma ka dy faqe në hartë (2 te zona 40). Dafina zgjodhi "kursimet pa
  rrezik"; rregulli është te `AGENTS.md`.
  - `pipeline/dropcontact_rounds.py` (i ri): `split_rounds` (një person,
    dy faqe të së njëjtës firmë → raundi 1 një herë, raundi 2 vetëm nëse
    s'u gjet), `paid_unusable` (adresat e paguara që s'dërgohen).
  - Regjistri mban mend domain-et catch-all (nga `paid-not-sendable.json`)
    dhe lexon edhe `request-id-2.json`. Kush pyet regjistrin — zonat,
    `lauf`, `schnelllauf`, `grosslauf` — s'paguan më te ato domain-e.
  - `zona32-dropcontact.py`: lexon së pari falas çdo batch që vrapimi e ka
    paguar, pastaj raundet; `--nur-bezahlte` rindërton pa mundësi pagese;
    `--nur-zeigen` tregon kush është paguar tashmë.
  - Lista përfundimtare ka fletën e tretë "Bezahlt, nicht versandfähig".
  - Prova: zonat 40 e 41 u rindërtuan me `--nur-bezahlte`, dhe kreditet
    mbetën 311 para dhe pas. Fleta "Versandfertig" doli e njëjtë rresht
    për rresht (52 dhe 20). Te zona 40 fleta e re ka 7 adresa catch-all
    (e teta është Markus Janhsen, që ka email të kontrolluar nga faqja
    tjetër). Listat e reja: `IT-Liste-Emails-Zona40-FERTIG-20260929-1308.xlsx`
    dhe `IT-Liste-Emails-Zona41-FERTIG-20260929-1308.xlsx`.
  - Kreditet sot: **311** (lexuar falas nga Dropcontact-i). Leximi falas
    i gjendjes: GET i një batch-i të vjetër, ose POST me `{"data": [{}]}`
    sipas dokumentacionit.
  - 1.508 teste jeshile (13 të reja: `tests/test_dropcontact_rounds.py`,
    5 te `test_dropcontact_register.py`, 1 te `test_dropcontact_batch.py`),
    90 të kaluara.
  - E hapur: `pipeline/schnelllauf.py` pyet në raundin 2 personin e dytë
    të së njëjtës firme edhe kur i pari doli catch-all. Brenda një vrapimi
    regjistri s'e di ende — ndreqet kur ai motor përdoret prapë.
- **29.09.2026 — Zona 41 (Mönchengladbach, Neuss, Kaarst, Dormagen) e
  gatshme: 20 kontakte.** Lista:
  `IT-Liste-Emails-Zona41-FERTIG-20260929-1135.xlsx` (24 kolonat e njëjta).
  - **Disa rrathë në një zonë.** Një rreth rreth katër qyteteve do të
    ishte 21 km dhe do të hynte thellë në Düsseldorf, ku kufiri prej 110
    do të harxhohej. Tash `pipeline/zonen.py` pranon `kreise` (një rreth
    për qytet), dhe Apify-t i shkon një `MultiPolygon` (e mbështet aktori,
    README "Custom search area"). Zonat 32–40 i shkojnë Apify-t saktësisht
    si më parë — e ruan testi. Rrathët e zonës 41: MG 8 km, Neuss 5,5,
    Kaarst 4, Dormagen 5.
  - **Ripërdorim i vendeve të paguara.** `maps_dazu` te `pipeline/zonen.py`:
    dataset-i i zonës 40 lexohet edhe për zonën 41 (99 vende në Neuss,
    Kaarst, Dormagen; 89 i gjeti edhe vrapimi i ri, 10 erdhën vetëm prej
    tij). `zona32-lauf.py --dataset=a.json,b.json` lexon disa dataset-e,
    një vend i dyfishtë numërohet një herë.
  - **Kufi parash për vrapim.** `zonen-maps.py --max-usd=` (te zinxhiri:
    `MAX_USD=2.40 ./werkzeuge/zonen-komplett.sh 41`) i kalon Apify-t
    `maxTotalChargeUsd`. Nëse vrapimi e prek kufirin, run-id-ja riemërohet
    `apify-run-id-e-paplote.json`, zinxhiri ndalet, dhe nisja e radhës bën
    kërkim të plotë.
  - Maps: 621 vende për **1,86 $** (kufiri 2,40 nuk u prek), 448 brenda
    zonës (72%; te zona 40 ishin 56%). Vetëm 3 nga 10 fjalë e prekën
    kufirin 110 (te zona 40: 9). Rrethi i Neuss-it prapë preku pak
    Düsseldorf-in (Bilk, Oberkassel — rreth 120 vende jashtë zonës).
  - Gjithsej 460 firma (447 të reja), 38 të pranueshme, 33 me vendimmarrës.
    AI 0,45 $. Dropcontact: 20 nga 33 (61%).
  - 2 nga 20 kontaktet janë vetëm falë listës së ndrequr: netpoint
    (41069) dhe IT-Consult Geromy (41239, Rheydt). Te zona 40 po ashtu 1:
    xpert.IT (40489).
  - Kontrolli: 2 email me domain tjetër të së njëjtës firmë (webmad,
    megabit), te credativ fusha e telefonit ka dy numra bashkë. Asnjë faqe
    e vdekur, asnjë dublikatë. Raporti:
    `Listen-Pruefbericht-20260929-1136.xlsx`.
  - Baza: 11.199 firma, 1.075 vendimmarrës, 328 kampanjefähig.
  - 1.495 teste jeshile (3 të reja te `tests/test_zonen.py`), 90 të
    kaluara (Postgres, Docker-i i fikur).
  - Buxhetet: Apify 0,62 $ deri më 01.10, pastaj 19 $. Dropcontact: 298 në
    dorëzimin e zonës 41 (të 33-at rezervohen në dorëzim, pastaj kthehen
    disa), pra rreth 300 kredite.
  - **Ndreqje e numrit të zonës 40:** Dropcontact-i nuk merr vetëm email-et
    e gjetura. Nga 392 para zonës 40 mbetën 331 para zonës 41, pra zona 40
    kushtoi **61 kredite** për 53 email, jo 53 si u shkrua në mëngjes.
- **29.09.2026 — Zona 40 (Düsseldorf) e gatshme si provë, lista e kodeve
  40–69 e ndrequr.** Jira AP-246 kaloi në "In Progress" (me koment).
  - **Lista e kodeve:** nga 2.096 kode, 1.619 nuk ekzistojnë (ishin radhë
    numrash të mbushura), dhe mungonin 50 kode të vërteta të po atyre
    qyteteve. Lista e ndrequr: `daten/plz-liste-oliver-40-69-corrected.csv`
    (527 kode, 35 qytetet e njëjta), origjinali i paprekur. Vegla:
    `werkzeuge/plz-list-correction.py` (burimet: kufijtë e kodeve te OSM,
    ruajtur te `daten/osm-postal-codes-40-69.json`, plus GeoNames). Shënimi
    për Oliverin: `docs/postal-code-list-40-69-correction.md`. 6 firma që
    i kishim tashmë në bazë rrinë mbi kode që mungonin.
  - **Zona 40:** 51 kode (Düsseldorf, Ratingen, Mettmann, Hilden,
    Langenfeld, Monheim, Meerbusch), qendra (51.23, 6.81), rrezja 19 km. Maps 1.056 vende për **3,17 $**, prej tyre 581 firma në zonë;
    OSM 35 falas. Gjithsej 612 firma (569 të reja). Profili IT + kontrolli
    i automatizimit → 85 të pranueshme, 74 me vendimmarrës me emër. AI
    0,61 $. Dropcontact: 53 nga 73 (73%) + 1 falas nga zona 38.
  - **Lista:** `IT-Liste-Emails-Zona40-FERTIG-20260929-1101.xlsx`, **52
    kontakte**, formati i njëjtë (24 kolona si te 32–39). U hoqën 1 person
    i dyfishtë (Fusion IT) dhe 1 që është te zona 38 (Malte Ehlers,
    ITANIX). Kontrolli `listen-pruefung.py`: vetëm 7 email me domain
    tjetër të së njëjtës firmë (p.sh. iacd.de/iacd.net), asnjë faqe e
    vdekur, asnjë dublikatë. Raporti: `Listen-Pruefbericht-20260929-1103.xlsx`.
  - **Mësimi kryesor:** në Düsseldorf 9 nga 10 fjalë kërkimi e prekën
    kufirin prej 110 — Maps dha vetëm një pjesë të firmave të qytetit.
    44% e vendeve ranë jashtë zonës, kryesisht Neuss (zona 41) dhe
    Solingen (zona 42); janë të paguara te
    `laeufe/leadquellen/apify-ds-5gLzrkb4NPjyijWbG.json` dhe mund të
    ripërdoren kur të vijnë ato zona.
  - Veglat e zonave morën zonën 40 (`pipeline/zonen.py`,
    `zona32-dropcontact.py`, `zona32-itliste-final.py`);
    `listen-pruefung.py` tash i sheh edhe listat 40+ (më parë vetëm
    `Zona3*`, pra do t'i kapërcente heshtazi).
  - Kopje e `stamm.db` para vrapimit:
    `daten/stamm-kopje-2026-09-29-para-zones-40.db`.
  - Baza pas rindërtimit: 10.752 firma, 1.032 vendimmarrës.
  - 1.492 teste jeshile, 90 të kaluara (Postgres, Docker-i i fikur).
  - Buxhetet pas zonës 40: Apify rreth 2,48 $ deri më 01.10 (pastaj 19 $
    në muaj). Dropcontact dha 319 kredite në dorëzim (73 të rezervuara);
    zona 40 kushtoi në fund 61 kredite (shih zonën 41). Që nga 03.09 (391)
    s'ka pasur rinovim: para batch-it ishin 392, pra të 500-at mujore nuk
    kanë ardhur ende këtë muaj.
- **23.09.2026 — AP-210 (kontrolli i bazës) dhe AP-223 (fushat e
  DataWarehouse-it) të mbyllura.** Asnjë ndryshim strukture, vetëm lexim.
  - Kontrolli i plotë: `docs/kontroll-baza-vendimmarresit-2026-09-23.md`
    (fushat e vendimmarrësit, email/telefon/celular, prejardhja, disa
    persona për firmë, ndërfaqja dhe eksporti). Numrat nga baza e 07.09:
    10.183 firma, 933 persona.
  - Tri gjërat që duhen ditur para ndryshimit të strukturës: **154 email
    të paguara nuk janë në bazë** (zonat 35–39 e disa të tjera); lista e
    vendimmarrësve zëvendësohet nga vrapimi i ri, pra një email a telefon
    i vjetër mund të humbasë; telefoni i firmës dhe i personit nuk janë
    të ndarë në përmbajtje (43 persona mbajnë centralën). Celulari nuk ka
    burim — pret AP-213.
  - AP-223: të gjitha fushat mbushen vetë. Sot: Bundesland 92%,
    Mitarbeiterzahl 49%, Kurzbeschreibung 33%, CEO/Inhaber 1.044,
    Entscheider-Bereich 81%. Mbetet vetëm gjysma e fushës "për cilin
    produkt", që kërkon listë produktesh — kemi një ofertë.
  - 1.572 teste jeshile (vrapim i plotë 23.09, me Postgres-in e ndezur).
- **23.09.2026 — 154 email-et që mungonin hynë në bazë.** Ndërtimi i
  `master.db` i lexon tash vetë rezultatet e Dropcontact-it të zonave
  (`_zonen_dropcontact_leads`), pra nuk varet më nga vegla me dorë
  `werkzeuge/zona32-emails-in-db.py` (ajo u përdor vetëm për zonat 32–34,
  dhe pikërisht prandaj mungonin adresat e zonave 35–39).
  - Pas rindërtimit: email personale **331 → 485 (+154)**, telefona të
    personit 699 → 737 (+38), LinkedIn 2 → 146 (+144) — të gjitha të
    paguara qëmoti te i njëjti rresht i Dropcontact-it.
  - Asgjë nuk u mbishkrua: 0 email të humbur, 0 të ndryshuar, 0 persona
    të shtuar a të hequr. Ajo që vjen me adresën mbush vetëm fusha bosh.
  - Kampanjefähig: 291 → 443. Të 42 firmat që kanë adresë po mbeten
    jashtë i ndalin rregullat e automatizimit, siç duhet.
  - 3 teste të reja (`tests/test_master_db_zone_emails.py`), 1.575 teste
    jeshile gjithsej. Jira: shënuar te AP-221 si hap i kryer.
- **23.09.2026 — AP-221, hapi i dytë: personat nuk mbishkruhen më.** Lista
  e vendimmarrësve e një vrapimi të ri nuk e zëvendëson të tërën e vjetrën;
  të dyja bashkohen (i njëjti emër = i njëjti person, mbushen vetëm fushat
  bosh). E njëjta vlen për lead-et e një vrapimi.
  - Pas rindërtimit: 935 persona (ishin 933) dhe 487 email (ishin 485) —
    dy njerëz me adresë të paguar që rregulli i vjetër i hidhte. Asnjë
    person dhe asnjë email i humbur.
  - 3 teste të reja (`tests/test_master_db_keeps_people.py`), 1.578 teste
    jeshile.
- **23.09.2026 — AP-221 e mbyllur: profili IT vendos edhe te baza.**
  `master.db` ka tash kolonën `it_profil` (yes/no/not_checked) me arsyen,
  dhe kampanjefähig është vetëm kush ka "yes" (vendim i Dafinës, opsioni
  A). Shih AGENTS.md.
  - **Kampanjefähig: 443 → 275.** Dolën jashtë 2.063 firma me gjykim
    "jo" dhe 2.780 pa gjykim (më parë dilnin si gati 110 me "jo" dhe 56
    pa gjykim). Profili te baza: 1.046 "po", 4.344 "jo", 4.793 pa gjykim.
  - Gjykimi i fundit fiton: 64 firma kishin gjykime të kundërta nëpër
    vrapime (rregulli i vjetër kundrejt atij të 31.08) — 50 dalin "jo",
    14 "po".
  - Personat dhe email-et nuk u prekën: 935 persona, 487 email.
  - Eksporti Excel ka kolonën e re "IT-Profil". Pamja e Oliverit me 46
    kolona mbeti e paprekur; Postgres-i nuk e ka ende këtë fushë (vjen
    me sync-un e Fazës 5).
  - 4 teste të reja (`tests/test_master_db_it_profile.py`), 1.582 teste
    jeshile.
  - Mbetet e hapur vetëm gjykimi i 4.793 firmave pa gjykim — bëhet kur
    një mbledhje përdoret vërtet, sepse kushton kohë dhe AI.
- **10.09.2026 — Jira AP-216 (waterfall-i i pasurimit) e mbyllur.** Plani dhe provat:
  `docs/plan-ap216-waterfall-2026-09-10.md`. Asnjë commit, 0 kredite të
  harxhuara gjatë punës.
  - **Regjistri i Dropcontact-it** (`pipeline/dropcontact_register.py`): çdo
    përgjigje që e kemi — zonat, vrapimi i madh (`zwischenstand.json`),
    fushatat (`leads.json`). Ripërdorim deri në 90 ditë, pa ripyetje të
    atyre pa rezultat; rregulli te AGENTS.md. E pyesin të katër rrugët:
    vegla e zonave, `lauf`, `schnelllauf`, `grosslauf`. Riluajtja e historisë:
    do të kishte kursyer 31 pagesa.
  - Vegla e zonave: `--nur-zeigen` (tregon kë do ta ripërdorte/pyeste, pa
    dorëzuar asgjë) dhe porta e zonës (pa kod postar nga lista → nuk
    paguhet). Kujdes: rreth 176 persona "për t'u pyetur" janë të pyetur
    para 03.09 pa listë emrash — pyetja pa rezultat nuk kushton kredit.
  - **Kreditet për kërkesë:** `dropcontact-guthaben-verlauf.jsonl` (në dosjen
    e projektit, vetëm shtim) me `request_id`; `guthaben.verbrauch()`. Të 18
    vrapimet e vjetra të zonave dalin "not recorded".
  - **Raporti i pasurimit** te `werkzeuge/zone-source-report.py`: 32–39 →
    5.121 firma, 678 të pranueshme, 502 me emër, 913 pyetje, 404 email të
    paguara (382 persona unikë + 22 të dyfishta), AI $5.02.
  - `docs/waterfall-uebersicht.md` u përditësua (pa Gelbe Seiten, MailCom,
    regjistri, kostot). Rendi përfundimtar i burimeve mbetet te AP-213
    (Blocked).
  - 1.482 teste jeshile, 90 të kaluara (Postgres, Docker-i i fikur).
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

- **29.09.2026 — Zonat 40–69 (Dafina).** (1) Lista e kodeve ndreqet: mbahen
  vetëm kodet që ekzistojnë, shtohen ato të vërteta që mungonin, origjinali
  mbetet i paprekur, Oliverit i shkon shënimi se çka ndryshoi. Rregulli
  është te `AGENTS.md`. (2) Së pari vetëm zona 40 si provë, me të njëjtën
  rrugë si 32–39 (kufiri 110 për fjalë); për 19 zonat e tjera vendoset me
  numrat e saj. (3) Pas provës: "vazhdo me tjera kode me radhë" — zonat
  vazhdojnë me radhë (41, 42, 44 ...), njësoj si zona 40, brenda
  buxhetit mujor.
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

### Zonat e reja 40–69 (Jira AP-246, "In Progress" që nga 29.09.2026)

Zonat 40, 41, 42, 44, 45, 47, 48 dhe 49 janë gati (shih "Gjendja tash").
**Zonat 43 dhe 46 nuk ekzistojnë te lista e Oliverit** — ajo kërcen
45 → 47; mos shto ndonjë pa e pyetur atë. **Zona 49 as ajo nuk është te
lista**, po u bë me kërkesën e Dafinës më 30.09, vetëm pesë qytetet.
Dafina tha më 29.09: "vazhdo me tjera kode me radhë" — pra zonat me
radhë, njësoj si 40. **TË 20 ZONAT E POROSITURA JANË KRYER më 07.10.2026.**
Nuk mbetet asnjë zonë nga lista e Oliverit.

Rezultati: **753 kontakte në katër dosje**, një për çdo dhjetëshe (shih
"Gjendja tash", 07.10). Dafina kërkoi që të mbahet vetëm një dosje për
dhjetëshe; listat zonë-për-zonë fshihen pas çdo rindërtimi.

**Çka mund të bëhet më tej, nëse kërkohet:**
- **Zonat jashtë porosisë.** Lista e Oliverit ka 20 zona; mungojnë 43,
  46, 49, 54, 56, 57, 58, 59, 61, 62. Zona 49 u bë me kërkesë të
  Dafinës më 30.09. Të tjerat do të ishin: 54 Trier, 56 Koblenz e
  Neuwied, 57 Siegen e Olpe, 58 Hagen e Iserlohn, 59 Hamm e Arnsberg —
  gjithsej 507 kode, rajone me shumë fshatra. **Nuk nisen pa fjalën e
  Dafinës dhe pa e ditur Oliveri.**
- **E metë e mbetur:** `mit_wiederholung()` te `werkzeuge/zonen-maps.py`
  nuk e riprovon një 502 të Apify-t, edhe pse quhet "me riprovë". Më
  07.10 e rrëzoi zinxhirin te zona 63. Duhet ndrequr me test.

**Buxheti (gjendja më 07.10.2026, mbrëmje).** Apify mbylli ciklin me
**25,84 nga kufiri 28 $**; kufiri u kthye në **19 $**. Cikli i ri nis më
2 nëntor. Dropcontact ka rreth **225 kredite**.

Kur ngrihet kufiri i Apify-t, pritet 2–3 minuta para nisjes (29.09, dy
herë: nisja një minutë pas ngritjes u refuzua me 403).

**Si paguhet Apify (kontrolluar te llogaria më 30.09.2026).** Plani është
**STARTER: 19 $ në muaj**, dhe brenda tij hyjnë 19 $ përdorim. Është
abonim — paguhet çdo cikël edhe po të mos përdoret. Çdo dollar **mbi**
19 $ faturohet **shtesë**. Pra kur ngremë kufirin, nuk po zhbllokojmë
kredite të paguara: po pranojmë para shtesë.

**Cikli nuk është muaji i kalendarit.** Te kjo llogari shkon **2 shtator
→ 1 tetor 23:59**, pra numëruesi fillon nga zero më **2 tetor**, jo më 1.
(Më herët këtu shkruhej "1 tetor" — gabim i imi, i ndrequr më 30.09.)
**Vendim i Dafinës (29.09.2026): kufiri i Apify-t ngrihet vetëm për një
vrapim, me fjalën e saj, dhe kthehet menjëherë në 19 $** — jo një tavan
i përhershëm më i lartë. Pra pyetje çdo herë, para çdo zone.
Kodet vijnë nga `daten/plz-liste-oliver-40-69-corrected.csv`;
origjinali `daten/plz-liste-oliver-40-69.csv` nuk përdoret më për zonat.
Pas çdo zone: `zonen-sammelliste.py 40` (ose 50, 60) për Excel-in e
përbashkët.

Si shtohet një zonë (si te zonat 40 e 41): skedari i kodeve
`laeufe/leadquellen/plz-liste-oliver-zona<NR>.txt` nga lista e ndrequr,
rreshti te `pipeline/zonen.py` (një rreth, ose `kreise` me një rreth për
qytet kur qytetet janë larg njëri-tjetrit; rrezja e mbulon kodin më të
largët; `tests/test_zonen.py` e kontrollon; `maps_dazu` për vendet që një
vrapim fqinj i ka paguar tashmë brenda zonës), rreshtat te
`zona32-dropcontact.py` dhe `zona32-itliste-final.py` (edhe emri i
burimit te `QUELLE_FIRMA`), pastaj `./werkzeuge/zonen-komplett.sh <NR>`
(me `MAX_USD=` kur buxheti është i ngushtë), `zona32-dropcontact.py
--zone=<NR> --nur-zeigen`, pa `--nur-zeigen`, `zona32-itliste-final.py
--zone=<NR>`, `listen-pruefung.py`, dhe në fund `zonen-sammelliste.py
<40|50|60>` për Excel-in e përbashkët të dhjetëshes.

Kosto e matur për zonë qyteti: Apify 1,90–3,20 $, AI rreth 0,50 $,
Dropcontact 1 kredit për çdo adresë të kthyer (zona 40: 61 për 53 email
+ 8 catch-all; zona 41: 20 për 20; zona 42: 49 për 40 + 9 catch-all;
zona 44: 31 për 28 + 3 catch-all). Personi pa email s'kushton gjë.
Buxheti: Apify 19 $ në muaj (rreth 6 zona; nëse ngrihet kufiri, bëhet me
API `PUT /v2/users/me/limits` dhe kthehet pas vrapimit), Dropcontact
**231 kredite** më 29.09 (rreth 5 zona) — 500-at mujore s'kanë ardhur
këtë muaj.

E hapur, për Dafinën: **plotësia në qytetet e mëdha.** Me kufirin 110
për fjalë, Maps-i te Düsseldorf u ndal te 9 nga 10 fjalë (te zona 41,
me rrathë për qytet, vetëm te 3). Kölni, Frankfurti, Dortmundi, Esseni e
Duisburgu janë po aq të dendur ose më shumë. Më plotë do të thotë kufi
më i lartë ose qyteti i ndarë në copa, pra më shumë para.

Shënime për zonat që vijnë:
- Zonat 45 dhe 47: dataset-i i zonës 40 (`apify-ds-5gLzrkb4NPjyijWbG.json`)
  ka tashmë 30 vende në kodet e zonës 45 (Essen-Kettwig/Werden) dhe 56 në
  ato të zonës 47 (Duisburg-Süd) — t'i jepen si `maps_dazu`.
- Rrathët s'duhet të hyjnë në qytetin e dendur fqinj: rrethi i Neuss-it
  (5,5 km) preku Düsseldorf-Bilk/Oberkassel dhe solli rreth 120 vende
  jashtë zonës. Te qytetet ngjitur (Dortmund–Bochum, Essen–Gelsenkirchen,
  Duisburg–Krefeld) qendra zhvendoset larg fqinjit ose rrezja ngushtohet.
- Frankfurt-West (65929–65936) fillon me 65 dhe Mainz-Kostheim (55246,
  Wiesbaden) me 55: kur të vijnë zonat 55, 60 e 65 vendoset ku hyjnë.
  `tests/test_zonen.py` sot kërkon që kodet e zonës të fillojnë me numrin
  e saj.
- Zona 67: Ludwigshafen dhe Kaiserslautern janë rreth 55 km larg —
  duhen dy rrathë, ndryshe paguhet krejt toka mes tyre.
- Për sy të Dafinës te lista 40: JS Dental GmbH dhe IT Service Dental
  (IT për ordinanca dentare), kzm GmbH Software | Systeme ("Software" në
  emër), Computacenter dhe SPIRIT/21 (firma shumë të mëdha, jo IT e
  vogël). Te lista 41: PC-Tronic Computer Handels GmbH dhe Habel
  Bürotechnik Handels GmbH (tregti), Kommunikationssysteme Scholz dhe
  SCALTEL (telefoni/telekomunikim).

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
