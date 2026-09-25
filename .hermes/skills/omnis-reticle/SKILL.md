---
name: omnis-reticle
description: "Use when verifying Omnis UI runtime with Reticle."
version: 0.1.0
author: OmnisAI (KovacsEmanuel), Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [omnis, development, qa, mcp]
---

# Omnis Reticle QA

## When to Use
Prove a declared consequence in an owned, instrumented local development app or rerun the synthetic acceptance smoke. This is not visual design approval, a pentest executor or a globally registered Hermes MCP capability.

## Prerequisites
Read `tools/development/reticle/README.md`, `upstream.json` and the actual verdict evidence. Use the pinned isolated npm/Python environments; run commands through `terminal`. Source and npm publication commits differ; do not rely on a version string alone.

## Procedure
1. For the proven baseline use `tools/development/reticle/.venv/bin/python tools/development/reticle/run_probe.py --browser <absolute-headless-shell-path>` from the repo root after the README install steps. Discover the actual existing browser executable; do not invent a cache path or download a browser silently.
2. Require loopback-only runtime, fresh HOME/state/temp, telemetry disabled, no cloud/provider credentials, reviewed fixture and owned process cleanup. No automatic `init`, installer, feedback, cloud link, model explore or unrestricted hooks. Missing containment blocks execution.
3. For later application wiring, make a separate dev-only slice after the app exists. Declare instrumented signals/state, data-capture policy and production-bundle exclusion, then prove connection. Do not patch Omnis build/agent configuration as a side effect of loading this skill.
4. Inspect the pinned server's live tools/list and input schemas. The tested workflow is direct stdio MCP on an existing connected SDK session; tool advertisement counts and names can drift. Only invoke tools that actually exist, not imagined native Reticle tool names.
5. State the consequence before acting: expected state/network result, trigger, bounded wait and a negative control. Require an explicit `verified: yes` plus matching underlying evidence. `unknown`, no-fault, action success, empty replay and doctor exit zero are not acceptance.
6. Keep Playwright/component/DB checks independent. Reticle detected an intentional HTTP 500 despite a success label in the fixture; that does not prove all UI, business or backend properties. Inspect screenshots against the user's reference separately.
7. Preserve negative/inconclusive results and cleanup readback. The CLI `verify --expect` reload path is unresolved and not the accepted alternative. Do not retry until it appears green or erase its failure record.

## Pitfalls
The FSL server is for internal development here, not product redistribution/embedding approval. The namespace wrapper is not a hostile-code filesystem sandbox. Real app data, hooks and production use need fresh review; supplied synthetic captures are not a general redaction guarantee.

## Verification
Run the real fixture and inspect positive state/signal, rejected failed request and closed listeners. No source mapping, React instrumentation or visual approval is claimed until independently exercised. Commit the instrumentation slice and its regressions when it is actually built.
