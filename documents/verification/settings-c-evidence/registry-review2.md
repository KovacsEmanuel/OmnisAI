# Settings registry — independent complementary review 2

## Verdict

**APPROVED_SOURCE_SCOPED — no concrete blocking findings in this review.** This approves the security/authority/transport/failure-path source scope for admission to the first isolated registry consumer QA. It is not a PostgreSQL, installed-runtime, provider, UI, release or full Prompt A acceptance. Missing PG execution is the next QA boundary, not a reason to refuse admission to that QA.

What this change does: It adds a bounded configured-model registry to the existing Settings owner. Models are saved locally with revision checks and durable command receipts, independently of existing assignments. This first increment does not add catalog discovery, the guided UI or selected-entry inference.

## Exact snapshot and ownership

- Repository: `/home/kali/OmnisAI`.
- Base/HEAD: `ed9091caeff29572d9f42861ae548a6094f732d6`.
- Branch: `checkpoint/p2-batch2-pause-20261015`.
- Candidate: 43 manifest-owned paths, including the six owned untracked source/test files. The worktree is an uncommitted candidate; no candidate commit or integration approval is implied.
- Manifest SHA-256: `60d1796a77f71e7178969248ed21036caa8ada723995ff15bd2a2b76e9307a84`.
- All 43 current file hashes matched at entry and again at handoff; zero mismatches. The byte-exact manifest copy is `source-snapshot.json` beside this report and contains every reviewed path/hash.
- Read-only review: no repository edits, commits, service launches, DB connections, migrations, credential reads or provider/target effects. Protected `tempkey.txt` and `documents/Omnis_Notite_Originale.html` were excluded from content reads/hashes.

## Findings

None confirmed. No style-only recommendations or requirements for later increments are being raised.

## Requirement → source assessment

| Criterion | Relevant source | Assessment |
|---|---|---|
| Preserve pairing/session/Host/Origin/CSRF | `api/src/omnis/security/host_origin.py:104-164,182-212`; `api/src/omnis/api.py:66-74` | The middleware change is only the body ceiling for exact PUT `/api/v1/settings/models`. Existing Host/Origin/session/CSRF logic remains unchanged and new routes remain behind it. Other verbs, trailing-slash route and existing providers write keep 4096. |
| Preserve old control authority and bounds | `api/src/omnis/transport/local_control.py:61-67,304-379`; `provider_key_models.py:76-93,113-125`; `provider_key_routes.py:47-103` | The 65536 physical reader does not admit oversized legacy operations. Non-registry frames are rejected above 4096; existing key command 3600/view 4096 validators remain. Kernel UID/capability checks, connection cap, deadlines and cleanup remain. |
| Full new frame/reply <=65536 | `provider_key_routes.py:49-74`; `local_control.py:355-369`; `provider_model_models.py:23-43,90-121` | Serialized request and complete reply are checked, including envelope/newline. Oversize registry replies become a small unavailable error; legacy replies are deliberately not clamped. Maximum exact escaped-ID fixtures pass. |
| One Settings owner; Stop/lease/concurrency | `provider_key_service.py:196-222`; `provider_model_service.py:142-222`; existing `instance/service.py:272-309,463-476` | Registry calls reuse the existing owner lock. New writes enter existing row-locked admission, check owner/epoch/generation/Stop and recheck live lease before commit. Current enabled connection/revision and registry/entry revisions are checked before inserts. Same-owner parallel commands serialize; the durable admission row remains the cross-owner boundary. These are source assessments, not a claim of executed PG overlap. |
| Failure atomicity / receive-only readback | `provider_model_service.py:119-175,176-222`; `provider_model_routes.py:23-49`; `provider_key_routes.py:96-103` | Registry, entries, revisions and receipt are within the same admission transaction. Stale/foreign/revoked/duplicate/entry65 denial occurs before writes. Exceptions or cancellation unwind the transaction; final lease loss prevents commit. Command digest conflict is distinct from exact receipt replay. Receipt reads intentionally precede mutation admission so committed history remains receive-only after Stop. API/client do not automatically resend after an unknown reply. |
| Typed durable identity and exact IDs | `migrations/versions/0016_provider_models.py:13-62,67-101`; `core/provider_schema.py:11-189` | Typed instance/entry/revision keys and identity/connection/registry foreign keys, exact connection+model uniqueness with C collation, finite output caps, immutable tables and readiness specifications are present. Migration backfill deduplicates current choices by exact identity without rewriting old selections/receipts. Actual PG enforcement/backfill remains NOT_RUN in this review. |
| Web boundary and old callers | `web/src/shared/api/providerModels.ts:9-31`; `client.ts:20-28,49-69`; supervisor callback and generated contract | Manual decoding checks exact fields, safe integers, UUIDs, exact ASCII IDs, deduplication/order and request-bound revision/cursor/command context. Client retains same-origin/no-store/redirect-error and single-attempt behavior. SaveSelection membership activation is explicitly deferred until the guided caller exists; no old UI guard is activated here. |
| Strict CLI schema / distribution compatibility | `cli/src/omnis_cli/{instance,start,release,backup}.py`; `ops/build_control_bundle.py` | Required schema changes consistently to 0016; older heads stay refused rather than silently adopted. Required wheel closure includes the migration and three new registry modules. No auth-policy change is introduced by this explicitly admitted propagation. Parent-recorded CLI/wheel evidence was not rerun. |

## Executed independent checks

1. Entry/final Python hash checks: **43 matched, zero mismatches**, manifest hash and HEAD as above; exit 0.
2. Focused SOURCE pytest, no database environment and no cache/bytecode writes:

   `env -u OMNIS_TEST_DATABASE_URL -u OMNIS_DATABASE_URL PYTHONDONTWRITEBYTECODE=1 api/.venv/bin/python -I -B -m pytest -p no:cacheprovider -c api/pyproject.toml` followed by these exact node IDs in `api/tests/test_provider_key_settings.py`:
   - `test_final_wire_size_and_secret_repr`
   - `test_invalid_secrets_are_bounded`
   - `test_registry_http_body_exception_is_exact_and_keeps_auth`
   - `test_registry_authority_uses_typed_identity_revision_and_foreign_keys`
   - `test_registry_has_separate_bounded_api_contract`
   - `test_registry_merge_is_additive_exact_and_revision_checked`
   - `test_registry_maximum_actual_dto_and_complete_wire_budgets`
   - `test_registry_capacity_and_bound_pages`
   - `test_registry_frame_exception_never_relaxes_legacy_limits`

   Flags: `-q -s --tb=short`. **14 passed in 0.96s, exit 0.** Actual serializer sizes: body41001, command41036, full frame41141, view11800, full reply12096 bytes. Fixture has 64 distinct 256-character IDs made entirely of JSON-escaped printable characters.
3. `PATH=/home/kali/.local/share/omnis-toolchains/bin:$PATH npm --prefix web test -- --no-file-parallelism src/shared/api/providerModels.test.ts`: **19 passed, one file, exit 0**. No web server/browser or backend was started.
4. Direct in-memory exercise of the actual `LocalControl._handle` writer with reader/writer doubles and `_dispatch` replaced; no socket/service/DB:
   - Actual old `ModelTestView(response_text="a"*8192)`: complete reply **9021 bytes, ok=true**.
   - Old native payload: complete reply **8282 bytes, ok=true**.
   - Synthetic admitted registry reply: **65094 bytes, ok=true**.
   - Synthetic oversized registry reply: replaced by **104-byte CONTROL_UNAVAILABLE, ok=false**.
   - All four assertions passed; client-task tracking empty after each handler; exit 0. This is SOURCE writer-boundary evidence, not a real transport/DB integration claim.
5. Programmatic OpenAPI comparison against HEAD: **zero changed existing paths**, exactly the three new registry paths; only existing schema changed is `ErrorCode`; zero other top-level changes. Exit 0.
6. `git diff --check`: exit 0.

## Limits and next decision

The parent-provided freeze records SOURCE122, CLI383, serial web170, quality/contracts and wheel14 matches. Those results were not presented as independent reruns here. Its default-parallel web three timeouts and other retained failed attempts remain retained; this review does not diagnose or erase them.

Proceed to the already-admitted bounded isolated PG registry save/receipt/paging/restart/migration consumer after the parent's complementary-review adjudication. Real schema enforcement, DB rollback under faults, lease/Stop overlap and restart durability are **NOT_RUN by this reviewer** and must be settled on that consumer; no PG PASS is claimed or demanded in advance.

No repository files were created or modified. Only this original report and its byte-exact source manifest snapshot were created outside the repository. Reticle is NOT_APPLICABLE to this source/API review; Chisel remains BLOCKED_NO_GO and was not invoked.

Not checked: PG/provider/installed/UI/canonical QA, catalog and selected-entry test; these remain outside this first-increment review.
Risk: source approval is not runtime acceptance, and this scratch report must be preserved by the parent before scratch expiry.
