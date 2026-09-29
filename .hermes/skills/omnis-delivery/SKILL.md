---
name: omnis-delivery
description: "Use when delivering an Omnis implementation slice."
version: 0.1.1
author: OmnisAI (KovacsEmanuel), Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [omnis, development]
---

# Omnis delivery

## When to Use
Implement a ticket, fix a regression, resume a slice, or coordinate a phase. This is the development workflow, not an autonomous assessment run.

## Prerequisites
Read repo `AGENTS.md`, the relevant plan ticket/gate and actual code. Resolve paths from the git root. Use only the available Hermes tools; role templates describe assignments, not extra tool APIs.

## Procedure
1. Use `terminal` for status/base SHA and `search_files`/`read_file` for the existing path. Account for dirty files before editing. Identify one acceptance criterion that the slice can demonstrate.
2. Write a short task contract: goal; non-goals; inputs; allowed files; observable success/failure; exact verification; rollback. For nontrivial work keep it in the task notes or commit body. If the contract changes, record why before expanding scope.
3. Choose the smallest end-to-end behavior: one persistence action, one event path or one validated operator action. Do not scaffold all future layers in advance. Separate discovery spikes from shipping code.
4. For behavior changes, reproduce RED, implement GREEN and refactor only with green tests. Preserve the failing assertion and actual output for the change record. Use a clean scratch/worktree for experiments; never present its substitute data as a production result.
5. Parallelize independent research/review; split writers by worktree/file ownership. Delegate with a bounded acceptance contract from `templates/task.md`. Findings return to the parent; a child summary alone is not integration evidence.
6. Review the minimal diff, execute acceptance and regression checks, and commit the coherent slice immediately as required by AGENTS. Preserve separate commits for an independent corrective action, documentation decision or dependency upgrade.
7. At a phase boundary run its actual gate, record passed/failed/blocked/not-run individually, and name the next unblocked slice. Never unlock a safety gate merely because prerequisite documents exist.
8. If the canonical gate is unsafe or lacks prerequisites, perform one read-only preflight, run only bounded safe checks, and record `BLOCKED`/`NOT-RUN` with the exact reason. Do not rerun the same partial suite to satisfy a Hermes verify-on-stop nudge, rename a partial target to `check`/`test`, or claim that focused tests close G00. Fix the prerequisite or hand off the blocker; do not keep editing a test oracle while the product acceptance row remains unchanged.

## Working stance
Use hypotheses instead of confidence claims; prefer removing accidental complexity over adding abstractions; measure before optimizing. Keep unrelated cleanup out of a feature. After two failed repair hypotheses stop repeating edits: inspect the failure mechanism, narrow the reproducer, then revise the plan. A blocker is a legitimate outcome, not permission to fake success.

## Pitfalls
- Audit cross-layer delivery before a session handoff: map each requested UI surface/action to its authoritative projection or command, persistence owner/migration, ticket and positive/negative acceptance. A navigable prototype and prose policy do not establish API behavior.
- Check gate dependencies as a graph, including bootstrap assets, schemas, configuration and test harnesses. A phase cannot require a component first delivered by its successor. Separate repaired-build admission for isolated tests from integrated boundary certification; never solve the cycle by marking the boundary safe or using a rejected dependency.
- Bound the first increment to a working observable artifact and real prerequisites, not every planned directory. Distinguish API, dashboard and assessment readiness; inert startup also excludes incidental provider validation, discovery/pricing and token refresh.
- Do not use automatic worktree defaults when local commits are ahead of remote. Use `terminal` with `git worktree add -b <branch> <new-path> HEAD` after reviewing the base.
- Do not load the entire skill catalog into each child. Give it the contract and the few relevant skills/files.
- Prompt wording cannot enforce commits or make side effects reversible. Git readback and external-state checks remain necessary.
- Name the product command and acceptance row advanced by each slice. If two review/repair cycles improve only harness evidence without advancing that row, checkpoint the WIP honestly, stop expanding the harness, and choose the next product or prerequisite slice. A blocked process proof remains `UNCERTAIN`, not an invitation to simulate a clean result.
- Project-local `.hermes/skills/` are versioned repo files, not the active profile's personal catalog. If `skill_manage` cannot find a project skill, use `patch` on its repo `SKILL.md` instead of creating a duplicate personal skill; verify with `skill_view`, then stage only the intended repo path.

## Verification
Every claimed acceptance criterion has real output; every intended change belongs to a verified commit; independent review issues are resolved or explicitly block delivery. A fresh session can recover the decision from Git and versioned notes, without chat history.
