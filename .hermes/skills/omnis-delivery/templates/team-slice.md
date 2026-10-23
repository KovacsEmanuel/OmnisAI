# Omnis implementation team — bounded slice contract

Parent/orchestrator: owns current scope, dependency admission, Git integration, resource cleanup and final acceptance; developers own product edits/fixes, reviewers assess frozen bytes, QA runs the affected real artifact. The parent does not become an unannounced parallel developer. Children never close a gate or commit in the shared checkout.

Before dispatch, bind the latest requested deliverable and this session's phase ceiling in the existing task contract. Handoff/prompt-only means no implementation writer or successor launch, even after an option is approved. On a later stop, cancel owned writers and verify actual state before handing off; a delayed completion cannot reopen that phase. QA may preflight existing real inputs/aggregate bounds without effects early, but real-consumer effects wait for the required reviews and authority.

Default: one orchestrator, one developer and one independent exact-snapshot reviewer; QA is a separate stage. No standing Loop Engineer. Add roles only for a real decision, independent workstream or affected consumer; agent count is not acceptance evidence.

## Architect (read-only, only for unresolved decisions/interfaces)
- Input: HEAD/status/diff including pre-existing WIP, one canonical ticket, relevant architecture/plan/UI contract and actual callers/tests.
- Return at most two pages: decision/interface resolution; observable outcome; scope/non-goals; domain/state invariants; requirement → code → RED/real evidence; necessary writer assignments (allowed paths, dependencies, interfaces, ownership); reviewer charters; affected-consumer journey, negative controls, resource owner/cleanup, commands and limits.
- Identify contradictions, absent prerequisites and unresolved decisions. No concurrent plan, service, model/target product call or file edit. Set a bounded tool/time budget; report partial findings instead of exhaustive catalog reading.

## Development (one author by default)
- Each author receives only file ownership, baseline hashes, interface contract, RED test and stop conditions. Add a second developer only for genuinely independent paths/acceptance criteria after interfaces are frozen; do not invent a test/research role just to fill a team. For concurrent writers, worktrees start explicitly at the verified local HEAD; the parent transfers the exact selected WIP bytes/diff into each, checks hashes and records the baseline. Never copy redacted rendered source or the protected untracked HTML.
- Before a concurrency probe, name the command/effect linearization points and legal outcomes. Do not hold a barrier inside a lock needed by Cancel/Stop and require that command to acknowledge first; separate admitted cancellation/drain from already-admitted work expiry and stale CAS refusal. Counters since operation start do not prove a post-ACK property.
- Concurrent writers touch disjoint paths. No commit in the common checkout, no push, no rollout or effectful assessment.
- Each returns changed paths/blobs, RED→GREEN command/exit, negative control and limits. Parent transfers only owned changes, verifies bytes, runs affected checks and commits each coherent integrated change.

## FREEZE — exact identity before review

Freeze the exact commit/blob/diff identity and owned artifact/file hashes for all reviewers and QA. Candidate commit **nu este acceptare**. Commit/blobs identify reviewable bytes; changed bytes need affected checks and focused re-review. Metadata-only edits do not force full product gates.

## Review (after a frozen integrated snapshot)
- At least one independent read-only reviewer checks compliance, correctness and safety. Two complementary independent reviewers are mandatory for changes to authority, epoch, concurrency, model dispatch, Stop, effect/secret boundaries or cross-runtime contracts:
- Reviewer 1: requirement/order/persistence and exact readback against normative contract.
- Reviewer 2: auth, input bounds, concurrency/epoch, failure and cleanup paths, accessibility/simplicity as applicable.
- All reviewers use the SAME commit/hash manifest. Return only concrete findings `{severity, file:line, reproducer, violated criterion, minimal remedy}` and a scoped verdict. Parent adjudicates every original and new finding. A later empty list does not clear an older reproducer.
- Părintele reproduce/adjudecă; developerul desemnat scrie remedierea, cu transfer de autorat numai explicit. Fix RED→GREEN on owned files, rerun affected checks after LAST edit, request focused re-review of changed bytes and affected call sites. Preserve reviewed unchanged scope; record source-unchanged/distribution-changed separately and verify parser/reapply/build/identity for the exact changed artifact. No approval transfers to changed source or untested distribution.
- Track harness-only review/repair cycles against the same product acceptance row across sessions. After two without product progress, narrow the reproducer or report WIP/BLOCKED, not another generic audit or a reset counter. New security findings remain explicit blockers.

## Live QA (new/affected real consumer, after blocking code findings clear)
- Execute the real final local artifact, not a synthetic verdict. An independent reviewer may perform QA under a separate execution contract; a distinct QA agent is not universally required. For affected UI: launch the built local app on an owned loopback API/PostgreSQL fixture, open a real browser, type/click/tab/reload/resize and inspect DOM/focus/screenshots; test success and denial on the same channel. For API/CLI-only: exercise the real consumer, process/DB and readback; no browser for unchanged UI or documentation-only changes. Reuse exact unchanged consumer evidence rather than replaying it for each follow-up.
- Clear blocking implementation findings and effect prerequisites before QA. Missing runtime evidence remains an open acceptance criterion for that admitted QA to establish, not a circular prerequisite that the same QA must already have passed. An exhausted harness row still requires a corrected causal model/narrowed boundary before another attempt; keep its counter and unresolved safety findings.
- Record exact command, exit, product assertion, negative control, source hashes and exact owned resource cleanup/readback. Block external requests, target traffic and provider calls unless separately authorized. Screenshots are not aesthetic approval; Reticle is not a substitute for browser/API/DB.
- Reticle: load only for admitted instrumented local UI evidence; CLI/docs are NOT_APPLICABLE, uninstrumented UI is NOT_INTEGRATED. Chisel remains BLOCKED_NO_GO; load only for an explicitly authorized adoption reevaluation, never an unsandboxed fallback. No ceremonial tooling smoke.
- If QA finds a blocker, parent reproduces it, assigns minimal fix, repeats affected gate and focused review, then reruns the live path on final bytes. No blanket PASS from a test count or `family_drained` alone.

## Closure
- The parent checks, stages narrowly, commits and reads back each coherent green integrated candidate. Candidate commit is not acceptance; integration/closure requires the applicable reviews and QA on exact current bytes. If review/QA finds a blocker, commit the minimal tested correction separately and re-review the current bytes. At closure, read back the already-reviewed commits; commit only factual status/documentation changes or genuine fixes, never an empty approval commit. Run affected tests after the last relevant edit and the canonical gate on final product bytes at the integration/phase boundary, not for every fix, Markdown edit or verify-on-stop reminder. Run documentary checks after documentary edits. Reconcile only affected status rows. Otherwise report BLOCKED/NOT_RUN with the next necessary action and preserve WIP/owned evidence.
