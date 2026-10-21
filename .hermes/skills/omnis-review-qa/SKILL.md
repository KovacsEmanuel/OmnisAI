---
name: omnis-review-qa
description: "Use when reviewing and verifying an Omnis change."
version: 0.1.44
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
2. Apply `CONTRIBUTING.md` §„Execuție orientată spre produs” for work admission, no-effect preflight, continuity and the two-cycle limit. Bind the scoped requirement/consumer, positive and negative controls, commands, budget and owned cleanup. After the last relevant edit rerun affected checks; full product gates belong at the applicable integration boundary. Review evidence on exact bytes, not test counts or exit0 alone.
3. Apply [team-slice](../omnis-delivery/templates/team-slice.md) for independent reviewer assignments, ownership, sensitive-boundary review count and separate real-consumer QA. Review compliance with the requested scope first, then security/correctness/maintainability; return concrete severity, file:line, scenario, criterion and minimal remedy on the same exact snapshot.
   For a fix or pin/patch reseal, the manifest separates unchanged source from changed distribution. Unchanged behavioral approval remains within its original scope; it does not approve changed source or distribution. Require affected tests and focused re-review, plus parser/reapply/build and identity readback for the exact changed artifact. A helper/test finding does not automatically reopen unrelated reviewed requirements.
   Maintain a requirement→code→evidence matrix and an explicit disposition for every concrete finding from the original and later reports. A newer empty findings list does not close an older named reproducer: compare it against current bytes, and require RED→GREEN plus focused re-review for each surviving blocker before acceptance. A focused fix re-review closes its findings, not requirements that were never reviewed. Separate confirmed defects, incomplete proof and explicitly deferred scope; do not infer completeness from the last blocker being closed. Compare snapshot/scenario, not reused issue IDs, when a later review arrives.
4. Reject findings based only on style preference unless they conflict with a committed rule. Verify suspected bugs with a test. The parent reproduces/adjudicates blockers; the assigned developer fixes them in minimal separate changes; rerun affected checks after the LAST edit. Two failed fix attempts trigger a narrower investigation, not blind repetition.
   Bound the review loop to the affected product acceptance criterion: re-review a concrete fix, not the entire growing harness. If two review/repair cycles advance only harness evidence without advancing that criterion, mark the slice WIP/BLOCKED and narrow the reproducer/reconsider the proof boundary before adding another process supervisor or mutation layer. Carry the cycles and dispositions for the same acceptance row across sessions; a new session or renamed oracle does not reset the count. New security findings remain separate explicit blockers. This does not approve unresolved findings.
5. For UI inspect the actual screenshot against the user's reference at agreed viewports. Test keyboard/focus, modal/drawer Stop, resize, loading/empty/error/unavailable, reduced motion, long content and real state transitions. Chromium smoke does not certify screen readers, all browsers or aesthetics.
6. Decide Reticle/Chisel applicability without ceremonial loading. For CLI/process/docs-only scope, report Reticle NOT_APPLICABLE and Chisel BLOCKED_NO_GO once; do not load either skill or rerun a tooling smoke. These are tools, not independent reviewers with opinions; never fabricate a second verdict from their presence. For executed applicable tooling, record scope/artifact, command, result and limitation.
   - Load `omnis-reticle` only for admitted, instrumented local UI runtime evidence; keep Playwright/DOM and screenshot checks independent. If the application is not instrumented, state NOT_INTEGRATED. A separately executed synthetic smoke is TOOLING_ONLY, not product acceptance, and need not be rerun for every finding. INCONCLUSIVE remains inconclusive. Do not install production instrumentation or use unrelated sites.
   - Apply Chisel's current NO-GO: BLOCKED_NO_GO on the repository/home/runtime profile until its adoption controls pass. Load `omnis-chisel` only for an explicitly authorized adoption reevaluation, using an exact artifact and OS-isolated disposable fixture; no unsandboxed fallback or automatic registration. Missing binary/probe infrastructure is NOT_RUN, not a fresh failure/pass measurement. Use native file tools while blocked.
7. Audit added lines and staged paths for credentials, sensitive evidence, unsupported dependencies and accidental files. Review generated changes against their source. Keep external revisions/licenses and actual failures in the change record.
8. Parent reproduces critical assertions and integrates/commits granular green candidate changes; candidate commit is not acceptance. Required review/QA precede acceptance. Record exact commands, counts, exit codes, limitations and base/head; final reporting distinguishes implementation, integration and visual acceptance.
9. Use `omnis-project-status` for ORIENT before review and a scoped status delta at handoff. A read-only reviewer reports proposed changes; only the parent reconciles the map in CLOSE after adjudication. Bind approval to the reviewed snapshot/files, preserve genuinely open findings and compare delayed reports with later fixes. End with approved/in-review/not-reviewed or changes-requested scope, global gates and the next canonical slice; a review is not a runtime PASS.

## Pitfalls
A newer empty findings list cannot clear an older reproducer. Preserve every concrete finding and failed evidence with its disposition. Exact snapshot review is distinct from product QA, tooling smoke and visual approval. No-rerun historical readback must observe every actual evaluator path; never invent terminal records or normalize retained failures for green.

## Verification
All scoped acceptance criteria accounted for; blockers resolved or explicitly BLOCKED/NOT_RUN. Commands/exit, snapshot, limitations and cleanup must be recorded. Integration and closure belong to the parent after the required reviews and QA; a developer report cannot approve itself. [Private NSS recovery](references/private-nss-audit.md) applies only to a demonstrated resolver prerequisite failure.

## Referințe la cerere

- [ui-browser](references/ui-browser.md)
- [postgresql-fixtures](references/postgresql-fixtures.md)
- [ipc-process-packaging](references/ipc-process-packaging.md)
