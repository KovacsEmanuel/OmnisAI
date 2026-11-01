# R2 — reader-root fixture delta

**Verdict: APPROVED_SOURCE_SCOPED (R2), no concrete findings.** This is approval of the frozen test/reader-root delta only, not native qualification, CI success, product acceptance or permission to execute a native consumer.

## Exact identity

- Repository: `/home/kali/OmnisAI`
- Base: `34aebfbee5073186cde1724089e2bf5fe56818e0`
- Freeze: `0cba4760eb4495fceaf29846843d18c1a41fe6b8`
- Only changed file: `api/tests/test_contract_method_pg.py` (+19/-7).
- Blob: `ab5f129371162af6c27a118314dbf0c09fae02c0`, identical to author commit `461f9904f2d7fba6cc8486bea7d52670e24b57b1`.
- File SHA-256: `e79f9d136bb051e57a203a844d04d91cbd8f7db3cc103022b28175e8e6b3c4a6`.
- Author `/home/kali/.hermes/cache/scratch/h4e/frozen.diff` independently compared byte-for-byte with the frozen Git diff: identical.

## What this change does

The existing explicit SOURCE fixture now covers the two synthetic current-reader tests. The reader uses the already-existing fixed-default root constant instead of repeating its literal; an outside-root control and a default-root assertion prevent accidental broadening or leaked fixture state. The stale negative now proves it reached inventory checking without invoking origin.

## Scoped checks and conclusions

- **Default authority preserved** (`:54`, `:1981-1985`, `:7821`): constant still defaults to `/home/kali/.hermes/cache/scratch`; fixture is function-scoped and non-autouse. No environment-selected root or new configuration option. `historical_installed_plan` and `h03_prerequisites` retain their literal/native root contracts. Native review inputs remain bound to the whole module digest (`:7962-7968`); the new module hash invalidates older qualification flags.
- **Complete directly affected caller isolation:** externally selected `test_batch2_current_reader_actual_helper` (`:7123/:7127`) remains unchanged and skips absent its explicit artifact selection; synthetic positive/negative calls (`:7469/:7473`) and synthetic stale (`:7677`) now use `source_scratch_root`. Retained `legacy_native` negative (`:7623`) and `h03_prerequisites` (`:8027`) do not acquire that fixture. All five direct caller functions were enumerated by AST and inspected. No changed extraction namespace requires a new explicit constant binding; existing namespaces copy globals.
- **No bounds/security weakening** (`:7734-7955`): independently inverted the one root-expression substitution and excluded only the three changed/new test controls; the entire remaining module AST equals the base. Descriptor/type/digest checks, UID/mode/nlink, bounded no-follow material reads, canonical paths, inventories, exact source/export/installed/wheel bytes, interpreter pin, origin arguments/environment/timeout, redacted refusal and exception set remain unchanged. ZIP/wheel limits remain 327680 bytes, 1179648 aggregate bytes, 131072 bytes/member and 128 members. No added private-data rendering or credential access.
- **Default restoration exercised independently:** actual fixture callable with `pytest.MonkeyPatch.context()` passed normal and exception exits with TMPDIR initially present and absent (four combinations). Both constant and TMPDIR restored exactly.
- **Independent focused pytest:** four existing nodes in this order: `test_h04_current_reader_source_snapshot[None]`, `[outside-root]`, `test_h04_rejects_synthetic_stale_reader_before_origin`, `test_h04_native_scratch_root_default`. Actual result **4 passed, exit 0, 1.02s**. Full argv/cwd/exit retained in `command.json`; output in `pytest.log`. Seven warnings came from deliberately disabled plugin autoload (asyncio configuration/marks), not a candidate failure. Positive origin is the existing test double; no real origin execution.
- **Author evidence read, not rerun/promoted:** inspected original RED and GREEN logs/traces under `h4e`, including three original positive failures, outside-root RED locally, four RED failures under controlled foreign-root simulation, GREEN 25 and 100. Parsed collection files independently: original 98 IDs retained, exactly two additions, 100 identical GREEN IDs in plain/foreign runs; 33 native plus one retained collection item have zero SOURCE fixture bindings. These are overlapping selections, not additive test totals. The author logs explicitly label the foreign topology simulated and report default restoration; they do not establish remote CI or native execution.
- `git diff --check` exit 0. Final HEAD and pre-existing untracked paths unchanged; neither protected untracked file was opened. No repository edits, commits, push, PG, browser, provider, target, operator-state or native actions.

## Findings

None within the assigned delta and caller/default/bounds scope. There is no severity/file-line/reproducer/minimal-fix item to adjudicate from R2.

Not checked: full reader matrix independently (R1 owns it), full API/module gates, real installed origin, native/PG execution or remote CI.
Risk/limit: SOURCE and simulated topology evidence cannot qualify native execution; parent alone adjudicates integration and any later separately authorized gate.
