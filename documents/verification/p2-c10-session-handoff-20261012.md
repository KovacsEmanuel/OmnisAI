# Handoff C10/B06 — prompt de continuare și checkpoint istoric

## CURRENT — continuare după acceptarea MethodResult PARTIAL, 13 octombrie

**Ultima felie acceptată: PARTIAL finit pe `e6ffcf8`.** [QA independentă](p2-bound-predicates-evidence/partial-requirement-schema-independent-qa.json)2PASS/25deselected59.63s/exit0/drained, fullCOMPLETE și prefixPARTIAL/NOT_RUN/DONE/schemaVALID/INCOMPLETE,8readeri/public după Stop/no-rerun/consum=1. [Părinte](p2-bound-predicates-evidence/partial-requirement-parent-acceptance.json):11SHA/150artefacte/cleanup exact/date păstrate. Selectorul publica2cf4e0 și schema generată9c6c4e9 au remedii RED→GREEN și re-reviewuri complementare; ambele FAIL-uri originale/cauza runtime NOT_OBSERVED păstrate. QA01/QA02 sunt închise **numai pentru acceptarea curentă scoped**, fără cauză istorică inventată. Continuă restB06b forme/binding/inventar/ResultQualification/M1M2/installed history/runtime restart; nu relansa PARTIAL acceptat ori auditul launch. B06b/G02/P2 PARTIAL, canonical final NOT_RUN, P4a-minim NOT_IMPLEMENTED, limitele live neschimbate. Paragraful și snapshotul următor sunt istorice după evidence/optional.

**Mandatul de continuare este în curs, nu suspendat la checkpointul istoric preconditions.** Invalidation `879efe6` și evidence/optional `a438538` cu reader fix `b20f339` sunt comise și acceptate scoped în [registrul CURRENT](p2-bound-predicates.md). Ultima [QA independentă](p2-bound-predicates-evidence/evidence-independent-qa.json):3PG/native PASS121.93s/exit0/drained; [părinte](p2-bound-predicates-evidence/evidence-parent-acceptance.json):16SHA/222artefacte/7bindings, cleanup exact/date păstrate. Full/optional cu required satisfăcute COMPLETE, required-prefix INCOMPLETE; public cached release/receive după Stop și12readeri fără reexecuție. Findings reader/oracle/scheduling remediate/re-reviewuite; nu se reiau aceste felii sau launch audit. Continuarea este **restB06b forme/binding/inventar/calificare M1M2/history/restart**, apoi B06c/m→acceptare P2-inert→P4a-minim; P2-live cere acord separat. Nu porni alt audit, plan, verifier sau owner. Acest handoff proiectează planul §7.1/§8 și registrele existente, fără a extinde criteriile. Snapshotul și unele limitări de mai jos sunt istorice înaintea continuării; Git și registrul CURRENT decid bytes/starea actuală.

### Snapshot și ce nu se reia

- Repo `/home/kali/OmnisAI`, branch `checkpoint/p2-vm-restart-20261011`; baza înaintea acestui handoff: **`8fc6c0f1ffb597103ed6445b72679d1a7e3531f3`**. Citește Git real înainte de lucru. Toate schimbările intenționate sunt comise; singurul untracked observat este `documents/Omnis_Notite_Originale.html`, protejat/neatins. Fără push sau rescriere de istorie.
- **Preconditions finite ACCEPTED_SOURCE_NATIVE_SCOPED:** produs `77d38a1844f0137baa9f654f43892a840ff4c0e8`, acceptare `4a3a1c6`, lecție prerequisite `8fc6c0f`. [Registru CURRENT](p2-bound-predicates.md), [autor](p2-bound-predicates-evidence/preconditions-author.json), [review normativ](p2-bound-predicates-evidence/preconditions-normative-review.json), [security](p2-bound-predicates-evidence/preconditions-security-review.json), [QA independentă](p2-bound-predicates-evidence/preconditions-independent-qa.json). Două APPROVED_SCOPED pe11SHA;315API+61adapter SOURCE/Ruff/mypy/wheels. QA pe `dd82dba4c69dbac409386db766f6abe57947f7ac`: **1PASS/20deselected31.32s, exit0/drained**, refuz real input gol cu delta assignment records/run=0; AIAgent/read1/PURE2 autentic,3receipts/2artifacts, COMPLETE fără PASS funcțional;4readeri/replay/no-rerun/single-consume/post-Stop duplicat receive-only. Parent11SHA+196inputs+78artefacte și cleanup exact/date păstrate.
- **Applicability/UNKNOWN finite acceptate** pe `0aeb328`/`f8b7fd6`, acceptare `af59462`; QA independentă3PASS79.39s/exit0/drained. **Partial return acceptat** pe produs `c8e84a8`, observer-only fix `146749d`, acceptare `e6e91a6`; QA independentă full+partial2PASS49.34s/exit0/drained. Nu redeschide aceste felii numai pentru că s-a schimbat sesiunea. Revalidează numai bytes/call-sites afectate de implementarea următoare.
- **QA-PARTIAL-RETURN-EXECUTION-01 este CLOSED_SCOPED pentru acceptarea curentă**; vechiul RuntimeUnavailable și cauza UNKNOWN rămân istorice. Audit-fanout a fost demonstrat/remediat în fixture, nu atribuit retrospectiv produsului. Pozitivul launch-only nu este acceptare. C10-NATIVE-F01 și findings applicability NORM-F01/F02/SEC01–04 au dispoziții scoped în registru; nu relansa reviewurile lor vechi. N01 LOW/neblocante păstrează motivele/scope-ul din registru; o constatare nouă concretă se adjudecă, nu se ignoră.
- [FAIL-ul preconditions prerequisite](p2-bound-predicates-evidence/preconditions-independent-qa-prerequisite-fail.json) rămâne **1FAIL0.59s/exit1/drained**, SOURCE_PIN_REQUIRED înainte launch. [Restaurarea exact-pin](p2-bound-predicates-evidence/preconditions-source-prerequisite-restored.json) în `dd82dba` și QA distinctă de mai sus închid blocajul curent de prerequisite, nu îl transformă în defect/remediu de produs. Originea dispariției exportului rămâne UNKNOWN.
- La pregătirea handoffului: **zero subagenți live**; nu există rezultat de review/QA de așteptat. Ultimele două fixtures PG proprii și endpointurile/readeri au readback exact de cleanup; PGDATA/logurile păstrate. Nu revendicăm absența globală a serviciilor VM, nu adoptăm fixtures istorice/r1. Exitul nativ −9 păstrat nu dovedește o cauză de produs, Stop graceful sau restart runtime.
- **B06b/G02/P2 sunt PARTIAL/NOT_CLOSED; canonical final NOT_RUN; P4a-minim NOT_IMPLEMENTED.** Canonicalul `ff095af` este istoric, nu PASS pe produsul actual. SOURCE_HOST_NOT_INSTALLED și document-preparation prerequisite double rămân limite; readerul istoric installed, restart runtime și inferența sunt dovezi distincte.

### Delta celor opt criterii §7.1 — nu alt backlog

| Criteriu canonic | Ce se reutilizează în scope | Ce trebuie închis în continuare |
|---|---|---|
| Transport/izolare B05/H01/H02 | B05/slot/bootstrap și probele H01/H02 acceptate la frontierele lor | Numai lipsurile la consumerul extins: reverse/EOF/timeout/backpressure/unknown method, no personal grants și drain owned; synthetic peer nu este nativ. Nu recertificare B05 neschimbat |
| Catalog/publicare B06a/b | Seed real calificat/Publish exact/CAS, snapshot pinned NO_MODEL și readback/replay acceptate | Recalifică fixture-ul afectat de compiler/evaluator/pin nou; nu transfera calificări vechi și nu introduce alt demo/editor/catalog larg |
| Brief/composer/metodă B06b | Read/PURE/receipts reale, full+partial, applicability/preconditions/invalidation finite, UNKNOWN păstrat; evidence/optional pe same-attempt artifacts și required closure acceptate scoped; outcomes fără oracle BLOCKED | Restul cerințelor/stărilor/motivelor/gaps și formelor refs/slots/StepOutput/predicate contractate neacoperite rămâne explicit deschis. Refuzul prudent existent nu înseamnă funcție implementată. SOURCE preflight și checker nu substituie consumerul real; nu relansa cazurile acceptate neafectate |
| Binding/inventar H03–H05 | Mapping și inventar native probate în subseturile documentate | Root/child/batch/attempt distincte, mapping comis pre-access, goaluri identice cu identități distincte, inventar efectiv, wrong-identity/observer failure deny; lineage autentic/atomic sau refuz fără acces. Compresia care cere inferență rămâne live, nu pozitiv simulat |
| Rezultat/inbox H06/H07 | Persist→check, replay/reconcile/consum o dată, receive-only post-Stop și cache same-Host acceptate scoped | M1 după M2 aditiv rămâne istoric; input/auth/precondiții invalidate nu primesc calificare curentă. Duplicate/conflict/restart/lost reply și HELD fără wake/execuții/consum dublu; markerii delivered/admitted/turn_completed/consumed distincte. **Restart runtime real și installed historical-reader încă NOT_RUN**; Same-Host cache și legacy producer fresh nu le închid |
| DATA B06c | ModelProjections/decizie DATA, DTO guard final/direct-worker și SDK real NO-IO cu acceptări scoped în registre | Producer/proiecție calificată → decizie DATA exactă → DTO final immutable → guard integral după transform pe consumerul real. Sentinel întreg input/payload/result/error/log; raw/secrete/unknown sensitive/cross-case/bypass refuzate. Refolosește SDK neafectat; probează SDK real NO-IO numai unde schimbarea consumerului o cere. DATA/UUID sintetic nu acordă model; NO_MODEL rămâne pre-client |
| Admission B06m/H08 | Ledger și helpers reserve/mark_sent/settle cu probe PG de contabilitate | **Același caller de produs** → reserve tranzacțional comis → SENT durabil înainte send → protocol inert declarat → receipt/UNKNOWN. Caps calls/output/deadline/VALIDATION; overlap PG observat; Stop reserve/send și veto sink; UNKNOWN după SENT păstrează rezervă, RELEASED numai no-send demonstrat; retry/fallback/aux readmise+contabilizate sau refuzate; cost necunoscut nu devine zero. Nu atomicitate DB/rețea. Native turn/config/purpose și plafon financiar neimplementat/neprobat blochează live, nu amână obligațiile inerte |
| Snapshot final | Reviews/probe scoped și FAIL-uri păstrate | După remediile și QA afectată: reconciliază toate8rânduri cu cod/consumer/evidence/review, adjudecă fiecare finding concret și justifică orice rest live/ulterior din canon; apoi canonical real pe bytes finali și cleanup/readback. Fără PASS global din test count, SKIP sau raport SOURCE |

### Fișiere/callers existente — verifică înainte de editare

- B06b: `api/src/omnis/modules/settings/skill_catalog.py` și `candidate_catalog.py`; `modules/tasks/managed_contract.py`, `managed_composition.py`, `method_checks.py`, `method_checker_identity.py`, `criterion_checks.py`; `modules/runs/managed_admission.py` (`reserve_dispatch`, `_result_check`, `_method_schemas`, `reconcile`); `api/src/omnis/supervisor/native_tasks.py`; adaptor `prompt_bundle.py`/`contract_method.py` și upstream `agent/contract_execution.py` (`run_contract`). Actual producer și preflight **încă refuză** invalidation/evidence forms neimplementate; nu elimina guarduri fără semantica și probele lipsă. Nu crea registru/evaluator general ori pachet SECURITY pentru această completare.
- B06c: `modules/runs/model_projection.py:ModelProjections.prepare/read`; `modules/runs/model_dispatch.py:ModelDispatch.prepare/read` și prepararea/readbackul configurației; `policy/model_context.py`, `model_projection.py`, `ready_model_configuration.py`; adaptor `model_request.py:FinalModelRequest/final_sdk_guard` și `model_admission.py`, plus sinkul direct/worker pin-uit. Trasează definițiile/usages întregului input transformat, nu testa numai helperul.
- B06m: `policy/budgets.py:reserve/mark_sent/release/settle`; `ModelDispatch` și **`NativeTaskOwner` real**. La acest checkpoint, metodele de model ale ownerului sunt preflight/configuration/initialization; acestea nu sunt send. **`api/src/omnis/policy/admission.py` nu există**, deși apare în plan/note istorice. Nu inventa importul; reutilizează seamul potrivit, introducând cod nou numai când callerul necesar îl consumă.
- Matricea M1/M2/qualification este în arhitectură §6.3; metoda/evidence/optional în §9.4–9.5/§9.10. Nu declara un `ResultQualification` sau consumer ca existent numai fiindcă documentul îl numește; tracează implementarea reală. M1 istoric, calificarea curentă și admiterea de lucru nou sunt trei frontiere, nu aceeași stare.
- Pentru DATA/admission citește [registrul integrării](p2-integration-b06cm.md), [guardul final](p2-final-dto-20261011.md), [READY configuration](p2-ready-configuration-20261011.json) și §7.1 CURRENT înainte de a adopta concluzii vechi. Granturile/nonce-urile istorice nu se reutilizează; limita live se separă conform canonului.

### Probe și remedieri — execută doar ce avansează cerința

1. O singură felie: criteriu observabil → producer/caller/sink existent → pozitiv și refuz pe aceeași frontieră. Citește înainte, reproduce RED, fix minimal, GREEN și regresii afectate după ultima editare. Commit mic cu motiv/comenzi/exits/limite/revert; stage paths explicit și `git show/status`. Fără any/ignore global/catch gol/date inventate/dependențe latest.
2. Source-first: teste existente `api/tests/test_c10_bound_predicates.py`, `test_contract_method_producer.py`, `test_contract_method_checks.py`, `test_managed_composition.py` pentru seamul metodologic; model `test_model_projection*.py`, `test_model_admission*.py`, `test_model_budget*.py` pentru seamul lor. API interpreter `api/.venv/bin/python -I -B`, plugin autoload dezactivat, fără variabile Python/pytest ambientale; Ruff/format/mypy din manifest, pe scope afectat. Nu rula toate familiile pentru fiecare fix sau reminder.
3. Review independent pe snapshot exact; **două complementare** la authority/concurrency/Stop/effects/secrets/cross-runtime. Findings concrete trebuie reproduse/adjudecate: remediu minimal, affected checks, re-review delta/call-sites; o listă nouă goală nu șterge findingul vechi. QA independentă pe consumerul real nou/afectat după review, cu fixture și cleanup/readback proprii. Copilul nu comite și nu închide integrarea.
4. PG numai prin `ops/run_test_db_gate.py`/ownerul existent, fixture **nouă**, atestată, UDS/no-network; nu DSN extern/SQLite/r1. Verifică `--help`/choices și wrapperul înainte de efecte. **`test-contract-method-native-pg`, `test-contract-method-pg`, `test-model-projection-pg` NU sunt choices CLI --target la checkpoint**, deși există Make targets. Native folosește ownerul și opt-in explicit; projection cere preflight `installed-origin.json`. Nu inventa un target și nu schimba lifecycle-ul doar pentru selector.
5. Consumerul PG/native existent este `api/tests/test_contract_method_pg.py`; wrapperul scratch `/home/kali/.hermes/cache/scratch/p2-partial-return-pg-selection.py` selectează red/green/applicability/not-applicable/precondition, **nu invalidation**. Adaptează selecția minimă numai odată cu noul test/cerință și verifică argv/collect-only fără launch. Nu rerula precondition acceptat ca primă acțiune. Accounting-only `test-model-budget-pg` nu închide B06m; exercită callerul și overlapul real, nu helpers secvențiale.
6. Preflight prerequisite **înainte de PG/native**: source PIN `/home/kali/.hermes/cache/scratch/contract-method-evidence/pinned`, entry `run_agent.py`; libraries exact din consumerul existent. Restaurare numai commit `ee5ee84a345204a3b1d6ef6ba1ab747e602867b9`, archive SHA `f18177d037fc8012ad9a7bf7e5b4d05f5e0ca63bad9d28e43905389264282c80`. Exportul curent15.208files este atestat în receipt; scratch poate expira. Recuperează exact arhiva/pinul și verifică inventory/original overlay inputs, fără personal runtime substituit, imports prewarmed sau instalare implicită. Logs/fixture/bootstrap/RPC/traceback PG se parsează privat pe allowlist, fără DSN/capability/secrets în tool output ori Git.
7. Native/distribuție schimbată: pin/patch/manifest coerente, parser/reapply/build și inventar/hashes reale; UID non-root trebuie să poată citi. Refolosește referința locală base atestată, nu `FROM sha256:IMAGE_ID` interpretat ca registry. SOURCE/synthetic/copy-installed/native/SDK/live sunt frontiere separate, nu un verdict unic.
8. La FAIL, o investigație bounded a frontierei eșuate: fază/first reason sanitizat/timpi/peer/settlement înainte cleanup, apoi remediu conform mecanismului produs versus fixture. Fără retry până verde/prewarm/măriri arbitrare deadline/grant; SIGTERM/SIGKILL cleanup nu explică eșecul. După două cicluri numai harness fără progres, restrânge reproducerul; nu reseta numărătoarea prin sesiune nouă și nu adăuga verifier/supervisor. Păstrează FAIL/UNCERTAIN/date/loguri și refuză felii dependente peste blocker.
9. Joburile lungi PG/canonical: tracked background cu pinned paths, bounded timeout și exact-session readback; nu foreground timeout care omoară ownerul înainte drain. În final verifică exact daemon/CID/project/network/UDS/host/readeri și receipt family_drained, fără cleanup global/adopție. Documentele: **`/usr/bin/python`**, nu API venv fără markdown; `python scripts/render_docs.py --check`, `python -m unittest discover -s tests/documentation -v`; regenerează HTML la Markdown normativ. În această sesiune72docs/46development PASS, nu canonical de produs.
10. **Gate final de integrare/fază**, după toate remedierile și QA afectată, pe bytes finali:

```sh
PATH=/home/kali/.local/share/omnis-toolchains/bin:/usr/bin:/bin TMPDIR=/home/kali/.hermes/cache/scratch make check UV=/home/kali/.local/share/omnis-toolchains/bin/uv
```

Canonicalul standard nu înlocuiește native/projection cu opt-in; înregistrează separat probele cerute. Modificarea produsului după gate cere affected checks și gate final pe snapshotul integrat; Markdown-only/reminder nu cere recertificarea produsului neschimbat. Închide P2-inert numai cu toate obligațiile inerte probate/reviewuite; altfel exact BLOCKED/NOT_RUN și următoarea acțiune, nu „faza2 gata”.

### După P2-inert: P4a-minim și limita live

Settings utilizabil pe build/API/DB proprii: catalog read-only și pachete reviewed/published immutable; selecție explicită/save→readback/reload; runtime/dependency readiness; requested/effective cu fallback reason; REQUIRED nesuportat blochează, fără hot-swap sub copii activi; configured/authenticated/reachable/inference_ready și methodology-only/benchmark-validated distincte. Fără cont, indisponibilitate corectă; fără provider discovery/pricing/refresh/inferență, fără editor complet preventiv. QA browser real: salvare/reload/readback/stări/erori/tastatură/focus; testele tehnice nu aprobă estetica.

B06j/Jev păstrează alocarea §8: typed questions/DecisionReceipt și sentinel inert la consumerul său; shadow/live/advisory nu se simulează. După P4a-minim, **oprește pentru acord cont/provider/model/date/buget și run/selection/manifest noi**. Fără warm NO_MODEL, ținte/P3, profiluri/r1, credentiale personale sau push. Acceptarea P2-inert/Settings nu închide G02-live; „faza2 completă” fără această probă live separată ar fi fals.

### Prompt scurt actual pentru sesiunea nouă

```text
Continuă implementarea OmnisAI în /home/kali/OmnisAI, cu cod minimal,
până la acceptarea P2-inert și livrarea P4a-minim, în ordinea canonică.
Citește CURRENT din documents/verification/p2-c10-session-handoff-20261012.md,
p2-bound-predicates.md și implementation-status.md; Git real, AGENTS,
CONTRIBUTING, README, plan §7.1/§8 și arhitectura relevantă feliei.
Baza înaintea handoffului este 8fc6c0f pe checkpoint/p2-vm-restart-20261011;
HEAD real poate include commitul documentar al handoffului. Păstrează toate
schimbările preexistente și documents/Omnis_Notite_Originale.html neatins.
Partial return, applicability/UNKNOWN finite și preconditions finite sunt
acceptate scoped: nu relua auditul launch sau probele lor neschimbate.
Invalidation și evidence/optional au avansat și sunt acceptate scoped;
continuă restB06b (forme, binding/inventar/lineage, M1/M2, restart/history), B06c și
callerul B06m reserve COMIS→SENT durabil→protocol inert→receipt/UNKNOWN.
Folosește delta celor8criterii și toate limitele/probele din CURRENT.
Nu presupune policy/admission.py existent; verifică definiții/usages,
runner choices/opt-in și source/library prerequisites înainte de efecte.
RED→fix minimal→GREEN; reviews independente exact-snapshot, două la
authority/Stop/concurrency/effects/secrets/cross-runtime; QA consumer real,
cleanup exact/date păstrate, commituri mici și re-review findings concrete.
Continuă următoarea felie inertă admisă fără aprobare cosmetică; nu alt audit,
verifier, owner, demo sau framework. După două cicluri numai harness,
restrânge frontiera, fără weakening/retry orb/prewarm/deadline widening.
După toate remedierile și QA afectată rulează canonicalul real pe bytes finali,
nu transforma SOURCE/synthetic/installed/native/SDK sau SKIP în PASS global.
P4a-minim numai după P2-inert, cu browser pe build/API/DB proprii.
După Settings oprește și cere acordul separat cont/provider/model/date/buget
și run/selection/manifest noi pentru P2-live; fără cont/inferență/target/P3/r1/
global/push implicit. Predare română scurtă: commituri, probe, blockers și
matricea globală. Nu te opri la diagnostic/helper când consumerul este disponibil.
```

## Istoric — acceptare C10 integrată înainte de extensiile ulterioare

Candidatul8ea28b2 **este integrat** în `25395bd`, după două re-reviewuri complete APPROVED_SCOPED; C10-NATIVE-F01 închis. Remediile quality/cold legacy/fixture sunt comise separat în `9a49d15`/`46589bf`/`d3a176b`. [Registrul actual și toate dispozițiile](p2-bound-predicates.md), [canonical final versionat](p2-bound-predicates-canonical-pass.json) și [harta](implementation-status.md) înlocuiesc punctul de reluare de mai jos. Canonical3 pe `ff095af`: exit0/drained,969hashes stabile, cleanup exact/date păstrate; C10 integral/B06b/G02/P2 rămân deschise. Observația C10-LEGACY-SEC-N01 este LOW/neblocantă/deferred, nu un blocker ignorat. Git real decide HEAD-ul curent, fără SHA auto-referențial inventat.

**Prompt istoric — înlocuit de CURRENT și promptul scurt de mai sus:**

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

## Prompt scurt istoric — nu punctul actual de reluare

> Continuă OmnisAI din checkpointul local existent. Citește întâi `documents/verification/p2-c10-session-handoff-20261012.md` și `p2-bound-predicates-checkpoint.json`, apoi Git real/AGENTS/README/harta și numai secțiunile relevante din plan/arhitectură. C10 final este comis în `work/p2-bound-predicates-nativefix` la `8ea28b2`, **neintegrat**, cu2PG/native PASS și review delta încă NOT_RUN. Începe cu re-review focalizat C10-NATIVE-F01 pe cele6 fișiere, nu audit/restart/tests redundante. Păstrează aprobările SOURCE F01–F04 în scope, FAIL-urile și limitele legacy. Integrează exact17paths numai după acceptare, verifică gate-ul real la frontiera integrată, apoi restB06b→B06c/B06m→P4a-minim conform §7.1; live separat. Un singur autor pe worktree, subagenți fresh, TDD și commituri mici. Nu atinge HTML-ul protejat, profiluri/r1/daemon, conturi/model/target/push. Nu inventa breadth sau verdicturi și nu te opri la helper/harness când consumerul de produs este disponibil. Predare scurtă în română cu implementare/probe/review separate și matricea globală.
