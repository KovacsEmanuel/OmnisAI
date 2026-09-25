---
name: omnis-hermes-runtime
description: "Use when integrating Omnis with native Hermes."
version: 0.1.0
author: OmnisAI (KovacsEmanuel), Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [omnis, development]
---

# Omnis native Hermes integration

## When to Use
P2/P4/P7: supervisor, JSON-RPC, native children, providers/settings, skill snapshots, wake/stop/recovery. Do not replace Hermes with another agent framework.

## Prerequisites
Load the `hermes-agent` skill and relevant official documentation; read architecture §5 and the current integration gate. Check installed versus pinned Hermes revision using `terminal`. Use an isolated runtime home with synthetic test data, never the operator's personal profile, sessions, credentials or imported environment.

## Procedure
1. Declare the exact native contract being probed and its observable oracle. First build a deterministic protocol fixture; label it simulation. Then exercise the pinned real Hermes path inertly where possible. Provider inference is separately opt-in with explicit model/account/budget.
2. Implement one private supervisor owner. Parse protocol framing, request IDs and server-to-client requests; bound time/output and test EOF, cancellation and restart. Browser Omnis does not call management/RPC endpoints directly.
3. Establish task→native-child mapping BEFORE the first tool effect. Bind capabilities to trusted launch lineage and fencing epochs; a task ID in model text grants no rights. Test wrong-child, stale generation and cross-run substitution.
4. Pin executable skill content and every referenced file per RUN, not per task. Draft authoring is separate from runtime publication. Test unavailable tools, rejected bundles and emergency revocation through Stop/fencing.
5. Model native children as process-local, non-durable executions. Persist domain tasks, wake intentions, outcomes and recovery decisions in Omnis. ACK admitted/delivered/consumed are distinct; test crash at each boundary and duplicate wake without duplicate effects.
6. Verify Stop in two dimensions: no newly authorized target effects, and no unapproved model continuation. A 202 is STOPPING. Interrupt/cancel acknowledgements are not proof that children, auto-wake and executors are drained.
7. Keep Settings secrets out of prompts/logs, use save→readback for nonsensitive effective configuration, and freeze provider/model/catalog during a run. Probe 401/429/cancel/logout without calling them successful inference.
8. Record whether the installed API supplies each required capability. Prefer plugin contracts; use only a minimal audited upstream patch if unavoidable, with pin and regression tests. Missing support blocks the gate rather than motivating a FIFO/goal-text association.

## Pitfalls
Profiles are not OS sandboxes. Hooks/tool descriptions are not an egress boundary. A simulated RPC peer is not the real runtime; an installed skill is not a validated investigator. Keep the development MCP tools out of the assessment runtime.

## Verification
Each G02/G04/G07 subgate has evidence at its actual boundary. Test restart, compression/lineage, duplicate events, wrong identity, stopped run and bounded outputs. Report live LLM tests as not-run until explicitly authorized and exercised.
