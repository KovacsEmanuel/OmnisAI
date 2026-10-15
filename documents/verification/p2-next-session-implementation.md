# Prompt pentru sesiunea fresh — închidere P2-inert → P4a-minim

**RELUAT EXPLICIT după reboot de operator; mandatul curent este continuarea inertă.** Pauza din 15 octombrie și backupul de mai jos rămân recovery istoric, nu interdicție după mesajul nou de reluare. Orice stop ulterior prevalează și schimbă livrabilul în `HANDOFF_ONLY`; rezultatele asincrone nu îl anulează. CURRENT precede pașii istorici de „prima implementare” sau WIP.

**DOAR ÎN SESIUNEA FRESH cu prompt publicat explicit — sau în conversația restaurată după un mesaj nou explicit de reluare al operatorului.** Închiderea și redeschiderea aplicației nu reactivează singure implementarea.

Acesta este promptul de execuție al planului existent, nu un plan paralel. Arhitectura decide comportamentul; planul §7.1/§8 decide ordinea și porțile. Handofful `p2-c10-session-handoff-20261012.md` trimite aici. Paragrafele și blocurile copy-ready istorice din alte documente nu sunt sarcini curente.

## CURRENT — stare de recuperat, nu de reinvestigat

- Branch activ: **`checkpoint/p2-batch2-pause-20261015`**. WIP-ul istoric `17866dd` este continuat în `b16eda5`, remediat în `1ab0274`/`e4531b8`; citește HEAD real. **Produsul batch2 SOURCE aprobat pe `ef6dae7` este neschimbat.** Callerul installed și distribuția au reviewuri complementare scoped; cele3findings QA și rezidualul selectorului sunt închise SOURCE, cu FAIL-uri păstrate în [registru](p2-bound-predicates.md). Nu relua implementarea, restaurarea, buildul sau grupurile aprobate neschimbate.
- **Pasul imediat actual este prima QA reală**, nu finalizarea WIP-ului: caller SHA`93c1784138823628f488a562d113107e5fd215a1a05894beac14fba3f26d0a28`, selector activ SHA`5f99ce77c93b13a29a00c9acca90b13034bea1525d42185ca00035d0d7e71f85`, candidat exact aprobat de ambii revieweri și adjudecat de părinte. Imaginea/readerul din §0 sunt păstrate identic și aprobate static. Refolosește selectorul existent: release-first, apoi stop-first, serial, fresh fixture/root/boot, deadline240 și cel mult o tentativă inițială/variantă. Preflightul/collect au trecut; verifică numai identitatea și prerechizitele care s-ar fi schimbat. Qualified sizes/PG/native/canonical încă NOT_RUN; nu transforma această admitere în PASS.
- Qualification `191b901` și H01/H02 installed history `c2fdf7d` rămân acceptate scoped. D01–D03/pre-main, M2/F01, numitorul CONTRACT, PARTIAL/evidence/invalidation și schema0013 nu sunt sarcini de reluat neschimbate.
- **H03 ACCEPTED_SCOPED pe `e037cf1`**, caller SHA256 `05ee180c0b11287c1b275c71fa63da1bdc3eaff8e8e2df59f1233ccbc5570c77`: [adjudecare și cleanup](p2-bound-predicates-evidence/h03-installed-restart-parent-acceptance.json). Pozitiv1PASS40.69s și negativ fără final1PASS32.63s, ambele exit0/family_drained=true. Final/check autentice persistate → restart real Host/native OCI stock → public cached receive/readeri instalați fără reexecuție și consum1; lipsa finalului refuză TASK_INDETERMINATE/NEEDS_RECONCILIATION fără scrieri. API owner SOURCE, **nu recovery al supervisorului stock**. Resursele proprii au fost retrase/verificate, datele și logurile păstrate.
- Packaging `9937bc5` a completat closure-ul jsonschema. IPC `0448cd9` închide canalul confirmat drenat înaintea readerilor offline; retirementul reconectează același owner pentru Stop/status fresh. `e037cf1` verifică boot și PID/starttime, nu unicitatea inode-ului namespace între vieți distincte. Confinarea privată rămâne obligatorie. Cauzele interne istorice release/cold-start rămân UNKNOWN; FAIL-urile și fence-urile vechi nu sunt șterse retrospectiv.
- **Primul rezultat lipsă:** acceptarea batch2 prin consumerul PostgreSQL/native instalat existent — binding integral COMMIT pre-access, overlap real read/PURE, două result/check/inbox și consum unic. Producerul/indexarea/concurența/checkerul SOURCE sunt deja implementate; nu le reface. Continuă WIP-ul installed QA din §0. Apoi DATA/admission → canonical P2-inert → Settings și browser/polish numai UI afectată. B06b/G02/P2-inert/P4a-minim nu sunt închise; P2-live rămâne separat.

## 0. Checkpoint istoric de pauză și contractul probei reale

**După reluare:** WIP-ul și pașii2–3 de pregătire de mai jos au fost executați și reviewuiți în commiturile CURRENT. Artefactele și backupul rămân valabile la scope-ul lor; primul rest este pasul4, QA reală. Nu reseta contorul încercărilor sau reexecuta munca neschimbată din descrierea pauzei.

### Ce este salvat și acceptat

- `a7e4df5`: implementare finită batch2 pe17fișiere, material comun versionat, două identități/Brief/scheme, executor existent și două checks; fără cap mai mare/owner nou. `edc19e5`: submit failure/publicare atomică. `ef6dae7`: oracle comun după cleanup și import singleton. `a8244b1`/`9abcd93` păstrează reviewurile/adjudecarea; `a916509` reține numai lecțiile procedurale.
- [Registrul unic al feliei](p2-bound-predicates.md) și rapoartele originale legate acolo consemnează RED/GREEN și două re-reviewuri **APPROVED_SCOPED SOURCE**. NORM-BATCH2-F01 și SAFETY-BATCH2-F01/F02/F03 sunt închise numai în acel scope. Parent3PASS8.77s, normative3PASS1.78s și8controale async, safety3PASS8.41s inclusiv6native. Nu rerula grupurile neschimbate pentru o nouă sesiune.
- Dimensiuni SOURCE complete: stage32503<=32768, graph47621+preparation14828=62449<=65536, final27775<=32768. Doubles storage/publication/receipt-read sunt declarate. Dimensiunile fixture-ului calificat real rămân de măsurat.
- Cancel/replay scratch separat rămâne **INCONCLUSIVE după două eșecuri de harness**; nu reseta contorul și nu relansa acel harness. Restanța concretă este consumerul real, nu o campanie nouă de faults.

### WIP întrerupt — nu este GREEN sau aprobat

- `17866dd` salvează exact **numai** `api/tests/test_contract_method_pg.py`, SHA`6925c3d394a8f1e7989b969451a9e158fe625e29e6908ce14b1b32386148216d`.244adăugări/50ștergeri: routing `installed_native`, bootstrap QA explicit, reader current-only, identity/fence/cleanup. Parent a verificat SHA și `ast.parse`, **nu teste**. Trei RED-uri așteptate înainte de editare sunt păstrate; GREEN/quality/collect/review după editări **NOT_RUN**.
- Selectorul `documents/verification/p2-bound-predicates-evidence/h03-process-fixed-pg-selection.py` este încă **nemodificat** (SHA`b1c42e1382f82a87de78fbe5a0e83bb9be822fe5010348389aef9252e9032d64`); nu îl rula ca batch2. [Raportul original de pauză](p2-bound-predicates-evidence/batch2-installed-pause.json) enumeră complet ce s-a scris și ce lipsește. [Decizia de legare a consumerului](p2-bound-predicates-evidence/batch2-installed-consumer-seam.json) este perimetrul, nu un PASS.
- Refolosește OCI/reader/family owner existente; installed-native pentru H03 sau batch2, restart numai pentru H03. Host/native bytes instalate cu **entry QA explicit**, nu stock argv nemodificat; imaginea păstrează CMD stock/autoload NONE. Fără Overlay/checkout/PIN/LIBRARIES personale în modul installed. API/owner/prepare CLI SOURCE și document-preparation prerequisite double rămân limite declarate. Nu relaxa vechiul manifest historical current=`2891a3f` pentru noul reader.

### Distribuție păstrată și oprire verificată

- Buildul offline deja pornit a terminat exit0 înaintea predării. Imagine nouă **`omnis-batch2-owned-c6eac5f5a13440ffa6bcb35a6e853ab0:current`**, ID **`sha256:261aa5ec522b407d6a014cc3f05e4e08eef783ce0b79ddca492c7dd592b29e12`**, UID1000:1000/CMD stock;19native+15adapter, wheel API și reader privat copy-mode cu installed==wheel==snapshot. Acestea sunt probele statice ale autorului, **nu review independent al distribuției sau QA runtime**. Nu reconstrui automat un artefact încă identic/utilizabil.
- Rootul artefactelor: `/home/kali/.hermes/cache/scratch/p2-batch2-cdbfa74/installed-c6eac5f5a13440ffa6bcb35a6e853ab0`. Locatoare: `native-artifact.json`, `current-reader.json`, `attestation.json`, `context/Dockerfile`; driverul `../build-installed.py` este păstrat, dar nerevizuit ca artefact nou. Hashurile originale și toate comenzile sunt în raportul de pauză. Aceste fișiere nu acordă singure permisiunea de execuție.
- Parent readback: daemon `94260307-c33f-46ac-af7c-8a5ac1a7ffdc`, base image`151e55e…` și noua imagine exacte; CID de extracție **`4aaaab3306d58850e3dbaf24b0e862851d5e18309cf0ac93864f1d81ee98a6d6`** absent, lista labelului `org.omnis.batch2.owner=c6eac5f5a13440ffa6bcb35a6e853ab0` goală, niciun proces cu argv sub rootul sarcinii. Containerul de extracție nu a fost pornit. **PG/Host/native runtime nu au fost pornite și nu există fixture/fence de reluat.** Nicio resursă străină nu a fost oprită/adoptată. Inversa imaginii, numai după probele dependente: elimină exact tagul nou din raport, fără prune/base cleanup.
- **Backup privat durabil, în afara scratch-ului:** `/home/kali/.local/state/omnis-development/checkpoints/p2-batch2-pause-20261015/p2-batch2-cdbfa74.tar.gz`, SHA256 **`57ca33dfaa8d1fbc0715aa054f08c575423d6556bf44dd677263eb583c853891`**,269241033bytes, mod0600,39841intrări, gzip integrity PASS. Păstrează întregul scratch al sarcinii: rapoarte/loguri/source original/reapply/build context/wheels/reader/WIPdiff. Nu conține o copie a imaginii Docker, care rămâne locală în daemon. Este backup pe același laptop, nu backup off-device sau push.
- La reluare verifică SHA-ul arhivei și existența/identitatea locatoarelor înainte de folosire. Scratch-ul poate fi curățat după24h; restaurează numai materialul propriu lipsă la **aceleași căi originale**, păstrând modes/symlinks, fără a suprascrie lucru nou. Nu muta venv-ul și nu rescrie receipts pentru că s-a schimbat calea. Upstream original din backup are SHA`f18177d037fc8012ad9a7bf7e5b4d05f5e0ca63bad9d28e43905389264282c80`, commit`ee5ee84a345204a3b1d6ef6ba1ab747e602867b9`;15208fișiere PIN fuseseră comparate exact, zeroextra. Dacă exportul PIN a dispărut, refă doar acest export exact, nu un harness.

### Primii pași după mesajul explicit de reluare

1. Citește Git real și CURRENT de aici; confirmă checkpointul și păstrează originalul HTML protejat. Verifică read-only locatoarele/artefactul nou și absența writerilor proprii. Nu porni r1, servicii ori teste din reflex. Aprobarile source rămân numai pe bytes/callers neschimbate.
2. Un singur dezvoltator continuă WIP-ul în exact cele două fișiere admise. Completează selectorul fail-closed cu choices/locatoare/hashuri batch2 distincte și măsurătorile **graph+FULL preparation/stage/final/expanded** prin CLI2 real. Verifică tipurile/constructor entry, current-reader negatives/origin și ambele early-return cleanup/fence. Rulează RED→GREEN/regresiile **focalizate** și quality pe delta, nu canonicalul integral încă.
3. Două reviewuri complementare focalizate pe **delta callerului și distribuție**, nu reauditarea sursei batch2 deja aprobate. Fix/re-review numai constatările concrete. Preflight exact fără efecte (`--help`/collect/static inputs): **`ops/run_test_db_gate.py --check` NU este dry-run, ci creează DB**. `test-contract-method-native-pg` nu este choice CLI `--target`.
4. După adjudecare, QA independentă: `batch2-release-first`, apoi `batch2-stop-first`, serial, maximum o tentativă inițială/variantă prin `run_gate`/`prove_private_fixture` existente, deadline240. Fresh boot/root și un RUN cu2taskuri în fiecare. Binding COMMIT vizibil altei conexiuni înainte read/PURE, overlap autentic,2result/check/inbox și replay/consum unic; negative pe același canal, waiter PG în ambele ordini. Fără retry automat, grants mărite, prewarm ori rezultat fabricat. Cleanup/family/reader/resource settlement înainte de DB clearance; incertitudinea păstrează fence/date.
5. Numai după acceptarea batch2: restul DATA/admission din §4, canonical P2-inert din §5, Settings minim din §6. Fără P2-live înainte de acord separat cont/provider/model/date/buget. Nicio etapă nu începe în mandatul actual de pauză.

### Cele opt criterii P2-inert la pauză

| Criteriu §7.1 | Stare păstrată / rest concret |
|---|---|
| Transport/izolare | B05/H01/H02 acceptate scoped; extensia batch2 instalată încă NOT_RUN. |
| Catalog/publicare | Seed și publicare acceptate scoped; fixture calificată fresh pe compilerul actual la QA, fără recertificare generală. |
| Brief/composer/metodă | Batch2 SOURCE implementat/aprobat; consumerul PG/native final lipsește. |
| Binding/inventar/lineage | Indexare/izolare/overlap SOURCE; COMMIT pre-access/overlap PG/installed și inventarul relevant încă restante. |
| Rezultat/inbox/restart | Qualification/history/H03 acceptate; două checks/inbox batch2 și receive-only instalat încă NOT_RUN. |
| DATA | Proiecție/guard/SDK existente scoped, integrarea admission restantă. |
| Admission | Ledger/veto scoped; reserve COMMIT→SENT durabil→transport inert/Stop/caps/UNKNOWN încă nelivrate integral. |
| Acceptare snapshot final | Source batch2 reviewuit; installed caller WIP nereviewuit, QA și canonical final NOT_RUN. |

## 1. Mandat și ierarhie în sesiunea nouă

În `/home/kali/OmnisAI`, livrează restanțele finite prin callerii existenți până la P2-inert și Settings P4a-minim. Nu promite terminarea fazei din numărul de teste. Nu numi faza2 completă fără poarta live separată.

Respectă ierarhia deja aleasă:

| Rol | Responsabilitate și limită |
|---|---|
| orchestrator | Fixează livrabilul curent, dependențele, fișierele, bugetul și autoritatea; verifică preflightul existent, atribuie un writer, integrează, adjudecă și comite. Nu devine un dezvoltator paralel neanunțat și nu scrie un al doilea produs în scratch. |
| dezvoltator | Deține codul/reproducerul/fixul într-un perimetru explicit; RED→GREEN, regresii și quality. Nu autoaprobă și nu comite în checkoutul comun. |
| reviewer | Citește același snapshot înghețat, verifică întâi conformitatea cu cererea actuală și canonul, apoi corectitudinea/safety. Read-only; findings concrete și verdict scoped, nu încă un audit general. Două reviewuri complementare la auth/epoch/concurrency/Stop/effects/secrets/cross-runtime. |
| QA | Verifică fără efecte prerechizitele reale devreme; după reviewurile cerute execută consumerul real pe artefactul final, pozitiv/refuz relevant, persistență și cleanup exact. Reviewerul poate îndeplini această etapă prin contract QA separat dacă regulile proiectului permit; dezvoltatorul nu își certifică singur livrarea. |

Nu crea patru procese doar pentru etichete. Un autor pe aceleași fișiere; maximum trei workstreamuri simultane implicit, cu worktrees din HEAD local pentru autori concurenți. Folosește contractele existente din `.hermes/skills/omnis-delivery/templates/`, cu livrabilul și phase ceiling explicite la fiecare delegare.

Nu preda după fiecare fix, commit sau raport dacă implementarea este mandatul actual și continuarea este admisă. Oprește la livrabilul cerut, blocker real, autorizație lipsă, buget/context nesigur sau cererea operatorului. După Settings: STOP pentru acord separat cont/provider/model/date/buget și RUN nou P2-live.

### Controlul derapajelor

- Un singur rezultat de produs activ. Fiecare verificare/delegare are **cerință → consumer → risc → decizie**, în contractul existent; nu un raport nou pentru fiecare comandă.
- Minimum SOURCE și reviewurile obligatorii, apoi prima probă reală bounded a consumerului afectat. Nu acumula helpers, matrice de faults ori inventare înaintea comportamentului. Un helper, collect-only, SKIP sau launch-only nu este livrare.
- Înainte de autor/QA, verifică reprezentarea reală și **întregul material**, inclusiv preparation bytes, toate limitele agregate și legătura comună selection/snapshot/preparation. Nu repeta greșeala fixturelor mici ori cu metadata independente.
- Contorul ciclurilor numai-harness se păstrează între sesiuni și nume de probe. După două fără avans pe același criteriu, restrânge frontiera existentă sau raportează BLOCKED/NOT_RUN; nu alt owner/observer/verifier și nu o etichetă nouă pentru același ciclu.
- Nu porni un verifier pentru verifier. Refolosește probele neafectate; affected checks după ultima editare, re-review pe delta/call-sites, canonical complet la frontiera finală. Findings de safety și cleanupul rămân obligatorii.
- Nu reaudita P0/P1/B05 sau cauza istorică UNKNOWN fără defect nou care afectează callerul. Nu mări grant/TTL/deadline, nu prewarm și nu fabrica rezultat/autoritate ca să obții verde.

## 2. Intrare scurtă și autorizații

1. Citește `git status --short --branch`, HEAD, diff/staged și ultimul commit. Identifică proprietarul oricărui WIP; nu reseta/stash-ui/șterge lucru străin. Fără checkout remote/fetch/push implicit.
2. Protejat: `documents/Omnis_Notite_Originale.html`, untracked preexistent — **nu citi, hash-ui, edita, șterge sau stage**. Fără r1, profil personal, conturi, fixture-uri sau servicii străine adoptate.
3. Citește AGENTS, CONTRIBUTING „Execuție orientată spre produs”, CURRENT de aici și rândurile SL09–SL13 din `implementation-status.md`, apoi numai plan §7.1/§8, arhitectură §5/§6.3/§9.4–9.10 și definițiile/usages relevante. Nu reîncărca întreaga istorie.
4. Încarcă delivery/review/status, API/TDD/debug, runtime/Hermes; frontend/accessibility când apare UI afectată. Nu catalogul integral în fiecare copil.
5. Operatorul a aprobat explicit **format versionat și partajare imuabilă strict pentru batch2, fără codec general/framework nou, cap mai mare, obligații eliminate ori istoric rescris**; plan §7.1 consemnează acordul. Nu cere aceeași aprobare din nou. Extinderea substanțială dincolo de această limită cere decizie nouă.
6. Autorizarea inertă nu include provider/model/ținte, credentiale personale, P3, rollout sau push. NO_MODEL nu este tur Brain, rezultat de inferență sau PASS funcțional.

## 3. Prima implementare — batch2 cu reprezentare finită, nu încă o fezabilitate generală

**Contract de referință după checkpoint:** producerul și verticala SOURCE de mai jos sunt deja implementate/reviewuite pe `ef6dae7`. La reluare execută numai restul concret din §0; nu recrea implementarea, rapoartele sau probele neschimbate.

### Dovezi suficiente pentru a începe felia, cu limitele lor

[Fezabilitatea coerentă](p2-bound-predicates-evidence/finite2-coherent-factory-feasibility.json) a executat `NativePreparation.build` și `ManagedAdmission._source` pe aceeași selection/snapshot/preparation-ref/package refs. Compiler/capture/prepare_packages/envelope/validators sunt reale. Storage/publication/material/receipt-read sunt doubles SOURCE declarate: **nu ACK nativ, publicare calificată sau PG**.

Pe aceeași metodă records completă, propunerea măsurată are **stage31432<=32768**, graph46518 + bundle COMPLET14828 = **61346<=65536**. Două assignments și două compoziții semantice valide, task/attempt/Brief și scheme de rezultat distincte; roundtrip exact după rebind cu refs/digests noi oneste. Aceasta admite implementarea, **nu aprobă produsul sau izolarea runtime**. Limitele se măsoară din nou pe producerul implementat și fixture-ul calificat real.

Propunerea SOURCE: un BoundProcedure imuabil comun pentru aceeași mission/procedure/slot values și un record tipizat de material prompt comun; compoziții versionate țin refs specifice fiecărui Brief. `shared-prompt-material`, `batch2-common-material-v1` și `batch2-shared-material-v2` sunt **nume propuse, nu API-uri existente**. Preferă extinderea aditivă minimă a transportului existent dacă respectă contractul; protocolul experimental din probă nu impune un transport nou.

Nu partaja schema cu header task-specific. BoundProcedure comun nu acordă drepturi asupra rezultatului/artifactului fratelui. Păstrează exact toate obligațiile, schema, skill text, file SHA/size, provenance, precondiții, evidence, cleanup și limits. Refs vechi/istoric rămân nemodificate; material nou produce identități noi.

Eșecurile sunt păstrate: [candidatul retras](p2-bound-predicates-evidence/finite2-source-blocked.json), [wire-only insuficient](p2-bound-predicates-evidence/finite2-bounded-design-decision.json), [fezabilitatea inițială cu metadata necorelate](p2-bound-predicates-evidence/finite2-narrow-feasibility-and-authorization-review.json). **Nu aplica diff-ul abandonat.** 308SOURCE PASS pe baza restaurată nu sunt batch2 GREEN. Scratch-ul poate expira: locatoarele sale sunt istorie, nu prerechizite ale runtime-ului; nu reconstrui întregul harness de măsurare ca primă sarcină.

### Fișiere și singletonuri reale de schimbat

Căile API sunt sub `api/src/omnis/`; linii istorice orientative, verifică definițiile/usages înainte de editare.

| Frontieră | Simboluri existente | Schimbarea finită |
|---|---|---|
| Request/producer | `modules/runs/managed_admission.py::validate_request`, `BuildSource`, `_build`, `_verify_compositions`; `modules/tasks/managed_contract.py::build_records`, `validate_manifest` | prepare-method/task_count2 în același RUN, numai v4 executabil. Refolosește loopurile; păstrează singleton cold v2/v3. Graph canonic + preparation COMPLET <=65536, nu contabilizare comprimată substituită. |
| Material compact | `modules/tasks/managed_composition.py::compose`, `compact_refs`, `expanded_payload`, `validate`, `stage_payload`; mirror `integrations/hermes/src/omnis_hermes/prompt_bundle.py` | Material comun tipizat/local/immutable, format explicit versionat; exact closed union derivată, nu pool count7/9 presupus. Fără lookup global/fallback/resolver generic. Producer, mirror, readback/replay și `_verify_graph` consumă aceeași reprezentare. Old compact/inline/cold rămân. |
| Wire și assignment | `integrations/hermes/src/omnis_hermes/managed_admission_contract.py::validate_stage/release/response`; `contract_method.py::assignment` | Ambele assignments/materialul integral validate înainte de primul constructor. Whole stage/final <=32768, fiecare expanded composition sub capul existent. Selecție strictă după index trusted și Brief/composition/header/Ref exacte, nu entry0/goal/FIFO. |
| Sidecar și acces | `upstream/managed-source/agent/contract_execution.py::ContractAdmission`, `ContractState`, `initialize_contract`, `BoundContractTools`, `run_contract` | `batch_index` constructor-owned propagat în TOATE call sites; int exact0..1, fără bool/float/implicit0 pentru batch2. Read/PURE numai pentru scope-ul copilului și predecessorul real; originalul shared admis, outputul fratelui refuzat. |
| Lifecycle/concurență | `upstream/managed-source/agent/subagent_lifecycle.py::stage`, `release`, `_contract_guard`, `_release_contract` | Latch întreg bindingul și RUNNING pentru ambii înainte de acces; păstrează per-state one-use. Folosește `_EXECUTOR`/`_Record.future` existente. Niciun wait/join sub registry lock, inclusiv lockul exterior din release. Guard locked pe root/parent/index/record/session/deadline, handler în afara lockului. Final ordonat/homogen doar după settlement ambii. |
| Persistență/checker | `supervisor/native_tasks.py::NativeTaskOwner`; `modules/runs/managed_admission.py::commit_binding/ingest_result/_check/_result_check/readback`; `modules/tasks/method_checks.py::_binding` | Ownerul/DB loops existente sunt deja whole-batch; păstrează COMMIT integral înainte release. Checkerul selectează exact copilul din binding COMPLET, nu un binding singleton fabricat. Două result/check/inbox, consum unic per rezultat. Verifică task-scoping în `result_qualification.py`/`criterion_checks.py`, nu BoundProcedure ID singur. |

Fără migrare/owner/service/scheduler nou preventiv. Limitele grant4.5s/stage4.5s/execution3s/Host3.2s/control4s rămân. Submit parțial/failure/timeout păstrează indeterminate/UNKNOWN, no retry/no final parțial inventat, cleanup ambii. Future timeout nu dovedește worker drained.

### Prima felie verticală și acceptarea ei

1. Dezvoltatorul scrie RED pe consumerul SOURCE existent, cu aceeași metodă completă și preparation bytes reale; nu numai o funcție extrasă ori un fixture fără metadata. Minimum GREEN: producer → stage API/native → două assignments indexate → read/PURE → final integral → două checks task-scoped. Implementează o verticală, nu o colecție preventivă de helpers.
2. Controale necesare: missing/extra/duplicate/shadow/wrong kind/revision bool/digest/pool/ref și overflow refuzate înainte de constructor; index1 selectează Brief1; swap task/attempt/session/root/Brief/row, sibling artifact/receipt și observer raise/False refuză fără acces neautorizat. Same-bound nu permite schimbul execuțiilor. Păstrează singleton/cold/history, no-rerun și statusurile incomplete/UNKNOWN.
3. SOURCE overlap pe handlerul PURE real delegat, threaduri/intervale observate, nu doar două futures. Lock order verificat la caller; pipeline SOURCE nu este binding COMMIT în PG.
4. Schimbarea composerului cere SHA API/mirror corect; `managed_contract` schimbă identitatea compilerului, iar checkerul are closure de surse. Capturează predecessorul real înainte de editare, păstrează suportul receive-only legitim; nu forța digesturi și nu scoate fișiere din closure. Fixture calificată fresh pe codul final.
5. Dacă sursa managed se schimbă, reseal minimal `upstream/omnis-managed.patch`, `managed-patch-manifest.json`, `integrations/hermes/pin.json`; reapply pe originalul exact și verifică inventarul. Nu modifica inert patch dacă nu este afectat. Build/distribution pe bytes revizuiți, UID access și installed origin, nu împrumut de site-packages din harness.
6. Două reviewuri complementare pe snapshot integrat exact, findings reproduse/remediate și re-review focalizat. Apoi QA pe o variantă batch2 **nouă de implementat** în consumerul existent `api/tests/test_contract_method_pg.py::test_contract_method_real_native_pg_owner_receipts_check_inbox`, nu două RUN-uri ori un runner nou.
7. QA reală: CLI prepare-method2 → stage/binding integral → altă conexiune vede ambii BOUND COMMIT înainte de primul read/tool → pinned AIAgent0/1 și read/PURE overlap autentic → două rezultate/checks/inbox → receive/readback/reconcile/replay după Stop, fără reexecuție/consum dublu. Refuzurile pe același canal și overlap PG Stop/release în ambele ordini, cu waiter observat. Family/resource settlement înainte clearance DB; incertitudinea păstrează fence și datele.

Inventory/root-child și lineage H03–H05: măsoară callable/allowed separat de registered bootstrap; NOT_INITIALIZED/UNKNOWN rămân oneste. Lineage autentic/atomic **sau refuz fără acces**, fără compresie LLM simulată. Completează transport/reverse/EOF/timeout/backpressure/unknown method numai la extensia afectată și obligația canonică încă lipsă; nu campanie B05 nouă. Nu extinde gramatica/alte demo-uri dacă metoda selectată nu le cere.

## 4. DATA → admission — următoarea verticală, același owner

| Pas | Caller existent și rezultat |
|---|---|
| Proiecție/final DTO | `ModelProjections._produce/prepare/read`, `ModelDispatch.prepare/read/_context`, `policy/model_request.py`: decizie DATA și proiecție calificate → bytes finali imuabili după transform, owner/run/refs/config/selection/purpose/caps exacte. Guard integral post-transform/direct-worker; sentinel input/body/result/error/log și bypass negatives la frontiera afectată. |
| Intrare owner | `NativeTaskOwner._model_preflight/_model_configuration/_model_initialization`, `NativeTaskCommand`, `LocalControl._dispatch`: adaugă numai callerul inert necesar prin owner/UDS existente. Preflight/config/init nu sunt send. Descriptorul și authority se derivă backend, nu din booleenii callerului. |
| Reserve | `policy/budgets.py::reserve`, `InstanceService.native_preparation_commit`: rezervă tranzacțională **COMISĂ** înaintea fazei următoare; caps calls/output/deadline și VALIDATION efective. Cost nesuportat refuzat/necunoscut, nu zero fictiv. |
| SENT | `budgets.mark_sent`, owner și `RuntimeClient._exchange/managed`: **SENT durabil, vizibil altei conexiuni înainte de primul byte send**, sub barieră reală cu Stop/epoch. Nu mark_sent necomis + send și nu simplu recheck TOCTOU. |
| Transport/settlement | `budgets.release/settle`, `test_model_admission_pg.py`: transport de protocol inert declarat, request-id/body-digest/caps/deadline reale, fără retries/canned rezultat. Receipt→settle/readback; EOF/timeout/cancel după SENT→UNKNOWN cu rezervă păstrată. RELEASED cere no-send demonstrat; replay nu resend, retry/fallback/aux refuzate ori readmise/contabilizate. |

Carrierul inert este SYNTHETIC_PROTOCOL/NO_MODEL dacă schema native FinalModelRequest cere native-turn. Nu relaxa schema și nu fabrica turn/config/purpose/grant. `prepare_inert_request`/`InertProtocolRequest`/`_model_dispatch_inert` sunt propuneri, nu API-uri existente; `policy/admission.py` nu există.

Tracează lock graph-ul înainte de cod. Propunere de verificat, nu soluție aprobată: reserve COMMIT; conexiuneaA ține Instance→lease→Stop fence, B ia numai managed/budget locks, publică SENT și COMMIT, A ține bariera prin transport finit. B nu reacquirează Instance deținut de A; A nu ține managed/budget cerut de B. Grantul se obține înainte de A și se revalidează în fence: `RuntimeClient.managed` cere runtime_authority/Instance, deci nu se apelează naiv sub A. Refolosește preobtained-grant exchange-ul existent din v4 release. Verifică ambele ordini Stop/send prin overlap PG observat, nu apeluri secvențiale. Nu pretinde atomicitate DB/rețea. Settlement după Stop rămâne receive-only/accounting fără autoritate nouă de send.

## 5. Închiderea P2-inert — exact cele opt rânduri §7.1

Reconcilează cerință → cod → consumer → probă/review și fiecare finding pentru: (1) transport/izolare, (2) catalog/publicare, (3) Brief/composer/metodă, (4) binding/inventar/lineage, (5) rezultat/inbox/restart/lost reply, (6) DATA, (7) admission, (8) acceptare snapshot final. Refolosește acceptările neafectate de la CURRENT. Un rest inert obligatoriu neprobat blochează; nu îl redenumi live pentru a închide faza.

Nu relansa qualification: produsul `8cec478` și proba reală `191b901` sunt scoped; `precondition_state_refs=[]`/REVALIDATION_REQUIRED rămân, fără ELIGIBLE/INELIGIBLE ori freshness fabricate din M2/COMPLETE. CriterionOutcome fără oracle/controls nu devine PASS funcțional. B06j/Jev păstrează alocarea canonică: numește obligația inertă concretă dacă este necesară aici, fără a inventa shadow live/framework preventiv.

După bytes finali și reviewuri, rulează canonicalul real plus opt-in native/projection necesare, cu cleanup/readback și date păstrate. P2-inert acceptat nu este G02-live. Continuă Settings în sesiunea nouă dacă mandatul și bugetul o permit.

## 6. P4a-minim și browser/polish — numai suprafețele afectate

- API: `api.py`/SPA shells, `catalog_publication.py`, `candidate_store.py`, InstanceRecord.instance_id. Service/schemas/routes noi sub `modules/settings/` sunt propuneri; GET runtime/catalog/execution și PUT execution nu există implicit. Owner/namespace/root server-authoritative, nu owner_id arbitrar din browser. Catalog real read-only immutable/bounded, fără compiler/PURE; lipsă root→UNAVAILABLE+reason, nu catalog gol fals.
- Persistență: preferință requested-only pentru RUN NOU, receipt/CAS/replay pe storage/lock existente dacă schema permite; nu hot-swap execution-selection activă și nu relaxa NO_MODEL. Requested/effective/fallback/readiness distincte; REQUIRED nesuportat BLOCKED. Migrare numai din necesitate demonstrată, cu upgrade probes.
- Security: Host/Origin/session/CSRF/body bounds, duplicate JSON detection strict pentru noul PUT, nu carveout1MiB al engagementului. DTO strict, U+0000/extra/secret literals refuzate, command-id/If-Match unice, rollback/timeouts/409/replay. Fără chei/parole/token/vault UI, provider discovery/pricing/refresh/inference.
- UI: `web/src/features/engagement/Settings.tsx`, `web/src/shared/api/client.ts`, contracte generate prin `scripts/export_contracts.py`. Providers requested/Save, Skills read-only și runtime/dependency readiness prin clientul/primitives/tokens existente. Configured nu înseamnă authenticated/reachable/inference_ready; fără cont, stări unknown/unavailable oneste.
- Browser real pe build/API/PG proprii, prin runnerul/journey existente: navigare → Save → receipt → **GET exact** → reload → restart backend pe aceeași DB. GET eșuat după receipt nu afișează succes. Refuz/stale/replay/conflict/fallback și loading/error/empty/unavailable/unknown relevante; keyboard/focus/nume accesibile/Stop/identitatea scopului păstrate. Census run/native/dispatch/usage neschimbat și zero provider IO.
- Inspectează capturi reale desktop și narrow relevante; repară local overflow/ocluziune, spacing/ierarhie/contrast/lizibilitate/feedback și blockers de acces. Polish neblocant finit, nu perfecționare continuă. Testele tehnice nu aprobă estetica.
- Perimetrul rezultă din diff-ul UI și callerii direct afectați ai acestei faze. **Fără audit/redesign general Dashboard/wizard/alte componente**, rebrand/framework/animații decorative. CLI-only nu primește browser artificial. Reticle numai dacă deja instrumentat și util, altfel NOT_INTEGRATED; Chisel BLOCKED_NO_GO.

După Settings și gate-ul final pe produsul afectat: STOP pentru selecție/acord separat cont/provider/model/date/buget și RUN nou P2-live. Nu conecta conturi automat.

## 7. Comenzi și prerechizite reale — numai în execuția fresh admisă

**preflight fără efecte înainte de QA:** verifică argv/choices/opt-in/collect, sursa/interpreterul/libraries/pin/mount/UID access și oracle-ul pozitiv/refuz pe același canal. Colecția nu dovedește prerechizitele care sunt assertate abia în test. Nu prewarm runtime-ul și nu instala implicit.

SOURCE: API Python3.13.15, uv0.12.19; `-I -B`, elimină PYTHONPATH/PYTHONHOME/MYPYPATH/PYTEST_ADDOPTS/PYTEST_PLUGINS, dezactivează autoload și cacheprovider, activează explicit pytest_asyncio.plugin. Exemplu de comandă reală pentru grupul existent, nu instrucțiune de rerulare neafectată:

```sh
env -u PYTHONPATH -u PYTHONHOME -u MYPYPATH -u PYTEST_ADDOPTS -u PYTEST_PLUGINS PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 api/.venv/bin/python -I -B -m pytest -p pytest_asyncio.plugin -p no:cacheprovider -c api/pyproject.toml api/tests/test_contract_method_producer.py api/tests/test_managed_requests.py api/tests/test_managed_contract.py api/tests/test_managed_composition.py api/tests/test_managed_wire_parity.py api/tests/test_composition_native_parity.py api/tests/test_native_task_owner.py api/tests/test_contract_method_checks.py -k 'not test_pg_qualified_goal_prepare_before_reservation' -q --tb=line
```

Selectează mai întâi noul RED/GREEN afectat după collect; adaugă testele native mirror/contract/execution/qualification/criteria efectiv afectate. Lint/format/mypy prin manifestele reale și pe snapshot coerent, nu în timp ce writerul editează/retrage fișiere. Fără any/ignore global/catch gol sau teste slăbite. Unit tests nu sunt PG/native.

PG/native: `ops/run_test_db_gate.py`/prove_private_fixture/run_gate existente, fresh/private UDS/no-network. `test-contract-method-native-pg` și `test-model-projection-pg` NU sunt choices CLI --target. Selectorul H03 [păstrat în Git](p2-bound-predicates-evidence/h03-process-fixed-pg-selection.py) este model de integrare cu ownerul/deadline240, dar e legat de callerul H03 vechi: **nu îl rula ca batch2 și nu inventa --case batch2**. Implementează întâi varianta finită în consumerul existent, adaptează selecția minimă și leagă exact closure-ul după review. `--review-adjudicated` nu este approval prin nume.

Targetul B06m existent: `ops/run_test_db_gate.py --check --target test-model-admission-pg --uv /home/kali/.local/share/omnis-toolchains/bin/uv`; confirmă grammar/entrypoint înainte de lansare. Projection cere `$TMPDIR/installed-origin.json` cu origini/wheels reale. Settings folosește E2E/browserul existente, nu B04 ca fals Settings PASS.

Native PIN `ee5ee84a345204a3b1d6ef6ba1ab747e602867b9`, source archive SHA `f18177d037fc8012ad9a7bf7e5b4d05f5e0ca63bad9d28e43905389264282c80`. Preflight locatoarele reale PIN/LIBRARIES din caller, nu din memorie. Export dispărut→restaurează numai originalul hash-matching și inventarul, fără profil personal/latest. Imaginea H03 istorică `sha256:151e55e57b7ace35bb0053ab74caf4d2a71d8d2c82a0176aa9872c148071329f` **nu conține implementarea batch2 viitoare**. Cod nativ nou cere artefact aditiv revizuit, pins/closure/UID/installed bytes verificate; nu transfera vechea distribuție sau auditul ei la bytes noi.

Jobs lungi: tracked background cu pinned paths, exact-session readback până la settlement. Logs private0600; parsează allowlist status/reason/count/exit, fără raw traceback PG/DSN/runtime.boot/capability/credentiale. Cleanup numai exact daemon/CID/project/network/Host/endpoint/process/reader/family; UNKNOWN sau child/handoff nesettled păstrează fence DB și date/loguri. Exit0/family_drained singure nu justifică DROP anterior settlementului.

Canonical final real:

```sh
PATH=/home/kali/.local/share/omnis-toolchains/bin:/usr/bin:/bin TMPDIR=/home/kali/.hermes/cache/scratch make check UV=/home/kali/.local/share/omnis-toolchains/bin/uv
```

La frontiera finală P2-inert și pe produsul final afectat de Settings; nu după fiecare fix/proză/reminder. Docs: `/usr/bin/python scripts/render_docs.py --check`, `/usr/bin/python -m unittest discover -s tests/documentation -v`, `git diff --check`; regenerează HTML când Markdown normativ se schimbă.

## 8. Acceptare și predare

Review independent exact-snapshot; fiecare finding are dispoziție, reproducer/fix/probă sau BLOCKED/NOT_RUN. O listă nouă goală nu închide un finding vechi. Aprobare SOURCE ≠ distribuție ≠ consumer real ≠ browser ≠ estetică.

Commit local după fiecare schimbare coerentă, inclusiv docs/config/fix, cu motiv/comenzi/exits/limite/revert; stage numai paths intenționate. Verifică `git show --stat --oneline HEAD` și status; fără amend/squash/rebase/reset/clean/stash/push implicit. Pentru starea externă consemnează before/after/inversa; Git nu inversează DB/credentials/servicii.

La final, actualizează în loc CURRENT/rândurile afectate și dă scurt rezultat, dovezi, commituri, cleanup, cele opt criterii adjudecate și matrice globală cod/probe/review/pas următor. Nu încă un lanț de rapoarte. Un rest inert obligatoriu lipsă blochează închiderea; o sesiune oprită rămâne recuperabilă, nu PASS.

## Mesaj de publicat în sesiunea fresh

> Reia după pauză folosind CURRENT și §0 din `/home/kali/OmnisAI/documents/verification/p2-next-session-implementation.md`, din HEAD local verificat pe `checkpoint/p2-batch2-pause-20261015`. Autorizez reluarea continuării inerte: finalizează WIP-ul callerului installed QA din `17866dd`, refolosește sursa batch2 aprobată și distribuția păstrată dacă identitatea ei se confirmă, apoi review focalizat și QA reală. Nu reface qualification/history/H03 sau probele SOURCE neschimbate. După batch2 continuă DATA/admission → canonical P2-inert → Settings și browser/polish numai UI afectată, respectând rolurile, safety și commiturile. Oprește înainte de live pentru acord separat; nu declara faza2 completă din probe inerte.
