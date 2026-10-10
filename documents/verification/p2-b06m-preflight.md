# SL11 / B06m — preflight bounded

Base: `c0261a7ae2319b57a0a3154d3e79b2ed908418f8`, branch `p2/b06m-critical-20261010`, only writer worktree `/home/kali/.hermes/cache/scratch/omnis-p2-b06m-20261010`. Main and B06c are read-only dependencies. Protected original HTML is excluded from every read/scan/hash/stage. No new scheduler, provider routing, auth, input/demo or UI.

## Observable contract and scope

Architecture §5.2/§9.3/§9.9/§10 and plan §7–8 govern: admitted exact projection + authenticated binding/owner/turn + fencing → transactional immutable allocation → durable SENT intent → exactly one bounded physical send → usage receipt/reconciliation. Missing prerequisites deny, never authorize from prompt/operator assent alone. Ledger/history can ship independently; no synthetic projection may claim integration.

Reuse schema0011 `managed_record` immutable envelopes and `managed_store` owner/run read checks. One budget definition per owner/run-or-job; no child subbudget multiplication. Reservations and transitions/receipts are distinct append-only records. Run-scoped transactional advisory lock serializes capacity and duplicate attempts; InstanceControl → lease → Stop → ledger is the admission lock order. Reservation remains charged for SENT/UNKNOWN; only a proven no-send RESERVED allocation can be RELEASED. Costs estimated/observed/limit remain separate; strict monetary limits block until a conservative/provider mechanism exists. Validation carve-out is within total and inaccessible to other purposes.

Allowed source: new `policy/budgets.py`, `policy/admission.py`, `policy/model_dispatch*`, `runs/model_dispatch*`, adapter `model_admission*`, minimal owned connectors and tests `*model_budget*`/`*model_admission*`. Do not edit projection producers, shared Makefile/CLI/status/README/rendered HTML. No schema bump is planned; if existing storage proves insufficient, request the smallest migration/integration ownership change before proceeding. Rollback is granular Git revert; no operator DB/profile rollout.

## Pin, receiver, veto and retries

Hermes 0.21.5 at `ee5ee84a345204a3b1d6ef6ba1ab747e602867b9`; pin.json keeps inference unauthorized. Installed revision was NOT inspected/executed: effects are not owned. Read-only preflight compared managed overlay provenance and fetched missing modules at this exact upstream SHA, not latest.

Current installed-path source: supervisor `native_tasks.py:95–158` → `RuntimeClient.managed` → runtime_host `_managed` → `agent/managed_admission_rpc.py` → `SubagentLifecycleService.stage/release`. It creates a cold root and returns authentic BLOCKED/NO_MODEL. It has no latent warm turn or admitted prompt.submit.

Warm source `agent/turn_api_call.py:68–139` / `perform_api_call` invokes execution middleware and then `_interruptible_api_call` (non-stream) or `_interruptible_streaming_api_call`. Chat Completions physical sink is `agent/chat_completion_helpers.py:716–749`, `request_client.chat.completions.create(**api_kwargs)`. `pre_api_request` at `turn_api_request.py:42–89` ignores return values and catches exceptions; request middleware also falls back on failure. `hermes_cli/middleware.py:179–212` can execute downstream after a callback exception. Thus neither hook is an authorization barrier.

SDK request-local client sets max_retries=0 (`agent/client_lifecycle.py:437–446`), but native streaming/compatibility/summary retries and recovery/fallback remain. `conversation_loop.py:1421–1449` catches exceptions for recovery; `turn_api_error.py:324–370` allows fallback. api_request_id is outside the retry loop, not a physical-attempt identity. An ordinary Exception from a wrapper is insufficient.

Minimal defensible extension: trusted terminal gate at one explicit physical non-stream sink, single-use permit bound to final bytes/transport/model/turn/attempt and durable SENT; all other transports/retries/auxiliaries denied until separately integrated. No global plugin semantic change and no cold→warm switch. Overlay build application would require the shared build owner's connector; do not claim an unapplied patch is installed enforcement. Current disposition: BLOCKED_NATIVE_SEAM, not G-MODEL.

## Authentic owner, native turn and projection dependency

Domain owner (`command.owner_id`) differs from supervisor lease owner (`self.owner`). Existing binding commits boot/instance/owner/epoch/generation between stage and release. Native cold child/session/root IDs come from native objects and recheck the same root object under lock. They are not model turn IDs.

Warm turn producer is `agent/turn_facade.py:57–65`; turn context attaches in `agent/turn_context.py:532–556`. Adapter must persist a native-turn ref from this authenticated lifecycle and bind it to boot/binding. Do not manufacture a turn UUID from a task/session/API request ID. Purpose derives from binding, never model JSON. C02 selection is NO_MODEL/effective=null today and cannot grant later inference. Settings needs its own fixed trusted job owner and configuration through the same ledger, not a fictional child.

B06c interface was absent at initial and preflight reads: NOT_INTEGRATED. Consume only its FROZEN/reviewed commits and its projection_ref/projection_digest contract. Missing projection is a default deny. No WIP merge, no main cherry-pick, no personal runtime/config adoption.

## Evidence and remaining live conditions

Effects registry holder was `c03-records`, allowed_worker_fixture_targets empty. No DB/OCI/installed/native fixture is authorized for b06m now. Allowed: owned source/venv, offline tests/lint/reviews. Owned API venv created offline with cached uv0.12.19 and Python3.13.15, exact locked dependencies, exit0. DB persistence/readback/restart/overlap tests will use the existing attested PostgreSQL runner when targets transfer; until then NOT_RUN, not a mocked PASS. Canonical make check belongs to serial integration only.

Required checks: exhaustion/reference mismatch; real concurrent reservations; duplicate attempt conflict/replay; validation isolation; Stop between reserve/send; zero bytes on denial; SENT visible at sink before bytes; lost response/UNKNOWN; no retry/fallback; receipt replay/conflict and historical readback after Stop/restart. Source/unit, synthetic transport, native pinned and provider live results must stay separate. Two complementary exact-snapshot reviews and independent actual-consumer QA are acceptance gates. No fixture cleanup is needed yet; owned venv/evidence retained.

Live conditions remain C02 resolved requested/effective configuration; C06–C08 authentic root/child/lineage and turn binding; C09/C11/C12 usage/results/inbox/recovery/late receive-only; C10 method predicates, without promoting synthetic results to method completion; H04–H08 corresponding native identity/compression/Stop/wake/lost RPC/inventory/retry/auxiliary behavior. B06c data gate and P4a Settings precede separate account/model/data/budget authorization. These are not blockers to ledger source work and cannot be closed by NO_MODEL or simulation.

Independent read-only architect locator: `/home/kali/.hermes/cache/delegation/live/deleg_188cd146/task-0.log` (exact base above). It supplied seam analysis, not implementation approval or QA.
