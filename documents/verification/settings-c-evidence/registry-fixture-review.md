# Independent focused review — heartbeat / disposal fixture repair

**Verdict: APPROVED_SCOPED.** Findings: none. Same existing `test-provider-settings-pg` consumer may be retried on a NEW owned fixture after the parent's normal effect preflight. This is source-review approval of the one-file repair, not PostgreSQL PASS, integration, or approval of new authority.

## What this change does:

Testul păstrează lease-ul prin metoda reală `InstanceService.heartbeat`, la intervalul existent de 1s. Așteaptă terminarea taskului fiecărui owner înainte de release/handoff și execută disposal chiar dacă release eșuează, fără să ascundă eroarea primară.

## Snapshot / scope

- Repository: `/home/kali/OmnisAI`; HEAD/base `ed9091caeff29572d9f42861ae548a6094f732d6`.
- Frozen manifest SHA256: `4cbef237ca8c91a67a028c05a994fd417dfd57d248becf3bd053d013d033fdd2`.
- Only reviewed delta: `api/tests/test_provider_key_api.py`; SHA256 `115cb08f485019ce6e5db4bf2c63fd439367aaebc62e9c5f4b233b9a774c1ed7`; blob `9260f7f98045f5e1a5c85901dca08c78874a92f5` (manifest).
- Test-only patch SHA256 `6e9f2e0bc41d978f6493ee28b295ab9f6bc44d891e0de617a9786dc3ca00c3e7`; reverse-apply check passed.
- Prior 42 unchanged files and prior product approvals are inherited from the parent's exact comparison; no repeated product audit. Shared checkout already contains the uncommitted candidate and protected untracked inputs. Neither was modified; protected contents were not read.

## Requirement → code → disposition

| Requirement | Readback | Disposition |
|---|---|---|
| Faithful lease authority, not TTL inflation or bypass | Test lines41–50 calls real heartbeat; service lines299–309,334–375 still require live matching owner/epoch and enforce the existing5s lease; supervisor lines213–222 uses1s cadence | APPROVED. Only expected wait timeout is caught; heartbeat errors propagate. No mocked authority, reacquire-on-loss or policy/deadline change. |
| Settle tasks before changing owner | Test78–82,393–408,420–421; TaskGroup encloses LocalControl; stop event is set before normal scope exit; previous TaskGroup finishes before release396 and acquire399 | APPROVED. Exception exits cancel/join the child. Renewal arguments bind owner/epoch values. Event reuse begins only after the old task has settled. Both owners must record a positive real heartbeat. |
| Preserve consumer assertions and restart readbacks | AST comparison against `test_provider_key_api.before.py`; original journey54 assertions remain, now56; whole file66→68; migration AST identical | APPROVED. No old assertion removed or weakened. Fresh owner/vault/control still reads the same durable receipt, page and selection. |
| Cleanup after setup/body/release failure or cancellation | Test38,52–53,397,422–433 | APPROVED. Nullable epoch avoids false release after failed acquisition; nested finally attempts engine disposal even when release raises. Cleanup without a primary propagates; with a primary, the same primary is raised with cleanup as cause, including cancellation. Catching BaseException does not convert failure into success. |
| No hidden consumer or transport replacement | Existing ASGI/private UDS/real-PG test body unchanged apart from lifecycle; LocalControl103–157 reviewed for entry/exit ordering | APPROVED within the focused scope. No new dependency, fixture abstraction, DB runner, provider call or service edit. |

## Executed independent checks

1. Git status/base/diff readback: exit0; dirty candidate identified, no stage/reset/commit.
2. Exact manifest/file/patch SHA256 checks, `git diff --check`, `git diff --cached --quiet`, `git apply --check --reverse /home/kali/.hermes/cache/scratch/hbfix/test-only.patch`: exit0. Hashes match the snapshot above; index empty.
3. AST assertion-preservation and migration-identity check: exit0. All66 original file assertions retained, exactly2 positive heartbeat assertions added; migration test unchanged. Initial reviewer counting assertion incorrectly applied the file-wide66 count to the first function and exited1; corrected scope showed journey54→56 and module66→68. This was a reviewer-check error, not a candidate defect.
4. Existing inert exact-source-block check, rerun without modification:
   `env -i HOME=/home/kali PATH=/home/kali/.local/share/omnis-toolchains/bin:/usr/bin:/bin TMPDIR=/home/kali/.hermes/cache/scratch/hbfix api/.venv/bin/python -I -B /home/kali/.hermes/cache/scratch/hbfix/check_cleanup.py`
   Exit0. Actual output:
   ```text
   7 cleanup cases passed: unconditional dispose; primary assertion/cancellation preserved; cleanup errors chained; unowned disposal
   Heartbeat loop: timed renewal, 2 settled owner scopes, positive counts, failure observed
   ```
   These doubles establish Python cleanup/loop behavior, not PG authority or physical cancellation completeness.

## Admission / remaining gate

The recorded previous PG failure remains FAIL:52PASS/1FAIL/1ERROR, exit2, release LEASE_LOST followed by disposal skipped and DROP timeout. The new lifecycle directly addresses that identified mechanism without changing product bytes or acceptance expectations. No surviving source blocker found for retrying the same53-case target on a fresh owned fixture. Do not require an already-passing PG run as a circular prerequisite for this admitted QA.

Parent retains effect preflight, fixture ownership, bounded command, cleanup/readback, fresh PG result and integration. Carry harness-only counter1 forward; if the next harness-only attempt fails, apply the existing two-cycle stop/narrowing rule, not a third generic repair loop. Candidate remains uncommitted and not product-accepted pending green real PG.

Reticle NOT_APPLICABLE; Chisel BLOCKED_NO_GO. No DB, services, provider/target, PromptB/auth, protected input, repository edit or commit performed. Created only this original review report outside the repository.

Not checked: no fresh PostgreSQL execution, installed/runtime QA, unrelated source re-audit, or Ruff/mypy rerun (existing recorded results inherited).
Risk: scheduler/DB stalls can still legitimately lose the unchanged5s lease; the real fresh-fixture result and cleanup remain unproven until the parent's separate QA stage.
