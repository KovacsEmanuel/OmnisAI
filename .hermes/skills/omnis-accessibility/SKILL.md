---
name: omnis-accessibility
description: "Use when auditing Omnis keyboard and accessibility."
version: 0.1.1
author: Julien Thibeaut (upstream), OmnisAI, Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [omnis, development, ui]
---

# Omnis accessibility

Adapted from ibelick/ui-skills `fixing-accessibility` with local safety and composite-widget qualifications. MIT source/notice are in `references/`.

## When to Use
Forms, tables, dialogs, drawers, tabs, menus, live events and accessibility regression review. Do not rewrite unrelated layout or migrate primitives as an accessibility fix.

## Procedure
1. Use `read_file` and browser tools to inspect the actual semantic/accessible tree and reproduce a specific failure. Prioritize accessible names, keyboard reachability, focus and state comprehension.
2. Prefer native HTML; label fields, name icon-only buttons, hide decorative icons, associate errors/help text and expose invalid/required/expanded/busy state. Do not add redundant ARIA or clickable div substitutes.
3. Test the complete keyboard path. Tab reaches composite widgets; arrows/roving tabindex reach their items according to the primitive's pattern. Do NOT force every menu/tab option into the Tab sequence or use positive tabindex. After a long disclosure or rerender, test Tab then Shift+Tab back to its summary and compare target bounds with the sticky header; activeElement alone misses partial occlusion. Account for the measured header size in native scrolling, not only explicit click handlers, and repeat after responsive changes.
4. Test modal initial focus/trap/close and restoration to a still-visible trigger or sensible fallback. Resize drawer→desktop must remove stale inert state and move focus to a visible element. Critical Stop stays reachable even when the topbar is inert.
5. Critical errors persist near the action, not only in a toast. Aggregate SSE updates through polite announcements; do not read every event. A visible disabled action explains the missing gate. Status uses text/icon as well as color.
6. Test skip link, named table-scroll region, adequate target size, contrast, long labels, 320/390/1280/1440 layouts, 200% zoom, forced colors and reduced motion, scoped to the feature. Do not silently reduce typography/contrast to fit more data.
7. Use `terminal` for targeted component/Playwright regressions and browser tools for manual keyboard/screenshot inspection. Add the failing case before the minimal fix; rerun related overlay/resize/Stop tests.

## Pitfalls
Radix usage and automated a11y checks are not WCAG certification. Report screen-reader/browser combinations actually exercised; distinguish unavailable coverage. Do not add an emergency-stop confirmation or hide safety explanations to satisfy superficial UI cleanup.

## Verification
Each reported issue has a before/after reproducer and concrete code location. The affected operator journey remains usable by keyboard with visible focus, persistent errors and reachable Stop. Keep unrelated visual redesign out of the correction.
