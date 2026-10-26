# R2 — focused read-only re-review of query / Content-Encoding repair

**Verdict: APPROVED_SOURCE_SCOPED. No surviving or new blocker in the four-file repair.** Parent retains adjudication, QA admission and integration authority; this is not runtime acceptance.

What this change does: permits both documented offset/limit query orders while retaining exact release URL validation. It rejects every non-identity Content-Encoding case-insensitively before HTTPX can decode the response, restoring the catalog page-byte guarantee without adding compression support.

## Exact snapshot and scope

- HEAD `66252862587f1f2f44cf81837372b2c855e8dfef`.
- Freeze `/home/kali/.hermes/cache/scratch/cfix/catalog-entry-fix-freeze.json`, SHA256 `e4c0e760c3dabac2fed58789b9ef6f1751b62fe05e3385b3fefa9a3af2431ba8`.
- Independently matched all **27 files / byte lengths / hashes before and after**; compared previous manifest: **23 unchanged**, three previously manifested files changed, existing `api/tests/test_model_sender.py` added to the manifest. The latter is not a newly created repository file.
- Four-file repair only: `api/src/omnis/modules/settings/provider_catalog.py`, `api/src/omnis/supervisor/model_sender.py`, `api/tests/test_provider_catalog.py`, `api/tests/test_model_sender.py`.
- Delta SHA256 `11c002c7f4b55e582fc951f3319073f294896fa39be6f85bb45e4035b20f85ba`; verified delta and six retained evidence logs against freeze hashes. `git diff --check` exit 0; staged diff empty.
- Reviewed changed code, affected production callers and regressions against architecture §5.3:341. Unchanged original complementary security review scope is preserved, not reopened or newly certified.

## Explicit original finding dispositions

### R2-CATALOG-01 — HIGH — CLOSED_SOURCE_SCOPED

Original report `/home/kali/.hermes/cache/scratch/catalog-r2-review-original.md` remains intact. At `model_sender.py:197-200`, `httpx.Headers` performs case-insensitive field lookup and combines duplicate values; lowercasing only the resulting identity comparison does not discard duplicate encodings. Gzip, uppercase GZIP and gzip/identity duplicates in both orders all fail closed, call `response.aclose()`, and raise `ENCODED_RESPONSE_DENIED` **before constructing an HTTPX Response or reading its stream**. Therefore HTTPX never obtains a compressed body to inflate past the permit.

Executed the real Transport / ResponseStream / HTTPX / metadata_page path through the existing eight-case regression: five encoded cases refuse unread and closed, mixed-case Identity succeeds, exactly 2,097,152 unencoded bytes succeed, and 2,097,153 identity bytes raise `RESPONSE_LIMIT`. These checks substitute only the httpcore pool reply and guard network access; they are SOURCE, not sockets/TLS/provider QA. Retained RED evidence includes the actual missing-denial failures on the old header lookup; current GREEN independently reproduced.

Byte-bound caller trace: `ResponseStream.__aiter__` (`model_sender.py:140-146`) checks cumulative raw bytes before yielding; with nonidentity encoding refused, HTTPX cannot expand yielded content. `provider_catalog_runtime.py:215-238` supplies `min(2097152, 16777216 - ingest.bytes)`, stops at zero remaining, accounts returned size and keeps the existing total guard. The unchanged 32-page / 8192-entry / 15-second guards remain in place. Independent two-chunk SOURCE control additionally accepted exactly a 64-byte remaining permit and refused 65 bytes with `RESPONSE_LIMIT`, with both streams closed. The 16 MiB operation boundary was traced in source, not exercised end-to-end through PG/runtime.

### R1-CATALOG-PAGING-01 — MEDIUM — CLOSED_SOURCE_SCOPED

Original report `/home/kali/.hermes/cache/scratch/settings-c-review1/catalog-entry-review1.json` remains intact. At `provider_catalog.py:99-116`, exact absolute release base or exact admitted relative path is checked independently of strict `parse_qsl(max_num_fields=2)` parsing. The parsed pairs must be exactly one limit=1000 and one expected forward offset, regardless of ordering. Duplicate, extra, blank, fragment and loop values do not pass.

Both absolute/relative bases and both query orders independently completed two rows. Existing negatives pass; an additional SOURCE control denied ten foreign/suffix-host/userinfo/explicit-port/scheme-relative/HTTP/fragment/duplicate/loop variants. No continuation URL is sent: CatalogIngest returns its owned integer offset; `refresh()` passes that integer and the release ENDPOINTS constant to metadata_page, which constructs its own URL. Query parsing therefore grants no URI authority, credential destination or arbitrary request option.

## Independently executed evidence

From `/home/kali/OmnisAI`, with PYTHONPATH/MYPYPATH/PYTEST_ADDOPTS/PYTEST_PLUGINS removed and TMPDIR set to the owned scratch evidence directory:

```text
api/.venv/bin/python -I -B -m pytest -c api/pyproject.toml -p no:cacheprovider api/tests/test_provider_catalog.py api/tests/test_model_test_routes.py api/tests/test_model_test_v2_contract.py api/tests/test_model_sender.py -k 'not tls_handshake_cut and not sdk_tcp and not missing_broker' -q -s
```

**59 passed, 8 deselected in 2.57s; exit 0.** Writer output unchanged: catalog command/frame/escaped-frame/reply 1261/1366/3433/38247; entry body/frame/reply 277/528/54151; legacy model/native replies 9021/8282.

Additional command: `env -u PYTHONPATH -u MYPYPATH api/.venv/bin/python -I -B -c <bounded assert-based two-chunk metadata_page and CatalogIngest controls>`; exit 0. Results: remaining=64/bytes=64 accepted, remaining=64/bytes=65 RESPONSE_LIMIT, ten invalid authority/query controls denied, four order/base positives complete. Only pool reply synthetic; TCP and admission guards raise if reached. No persistent new probe/harness was added.

Own evidence:
- `/home/kali/.hermes/cache/scratch/catalog-r2-fix-review/identity.json` — SHA256 `fe5b641fca4a0ff03e4d7d95c4e8125606eccf1eafa8de308b7802009cc631c9`.
- `/home/kali/.hermes/cache/scratch/catalog-r2-fix-review/source.log` — SHA256 `229dc56fae6fdd3f187270c004d23fb566a000527e734e56764fc657e9901c03`.
- `/home/kali/.hermes/cache/scratch/catalog-r2-fix-review/focused.log` — SHA256 `a988596b9a29f11173de613c5db9fa81070e07410d83d11e73b4203a3f2e8275`.

## Handoff and limits

No repository edits, commit, services, DB, sockets, credentials, provider/target effects or spending. Created only this original scratch report and the three own evidence files above. Protected `tempkey.txt` and `documents/Omnis_Notite_Originale.html` were not read. No issues encountered. Reticle NOT_APPLICABLE; Chisel BLOCKED_NO_GO.

SOURCE approval closes the two concrete defects only. After the other complementary focused verdict and parent adjudication, the existing bounded `test-model-test-v2-pg` target is the next real consumer; historical PG PASS is **not** a prerequisite for that first QA. PG attempts / harness-only cycles remain **0 / 0**; PG/native/installed/live/browser acceptance remains NOT_RUN. Quality evidence in the freeze was not rerun by this reviewer.

Not checked: unchanged 23-file scope was not re-audited; no Prompt B/auth/UI or installed/provider-live compatibility review.
Risk: SOURCE doubles do not prove PostgreSQL persistence, runtime Stop/quiescence or provider behavior; the parent must still obtain the admitted real-consumer QA before acceptance.
