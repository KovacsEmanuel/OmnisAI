---
name: omnis-frontend
description: "Use when building Omnis UI from a visual reference."
version: 0.1.0
author: Julien Thibeaut (upstream), OmnisAI, Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [omnis, development, ui]
---

# Omnis frontend engineering

Adapted from ibelick/ui-skills; original and MIT notice are in `references/`. The explicit Omnis qualifications below govern the adaptation; the upstream document is not a request to install its preferred stack.

## When to Use
Build a reference-led screen or a functional React slice. Do not use this as permission to polish the rejected current prototype before the user supplies the reference.

## Prerequisites
Read the relevant UI/UX flow and data/state contract. Use `vision_analyze` for a user-supplied image, or browser tools for an authorized URL. Inspect the actual screenshot, component code and token file before choosing values. React/TypeScript/Vite, Radix and CSS Modules/tokens remain the selected stack; do not import Tailwind, cn/tailwind-merge, Base UI or Motion by default.

## Procedure
1. Establish the operator's task and primary surface (operate/monitor/configure/inspect), reference viewport and hierarchy. Extract layout, density, typography, spacing and interaction vocabulary from evidence, not memory. Identify functional constraints and uncertainties; no invented business metrics or branded assets.
2. Propose one focused reference interpretation, noting what is retained versus adapted for Omnis. Implement one representative screen with real states; get visual approval before spreading new tokens/layout across every screen. Do not create a pile of competing baseline documents.
3. Reuse existing primitives and tokens. Native buttons, links, forms and tables first; use existing Radix widgets for complex interaction. Do not mix primitive systems in one surface. Use fixed layering tokens, visible focus, named icon buttons and safe areas.
4. Model loading/empty/error/stale/unknown/unavailable distinctly. Actions reflect authoritative persisted state. Keep critical identity, scope, snapshot and Stop information readable; do not truncate it to make the layout cleaner.
5. Preserve Stop without confirmation, including an equivalent control inside an overlay that makes the topbar inert. Confirm genuinely destructive data changes; Start keeps its preflight. STOPPING/PAUSING are not STOPPED/PAUSED until confirmed.
6. Derive state in render when possible; reserve effects for external-system synchronization with cleanup. Use Query keys/revisions and React Router consistently; type client DTOs from the Omnis contract. Add component behavior tests before implementing functional changes.
7. Use no decorative motion unless requested/approved. Respect current project motion limits and reduced-motion removal; do not inherit upstream 200/300ms examples. No remote fonts, generic hero/cards, glows or arbitrary statistics as filler.
8. Render and inspect actual screenshots at agreed desktop/mobile sizes; compare hierarchy, density and placement with the reference. Exercise keyboard and state transitions, then run component/build/type checks actually present in the repo. Commit the smallest accepted visual or functional slice separately.

## Pitfalls
An automation-green screen can still be visually poor. Existing DESIGN.md is a technical token record, not renewed visual approval. The upstream AlertDialog rule does not apply to emergency Stop; its Tailwind and animation defaults are not adopted. Avoid unnecessary new components and visual-only rewrites of safety behavior.

## Verification
Actual reference comparison plus interaction evidence and honest current-data states. The user approves the visual direction; tests establish specified behaviors, not taste. No UI changes are made by installing this skill.
