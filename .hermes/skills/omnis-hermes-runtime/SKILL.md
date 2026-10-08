---
name: omnis-hermes-runtime
description: "Use when integrating Omnis with native Hermes."
version: 0.1.3
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

- Attest live mounted state from the running container's mount namespace, not a Docker archive copy: `docker cp` may miss tmpfs contents. Use a finite, isolated installed-interpreter observer restricted to the exact synthetic paths; require unchanged file hashes and exact boolean marker absence, join the observer before family/drain checks, and retain a sensitive positive/negative control. Static installed source files can still be archive-attested separately.
- Renew actual stock-client authority immediately after successful launch, before blocking postlaunch census/observation; do not rely on a periodic task that has not yielded or extend the product grant to accommodate the harness. Register and checkpoint partial launch/renew/family evidence before an observer can refuse. A later successful run does not establish the cause of an older signal exit or reconcile its uncertainty.
- Keep credential-reader and native-runtime observation boundaries separate: an installed observer's store flags/modules and `/proc` initial environment do not prove the runtime's post-import memory, refresh behavior or loaded tools. Reverse `server_requests` advertisements are not a loaded-tool census. If a bootstrap registry is uninitialized/unobservable, retain NOT_INITIALIZED/NOT_OBSERVED rather than import/register/prewarm tools to fabricate an empty or complete inventory.
- Verify a proposed pre-run guard's actual veto semantics before using it as authority: the pinned `subagent_start` observer runs after child construction, omits an explicit batch index/manifest and swallows failures; execution middleware may fall through to downstream after an exception. Require an explicit indexed trusted sidecar and a fail-closed commit barrier before access, not association after `launch()` returns or a callback that merely logs failure.
- Establish NO_MODEL before native client initialization and conversation admission, not by cancelling a launched child, setting zero iterations or passing empty toolsets. At the pin, empty `allowed_toolsets` inherits the parent inventory. Keep installed preparation/loading evidence separate from native result/continuation evidence; neither a fake provider nor a deterministic emitter closes the latter boundary.

## Verification
Each G02/G04/G07 subgate has evidence at its actual boundary. Test restart, compression/lineage, duplicate events, wrong identity, stopped run and bounded outputs. Report live LLM tests as not-run until explicitly authorized and exercised.
