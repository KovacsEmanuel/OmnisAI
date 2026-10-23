# R2 — 878 host-boundary delta

**Verdict: APPROVED_SOURCE_SCOPED.** No blocking code defect identified in the nine-file delta. This approves the inspected SOURCE change, not full relay safety proof, PostgreSQL concurrency, installed distribution, T1 acceptance, or permission to run a consumer. Prior unchanged fb54 scoped approvals remain scoped; the previously OPEN R2 physical-proof obligation remains OPEN.

## Snapshot and authority

- Frozen checkout: `/home/kali/.hermes/cache/scratch/ot1-0zxf62th/model-review-878`.
- Base: `fb54beace973b7c49422b197404f04c8baa6a9dd`.
- HEAD: `878895d3a4dda1f50c394dd01a711ac79acd1586`.
- Tree: `f666a1b26d9fd530291227f7da1f766bd86f6e9b`.
- Manifest: `../logs/parent-878-freeze.json`. Independently compared the Git delta list, all nine current blobs and SHA-256s with this manifest: MATCH. API/CLI protocol bytes independently compared: IDENTICAL.
- Frozen checkout clean at entry. Main checkout observed separately at `de7a3705a53154a9234f31126167670a07d2200e`, with only preexisting protected `documents/Omnis_Notite_Originale.html` untracked; untouched. No inspection of mutable `runtime-src`.
- Reviewed README CURRENT, affected status/verification context, CONTRIBUTING product-first/preflight constraints, team-slice and the directly affected producer/relay callers. This is RCA + repair review, not authorization to continue all T1. No chronology inferred from fixture-array order; historical failures and the existing two-cycle boundary are not cleared or reset.

Exact delta scope:

1. `api/src/omnis/supervisor/model_relay_protocol.py`
2. `api/src/omnis/supervisor/model_sender.py`
3. `api/tests/test_model_relay_protocol.py`
4. `api/tests/test_model_relay_scopes.py`
5. `api/tests/test_model_sender.py`
6. `api/tests/test_model_test_v2.py`
7. `cli/src/omnis_cli/model_relay.py`
8. `cli/src/omnis_cli/model_relay_protocol.py`
9. `cli/tests/test_model_relay_fence.py`

## Findings

**Blocking code findings: none identified in this scope.** The following are explicit proof limits/tradeoffs, not fabricated code defects or closed runtime obligations.

### P1 — Physical proof OPEN, not a source-code finding

- Locations: `api/tests/test_model_test_v2.py:669-754,755-863`; `cli/src/omnis_cli/model_relay.py:160-175`.
- Concrete scenario: production PG admission and cancellation while OPEN is already suspended in TCP connect. The changed source has cancellation/closure tracking, but the supplied executed CLI case holds DNS, and the added SOURCE case exercises connect expiry, not concurrent FENCE/DRAIN during held connect. The v2 PG scenarios were collected only.
- Criterion: real-consumer lock/fence/drain and terminal/readback proof must be observed on current bytes, not inferred from source review or counts.
- Minimum disposition: retain NOT_RUN/OPEN. Parent alone may admit a bounded affected consumer after complementary blocking code findings are clear; no new framework or blind rerun is requested by this review.

### P2 — Late-WRITE assertion is a replay negative, not an isolated fence oracle

- Location: `api/tests/test_model_test_v2.py:778-847`.
- Concrete scenario: the post-ACK frame reuses the captured producer sequence already consumed by the earlier header WRITE and its old deadline. DENIED can therefore also follow from sequence/expiry, independently of cancellation fencing. It correctly uses real producer context, asserts exact denial and observes post-ACK counters; it does not isolate all denial predicates.
- Criterion: positive/negative evidence must not overclaim which boundary was proven.
- Minimum disposition: describe this as exact stale replay rejection. If an isolated post-Cancel next-WRITE claim is needed in the already bounded consumer, distinguish that case using the next valid sequence and a still-valid captured authority window, without minting fake DB authority or weakening expiry. Existing same-channel `a/b/c` controls in `test_model_relay_scopes.py:183-202` remain useful but are not a production Cancel proof.

### P3 — Preparation availability tradeoff is real

- Locations: `model_sender.py:120-125`; CLI `model_relay.py:120-123,160-175`.
- DNS, IPC delay and TCP establishment now consume the existing lease-derived <=0.5s window (production producer subtracts a safety margin). Slow cold DNS/connect can fail despite the SDK's longer timeout. This is not demonstrated provider-live availability and is not equivalent to retaining the former DNS allowance. No retry, larger authority window or new wire field is silently introduced. Parent must retain this limit in acceptance; increasing it would need a separate justified change.

## Requirement → code → evidence assessment

- **OPEN freshness:** sender exits the guard before RPC. Host requires OPEN's existing UTC `write_deadline`, bounds it by scope deadline and now+0.5s, checks after DNS and again after connect, and closes uncertain OPEN on timeout/error/cancellation. No SQL-held TCP readiness remains in this path. The host consumes producer authority; it does not independently query PostgreSQL owner state. Production `metadata_guard`/`write_guard` and `physical_window` were read as affected callers, not re-approved wholesale.
- **FENCE/DRAIN/lifetime:** OPEN registers the connection and current task before resolver start. Resolver liveness participates in pending/drain; `close()` closes any socket and cancels other owning tasks. DNS completion cannot continue into connect after fenced/closed checks. During held connect the same task/socket are tracked and cancellable; inspection is not executed physical proof. Failed OPEN remains a closed consumed identity; resolver still alive prevents a replacement live stream.
- **WRITE local handoff:** CLI lines 194-207 require the already-prepared nonblocking socket. There is no reconnect, `sock_sendall`, network-await loop or continuation queue in WRITE. One finite `send` either accepts the complete chunk or fails; partial/zero/EAGAIN/OSError close the connection and cannot return OK. Post-syscall deadline uncertainty also closes with upstream-unavailable. Cancellation leaves DENIED and closes an owned OPEN/WRITE; no syscall is interrupted halfway by an asyncio await inside this synchronous branch.
- **No stale CURRENT/retry:** the unchanged CipherStream callback resolves CURRENT at each guarded ciphertext chunk, updates its scope, consumes sequence before effect and retains the missing-ACK/cancellation deadline wait. Sender/SDK retries remain disabled. Connection reuse still checks stable instance/execution owner/epoch/generation/provider and binds the current operation scope; no cached OPEN authority replaces WRITE admission. Unchanged behavior is preserved at its prior scope, not audited anew.
- **Trust boundaries:** exact-envelope/UTC/integer/body limits, UID, capability, endpoints, request replay, connection identity/sequence and response ACK matching were not weakened by the delta. Protocol copies are byte-identical. No additional field or owner was added. Existing strict ACK tests include Boolean version/sequence/epoch rejection and a valid same-channel control.
- **SOURCE TLS and outward-traffic risk:** added SDK test uses actual broker, public SDK and verified owned TLS with an explicit admission-lock double. Its DNS placeholder `8.8.8.8:443` is asserted then rerouted to the owned loopback listener *before* calling original `sock_connect`; AF_UNIX retains its ordinary local path. Scope DNS-success tests now intercept non-UNIX connect with an effect-free double. Held-DNS CLI uses a connect assertion trap. v2 fixture similarly redirects to its owned loopback address. No inspected added path actually connects to 8.8.8.8; no universal packet trace or provider-live claim is made.
- **Negative tests:** SOURCE modes healthy/veto/connect-expiry/backpressure/partial/closed inspect guard ownership and actual `socket.send`, prohibit async upstream sendall, require UNKNOWN/no request for failures and exactly one attempted handoff for partial/backpressure/closed. Partial injects a real one-byte loopback send. These are boundary injections, not measured kernel-buffer saturation. v2 IPC-write expiry is deliberately delayed inside the production guard; its `physical_window` timeout cancels before the delayed original RPC, so it is not evidence that the host received an expired WRITE. Cancel-at-body pauses before the body guard, allowing Cancel admission, FINISHED/CANCELLED readback and producer-scoped FENCE/DRAIN ACK assertions without the former lock-order oracle. Those PG assertions have not run on this snapshot.

## Commands and retained output

Read-only review commands included `git status --short --branch`, `git diff --stat`, `git diff --cached --stat`, `git rev-parse HEAD`, frozen `git show -s --format=fuller HEAD`, `git diff --name-only` and affected `git diff fb54beace973b7c49422b197404f04c8baa6a9dd HEAD`, plus `git rev-parse HEAD^{tree}`. A stdlib Python identity check used the manifest, Git blob IDs, SHA-256 and direct protocol-byte comparison; exit0: `MANIFEST_IDENTITY 9 MATCH; API/CLI protocol BYTE_IDENTICAL`. File reads/searches inspected the raw outputs and actual test producers. A few initial guessed caller/document filenames did not exist; actual runtime caller and canonical architecture name were subsequently located. No effectful fallback was used.

Retained execution evidence was read, **not rerun**:

- `../red-readiness.log`: both readiness cases fail because connect is under guard (`[True]`, expected `[False]`). Commit records `pytest api/tests/test_model_sender.py -k tcp_readiness` with the isolated GREEN interpreter/options. This establishes the old failure, not SQL proof.
- `../green-final.log`: `86 passed in 2.89s`. Recorded command: `env -u PYTHONPATH -u MYPYPATH -u PYTEST_ADDOPTS -u PYTEST_PLUGINS PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 api/.venv/bin/python -I -B -m pytest -p pytest_asyncio.plugin -p no:cacheprovider -c api/pyproject.toml api/tests/test_model_sender.py api/tests/test_model_relay_scopes.py api/tests/test_model_relay_protocol.py api/tests/test_model_test_v2_contract.py -q --tb=short`.
- `../quality-final-pass.log`: checks passed / 77 files already formatted; commit records `make lint-api typecheck-api`, API Ruff check/format on CLI source/tests, and strict no-incremental mypy on CLI source, exit0. Bare log is not a complete shell transcript.
- `../cli-final.log`: affected unittest discovery separately for `test_model_forwarder.py` (2 tests OK) and `test_model_relay_fence.py` (1 test OK, held DNS).
- `../collect-final.log`: 27 collected only, including v2 PG/migration consumers; no DB execution. Exit0 for the final gates is recorded by the frozen commit body, not independently embedded in every raw log.

## Handoff limits

Only this report was created; no product/tests/docs/Git/profile changes, installs, secrets, services, PostgreSQL, network or browser effects. No unchanged suite was rerun. Reticle NOT_APPLICABLE; Chisel BLOCKED_NO_GO. No fresh acceptance follows from this report, aggregate counts or the corrected fixture order. Historical 21 → 24/2 → 47/2 evidence remains untouched; settlement/CAS history remains UNATTRIBUTED. The parent owns adjudication and any next bounded real-consumer admission.

Skipped: full old-source audit, PG/full-relay/installed/provider-live/UI execution. Risk: short preparation window and unexecuted physical concurrency proof remain explicit; the late replay negative does not by itself isolate cancellation fencing.
