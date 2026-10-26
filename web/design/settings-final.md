# Selected Settings design — C, guided and English-only

**Design decision, not a product implementation or a new roadmap.** The operator selected C
and explicitly added a persistent configured-model list, provider catalog search, multiple
models per saved key, and a separate assignments section. `settings-final.html` is the current
interactive reference. `settings-options.html` is the previous comparison, not another direction.
Keep the accepted Omnis palette, local Geist, capsule navigation and double-bezel panels.
All visible application copy, labels, messages and accessibility names are English.

## Final operator flow

1. **Connection:** choose OpenRouter or OrcaRouter. Existing connection: `Saved key`, no
   secret field and no resubmission of the key. New/replaced key: write-only field.
   `Continue` **saves the connection locally and explicitly loads its catalog**. One short
   hint states this. Cancelling later discards pending model selections, not the already
   saved connection; an unconfirmed Save must be read back before any catalog call.
2. **Models:** `Search models` filters the selected provider's catalog by name or exact ID.
   Each result has `+ Add`; selected models become removable chips. Already configured
   entries cannot be duplicated. Add several models without re-entering/re-saving the key.
   Back preserves selection; changing provider requires confirmation before discarding it.
   Catalog error/partial/stale is explicit, never an empty-success list. `Enter a model ID`
   is a compact fallback; an unverified entry can be saved, not claimed usable or tested.
3. **Review:** provider, selected models, unchanged assignments/default information.
   `Save models` is local only. `Save & test` names **one selected model** and approves one
   fixed synthetic call, not a paid test for every selected model. A successful test marks
   only that exact model/connection revision. `Models saved` is not `Model connected`.

At normal re-entry the user sees the saved model list, not the wizard. `Add models` opens
Connection; `+ Add model` under an existing provider can go directly to Models using its
saved key. No automatic provider traffic or test at boot/reload. A compact connection menu
preserves Replace key/Disable/Reconnect; active-test Cancel and UNKNOWN readback remain
reachable independently of the wizard. No run is active in this scene; the real global
Stop and run identity must remain in the product shell.

## Model assignments — separate from registration

- Zero configured models: `Add a model first.`
- One usable model: `All roles use <model>.` No redundant role selectors.
- Several configured models: Default model, Brain, Investigator, Validator. Every picker
  is populated from **saved configured entries across both connections**, not the raw catalog.
  Labels include provider, so identical model IDs through different routers are distinguishable.
- Brain/Investigator/Validator offer `Use default`. Explicit assignments stay explicit when
  Default changes or models are added. Adding a model must not reset old overrides.
- Disabled/stale/unverified entries remain identifiable but unavailable, including a selected
  stale entry. Never silently switch provider/model or reactivate a revoked connection.
- `Save assignments` is independent and affects future runs only. Existing runs keep pinned
  snapshots. Configuration is not proof of role execution; that consumer remains T2.

No new role is invented. The role set is the current BRAIN/INVESTIGATOR/VALIDATOR contract.
Output/capability controls and test input/usage/operation IDs remain secondary details, not
extra onboarding steps. Existing per-role/output settings must survive migration unchanged;
the small 128-token demo test cap must not become an artificial total harness budget.

## What needs real implementation

This request is now **more than a UI-only change**. Before product edits, align the affected
canonical plan/UI/architecture paragraphs in place; do not launch T2 or duplicate P4b.

| Consumer | Reuse | Necessary delta / acceptance |
|---|---|---|
| Saved configured models → assignments/test | Existing seif, connection revisions and provider_selection_revision | Add an instance-owned model registry, unique current `(connection_id, exact_model_id)`, stable entry ID/revision, proposed maximum **64 configured entries per instance**. No copied secrets. Backfill existing default/overrides idempotently by exact connection/model, preserving revisions, explicit overrides and output settings. Empty and upgrade PostgreSQL migrations, duplicate/conflict and restart readback. |
| Connection → provider catalog → search/+ | ModelSender metadata transport, allowlisted endpoints, owner/Stop/revoke guards | Connection-scoped catalog operation independent of a saved default, normalized bounded DTO/cache, local paginated search. Browser sees only metadata. Typing searches local indexed/cache data, not the provider. Explicit Continue/Refresh produces the outbound catalog action. Do not require a dummy model/default or temporarily change Default to browse. |
| Registry entry → existing selection snapshots | Existing SaveSelection and role inheritance | Resolve a chosen registry entry into the existing exact connection revision/model/output representation. No second role owner/table unless necessary for a concrete invariant. Unmatched historical choices remain visible/stale, never fuzzy-matched or silently replaced. |
| Registry entry → Test model | Existing finite SystemOperation, sender, ledger, outcomes/Cancel/readback | Extend admission to one selected saved entry and its metadata snapshot; do not test another entry by swapping the global default. Keep exact requested/observed, one call/300s, no retry/fallback, no duplicate spend, persistent UNKNOWN/partial and connection-revision invalidation. Current T1 only tests default. |
| Web → these persisted consumers | React/Query/client/DTOs, session/Host/Origin/CSRF, existing CSS/tokens | Guided English-only UI, selected-model chips, separate saved-entry assignments, persistent errors and scoped notifications. API/OpenAPI/generated TS/manual decoders/client/component fixtures change together. Real browser/API/PG save→GET/reload/restart plus one explicit test; key absent from storage/log/URL/output. |

### Input/size prerequisites, not a global limit increase

The existing Settings command is bounded at **3600 encoded bytes**, its control frame at
4096 and Settings view at 4096; T1 metadata response is bounded at 2 MiB. A 64-entry library
must not be put into those existing frames or silently truncated. Before assigning a writer,
prove maximum encoded new request/response fixtures and choose a separately bounded command
and paginated read DTO; keep old message limits unchanged. Proposed new write ceiling: 64 KiB
including envelope, with exact worst-case tests before admission. Do not carry raw provider
catalogs in the small control response.

For catalog ingestion, proposed caps are 8192 normalized entries, 2 MiB/page, 16 MiB total,
32 upstream pages and a finite whole-operation deadline. Return local search pages, not the
whole catalog to each render. Confirm provider pagination/schema with real fixtures first.
Treat declared totals/next links as data: follow only the release-allowlisted endpoint/query,
refuse loops/foreign next URLs, dedupe exact IDs, verify completion, and label PARTIAL if a
cap is reached. Never claim “all models” from the first upstream page. Cache and test results
are tied to connection/credential revisions; a key rotation invalidates their current eligibility.
These caps are proposals for implementation preflight, not newly enacted runtime contracts.

### Official documentation checked, no API calls made

- [OpenRouter model listing](https://openrouter.ai/docs/api/api-reference/models/list-all-models-and-their-properties)
  documents `/api/v1/models`, paging, exact IDs and supported parameters. A catalog list is
  not an inference/access/balance guarantee for the key.
- [OrcaRouter model catalog usage](https://docs.orcarouter.ai/routing/free-models) documents
  `/v1/models`; it says anonymous access is accepted, while supplied invalid keys are rejected.
  Do not fallback from an authenticated failure to an anonymous “connected” result. Live
  adapter/pagination/schema compatibility remains unverified; do not assume parity from names.
- Repo ownership: `provider_key_models.py`, `provider_key_service.py`, `provider_vault.py`,
  `model_test_runtime.py`, `model_sender.py`, current API routes/control framing and generated
  clients; canonical plan §8/§12/SL12/SL33, architecture §4/§5.3/§8.1, UI Settings contract.

## The other requests: keep the boundaries

- Same-key multi-model registration/search/assignments is part of the selected Settings scope
  now; it is no longer deferred as an optional favorites feature. Deliver it end-to-end through
  existing owners, with coherent revertible commits, not disconnected helpers or a mega-commit.
- Both routers and a real mixed-role run remain P4b/B14a–G04b. Showing sample entries from
  both providers in this mockup does not certify OrcaRouter or close P4b. Run mixing needs T2's
  actual run consumer; it does not block registration UX.
- CLI → web → Home with a valid session already exists. First/expired-session autopair is a
  separate proposed SL03 amendment. Current canon forbids pairing codes in URL/argv, including
  fragment. A one-use launch ticket via fragment needs explicit approval of that exception and
  browser/opener exposure; otherwise select a different private browser handoff. No localhost
  auto-login, removal of authentication, or authorization inferred from choosing C.
- No third provider, arbitrary base URL, auto-paid bulk tests, runtime hot-swap, editor/IDE,
  metrics, decorative messaging or dependency installation is included.

## Evidence boundary

The HTML is offline, with a readonly demo key, sample catalogs, in-memory state and no provider
or persistence. It demonstrates 0/1/many models, two provider namespaces, search/selection,
separate assignments, test one/not-all, Cancel/UNKNOWN and catalog failure/manual fallback.
It does not implement or certify any API/DB/crypto/CLI change. User selection approves the
C direction; the expanded mockup still needs the operator's final visual/flow acceptance.
