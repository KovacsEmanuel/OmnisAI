---
name: omnis-frontend
description: "Use when building Omnis UI from a visual reference."
version: 0.1.6
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
2. Write a fidelity checklist for the reference's composition, density, type scale, pills, card treatment and component order before changing tokens. A palette match or navigation reshuffle is not a layout match. Preserve explicitly requested metric cards, distributions and reference-led headers instead of deleting them through generic minimalism rules; derive every demonstrated count from one labelled synthetic model. When the user requests a coordinated multi-view prototype iteration, complete that linked flow for review, not just its data model. Reuse the accepted UI/UX §0 baseline; request approval for a changed visual direction. Keep one current baseline.
3. Reuse existing primitives and tokens. Native buttons, links, forms and tables first; use existing Radix widgets for complex interaction. Do not mix primitive systems in one surface. Use fixed layering tokens, visible focus, named icon buttons and safe areas.
4. Model loading/empty/error/stale/unknown/unavailable distinctly. Actions reflect authoritative persisted state. Keep critical identity, scope, snapshot and Stop information readable; do not truncate it to make the layout cleaner.
5. Preserve Stop without confirmation, including an equivalent control inside an overlay that makes the topbar inert. Confirm genuinely destructive data changes; Start keeps its preflight. STOPPING/PAUSING are not STOPPED/PAUSED until confirmed.
   Keep the exact engagement/run identity beside an overlay Stop even on global Dashboard/Settings; the obscured or inert page cannot supply its context. A compact cross-page run control does not justify displaying the engagement's entire navigation globally.
6. Derive state in render when possible; reserve effects for external-system synchronization with cleanup. Use Query keys/revisions and React Router consistently; type client DTOs from the Omnis contract. Add component behavior tests before implementing functional changes.
7. Use no decorative motion unless requested/approved. Respect current project motion limits and reduced-motion removal; do not inherit upstream 200/300ms examples. No remote fonts, glows or arbitrary statistics as filler. Generic hero/card defaults must not override a user's explicit reference composition; density and requested widgets are part of fidelity, not optional decoration.
8. Render and inspect actual screenshots at agreed desktop/mobile sizes; compare hierarchy, density and placement with the reference. Exercise keyboard and state transitions, then run component/build/type checks actually present in the repo. Commit the smallest accepted visual or functional slice separately.
   Capture screens reached through real navigation, including re-entry from a long page or an existing wizard's final step. Direct-load screenshots can hide retained scroll, obscured tabs or leaked draft-step state.

## Pitfalls
Keep synthetic/reference copy separate from product requirements; automation success is not aesthetic approval. Preserve Stop without confirmation, authoritative hydration/stale/unknown state, native keyboard order and cleanup.

## Verification
Actual reference comparison plus interaction evidence and honest current-data states. Reuse the accepted baseline; the user approves a changed visual direction, while tests establish behaviors.

## Referințe la cerere

- [ui-state-and-capture](references/ui-state-and-capture.md)
