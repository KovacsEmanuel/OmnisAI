# Selected Settings design — C, guided and English-only

**Design decision, not a product implementation or a new roadmap.** The operator selected C
and explicitly added a persistent configured-model list, provider catalog search, multiple
models per saved key, and a separate assignments section. `settings-final.html` remains the
visual baseline; the revised flow below supersedes its older single-test controls. No new mockup
or competing direction is needed. `settings-options.html` is the previous comparison.
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
3. **Review:** provider and all selected exact models; no single-model test picker.
   `Save models` is local only. `Save & connect` requires short explicit consent to at most
   one real fixed-input verification per selected model, with possible provider charges.
   Save receipt and paged revision readback precede the first call; each next call waits for
   successful terminal readback of the previous one. Missing capabilities permit Save models,
   not silently testing a subset. Failure/stale/UNKNOWN/Cancel/Stop halts unsent work. Reload,
   navigation or tab close abandons remaining continuation, not the already-admitted operation;
   returning reads persisted results and never resumes paid calls automatically.

At normal re-entry the user sees saved models. Keep one global `Add models`; remove its
per-provider duplicate. Put compact Connection options at the bottom of each provider card,
preserving Replace key/Disable/Reconnect and their confirmations. Show each model's persisted
latest-check state: `Connected` only for exact current revisions and FINISHED/COMPLETED;
Not tested/Connecting/Failed/Unconfirmed/Unavailable remain distinct. Read the existing owner
by entry ID, not only the browser's last operation ID; no separate status table or migration
is intended. No automatic provider traffic at boot/reload or from typing/search.

Use the existing centered/aligned composition with quieter spacing, controls, scrollbar and
chips. A smaller X glyph must retain its usable hit area. Remove repeated instructional copy,
normal Test details and the large duplicate test panel; keep short cost/consent and actionable
safety states. Bottom-right notifications carry confirmations and error/recovery actions;
critical/uncertain errors do not auto-dismiss or vanish from the model state. No forced scroll
on Continue or query refresh. Active Cancel and same-operation readback remain reachable.
Global Stop/run identity and Default/override/output controls remain; no new visual direction.

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

## Original Settings C implementation contract — historical

The original registry/catalog/exact-entry implementation below is already delivered scoped;
do not rebuild it for the follow-up. The current delta is the latest-entry read projection,
finite frontend sequencing and UI simplification above. Canonical plan/UI/architecture are
amended in place; no T2, second provider client, persistent batch queue or duplicate P4b.

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

### Prompt A activated — admitted implementation contract

The operator explicitly activated Prompt A from `settings-delivery-prompt.md` on base
`cd99dfbe34a3ad690273c493177beee491da1fb6`; Prompt B/authentication remain excluded.
Architecture §5.3 and plan §8 now enact the bounded Settings C extension without reopening
historical T1 acceptance or launching T2/P4b. The proposals above are retained as design
provenance; the canonical admitted contract is authoritative.

Existing producer/consumer: ProviderSettings → client/decoder → paired provider routes →
LocalControl → ProviderSettingsOwner → PostgreSQL. Extend this owner with a separately
bounded `provider_models` command, additive/CAS save and durable exact-command receipt;
64 entries per instance, unique connection+exact ID, stable entry ID/revision and no secret
copy. Keep assignments in existing SaveSelection; preserve explicit overrides/output caps.
Backfill current default/overrides idempotently; historical revisions and stale refs remain.
Registry/catalog pages contain at most16 entries and are revision/context bound. Metadata
name≤128 code points, exact model ID≤256 printable ASCII, reason codes allowlisted≤64ASCII.

No-effect preflight: pinned Python3.13.15/Node24.21.0/npm11.19.0/uv0.12.19 and private test
PG18.6 image are available; existing PG runner targets/pytest collection were inspected.
Independent SOURCE calculations and parent execution of the full64-entry request agree:
body41001/command41036/frame41141 bytes including envelope/newline, versus old maximum
selection frame2882≤4096. Fixtures use64 distinct256-character IDs composed entirely of
JSON-escaped printable characters, full UUIDs and19-digit revisions. Proposed16-entry
registry reply13052/catalog reply34654 and selected-entry test reply54092bytes fit65536;
these reply figures are independent SOURCE preflight, not actual new DTO/runtime PASS.
The developer must bind maximum fixtures to the final DTOs/real serializers and repeat
affected size checks if their shape changes. HTTP exception is only the new registry PUT;
other old3600/4096 limits remain, even with a larger physical socket buffer.

Public official docs retrieved during admission, without provider endpoint calls:
[OpenRouter OpenAPI](https://openrouter.ai/docs/api/api-reference/models/list-all-models-and-their-properties.md)
defines offset/limit (maximum1000), response data/links/total_count; completion requires
validated traversal and count agreement. [OrcaRouter model reference](https://docs.orcarouter.ai/api-reference/models/list-available-models.md)
defines an OpenAI-style object/list/data response with optional max_completion_tokens,
context_length and modality metadata, no documented pagination parameters. Do not assume
OpenRouter capability/pagination fields for OrcaRouter or invent missing caps. Unknown
continuation/schema remains partial/unavailable; authenticated rejection never falls back
to anonymous. Documented schema fixtures are synthetic, not captured provider responses.
Live compatibility remains NOT_RUN pending explicit provider/model/data/call permission.

Delivery ownership: parent owns canonical admission/integration; one assigned developer
owns product/tests/fixes; two complementary frozen-snapshot reviews precede real-consumer
QA. First acceptance row is registry save→exact receipt→paged GET/restart/migration on
newly owned isolated PG; negative stale CAS/duplicate/entry65/oversize/revoked connection
uses the same channel. Harness-only cycles0 at admission. Continue through catalog,
exact-entry test and English C UI rather than declaring isolated helpers complete.
Rollback is granular Git revert for source; fixture DB/vault data remain preserved,
and no operator instance/PGDATA is adopted. No provider traffic, spending, push or auth edits.

**Original execution outcome — functional scoped PASS; whole canonical BLOCKED_BUDGET, NOT_CLOSED.**
Registry `a3e04a7` and catalog/exact-entry test `6d9c0c5` retain their
[53PASS](../../documents/verification/settings-c-evidence/registry-result.json) and
[72PASS](../../documents/verification/settings-c-evidence/catalog-result.json) API/private-PG evidence.
The [UI/guard record](../../documents/verification/settings-c-evidence/ui-result.json) composes
the original complementary reviews and focused fixes through `6dbaec5`: guided English C,
first-model explicit assignment confirmation (no automatic Default mutation), multiple saved
models per key, local search/chips/Back, separate role/output settings and exact-entry testing.
Real guard54PASS40.03s, ModelTest72PASS116.78s and UI4 **1PASS47.64s** exercise the existing
owners and PostgreSQL; UI4 includes first setup, saved-key31-add, real stale-CAS409,
exact `fixture/02` test without assignment changes, Disable/stale-wizard409 and API-process restart.
The [artifact index](../../documents/verification/settings-c-evidence/ui-artifacts.json) preserves
original reports/freezes/receipts byte-exact and29 real UI4 screenshots across320/390/1280/1440
including CSS200%, plus4 B04 regression captures. SOURCE built-browser checks cover long64,
focus/re-entry, target geometry, reduced motion and computed contrast; they are not PG/live proof.
Actual pixels preserve the selected centered900px composition and house controls, not a new
aesthetic approval. N01 LOW denial/recovery copy and minor Reload spacing remain nonblocking.

UI1/2/3 FAILs are retained with their narrowed DNS/locator/unsupported-matcher fixes and reviews.
Canonical1 remains **FAIL2/drained** at the obsolete Romanian B04 caller after3168API/23migration,
web196 and another Settings UI pass; its later CLI/release stages did not run. Caller-only
`6dbaec5` preserves the custom Unicode/whitespace objective and all assertions; focused R1
and real B04 **1PASS18.88s** confirm create/edit/CAS/refusals/reload/actual API restart.
The [supplemental actual controls journey](../../documents/verification/settings-c-evidence/controls-result.json)
passed **1PASS38.05s** on the unchanged built product: Replace/Disable confirmation/Reconnect,
catalog read/Cancel/Refresh, paging/chip removal/manual UNVERIFIED, committed-save receipt
recovery without resend, direct consent/Send and Cancel after SENT, UNKNOWN same-ID readback,
then API restart/census13 equality. Its two-file reviewed QA overlay is retained separately;
it does not overwrite the original UI4 source/evidence or introduce another product owner.
The first private-dependency build failure is retained, with its `.bin` link prerequisite repair.

The unchanged final `make check` **actually ran and timed out at3600s** in CLI source unittest,
outer2/gate124/drained, after3168API/23migration/196web/Settings1/E2E10 PASS. The remaining
[normal CLI/release components](../../documents/verification/settings-c-evidence/components-result.json)
passed separately:383source+383wheel+1status and73release/install tests, exact cleanup/data retained,
source34/build4 identity confirmed. This is composed scoped evidence, not a single canonical exit0;
whole-gate acceptance stays BLOCKED_BUDGET/NOT_CLOSED. Stop at the user's session/context boundary;
no third full run or successor automatically. No timeout widening, installed operator upgrade,
external provider traffic/spending, Prompt B/auth policy or T2/P4b closure.
Orca's undocumented parameter support remains unknown. N01LOWcopy/spacing were nonblocking at that snapshot.

### Subsequent installed delivery and selected-direction polish

The [same evidence register](../../documents/verification/settings-c-evidence/ui-result.json)
now records the separate normal installation of `7673066` at `http://127.0.0.1:8780`,
`/home/kali/.local/share/omnis-settings-c-9e51d10`, and the reversible global `omnis` launcher
redirection. Existing installed Wizard keep/discard and Stop→Start preserve the draft;
the operator's own model test was read as COMPLETED, never replayed for this continuation.

Presentation-only `7795b66` is accepted scoped in the checkout after complementary source
reviews and one real isolated browser/API/PostgreSQL journey. It makes Reload secondary,
shortens repeated copy, moves normal assignment identities and operation UUIDs into closed
details, and names the exact provider/model before consent. Active/unconfirmed Cancel,
receive-only recovery, cost and stale/unavailable states remain visible. Assignments/defaults,
API, schema, authentication and dispatch are unchanged. Desktop/mobile captures and keyboard
disclosure checks retain C; this is not a new aesthetic approval.

**The polished UI is delivered at8780 through the explicitly selected development setup.**
CLI6aa4d5e serves the exact accepted local build with narrow read-only mounts; the original
immutable release/image, instance, DB, keys and history remain. Real isolated lifecycle/rollback
and operator Stop→Start/two visible UI updates passed; no new profile or updater. Original
desktop/mobile/focus evidence is reused unchanged; fresh authenticated operator captures are
NOT_RUN without pairing. Selective cleanup removed24worktrees and dispensable QA artifacts,
not historical unique/uncertain data; root-owned QA data still needs local admin cleanup.
Canonical TIMEOUT/default check-web FAIL/causeUNKNOWN remain. No Prompt B/T2 or new provider call.

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
