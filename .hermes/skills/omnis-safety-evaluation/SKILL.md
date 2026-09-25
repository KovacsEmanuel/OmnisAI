---
name: omnis-safety-evaluation
description: "Use when testing Omnis safety and finding validity."
version: 0.1.0
author: OmnisAI (KovacsEmanuel), Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [omnis, development]
---

# Omnis safety and evaluation

## When to Use
P3/P5/P6/P7/P8: broker/executor policy, auth isolation, evidence, vulnerability validators and held-out evaluation. Only synthetic authorized local lab targets are the default.

## Prerequisites
Read the scope/action/effect/data contracts and the relevant gate in the canonical architecture/plan. Check dependency readiness first: a known rejected proxy build cannot handle target traffic. Keep secrets and personal provider sessions out of fixtures.

## Procedure
1. State expected allow and deny outcomes before running the probe. Use fixture manifests with explicit ownership, identities, business access rules, health/sink state and budgets. Never infer business authorization from status 200 or resource ownership alone.
2. Exercise the deterministic boundary, not the model's agreement: URL parser; broker; proxy; network namespace; target sink. Test redirect, DNS rebinding, CONNECT/SNI/Host/path mismatch and browser subrequests. Verify denied traffic did not reach the sink.
3. Bind each browser context generation to one attempt, with trusted run/attempt/action/auth/fencing lineage. Test stale contexts and cross-attempt reuse. Bound workflow windows and streaming/decompression before buffering, not after memory use.
4. Test effects separately from verbs: GET mutator, auto-submit, downloads, email/webhooks and cleanup failures. UNKNOWN does not become read-only. Stop/revocation must deny new effect admission; uncertain in-flight outcomes remain explicit.
5. Exercise auth refresh crash windows: durable intent, rotated secret persistence, generation/fencing at publication and only then epoch activation. Baseline/probe/validator identity and target reset must be recorded; auth expiry is not a secure negative.
6. Before any model-facing data use the approved projection DTO and synthetic sentinel leak checks over requests, errors, evidence and logs. Include screenshots/imports where applicable. Generic redaction is not universal data-loss prevention.
7. For each finding family supply vulnerable and fixed fixtures, an expected oracle and secure controls, independent replay, provenance and bounded evidence. Keep candidate/verified/rejected/inconclusive distinct. `tested_no_issue` requires an executed procedure and evidence; absence of a finding is not coverage.
8. For final evaluation start from authorized URL/context, with inventory hidden from the agent. Compare against the deterministic baseline under equal information/request/time budgets; attribute misses by recon/planning/execution/validation. Freeze protocol before results and report negative results as product evidence.

## Pitfalls
A second model's vote is not validation. Mocked denials do not prove network confinement. UI counts must reconcile to DB/report at the same snapshot. Never use Reticle or Chisel as the pentest broker.

## Verification
No unauthorized effects, honest coverage and repeatable class-specific evidence. Fault injection covers timeouts, crash, duplicated work, lost ACK, identity changes and restored stale leases. Restore starts stopped and re-runs preflight; Git revert alone cannot undo target/DB state.
