# Bauplan: Katër kërkesat e Oliverit (19.08.2026)

Urdhri erdhi si specifikim i plotë nga Dafina (mesazhi i 19.08.2026, në
anglisht). Ky plan e përkthen në hapa të kontrollueshëm. Rregulli i
pandryshueshëm: workflow-i ekzistues i fushatave, CRM-i dhe Instantly
nuk prishen — prova është suita e plotë e testeve (1.014 teste të
gjelbra para fillimit).

## Gjendja e gjetur (inspektimi, 19.08.2026)

- **Mbledhja e firmave**: `pipeline/firmen_sammeln.sammeln()` — një
  thirrje për burim (Maps përmes poligonit GeoJSON, Gelbe Seiten me
  `maxPages=1`, Overpass një bbox). PA lak deri-në-cak, pa faqosje të
  vazhduar; numri i kërkuar (hapi 1) nuk arrin kurrë te mbledhja.
  Qyteti është i DETYRUESHËM te mbledhja e re — "krejt Gjermania"
  funksionon vetëm për filtrimin e bazës ekzistuese.
- **Dublikatat**: brenda një mbledhjeje `listen_fusion.fusionieren`
  (çelësi: domain, ndryshe emër+PLZ); ndërmjet mbledhjeve
  `_firmen_bestand` (web/routen/assistent.py) bashkon në lexim.
  Email-dublikatat ndalen te `pipeline/dedupe.py`.
- **Vendndodhja**: fusha `plz` veç, fusha `ort` bosh te të gjitha
  firmat e mbledhura; dje (18.08) u bashkuan për shfaqje si
  "30161 Hannover" (`ort_mit_plz`). Excel ka një kolonë "Ort".
- **Shërbimet**: fjalë të lira + sugjerime nga kategoritë reale të
  bazës (`dienste_vorschlagen`); përputhja është kërkim teksti
  (`passt_zum_dienst`). S'ka familje kategorish.
- **Vendimmarrësit**: shkalla Impressum (KI lexon emrat e drejtuesve,
  Dropcontact ndërton+verifikon email). Roli i personit NUK ruhet
  (titull fiks "Geschäftsführung (laut Impressum)"), pa renditje
  prioriteti, pa "primar", emrat pa email të verifikuar HUMBASIN.
  Firmat pa person mbeten me `ausgang: kein_entscheider` (nuk hidhen).

## Hapat e ndërtimit

1. **PLZ + qyteti ndamas (kërkesa 4)** — `stadt()` në firmen_filter;
   burimi Maps merr `city`, fusioni e mbush `ort` nga adresa; hapi 4
   dy kolona (PLZ | Ort); Excel dy kolona; `ort_mit_plz` mbetet për
   pajtueshmëri ku duhet. Prova: teste të reja + ekzistuese të gjelbra.
2. **Familjet e shërbimeve (kërkesa 3)** — modul i ri
   `pipeline/service_categories.py`: hartë prind → nën-kategori
   (Computer Services → IT-Service, Netzwerk, Softwareentwicklung,
   Cybersecurity, Cloud, …), `expand_for_matching()` (i gjerë, për
   filtrim) dhe `expand_for_search()` (i kufizuar, për scraping me
   pagesë). Lidhet te `filtern()`, te numëruesi live dhe te mbledhja.
   Kujdes: përjashtimet e vjetra të Oliverit (hosting/automation/
   provider te `listen_fusion.AUSSCHLUESSE`) mbeten në fuqi — konflikti
   shënohet në raport, e vendos Oliveri. Prova: teste të reja.
3. **Laku deri-në-cak + krejt Gjermania (kërkesa 2)** —
   `sammeln_bis_ziel()`: cak = numri nga hapi 1; qytet bosh = krejt
   Gjermania si radhë rajonesh postare (të renditura nga dendësia,
   nga tabela e PLZ-ve); pas çdo grupi: valido → fusiono → numëro të
   rejat unike → vazhdo derisa caku arrihet ose burimet shterohen;
   asnjë rezultat i shpikur; log i qartë pse ndalemi. Gelbe Seiten
   merr faqosje sipas cakut; limitet e Maps rriten me cakun.
   Prova: teste me burime false (cak arrihet në 2 grupe; mungesa
   raportohet me arsye).
4. **Vendimmarrësit me prioritet (kërkesa 1)** — moduli i ri
   `pipeline/decision_maker.py` me radhën CEO/Geschäftsführer →
   Inhaber/Owner → Gründer/Founder → Managing Director → drejtues
   tjetër; prompt-i i Impressum-it kthen edhe rolin (dhe LinkedIn-in
   nëse shkruan aty — zakonisht s'ka); personat ruhen te firmen.json
   (`entscheider`: emri, mbiemri, roli, burimi, statusi;
   `entscheider_primaer` i shënuar) EDHE kur s'del email i verifikuar
   (statusi "ohne_mail"); Excel merr kolonën "Rolle" dhe fleta
   "Anruf & Brief" e tregon personin e gjetur pa email. Firmat pa
   person: mbeten, `kein_entscheider` (siç është). Prova: teste.
5. **Suita e plotë** — të gjitha testet, në blloqe nëse duhet.
6. **Verifikimi i vërtetë** — një mbledhje "Deutschland / Computer
   Services / 100 firma" me çelësat realë (Apify: dollarë të vegjël,
   llogaria e firmës); emrat e vendimmarrësve mbi firmat e gjetura
   me Impressum-KI (OpenAI, cent); PA Dropcontact (s'harxhohen
   kredite), PA Instantly, PA asnjë email. Raporti me numrat e
   kërkuar në specifikim.

## Rreziqet / të hapura

- Kostoja e verifikimit: rajonet e para të Gjermanisë me ~10 terma
  kërkimi — brenda buxhetit të llogarisë Apify (mini-lauf); logu e
  tregon shpenzimin për gjykim.
- Konflikti përjashtime ↔ familja e re (hosting/automation): mbetet
  vendim i Oliverit; deri atëherë përjashtimet fitojnë.
- LinkedIn: burimet tona rrallë e kanë; fusha ruhet vetëm kur gjendet
  vërtet — pa shpikje.

## Ecuria

- [x] Hapi 1: PLZ + qyteti ndamas (19.08: burimet mbushin "ort", fusioni
      e lexon nga adresa; hapi 4 dhe Excel me dy kolona; 102 teste)
- [x] Hapi 2: familjet e shërbimeve (pipeline/service_categories.py; lidhur
      te filtern, numëruesi live, mbledhja dhe hapi 3 i formularit)
- [x] Hapi 3: laku deri-në-cak + Gjermania (sammeln_bis_ziel,
      regionen_deutschland; CLI --ziel/--deutschland; formulari e nis me
      numrin e hapit 1; ort bosh = krejt Gjermania)
- [x] Hapi 4: vendimmarrësit me prioritet (pipeline/decision_maker.py;
      Impressum-i lexon rolin+LinkedIn; entscheider/entscheider_primaer
      te firmen.json edhe pa mail; Excel me kolonën Rolle)
- [x] Hapi 5: suita e plotë e gjelbër — 1.052 teste (19.08.2026)
- [x] Hapi 6: verifikimi i vërtetë (19.08.2026 pasdite, llogaria reale
      Apify, PA Dropcontact/Instantly/email): cak 100 → 4.252 të
      lëvruara bruto nga rajoni i parë (PLZ 86) + Gelbe Seiten
      mbarëgjermane + OSM; 3.530 unike të ruajtura (348 dublikata të
      hequra, 374 të përjashtuara nga rregullat e vjetra të Oliverit);
      829 qytete të ndryshme; mostra 100 firma me Impressum-AI:
      67 me vendimmarrës me emër (+rol), 33 pa (mbeten të shënuara),
      0 gabime leximi, 0 LinkedIn (Impressum-et s'i kanë). Mësim i
      çmuar: limiti i Maps ishte PËR TERM → 35× mbi cak; formula u nda
      me numrin e termave (test i ri). Rezultatet:
      laeufe/leadquellen/sammlung-verifikation-2026-08-19/
