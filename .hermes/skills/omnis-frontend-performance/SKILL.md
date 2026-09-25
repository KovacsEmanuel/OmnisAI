---
name: omnis-frontend-performance
description: "Use when measuring Omnis frontend performance."
version: 0.1.0
author: Julien Thibeaut (upstream), OmnisAI, Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [omnis, development, ui]
---

# Omnis frontend performance

Adapted from ibelick/ui-skills motion-performance guidance and extended for the Omnis event/evidence UI. Original and MIT notice are passive references.

## When to Use
Measured slow interactions, expensive tables/evidence views, event streams, jank, leaking observers/subscriptions or an approved motion change. Do not preemptively optimize an unimplemented UI.

## Procedure
1. Establish a representative synthetic fixture, viewport and interaction. Use browser profiler/performance recordings and `terminal` for the actual build bundle. Record before values and sample conditions; set acceptance from the task, not invented benchmark scores.
2. Separate network, rendering, DOM size, JS, layout and memory cost. Diagnose a bottleneck before choosing a fix. Keep tables server-paginated; use virtualization only with measured need and keyboard/screen-reader evidence.
3. Batch layout reads before writes. Prefer transform/opacity for necessary motion, bounded work and cleanup on unmount. Stop offscreen loops, observers and subscriptions. Profile compositor promotion rather than assuming it; use will-change briefly, not on every element.
4. Follow the current project motion cap and remove nonessential motion under reduced-motion. No unrequested animation, decorative blur/glass or default new library. Static CSS variables/tokens are fine; continuously animating inherited variables can broaden invalidation.
5. Bound evidence payloads/rendering and event batches. Keep durable SSE cursor/replay idempotency, revision-aware invalidation and stale/unknown states. Under load Stop must remain responsive and new effect admission must remain governed by backend policy.
6. Prefer simpler ownership and precise data flow. Optimize growing copied accumulators only within fresh local objects; do not mutate React state, Query cache or shared input. Do not remove validation, escaping, redaction or provenance for performance.
7. Rerun the same scenario and functional/a11y tests after the minimal change. Report measured before/after, fixture dimensions and remaining limitations; commit optimization independently of feature behavior.

## Pitfalls
The upstream preference to retain motion does not override reduced-motion/user choice. A smaller bundle does not prove faster interaction. A mocked event source cannot certify network/recovery behavior. Avoid duration assertions that only measure a loaded test host.

## Verification
A repeatable improvement in the specified scenario, no functional/safety/accessibility regressions, and resource cleanup under repeated mount/navigation/reconnect. No performance claim without a real trace or measurement.
