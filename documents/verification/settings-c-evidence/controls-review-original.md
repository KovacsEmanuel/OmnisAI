# Focused QA-overlay review — CHANGES_REQUESTED

What this change does: Replaces only the isolated `settings_ui` supplemental journey and its fixture oracles. It does not alter the product or replace the original UI4 proof on main.

**Admission: BLOCKED. Do not launch the real browser/API/PostgreSQL journey on this candidate. Fix findings 1 and 2 first, then perform focused source re-review and the one admitted live journey.** No product defect is claimed by these findings.

## Exact reviewed identity

- Worktree: `/home/kali/.hermes/cache/scratch/settings-controls-d37b4a54`
- Branch: `qa/settings-controls-d37b4a54`
- Base: `37baf0c421b3d10f6e47adc2d0df7fb75c8ea172`
- Candidate/HEAD: `a369430beea8e25b358f118243ef4326767fb983`
- Exactly two changed tracked files:
  - `api/tests/test_model_test_v2.py`: SHA256 `49d300fd93404d53b6b998bdde37776aeaa70bbb07a328a81b95ae8fe19bc49e`
  - `web/tests/e2e/settings-models.mjs`: SHA256 `0a27034549bf12c89e01a04465b7f8e9acd921d00de0270ffef9c596b47d6d21`
- Binary Git diff SHA256: `be60259dabea8a032f826b148fde7808f201dfb171b845ea6f48ccf4a4447625`
- Existing build manifest SHA256: `e2d646e4bcd898ff8bb9621c23e3ce055bd83b8f7a4e507e4935d19c45641fe1`.
- Start/end tracked status clean; pre-existing untracked `api/.venv` preserved. No source/index/commit/dependency changes were made by this review.

## Must fix

### 1. HIGH — Exact Provider label never matches the native select

**Location:** `web/tests/e2e/settings-models.mjs:109-114` (all four `getByLabel('Provider', { exact: true })` occurrences).

**Problem / reproducer:** The real wizard wraps the native select inside an implicit label, with both option texts inside that label (`SettingsModelWizard.tsx:112`). Playwright's label engine compares the full label text, which includes those option texts. Therefore the exact label `Provider` matches zero elements. The journey times out at line 109, before provider discard, catalog cancellation, response-loss recovery or model cancellation can be qualified.

**Verified SOURCE-only:** The installed Playwright core reports version `1.63.0`. Extracting its actual bundled injected selector engine from `lib/coreBundle.js` and evaluating it on a tiny offline jsdom control containing the same native label/select structure returned:

```text
internal:label="Provider"s -> 0
internal:label="Provider"i -> 1
internal:role=combobox[name="Provider"s] -> 1
internal:label="Brain"s -> 1
internal:label="API key"s -> 1
SOURCE_ONLY_JSDOM_PLAYWRIGHT_1_63_SELECTOR_REPRO_PASS
```

This is a selector-engine/source reproducer, not a live browser or product PASS. jsdom emitted its pseudo-element `getComputedStyle` limitations while evaluating the role selector; the assertions still passed. The explicit `htmlFor` assignment selectors and implicit input labels do not share this options-text failure. The already-corrected `Model to test` role selector is appropriate.

**Minimal fix:** Replace these Provider locators with `wizard.getByRole('combobox', { name: 'Provider', exact: true })`. No product change, DOM wrapper, new dependency or larger harness is needed.

**If skipped:** One doomed effectful QA attempt with no evidence for the remaining controls.

### 2. HIGH — Command-table total ignores all six catalog commands

**Location:** `api/tests/test_model_test_v2.py:656-658`.

**Problem / reproducer:** The new assertion expects the entire `model_command_v2` table to contain only the entry Start and Cancel (2 rows). The same actual producer also stores every catalog Refresh and Cancel in this table. `provider_catalog_runtime.py:188-195` calls `store.command` for both catalog mutation types; `model_test_store.py` implements that shared durable command store. The overlay itself requires five catalog refreshes (`test_model_test_v2.py:606`) and one catalog cancel (`settings-models.mjs:122`), in addition to one entry Start and one entry Cancel. A successful journey therefore produces **8 rows**, not 2.

The source-derived arithmetic was executed without DB effects:

```text
catalog_refreshes=5 + catalog_cancel=1 + entry_start=1 + entry_cancel=1 = 8
```

Catalog commands use `operation_id=NULL` (`provider_catalog_runtime.py:194`); entry Start and Cancel reference the one real operation (`model_test_runtime.py:347-349,478-479`). This explains why an operation-scoped count of 2 would be legitimate but the current unfiltered total is not.

**Minimal fix:** Change the unfiltered exact total to 8. If retaining a separate assertion for the two entry commands, scope that assertion to the exact operation ID (or non-null operation IDs in this fresh one-operation fixture). Do not weaken the table-total oracle to a lower bound.

**If skipped:** Even after fixing the Provider selector and successfully exercising every control, the final DB assertion deterministically rejects the correct result.

## Other reviewed boundaries — SOURCE only

- Read the complete two-file diff plus the actual `SettingsModelsPage.tsx`, `SettingsModelWizard.tsx`, `SettingsAssignments.tsx`, provider registry/key/catalog producers, entry admission, operation cancellation/settlement/view and migration columns. Remaining new matchers were compared with those rendered labels, regions, summaries, button names and state text; no additional concrete selector blocker identified.
- Response loss is causal: `route.fetch({ maxRetries: 0 })` reaches the actual API, verifies its real successful command/operation identity, then aborts only browser delivery. Exact command receipt recovery and same-operation status read do not synthesize JSON or restart inference. The write census rejects mutation resend.
- The model peer holds the actual POST response. Before owner cancellation, the fixture waits for the actual peer event and checks committed SENT=1 and system state RUNNING. Owner cancellation is outside the physical write lock; response release is in the owner-call `finally`. Runtime producer establishes PENDING revision1 -> RUNNING2 -> STOPPING3 -> FINISHED4; cancellation yields `CANCELLED`, outcome `UNKNOWN / CANCELLED_OR_STOPPED / ABSENT`, and `RESERVED,SENT,SETTLED`. Those SQL column names and payload keys are real.
- Catalog cancel uses the existing owner/drain producer and the held first metadata page. Five explicit refreshes imply nine metadata GETs (2+1+2+2+2), plus one inference POST. The frozen ordered TLS list and seven Settings writes agree with the journey; overlapping commands are not attributed using global I/O deltas.
- Registry/key producers support three stable entries, five entry revisions, two registry saves, five key/selection commands, registry revision2 and connection revisions1->2->3->4. Default00/cap64 and Brain01/cap37 remain at selection revision1 with their original connection revision1; no silent assignment rewrite is expected. Replace/Update and final stale disabled Test/Save controls are consistent with product handlers.
- The existing 13-table full census, restart read-only equality, API/driver owned-child cleanup and deadlines are unchanged (`api/tests/test_web_e2e.py:278-383`). All product source, runner, schema, Make/config paths are unchanged by the two-file diff. This does not certify runtime cleanup under failure or perform a new product integration review.

## Execution and limits

- `git diff --check <base> <candidate>`: exit0.
- `node --check web/tests/e2e/settings-models.mjs`: exit0.
- Installed Playwright selector-engine + offline jsdom reproducer: exit0, SOURCE-only.
- Hashes, exact changed-file census, unchanged handler/runner paths and final Git status verified with real command output.
- Shell `node --version` was `v22.22.0`; the project manifest specifies Node `24.21.0`. The successful local selector reproduction is not a pinned runtime-QA claim; parent must retain the proper execution environment for live QA.
- No PG, API, actual fixture/browser journey, network/provider requests, spending, full suite/build, original UI4 rerun, canonical rerun, external agents or personal credential files were used. Reticle: NOT_RUN/source review only. Chisel: BLOCKED_NO_GO.

**Verdict: fix 1 and 2 first. Not APPROVED_SOURCE_SCOPED; one actual live control journey is not admitted on `a369430`.**

Not checked: live behavior, rendered visual quality, actual cleanup/restart effects, canonical2 completion or original main evidence re-execution. Those remain with the parent after the two concrete source blockers are fixed; no Prompt B/T2 or product-source work is authorized here.
