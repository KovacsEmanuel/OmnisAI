# R1 — re-review focalizat ae722 / Settings C

**Verdict: APPROVED_SOURCE_SCOPED în charterul R1**, prin compunerea reviewului original cu remedierile F01/F02/F03. Cele trei findings originale sunt **CLOSED_SOURCE**; proba reală și acceptarea produsului rămân **NOT_RUN / neacordate**. Nu este verdict asupra charterului R2, asupra tuturor defectelor posibile ori asupra esteticii.

## Snapshot și compunere

- HEAD verificat: `a2eb7f50440dade4c66e13acd4c59a4d39862a77`.
- Base: `94f48fd7e7f0a418a876c6db69ad48b62971a2bd`.
- Candidate ID recalculat: `ae722e7508ee8b348c93bdeea3cbcef33279acad0224fe7de710ab84b7e18319`; **33/33 hashes identice**, zero mismatch, la început și la finalul verificării SOURCE.
- Manifest `/home/kali/.hermes/cache/scratch/uif5/final33-freeze.json`, SHA256 `1a6b4251233a351bfb54333e6983f83a79eb0d8d9c5a1b890516b35155555d81`. `integration_head=9b6a55b` precedă commitul F03; identitatea finală se leagă de actualul HEAD și de bytes, nu de acel câmp istoric.
- Originalul `/home/kali/.hermes/cache/scratch/settings-r1-57ae4967-lsn50i8c/R1-original.md` este păstrat byte-exact, SHA256 `fcb4cee7f7ffb71c3a25cf23f29e210c7e854f984f258be93faea7bea9f3bfb9`. Matricea și limitele sale rămân compuse, nu înlocuite de un audit gol.
- Față de freeze-ul original: 24 fișiere identice, 8 schimbate și un fișier adăugat. Deltas F01/F02/F03 și callerii afectați sunt scope-ul acestui re-review; grant/Make/frontierele F03 de autoritate și concurență rămân la R2. Originalul R2 a fost verificat nemodificat (`ebc66d7b0311c86ef25f145ef73b0aa4ab6972b941a55f343a6a840bd1ce16ac`); nu îi închid constatările.

## Dispoziții

### R1-F01 — CLOSED_SOURCE

`SettingsAssignments.tsx:14–33,44–61`; `SettingsModelsPage.tsx:92–107,210`; `ProviderKeySettings.test.tsx:131–186`.

Cazul exact-unul eligibil fără selecție prezintă identitatea unică și viitorul „All roles will use … after saving assignments”, fără selectoare. Zero scrieri la boot. Confirmarea explicită trimite `expected_revision=0`, Defaultul exact și roluri null; „All roles use” apare numai după receipt și readback autoritativ. Capurile independente37/89, capul incompatibil8192 și referința stale77 nu sunt șterse/ascunse sau substituite.

Am rulat focalizat cele patru regresii actuale: **4 PASS / 16 filtered, exit0, 1.93s**. Dovada anterioară37 afectate și controalele originale3 GREEN rămân scoped pe componenta byte-identică. Eșecul loggerului original `getAllByRole` la zero selectoare este defect de instrumentare, nu FAIL de produs; originalul nu a fost rescris.

### R1-F02 — CLOSED_SOURCE

`api/tests/test_model_test_v2.py:1684–1709,1733–1751,1785–1807`; `installed_sent_probe.py:175–182`; `provider_model_service.py:176–221`.

Censusul produce/cut primește **exact** `provider_model_registry_revision`, `provider_model_entry`, `provider_model_entry_revision`, `provider_model_command`, tabelele scrise legitim de SaveModels înainte de SaveSelection. Egalitatea rămâne strictă; censusul integral și recover/readback nu sunt relaxate. Am verificat programatic că scoaterea exactelor patru linii restituie funcția pre-fix și că funcția instalată este byte-identică între b8e93e0 și HEAD după F03. Extragerea AST reproduce lipsa veche și verifică alinierea curentă; modulele/PROBE compilează fără execuție: **exit0**. Nu este PostgreSQL PASS.

### R1-F03 — CLOSED_SOURCE ca readiness a consumerului existent

`test_model_test_v2.py:143–160,512–594`; `web/tests/e2e/settings-models.mjs:97–267`; `web/tests/e2e/run.mjs:183–184`; caller neschimbat `test_web_e2e.py:278–383`.

Scenariul pornește fără conexiune numai pentru settings_ui, face new-key Save prin UI și observă receiptul exact înainte de catalog; salvează întâi00/cap64, confirmă separat Defaultul, exercită writerul real Brain00/cap37/rev2 și CAS stale409 fără erase, apoi saved-key reentry fără resave, search/dedup/31 chips/Review→Back și Save & test02 fără modificarea selecției. Modificarea GUI Brain01/cap37/rev3, dezactivarea prin alt writer cu wizard deschis, Continue409/Reload/barieră/Cancel, intentul test nou refuzat și reload/API-process restart/history sunt codificate pe același App/API/control/owner/PG/TLS propriu. Nu există route.fulfill sau prototip substituit.

Oracle-ul SOURCE cere exact4 GET metadata,1 POST,1 SENT, refreshes[0,2,5], starts[4,5] și8 tentative de write inclusiv CAS refuzat. Helperul păstrează census13 tabele/restart egal și cleanupul existent. Sunt pregătite29 capturi (șapte stări la patru lățimi plus CSS200%); nu sunt capturi reale deja obținute. Deadline-urile120/300/600 sunt neschimbate; încadrarea efectivă nu a fost executată. Corectitudinea interleavingului contorilor și autoritatea F03 aparțin suplimentar R2.

## Ipoteza nouă CONNECTION_UNAVAILABLE / recuperare

**Nu confirm blocajul propus cu ID rămas / ReplayNotFound.** În bytes actuali `SettingsModelsPage.tsx:17,119–139`, eroarea CONNECTION_UNAVAILABLE este definitivă: linia128 șterge identitatea reținută și setează bariera stale. Reload poate încărca starea dezactivată; după Cancel și Reconnect explicit, refreshul nou este posibil. Backendul refuză conexiunea înainte de scrierea catalog-request (`provider_catalog_runtime.py:160–187`).

Reproducer independent pe App real/jsdom și HTTP explicit sintetic: clean409 → niciun Catalog recovery/ID în storage → Reload/barieră → Cancel → Reconnect rev3 → refresh nou; controlul negativ lost reply păstrează ID-ul și refuză alt refresh. **2 PASS, exit0,1.97s**. Nu pretind execuție API/PG sau compatibilitate provider.

**R1-N01 — LOW, OPEN/neblocant, copy:** `SettingsModelsPage.tsx:128` și driver `settings-models.mjs:245,250` afișează/așteaptă „Catalog outcome unknown … Recover by reading the same catalog operation” chiar la clean409 definitiv, deși identitatea tocmai este eliminată. Errorul concret „No provider call was admitted” este inclus și Reload/Cancel funcționează; nu este capcană de recuperare ori efect ascuns. Remediul minim propus părintelui: text separat pentru ramura definitivă, cu refuz/Reload, păstrând UNKNOWN/read-same-ID numai pentru răspuns realmente incert; nu relaxa guardul și nu schimba comportamentul pe baza unei presupuneri de runtime. Această observație nu blochează prima QA bounded.

## Execuții și limite

Artefactele sunt exclusiv în `/home/kali/.hermes/cache/scratch/r1-ae722-focused-5juh6ndb/`:
- `binding.json`: HEAD/manifest/candidate și toate33 hashes.
- `f01-focused.log`: `PATH=/home/kali/.local/share/omnis-toolchains/bin:$PATH TMPDIR=<scratch> timeout --signal=TERM --kill-after=5s 90s npm --prefix web test -- src/app/ProviderKeySettings.test.tsx -t 'first single-model|one usable model|one usable entry|stale historical' --reporter=verbose` → exit0.
- `catalog-recovery.test.tsx`, `vitest.config.ts`, `catalog-recovery.log`: același mediu/prefix90s, `npm --prefix web test -- --config <scratch>/vitest.config.ts --reporter=verbose` → exit0. Symlink local spre node_modules existent; fără instalare. Warningul CJS/Vite este neblocant; diagnosticele LSP de rezolvare au precedat symlinkul, iar testele au rulat efectiv.
- `source-census.py`, `source-census.log`: `timeout --signal=TERM --kill-after=5s 45s python -B <scratch>/source-census.py` → exit0; AST/hash/compile, fără import sau execuție de consumer.
- `git diff --check`, index și status final → exit0; zero editări tracked/index, aceleași două nume untracked protejate, necitite.

Nu am schimbat surse/docs/index/commituri/skills, nu am delegat, pornit servicii/PG/browser-consumer sau efectuat provider/network/operator/push/deps. Reticle NOT_INTEGRATED; Chisel BLOCKED_NO_GO. Nu am relansat full196, build/canonical sau backend53/72 neschimbat.

**Următoarea decizie:** părintele compune acest verdict cu R2 și adjudecă N01; după eliminarea oricărui blocker complementar, admite prima QA reală bounded pe aceiași bytes. SOURCE readiness nu este runtime PASS, aprobare vizuală ori închiderea Prompt A.
