# Settings — selected design C

Open **[settings-final.html](settings-final.html)** directly in a browser. No server or keys.
The interface is English-only and keeps the accepted Omnis visual baseline.

- Guided **Connection → Models → Review**.
- Search the selected provider's example catalog; `+ Add` selects several models per key.
- Saved models grouped by connection; no repeated key entry.
- Separate **Model assignments**: one model uses all roles; multiple configured entries
  populate Default/Brain/Investigator/Validator, including provider identity.
- `Save models` versus one explicitly selected `Save & test`, not automatic bulk testing.
- View controls expose first setup, one/many models, catalog failure, LOCKED and UNKNOWN.

The preview is offline: readonly demo key, sample catalogs, in-memory state only. Reload
resets it. It is outside the application build; no production API/DB/CLI/auth changes.

**[Selected design and implementation delta](settings-final.md)** records the operator's
choice, exact behavior, required persistent registry/catalog/test changes and size prerequisites.
This is now more than UI-only. Autopair remains a separate security decision; role execution
is T2, live router/mix evidence is P4b, neither is claimed from the preview.

The older [A/B/C comparison](settings-options.html) is historical. Its Romanian copy,
recommendation of A and narrower UI-only scope were superseded by the selected C design.
Original analysis/review/evidence remain recoverable in commit `e6aa237`.

## Offline browser check

Uses the existing Playwright 1.63.0 / pinned Chromium installation, no new dependencies:

```sh
node web/design/settings-final.test.mjs
OMNIS_DESIGN_OUTPUT="$TMPDIR/omnis-settings-final" node web/design/settings-final.test.mjs
```

Checks English UI, same-key multi-add/search/dedup, separate saved-entry assignments,
0/1/many models, exact one-model test, Cancel/UNKNOWN, manual fallback/inert text,
keyboard, 320/390/1280/1440 and CSS200%, with zero external requests/console errors.
These are artifact checks, not live product, persistence, screen-reader or aesthetic approval.
Current product status remains T1 CLOSED_SCOPED; no successor implementation is authorized here.
