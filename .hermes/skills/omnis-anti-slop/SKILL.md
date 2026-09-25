---
name: omnis-anti-slop
description: "Use when linting Omnis TypeScript for evidence loss."
version: 0.1.0
author: OmnisAI (KovacsEmanuel), Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [omnis, development, typescript, review]
---

# Omnis anti-slop

## When to Use
Implement/review TypeScript and maintain the vendored subset of `dmmulroy/anti-slop`. This is executable Oxlint policy, not a generic prose or visual-design prompt.

## Prerequisites
Read `tools/development/anti-slop/README.md` and `upstream.json` from the git root. The isolated package pins matching Oxlint/plugin versions; it does not change the product stack or install Effect.

## Procedure
1. Use `terminal` with `npm --prefix tools/development/anti-slop ci --include=dev --ignore-scripts --no-fund` on a fresh checkout. Do not invoke a blind upstream skill installer or unpinned `npx`.
2. Run `npm --prefix tools/development/anti-slop test`. Require the valid boundary fixture to pass and each invalid fixture to fail with its specific rule diagnostic. Installation alone is not success.
3. For an implementation change use `terminal` with `npm --prefix tools/development/anti-slop run lint -- <absolute-source-path>`. Specify owned files; do not sweep vendored code, fixtures, generated types and unrelated work into a rewrite.
4. Replace fabricated cast evidence with actual boundary parsing or a precise type. Explain unavoidable casts with a checked invariant; adding a SAFETY comment alone does not make unsafe input trustworthy.
5. Preserve validation, cancellation, error handling, auditability and tests. `unknown` and `typeof` are allowed at trust boundaries. Do not introduce `any`, remove checks or weaken tests to silence a style rule.
6. Rerun component TypeScript/tests plus this lint; document actual findings and commit the minimal correction. For upstream updates preserve the selected subset, license, source digests and custom config; review new rules before enabling.

## Pitfalls
The upstream installer enables much more opinionated policy; it is not Omnis authority. Host Node may lack native TS support despite its version, so retain the `tsx` loader. `NODE_ENV=production` can silently omit dev dependencies. A lint timeout is failure, not a clean file.

## Verification
Real CLI execution, positive and negative controls, intended source files checked, no weakened trust boundary. Lint cannot certify runtime safety or UI aesthetics. Keep this tool out of the assessment runtime and production application bundle.
