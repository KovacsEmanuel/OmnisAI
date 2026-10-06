# Omnis implementation team — bounded slice contract

Parent/coordinator: owns Git integration, exact shared checkout, resource cleanup and final status. Children never close a gate or commit in the shared checkout.

## Architect (read-only, first)
- Input: HEAD/status/diff including pre-existing WIP, one canonical ticket, relevant architecture/plan/UI contract and actual callers/tests.
- Return at most two pages: observable outcome; scope/non-goals; domain/state invariants; requirement → code → RED/real evidence; two nonoverlapping writer assignments (allowed paths, dependencies, interfaces, ownership); reviewer charters; live-QA journey, negative controls, resource owner/cleanup, commands and limits.
- Identify contradictions, absent prerequisites and unresolved decisions. No concurrent plan, service, model/target product call or file edit. Set a bounded tool/time budget; report partial findings instead of exhaustive catalog reading.

## Development (parent dispatches two leaf agents)
- Dev A and Dev B receive only their file ownership, baseline hashes, interface contract, RED test and stop conditions. Two worktrees start explicitly at the verified local HEAD; the parent transfers the exact selected WIP bytes/diff into each, checks hashes and records the baseline. Never copy redacted rendered source or the protected untracked HTML.
- Writers touch disjoint paths. If the slice has one write surface, the second developer writes independent tests in a separate path or investigates read-only; do not invent parallel code ownership. No commit in the common checkout, no push, no rollout or effectful assessment.
- Each returns changed paths/blobs, RED→GREEN command/exit, negative control and limits. Parent transfers only owned changes, verifies bytes, runs affected checks and commits each coherent integrated change.

## Review (after a frozen integrated snapshot)
- Reviewer 1: requirement/order/persistence and exact readback against normative contract.
- Reviewer 2: auth, input bounds, concurrency/epoch, failure and cleanup paths, accessibility/simplicity as applicable.
- Both read-only on the SAME commit/hash manifest. Return only concrete findings `{severity, file:line, reproducer, violated criterion, minimal remedy}` and a scoped verdict. Parent adjudicates every original and new finding. A later empty list does not clear an older reproducer.
- Fix RED→GREEN on owned files, rerun affected checks after LAST edit, request focused re-review on changed bytes only. Two cycles that advance only harness work trigger a narrower product reproducer or BLOCKED, not another generic audit.

## Live QA (real consumer, after blocking code findings clear)
- Independent QA agent executes the relevant real local artifact, not a synthetic verdict. For UI: launch the built local app on an owned loopback API/PostgreSQL fixture, open a real browser, type/click/tab/reload/resize and inspect DOM/focus/screenshots; test success and denial on the same channel. For API/CLI-only: exercise the real consumer, process/DB and readback; do not claim browser testing when not applicable.
- Record exact command, exit, product assertion, negative control, source hashes and exact owned resource cleanup/readback. Block external requests, target traffic and provider calls unless separately authorized. Screenshots are not aesthetic approval; Reticle is not a substitute for browser/API/DB.
- If QA finds a blocker, parent reproduces it, assigns minimal fix, repeats affected gate and focused review, then reruns the live path on final bytes. No blanket PASS from a test count or `family_drained` alone.

## Closure
- Each coherent integrated change is checked, staged narrowly, committed and read back before review. If review/QA finds a blocker, commit the minimal tested correction separately and re-review the current bytes. At closure, read back the already-reviewed commits; commit only factual status/documentation changes or genuine fixes, never an empty approval commit. Run the canonical gate on final product bytes at the phase boundary and documentary checks after documentary edits. Reconcile only affected status rows. Otherwise report BLOCKED/NOT_RUN with the next necessary action and preserve WIP/owned evidence.
