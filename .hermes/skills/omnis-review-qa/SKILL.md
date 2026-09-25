---
name: omnis-review-qa
description: "Use when reviewing and verifying an Omnis change."
version: 0.1.3
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
4. Reject findings based only on style preference unless they conflict with a committed rule. Verify suspected bugs with a test. Fix blockers in minimal separate changes; rerun affected checks after the LAST edit. Two failed fix attempts trigger a narrower investigation, not blind repetition.
5. For UI inspect the actual screenshot against the user's reference at agreed viewports. Test keyboard/focus, modal/drawer Stop, resize, loading/empty/error/unavailable, reduced motion, long content and real state transitions. Chromium smoke does not certify screen readers, all browsers or aesthetics.
6. Use Reticle optionally for instrumented local runtime evidence; keep Playwright/DOM and screenshot checks independent. An INCONCLUSIVE result remains inconclusive. Do not install instrumentation into a production build or use it on unrelated sites.
7. Audit added lines and staged paths for credentials, sensitive evidence, unsupported dependencies and accidental files. Review generated changes against their source. Keep external revisions/licenses and actual failures in the change record.
8. Parent reproduces critical assertions and commits the accepted slice. Record exact commands, counts, exit codes, limitations and base/head; final reporting distinguishes implementation, integration and visual acceptance.

## Pitfalls
For hash-routed prototypes, reload or create a fresh browser page between cases: fragment navigation retains run, dialog and filter state. Verify the isolated RED fails only for the intended behavior.

Verify focused pixels and target geometry, not only activeElement: an outer outline can be clipped, and a contextual link can preserve scroll below the selected object's title. Test repeat navigation from long mobile pages and place focus below persistent run controls.

Resolve an evidence/task link's operation, identity and snapshot explicitly; opening the destination page while retaining incompatible filters can display another object's evidence. Include a prior-selection/empty-filter regression.

Exercise rerenders as well as initial clicks: a stopped/paused run must not regain an active phase after finding review or filtering. Recheck current evidence availability in every consumer (finding, operation inspector, coverage and newly exported reports), while preserving historical verdicts and saved report snapshots. Download and parse the actual export; a preview count is not evidence that its bytes match.

No universal 'verified' badge. Verify the verifier: match exact structured diagnostic identifiers/severity/source, not a substring in an exception stack; require positive and negative controls on the SAME evidence channel. An arbitrary failure or always-rejecting observer must not pass the negative control. Add a regression for each false-green mechanism before trusting the repaired gate. A test that mocks the entire behavior or merely checks a filename cannot certify a feature. Do not loosen security/error handling to remove 'slop'. Do not auto-approve a review because it agrees with the implementer.

## Verification
All named acceptance criteria accounted for, blocking findings resolved, regressions rerun and intended changes committed. Retained failures/limits are searchable in Git or concise versioned notes, not hidden in temporary transcripts.
