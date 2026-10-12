# Handoff — P2-inert după metoda nativă, 12 octombrie 2026

**ISTORIC — punctul de reluare de mai jos a fost înlocuit de [handofful C10 current](p2-c10-session-handoff-20261012.md).** History, compact, C04 și C11 au fost ulterior integrate scoped; C10 final este WIP comis separat la8ea28b2, cu re-reviewul ultimei delte încă NOT_RUN. Nu relua reviewul1890f68 sau implementarea history din această notă. FAIL-urile și probele de mai jos rămân la snapshoturile lor.

Checkpoint de sesiune, **nu plan nou**. Autoritate: AGENTS.md, README, plan §7.1/§8/§19 și arhitectura relevantă. Status global: [harta](implementation-status.md); dovezi: [registrul metodei](p2-contract-method.md) și [FAIL canonical păstrat](p2-method-canonical-snapshot5-fail.json).

## Punctul de reluare

- Repo `/home/kali/OmnisAI`, branch `checkpoint/p2-vm-restart-20261011`. Produsul metodei este comis; la pregătirea handoffului, HEAD înaintea acestei note este `b20335c`. Citește HEAD/status real, nu presupune SHA-ul commitului acestei note.
- Checkoutul principal nu mai are cod intenționat necomis. Singurul untracked preexistent este **`documents/Omnis_Notite_Originale.html` — protejat, nu atinge/stage/reset**.
- Nu mai sunt subagenți live. Canonicalul și targetul PG afectat s-au încheiat, nu sunt procese de așteptat/reluat prin polling. Nu pretindem că orice serviciu străin al VM este oprit.
- `work/p2-method-history` are checkpoint WIP **`1890f687db9496c191dcc66ab7252f89fe762320`**, bază `36158b378a655e77b17a926e9accfe5b5b619272`, worktree `/home/kali/.hermes/cache/scratch/omnis-p2-method-history`. Unicul fișier modificat/comis: `api/tests/test_contract_method_pg.py`. **NOT_REVIEWED / NOT_INTEGRATED**; nu cherry-pick înainte de review.
- Worktree-ul history păstrează un link owned untracked `api/.venv` către mediul locked API principal; nu îl comite. Codul checkpointului este recuperabil din ref-ul Git chiar dacă scratch expiră.
- Worktree-ul vechi `/home/kali/.hermes/cache/scratch/omnis-p2-contract-method-native`, branch `work/p2-contract-method-native`, derivă din `abac977`; este material de implementare deja integrat și ulterior remediat. Nu îl reimporta sau credita ca snapshot curent.

## Ce funcționează efectiv

| Frontieră | Implementare / dovadă | Review / limită |
|---|---|---|
| Metoda records | Seed calificat/publicat → PG context/input/prepare → owner/client/Host/Peer real → AIAgent/read1/PURE2 → result1/receipts3/artifacts2 → persistare → MethodCheck COMPLETE → inbox/readback/replay | Două reviews snapshot5,47 hashes, APPROVED_SCOPED; QA12 SOURCE PG/native exit0. Nu INSTALLED, inference, tur Brain sau sandbox OS |
| Cleanup IPC | Host închide clienții UDS înainte wait_closed; release întrerupt închide canalul în fence și propagă excepția | RED→GREEN/re-review scoped; nu inventa grant/retry nou |
| Schema | `0012_contract_methods`, SUCCEEDED cere result/check; pins API/CLI/bundle explicite, cold v1–v3 separat | Upgrade PG scoped; nu migrare peste profilul operatorului |
| Componente runtime | `make check-runtime`:422 pytest +6 AST, Ruff/mypy15 exit0 | Gate componentă, nu canonical/P2 PASS |
| Remedii fixtures canonical | v4 pozitive current-grant; v5 unknown; wrapper legacy acceptă și afirmă `method_execution is False` | 19 SOURCE/181 PG exit0 și review independent APPROVED_SCOPED exact2 hashes; produs neschimbat |
| Receive-only/restart WIP | Două scenarii reale SOURCE PG/native: normal și primul final nou după Stop; opt procese CLI readback/reconcile pe aceeași DB după retragerea producerului | Run5:2PASS59.00s, gate/outer0/drained. Parent hash/proof/cleanup readback, dar test/oracle încă NOT_REVIEWED și neintegrat |

Protocolul `omnis-managed-admission-v4` / `ContractAdmission` este mod constructor-owned determinist, distinct de cold NO_MODEL și warm/model. Bindingul comis precede accesul. Backendul nu fabrică succesul; checkerul nu rerulează algoritmii. Catalog owner și supervisor lease owner sunt identități diferite.

Inputul records rămâne **65418 bytes**, sub capul **65536**; deadline-ul nativ **4.5s** nu a fost extins. Inert import exclude helperul stock care activa tool/plugin discovery, păstrând controlul nonmanaged. QA menține același lease real prin heartbeat și oprește renewal înainte de Stop.

## Regresii, FAIL-uri și ce nu este închis

- Canonical `make check UV=/home/kali/.local/share/omnis-toolchains/bin/uv`, proces `proc_85e6150485ed`: **exit2**, test-api **1491 PASS / 2 FAIL / 2 SKIP**, 2199.27s. Failurile sunt exact fixtures unknown-v4 și short-builder keyword; remediate/comise/reviewed, nu șterse din istoric. Gates downstream nu au fost atinse. **Canonical după fixuri NOT_RUN**, deci fără garanție de absență a altor regresii.
- Targetul real afectat `test-managed-admission-pg`, `proc_7b74147a42a7`: **181 PASS147.15s / exit0**, cleanup DB/rețea/socket absente, uncertain=false, date păstrate. SOURCE transport19/Ruff/mypy2 exit0; acesta nu înlocuiește canonicalul.
- Blocantele confirmate N1-F01 overflow, N1-F02 host v4, SEC3-F01 interrupted authority stream și host idle-UDS teardown au RED→GREEN și re-review scoped. Nu există blocker de produs rămas **confirmat în tracerul records acceptat**; restul obligațiilor neacoperite nu devin acceptate prin asta.
- În checkpointul history, prima primire este final autentic după SHUTDOWN real, înainte de prima persistare: HELD, delivered=true, admitted/turn_completed/domain_result_consumed=false. Instanța inertă normală avea deja admission_closed, deci și controlul normal este HELD; nu atribui un tur sau grant model.
- Restartul history este readerul persistent CLI în procese noi, **nu runtime restart/crash-cut/lost-reply**. Native producer este retras înainte de comparația byte-exact a observerului. Exit nativ -9 este teardownul bounded existent, nu exit graceful sau dovadă de Stop fizic universal.
- History run1 no-env/no-DB; run2 alias Python refuzat; run3 oracle RECEIVED greșit pentru CLOSED; run4 producer viu modifica journalul în timpul readbackului. Toate rămân FAIL-uri păstrate; run5 nu le promovează retroactiv. Părintele a citit cleanupul runnerului și a verificat proaspăt toate patru proiectele proprii fără CID.
- B06b complet: C04/nonempty CriterionBinding/CriterionOutcome/done_when/return_when, predicate calificate, M1/M2, lost-reply și formele încă neacoperite din C01–C12/§7.1. History ar avansa numai first-late-held/restart receive-only după review/integrare. INSTALLED/Brain/G02/P2 sunt deschise.
- B06c/B06m reserve→SENT→transport inert/UNKNOWN, caps/Stop/concurență/VALIDATION/retry sunt încă obligații de produs. Settings P4a-minim nu a fost implementat în această sesiune.

## Ordinea continuării — păstrează mandatul existent

1. ORIENT: Git/status în principal și worktree, AGENTS/README/harta/această notă; încarcă `omnis-project-status`, `omnis-delivery`, `omnis-review-qa`, `omnis-hermes-runtime`, `hermes-agent` și skills API/TDD relevante. Fără alt audit general, rerun P0/P1 neschimbat sau alt input demo.
2. Review independent exact pe checkpointul history `1890f68`, un singur test: primul final autentic după Stop înainte de persistare; replay/readback/reconcile prin CLI în procese noi, alias census fără PURE/handler/constructor nou; marker counts/idempotency; no-authority Stop negatives; bounded cleanup și păstrarea aserțiunilor originale. Nu transfera reviewurile snapshot5 către testul nou. Pentru findings blocante: reproducer minimal → fix → gate afectat după ultima editare → re-review focalizat; nu încă un verifier-framework.
3. Numai după review și verificarea neafectării produsului, integrează byte-exact acest unic test din branchul WIP și comite. Rerulează real PG/native dacă bytes relevanți se schimbă; păstrează limitele SOURCE/INSTALLED. Actualizează numai statusurile afectate.
4. Continuă restul B06b și B06c/B06m în ordinea planului §7.1, reutilizând store/binding/registry/projection/ledger/owner existente, în felii mici comise. Nu te opri la helper/DTO/preflight și nu lărgi input/harness fără avansarea criteriului de produs.
5. După închiderea P2-inert, strict P4a-minim: selecție explicită/catalog read-only/save→readback/stări configured/authenticated/reachable/inference_ready distincte. Apoi canonicalul real pe snapshotul final integrat, cleanup/readback și status global.
6. Provider/cont/model/date/buget se aleg explicit numai pentru P2-live, sau dacă apare înainte o decizie concretă ce cere acces extern. Nu folosi sesiunea/credentialele personale și nu încălzi un NO_MODEL.

## Commituri și artefacte de recuperare

Principal: `35ff2f4` UDS exit; `381c394` schema/pins; `fb97c8e` metoda nativă/inbox; `eab97de` adjudecare scoped; `36158b3` lecții runtime skill0.1.7; `9a9bdcf` FAIL canonical; `02e510f` unknown/current v4 tests; `b20335c` legacy clock wrapper. **Fără push**. Handofful/statusul au propriul commit ulterior, citește Git.

Scratch (poate expira; concluziile de mai sus și codul sunt în Git):

- `/home/kali/.hermes/cache/scratch/contract-method-evidence/review-snapshot5.json`, `review-security5.json`, `review-normative5.json`.
- În același director: `native-pg-green12.log`, `runtime-integrated5.log`, `canonical-snapshot5.log`, `canonical-fixtures-green-pg.log`, `canonical-fixtures-review.json`, `canonical-fixtures-review-result.json`.
- `/home/kali/.hermes/cache/scratch/p2-method-history-qa.json` și `p2-method-history-driver.py`; driver SHA256 `289c0d364170989a0ba85e43411b74090d8d6695dd8e7a1068506892bd1dd86f`.
- History test SHA256 `3da10a75d1adfc1b5b6aef035edd3f8b74a7013520758812ee48e29a234dae11`. Full report conține cele două proof hashes, run dispositions și referințele private per-fixture.
- Interpreter API `/home/kali/OmnisAI/api/.venv/bin/python -I -B`, Python3.13; uv `/home/kali/.local/share/omnis-toolchains/bin/uv`. Docs folosesc Pythonul existent din `/usr/bin`, nu venv API fără Markdown.
- Upstream pin `ee5ee84a345204a3b1d6ef6ba1ab747e602867b9`, SOURCE export `/home/kali/.hermes/cache/scratch/contract-method-evidence/pinned`; bibliotecile immutable din test trebuie să existe/readable înainte de QA. Testul nu descarcă/instalează. Dacă scratch a expirat, recuperează explicit pinul și prerequisites în scope nou, nu pretinde că probele au rerulat.
- QA autentic existent: `ops/run_test_db_gate.py:prove_private_fixture("test-contract-method-native-pg", pinned_uv, 600)` cu opt-in `OMNIS_CONTRACT_METHOD_NATIVE_PG=1`; folosește runnerul/handlers/owned fixture, nu DSN extern sau profilul r1. Driverul worktree face doar lookup read-only al mediilor locked pentru stock preflight, apoi restabilește root-ul privat.

Nu afișa raw `runtime.boot`, capability, DSN sau traceback PG; parsează privat numai câmpuri nonsensibile. Nu șterge datele/logurile, nu reseta/stash modificări străine, nu adopta/reporni r1, nu modifica profiluri sau daemon global, nu trafic target/LLM/rollout/push implicit. Istoria FAIL/UNCERTAIN și countul ciclurilor QA se păstrează între sesiuni.
