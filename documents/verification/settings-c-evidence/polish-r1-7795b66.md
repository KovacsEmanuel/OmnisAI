# R1 — Settings C polish, exact-snapshot review

Verdict: **APPROVED_SOURCE_SCOPED**

Findings: `[]` — no concrete blocker found in the reviewed delta.

## Snapshot and scope

- Base: `0b882cbd7d90d247f130718ac877168267788963`
- Reviewed HEAD: `7795b66f1dd62f93043d430543d2450d6899b871`
- Diff SHA256: `8adc2be2ab2a3de357c23618e3ea4d46e03e69ae152fe254265fd339bd452957`
- Exact eight source/test identities and four built assets matched `/home/kali/.hermes/cache/scratch/settings-polish-freeze-yLnpHE/freeze.json`; its HEAD/status labels are precommit, not current Git labels. Final readback retained reviewed HEAD and no tracked modifications.
- Reviewed SettingsModelsPage, SettingsModelWizard, SettingsAssignments, SettingsModels.module.css, their three affected test files, and settings-models.mjs with affected helpers/callers.

## Review evidence and limits

The delta preserves independent assignment persistence, explicit default confirmation, exact provider/model identity before testing, unchecked consent/cost warning, saved-versus-tested distinction, stale/partial/UNKNOWN explanations, and active Cancel/readback. Native disclosures retain full valid assignment identities as secondary content; unavailable assignment identity remains outside the disclosure. No handler/API/dispatch change was found beyond shorter status text and presentation.

Inspected reference desktop/mobile images and author SOURCE desktop/mobile assignment plus mobile Review screenshots. The centered 900px house composition and Connection → Models → Review hierarchy remain; no visible blocker in those images. This is reference comparison, not universal accessibility or operator aesthetic approval.

E2E admission: installed `@playwright/test` is 1.63.0; actual caller supplies `expect.configure`. Bounded native-DOM probe using Chromium 153.0.8010.12 verified summary Enter open/close, `toBeFocused`, 2px focus outline, and `getByLabel('Model response')` on the actual paragraph markup pattern. Correct response matched; deliberately wrong response was rejected. Exit 0. Initial probe exited 1 because the probe omitted tokens.css, invalidating `var(--color-focus)`; corrected probe included tokens.css + global.css. This is a probe construction failure, not a product finding.

The real TLS fixture produces `OMNIS_MODEL_TEST_OK` (`api/tests/test_model_test_v2.py:330`). Traced run.mjs → runSettingsModels and Python settings_models_browser: existing API restart, full table census, no-resend and owned cleanup remain. Verified Makefile target and runner option definitions: `python -B ops/run_test_db_gate.py --check --target test-settings-models-ui-pg --timeout-seconds 600`; did not execute that command. Runtime success remains for the separate admitted QA stage, not a circular prerequisite or a claimed PASS here.

No repository, docs, skills, index or product files changed. Only this original scratch report created. Existing protected untracked paths were not read or touched.

Not checked: real API/PG E2E, installation/rollout, operator browser, provider effects, screen readers or full canonical gates. Reticle NOT_RUN (no instrumented runtime admitted); Chisel BLOCKED_NO_GO.
Risk retained: default check-web FAIL/cause UNKNOWN and canonical TIMEOUT3600/BLOCKED_BUDGET remain; source approval does not close runtime acceptance or authorize rollout.
