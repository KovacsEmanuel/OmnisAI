# omnis-frontend: ui-state-and-capture

Rețete tematice păstrate din procedura anterioară. Încarcă numai pentru frontiera concretă afectată; nu sunt preflight universal sau autorizație de efecte. Dovezile istorice rămân la reviziile lor.

## Pitfalls

Gate initial form controls on accepted hydration/readback, not Query `isPending`: cached data can make the query successful while the first guarded GET still waits. Reproduce with populated projection/draft cache keys and a held initial GET; require no blank fields or actionable Next before hydration, exact values afterward, visible initial errors and editable hydrated background refresh without losing local edits.

Preserve native first-entry tab order: do not focus `main` unconditionally on mount, which makes the first Tab bypass the skip link. Reset scroll/focus only on an actual client route transition; test initial Tab/skip independently from post-navigation focus.

Before crediting a reload/resize screenshot, await the intended route's authenticated content and exact object identity, not just document load or absence of overflow. A bootstrap/loading capture can satisfy geometry checks while proving nothing about the named target screen.

A Playwright `fullPage` capture after scrolling can paint a fixed, off-viewport skip link over an unrelated form field in the stitched image. Before filing an obstruction or changing CSS, compare a viewport-only capture at the same scroll/focus state and the link's live `getBoundingClientRect()`/activeElement. Keep the real skip-link keyboard path; a stitched screenshot alone is not an overlay reproducer.

Serialize browser-auth transitions and fence every asynchronous continuation, including direct readbacks outside Query. Cancel pending session/instance reads on expiry/logout and pause polling during pairing/logout; reproduce held older responses arriving after a newer denial or confirmed logout, allowing Query notification batches to flush before assertions.

Use an explicit loopback network policy rather than assuming Internet connectivity determines localhost availability. Exercise the browser offline flag and Query pause behavior; display paused/aged/error observations as unverified or stale, and never claim a previous confirmed response when the first request failed.

Classify visible elements by provenance: explicit user request, existing baseline contract, reference-only example, or synthetic design copy. Do not promote mock examples into new product requirements. Keep simulation selectors and evidence/replay/retest preview tools in labelled, default-collapsed design controls; persistent availability/error/Stop feedback must remain outside them.

An automation-green screen can still be visually poor. Existing DESIGN.md is a technical token record, not renewed visual approval. The upstream AlertDialog rule does not apply to emergency Stop; its Tailwind and animation defaults are not adopted. Avoid unnecessary new components and visual-only rewrites of safety behavior.

Distinguish a trusted pre-mutation size refusal from an unknown write and from a received write receipt whose GET confirmation failed. Keep explicit `BODY_TOO_LARGE` editable without automatic retry; preserve the stale receipt barrier through subsequent local edits. Test POST and PUT: receipt → failed GET → edit must retain disabled Save/Next and exact-readback recovery, then require explicit compare/keep/discard before a new CAS write. A corrected form identical to the saved payload should still have Save disabled; use a genuinely dirty control to test recovery rather than weakening that invariant.

## Verification
Actual reference comparison plus interaction evidence and honest current-data states. The user approves the visual direction; tests establish specified behaviors, not taste. No UI changes are made by installing this skill.
