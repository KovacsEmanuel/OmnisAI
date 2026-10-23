# R1 — quiescence unlocked prerequisite, independent read-only review

**Verdict: APPROVED_PREREQUISITE_SOURCE_SCOPED. Findings: none. NOT T1 acceptance, NOT integration approval, NOT independent PostgreSQL consumer QA.**

Requirement → consumer → risk → decision: committed closed-generation barrier → existing supervisor quiesce and CLI Stop/finalize/readback → SQL self-deadlock or stale quiescence acknowledgement → admit only this source prerequisite to the parent's two-review adjudication; the first independent PG consumer probe still waits for both reviews and separate admission.

## Frozen identity and scope

- Candidate: `/home/kali/.hermes/cache/scratch/ot1-0zxf62th/runtime-src`, branch `impl/api-key-runtime-t1-model`, clean.
- Base: `a20cc59faccea51fe8ea440325a7223bdd8852d2`.
- HEAD: `1dce3cd38a4555be221826c43bc2f22e6a830c17`.
- Tree: `e9ebc373ce88968ef277b552595f9fe2c12ba504`.
- Commits: `6d98fa3a10bf467054bab78e0dd622d5b28747fe`, `1dce3cd38a4555be221826c43bc2f22e6a830c17`.
- Freeze: `core-evidence/wip-freeze.json`, SHA256 `f76cf34686cd461853eeef094ee0dbc3f85ade6919ba08581a998563e98bc1e3`; all four file identities below matched the on-disk files and committed blobs.

| File | Git blob | SHA256 |
|---|---|---|
| `api/src/omnis/modules/instance/service.py` | `df0d3b4437d13fc800cef32d730011ff622f608f` | `9412e591b8bd40fec9d1e3e7de7507eefcd89130cfab078b463eac77f807d551` |
| `api/tests/test_instance.py` | `9ff7a9239869645432c798b899d27c1becc5ec27` | `b1a339de9d82bf0b676358acd4479c846dbae9a301b0ecf0c8282d3ae028ed04` |
| `Makefile` | `cdd1803fa674695ea4da2946ce02994b2a7d1832` | `d8cc4b21d9545d36a1c276eb649eb84dc8723ab73094c815651b24de6589ef98` |
| `ops/run_test_db_gate.py` | `f13121588fddfbc13449bc10bbabac07c766dca9` | `86991514b2f14053dfdf9ef787bd39bfdf063454aa9fb55d901e86143378d7ef` |

The diff is exactly four files, 98 insertions / 21 deletions. No schema, vault, DTO/API, UI, release or dependency changes. Shared checkout `/home/kali/OmnisAI` was read only: observed HEAD `d3eebd265161967a778c41e6bcf28a6e5c14d6b1`, branch `checkpoint/p2-batch2-pause-20261015`, protected untracked `documents/Omnis_Notite_Originale.html` preserved. The supplied shorthand “main” is not the observed branch name; no branch was switched.

## Compliance, ordering and actual callers

1. **Commit/unlock before settlement:** `service.py:270–295` uses `engine.begin()` and locks instance then lease. `quiesce:489–500` validates a live owner, reads a closed shutdown's generation and command, then exits that transaction before calling drain. An uncommitted shutdown cannot slip through the row lock. A transaction-exit/commit failure cannot proceed to drain. Open/no-shutdown remains an owner-validated no-op.
2. **No self-held SQL locks across drain:** the drain call is outside both `_locked()` contexts, retaining the existing 2.5-second budget. Settlement can re-enter the same instance/lease rows. This is the concrete prerequisite, not proof of an implemented SystemOperation sender. New PG test `test_instance.py:202–224` performs that re-entry and commits the settlement marker.
3. **Fresh authority and exact closed scope:** `service.py:505–509` reacquires the same lock order, obtains fresh records, and checks owner UUID, epoch, live DB-clock lease, captured generation, closed admission and captured shutdown identity. Takeover cannot retain the same epoch; reopening increments generation and clears shutdown/quiescence. The second transaction holds both authority rows through the acknowledgement. No hypothetical unrestricted DB writer is needed to justify these checks.
4. **Fail closed on drain failure/cancellation:** false/non-True returns and handled drain errors stop before the second transaction (`497–504`). `CancelledError` is not converted to success or suppressed here, so cancellation during drain cannot reach the UPDATE. Real `RuntimeClient.drain` (`api/src/omnis/supervisor/runtime_client.py:840–850`) requires stop ACK plus observed drained readback; `ProviderSettingsOwner.drain` (`provider_key_service.py:97–103`) rejects pending writers/non-quiescent vault. Neither catches cancellation as successful drain. An explicit cancelled-quiesce PG case is not among the recorded ten; this cancellation conclusion is source-scoped, not newly executed fault evidence.
5. **Post-UPDATE expiry protection retained:** `service.py:510–517` still checks live owner after the UPDATE and before transaction exit. Expiry during an UPDATE/table-lock wait raises and rolls back the acknowledgement. The new target explicitly includes the unchanged real SHARE-table-lock regression `test_control_regressions.py:203–255`; no lease check was removed or weakened.
6. **Open/shutdown/finalize and replay unchanged:** `service.py:365–449,466–487,519–535`. Shutdown records closure transactionally; finalize still requires the expected quiesced generation and rechecks owner after recording. Same-owner reopening still requires restart/new epoch; historical command replay does not mutate a newer generation. Existing `test_instance.py:110–179` covers admission serialization, closure/finalize/restart and historical shutdown replay. `command_readback:886–938` binds committed command identity, expected/result generation, owner epoch and current lifecycle state under the same locks; stale mixed-generation replies remain refusals.
7. **Real Stop path preserved:** `local_control.py:231–269` still dispatches open/shutdown/finalize and then performs command readback. Supervisor startup drains inherited shutdown before exposing LocalControl (`__main__.py:136–153`); its existing heartbeat→quiesce loop remains (`180–197`). CLI `omnis_cli/stop.py:715–771` obtains shutdown readback, polls exact instance/generation/shutdown/epoch, finalizes only after quiescence, verifies the final reply and persists/reads the local and DB receipt before Stop inventory/arm. A concurrent actual reopen requires prior quiescence/finalize and a newer epoch, so an older drain cannot acknowledge it. No alternate lifecycle writer or SDK experiment is being ratified.

## Tests/target oracle and reused recorded evidence

All evidence below is historical developer execution read back from the owned root; **R1 ran no tests, PG, OCI, service, provider or installed consumer**.

- New `test_instance.py:184–247`: settlement, false drain, takeover, generation mismatch and expiry. Positive reads one committed settlement marker and the closed-generation acknowledgement; negative controls require the exact conflict reason, one settlement marker and NULL quiescence. The direct generation/expiry mutations are fault injections, not claims about unrestricted production writers. The actual lifecycle caller constraints were reviewed separately above.
- Original focused RED: `core-evidence/drain-focused-red.log` wrapper exit2; original `core-tmp/db-4acc01becb22443d/gate.log` has **4 failed / 4 passed, 24.88s**, settlement/refusal/takeover/generation, with statement cancellation while trying to re-enter the locked authority row. Intermediate GREEN: `db-db0f55732d864a3b/gate.log`, **8 passed / 18.07s**, wrapper exit0. The later expiry case and post-UPDATE regression account for the final target's expansion.
- Final focused PG: `core-evidence/drain-final-pg.log`, wrapper exit0; `core-tmp/db-a618fece220f433a/gate.log`: **10 passed / 25.60s**. Exact recorded inner command: `env -u PYTHONPATH -u MYPYPATH -u PYTEST_ADDOPTS -u PYTEST_PLUGINS api/.venv/bin/python -I -B -m pytest -c api/pyproject.toml api/tests/test_instance.py api/tests/test_control_regressions.py::test_quiesce_owner_expiry_during_update_lock_wait_rolls_back -q --tb=short`.
- Affected settings regression: `core-evidence/settings-regression-pg.log`, wrapper exit0; `core-tmp/db-8abf139cab0b4a05/gate.log`: **36 passed / 24.79s**. Exact recorded inner command: `env -u PYTHONPATH -u MYPYPATH -u PYTEST_ADDOPTS -u PYTEST_PLUGINS api/.venv/bin/python -I -B -m pytest -c api/pyproject.toml api/tests/test_provider_key_settings.py api/tests/test_provider_key_api.py api/tests/test_provider_vault.py -q`. Its existing cancelled-save/successor-writer test (`test_provider_key_settings.py:476–543`) retains NULL quiescence until the writer settles.
- SOURCE runtime-service: `core-evidence/drain-source.log` directly contains **11 passed / 1.63s**; exit0 is recorded in the freeze and second commit. This short log does not embed its launch argv. The first commit's “8” is explicitly corrected by `1dce3cd` and the handoff; it is not reused as the count. The source false-drain/UPDATE oracle is at `test_runtime_service.py:299–340`.
- `make lint-api typecheck-api`: exit0 recorded in freeze/second commit. `final-quality.log` contains only `[][]`, not raw Ruff/mypy output; no claim of independently rerunning or reconstructing those tools.
- Broad original `test-sl04-pg`: `core-evidence/drain-red.log` wrapper **exit124**; original `db-764b9581a8724cbe/gate.log` shows four failures then termination. Handoff records the 240-second limit. Timeout cause remains unobserved. **The focused ten are not a global SL04 PASS.**
- Makefile adds only the dedicated fixture-required target and includes it in existing unsafe `n/t/q/i` flag rejection. Runner change only adds the target choice. Current target argv matches the final recorded inner command; no old target or oracle was replaced.
- Five exact owned fixture identities/retained roots and recorded absent-CID/cleanup flags were read from the freeze and paired with their original gate summaries. No fresh OCI census or cleanup was authorized/performed. This review does not expand those recorded cleanup assertions into a new live observation.

## Review commands, results and limitations

Executed with workdir `/home/kali/OmnisAI`; read-only candidate access used its explicit path:

- `git status --short --branch`, `git diff --stat`, `git rev-parse HEAD` on shared checkout: exit0; pre-existing protected untracked file only.
- `git -C <candidate> status --short --branch`, `rev-parse HEAD HEAD^{tree}`, `diff --stat a20cc59faccea51fe8ea440325a7223bdd8852d2..HEAD`: exit0.
- `git -C <candidate> diff --no-ext-diff --unified=18 a20cc59faccea51fe8ea440325a7223bdd8852d2..HEAD -- Makefile api/src/omnis/modules/instance/service.py api/tests/test_instance.py ops/run_test_db_gate.py`: exit0.
- Read-only Python `pathlib`/`ast` source/caller extraction and `json`/`hashlib` freeze-file comparison: exit0. Read README CURRENT, CONTRIBUTING, status summary, team-slice, handoff, changed code and actual affected callers; reviewed the required PG original gate summaries rather than auditing unrelated logs.
- `git -C <candidate> diff --check a20cc59faccea51fe8ea440325a7223bdd8852d2..HEAD`: exit0.
- Final `git -C <candidate> status --porcelain`: exit0, empty; `rev-parse HEAD HEAD^{tree}`: exit0, frozen HEAD/tree unchanged.
- `git -C <candidate> show -s --format=full <each of the two candidate commits>`: exit0; historical source-count correction confirmed.

Two broad read outputs were display-truncated; the relevant omitted caller/cancellation/readback sections were then read in a bounded extraction. No product code, test, harness, dependencies, profile, Q root or port was written/touched. The sole created file is this requested original report, outside Git; no commit was made. Reticle NOT_APPLICABLE; Chisel BLOCKED_NO_GO.

## Handoff

Concrete findings in requested `{severity, file:line, reproducer, violated criterion, minremedy}` schema: **[]**. No unsupported theoretical-writer finding or stylistic remediation is requested. Parent owns reproduction/adjudication, the complementary review, later consumer-QA admission and integration.

SystemOperation/model/outcome/API/relay vertical, SDK guard-double experiment, wheel/bundle/installed QA, provider live, canonical/global SL04 and historical-reader breadth are outside this approval. Existing Settings/focus acceptances are neither reopened nor promoted by it.

Skipped: test reruns, direct cancelled-quiesce fault execution and all external effects; only the required owned evidence was read. Risk: SOURCE prerequisite approval does not establish a production sender, an independent PG consumer PASS or T1 completion.
