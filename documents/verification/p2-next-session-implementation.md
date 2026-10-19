# Sesiune fresh — restul P4a/G04a și P2-live/G02-live

**CURRENT = UI_SIMPLE_CONNECT_DELIVERED / WAITING_OPERATOR_AUTH, fără continuare automată.** Cererea de dimineață a schimbat livrabilul imediat la web simplu; `922dc9f` livrează Provider/Model/Connect, Diagnostic pliat, două re-reviewuri APPROVED_SCOPED și web115unit/6tooling/audit0/exit0. UI8 ultimul readback READY/date păstrate, QA instalată patru viewporturi/tastatură/un click read→save→connect→CHALLENGE și tab oficial deschis. Formularul operatorului fără răspuns; ulterior același ID INDETERMINATE/oauthNONE/challenge absent/cauzăUNKNOWN, fără retry/inferență. UI7 retrasă fizic/logicUNCERTAIN după supervisor exit3. `e0d23d6`/9AST/8regresii se reutilizează, runtime441PASS/1FAIL stock agent=None și canonical complet NOT_RUN rămân. Prima probă Codex/xhigh1apel/300s neconsumată. Promptul de mai jos se activează numai la cererea explicită de continuare live; verifică Git/CURRENT, nu relua arhiva.

## Prompt pentru următoarea implementare

**HANDOFF_ONLY — DOAR ÎN SESIUNEA FRESH**, activat prin cererea explicită a operatorului, nu prin închiderea sarcinii UI.

```text
Lucrează în /home/kali/OmnisAI.
/ponytail:ponytail full

MANDAT
Acest prompt este recuperare, nu continuare automată după simplificarea UI.
Aplică-l numai când operatorul cere explicit reluarea P4a/P2-live.
Continuă secvențial restul fazei 2 conform planului §7–8/§19:
P4a/G04a → P2-live/G02-live. Primul apel reușit nu închide faza 2.
Fără P3, trafic target, provideri/catalog/editor extinse, r1/P0,
profiluri personale, modificări globale, push sau buget nelimitat.
Respectă SOUL, AGENTS.md, CONTRIBUTING.md; nu le modifica pentru a evita gates.
Încarcă Ponytail full/audit/review și skill-urile de proiect relevante.
Audit read-only numai pe traseele afectate și criteriile restante.

STARE DE RELUARE
Verifică Git: branch checkpoint/p2-batch2-pause-20261015;
UI922dc9f și remediul prerequisite e0d23d6 sunt integrate, nu se reimportă.
Citește CURRENT din README, p4a-minim.md, p2-integration-b06cm.md,
implementation-status.md și p4a-oauth-evidence/preauth-ui-recovery.json,
plus plan §7–8/§19. Dovezile curente: simple-connect-installed.json,
simple-connect-visible-through-challenge.json și cele șase originale
simple-connect-author/review/rereview*.json. NORM-F01 închis scoped;
worktree autor p4a-simple-aeqwhv_2/work curat/a64df8a, deja integrat.
clean-ui-installed.json și probele neafectate rămân istorice/scoped.
Singurul untracked cunoscut: documents/Omnis_Notite_Originale.html.
NU citi/copia/hash/modifica acel HTML sau tools/development/ponytail.json.
Păstrează munca străină și FAIL/UNKNOWN/INDETERMINATE. Fără reset/stash/push.

ARTEFACT ACTUAL
/home/kali/.omnis-p2-ui8, origin http://127.0.0.1:8765, generation3/epoch2,
instance cebb549c-2a72-40fe-89fd-877f62b1b4d6,
release SHA256 660cb2df9b0c89c0e1fcc5960cdd59bbfac70a77890e440b9b0aff85cb33949a.
Mediul CLI și ownerii sunt în recovery/intent.json; parsează privat.
Reobservă readiness, contul/datele și browserul înainte de orice efect.
Profilul QA UI3/debug9226 este istoric; nu îl lansa pentru testul actual.
Operatorul deschide Chrome normal și face auth; nu automatiza profilul său,
nu citi/copia cookies/credentiale/sesiuni și nu substitui browserul testing.
Ulterior operatorul a cerut Stop/Start cu loguri și auth în Chrome-ul său normal:
operator-chrome-restart.json păstrează Stop0, primul PORT_CONFLICT/TIME_WAIT,
Start distinct0/READY/generation3/epoch2/date identice/logging existent activ.
Nu porni Chrome testing și nu copia credentialele Hermes personale.
UI6 este STOPPED/generation2/date păstrate. UI5 are resursele fizice absente,
dar rămâne UNCERTAIN/RECOVERY_REQUIRED după supervisor exit3/cauză UNKNOWN.
UI7 la fel: supervisor exit3/OOMfalse în pauză, Stop original exit4/9.554s,
exact4CIDs/proiect/rețele absente și identitățile datelor păstrate;
logic UNCERTAIN/RECOVERY_REQUIRED, nu READY/STOPPED reconciliat.
Nu o adopta/reporni și nu șterge markerul. Dacă defectul reapare pe instanța
actuală, capturează motivul finit prin ownerul existent înainte de cleanup;
nu inventa retrospectiv cauza și nu relansa la orb.

CE NU SE REIA
UI simplă: două re-reviewuri scoped, make check-web final115unit/6tooling/audit0,
QA instalată1440/1280/390/320, tastatură,4assets, Diagnostic pliat,
un singur click real read/save/connect și tab oficial deschis, exit0 până la CHALLENGE.
Nu relansa polishul, read/save sau probele unknown/logout neafectate;
aprobarea estetică rămâne distinctă. Nu adăuga provideri/modele/catalog nou.
P2-inert/G02-inert și SEND PG/native controlat7a2ac5a sunt acceptate scoped
(1PASS/35,72s/exit0/family_drained=true), nu inferență provider live.
Pre-auth Connect/background/reload/Cancel32.411s pe27f86d1 se reutilizează
numai pe logica neschimbată. Niciun candidat vechi nu se reimportă.

PRIMII PAȘI ȘI RESTANȚE
1. Reutilizează e0d23d6 și cele două reviewuri din p4a-minim.md:
   HERMES_NATIVE_SOURCE=/home/kali/.hermes/cache/scratch/of-n9n2qc5w/prepared/runtime-source
   este inputul MANAGEMENT explicit, validat înainte de provisioning și la AST.
   Nu este no-input GREEN. Nu relansa remediul locatorului sau9AST neafectate.
   Adjudecă următorul FAIL real: test_public_turn_denies_before_native_dependencies_and_preserves_stock_control
   din integrations/hermes/tests/test_model_terminal.py trimite function(None,None),
   dar native conversation_loop citește agent.__dict__ înaintea tripwire-ului stock.
   Check-runtime:9AST PASS,441PASS/1FAIL25.64s/exit2; izolat1FAIL0.06s/exit1.
   Test/producer/adaptor relevante sunt neschimbate de e0d23d6. Reproducer→fix minim
   al fixture-ului/callerului legitim dacă se confirmă→regresii/review; fără skip,
   produs auth modificat preventiv sau assertions slăbite. Nu este bug UI demonstrat.
   Dacă alegi installed_browser.mjs mode=session, repară întâi callerul care
   pornește Home și apoi cere identitatea Runtime; nu schimba ruta produsului.
2. Păstrează QA vizibilă: fereastră headed efectiv în față, URL comunicat,
   fără înlocuire cu headless/screenshot-only. La preluarea operatorului,
   oprește automatizarea și reobservă înainte de continuare.
   Testul actual folosește Chrome normal deschis de operator; fără pornire
   Chrome testing, control CDP sau capturi ale profilului personal.
   Pin153 și cele două SIGTRAP ale Chromium145 sunt istoric QA, nu pași actuali.
   Connect0e4e7c98-e19d-4436-ab7f-e9876cb19d20
   a produs CHALLENGE și tab oficial auth.openai.com confirmat efectiv deschis,
   apoi controlul a fost lăsat operatorului. Formularul a rămas fără răspuns;
   readback3682.983s mai târziu: INDETERMINATE/configuredfalse/selectionnull,
   oauthNONE/challengeabsent/auth&reachableNOT_VERIFIED/inferencefalse.
   Cauză UNKNOWN, nu expiry cert din timp; markerii finiți lipsesc.
   Nu retrimite Connect sau refresh automat. Verifică operația exactă/starea
   locală prin ownerii existenți și decide frontiera necesară înainte de efect.
   UI veche7d9d7d7b… este CANCELLED/ABSENT; nici acel ID nu se reia.
   Pentru orice deschidere ulterioară verifică tabul real, nu doar click ACK.
   Operatorul face autentificarea/confirmarea contului Codex numai în web.
   Nu solicita/copia parole, tokenuri sau coduri în chat,
   capturi, loguri ori Git. Save nu este auth; LOCAL_PRESENT se verifică
   prin operația care îl produce și nu înseamnă inference_ready.
3. Buget confirmat/neconsumat: cont Codex ales de operator, gpt-6.1-sol/xhigh,
   date sintetice, maximum1apel/300s pentru prima probă, fără retry/fallback.
   Nu extinde acest acord la alte calls; auth/consimțământ încă nefinalizate.
   Cererea de web simplu nu autorizează pornirea acestei probe în fundal.
   Prima inferență trece exclusiv prin callerul legitim deja existent:
   native_tasks.py/_model_test_prepare și _model_test_send → ModelTest,
   cu producerii reali ai inputurilor, nu un apel SDK auxiliar sau helper fals.
   Verifică legătura și limitele complete înainte de a atribui cod.
   DATA, reserve/SENT durabile, usage/receipt/readback, Stop și no-retry/fallback
   rămân obligatorii. Subscripția se monitorizează fără promisiunea unui plafon
   garantat de output; plafoanele API și celelalte protecții rămân.
4. Continuă criteriile live aplicabile: copil nativ + skill publicat/pin-uit,
   identitate/mapping autentic înainte de acces, requested/effective model/effort,
   inventar Brain/copil și auxiliare/no hidden calls, lineage/compresie sau
   refuz explicit conform canonului, rezultat/inbox/consum/recovery și Stop.
   Reutilizează părțile inerte neafectate; nu transforma un PASS sintetic ori
   primul răspuns în închiderea G04a/G02-live. Fără alte familii/demo/editor.
5. Canonical final real pe snapshotul final, după preflight fără efecte:
   exportă inputul HERMES_NATIVE_SOURCE MANAGEMENT de mai sus;
   make check UV=/home/kali/.local/share/omnis-toolchains/uv-0.12.19
   --check al runnerului PG PROVIZIONEAZĂ; nu este dry-run.
   Respectă argv, opt-in, source/library/toolchain și ownership existente.
   Cleanup prin ownerii originali, exact readback și date păstrate.

MOD DE LUCRU
Un developer în worktree din HEAD local; orchestratorul integrează/acceptă.
Dezvoltare și review: openai-codex/gpt-6.1-sol/xhigh, fără downgrade/fallback.
Node24.21.0/npm11.19.0, Python3.13.15/uv0.12.19 pentru componentele pin-uite.
RED → fix minim → GREEN, review independent pe bytes exacți; două reviewuri
complementare pentru authority/model dispatch/Stop/secrete/cross-runtime.
Nu adăuga owner/contabil/framework/dependency/harness fără nevoie demonstrată.
Nu mări granturi/calls/deadline-uri/limite ca să obții verde; nu reseta contorul
ciclurilor numai harness. După două fără progres restrânge frontiera probei.
Commit local după fiecare schimbare coerentă, stage numai fișierele intenționate,
verifică commit/status și actualizează CURRENT în loc/registrul existent.
Continuă fără handoff după fiecare fix; oprește la faza2 verificată, intervenția
necesară a operatorului, blocker real ori limită de siguranță/buget. Raport scurt
în română, PASS/FAIL/BLOCKED/NOT_RUN distincte, fără promisiune gap-free.
```

## Arhivă — promptul P2-inert anterior, inactiv

Datele de mai jos păstrează checkpointul istoric. P2-inert a fost între timp închis scoped; nu relansa caps/H04/WIP-urile sau ordinea de atunci din această arhivă.

## 1. Starea exactă de recuperare

- Repo `/home/kali/OmnisAI`, branch `checkpoint/p2-batch2-pause-20261015`. Citește Git/status real și păstrează modificările străine; fără reset/stash/checkout implicit. Commiturile documentare ulterioare nu schimbă singure snapshoturile de mai jos.
- **Ultima acceptare de produs:** `4ed765c`; [QA originală](p2-integration-projection-reuse-pg-qa.json), SHA256 `1c71a8eb27e1c1c7eb19d8b3385139704e97bca01402096a9a7b1c639e1f82ca`: **99PASS201.21s/exit0/family_drained=true**,83SOURCE+16PG. Nominal/Stop-first/send-first/duplicate/conflict trecute cu overlap PG real și exact census/replay; duplicate3851ms în4s, marjă149ms într-un singur eșantion, nu benchmark/garanție. Oracle-ul prematur `e87a8de` și validarea intra-apel3→1 cu eligibilitatev4 conservată sunt reviewuite. FAIL-urile și findingurile istorice rămân în [registrul unic](p2-integration-b06cm.md); nu relansa diagnosticul rezolvat sau batch2 pe bytes neafectați.
- **Admission caps/VALIDATION/buget imuabil/deadline-B:** checkpoint comis **`754f203`**. Produs neschimbat; numai `api/tests/test_model_admission.py` și `test_model_admission_pg.py`. [Autor](p2-integration-caps-author.json), [review normativ](p2-integration-caps-review-norm.json), [review safety](p2-integration-caps-review-safety.json): **89SOURCE PASS51.06s**, Ruff/format/mypy/diff0, două **APPROVED_SCOPED** pe40hashuri identice. **108noduri colectate,89SOURCE+19PG; noile3PG NOT_RUN.** Nu este încă acceptare de consumer/integrării.
- **H04–H05 WIP separat, neintegrat:** branch `work/p2-h04-42ef34fc`, commit **`619e3ecd3e536df77b6ac7b7dc42273f4949915b`**, bază locală `d0504e4`; worktree `/home/kali/.hermes/cache/scratch/h04-work-42ef34fc`. [Snapshot/limite/eșecuri](p2-h04-wip-handoff.json). Două fișiere: `api/tests/test_contract_method_pg.py` SHA `b2f47e840b6e1d749c208d677e9b156a6930fc3fd8fa7ea7b05e29f701143121`; selectorul existent `documents/verification/p2-bound-predicates-evidence/h03-process-fixed-pg-selection.py` SHA `a7eb6b9ceaca89f93fc8ba0fb9e8c196cae38b0daf5e3ab4ac9906b34a5c259d`. Autor întrerupt la limita modelului, fără raport final/review. AST și diff-check părinte PASS, **nu execuție**. Ultima suită largă SOURCE: **2FAIL/316PASS/42SKIP**, la `test_batch2_current_reader_actual_helper[None]` și `test_batch2_installed_static_prerequisites`; targeted ulterior23PASS nu închide aceste failures. Nu este SOURCE integral green și nu este QA installed. PG/OCI effectful **NOT_RUN**; toate selectoarele REVIEWED sunt None. Nu integra sau activa WIP-ul fără adjudecare/remedii/review.
- WIP-ul este în obiectele/ref-ul Git local, nu numai în scratch. Dacă worktree-ul dispare, inspectează ref-ul și recreează un worktree/branch nou din commitul exact, fără curățare implicită a înregistrărilor vechi. Artefactele native din scratch trebuie reatestate înainte de folosire; existența lor veche nu este acces actual.
- La handoff: **zero subagenți activi**, niciun job urmărit running; familiile QA vechi retired/drained, resursele exacte și datele păstrate în rapoarte. Niciun proces H04 corelat cu rootul propriu la scanarea limitată same-UID; cinci procese preexistente fără permisiuni nu constituie census global. Nu adopta/șterge resurse străine. HTML-ul `documents/Omnis_Notite_Originale.html` este **PROTEJAT: NU citi/hash/edit/stage/șterge**.

## 2. Prima acțiune executabilă — QA caps/VALIDATION/deadline-B

Roluri: **orchestrator** pentru scope/adjudecare/integrat/commit; un **dezvoltator** pe fișierele produsului/testelor; **reviewer** independent pe snapshotul exact; **QA** pe consumerul real după blocante. Admitere: **cerință → consumer → risc → decizie**. Citește AGENTS/CONTRIBUTING, README CURRENT, [registrul](p2-integration-b06cm.md) CURRENT/D1–D3 și numai secțiunile relevante din plan/arhitectură. Filtrează rapoartele la manifest/verdict/final_results/limite; nu vărsa istoricul sau logurile brute integral.

1. Verifică40hashuri din raportul autorului caps și ambele verdicturi pe aceiași bytes. Refolosește89SOURCE/quality și reviewurile neschimbate; nu le rerula doar pentru reluarea sesiunii. Cele99teste vechi rămân în targetul afectat, nu devin o etapă QA separată.
2. **preflight fără efecte** pentru argv/selecție/source/library/toolchain/UID/căi și oracle. `--check` din runner este **efectful**, nu dry-run. Citește implementarea și folosește help/collection/metadata înainte de efecte. API/CLI Python3.13.15, uv0.12.19, Node24.21.0, npm11.19.0; PATH fixat include `/home/kali/.local/share/omnis-toolchains/node-v24.21.0-linux-x64/bin` și `/home/kali/.local/share/omnis-toolchains/bin`.
3. Prima QA admisă fresh, pe snapshotul revizuit, prin ownerul existent: `api/.venv/bin/python -I -B ops/run_test_db_gate.py --check --target test-model-admission-pg --uv /home/kali/.local/share/omnis-toolchains/bin/uv --timeout-seconds 600`. Rulează ca job tracked background cu PATH/HOME/TMPDIR private explicite și loguri0600; citește sesiunea exactă și receiptul strict/family_drained, apoi cleanup exact/date cluster păstrate. Nu reutiliza fixture-urile consumate. Per-test DBs sunt DROP conform conftest, nu pretinde row retention.
4. Oracle: PREPARE→epuizare ordinară→VALIDATION rezervată→epuizare; caps sursei calificate și DTO max/max+1; buget existent127 versus128 refuzat fără rescriere; T0 comis/A fence/B waiter real pe trei backenduri, expirare originală monotonică+UTC înainte release→zeroSENT/send și RESERVED/UNKNOWN conservator. No-send nu obligă refund când bugetul cleanup a expirat. Două calls×max64 limitează rezervarea128; nu fabrica output-only exhaustion sau usageNO_MODEL nenul.
5. Parsează numai diagnostice sanitizate din producerul actual; noile order/await_site au propriile etichete. `SOURCE_CONTROL` nu este PG și linia timing nu este verdictul final. Nu expune DSN/capability/fullframe/mesaj de excepție/log brut. On failure păstrează tentativa, identifică prima frontieră și remediază cauza înaintea unei noi încercări; nu retry orb și nu mări limitele. **Nu preda după fiecare fix. Nu porni un verifier pentru verifier.** După două cicluri numai harness fără progres restrânge frontiera; nu reseta contorul prin sesiune/rename. Raportează **BLOCKED/NOT_RUN** numai când dovada nu poate fi produsă sigur, nu ca înlocuitor pentru un pas executabil.

## 3. H04–H05 — încheie WIP-ul fără să redeschizi batch2

- Inspectează mai întâi diff-ul `d0504e4..619e3ec` și cele două failures SOURCE de prerechizite reader/artifact; cauza lor nu a fost adjudecată la întrerupere. Logurile originale sunt private și pot expira; summary/hashes sunt versionate. Nu înlocui failures cu targeted23PASS și nu slăbi verificările de artefact.
- Scop: inventar callable cold root/CONTRACT child, wrong-root/child-lineage și guardFalse/exception înainte de acces, zero read/PURE și niciun rezultat utilizabil. Producerul/consumerul/observerul/selectorul existente; fără RPC nou, registry generic, grant extins sau native/model live. Pozitivele autentice neafectate se reutilizează; inventarul de fișiere nu este callable inventory.
- Artefactul existent și image pin au fost găsite/readback înaintea autorului; detaliile exacte sunt în registru. Reatestează hashurile și accesul la reluare, fără adopție/rebuild implicit. Selectorul are ROOT fix la main: testează/integră numai bytes explicite după două reviewuri complementare; nu rula din greșeală main vechi din worktree. Parent integrează doar cele două paths revizuite, prin diff/bytes exacți, comite și verifică; niciun cherry-pick automat al WIP-ului neaprobat.
- QA installed numai după prerequisite SOURCE curente/reviews și admiterea exactă, pe roots NOI, efecte seriale cu QA Admission. BATCH2/STARTUP/H04 REVIEWED=None nu se transformă în acord printr-un flag. [Arhiva fezabilității batch2](p2-bound-predicates-evidence/finite2-coherent-factory-feasibility.json) este trasabilitate, **nu sarcină de reluat**.

## 4. Restul finit până la P2-inert

- După caps: EOF/timeout/cancel după write→SENT/UNKNOWN fără refund/resend; receipt/accounting întârziat post-Stop, duplicate/conflict receive-only fără grant nou; negative DATA/owner/config/projection/ref/digest/receipt și sentinel input/result/error/log pe același consumer. Cod numai pentru lipsă/defect demonstrat, nu helper breadth.
- Reutilizează qualification `191b901`, historical readers `c2fdf7d`, restart H03 `e037cf1`, batch2 `94de21a` și fondațiile B05/B06a/P0/P1 neafectate. Formele efectiv alocate records sunt CASE_SLOT_REF exact1 și STEP_OUTPUT imediat; nu un resolver general. Reverse/cancel/flood SIMULATION rămân astfel etichetate; consumerul CONTRACT nou nu introduce emitterul nativ respectiv.
- Reconciliază exact8rânduri plan§7.1 cu cod/consumer/evidence/review și limitele inerent-live. Apoi canonical real pe bytes finali: `make check UV=/home/kali/.local/share/omnis-toolchains/bin/uv`, după preflight și cleanup/readback. Nu promova SOURCE, test count sau documentare la G02/P2 PASS.
- Ordine neschimbată: **P2-inert → P4a-minim/Settings → acord separat P2-live → P3**. Fără provider/model/target/r1/profil/global/push în această reluare inertă. Cost necunoscut rămâne null/UNKNOWN; FinalModelRequest și NO_MODEL stricte. Commituri mici/revertibile, stage numai paths intenționate, fără amend/reset/force-push. La rezultat sau limită reală de siguranță, păstrează o singură stare de recuperare verificată; nu lăsa intended changes necomise.
