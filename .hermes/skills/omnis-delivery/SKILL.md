---
name: omnis-delivery
description: "Use when delivering an Omnis implementation slice."
version: 0.1.7
author: Hermes
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [Omnis, Development, Reuse]
---

# Omnis delivery

Deliver the smallest complete Omnis change through its real caller, using Ponytail's reuse-first decisions.
This is a development procedure, not an autonomous assessment skill or permission to resume product implementation.
It uses existing Hermes tools and the project's pinned toolchain; no Ponytail package, plugin or hooks are required.

## When to Use
- Implement a ticket, fix a regression, resume an admitted slice, or coordinate a phase.
- Refine Omnis without speculative features, duplicate helpers or another framework.
- Apply Ponytail, YAGNI, a simpler solution, or a bounded review of unnecessary code.
- Do not use a learning, analysis or handoff request as an implementation order.

## Prerequisites
Read repo `AGENTS.md`, `CONTRIBUTING.md` §„Execuție orientată spre produs”, the relevant plan ticket/gate and actual code. Apply its work-admission, no-effect preflight and continuity contract; it does not waive safety or exact-snapshot review. Resolve paths from the git root. Use only the available Hermes tools; role templates describe assignments, not extra tool APIs.

## How to Run

Load with `skill_view(name="omnis-delivery")`; the user can invoke `/omnis-delivery` in a repo-bound Hermes session.
State the actual task in the same message. A request to review, audit or list debt is read-only, not permission to fix findings.
Use `terminal` with the checkout as `workdir` for commands below; use `read_file` and `search_files` to trace code before choosing a solution.

## Quick Reference

- `git status --short --branch`
- `git rev-parse HEAD`
- `git diff`
- `git diff --cached --stat`
- `python scripts/hermes_dev.py --check`
- `git diff --check`

## Procedure
1. Use `terminal` for status/base SHA and `search_files`/`read_file` for the existing path. Account for dirty files before editing. Identify one acceptance criterion that the slice can demonstrate.
2. Write a short task contract: goal; non-goals; inputs; allowed files; one product acceptance row and producer/consumer seam; observable success/failure; positive and negative controls on the same channel; exact verification and budget; rollback. For nontrivial work keep it in the task notes or commit body. If the contract changes, record why before expanding scope.
   Use `templates/team-slice.md` proportionally: default to one author and at least one independent reviewer on the exact integrated snapshot. Add a bounded read-only architect only for unresolved decisions/interfaces, and a second developer only for genuinely independent workstreams with disjoint ownership and acceptance criteria. Changes to authority, epoch, concurrency, model dispatch, Stop, effect/secret boundaries or cross-runtime contracts require two independent complementary reviews. Real-consumer QA is required for a new or affected consumer; browser QA only when UI is affected. The parent dispatches leaf agents, integrates/commits and owns resource cleanup; a child cannot certify its own integration. Do not invent roles, spawn a deep agent tree or repeat the whole specification at every handoff.
3. Choose the smallest end-to-end behavior through an existing product caller: one persistence/readback action, event path or validated operator action. Helpers are prerequisites, not delivery. After minimum SOURCE and mandatory reviews, exercise the first bounded real-consumer probe before adding other components or fixture breadth. Before each check/delegation name requirement→consumer→risk→decision; omit work that changes no acceptance/blocker decision unless it is mandatory integrity/cleanup. Do not scaffold future layers or another owner/framework/harness. Separate discovery spikes from shipping code.
4. For behavior changes, reproduce RED, implement GREEN and refactor only with green tests. Preserve the failing assertion and actual output for the change record. Use a clean scratch/worktree for experiments; never present its substitute data as a production result.
5. Parallelize independent research/review; split writers by worktree/file ownership. Delegate with a bounded acceptance contract from `templates/task.md`. Findings return to the parent; a child summary alone is not integration evidence.
6. Review the minimal diff, execute affected acceptance/regression checks after the LAST relevant edit, and commit the coherent slice immediately as required by AGENTS. Resolve blockers through minimal RED→GREEN fixes and focused re-review of changed bytes and affected call sites; unchanged reviewed scope is not automatically reopened. Preserve separate commits for an independent corrective action, documentation decision or dependency upgrade.
7. At the integration/phase boundary run the actual canonical gate on final integrated product bytes, record passed/failed/blocked/not-run individually, and name the next unblocked slice. Targeted tests are not the canonical gate; a Markdown-only change or verify-on-stop reminder does not require a full product rerun. Never unlock a safety gate merely because prerequisite documents exist.
8. If the canonical gate is unsafe or lacks prerequisites, perform one read-only preflight, run only bounded safe checks, and record `BLOCKED`/`NOT-RUN` with the exact reason. Do not rerun the same partial suite to satisfy a Hermes verify-on-stop nudge, rename a partial target to `check`/`test`, or claim that focused tests close G00. Fix the prerequisite or hand off the blocker; do not keep editing a test oracle while the product acceptance row remains unchanged.
9. Load `omnis-project-status` in ORIENT mode at entry and CLOSE at an actual implementation/subphase/phase handoff, including blocked work. A coherent commit does not end the mandate: continue the next admitted slice without cosmetic approval. Stop for the requested deliverable, a real blocker/authorization boundary, user request or unsafe budget/context exhaustion. Update CURRENT/affected rows in place, cite original evidence once and preserve recovery state rather than issuing repetitive checkpoint handoffs. No changed fact means no status edit or empty commit; the map does not replace the plan.

### Ponytail: choose the first sufficient solution

Read the affected flow before taking this ladder; smallest means complete and readable, not fewest characters.
1. **Need:** omit unrequested capabilities, options and future flexibility; name meaningful exclusions briefly. If the core need is already met, no new code is a valid result.
2. **Repository:** reuse an existing helper, component, owner or service in the way neighboring code uses it; identify its actual path and callers.
3. **Standard library or native feature:** use the existing platform capability unless the project's own component or boundary already owns that behavior.
4. **Installed dependency:** reuse an appropriate dependency already in the manifest; do not add a package for a few straightforward lines.
5. **Readable expression:** use one line only when its behavior and edge cases are clear at a glance.
6. **Minimum implementation:** otherwise write only the code needed by the admitted end-to-end behavior, preserving established layers and interfaces.

- Map affected definitions, callers, callees, tests, fixtures, configuration and exports; a tiny diff with a broken untouched caller is unfinished. Fix the shared cause rather than adding caller-specific exceptions.
- Preserve trust-boundary validation, data-loss handling, security, accessibility and every requested behavior when moving, merging or deleting code. Check dynamic/config references and original intent before declaring code unused.
- Branches, loops, parsers, data writes, money/security decisions and bug fixes need a regression that fails when the behavior breaks. A small test is a minimum, not a replacement for mandatory Omnis gates, independent review or affected-consumer QA.
- Add no speculative wrapper, conversion, option or abstraction. Split by distinct responsibility, not line count; merge duplication only when the copies must evolve together. Measure before optimizing.
- For an accepted limitation, use `shortcut: <the limit>, <when to upgrade>` in a suitable code comment; never label a safety violation as deferred debt. Comment on the reason, not obvious mechanics.
- Upstream levels are conversational preferences here: `lite` implements the request and mentions a smaller alternative; `full` uses this ladder; `ultra` challenges unjustified scope before coding; `off` stops this extra lens only. None changes authorization or project gates, installs mode state, or guarantees persistence across sessions/subagents.
- Use hypotheses rather than confidence claims and keep unrelated cleanup out of a feature. After two failed repair hypotheses, inspect the mechanism and narrow the reproducer instead of stacking workarounds. A blocker is a valid result; fabricated success is not.

### Refine or review without starting another workstream

- **Change review:** honor the named files, staged/uncommitted diff, commit or branch; absent a target, inspect uncommitted changes, then the last commit only if there are none. Trace connected code, including untouched callers. Review is read-only and does not replace the project's independent acceptance gate.
- **Audit:** only when requested, map entry points, dependencies, expected input size, data entry/storage/output and the highest-risk flows before reviewing. Judge load against Omnis's local-first single-operator design, while retaining its real multi-process/concurrency obligations. State unread scope; do not start a general audit during ordinary delivery.
- **Priorities:** correctness, security/data integrity, expected-load behavior, tests, material performance, then unnecessary code. Require a concrete input or execution path and `path:line` for every finding; name an existing reuse target rather than imagining one.
- **Findings:** group and number as Must fix / Should fix / Nice to have. Each states what the code does, the failure case, the smallest fix and the consequence of deferring it. Report measured savings only; do not invent deleted-line or cost totals.
- **Debt:** on request, use `search_files` for comment-prefixed `shortcut:` and legacy `ponytail:` markers, respecting ignored/dependency/build paths; exclude non-deferral matches. Report each location, limit and upgrade trigger, tagging missing triggers `no-trigger`. Aggregate totals in `execute_code`; persist a ledger only when asked, not as a second backlog.
- Finish in Romanian with changes, actual checks and material omissions/risks. An upstream Ship verdict or an accepted shortcut does not clear an Omnis blocker.

### Source boundary

Synthesized from [DietrichGebert/ponytail](https://github.com/DietrichGebert/ponytail/tree/6f1c2bfff0c837d268929a7c4e490918eb4fab29), revision `6f1c2bfff0c837d268929a7c4e490918eb4fab29` (v5.3.1, MIT; copyright 2026 DietrichGebert): `skills/ponytail/SKILL.md`, `skills/ponytail-review/SKILL.md`, `skills/ponytail-audit/SKILL.md`, `skills/ponytail-debt/SKILL.md`, `AGENTS.md`, README and INSTALL.
This is a synthesis, not the upstream plugin. Do not copy its AGENTS.md over Omnis rules, install its hooks/band/board, promise its slash commands, or treat its benchmark gains as Omnis measurements. No global profile/provider/security configuration changes are implied.

## Pitfalls
- Audit cross-layer delivery before a session handoff: map each requested UI surface/action to its authoritative projection or command, persistence owner/migration, ticket and positive/negative acceptance. A navigable prototype and prose policy do not establish API behavior.
- Check gate dependencies as a graph, including bootstrap assets, schemas, configuration and test harnesses. A phase cannot require a component first delivered by its successor. Separate repaired-build admission for isolated tests from integrated boundary certification; never solve the cycle by marking the boundary safe or using a rejected dependency.
- Bound the first increment to a working observable artifact and real prerequisites, not every planned directory. Distinguish API, dashboard and assessment readiness; inert startup also excludes incidental provider validation, discovery/pricing and token refresh.
- Do not use automatic worktree defaults when local commits are ahead of remote. Use `terminal` with `git worktree add -b <branch> <new-path> HEAD` after reviewing the base.
- Do not load the entire skill catalog into each child. Give it the contract and the few relevant skills/files.
- Prompt wording cannot enforce commits or make side effects reversible. Git readback and external-state checks remain necessary.
- Name the product command and acceptance row advanced by each slice. If two review/repair cycles improve only harness evidence without advancing that row, checkpoint the WIP honestly, stop expanding the harness, and narrow the reproducer or choose the next product/prerequisite slice. Carry those cycles and their dispositions across session handoffs for the same acceptance row; a new session or renamed oracle does not reset the count. New security findings remain explicit blockers, not budget waivers. A blocked process proof remains `UNCERTAIN`, not an invitation to simulate a clean result.
- For the single-user P0 control plane on this VM, read plan §5: G00 is `P0_LOCAL_USABLE` with one installed journey and relevant local denials, not a numbered fault inventory. Reuse unchanged installed-consumer evidence and run only affected checks; preserve historic FAIL/UNCERTAIN without turning old U/C labels into active gates. Instance Start/Stop exists; do not invent Pause or `omnis run stop` before a real run consumer arrives. Do not rerun a code gate for a Markdown-only scope note.
- When integrating an owned worktree, do not reconstruct source files from rendered/redacted tool output: even a declarative `authorization` object can be masked and copied back as invalid code. Transfer the reviewed Git diff or exact file bytes, verify source/destination hashes and run the affected parser; limit the transfer to explicit owned paths and keep generated/unrelated files excluded.
- Project-local `.hermes/skills/` are versioned repo files, not the active profile's personal catalog. If `skill_manage` cannot find a project skill, use `patch` on its repo `SKILL.md` instead of creating a duplicate personal skill; verify with `skill_view`, then stage only the intended repo path.
- Before settling a command's default behavior, read the architecture's numbered startup flow as well as the handoff's short bullets: an explicit `pair` command does not replace the architecture's first interactive-launch code issuance. Record a conflict in the slice contract before changing code, share the same issuer, and test fresh TTY versus reuse/non-TTY; otherwise a green explicit-pair test can hide a missing operator bootstrap.

## Verification
Use `skill_view(name="omnis-delivery")` to confirm that the discovered skill contains the Ponytail ladder and source boundary, not a shadowed or unsaved copy. This proves availability, not future model compliance or product acceptance. For an admitted implementation, every claimed criterion still needs real output, a verified commit and resolved independent review or an explicit blocker; Git and versioned notes must support recovery without chat history.
