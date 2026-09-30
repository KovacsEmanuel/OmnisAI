---
name: omnis-project-status
description: "Use when orienting or closing an Omnis work slice."
version: 0.1.1
author: OmnisAI (KovacsEmanuel), Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [omnis, development, status, handoff]
    related_skills: [omnis-delivery, omnis-review-qa]
---

# Omnis project status

Maintain one evidence-backed view of the whole project at implementation/review handoff.
This is a development procedure, not a runtime pentest skill or a second implementation plan.
Use repository Git and versioned project memory; no new service, dependency or model call.

## When to Use

- At the end of every implementation slice, subphase, phase or review prompt, including a blocked handoff.
- At session entry, after context loss, or when the operator asks where Omnis stands.
- To reconcile a concrete change of plan, implementation, evidence or review status.
- Not for marking the entire MVP complete from one gate, reopening accepted design, or implementing the next phase without authorization.

## Modes

- **ORIENT (read-only):** default at session entry/review. Read Git/map/evidence, report current location and discrepancies. No files changed, services, credentials, fetch/push, or approval transitions.
- **CLOSE (predare):** after an authorized implementation/review outcome, reconcile only affected status rows and evidence. The parent owns the integration decision. If nothing factual changed, report the fresh snapshot **fără commit gol**; do not manufacture a status edit.
- A mid-task update stays ÎN LUCRU/IN_REVIEW, not DONE. At a read-only prompt's end use ORIENT rather than force a write.

## Prerequisites and authority

Resolve the actual git root. Read AGENTS.md and CONTRIBUTING.md, then
`documents/verification/implementation-status.md` and the relevant evidence it links.
Architecture decides behavior; plan §4/§4.2/§4.3/§15/§19 decides order, gates and MVP/post-MVP scope.
The map is a derived projection; do not create another backlog or global-memory copy.
A stale/contradictory source is a discrepancy to adjudicate, not permission to choose the most optimistic status.

## How to Run

Use `terminal` with `workdir=<repo>` for the following read-only snapshot (argv/commands contain no credentials):

```text
git status --short --branch
git rev-parse HEAD
git diff --stat
git diff --cached --stat
git log -12 --oneline
git log -1 --format='%H %s' -- documents/verification/implementation-status.md
git worktree list --porcelain
git for-each-ref --format='%(refname:short) %(objectname)' refs/heads refs/remotes
```

Inspect affected diffs with `terminal`; read files with `read_file`/`search_files`.
Local remote refs are cached observations, not a fresh remote CI/push result.
Other branches/worktrees may contain unintegrated work; identify it without switching,
merging, resetting, stashing, adopting or crediting it to the active branch.

## Procedure

1. **Locate:** account for HEAD, branch and all preexisting tracked/untracked changes. Preserve ownership; a dirty checkout is not proof the last gate covered those bytes. Completion criterion: exact snapshot and scope named.
2. **Orient:** read the map's summary, the active SL/B row and its dependency gate; inspect the relevant canonical plan/architecture sections and verification entry. Inspect code/tests when the claim is not established. Reconcile all SL IDs, E waves, foundational P0, milestones and execution-unscheduled breadth when the plan changes. Completion: no missing/remapped row or invented phase/progress percentage.
3. **Separate axes:** code IMPLEMENTED/PARTIAL/NOT_IMPLEMENTED; proof PASS_LOCAL_RECORDED/PARTIAL/FAIL/BLOCKED/NOT_RUN; review NOT_REVIEWED/IN_REVIEW/APPROVED_SCOPED/CHANGES_REQUESTED. Never turn documentation, harness, static review, a commit message or a test count into live product PASS. Require revision, command/exit, boundary and limitations for each proof promoted.
4. **Adjudicate review:** bind report ID, reviewed snapshot (commit or blob/diff), files, scenario and verdict. A subagent proposes findings; the **părinte** reproduces/adjudicates relevant findings and accepts integration. A report arriving **întârziat** is compared with the fixes and later review before changing current status. Do not discard a genuinely new reproducer merely because its issue ID is old. No approval inferred from silence, dispatch or a passing unrelated test.
5. **Reconcile CLOSE:** update affected rows and summary in the existing map; put detailed decisions/failures in the slice's verification register and link it. Update README/plan §19 only when their current status actually changed, retaining historical failures. If an authorized plan adjustment is needed, amend the canonical source first and then its projection; otherwise record a proposal/blocker. Do not edit protected files through a bypass or copy secrets/raw private logs into the map.
6. **Verify:** use `terminal` for `python -m unittest discover -s tests/documentation -v`, `python scripts/render_docs.py --check` and `git diff --check`. Regenerate HTML only for changed normative Markdown. Run the affected product checks when code changed; documentation checks do not rerun or transfer old product gates. A reviewer operating read-only returns the proposed delta to the parent rather than writing the shared map.
7. **Commit/readback:** commit only intended coherent changes, including the map/evidence delta, under AGENTS rules. Read back `git show --stat --oneline HEAD` and status before reporting. Store the tested/reviewed revision, not an impossible self-reference to the commit containing the status edit. If HEAD changed during review, compare the affected scope before accepting it; an uncommitted intended change prevents a DONE claim.
8. **Report:** finish with the compact Romanian block in `templates/handoff.md`: current location, delta, approved/pending/not-approved review, real proof and limit, open gates, exact next slice, MVP/post-MVP outlook, Git and owned cleanup. Link the full map instead of printing all rows on every prompt. Completion: the operator can distinguish what works, what is merely planned and what needs review.

## Pitfalls

- **Skill nu este enforcement:** these are instructions loaded by the agent, not an automatic exit hook. Wire this skill into project delivery/review rules; **nu porni cron**, plugins, auto-commit or a background watcher to simulate reliability.
- A source-reviewed skill is not imported/execution-certified; a development skill is not a product feature. Keep E1–E4, B21m and EXECUTION_UNSCHEDULED separate from mandatory MVP branches.
- A failed/blocked task still receives a truthful handoff; never clear open findings or uncertainty to make the map green. Do not relaunch suites just to appease a repeated verification nudge.
- Distinguish the immediate corrective action from the next new SL in the plan. A newly confirmed defect reopens acceptance on its owning slice as CHANGES_REQUESTED; keep historical scoped PASS, but do not send the operator past that blocker or invent another phase. Reusable primitives do not mark a future product outcome partially delivered by themselves.
- Global conversational memory is not the project ledger. Git/history plus canonical docs and verification entries must suffice after a fresh session. Scratch reports may expire: persist the adjudicated conclusion and limits, not only a temporary path.
- Changes to this map do not authorize targets, provider spending, services or deployment. Do not inspect private credentials to improve status completeness.

## Verification

The map's SL/E IDs and phase labels match the canonical plan, links resolve and code/proof/review remain independent. Test the instructions structurally and exercise a real read-only Git snapshot; neither proves future model compliance. Verify project-local discovery in a fresh repo-bound Hermes process without invoking a model. Preserve old PASS at its actual revision, report changed/unverified scope honestly, and leave the next product gate closed until its own evidence exists.
