# Handoff C10/B06 — prompt de continuare și checkpoint istoric

## CURRENT — acceptare integrată după reluare

Candidatul8ea28b2 **este integrat** în `25395bd`, după două re-reviewuri complete APPROVED_SCOPED; C10-NATIVE-F01 închis. Remediile quality/cold legacy/fixture sunt comise separat în `9a49d15`/`46589bf`/`d3a176b`. [Registrul actual și toate dispozițiile](p2-bound-predicates.md), [canonical final versionat](p2-bound-predicates-canonical-pass.json) și [harta](implementation-status.md) înlocuiesc punctul de reluare de mai jos. Canonical3 pe `ff095af`: exit0/drained,969hashes stabile, cleanup exact/date păstrate; C10 integral/B06b/G02/P2 rămân deschise. Observația C10-LEGACY-SEC-N01 este LOW/neblocantă/deferred, nu un blocker ignorat. Git real decide HEAD-ul curent, fără SHA auto-referențial inventat.

**Prompt copy-ready actual:**

Promptul de mai jos înlocuiește mandatul îngust de „numai partial return” cu o continuare secvențială a lipsurilor canonice B06/P2-inert, apoi P4a-minim. Nu este un plan nou, nu închide niciun gate și nu pornește implementarea prin simpla versionare a acestei note. Se execută când operatorul îl transmite sesiunii de implementare. P2-live rămâne separat autorizat.

```text
Continuă OmnisAI în /home/kali/OmnisAI spre închiderea P2-inert,
apoi livrează P4a-minim, cu cod minimal și probe relevante. Implementează
și remediază, nu te limita la un audit, un plan sau alt handoff.

BAZĂ ȘI AUTORITATE
Baza acestei pregătiri: 65d8c7057f54841f4607622b4045c3e41305236b,
branch checkpoint/p2-vm-restart-20261011. Citește HEAD/status/diff/staged
și worktree-urile reale; nu schimba branchul și nu adopta munca străină.
Produsul C10 records este integrat25395bd, cu remedii9a49d15/46589bf/d3a176b.
Canonicalul ff095af a trecut exit0/drained; până la baza65d8c70 s-a schimbat
numai documentația. Nu reimporta8ea28b2 și nu relansa acceptările neschimbate.

Citește AGENTS/CONTRIBUTING/README CURRENT și harta implementation-status.
Intrare: documents/verification/p2-bound-predicates.md și canonical-pass.json
cu prefixul p2-bound-predicates-. Autoritate: plan §7/§7.1/§8/§19 și
arhitectură §5/§5.2/§6.3/§9.3–9.5/§9.9–9.10. Citește registrele B06c/m,
DATA și B06b numai pentru seamul activ. Secțiunile vechi ale handoffurilor
sunt istorice; granturile/holderii/nonce-urile lor nu sunt mandate actuale.
Încarcă skill-urile relevante, nu întregul catalog.

MANDAT FINIT, FĂRĂ ÎNCĂ UN PLAN PARALEL
Fă o singură comparație scurtă cu cele opt criterii din plan §7.1:
cerință → owner/caller existent → probă acceptată și snapshot → lipsă.
Separă defectul confirmat, funcția nelivrată, proba lipsă și live neautorizat.
Reutilizează evidence pe bytes/artefacte neafectate; nu transforma rapoarte
SOURCE/AST/SDK în installed/native/live și nu declara skip drept PASS.
Păstrează această delta în registrul existent, fără alt catalog de faults.

Lucrează în felii mici, coerente și comise, în ordinea de mai jos.
Continuă automat următoarea felie inertă admisă după acceptare, fără
reaprobări cosmetice sau oprire după fiecare raport. Nu scrie toate
restanțele într-un singur commit și nu trece peste un blocker de safety.
La buget/context insuficient păstrează checkpoint recuperabil, fără DONE fals.

1. TERMINĂ CONSUMATORII B06b, ÎNCEPÂND CU PARTIAL RETURN
- Pe metoda records existentă, return_when calificat și satisfăcut după
  un prefix real read/PURE permite predarea bounded fără pașii rămași.
  Nu prezenta un fault injectat sau rezultat fabricat ca pozitiv.
- TaskResult autentic: header/refs/context exacte, receipts/artifacts reale,
  exact un MethodResult per MethodPlan.requirement, stări/motive/gaps corecte.
  DONE cere probe; cerințele lipsă nu dispar și nu devin N/A.
- Persistă rezultatul înainte de MethodCheck. Backendul verifică independent
  prefixul/predicatele și produce INCOMPLETE când un done_when lipsește;
  fără SUCCEEDED automat sau PASS funcțional fără oracle/controls trusted.
- Readback/reconcile/replay fără read/PURE/usage/consum dublu; păstrează
  traseul complet, compact/inline și compatibilitatea cold/legacy admisă.
- În următoarele felii strict necesare închide restul contractului metodei:
  applicability/preconditions/invalidation și evidence-bearing obligations,
  optional versus required, UNKNOWN distinct de NOT_APPLICABLE, checker
  indisponibil/semantică nedecidabilă → UNKNOWN/gap, fără completitudine falsă.
  Formele contractate neacoperite rămân explicit deschise, nu „rezolvate”
  prin broadening arbitrar, regex sau un demo nou.
- Completează numai lipsurile obligatorii C03/C04/C06–C12/H03–H08:
  refs/slots/StepOutput/predicate calificate, root/child/batch/attempt reale,
  mapping comis înainte de acces, două goaluri identice distincte, inventar
  efectiv fără inheritance neadmis și observer/wrong-identity deny.
  Lineage autentic/atomic ori refuz fără acces la seamul real este admis;
  compresia care cere inferență se probează live, nu se simulează ca PASS.
- M1 exact după M2 aditiv rămâne istoric; input/auth/precondiții invalidate
  nu devin calificare curentă. Duplicate/conflict/restart/lost reply și
  receive-only post-Stop → HELD fără wake/model/tools noi/dublu accounting.
  delivered/admitted/turn_completed/consumed sunt stări distincte.
  Same-Host cache acceptat nu dovedește crash/restart al întregului runtime.
- N01 LOW deferred nu este blocker nou; remediază-l proporțional dacă
  atingi frontiera relevantă, sau păstrează explicit dispoziția motivată.

Trasează producerul, run_contract din agent/contract_execution.py,
omnis_hermes/contract_method.py:task_result, validatorii/schema/finalul nativ,
tasks/managed_contract.py, tasks/method_checks.py și
runs/managed_admission.py:_result_check/reconcile. Nu repara numai helperul
ignorând callerii, cardinalitatea receipts sau starea task/attempt.

2. LEAGĂ B06c ȘI B06m LA ACELAȘI OWNER REAL
- Reutilizează ModelProjections/ModelDispatch, NativeTaskOwner,
  policy/admission.py, policy/budgets.py și adaptorul/sinkul existente;
  verifică definițiile/usages înainte de stabilirea exactă a paths.
- Producer/proiecție calificată → decizie data-policy exactă → DTO final
  immutable → guard integral după transform, pe direct și worker.
  Aprobarea DATA sau UUID-urile din fixture nu sunt grant, turn/config
  autentice ori selecție de model. NO_MODEL rămâne înainte de client.
- Probează SDK real NO-IO unde este necesar, fără egress/provider, și
  sentinelul pe întreg input/payload/result/error/log. Refuză raw/secrete,
  unknown sensitive, cross-case și extra_body/headers/query/bypass.
  Refolosește măsurătorile SDK neschimbate; nu reface serializerul de dragul QA.
- Owner de produs → reserve tranzacțional COMIS → SENT durabil independent
  înainte de send → transport de protocol inert declarat → receipt/UNKNOWN.
  Callerul și bariera efectivă trebuie implementate; contabilitatea singură
  sau apelurile directe la helper în teste nu închid B06m.
- Caps calls/output/deadline, rezervă VALIDATION, concurență cu overlap
  observat, Stop între reserve/send și veto la sink. UNKNOWN după SENT
  păstrează rezerva; RELEASED numai cu no-send demonstrat. Cost necunoscut
  nu este zero; limita financiară neimplementată/neprobată rămâne BLOCKED.
- Retry/fallback/auxiliary sunt readmise și contabilizate ori refuzate;
  niciun client/provider/retry ascuns. Nu pretinde atomicitate DB/rețea.
  Proveniența nativă turn/config/purpose și seamul pre-send real se califică
  pe run nou înainte live; transportul sintetic nu este turn/grant nativ.

3. ACCEPTĂ P2-INERT, APOI P4a-MINIM
Închide inert numai când toate obligațiile inerte §7.1 au implementare,
probe la consumerul cerut și review acceptat; fiecare rest live/ulterior
are motiv canonic, nu doar eticheta „deferred”. Completează și scenariile
H01/H02 obligatorii lipsă la consumerul extins (reverse/EOF/timeout/
backpressure/unknown method/no personal grants/drain), fără recertificare B05.
Installed/copy-installed/native și readerul istoric sunt dovezi distincte;
produce proba cerută sau păstrează explicit BLOCKED/NOT_RUN.

După închiderea inertă, livrează P4a-minim: catalog read-only, selecție
explicită, save→readback, status runtime/dependencies și requested/effective
cu motiv de fallback. REQUIRED nesuportat blochează; fără hot-swap sub copii.
configured/authenticated/reachable/inference_ready sunt distincte.
Fără cont se livrează stările indisponibile corecte, nu readiness fabricată.
Nu conecta conturi și nu face provider discovery/pricing/refresh/inferență.

Pentru P2-live oprește la acordul separat cont/provider/model/date/buget,
cu blocajul și cererea concretă, o singură dată. Cere run/selection/manifest
noi, nu „încălzirea” NO_MODEL. Nici P2-inert, nici Settings nu închid G02-live.
B06j/Jev își păstrează alocarea canonică §8: SDK/typed questions/DecisionReceipt
și sentinel inert când ajunge la consumerul său; shadow live numai cu acord,
paired/advisory după G-LOOP. Nu inventa evaluator live sau gate circular
Jev/editor/research înainte de închiderea inertă ori primul finding.

TESTE ȘI REMEDIERI — PROPORȚIONALE, DAR REALE
- RED pentru defect/funcție lipsă → fix minimal → GREEN și regresii afectate
  după ultima editare. Refolosește fixtures și teste; fiecare test nou trebuie
  să acopere cerință lipsă ori defect reprodus, nu să mărească un număr.
- Lint/type/contracte și preflight determinist o dată înainte de PG/native;
  detectează devreme importuri, keyword drift, compact expansion și cold pins.
- Makefile oferă targets pentru publication/PURE, managed-composition/admission,
  contract-method/native, model-projection, model-budget și model-admission.
  Alege doar targets afectate, nu toate la fiecare felie. Targetul Make nu
  implică acceptare în --target al runnerului: verifică choices și wrapperul
  real. Native/projection au prerequisites/opt-in distincte; canonicalul
  standard nu dovedește automat că aceste probe au rulat.
- PG numai prin ops/run_test_db_gate.py/ownerul existent, fixture nouă proprie
  atestată, UDS/no-network; fără DSN extern, SQLite fallback sau r1.
  Build/installed/native cer pin, patch reapply și origini/hashuri reale.
  Folosește referința locală base atestată, nu FROM sha256:IMAGE_ID interpretat
  ca registry. Metadata/install/AST/synthetic peer nu sunt integrare nativă.
- Un autor; minimum review independent exact-snapshot; două reviewuri
  complementare în paralel la authority/concurrency/Stop/effects/secrets/
  cross-runtime. QA reală poate intra în aceste roluri, fără agent ceremonial.
  Reproduce/adjudecă blocantele, repară minimal, rerulează affected checks
  și cere re-review numai pentru delta/call-sites afectate, până la acceptare.
- Înainte de acceptarea unui snapshot integrat/faze rulează canonicalul real,
  nu după fiecare commit, fix, document sau reminder. Fă deterministele și
  probele afectate întâi pentru a evita eșecuri târzii. Comanda cunoscută:
  PATH=/home/kali/.local/share/omnis-toolchains/bin:/usr/bin:/bin TMPDIR=/home/kali/.hermes/cache/scratch make check UV=/home/kali/.local/share/omnis-toolchains/bin/uv
  Dacă bytes relevante se schimbă după gate, rerulează gate-urile afectate
  și canonicalul când snapshotul de integrare este final. Nu redenumi subsetul.
- Browser numai pentru UI/call path afectat (inclusiv P4a), pe build/API/DB
  proprii, cu tastatură, stări și persist/readback, nu galerie de screenshots.
  Join/readback exact resurse proprii și receipt/drain; păstrează date/loguri,
  FAIL-urile și limitele. Parsează sanitizat, fără dump de secrets/traceback PG.

DISCIPLINĂ ȘI PREDARE
După două cicluri numai harness fără avans la aceeași cerință, chiar între
sesiuni: checkpoint WIP/BLOCKED, restrânge reproducerul/frontiera; nu alt
verifier/owner și nu ignora safety. Pentru prerechizit lipsă încearcă alternativa
admisă; dacă nu există, raportează cauza concretă, nu output inventat.
Nu crea framework, supervisor, scheduler, catalog/test runner paralel, alt demo,
dependență latest, critic LLM/REVIEWER/B18a.r sau editor complet preventiv.
Schimbările de schemă/contract numai cu consumerul necesar și probele lui;
păstrează istoricul/pins și compatibilitatea, fără weakening/any/global ignore.

Commituri mici coerente cu motiv/verificări/limite/revert; stage explicit,
git show/status după fiecare. Notele concise în registrele existente, nu
raport nou la fiecare apel. Nu modifica/stage HTML-ul protejat, r1/profiluri,
credenciale, servicii străine sau configurație globală. Fără target/P3/push.

Predare scurtă în română: funcții livrate, fiecare criteriu inert PASS/FAIL/
BLOCKED/NOT_RUN, review și commituri, probe SOURCE/PG/native/installed/SDK/live
separate, cleanup propriu, următorul pas sau exact acordul live necesar și
matricea globală. „Gata” numai pe scope verificat, fără modificări intenționate
necomise. Nu promite absența tuturor gap-urilor și nu închide P2 din test count.
```

## Checkpoint istoric — înainte de acceptarea de mai sus

Textul următor și promptul său final sunt păstrate la frontiera inițială. „Neintegrat”, „review pending” și instrucțiunea de oprire aparțin **sesiunii vechi**; nu sunt starea sau următoarea acțiune curentă.

Checkpoint cerut de operator după două compactări. **Oprește implementarea în această sesiune; continuarea este pentru sesiunea nouă.** Nu este un plan concurent. Autoritate: `AGENTS.md`, plan §7.1/§8/§19, arhitectură §5/§6.3/§9.3–9.5/§9.10 și [contractul B06b](p2-b06b-next-contract.md). [Harta](implementation-status.md) este proiecția, nu înlocuiește canonul.

**Această notă înlocuiește punctul de reluare din [handofful anterior](p2-method-session-handoff-20261012.md).** History/C04/compact/C11 au avansat între timp; nu reporni reviewurile vechi sau implementarea lor.

## 1. Git și resurse — citește starea reală la intrare

- Principal: `/home/kali/OmnisAI`, branch `checkpoint/p2-vm-restart-20261011`. HEAD **înaintea commitului acestui handoff**: `9fb26d5396c81164107eb882f51073c5e74962e6`. Citește HEAD real; această notă nu își inventează propriul SHA.
- Produs integrat: C04 `77c835d28f712ee39f49a39b8d79de2739789497`, C11 `d7a51f3adc04be57fe528f6e14425111d3615144`; docs C11 `8e432a9`, lecția API `9fb26d5`.
- Singurul untracked preexistent din principal: **`documents/Omnis_Notite_Originale.html`, protejat**. Nu modifica, șterge, stage, stash sau reset acest fișier ori alte modificări străine.
- **C10 nu este integrat în principal.** Candidatul final este comis și clean în branch `work/p2-bound-predicates-nativefix`, HEAD **`8ea28b2794912726428fbc3cac6f6d18269be454`**, worktree `/home/kali/.hermes/cache/scratch/omnis-p2-bound-predicates-nativefix`.
- Istoric C10 reversibil: `5fac42e31861d5be7ba8f5239eb6473cacd4b925` candidat inițial; `2ca04773e3d3e3d9a30d9601ab8dad45756569b0` remedii SOURCE, dar caller compact defect; `8ea28b2` corecția callerului. Primele două sunt WIP, **nu cherry-pick serial în principal pentru a lăsa checkpointuri defecte**. După acceptare transferă numai diferența finală scoped față de baza produsului `d7a51f3`, cu istoria candidatului păstrată pe branch.
- Worktree-ul precedent `/home/kali/.hermes/cache/scratch/omnis-p2-bound-predicates`, branch `work/p2-bound-predicates`, este clean la `2ca0477`; păstrează snapshotul reviewului SOURCE. Nu îl confunda cu candidatul final.
- Celelalte worktree-uri sunt istorice; `git worktree list --porcelain` le identifică. Nu le reimporta, șterge sau adopta automat. Codul C10 rămâne recuperabil prin ref Git chiar dacă scratch expiră; recreează worktree numai din commitul local exact.
- `delegate_task(action='list')` a confirmat **zero subagenți live** la handoff. Nu există un review final de așteptat. Notificările întârziate nu redeschid scope-uri deja adjudecate.
- Părintele a verificat receipturile și absența exactă a containerelor/rețelelor pentru trei proiecte C10: ultimul PASS, preflightul întrerupt și FAIL-ul remedierii anterioare. Două endpointuri native finale și opt PID-uri reader absente; date/loguri păstrate. **Nu este o declarație că toate serviciile străine ale VM sunt oprite.**
- Nu s-a făcut push, restart/adopție r1, schimbare globală/profil personal, cont/model sau trafic target.

## 2. Ce funcționează și unde este frontiera

| Perimetru | Implementare | Probe | Review / limită |
|---|---|---|---|
| History/compact | Integrate `93b7700` / `024a10b` | SOURCE/native/PG scoped, caps/input păstrate | APPROVED_SCOPED la snapshoturile lor; nu le relua |
| C04 CONTRACT/no-oracle | Integrat `77c835d` | 121 SOURCE, 4 PG/native PASS; 19 SOURCE la integrare | APPROVED_SCOPED; perechi native exacte și două outcomes **BLOCKED+reason**, nu oracle pozitiv |
| C11 same-Host lost reply | Integrat `d7a51f3` | 8 SOURCE, 47 runtime, un caz real post-Stop PASS33.48s/drained | APPROVED_SCOPED; cache Host original, fără resend/grant/read/PURE; nu Host crash/restart sau provider loss |
| **AICI — C10 end-of-method records** | Candidat final `8ea28b2`, neintegrat | 135 SOURCE +21 native/build PASS; două cazuri PG/native reale PASS56.81s, exit0/drained | Remedii originale aprobate SOURCE pe `2ca0477`; **delta finală de șase fișiere NOT_REVIEWED** |
| C10 integral / B06b / G02 / P2 | PARTIAL / NOT_CLOSED | Forme restante și canonical final NOT_RUN | Nu închide din ultimul PASS targeted |
| B06c/B06m | Componente/proiecții/ledger parțiale | Probe istorice scoped | Consumer owner reserve→SENT→transport/Stop/caps încă restant |
| P4a-minim / P2-live | Nelivrate | NOT_RUN | După închiderea inertă; live cere acord cont/model/date/buget |

C10 finit existent: registru trusted cu trei predicate pentru cerințele publicate `normalize-records`, `build-surface-map`, `preserve-input-context`; refs calificate pe BoundProcedure și closure schema/pași/required. Producerul emite trei `done_when` și un `return_when`. Copilul real citește inputul și execută două PURE; predicatele se evaluează pe receipts/output/header reale. Checkerul backend verifică independent lanțul înainte de MethodCheck COMPLETE. **Return satisfăcut nu autorizează succes când un done lipsește.** Fără oracle/control trusted, cele două CriterionOutcomes rămân BLOCKED cu reason și gaps.

## 3. Findings — nu pierde și nu redeschide inutil dispozițiile

| Finding | Reproducere / remediu | Stare exactă |
|---|---|---|
| C10-NORM-F01 / C10-SEC-F01 | Pinul nou admitea eliminarea tuturor predicatelor; propagare explicită retained bundle/version, current records impune closure, legacy explicit zero-only | CLOSED_SOURCE_SCOPED în reviewurile pe `2ca0477` |
| C10-SEC-F02 | `SchemaRef.revision=true` compara egal cu 1; validează toate refs/tipurile înainte de equality/lookup, API/native parity | CLOSED_SOURCE_SCOPED pe `2ca0477` |
| C10-SEC-F03 | Step străin/lipsă producea KeyError preconstructor; structură/Key/existență înainte de lookup, refuz sanitizat | CLOSED_SOURCE_SCOPED pe `2ca0477` |
| C10-SEC-F04 | Descriptorul pinna alt fișier și callerul nu verifica identitatea checkerului; v2 descriptor pentru closure real13, record retained verificat înainte COMPLETE | CLOSED_SOURCE_SCOPED pe `2ca0477`; istoric numai combinații digest/composer exacte, existing-check receive-only + regeneration/equality |
| **C10-NATIVE-F01** | Callerul nou căuta `payload['prompt_bundle']` în wire compact cu numai `prompt_bundle_ref`; READ1/PURE2→KeyError. Corecția folosește strict `expanded_payload` după validarea assignmentului constructor-owned, apoi retained bundle către `task_result` | **FIXED_UNREVIEWED** în `8ea28b2`; RED2FAIL/2inlinePASS → GREEN și două cazuri reale PASS; re-review focalizat încă necesar |

Reviewurile SOURCE complete și hashurile sunt versionate în [normative-source-rereview.json](p2-bound-predicates-evidence/normative-source-rereview.json) și [security-source-rereview.json](p2-bound-predicates-evidence/security-source-rereview.json). Verdictul normativ era CHANGES_REQUESTED pentru callerul încă defect, iar security aproba numai F01–F04. **Nu transforma aceste rapoarte în aprobare a lui `8ea28b2`.** Codul API/composer și closure13 nu s-au schimbat în ultimul fix; aprobarea neafectată se păstrează numai în scope-ul original.

## 4. Dovezi finale și limite — nu rerula ca reacție la remindere

[Checkpointul JSON versionat](p2-bound-predicates-checkpoint.json) păstrează **17 paths/hashes** ale diff-ului final față de `d7a51f3`, cele șase paths ale ultimei corecții, comenzile/exits, proof hashes, reviewuri și cleanup. Părintele a comparat hashes/probe/receipturi/counturi, nu doar rezumatul autorului.

- SOURCE pe bytes finali: `api/tests/test_assignment_compact.py`, `test_contract_method_checks.py`, `test_c10_bound_predicates.py` → **135 PASS8.81s/exit0**; native contract/build → **21 PASS0.50s/exit0**. Ruff și mypy pe două fișiere afectate exit0, diff-check0. Runda anterioară are179API/205native/36C10 PASS, fără transfer de autentificare din holders SOURCE.
- Patch/manifest/pin native resealed, **15 fișiere reaplicate cu SHA exacte**. Composer păstrat `4a3606b8e0354bceb8066f6de536932ee420d1147aa9311084ceafb4afbea850`; checker `managed.contract-pure.v2`, closure13 digest `388fe9da680951249202045b10e10245d42352a0c194413d221d647b54a085db`.
- Ultimul gate existent selectat: `criteria-normal` + `criteria-legacy717` → **2 PASS,5deselected56.81s/exit0/family_drained=true**. SOURCE Host, stock pinned AIAgent/RuntimeHost/NativePeer/RuntimeClient/owner real; document preparation este prerequisite double declarat, nu înlocuiește execuția metodei.
- Pentru fiecare caz: read1/PURE2/result autentic, MethodCheck COMPLETE, două BLOCKED+reason/gaps, inbox1/consumed1, patru readeri CLI noi exit0 fără reexecuție. Current: trei predicate native SATISFIED. Legacy717: zero-predicate explicit. `admitted=0`, `turn_completed=0`; nu tur Brain. Exit native -9 este teardown bounded, nu Stop graceful universal.
- **Legacy717 PG este producer fresh cu pin composer vechi și checker nou, nu reader al unui checker vechi instalat imuabil.** Compatibilitatea celor trei perechi de descriptor istoric are SOURCE regeneration/equality; proba autentică a unui record/checker istoric instalat rămâne NOT_RUN. Nu inventa o asemenea probă sau rescrie vechile records.
- Formula cap/accounting și materialele obligatorii sunt păstrate: assignment65536, wire/context32768, deadline4.5s, execution guard3s, seed records/input original. Fără creșteri de timeout sau prewarm pentru QA.

### FAIL-uri păstrate

- C10 înaintea remedierilor: pozitiv PG1PASS28.48s la snapshotul inițial nu transfera F01–F04 sau callerul ulterior.
- `2ca0477`: **2FAIL45.19s/exit1/drained**. Current RuntimeUnavailable înainte de stage, cauza **UNKNOWN**; legacy după read1/PURE2, fără rezultat. Bugul compact a fost reprodus separat; nu declarăm retroactiv că explică eșecul pre-stage. Ultimul PASS nu șterge această încercare.
- Un `runpy` preflight al ultimului autor a executat accidental driverul unguarded sub tool timeout5s: **gate130/drained, zero cazuri**, date păstrate și endpoint retras; deviere de driver, produs NOT_RUN, nu RED. Execuția finală tracked și2PASS sunt separate. Nu executa un driver cu `runpy.run_path(..., run_name='preflight_only')` ca test de parser când are apel top-level.
- C11 full-target FAIL302/303 și canonical snapshot5 **FAIL exit2 /1491API PASS2FAIL2SKIP** rămân. Fixurile fixtures și targeted PASS nu acordă canonical GREEN.
- **Canonicalul final integrat este NOT_RUN.** Blockerul mediilor lipsă invocat de ultimul autor era numai în worktree-ul fără venv-uri; nu este dovadă că principalul este blocat. În sesiunea nouă verifică prerequisites reale în principal după integrare. Nu slăbi Makefile/gates și nu crea aliases false-green.

## 5. Următorii pași strict necesari

1. **ORIENT finit:** `git status --short --branch`, HEAD/diff/staged/worktrees în principal și candidat; citește această notă, checkpointul JSON, AGENTS/README/harta. Încarcă `omnis-project-status`, `omnis-delivery`, `omnis-review-qa`, `omnis-hermes-runtime`, `hermes-agent`, `omnis-api-data`, `test-driven-development`; pentru debug numai când apare un defect concret. Nu audit general și nu reimport history/C04/C11.
2. **Re-review focalizat C10-NATIVE-F01 pe `8ea28b2`:** delta exactă `2ca0477..8ea28b2`, șase fișiere: test compact/helper, upstream caller, pin/manifest/patch. Reviewerul primește criteriul și raportul final, nu verdictul dorit. Verifică actual caller după constructor-owned assignment, expansiunea exactă compact/inline/current/legacy, bounds/no new work, regression RED→GREEN și15 reapply hashes. Reutilizează dispozițiile SOURCE F01–F04 neafectate; nu relansa reviewul întregului proiect sau PG doar pentru că s-a schimbat sesiunea.
3. Numai după aprobare și compararea exactă a celor17 hashes: integrare byte-exact în principal a **diff-ului final** `d7a51f3..8ea28b2`, numai paths owned; păstrează docs/HTML străin. Commit produs normal cu teste trecute, nu checkpointuri intermediare defecte. Rulează un check afectat de integrare și canonicalul real la frontiera produsului după prerequisites; fără rerun al probei PG identice când bytes/distribuția/evidence nu s-au schimbat. Dacă un finding schimbă bytes relevante: reproducer→fix minimal→numai gate afectat→re-review delta.
4. După integrarea scoped, continuă **restul B06b pe consumerii existenți**, conform §7.1/C01–C12: early return bounded cu rezultat parțial persistent (acum numai refuse success), applicability/preconditions/invalidation/obligații evidence-bearing/unknown checker, M1/M2 și calificarea materială istoric versus new admission, formele C04/C11/H07 și binding/lineage/inventar încă neacoperite. Delimitează următoarea singură felie prin cerință→owner→probă; nu decreta completitudine din numărul de teste. Oracle pozitiv este separat; nu transforma COMPLETE în FunctionalPASS și nu forța un al treilea demo/input.
5. Apoi **B06c/B06m** pe owner/store/projection/ledger existente: producer/proiecție qualified→guard integral; reserve comis→SENT durabil→transport inert/receipt UNKNOWN, caps/VALIDATION/concurență/Stop între reserve/send și retry/fallback/aux refuzat. Nu alt supervisor/engine/fixture framework. Componentele importate anterior nu sunt acest consumer complet.
6. **P2-inert → P4a-minim → P2-live**. P4a: selecție explicită/catalog read-only/save→readback, configured/authenticated/reachable/inference_ready distincte. Live numai cu acord separat cont/provider/model/date/buget, nu credentialele personale sau warm NO_MODEL. Nu faza3 înaintea dependențelor canonice.

**Regula anti-deraiere:** un singur autor/worktree, subagenți fresh pentru implementarea/reviewul concret; comite mici changes coerente, verifică Git după fiecare. Nu teste/reviewuri ceremoniale, audit de P0/P1/B05 neschimbate, inventar nou de faults sau verifier pentru verifier. După două cicluri numai harness fără progres la același criteriu, păstrează WIP/BLOCKED și restrânge reproducerul; countul nu se resetează prin sesiune nouă. Nu ignora un blocker de safety pentru a ieși din buclă. Un eșec/prerequisite absent rămâne FAIL/BLOCKED/NOT_RUN, nu output fabricat sau check slăbit.

## 6. Toolchain și artefacte

- API: `/home/kali/OmnisAI/api/.venv/bin/python -I -B`; uv `/home/kali/.local/share/omnis-toolchains/bin/uv`, locked0.12.19. API/CLI/native au medii separate; verifică manifests/prerequisites reale înainte de execuție.
- SOURCE pin: `/home/kali/.hermes/cache/scratch/contract-method-evidence/pinned`, Hermes commit `ee5ee84a345204a3b1d6ef6ba1ab747e602867b9`. Dacă exportul/libraries au expirat, recuperează explicit pinul și verifică hashes; nu presupune installed equivalence.
- Scratch final: `p2-c10-native-bundle-fix-author.json` (SHA `f865888b95e17081ef0ae878f1da6b12d9d780a529f5b9313ddd4da1d8b57ff6`), `p2-c10-native-bundle-consumer-driver.py`, `p2-c10-native-bundle-diagnostic-case.py`, `p2-c10-native-bundle-first-failure-final.json`, `p2-c10-native-bundle-qa-evidence/`. Probe hashes/comenzi/concluzii sunt versionate în checkpoint; scratch poate expira.
- Runnerul real este `ops/run_test_db_gate.py`/`prove_private_fixture`/`run_gate`, fixture own atestată UDS/no-network, nu DSN extern/r1 sau bootstrap/emitter fals. Logs600; **nu afișa** DSN/capability/runtime.boot brut/traceback PG. Parsează privat numai câmpurile allowlisted. Nu șterge date/credentiale/loguri și nu adopta resurse străine.
- Docs: `python scripts/render_docs.py --check`, `python -m unittest discover -s tests/documentation -v`, `git diff --check`; Markdown normativ se regenerează cu rendererul existent. Aceste verificări nu sunt canonical de produs.

## Prompt scurt pentru sesiunea următoare

> Continuă OmnisAI din checkpointul local existent. Citește întâi `documents/verification/p2-c10-session-handoff-20261012.md` și `p2-bound-predicates-checkpoint.json`, apoi Git real/AGENTS/README/harta și numai secțiunile relevante din plan/arhitectură. C10 final este comis în `work/p2-bound-predicates-nativefix` la `8ea28b2`, **neintegrat**, cu2PG/native PASS și review delta încă NOT_RUN. Începe cu re-review focalizat C10-NATIVE-F01 pe cele6 fișiere, nu audit/restart/tests redundante. Păstrează aprobările SOURCE F01–F04 în scope, FAIL-urile și limitele legacy. Integrează exact17paths numai după acceptare, verifică gate-ul real la frontiera integrată, apoi restB06b→B06c/B06m→P4a-minim conform §7.1; live separat. Un singur autor pe worktree, subagenți fresh, TDD și commituri mici. Nu atinge HTML-ul protejat, profiluri/r1/daemon, conturi/model/target/push. Nu inventa breadth sau verdicturi și nu te opri la helper/harness când consumerul de produs este disponibil. Predare scurtă în română cu implementare/probe/review separate și matricea globală.
