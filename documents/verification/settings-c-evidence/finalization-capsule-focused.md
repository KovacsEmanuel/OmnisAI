# Independent focused SOURCE review — Settings capsule and E2E callers

**Verdict: APPROVED_SOURCE_SCOPED_COMPOSED. Findings: none in the reviewed delta/callers.** This removes no SOURCE-review blocker to the parent's admission of bounded real QA and native UI verification. It is not an integration decision, a passing aggregate gate, runtime proof, or visual acceptance.

## Admission and exact freeze

Requirement → consumer → risk → decision: the current `1fe771c` presentation contract (`web/design/settings-final.md:49–71`, UI spec §161) requires a minimal truthful Input/Output/Cost disclosure, no normal operation diagnostics/repeated success, and persistent actionable recovery. Review the existing Settings render, component tests and both affected real E2E callers for lost identity, hidden recovery or weakened assertions before admitting real QA. No new harness, framework or product scope.

Main HEAD: `51eec4e776219b40d8439947a502af7c6ea5c7f0`. QA HEAD: `65ae0697d0cc5bc4fe7a00ad3f563866f5055e5e`. Frozen WIP manifest: `/home/kali/.hermes/cache/scratch/settings-capsule-candidate.json`. All five files' Git blob, SHA256 and byte length matched the manifest at start and end; both HEADs also matched at end.

| Root/path | Reviewed Git blob | SHA256 |
|---|---|---|
| Main `web/src/features/engagement/SettingsModelsPage.tsx` | `a8445362661450143ba163c5ced3c99b60c2f791` | `f8e28bbe7381e931ed8236cdae7f2c48f232aedf25d6d0cc163408834c2e6b20` |
| Main `web/src/features/engagement/SettingsModels.module.css` | `1c93dde6d2c40409fe3c961dfdfb548acf8550ee` | `54f0159f9da1f7a19275bb86da26d7cb0a2642f2452e70d8764565d454358f7e` |
| Main `web/src/app/SettingsWizard.test.tsx` | `e3722b5211865b9fcaacdd5563926726ff9b40a3` | `d6863c4d772bc4bbf62c5bdd5e443f968d2f539460af05b42bc5971dda7b6005` |
| Main `web/tests/e2e/settings-models.mjs` | `ea7344835a426cae1354f6a20320036d13bb0072` | `b8bfd22c0f0e849c131de0abdc7646bbd3f5e4ec6ff7fbd97d71541d6cb130e3` |
| QA `/home/kali/.hermes/cache/scratch/fqa-a488b26/web/tests/e2e/settings-models.mjs` | `2260a1606af86039049dd2af8e2f0db78ba9fc05` | `4c441ddbaa51d85d4d5f877d6ba42544deac3406bb730486149836a083d73819` |

QA Python fixture SHA256 remained `34cf202c633a42710ba291dfc668be24c3148d2de0663f001041169667843dce` at both checks. Its original `c579f89` SOURCE approval in `finalization-controls-review.json` remains composed, not reissued as fresh runtime evidence.

## Composed approvals and dispositions

Read the existing R1/R2 focused original reports and the active register. Preserve their unchanged `ca33c1a` scope and historical failures. **R1-F01, R1-F02 and R2-ACTIVE-UNKNOWN-01 remain CLOSED_SOURCE_SCOPED**, not reopened by removal of UI diagnostic text. Ordinary Git diff shows this Page delta is render-only; pre-render logic, `operationControls` and `entryStatus` are unchanged. No marker/assertion helper was introduced. No API/backend or wizard ownership behavior changed.

The render still delegates active Read/Cancel through the existing operation owner. FINISHED/UNKNOWN retains history and permits separately consented new work; genuinely active B outranks terminal A; historical selection stays disabled during B; pending admission, NEEDS_RECONCILIATION, generation/revision and unsent-continuation fences remain unchanged. Adapted tests retain exact endpoint, operation identity, state/revision, fresh unchecked consent and write-count assertions rather than relying on deleted UUID/state text.

## Requirement → code → assessment

- **Truthful minimal disclosure:** Page `:361–388`, CSS `:28–33`; component tests `:30–87`. Uses native row button/`aria-expanded`/`aria-controls` and a labelled `dl` with Input/Output/Cost. Nullish fallback preserves actual zero and unknown independently; no invented currency or raw ACK. Exact matching model name is not printed twice. Matching successful results have no redundant success paragraph, diagnostic disclosure or unnecessary history Read. Existing 44px button rule is retained; changed CSS selectors have no other consumers. Keyboard behavior and zero writes on disclosure are asserted.
- **Actionable context not swallowed by the capsule:** Page `:329–333,373–387`. Active Read/Cancel remain outside hidden details through unchanged controls; terminal UNKNOWN also retains its inline Read outside disclosure. Stale/mismatched saved checks, requested/observed mismatch (React-escaped text), failed/incomplete/cancelled result, truncation and partial usage remain contextual. Failed/stale/mismatched historical Read remains available on expansion and still uses `checkSelectionBlocked`/`readCheck`; the spec specifically requires closed-state access for active/unconfirmed recovery, not a redundant Read for every successful record. Orphan recovery loses only diagnostic UUID presentation, not the receive-only controls.
- **Hidden-toast oracle correction is semantically appropriate:** reviewed committed main `72d1397` and QA `65ae069` diffs, not just their current uncommitted capsule changes. Main `:16` / QA `:19` set `includeHidden: true` on BOTH complementary/status segments. These assertions establish exact passive confirmation text, not toast visibility. This matches Page `:118–132`, where confirmations intentionally yield to controls/focus with `visibility:hidden`. Main Reload now requires persistent recovery absent (`:200`) while preserving settings/assignment readback; the prior revision-conflict recovery must still be visible (`:194–195`). QA exact receipt recovery still verifies the actual matching receipt, absence of persistent recovery (`:182–190`) and no resend. Duplicate catalog notification checks now include hidden notifications, making the absence assertion stricter. No critical state/control visibility assertion, wait/deadline, worker count or selection was relaxed.
- **Canonical positive E2E is not weakened by deleting UI UUID/ACK:** main `:256–328` captures both actual Start requests after exact consent, checks their generation/distinct identities, waits for two Connected rows, reads both exact history and latest entry endpoints, compares them, and binds entry/connection IDs and revisions, requested provider and requested/observed model, FINISHED/COMPLETED/current and exact backend ACK. Usage definitions are compared to those real readbacks in the corresponding row, including after reload; exact history must remain byte-for-JSON-value equal. Backend identity replaces deleted UI diagnostics without losing real-operation proof. Existing 32-model coverage, assignment preservation and fresh-tab checks remain. New explicit disclosure-keyboard assertions complement native semantics.
- **Controls QA preserves authentic identity/SENT/no-resend boundary:** QA capsule delta `:265–270` changes only the removed diagnostic assertions to absent UUID/details and actual terminal usage values. The real Start/Cancel/reload/read/reply-loss checks remain. Both terminal readbacks retain exact IDs/revisions/outcomes; active B remains checked RUNNING/revision2 after attempted disabled A history click; Cancel targets B with revision2 and settles revision4; old A is unchanged; exactly two Starts/two Cancels and no resend remain asserted (`:275–330,379–383`). Unchanged Python-owned SENT/TLS, thirteen-table census and API restart controls retain their prior scoped SOURCE approval; they were not executed here.

## Independently executed verification

Pinned Node returned `v24.21.0`. Both absolute E2E paths passed `node --check` (exit0). `git diff --check` passed in both checkouts (exit0). Main cached diff was empty; final statuses retained exactly the original four modified main paths and one modified QA JS path, plus pre-existing untracked paths. No staging or repository edits.

From `/home/kali/OmnisAI/web`:

```sh
NODE_ENV=test /home/kali/.local/share/omnis-toolchains/node-v24.21.0-linux-x64/bin/node /home/kali/OmnisAI/web/node_modules/vitest/vitest.mjs run src/app/SettingsWizard.test.tsx --no-cache --reporter=verbose -t 'expands a minimal|keeps actionable|keeps .* recovery separate|expands history without replacing|recovers the actual active check|remote UNKNOWN with local|preserves receive-only recovery for an orphan'
```

**Exit0: 22 PASS, 68 not selected, 90 collected; one file; 3.72s total.** Passed/skipped counts independently parsed from verbose assertion lines and matched the summary. This exercises the changed capsule known/unknown/zero and contextual cases, adapted history/active identity checks, both UNKNOWN lifecycle states, orphan recovery and closed active controls through existing App/jsdom HTTP doubles. It is SOURCE evidence only. Log: `/home/kali/.hermes/cache/scratch/settings-capsule-independent-source.log`.

## Limitations and handoff

- No new concrete blocker, reproducer or minimal fix is proposed; findings list is empty for the exact five-blob scope above. Parent remains responsible for adjudication, integration and effect admission.
- The parent's full default web gate remains **NOT_PASS**: both reported aggregate failures are retained, including capsule bootstrap/library readiness and other existing fixture timeouts. The isolated result here neither diagnoses every aggregate failure nor turns that gate green. No full rerun, timeout/worker/selection change or waiver was made. Separate read-only diagnosis remains with its assigned owner.
- Prior real controls QA **FAIL37.61s** at the legitimately hidden passive confirmation remains historical FAIL; Cancel scenarios were not reached in that run. Harness-only counter remains1. This SOURCE approval of the causal locator correction is not a successful retry.
- No real QA/browser/native UI, build/rollout, services, PostgreSQL, credentials/environment discovery, provider/model/target traffic, operator data, protected untracked content, commit/stage, docs/status/skill edits or self-integration. Reticle **NOT_INTEGRATED**; Chisel **BLOCKED_NO_GO**. No visual approval, runtime/global/T1/T2 closure or repair claim for metadata/supervisor UNKNOWN.
- Created only this original scratch report and the selected SOURCE test log (tool-owned output captures are auxiliary). Existing frozen product/caller/fixture bytes were unchanged at review end. The unavailable plugin-qualified Ponytail review skill returned not found; the user's supplied full-mode rules and the available project review/frontend/accessibility procedures were followed.

Skipped: aesthetic/global audit, unrelated already-reviewed logic, full-suite rerun and real-effect verification.
Risk: admission to the next bounded QA/UI stage is not acceptance; aggregate gate failures and real runtime/visual obligations remain open.
