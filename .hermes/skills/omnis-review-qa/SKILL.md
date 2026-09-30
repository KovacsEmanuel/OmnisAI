---
name: omnis-review-qa
description: "Use when reviewing and verifying an Omnis change."
version: 0.1.8
author: OmnisAI (KovacsEmanuel), Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [omnis, development]
---

# Omnis independent review and QA

## When to Use
Before accepting an implementation slice, resolving a regression, or declaring a phase delivered. Review functional compliance separately from code quality and visual approval.

## Procedure
1. Use `terminal` to identify base/head and `git diff`; include owned untracked files, relevant surrounding code and acceptance criteria. Establish existing failures without stashing someone else's work. A detached clean worktree can reproduce a baseline.
2. Run the cheapest relevant deterministic checks first: syntax, schema, lint/type, targeted unit/integration, then regression and browser/E2E. Missing commands are NOT-RUN/BLOCKED, never silent green. A tool's exit 0 is only evidence for the property it tested.
3. Ask an independent reviewer via `delegate_task` for concrete findings: severity, file:line, reproducer, violated requirement, remedy. First ask whether the slice meets the spec; then inspect authorization, input boundaries, races, persistence, error handling and complexity. The reviewer is read-only in the shared checkout.
   Maintain a requirement→code→evidence matrix for the declared slice. A focused fix re-review closes its findings, not requirements that were never reviewed. Separate confirmed defects, incomplete proof and explicitly deferred scope; do not infer completeness from the last blocker being closed. Compare snapshot/scenario, not reused issue IDs, when a later review arrives.
4. Reject findings based only on style preference unless they conflict with a committed rule. Verify suspected bugs with a test. Fix blockers in minimal separate changes; rerun affected checks after the LAST edit. Two failed fix attempts trigger a narrower investigation, not blind repetition.
   Bound the review loop to the affected product acceptance criterion: re-review a concrete fix, not the entire growing harness. If two cycles expose new test-oracle blockers without advancing that criterion, mark the slice WIP/BLOCKED and reconsider the proof boundary before adding another process supervisor or mutation layer. This does not approve unresolved findings.
5. For UI inspect the actual screenshot against the user's reference at agreed viewports. Test keyboard/focus, modal/drawer Stop, resize, loading/empty/error/unavailable, reduced motion, long content and real state transitions. Chromium smoke does not certify screen readers, all browsers or aesthetics.
6. Use Reticle optionally for instrumented local runtime evidence; keep Playwright/DOM and screenshot checks independent. An INCONCLUSIVE result remains inconclusive. Do not install instrumentation into a production build or use it on unrelated sites.
7. Audit added lines and staged paths for credentials, sensitive evidence, unsupported dependencies and accidental files. Review generated changes against their source. Keep external revisions/licenses and actual failures in the change record.
8. Parent reproduces critical assertions and commits the accepted slice. Record exact commands, counts, exit codes, limitations and base/head; final reporting distinguishes implementation, integration and visual acceptance.
9. Use `omnis-project-status` for ORIENT before review and a scoped status delta at handoff. A read-only reviewer reports proposed changes; only the parent reconciles the map in CLOSE after adjudication. Bind approval to the reviewed snapshot/files, preserve genuinely open findings and compare delayed reports with later fixes. End with approved/in-review/not-reviewed or changes-requested scope, global gates and the next canonical slice; a review is not a runtime PASS.

## Pitfalls
For hash-routed prototypes, reload or create a fresh browser page between cases: fragment navigation retains run, dialog and filter state. Verify the isolated RED fails only for the intended behavior.

Verify focused pixels and target geometry, not only activeElement: an outer outline can be clipped, and a contextual link can preserve scroll below the selected object's title. Test repeat navigation from long mobile pages and place focus below persistent run controls.

Resolve an evidence/task link's operation, identity and snapshot explicitly; opening the destination page while retaining incompatible filters can display another object's evidence. Include a prior-selection/empty-filter regression.

Exercise rerenders as well as initial clicks: a stopped/paused run must not regain an active phase after finding review or filtering. Recheck current evidence availability in every consumer (finding, operation inspector, coverage and newly exported reports), while preserving historical verdicts and saved report snapshots. Download and parse the actual export; a preview count is not evidence that its bytes match.

No universal 'verified' badge. Verify the verifier: match exact structured diagnostic identifiers/severity/source, not a substring in an exception stack; require positive and negative controls on the SAME evidence channel. An arbitrary failure or always-rejecting observer must not pass the negative control. Add a regression for each false-green mechanism before trusting the repaired gate. A test that mocks the entire behavior or merely checks a filename cannot certify a feature. Do not loosen security/error handling to remove 'slop'. Do not auto-approve a review because it agrees with the implementer.

Test the producer of a safety flag as well as its consumer: injecting `uncertain=true` proves the cleanup predicate, not that signal exit, lost ACK or decoding failure actually sets it. Exercise the real failure boundary where safe, then pass its observed state into the cleanup oracle; label substituted daemon/resource seams rather than claiming an end-to-end effect.

For process-cleanup mutation controls, hold the synthetic child alive beyond the observed owner/reaper deadline unless an attested kill occurs, while arming a parent-death guard. Assert the actual `waitid` exit cause and bounded reap before crediting SIGKILL: a child's natural timeout can make a no-op kill mutant appear to pass. Rescue every pinned/adopted child and report UNCERTAIN on missing readback.

When Hermes verify-on-stop names `make test`/`make check` but their prerequisites are unsafe or absent, report that canonical gate once as BLOCKED with the last relevant command, exit and limit. Focused checks remain targeted evidence even if the workspace ledger says unverified. Do not repeat them solely for the nudge or change the Makefile into a false-green alias; move to the prerequisite or stop the slice.

For exception-based test guards, record each attempted violation to an independent parent-owned channel **before** raising. Test a child that catches the exception and exits successfully: its report must still fail the clean verdict. Require observer readiness, known event tags and positive/negative controls; missing evidence is not zero attempts. Fail closed if recording fails, and distinguish Python audit events from native syscalls/OS confinement.

When typing a test observer/decoder, preserve unknown fields before leak/completeness assertions. A parser that strips unrecognized fields can manufacture a clean result. Exercise an unexpected synthetic marker at both top-level and nested payload positions, while rejecting wrong types; this evidence-preserving test policy does not replace strict allowlists on production inputs.

Test teardown after an ordinary early driver exit, not only a live-driver timeout. A PPID snapshot taken after the leader exits loses reparented/detached children. Establish owned adoption or a managed scope before launch, exercise real SIGTERM-resistant children in both orderings, attempt all cleanup before exit-code assertions, and restore any per-test process attribute. Do not adopt preexisting/foreign work; publish final PASS only after teardown and parent-owned leak checks.

## Verification
All named acceptance criteria accounted for, blocking findings resolved, regressions rerun and intended changes committed. Retained failures/limits are searchable in Git or concise versioned notes, not hidden in temporary transcripts.
