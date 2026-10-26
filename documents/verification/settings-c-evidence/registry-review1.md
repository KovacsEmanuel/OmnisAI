# Settings registry — complementary reviewer 1, original report

## Verdict

**APPROVED_SOURCE_SCOPED** for the admitted first registry increment. No confirmed blocking correctness, persistence, migration/backfill, revision/CAS, exact-command readback or first-consumer compliance findings in this review. This admits consideration of the existing isolated PostgreSQL consumer QA after the complementary review; it does not claim PostgreSQL, installed, provider-live, UI or complete Prompt A acceptance.

Findings: `[]`.

## Exact snapshot and authority

- Repository: `/home/kali/OmnisAI`.
- Base and observed HEAD: `ed9091caeff29572d9f42861ae548a6094f732d6`.
- Frozen manifest: `/home/kali/.hermes/cache/scratch/settings-registry-dev/source-candidate-freeze.json`.
- Manifest SHA-256 independently verified: `60d1796a77f71e7178969248ed21036caa8ada723995ff15bd2a2b76e9307a84`.
- Independently hashed all 43 manifest-owned paths: zero SHA-256 mismatches. Included owned untracked source/test files; excluded protected untracked `tempkey.txt` and `documents/Omnis_Notite_Originale.html` before any content/hash access.
- Candidate remains uncommitted preexisting work; reviewer performed no repository edits, commits, service launches, database access or dependency installation.
- Read AGENTS/team-slice/review procedure, CONTRIBUTING product-admission rules, CURRENT, relevant architecture §5.3 and plan §8, and Settings design/admission. Scope is the first persisted registry consumer, not later catalog, exact-entry model testing, guided UI or activation of assignment membership enforcement. Prompt B/authentication and installed operator changes are excluded.

## Requirement → code → evidence/disposition

| Requirement | Inspected implementation and consumer | Disposition |
|---|---|---|
| Instance-wide 64-entry additive registry, exact connection/model identity and stable entry revisions | `provider_model_models.py`, `provider_model_service.py:57–91`, typed migration identity/revision tables; consumer adds 63 entries plus same exact ID on a second connection, then denies entry 65 | SOURCE compliant. Uniqueness is both typed DB identity and service enforcement; capacity is enforced on merged instance state, not merely request length. |
| Existing owner, admission and CAS | Existing `ProviderSettingsOwner.handle` lock delegates registry work; service validates current enabled connection revision, then persists inside existing `InstanceService.admission`, which locks/fences ownership/generation and rechecks owner before commit | SOURCE compliant. Registry/global and per-entry expected revisions are checked; identity cannot be repurposed. No second Settings owner. |
| Durable exact-command replay/readback and receive-only uncertain-outcome recovery | `provider_model_service.py:119–222`, shared exchange and new routes; immutable receipt, request digest, same transaction for registry revisions/entries/receipt | SOURCE compliant. Same command returns stored result; changed payload conflicts; GET by command never resends or admits a write. Old receipts intentionally retain their original bounded first-page result. |
| Revision/context-bound 16-entry reads | `page`, `ReadModels` validators, routes, manual TS decoder/client | SOURCE compliant. Continuation requires expected registry revision and exact cursor; changed registry denies stale continuation. Client binds command/revision/cursor, validates strict shape and entries, and does not automatically retry writes. Full traversal/reconciliation by the future guided UI is outside this increment. |
| 0015→0016 and empty upgrade, current-choice-only backfill, historical preservation | `0016_provider_models.py:67–101`, typed FK/check/unique definitions and readiness map; migration consumer `test_provider_key_api.py:399–578` | SOURCE compliant. Latest selection only; exact connection/model dedup, Default precedence for duplicate entry cap, other per-role caps retained in untouched selection payloads. Historical/disabled connection revisions remain referenced rather than remapped. Backfill is transactionally additive/idempotent. Actual SQL/upgrade execution remains NOT_RUN. |
| First real-consumer positive/negative cases | Existing `test-provider-settings-pg`; `test_provider_key_api.py` covers paired ASGI→real private UDS→owner→PG, durable receipt/replay/conflicts, paged 64, concurrent CAS, revoke, fresh app and owner, shutdown/readback; migration test covers retained old tables, constraints and readiness denial | Consumer is concretely implemented for admitted QA, not an isolated helper-only test. Its PostgreSQL assertions were inspected, not executed by this reviewer. Prior QA PASS is not required to admit that QA. |
| Preserve old Settings limits and old large model replies | Existing 3600 command / 4096 request frame / 4096 view validators retained; exception is only registry PUT/frame/reply; actual writer source tests exercised | Verified targeted tests below, including real legacy model-test reply 9021 bytes and native reply 8282 bytes. CLI delta inspected as strict 0016 schema/closure propagation, not authentication policy changes. |

## Independent execution

1. `api/.venv/bin/python -I -B -m pytest -c api/pyproject.toml api/tests/test_provider_key_settings.py -k 'registry or control_actual_writer' -q -s --tb=short -p no:cacheprovider`
   - Exit 0: **12 passed, 20 deselected**, 0.95s.
   - Actual writer: model test 9021-byte reply, native stub 8282-byte reply, registry 41141-byte request / 12096-byte reply; synthetic 65094-byte registry reply admitted and over-limit reply replaced with a 104-byte failure.
   - Actual DTO maximum: body 41001, command 41036, full request 41141, registry view 11800, full reply 12096 bytes.
2. Pinned toolchain readback: Node `v24.21.0`, npm `11.19.0`.
3. `PATH=/home/kali/.local/share/omnis-toolchains/bin:$PATH npm --prefix web test -- --no-file-parallelism src/shared/api/providerModels.test.ts`
   - Exit 0: **19 passed**, one test file, 973ms. Covers exact IDs/context, strict negative decoding, bound continuation and paired client calls/no automatic retry after lost reply.
4. `git diff --check`: exit 0.

The parent's broader SOURCE/CLI/web/quality/wheel evidence is recorded in the frozen manifest; this review does not claim to have rerun those suites. The retained three default-parallel web timeouts are not erased or retrospectively certified by the serial pass.

## Boundaries / next decision

Parent adjudicates this scoped review together with reviewer 2, then may admit the existing bounded private-PG consumer on these exact bytes. PostgreSQL schema/readiness/backfill/transaction behavior still requires that actual execution; successful collection/preflight is not execution. Catalog, exact-entry test, guided UI, final assignment membership guard and complete Prompt A remain later increments, not missing acceptance criteria for this source review.

Reticle: NOT_APPLICABLE to this API/decoder source review; unchanged UI not browser-tested. Chisel: BLOCKED_NO_GO, not invoked. No protected file, credential, installed instance, operator PGDATA, provider/target traffic or spending was accessed.

Skipped: real PostgreSQL, installed/runtime restart, browser/visual/catalog/provider-live and full canonical gates. Risk: SOURCE approval is not migration/runtime PASS; admit the already-defined isolated consumer QA before persistence acceptance.
