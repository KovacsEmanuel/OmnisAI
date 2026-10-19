# Sesiune fresh — restul P4a/G04a și P2-live/G02-live

**CURRENT — idle fix3de38bc instalat, așteaptă confirmare umană; faza2 NOT_CLOSED.** [Stare exactă](p4a-model-prepare-evidence/idle-fixed-current.json)/[registru](p4a-minim.md). Două reviewuri APPROVED_SCOPED/59SOURCE PASS, limite framing/grant/Stop păstrate. Candidatul este `/home/kali/.omnis-p2-fixed`, wrapper propriu `omnis`, instance2a6b89fd-5c36-4b77-94a9-b1dcb4dab796/8766/release1552956c; READY și STATIC/PURE reale. **Prima acțiune: citește rezultatul terminalului deja pornit proc_448586d0cb34**, receipt `recovery/confirmation-terminal-exit.json` și `state/omnis/catalog/requests/confirmed.json`; nu reemite confirmarea. Apoi Publish/readback/snapshot/select reale→un singur provision→normal Stop/Start/auth și Test model. Candidatul anterior `.omnis-p2-model` a murit în RUNTIME_STATUS înainte de confirmare (exit137, zero confirmări DB), apoi a fost retras fizic/date păstrate. Defectul instalat id:null după2.8s idle a fost reprodus și reparat; aceasta nu atribuie exclusiv toate FAIL-urile vechi. Recovery3a96b9f carantinat, nu se reia; vechiul provision nu se retrimite. Zero apeluri model, bugetul1call300s rămâne fără reset. RestP2/Setup/canonical restante, fără P3/target/global/push; locatoarele UI9 din promptul istoric de mai jos sunt înlocuite de CURRENT.

## Prompt pentru următoarea implementare

**HANDOFF_ONLY — DOAR ÎN SESIUNEA FRESH.** Operatorul a clarificat explicit: **finalizarea fazei 2 cu Test model simplu după logare, fără P3**. Pregătirea acestui prompt nu reia execuția; starea produsului rămâne cea din checkpointul de pauză. Copierea lui într-o sesiune nouă cu cerere de executare constituie reluarea.

```text
Lucrează în /home/kali/OmnisAI.
/ponytail:ponytail full

REZULTATUL CERUT
Închide verificat faza 2: P4a/G04a → P2-live/G02-live, fără P3.
Prioritatea vizibilă: după autentificarea operatorului, Provider → Model →
Connect → Test model → răspuns real afișat în web. Test model trebuie să poată
fi folosit înainte de completarea scope/ROE și separat de Start assessment.
Apoi simplifică Setup/ROE și încheie obligațiile restante și canonicalul final.
Un răspuns reușit nu închide singur faza 2. Nu promite închiderea dacă lipsesc
probe ori autorizări; raportează precis BLOCKED/NOT_RUN, fără rezultat inventat.

CONTEXT MINIM, NU RELUAREA ARHIVEI
Verifică Git/status/diff/HEAD; branch așteptat checkpoint/p2-batch2-pause-20261015.
Checkpoint de pauză14622ab, produs4370a40, adjudecare/reviewuri cd08bdd.
Commiturile documentare ulterioare nu sunt implementare sau reluare automată.
Citește AGENTS.md, CONTRIBUTING.md, primul CURRENT din README,
documents/verification/{p4a-minim.md,implementation-status.md},
p4a-model-prepare-evidence/{web-test-ui9-paused.json,web-test-parent-source-acceptance.json}
și planul documents/Omnis_Implementation_Plan.md §7–8/§19;
consultă arhitectura/UI spec numai pentru contractul afectat.
Folosește skill-urile relevante la nevoie, nu întreg catalogul în fiecare agent.
Nu citi/hash/copia/modifica/stage documents/Omnis_Notite_Originale.html sau
tools/development/ponytail.json; păstrează orice muncă străină.
Reutilizează P2-inert/G02-inert și aprobările pe bytes/calleri neafectați.
Cele două HIGH SAFETY-CATALOG-01/NORM-WEBTEST-F01 sunt închise SOURCE scoped;
nu relansa discovery, vechii autori, reviewurile ori probele neschimbate.

PUNCTUL EXACT DE RELUARE
Candidatul actual: /home/kali/.omnis-p2-ui9;
folosește exclusiv wrapperul /home/kali/.omnis-p2-ui9/omnis pentru lifecycle.
Ultimul readback, NU stare live garantată: http://127.0.0.1:8766,
instance d6a018ed-d3ad-462e-b5a2-d7997db9d704, READY/generation1/epoch1,
assessment_ready=false, ModelTest UNAVAILABLE/operation_id=null/response=null.
Release/pin/identitățile complete sunt în checkpoint; verifică înainte de efecte.
Codul Test model/bridge normal este deja integrat și instalat, nu de rescris.
CLI/OCI/HTTP/scratch0700 și calificările STATIC/PURE reale au trecut;
acestea nu sunt pregătire nativă, browser complet sau inferență.
Confirmarea umană TTY c9cf2e31-f8b5-4a4f-8524-9587eefa0bba este salvată.
Publicarea NU s-a făcut: head generation1/publication_ref=null.
Selecția exactă: UI9/state/omnis/catalog/requests/operator-confirm.json.
Native preparation, cross-boot, auth UI9 și prima inferență sunt NOT_RUN.
UI8/8765 are doar readbackul auth istoric; nu copia/adopta grantul, contul,
sesiunile, datele sau profilul Chrome/Hermes personal. Nu porni candidații vechi.
La pauză nu existau writeri activi; serviciile UI9 erau păstrate pornite.
Artefactele esențiale sunt în Git și UI9; scratch poate expira. Dacă un input
pin-uit lipsește, restaurează numai din proveniența atestată, nu din profilul personal.

EXECUTĂ ÎN ACEASTĂ ORDINE
1. Preflight fără efecte: argv/grammar, biblioteci/pin/source, UID/căi/mounturi,
   artefactul exact și ownerul/cleanupul existente. Citește schema producerului,
   nu inventa refs/câmpuri/rezultate. Reobservă status/head/receipts fără mutații;
   nu repeta publicarea/provisionarea sau apelul dacă starea s-a schimbat.
2. Dacă selecția/head/confirmarea încă se potrivesc, finalizează Publish exact
   prin catalog_publication și verifică readbackul real. Nu cere încă un yes
   pentru aceeași confirmare validă și nu simula autoritatea umană prin PTY.
   Obține snapshot/execution-selection reale prin ownerii existenți. Apoi
   api/src/omnis/modules/runs/model_test_source.py provision prin controlul
   supervisorului deja conectat → pregătire Hermes nativă reală. Nu înlocui
   cu fixture, prewarm, SDK paralel sau flags de test. Pierderea răspunsului
   cere readback/reconciliere, nu resend sau ștergerea intentului pentru retry.
3. Probează normal Stop → Start prin wrapperul original, fără reseed/Save
   repetat care ascunde pierderea datelor; verifică bootul nou și păstrarea
   sursei/configurației. Nu reseta bugetul prin altă instanță. Dacă un fix
   schimbă release-ul, nu suprascrie instalarea imuabilă și nu migra datele
   operatorului fără procedură/autorizație; păstrează probele vechi și recovery.
4. Lasă operatorul să facă pairing/auth/consent în Chrome normal. Pregătește
   serviciul și canalul TTY numai când sunt gata; nu expune coduri/tokenuri în
   chat, capturi, argv, env, Git sau loguri. Nu automatiza/atașa CDP/captura
   profilul personal și nu substitui Chrome testing pentru loginul operatorului.
   Reobservă selecția și auth reală prin owner: Save ≠ auth ≠ inferență.
5. După auth, probează fluxul simplu Test model în web, fără Setup obligatoriu,
   fără Start assessment și fără trafic către ținte. Primul buget aprobat,
   încă neconsumat la pauză: cont Codex ales de operator,
   openai-codex/gpt-6.1-sol/xhigh, date sintetice, maximum1apel/300s.
   Numai acțiune explicită; fără retry/fallback/auxiliare/tool calls sau probe
   SDK suplimentare. Reload/timeout/răspuns pierdut nu acordă un apel nou.
   După primul eșec nu încerca iar automat, nici cu UUID/instanță nouă.
   UI trebuie să arate răspunsul real, starea/failure sincer, durata/usage
   disponibile și requested versus effective observat ori UNKNOWN, nu din
   afirmațiile modelului. Verifică reload/readback fără al doilea apel.
   Dovada browser se face pe build/API/DB reale, cu click/focus/tastatură și
   viewporturi afectate, fără a inspecta profilul personal. Refolosește probele
   neafectate; nu cheltui apelul numai pentru screenshot sau un observer nou.
6. Simplifică Setup/ROE prin componentele existente:
   web/src/features/engagement/{Wizard.tsx,WizardSections.tsx,Engagement.tsx}.
   Folosește limbaj uman pentru scop/excluderi, obiectiv, conturi de test,
   permisiuni și limite; detaliile tehnice în Avansat unde este potrivit.
   Păstrează câmpurile/datele salvate, validările, CAS/conflictele, accesibilitatea
   și stările UNKNOWN/UNAVAILABLE. ROE se generează determinist din opțiunile
   operatorului, nu este inventat de model; niciun drept/scope lărgit implicit.
   Nu pretinde autentificare de țintă dacă există numai câmpuri declarative.
7. Încheie numai restul G04a/G02-live/G-MODEL/G-DATA-EARLY din plan §7–8:
   pachet real publicat/pin-uit și copil nativ; mapping autentic pre-access,
   identitate/lineage și inventar Brain/copil/auxiliare, compresie ori refuz
   explicit conform contractului; request model calificat, reserve→SENT
   durabile, caps/VALIDATION și no hidden calls; rezultat/inbox/delivered versus
   admitted/consumed, duplicate/lost reply/recovery receive-only și Stop fără
   inferență nouă. Păstrează UNKNOWN unde observația nu există; fără efecte
   target. H01–H08 și cele8rânduri §7.1 se reconciliază la dovezile lor, nu se
   rerulează automat și nu se reduc la primul răspuns sau la un număr de teste.
   Dacă alte probe obligatorii cer mai multe inferențe, cere înainte un buget
   finit explicit agregat; grantul1call nu le autorizează. Nu le ascunde/omite.
   Brain chat complet/STEER, identități target, catalog/editor larg și P3 nu
   devin condiții noi ale acestei faze.
8. Rezolvă blockerul canonic cunoscut înaintea gate-ului complet:
   integrations/hermes/tests/test_model_terminal.py:
   test_public_turn_denies_before_native_dependencies_and_preserves_stock_control
   a apelat function(None,None), iar native conversation_loop accesează
   agent.__dict__ înaintea tripwire-ului stock. Reproduce pe sursa pin-uită și
   repară minim callerul/fixture-ul legitim dacă se confirmă; nu presupune
   defect de produs, nu slăbi assertion/guard și nu folosi skip.
   Istoric441PASS/1FAIL rămâne; targeted PASS nu înseamnă canonical trecut.
9. Pe snapshotul final integrat, rulează canonicalul real, după preflight:
   make check UV=/home/kali/.local/share/omnis-toolchains/uv-0.12.19
   make test este alias: nu dubla aceeași suită pentru același snapshot.
   Respectă Node24.21.0/npm11.19.0/Python3.13.15/uv0.12.19 și inputul
   HERMES_NATIVE_SOURCE MANAGEMENT atestat în registru. Verifică accesul real
   înainte de provisioning; --check al ops/run_test_db_gate.py este EFECTFUL,
   nu dry-run. Folosește runnerul/family owner/DB izolat deja existente,
   loguri private, freeze inputs, readback/cleanup exact și date păstrate.
   Nu rula gate-ul pe datele UI9/operatorului. Raportează gate/exit/settlement,
   nu doar ieșirea make; după note-only rerulează doar verificările docs.

REMEDIERE FĂRĂ COMPLICAȚII
Folosește codul și callerii existenți, cea mai mică schimbare completă;
fără framework, SDK/backend/owner/registry/harness/dependență nouă fără defect
concret. Înaintea verificării: cerință → consumer → risc → decizie; control
pozitiv și negativ pe același canal, nu încă un raport de admitere.
Un orchestrator integrează/acceptă, un dezvoltator scrie în worktree din HEAD
local verificat; parentul nu devine al doilea autor. Reviewer independent,
QA pe consumerul real, fără roluri suplimentare de decor.
Development/review openai-codex/gpt-6.1-sol/xhigh, fără fallback.
Pentru defect: reproduce RED → fix minim cu toți callerii/tests/fixtures/config/
exports afectate → GREEN → review independent exact. Două reviewuri complementare
când schimbi authority/dispatch/Stop/secrete/cross-runtime; re-review focalizat
al findings și QA pe artefactul real după blocante. Reutilizează scope neschimbat.
Păstrează catalog Stop3000/legacy2900/grant3600/wire4096, fără alte creșteri de
limite/deadline/grant, compresii sau identități eliminate ca să iasă verde.
Nu crea audituri/rapoarte/verifieri recursivi; după două cicluri numai harness
fără progres restrânge proba ori raportează blockerul, fără reset prin sesiune.
Commit local după fiecare schimbare coerentă, numai paths intenționate, cu
comenzi/rezultate/limite/rationale și readback Git. Fără push/reset/amend/stash,
modificări globale, date/conturi personale sau trafic țintă. Nu adăuga cron.

ÎNCHIDERE
Nu preda după fiecare fix/review; continuă până la rezultat verificat, intervenție
umană necesară, blocker real, stop sau limită de siguranță/buget/context.
Final în română: pot sau nu pot folosi modelul după logare, URL/pașii simpli,
ce este efectiv PASS/FAIL/BLOCKED/NOT_RUN și reviewuit, commituri, resurse/date
păstrate, ce rămâne. Actualizează CURRENT/harta în loc și registrul existent.
Faza2 CLOSED numai cu toate obligațiile aplicabile și canonical final trecute;
altfel NOT_CLOSED cu motiv precis, nu doar „teste verzi”. STOP înainte de P3.
Explică simplu; finalul numește ce ai omis/neexecutat și riscul rămas.
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
