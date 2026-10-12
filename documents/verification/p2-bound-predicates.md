# B06b / C10 — predicate calificate pentru metoda records

## Contract și frontieră

Aceasta este evidența unei felii din plan §7.1/B06b și arhitectură §9.5/§9.10, nu un plan nou și nu închiderea integrală C10/B06b/G02/P2. Intrare: [handofful din 12 octombrie](p2-c10-session-handoff-20261012.md) și [checkpointul istoric](p2-bound-predicates-checkpoint.json), păstrate nemodificate la frontiera lor.

Rezultatul urmărit: seedul records publicat produce trei `done_when` și un `return_when` calificate per BoundProcedure; copilul real citește inputul și execută două PURE, iar backendul verifică independent predicatele/receipts înainte de MethodCheck COMPLETE. Un `return_when` satisfăcut nu poate elimina un `done_when` lipsă. MethodCheck COMPLETE nu acordă PASS funcțional fără oracle/controls trusted.

Scope de integrare: exact cele **17 paths** și hashes din checkpoint, diferența finală `d7a51f3adc04be57fe528f6e14425111d3615144..8ea28b2794912726428fbc3cac6f6d18269be454`. Non-obiective: early partial return, forme noi/inputuri suplimentare, critic AI, alt owner/engine/fixture framework, schema/migrație, model/provider/target, rollout/r1/profiluri/global/push.

## Integrare și adjudecare

- Principal la intrare: `097243d227b8ed5765efa6a52c2c7c2651f03b49`, branch `checkpoint/p2-vm-restart-20261011`. Singurul untracked preexistent este HTML-ul protejat; SHA `783c5b8dc3f4c00b0e3d3267560bc9a5abedeb4fab44f96eb07718a545b9c79f`, neschimbat la integrare.
- Produs integrat și comis: **`25395bdd0dbeab83afb7894182b7fe88202da104`**. Părintele a comparat inventarul și cele17 SHA înainte/după transfer și în indexul exact. Nicio schimbare a acestor paths în principal între baza produsului și intrare; transferul s-a făcut prin diff Git, nu reconstruire din output redacted.
- Istoria candidatului `5fac42e` → `2ca0477` → `8ea28b2` rămâne pe branches/worktrees originale. Nu au fost importate serial checkpointurile defecte și nu s-a rescris istoria.
- Două reviewuri complementare focalizate pe **aceiași bytes `8ea28b2`** aprobă C10-NATIVE-F01; părintele le-a citit integral, verificat hashes/snapshotul și acceptat numai scope-ul lor. Rapoartele complete sunt versionate mai jos, nu numai în scratch.

| Finding | Dispoziție a părintelui | Dovadă / limită |
|---|---|---|
| C10-NORM-F01 / C10-SEC-F01 | CLOSED_SOURCE_SCOPED păstrat | Closure current obligatorie / legacy explicit zero-only, bytes aprobați pe2ca0477 neschimbați |
| C10-SEC-F02 | CLOSED_SOURCE_SCOPED păstrat | Toate SchemaRefs/tipurile validate înainte de equality; fără credit suplimentar de autentificare |
| C10-SEC-F03 | CLOSED_SOURCE_SCOPED păstrat | Step/Key/existență înainte de lookup și constructor allocation |
| C10-SEC-F04 | CLOSED_SOURCE_SCOPED păstrat | Descriptor v2 closure13 și perechi istorice exacte receive-only + regeneration/equality; nu installed historical reader |
| **C10-NATIVE-F01** | **CLOSED_SCOPED / APPROVED_SCOPED** | Guard → assignment strict pe bytes constructor-owned → strict `expanded_payload` cu pool/ref exact → bundle retenut la callerul real `task_result`; current/legacy717, compact/inline |

Reviewurile originale SOURCE pe2ca0477 sunt [normativ](p2-bound-predicates-evidence/normative-source-rereview.json) și [security](p2-bound-predicates-evidence/security-source-rereview.json). Verdictul CHANGES_REQUESTED de atunci rămâne istoric pentru callerul vechi, nu este șters.

Reviewuri finale:

- [Normativ/comportament](p2-bound-predicates-evidence/nativefix-normative-final-review.json), SHA `15fd6485f5ec46e5d48eb6ba88d9bfe4e0f6598c3a244c1b24b9216ca4f2e247`: APPROVED_SCOPED, zero findings noi, patru regresii SOURCE independente PASS0.86s/exit0. State holders sintetice, nu autentificare nativă.
- [Input/failure/distribuție](p2-bound-predicates-evidence/nativefix-security-distribution-final-review.json), SHA `5cfe1861013a7e107afc782ecbc09f5a848b0387c600906afe554121e9383949`: APPROVED_SCOPED, zero findings noi,14negative/no-effect/no-retry și2teste build PASS; reaplicare efectivă a patchurilor pe exportul stock pinned,15/15 SHA și AST PASS. Exportul original nemodificat; nu build OCI/installed.

Composerul rămâne `4a3606b8e0354bceb8066f6de536932ee420d1147aa9311084ceafb4afbea850`, checkerul `managed.contract-pure.v2`, closure13 digest `388fe9da680951249202045b10e10245d42352a0c194413d221d647b54a085db`. Assignment65536, wire/context/output32768, deadline4.5s și execution guard3s/input original sunt păstrate.

## Verificare pe integrarea exactă

În `/home/kali/OmnisAI`, după transferul celor17 bytes și fără editări de produs/teste ulterioare:

1. `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 api/.venv/bin/python -I -B -m pytest -p pytest_asyncio.plugin -p no:cacheprovider -c api/pyproject.toml api/tests/test_assignment_compact.py api/tests/test_contract_method_checks.py api/tests/test_c10_bound_predicates.py -q --tb=line` → **135 PASS9.49s/exit0**.
2. Același interpreter/plugin/no-cache/config, cu `-o 'pythonpath=/home/kali/OmnisAI/api/src /home/kali/OmnisAI/integrations/hermes/src /home/kali/OmnisAI/integrations/hermes/tests /home/kali/OmnisAI/integrations/hermes/upstream/managed-source'`, pentru `integrations/hermes/tests/test_contract_method.py integrations/hermes/tests/test_managed_build.py -q --tb=line` → **21 PASS0.54s/exit0**.
3. `git diff --check` și `git diff --cached --check` → exit0; inventar staged17 exact, SHA identice candidatului; scan explicit pentru private-key/live-token markers fără match. `git show --stat --oneline HEAD` și status confirmă commitul și HTML-ul neadoptat.

### Probe reale existente, refolosite fără rerun redundant

Checkpointul păstrează două cazuri PG/native autentice **2PASS56.81s/exit0/family_drained=true** pe exact acești bytes: AIAgent/RuntimeHost/NativePeer/RuntimeClient/owner reale, read1/PURE2/result/check/outcomes/inbox/consum și8readeri CLI noi fără reexecuție. Current are trei predicate SATISFIED; legacy717 are zero predicate explicit. Ambele au MethodCheck COMPLETE, două outcomes BLOCKED cu reason/gaps oracle/controls indisponibile, inbox1/consumed1 și admitted0/turn_completed0. Document preparation este prerequisite double declarat; aceste probe sunt SOURCE_HOST_NOT_INSTALLED, nu Brain turn sau installed OCI.

Legacy717 este producer fresh cu composer vechi/checker nou, **nu** reader autentic al unui record/checker vechi instalat imuabil. Exit nativ-9 este teardown bounded, nu Stop graceful universal. Date/loguri păstrate și readbackul cleanupului propriu sunt în checkpoint; nu cleanup universal al VM.

### Eșecuri și discrepanțe păstrate

- `2ca0477`:2FAIL45.19s/exit1/drained; current RuntimeUnavailable pre-stage rămâne cauza UNKNOWN. Compact KeyError a fost reprodus separat; fixul nu dovedește retroactiv cauza pre-stage.
- Driverul anterior executat accidental prin `runpy` unguarded:gate130/drained/zero cazuri/product NOT_RUN. PASS-ul final este altă încercare.
- C11full-target FAIL302/303 și canonical snapshot5FAILexit2/1491API PASS2FAIL2SKIP rămân.
- Reviewul normativ a avut o încercare precollection cu plugin asyncio încărcat de două ori:exit1/zero teste; aceeași selecție cu autoload dezactivat a trecut4/4, fără schimbare de produs/gate.
- Preflightul părintelui a presupus inițial Playwright Python:metadata absentă/exit1. Manifestul/consumerul real folosesc Playwright Node1.63.0; verificarea corectă și browserul fixat existent au exit0. Nu prerechizit absent al canonicalului.
- Raportul autorului păstrează metadate precommit2ca0477; hashurile frozen și Git real8ea28b2 stabilesc snapshotul. Logurile SOURCE135PASS8.46s/8.39s și raportul135PASS8.81s nu sunt presupuse aceeași execuție. Proba nouă de integrare135PASS9.49s este distinctă.
- Reviewerul normativ a reacționat la un reminder de verificare printr-un helper scratch temporar ulterior raportului. Verificarea acelui JSON/checksum nu este QA de produs, nu modifică bytes aprobați și nu cere alt rerun.

## Frontiera canonical și continuarea

Preflightul real în principal a trecut: API/CLI Python3.13.15, uv0.12.19, Node24.21.0/npm11.19.0, Docker local și imagine PostgreSQL18.6 pinned disponibile, Playwright Node1.63.0/Chromium1243 existente. Lipsa venv-urilor din worktree nu blochează principalul. Prima rulare reală și remediul sunt distincte mai jos; outputul PG privat nu se afișează brut. Eșecul ori un prerechizit real lipsă rămâne FAIL/BLOCKED/NOT_RUN, fără gates slăbite.

### Canonical1 — FAIL păstrat; remediu quality acceptat separat

`PATH=/home/kali/.local/share/omnis-toolchains/bin:/usr/bin:/bin TMPDIR=/home/kali/.hermes/cache/scratch make check UV=/home/kali/.local/share/omnis-toolchains/bin/uv`, proces `proc_98c33787bd32`, pe HEAD **`833381fcc1080cf1f6e4780d3ff7bea01a3d3b86`** → **exit2**, receipt `code=2/family_drained=true`. [Evidența FAIL](p2-bound-predicates-canonical-fail.json) păstrează diagnosticele sanitizate și identity/hash/cleanup;962 fișiere tracked identice pre/post. Docs72/development46 și lint API au trecut; `typecheck-api` a refuzat importurile native C10/C04, iar test-api și gates downstream nu au fost atinse. Containerul/proiectul/rețelele/UDS proprii au fost citite înapoi absente pe daemonul exact; PGDATA/loguri păstrate.

Root cause: `mypy_path` API vedea numai API src/tests, nu sursa adaptorului consumată de noile teste. Canonicalul a emis4 import diagnostics; reproducerul separat `make typecheck-api` a emis5 în3fișiere din cauza importurilor repetate, aceeași clasă de defect, nu aceeași execuție. Adăugarea experimentală a întregului native tests tree a produs erori untyped/module shadowing și a fost respinsă fără scriere în config.

**Remediu `9a49d15838a7ed5c2f649c3f7668a254373e1983`:** adaugă numai source path ancorat `$MYPY_CONFIG_FILE_DIR/../integrations/hermes/src`; păstrează strict/disallow_any, Makefile/dependencies și API source/tests. Expresia existentă test-only `importlib`/Callable pentru `reseal_graph` este reutilizată prin facade-ul tipizat comun, fără import static al arborelui native tests sau no-op/mock/ignore. Source nativ/produs, patch/pins/composer/checker13 nu se schimbă; numai config și trei fișiere de test.

RED nou pe canalul Make real: testul quality de rezoluție import →1FAIL12deselected1.37s, `import-not-found`/`no-any-return`. GREEN după ultima editare: `make lint-api typecheck-api` exit0 pe întreg API src/tests și selecția quality+C04+C10+method+compact **167PASS29.43s/exit0**. Controlul pozitiv importă funcția reală `composer_revision` care întoarce str; negativul schimbă numai annotation→int și cere exact `return-value/error`, nu un failure arbitrar.

[Review focalizat quality](p2-bound-predicates-evidence/canonical-typing-fix-review.json), SHA `347168eddb730799f02c0c64f7ccf822ca0d230553ba2bd6ed2a5ea0f807e671`: **APPROVED_SCOPED** pe cele4hashes comise ulterior în9a49d15;5teste afectate PASS3.89s, întreg API typecheck exit0 și rezoluție din cwd străin către sursa reală. Părintele a citit/verificat raportul și staged bytes. Limita reviewerului `API_PY=-B` este explicită; nu canonicalul complet. Nicio editare de produs/distribuție care să motiveze un nou PG identic sau re-review global.

**Canonical2 pe snapshotul reparat: NOT_RUN la acest checkpoint; urmează rularea reală a aceleiași comenzi.** Canonical1 FAIL nu este șters/promovat de167SOURCE sau review. Aceasta este prima corecție quality a frontierei integrate din această sesiune, nu resetarea ciclurilor anterioare C10 și nu alt harness.

Restul C10/B06b rămâne PARTIAL: early bounded partial return persistent; applicability/preconditions/invalidation/obligații evidence-bearing și unknown checker UNKNOWN; M1/M2/material qualification; formele C04/C11/H07/binding/lineage/inventar încă neacoperite și installed historical reader. Următoarea felie de produs se delimitează pe consumerul existent, cerință→owner→probă, fără alt demo ori framework.

Ordinea rămâne **restB06b → B06c/B06m owner reserve comis→SENT→transport inert/UNKNOWN/Stop/caps/VALIDATION → P4a-minim → P2-live**. Live cere acord separat cont/provider/model/date/buget; fără faza3 înaintea dependențelor canonice. Reticle NOT_APPLICABLE; Chisel BLOCKED_NO_GO.

Rollback: inspectează dependențele și `git revert 25395bdd0dbeab83afb7894182b7fe88202da104`, apoi gate-urile afectate. Nu rescrie refs istorice sau records/checks/DB; Git nu revine asupra serviciilor/datei externe.
