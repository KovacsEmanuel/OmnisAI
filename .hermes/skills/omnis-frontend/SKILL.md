---
name: omnis-frontend
description: "Use when building Omnis UI from a visual reference."
version: 0.1.3
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
Build a reference-led screen or a functional React slice. A technically verified prototype is not a visual reference or user approval by itself.

## Prerequisites
Read the relevant UI/UX flow and data/state contract. Use `vision_analyze` for a user-supplied image, or browser tools for an authorized URL. Inspect the actual screenshot, component code and token file before choosing values. React/TypeScript/Vite, Radix and CSS Modules/tokens remain the selected stack; do not import Tailwind, cn/tailwind-merge, Base UI or Motion by default.

## Procedure
1. Establish the operator's task and primary surface (operate/monitor/configure/inspect), reference viewport and hierarchy. Extract layout, density, typography, spacing and interaction vocabulary from evidence, not memory. Identify functional constraints and uncertainties; no invented business metrics or branded assets.
   Map the reference's page boundaries before styling: central Dashboard, selected Engagement and global Settings have separate navigation/content scopes. Keep Skills/Runtime under Settings and the full Brain stream on its engagement surface; an overview summarizes rather than duplicating every detail panel. Synchronize global scope selection on desktop and mobile.
2. Write a fidelity checklist for the reference's composition, density, type scale, pills, card treatment and component order before changing tokens. A palette match or navigation reshuffle is not a layout match. Preserve explicitly requested metric cards, distributions and reference-led headers instead of deleting them through generic minimalism rules; derive every demonstrated count from one labelled synthetic model. When the user requests a coordinated multi-view prototype iteration, complete that linked flow for review, not just its data model. Visual approval remains required before product implementation. Keep one current baseline.
3. Reuse existing primitives and tokens. Native buttons, links, forms and tables first; use existing Radix widgets for complex interaction. Do not mix primitive systems in one surface. Use fixed layering tokens, visible focus, named icon buttons and safe areas.
4. Model loading/empty/error/stale/unknown/unavailable distinctly. Actions reflect authoritative persisted state. Keep critical identity, scope, snapshot and Stop information readable; do not truncate it to make the layout cleaner.
5. Preserve Stop without confirmation, including an equivalent control inside an overlay that makes the topbar inert. Confirm genuinely destructive data changes; Start keeps its preflight. STOPPING/PAUSING are not STOPPED/PAUSED until confirmed.
   Keep the exact engagement/run identity beside an overlay Stop even on global Dashboard/Settings; the obscured or inert page cannot supply its context. A compact cross-page run control does not justify displaying the engagement's entire navigation globally.
6. Derive state in render when possible; reserve effects for external-system synchronization with cleanup. Use Query keys/revisions and React Router consistently; type client DTOs from the Omnis contract. Add component behavior tests before implementing functional changes.
7. Use no decorative motion unless requested/approved. Respect current project motion limits and reduced-motion removal; do not inherit upstream 200/300ms examples. No remote fonts, glows or arbitrary statistics as filler. Generic hero/card defaults must not override a user's explicit reference composition; density and requested widgets are part of fidelity, not optional decoration.
8. Render and inspect actual screenshots at agreed desktop/mobile sizes; compare hierarchy, density and placement with the reference. Exercise keyboard and state transitions, then run component/build/type checks actually present in the repo. Commit the smallest accepted visual or functional slice separately.
   Capture screens reached through real navigation, including re-entry from a long page or an existing wizard's final step. Direct-load screenshots can hide retained scroll, obscured tabs or leaked draft-step state.

## Pitfalls
Serialize browser-auth transitions and fence every asynchronous continuation, including direct readbacks outside Query. Cancel pending session/instance reads on expiry/logout and pause polling during pairing/logout; reproduce held older responses arriving after a newer denial or confirmed logout, allowing Query notification batches to flush before assertions.

Use an explicit loopback network policy rather than assuming Internet connectivity determines localhost availability. Exercise the browser offline flag and Query pause behavior; display paused/aged/error observations as unverified or stale, and never claim a previous confirmed response when the first request failed.

Classify visible elements by provenance: explicit user request, existing baseline contract, reference-only example, or synthetic design copy. Do not promote mock examples into new product requirements. Keep simulation selectors and evidence/replay/retest preview tools in labelled, default-collapsed design controls; persistent availability/error/Stop feedback must remain outside them.

An automation-green screen can still be visually poor. Existing DESIGN.md is a technical token record, not renewed visual approval. The upstream AlertDialog rule does not apply to emergency Stop; its Tailwind and animation defaults are not adopted. Avoid unnecessary new components and visual-only rewrites of safety behavior.

## Verification
Actual reference comparison plus interaction evidence and honest current-data states. The user approves the visual direction; tests establish specified behaviors, not taste. No UI changes are made by installing this skill.
