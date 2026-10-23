# R2 — unlocked quiescence, exact prerequisite review

**Verdict: APPROVED_PREREQUISITE_SOURCE_SCOPED.** No confirmed blocking defect found in the four-file delta or the affected active caller. This is not T1 acceptance, a production-model Stop proof, or independent PostgreSQL consumer QA. Parent adjudication and the independent real-PG consumer remain required.

## Snapshot and scope

- Checkout: `/home/kali/.hermes/cache/scratch/ot1-0zxf62th/runtime-src`.
- Base: `a20cc59faccea51fe8ea440325a7223bdd8852d2`.
- HEAD: `1dce3cd38a4555be221826c43bc2f22e6a830c17`.
- Tree: `e9ebc373ce88968ef277b552595f9fe2c12ba504`.
- Clean before and after review. Exactly four paths differ from base. Read delta and necessary surrounding lifecycle/owner/fixture definitions; no product edits or commits.
- Manifest and handoff: `core-evidence/wip-freeze.json`, `core-evidence/handoff.md` under the enclosing scratch root.

Independently checked Git blob identities and SHA256 of all four working files against that manifest:

| Path | Git blob | SHA256 |
|---|---|---|
| `Makefile` | `cdd1803fa674695ea4da2946ce02994b2a7d1832` | `d8cc4b21d9545d36a1c276eb649eb84dc8723ab73094c815651b24de6589ef98` |
| `api/src/omnis/modules/instance/service.py` | `df0d3b4437d13fc800cef32d730011ff622f608f` | `9412e591b8bd40fec9d1e3e7de7507eefcd89130cfab078b463eac77f807d551` |
| `api/tests/test_instance.py` | `9ff7a9239869645432c798b899d27c1becc5ec27` | `b1a339de9d82bf0b676358acd4479c846dbae9a301b0ecf0c8282d3ae028ed04` |
| `ops/run_test_db_gate.py` | `f13121588fddfbc13449bc10bbabac07c766dca9` | `86991514b2f14053dfdf9ef787bd39bfdf063454aa9fb55d901e86143378d7ef` |

## Findings

**Confirmed blocking findings: none.** No new owner/reservation/framework is justified by the affected active caller.

### Authority window and actual callback ownership

- `service.py:489–517`: the first instance→lease transaction checks live owner and captures a closed shutdown generation. The drain begins after transaction exit; settlement is no longer blocked by those row locks. The second transaction rechecks current owner/epoch/DB expiry, exact generation, closed admission and shutdown command before UPDATE, then DB expiry again after UPDATE. An exception from the latter check escapes `engine.begin()` and rolls back the receipt.
- Takeover is possible after expiry/release while draining, but is not permission to reopen. `acquire:329–344` refuses a live owner and never opens; `open:422–448` requires closed-generation quiescence, FINALIZE and a strictly later epoch, plus the stop-fence check. A first, still-unacknowledged drain cannot bootstrap a new generation through these methods. Same-owner reopen after finalization is refused. Historical OPEN replay returns its old result without opening anything.
- Repeated quiescence is serialized in the actual supervisor heartbeat loop (`supervisor/__main__.py:179–197`), not exposed as another concurrent LocalControl command. Startup drains before exposing LocalControl (`:136–145`). A concurrent/stale attempt cannot publish a receipt for a different generation/owner. If a prior receipt already permits a later finalized restart, this does not grant an old callback authority over new work.
- Active API-key configuration binds `runtime_drain` to the **process-local** `ProviderSettingsOwner.drain` (`supervisor/__main__.py:79–92`). It waits for that owner's tracked filesystem tasks and checks the cross-process pending-write flock (`provider_key_service.py:71–103`; `provider_vault.py:121–132`); it does not issue new model/filesystem credential mutations. A stale owner finishing this observer does not write another owner's settings.
- Actual Save/Revoke/selection mutation reaches `_vault_write` only inside `service.admission` (`provider_key_service.py:234–275`). Closed admission/shutdown therefore prevents a queued or new command from registering a new credential writer during the unlocked drain. An already-running uncancellable filesystem write retains its independently owned pending descriptor; even a rolled-back/cancelled DB caller cannot make that physical worker disappear from quiescence detection. The vault comment claiming the check is called under a DB fence is no longer literally true; the durable closed state is the applicable admission barrier here. That comment is not an extra lock/authority guarantee.
- Necessary legacy caller definitions were inspected only to identify the seam: `RuntimeClient.drain:840–850` sends Stop and reads drained state; `drain_model_test` first joins the process-owned task via `close_model_test:56–62`. Native runtime is inactive in the admitted T1 configuration and was not re-audited or executed. These definitions do not prove safety of the absent T1 model sender or arbitrary future callbacks.

### Failure, cancellation and physical Stop

- False/non-True drain results and the listed callback failures refuse with SHUTDOWN_INCOMPLETE before receipt UPDATE. Uncaught exceptions and external cancellation also escape before ACK; cancellation is not converted into success. An asyncio timeout remains cooperative, not an OS hard-kill guarantee.
- A committed closed generation persists on drain failure. The supervisor exits its serving scope on failure and its finally path drains before release (`supervisor/__main__.py:215–261`); no quiescence/FINALIZE/STOPPED is inferred from that exit alone.
- `finalize:519–535` requires exact closed-generation quiescence. CLI Stop polls that generation, verifies FINALIZE and epoch, obtains the Stop grant, executes owned teardown, verifies physical completion, then publishes STOPPED (`cli/src/omnis_cli/stop.py:733–799`). `_publish_stopped:592–604` repeats completion verification before persisting/readback. The new unlocked interval does not introduce an earlier user-visible STOPPED path.

### Post-UPDATE expiry oracle — explicit proof limitation, not a reproduced product defect

`api/tests/test_control_regressions.py:204–250` still uses a real SHARE table lock, DB-clock expiry, exact LEASE_LOST and a NULL quiescence readback. Production retains the decisive post-UPDATE owner check at `service.py:517`.

However, the test's `checked` event (`:215–220`) fires at **every** owner check, including the new first transaction at `service.py:491`. Consequently `checked.wait()` / `not task.done()` (`:230–231`) alone no longer demonstrates that the second transaction has passed its pre-UPDATE check and is blocked specifically in UPDATE. Under a delayed first transaction exit/second-phase scheduling, expiry could be rejected before UPDATE and the test could satisfy the same final assertions. I did not reproduce that schedule on PostgreSQL; this is a source-visible oracle attribution limit, not evidence that the production rollback guard fails.

Minimal targeted improvement if the parent requires decisive post-UPDATE mutation resistance: signal only after the second successful owner check for this quiesce invocation, before allowing expiry/releasing the SHARE blocker, or observe the exact blocked UPDATE. Removing the final check should then fail the focused test. No universal test suite or another framework is requested. The new five-cut test separately checks settlement/false result/takeover/generation/expiry, but its expiry cut is a pre-UPDATE rejection, not a replacement for this oracle.

### Target / fixture / cleanup

- `Makefile:29–32` uses the existing isolated interpreter and explicit pytest config/selection, clears Python/pytest injected options/plugins and requires the fixture marker. That marker is not treated as ownership proof: all selected PG tests consume the attested migrated fixture.
- `api/tests/conftest.py:46–110,114–155` validates private UDS/DB/project identity, invokes the existing runner attestor before DDL and cleanup, verifies cluster identity and scopes CREATE/DROP to fresh UUID databases. No arbitrary operator PG fallback or new global SKIP was introduced.
- Runner change is only the target allowlist entry (`run_test_db_gate.py:1038`). Existing fresh-project attestation, clean environment (`:856–877`), owned family receipt and timeout handling (`:795–819`), and cleanup-after-drained-family (`:985–1021`) remain. No weakening of verification flags or cleanup scope was found in this delta.

## Real checks and retained evidence

Executed read-only/source-safe checks:

- Git status/base diff/blob/tree checks and Python SHA256 comparison: exit0, `EXACT_MANIFEST_4_OK`.
- `/usr/bin/make -n`, `-t`, `-q`, `-i` with `test-instance-drain-pg`: **each exit2**, exact unsafe-verification-flags refusal, before any recipe.
- `env -u OMNIS_TEST_FIXTURE /usr/bin/make test-instance-drain-pg`: **exit2**, dedicated-fixture-required refusal, before pytest/PG.
- `git diff --check a20cc59..HEAD`: exit0. Final HEAD/tree/status unchanged.

Read original retained logs, not rerun or promoted to independent QA:

- `core-tmp/db-a618fece220f433a/gate.log`: exact focused pytest selection, **10 passed /25.60s**; `core-evidence/drain-final-pg.log`: target exit0 and owned-resource readback absent/uncertain=False.
- `core-tmp/db-8abf139cab0b4a05/gate.log`: **36 passed /24.79s**; settings runner log: target exit0 and corresponding cleanup readback.
- `core-evidence/drain-source.log`: **11 passed /1.63s**.
- `core-evidence/final-quality.log` contains only `[][]`; this is not a useful independent Ruff/mypy transcript. Quality exit0 remains the author's manifest/commit claim, not a freshly reproduced reviewer result.
- Original broad exit124/unknown cause remains unresolved historical evidence; no retry or reinterpretation as PASS.

One reviewer tool payload had a Python quoting SyntaxError before executing any command; corrected on the next call. No product/fixture effect resulted.

## Limits and handoff

Only this scratch report was created. No source, tests, Makefile, runner, venv or repository metadata was modified; no commit. No PG/OCI/provider/native/global/profile/Q operation, service launch, SDK scratch audit, fixture deletion or fixed-port effect was performed. CID absence is retained author/runner evidence here; independent parent readback remains separate.

Reticle NOT_APPLICABLE; Chisel BLOCKED_NO_GO. No new skill/global memory write: this review was explicitly read-only outside its requested report.

Approval covers the quiescence prerequisite source on the exact snapshot above and the actual currently active API-key Settings drain seam. SystemOperation/model physical authority, new sender/lifecycle, installed QA and full T1 are absent/unapproved. Parent must adjudicate the oracle limitation and retain independent real-PG consumer QA before integration acceptance.
