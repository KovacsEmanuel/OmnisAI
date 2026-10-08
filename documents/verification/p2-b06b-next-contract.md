# SL09 / B06b — contractul următoarei felii (pregătit, neautorizat)

## Autoritate și intrare

Acesta este contractul următorului consumator din DAG-ul existent, **nu un plan concurent și nu implementare începută**. Autoritate: plan §4.2/SL09, §7/B06a–B06b și §19; arhitectură §5, §6.3 și §9.3–9.5/§9.7–9.10. B06a local STATIC/PURE este adjudecată CLOSED_SCOPED în `f057d4cfea23f0169f0f909f2262fccee73e7e4f`, cu cod/probe/review/QA installed și cleanup separate. G02 global nu este o condiție circulară înaintea consumatorilor proprii.

Baza viitoare se citește din Git real după acea adjudecare. Worktree-uri noi numai din HEAD local verificat; nicio adoptare a worktree-urilor curente/istorice. P0/G00, P1/G01, B04 hydration și B05-inert rămân acceptări distincte; nu se reiau fără defect nou concret. B06a oferă catalog/rezervări/freeze/closure/eval durabile, nu încă publicare sau Task/Attempt/copil.

Suportul pregătirii: [analiză și adjudecarea reviewului inițial](p2-b06b-preparation-analysis.json), cu omisiuni documentare, obligații de implementare și deferări distincte; [promptul copy-ready](p2-b06b-implementation-prompt.md), neexecutat. Analiza este checkpoint înainte de reviewul final, nu dovadă de închidere a implementării.

## Rezultatul observabil al SL09

Publicarea explicită a **exact seed-ului calificat**, cu refs/revizii/digests și calificarea neschimbate, apoi snapshot/Task/Attempt durabile și binding root–copil nativ pentru contractul inert permis. TaskBriefV1/TaskResultV1, ExecutionSelection, PromptBundleRevision, LaunchManifest, MethodPlan/Check, predicate calificate, lineage și inbox/receipts trebuie consumate efectiv; nu DTO-uri fără consumator, goal text ca identitate sau copil simulat ca integrare nativă. Publicarea cere confirmarea explicită a operatorului după review/eval independente, CAS și audit `author_kind`/actor/receipturi; AI/importerul nu primește autoapprove. Promovează materialul/indexul/closure existente, fără re-resolver spre latest. Releaseul se consumă numai în snapshoturi noi; STATIC/PURE nu califică SECURITY sau un assessment.

Publicarea este a B06b și necesită mandat nou. Materialele RELEASE sintetice test-only din B06a nu sunt seed publicat și nu pot autoriza selecția unui assessment. Nici contractul de față, nici închiderea B06a nu acordă această autoritate.

## Frontiera minimă de cod și reutilizare

- Producător Publish: extinde bounded `api/src/omnis/modules/settings/skill_catalog.py`, `candidate_catalog.py`, `candidate_store.py` și materialul immutable existent, numai pentru comanda/receiptul CAS/idempotent/readback necesare SL09. Catalogul nu se mută în tasks. Citește definițiile/usages reale înainte de a stabili fișierele permise sau schema.
- Consumatori: `tasks`, `runs` și `integrations/hermes` binding/composer/prompt bundle; introdu `runs/plan_snapshot.py`, `tasks/method_checks.py` și modulele de binding/prompt numai odată cu consumatorul lor, după contractul canonic. Aceste căi viitoare nu sunt pretinse existente. Supervisorul/controlul privat se extind numai la seamul necesar, nu sunt înlocuite.
- Reutilizează resolverul, storage-ul immutable, compiler/evaluator fingerprints, snapshotul calificat, runtime-host nativ și transportul/private ownership B05. Nu un motor generic de workflow, al doilea supervisor, tabel/serviciu per agent, editor Settings sau rescrierea feliilor acceptate.
- Creează migrația numai împreună cu primul consumator persistent; compară schema pins API/CLI/bundle și upgrade-ul real. Nu migra r1/P0/P1 și nu adopta DB-uri vechi ca fixture.
- Păstrează metodele native și prefixul stabil. Composerul citează refs și contextul minim calificat; nu dump de istoric ori instrucțiuni din output neîncrezut.

**Continuitatea calificării:** `candidate_catalog.py:45–70` include nouă surse în `BEHAVIOR_FILES`, inclusiv consumerul/store-ul; editarea lor schimbă fingerprint-ul compiler/evaluator chiar dacă numai adaugă Publish. Nu transferăm receipts vechi peste bytes noi, nu eliminăm fișiere din closure și nu relaxăm guardurile ca să păstrăm un verde. Preferăm seamul de publicare separat în același owner, fără modificarea producerului calificării când nu este necesară. Bootstrapul B06b folosește fixture nouă și freeze/review/eval pe **artefactul final** înainte de Publish, apoi promovează exact acel snapshot/receipts/refs fără recompoziție. A consuma un snapshot vechi sub producer schimbat cere compatibilitate/pinning verificabile ori candidat nou calificat explicit, nu rescrierea snapshotului/receipts istorice; rolloutul datelor de operator rămâne în afara mandatului. Proba in-memory a fingerprintului este numai discovery, nu test PG al acestui consumer viitor.

## Ordinea producătorilor și consumatorilor

Ordinea de adresabilitate este **fără refs inverse** sau digest propriu în preimagine:

1. CandidateSnapshot și review/eval exacte → confirmare operator → Publish atomic → release/profile/recipe fixate în RunSnapshot nou. Purpose este fixat de backend `CONTRACT_PROBE`, nu selector de grant în JSON; proba este exclusă din counts/findings/coverage normale.
2. Snapshot/recipe → ExecutionSelection `NO_MODEL`, `effective=null`, fără defaults personale, și PromptBundleRevision cu composer/tokenizer/limite/pins/provenance → assignment. Selection precede brief/launch, nu citează invers brief-ul.
3. ProcedureRevision + case refs → BoundProcedure adresabil → ProcedureBinding + MethodPlan → TaskBriefV1. CriterionBinding leagă exact criteriile alocate; zero bindings la suport trebuie justificat și nu poate produce CriterionOutcome.
4. Task READY/brief + autoritatea părintelui → rezervări TaskAttempt și LaunchManifest durabile pentru batch → binding root/copil trusted commit înainte de primul acces de domeniu/tool. JSON-ul model-facing nu deține mappingul sau tokenurile sale.
5. Emitent autentic → TaskResult persistat → MethodCheck determinist → receipt/event/inbox și calificare/consum conform §6.3. Result/check nu se hash-uiesc circular. CriterionResult are exact perechile alocate, iar outcome cere checker/oracle trusted separat; MethodCheck COMPLETE nu acordă CONFIRMED/coverage/PASS funcțional singur.

Inboxul distinge **delivered**, **admitted**, **turn_completed** și **domain_result_consumed**. ACK/notificarea Hermes nu dovedește finalizarea turului sau consumul. Există un owner al continuării: notificarea nativă nu rulează în paralel cu un al doilea wake Omnis. Restartul citește task/result IDs/cursori și reconciliază ownerul turului înainte de redelivery; markerul de consum este tranzacțional și idempotent, nu o promisiune exactly-once pe rețea.

## Istoric, calificare și admitere

Conform arhitectură **§6.3**, sunt trei frontiere distincte: ingesta istorică, calificarea curentă și admiterea lucrului nou:

- M1 exact al assignmentului rămâne istoric sub M1 după M2 aditiv; creșterea reviziei globale nu îl face automat stale. ResultQualification cere compatibilitate materială, nu similitudine de text sau copiere oarbă a verdictului.
- Auth/input/precondiții invalidate păstrează receiptul autentic, cu calificare `REVALIDATION_REQUIRED`/`INELIGIBLE`, nu dovadă curentă validă. Noul lucru verifică autoritatea curentă și bugetul; nu resetează consumul prin restart/reformulare.
- După PAUSING/PAUSED/STOPPING/STOPPED ori epoch revocat, canalul **receive-only** validează mappingul istoric al execuției deja expediate și primește rezultatul/usage idempotent în `HELD_FOR_RECONCILIATION`, **fără wake/model/dispatch** sau citiri/tools noi. Nu reactivează runul. Acest pozitiv este obligatoriu, nu un refuz universal al tuturor rezultatelor după Stop.
- Duplicat identic → același receipt/result și fără event/usage/consum dublu; payload diferit pe cheia acceptată → conflict. Emitent/attempt/header/context străin → refuz, nu atașare la cazul altuia.
- RedeliveryKey, ObligationKey și ExecutionKey au scopuri diferite; M1/M2 aditiv nu schimbă singur materialitatea execuției, iar investigatorul și validatorul nu sunt deduplicate între roluri. Nu implementăm aici motorul complet de replan/coverage al etapelor ulterioare.

## Limita nativă verificată înainte de implementare

Pinul este Hermes `0.21.5`, commit `ee5ee84a345204a3b1d6ef6ba1ab747e602867b9`, Python `3.13.15`; se verifică Git/pin/patch manifest real la reluare, nu runtime-ul personal sau documentația latest ca dovadă de pin. B05 RuntimeHost are numai `launch/status/renew/stop`, impune `HERMES_OMNIS_INERT=1`, iar overlay-ul `tui_gateway/rpc_dispatch.py` admite numai capabilities/ping și refuză session.create/prompt.submit. Public lifecycle `launch()` creează copil și programează `_run_child_lifecycle`; `_ChildRun.await_child` apelează `child.run_conversation`. Aceasta nu dovedește un traseu NO_MODEL end-to-end deja disponibil.

Prima verificare B06b este un discovery finit al seamului real: parent/child/batch identity, callback pre-run, lineage, native skill loading și inventar, apoi pozitiv/negativ pe runtime-ul instalat admis fără provider. Se preferă plugin/middleware; dacă metadata este insuficientă, §5 permite un patch minimal separat, auditat și testat pe **același SHA de bază**, cu overlay/manifest/provenance actualizate. Nu eliminăm inert flagul și nu deschidem administrarea stock ca scurtătură. Nu inventăm `tools/provider/skills per child`: `SubagentLaunchRequest.model/allowed_toolsets` sunt seamuri reale, însă null/lista goală de toolsets moștenesc inventarul, nu deny-all; workdir/timeout/blocked_tools per-launch nu sunt acceptate la pin.

Dacă un scenariu necesită model, se păstrează `NOT_RUN` până la etapele live. Dacă **bindingul core** nu poate fi probat inert prin consumatorul nativ admis, rămâne `BLOCKED`; pot fi livrate separat Publish/contractele deterministe probate, dar B06b nu se declară închisă integral. Un patch/seam de construit nu este un defect nou al B05 și nici o probă deja trecută. Fără model simulat, emitter fals, provider calls sau al doilea scheduler.

## Matrice bounded cerință → owner → probă

Toate rândurile sunt **obligații ale implementării B06b, NOT_IMPLEMENTED/NOT_RUN/NOT_REVIEWED**. Ownerul arată extensia/primul consumator, nu fișiere deja implementate sau un plan nou. Citările sunt la arhitectură; plan §4.2/SL09 și §7 fixează ordinea.

| ID | Cerință / sursă | Owner și consumator | Acceptare pe aceeași cale reală | Gate scoped |
|---|---|---|---|---|
| C01 | Publish exact / §9.8 | settings catalog/store → run snapshot nou | Pozitiv: confirmare, CAS, replay/restart cu bytes/index/refs/closure identice. Negativ: D→D2/stale/alt digest/AI autoapprove/receipt străin. | G-REVISION-core |
| C02 | Purpose/pins/selection / §9.3,§9.8–9.9 | runs + tasks/adaptor → brief | Pozitiv: CONTRACT_PROBE backend-fixed, NO_MODEL și effective=null, CHECK_ONLY explicit. Negativ: draft selectabil ASSESSMENT, defaults personale, model call/rol REVIEWER neactivat. | G-SKILL-core |
| C03 | BoundProcedure/slots/MethodPlan / §9.4,§9.10 | tasks/compiler → assignment/brief | Pozitiv: ownership/kind/revision/digest/cardinalitate și toate cerințele bound. Negativ: ref străin/slot lipsă/STEP_OUTPUT_REF global ori cross-attempt/overflow trunchiat. | G-METHOD-core |
| C04 | Brief/result criteria / §9.5 | tasks DTO + checker trusted → primul rezultat | Pozitiv: header și perechi CriterionBinding/CriterionResult exacte; suport justificat fără criterii. Negativ: header străin/criteriu omis/duplicat și outcome fără oracle/control. | G-METHOD-core |
| C05 | PromptBundle/composer / §9.5 | integrations/hermes → native loader | Pozitiv: invariants+rol+brief+metodă+overlay relevant, două skills fixate, prefix stabil. Negativ: wrong digest/shadowing/full history focused/mandatory overflow/prompt override. | H03 |
| C06 | Root binding / §5,§9.7 | supervisor + binding/tasks → primul read/tool | Pozitiv: owner/lease/generation/root context durabil înainte de acces. Negativ: root nelegat/cross-run read/identitate revendicată în JSON. | H04 |
| C07 | Child mapping / §5 | binding + LaunchManifest/Attempt → native pre-run | Pozitiv: batch index/parent/child exacte, goaluri identice distincte, overlap observat. Negativ: wrong child/task/attempt/observer întârziat ori excepție, mapping fără commit. | H04 |
| C08 | Lineage / §5 | runtime trusted + binding → rotație/compresie | Pozitiv: lineage autentic actualizat atomic ori refuz explicit fără acces. Negativ: lineage lipsă/greșit/text/FIFO. Producer real separat de fixture. | H05 |
| C09 | Ingestă rezultat / §6.3,§9.5 | tasks/store → receipt/check/inbox | Pozitiv: emitent autentic, persistare/replay idempotent, usage UNKNOWN păstrat. Negativ: header străin/payload conflict/usage sau event dublu/UNKNOWN tratat zero. | H06/H07 |
| C10 | MethodCheck/predicate / §9.10 | tasks/method_checks → Attempt state | Pozitiv: toate done_when, return_when bounded fără succes automat, probe/bytes/context reale. Negativ: N/A fals/UNKNOWN/cerințe omise ori duplicate/coliziune între bound predicates. | G-METHOD-core |
| C11 | Inbox și patru stări / §6.1 | tasks + owner tur nativ → consum durabil | Pozitiv: restart/readback și crash windows software înainte/după acceptare/finalizare/consum. Negativ: ACK confundat cu turn/consum, lost reply cu retry orb, double wake. | H06/H07 |
| C12 | M1/M2/receive-only / §6.3 | tasks/qualification + fencing → istoric versus admitere | Pozitiv: M1 exact după M2 aditiv și late post-Stop HELD fără wake. Negativ: auth/input invalid calificat proaspăt/foreign result/ref/dublu consum/lucru nou după Stop. | H06/G-REVISION-core |

## Gates core versus breadth ulterioară

| Gate | Core B06b, de demonstrat pe consumatorul propriu | Breadth ulterioară, fără credit anticipat |
|---|---|---|
| H03 | Native loading, package pins/compoziție, missing/wrong digest/shadowing. | Inferență reală copil+skill P2-live; SECURITY FIXTURE_PASS B11/B12. |
| H04 | Root/child mapping pre-tool, batch/identical goals, wrong identity/read și observer failure. | Model dispatch B06m/P2-live și target sink B07; mappingul nu este amânat. |
| H05 | Lineage autentic/atomic ori refuz fail-closed pe seamul real admis. | Compresia efectivă care necesită inferență rămâne NOT_RUN până la P2-live; H04/H05 nerezolvate blochează P3. |
| H06 | Patru stări receipt/inbox, owner unic, duplicate/late/receive-only/Stop și restart; submit=False dacă este admis inert. | Auto-wake/inferență și pre-send Stop B06m/P2-live; target B07, fault breadth B19. |
| H07 | Lost RPC reply/restart și attempts/results reconciliate, fără prompt resend orb. | Lost provider response/accounting B06m/P2-live; recovery integrat B19. |
| H08 | Inventar efectiv Brain/copil minimal, inheritance negatives, deps/caps/read scope și selection NO_MODEL; preferințe REQUIRED/PREFERRED declarative fără fallback tacit, effort invalid/ignorat refuzat (`xhig` rămâne literal invalid, nu este normalizat). | ModelProjection/G-DATA-EARLY B06c; ledger/pre-send G-MODEL B06m; effective provider/model/effort P4a; calls/fallback/auxiliare reale P2-live. |

G-REVISION-core certifică numai Publish exact/CAS/restart/pins; editor/retire/G04b/G-REVISION complet vin în B14b. G-METHOD-core face plan/check/predicate și primul rezultat; seed-ul folosește **CHECK_ONLY**. Rolul REVIEWER și MethodReview/MethodResolution/rework vin cu **B18a.r după G06a**; review_request/method_review nenule sunt refuzate până la activare. Declararea structurii nu implementează consumatorul ulterior. G-MODULE/G02 globale rămân deschise. Native NOT_RUN/BLOCKED nu devine PASS din golden, AST, simulare ori docs.

## Acceptare falsificabilă și gate-ul consumatorului

1. Seed calificat → publicare explicită exactă/readback → snapshot/Task/Attempt/Brief/LaunchManifest → binding nativ → rezultat structurat cu exactele task/attempt/brief refs → cele patru stări durabile și consum → restart/readback fără dublă execuție/consum, numai la frontiera nativă efectiv demonstrată.
2. Două goaluri identice păstrează identități și lineage distincte. Wrong child/task/attempt/ref pin/owner, rezultate duplicate/târzii și compresia contextului sunt probate prin consumatorul nativ admis, cu pozitive pe aceeași cale.
3. Case slots se leagă numai la assignment în BoundProcedure, cu ownership/kind/revision/digest/cardinalitate exacte. STEP_OUTPUT_REF rămâne legat de procedura/pasul/outputul declarat; nicio rezolvare prin text sau nume global. MethodPlan/Check și M1/M2 respectă contractele canonice și feedbackul metodologic separat de verdictul tehnic.
4. Stop/fencing/inbox și retry/UNKNOWN sunt probate pe lucrul efectiv livrat, inclusiv pozitivele istorice M1/M2 și receive-only. H03–H08/G-REVISION-core/G-METHOD-core primesc dovezile scoped din matrice; breadth viitoare și H01 native absentă rămân explicit NOT_RUN/BLOCKED, nu recertificare a întregului B05 ori emitter fals.
5. Două reviewuri complementare pe snapshot exact și QA independentă installed, PostgreSQL disposable propriu UDS/no-network, procese native și cleanup exact/date păstrate. UI numai dacă este efectiv afectată: browser real, persist/readback și capturi inspectate, nu interfață inventată.

Pentru fiecare comportament: RED real → fix minimal → GREEN/regresii; pentru concurrency cerută, overlap observat, nu apeluri secvențiale. Probe neexecutabile sunt BLOCKED/NOT_RUN. Încercările eșuate, incidentele și limitele rămân versionate. Commituri granulare locale, fără push sau history rewrite.

## Non-obiective și continuarea existentă

Fără inferență, cont/provider/model/buget, trafic către ținte, proxy/broker/auth, rollout peste P0/P1, restart/adopție r1 ori schimbări globale. Dacă bindingul nativ nu poate fi probat inert prin consumatorul admis, se raportează acel blocker; nu se simulează un model și nu se cheltuie buget pentru PASS.

După B06b: **B06c** proiecții/G-DATA-EARLY → **B06m** admission și buget înainte de dispatch → **Settings minim/P4a** → **P2-live** numai cu acord separat cont/model/buget. Apoi build proxy admis → broker/HTTP/auth → prima BOLA cu validator, review, raport și retest. Aceste implementări nu sunt autorizate de mandatul B06a și nu sunt începute aici.

Rollbackul codului este granular prin revert; nu anulează publicări/DB/credenciale/servicii. Mandatul viitor trebuie să declare separat before/after, backup/restaurare unde există date de operator și inversul efectelor externe. Contractul pregătit nu acordă drepturi de execuție.
