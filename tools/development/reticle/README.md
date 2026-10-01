# Reticle — isolated development QA

This package is an **optional internal development helper**, not part of the Omnis application/runtime. Source/artifact identities, licenses and exclusions are in [upstream.json](upstream.json). It is callable through Hermes `terminal`; no native Reticle tools or global MCP server were registered.

## Reproduce the accepted smoke

Linux, Node, `unshare`, `ip`, permitted user/network/PID namespaces and an existing Chromium/headless-shell executable are required. The helper refuses missing prerequisites; it never falls back to an unrestricted process.

From the repo root:

```sh
npm --prefix tools/development/reticle ci --ignore-scripts --omit=optional --no-audit --no-fund
uv venv --python 3.13 tools/development/reticle/.venv
uv pip sync --python tools/development/reticle/.venv/bin/python --require-hashes tools/development/reticle/requirements.lock
tools/development/reticle/.venv/bin/python tools/development/reticle/run_probe.py --browser /absolute/path/to/chrome-headless-shell
```

`TMPDIR` must point to an owned scratch directory (Hermes already supplies it). Every run stages the authored fixture into fresh scratch and prints `RUN_DIR=...`; runtime HOME, XDG, state, logs and temporary files stay there. The tool package is installed locally; do not use global npm or a remote shell installer. Retain evidence you need before scratch expiry; do not commit runtime homes or real application captures.

The accepted path starts a supervised local daemon, connects the actual MCP CLI and browser SDK, drives an increment, checks a state predicate and proves that an HTTP 500 is rejected even when the synthetic screen claims success. It also requires a successful POST `/api/ok`→200 network verdict and Reticle-captured method/URL/status for both the 200 and 500 calls. The failure must be `assertion_failed` on `net.present`, not an arbitrary `verified: no`. Cleanup checks both listeners closed. It contains no account, provider or third-party target call. `verification/mcp-smoke.json` is a parent-executed result, not a fabricated protocol response.

Independent review caught that the first reusable gate accepted any negative reason. A RED regression reproduced that false green, including missing capture and an always-rejecting verifier. `verdicts.py` and `tests/development/test_reticle_verdicts.py` now enforce the explicit positive/negative network controls; the actual browser/MCP probe was rerun after the correction.

## Important limits

- The CLI shortcut `verify --expect` navigates/reloads and was unreliable on the plain-HTML fixture (old state or disconnected session). The complete probe initially failed at session yield after that reload. Its real failure is retained in `verification/cli-reload-failure.json`; **no fix or acceptance of that CLI path is claimed**. The accepted smoke tests direct MCP on the connected session separately.
- Default telemetry is on upstream. The helper sets `RETICLE_TELEMETRY=0` and `DO_NOT_TRACK=1`; the independent background update check still needs network isolation. Cloud linking/sync, feedback and model exploration are not enabled.
- SDK error-body capture can expose data. This fixture deliberately captures synthetic bodies only; future Omnis instrumentation must explicitly disable sensitive captures and stay dev-only. Redaction is not a universal safety boundary.
- `.reticle/hooks.json` and dev-server commands are executable inputs; the fresh fixture copies neither arbitrary project config nor hooks. Never start it in an unreviewed downloaded project.
- This is network/process isolation, **not filesystem sandboxing of hostile tooling**. The helper and dependency code are trusted reviewed local tools; Chisel-like untrusted effects need a separate filesystem boundary.
- Measured host: Node 22.22.0, CPython 3.13.12, Playwright 1.60.0, Chromium headless shell 148.0.7778.96. These are development-probe versions, not an amendment of the future application/executor stack. Full Chromium variants crashed in the original isolated probe; only headless shell is validated here.
- No React/Vite instrumentation, source `file:line`, native browser lease, saved replay, production tree-shaking or visual approval has been certified. The P0.3 application exists, but Reticle application instrumentation remains unimplemented and unverified. Wiring it later is its own tested commit.

## Licensing / update

Server/init are FSL-1.1-ALv2, not universally permissive open source; internal use is explicitly permitted by the linked terms. SDK/core/adapters are Apache-2.0 and enterprise code has separate terms. Do not embed this as a customer-facing Omnis verification service without reviewing the applicable licenses.

Pin artifact versions and locks, inspect release diff and actual `tools/list` schemas, repeat both positive and negative controls and retain failed paths. Same-version checkout HEAD and npm publication can differ. Revert this tool commit to remove the integration; ignored node_modules/.venv and scratch evidence are disposable development state. No Hermes configuration inverse is needed because none was registered.
