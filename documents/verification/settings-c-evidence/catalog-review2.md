# R2 — independent read-only catalog / exact-entry review

**Verdict: CHANGES_REQUESTED_SOURCE_SCOPED — R2-CATALOG-01 must be fixed.**

Snapshot: HEAD `66252862587f1f2f44cf81837372b2c855e8dfef`, 26-file `/home/kali/.hermes/cache/scratch/scat/catalog-entry-freeze.json`, SHA256 `0451634a5a52103b2d32e83113cab9a9ac22b206e0d7d0197b91400aee6a192c`. All 26 paths/lengths/SHA256 matched at entry; own original identity: `/home/kali/.hermes/cache/scratch/catalog-r2-identity.json`.

What this change does: adds connection-revision-scoped catalog refresh/local search and a finite test of an exact saved entry, without writing the global Default. Review scope was untrusted output/secrets, endpoint/pagination/byte bounds, owner/Stop/concurrency and no hidden retry/duplicate spend; not the deferred UI membership guard.

## Must fix

### R2-CATALOG-01 — HIGH — mixed-case Content-Encoding bypasses catalog page cap

- **Location:** `api/src/omnis/supervisor/model_sender.py:197-200`, reached by new `metadata_page()` at lines 287-298 and `provider_catalog_runtime.py:220-236`.
- **Reproducer:** give the existing Transport an HTTP-core response with `Content-Encoding: gzip` (normal HTTP casing), compressed body 3,059 bytes representing a valid OpenRouter catalog JSON of 3,000,145 decoded bytes. The actual HTTPX client decompresses it because the transport checks a case-sensitive bytes dictionary for only `b"content-encoding"`. `metadata_page()` returns 3,000,145 bytes despite its 2,097,152-byte page permit; `CatalogIngest` accepts the row and reports complete with no reason because the total remains below 16 MiB. Lowercase `content-encoding` correctly raises `SendDenied("ENCODED_RESPONSE_DENIED")`. HTTP-core 1.0.9 `_receive_response_headers()` explicitly returns `event.headers.raw_items()`, preserving upstream casing, so this is reachable on the real seam, not only a fake-header normalization mismatch.
- **Violated criterion:** architecture §5.3 requires 2 MiB per upstream page and bounded total bytes. Encoding rejection must not depend on HTTP header case. The new catalog can claim READY after accepting an oversized page; a compressed bomb also allocates before the total-byte check.
- **Minimal fix:** inspect response headers case-insensitively (e.g. `httpx.Headers(response.headers).get("content-encoding", "identity")`) and continue rejecting every non-identity encoding before constructing the HTTPX response. Keep raw limits and add one regression through the real Transport/HTTPX seam with mixed-case gzip and lowercase negative control. No decompression feature is needed.
- **Scope note:** the faulty shared header lookup predates this candidate. This finding blocks the newly admitted catalog page-byte guarantee; it does not reopen unrelated historical T1 acceptance.

### Executed SOURCE reproducer (no sockets, DB, services or provider)

Command prefix: `env -u PYTHONPATH -u MYPYPATH api/.venv/bin/python -I -B -c '<code below>'`, cwd `/home/kali/OmnisAI`; exit 0.

```python
import asyncio, gzip, json, httpcore
from pathlib import Path
from contextlib import asynccontextmanager
from omnis.supervisor.model_sender import ModelSender
from omnis.modules.runs.model_test_contract import ENDPOINTS
from omnis.modules.settings.provider_catalog import CatalogIngest

@asynccontextmanager
async def guard():
    raise AssertionError("NO_NETWORK_GUARD")
    yield

class Stream:
    def __init__(self, data): self.data = data
    async def __aiter__(self): yield self.data
    async def aclose(self): pass

class Pool:
    def __init__(self, data, header): self.data, self.header = data, header
    async def handle_async_request(self, request):
        return httpcore.Response(200, headers=[(self.header, b"gzip")], content=Stream(self.data))
    async def aclose(self): pass

async def main():
    data = json.dumps({"data": [{"id": "exact", "name": "x" * 3000000,
        "supported_parameters": ["max_tokens"],
        "top_provider": {"max_completion_tokens": 128}}], "total_count": 1}).encode()
    compressed = gzip.compress(data)
    for header in (b"Content-Encoding", b"content-encoding"):
        sender = ModelSender(Path("/nonexistent-r2-probe"))
        sender.transport.pool = Pool(compressed, header)
        try:
            value, size = await sender.metadata_page(ENDPOINTS["openrouter"], "synthetic-key", guard, 0)
            ingest = CatalogIngest("openrouter")
            ingest.bytes += size
            ingest.add(value, "synthetic-key")
            print(json.dumps({"header": header.decode(), "raw_bytes": len(compressed),
                "page_limit": 2097152, "decoded_size": size,
                "over_page_limit": size > 2097152, "within_total_limit": size <= 16777216,
                "ingest_complete": ingest.complete, "reason": ingest.reason,
                "entries": len(ingest.entries)}))
        except Exception as exc:
            print(json.dumps({"header": header.decode(), "exception": type(exc).__name__, "reason": str(exc)}))
        finally:
            await sender.close()
asyncio.run(main())
```

Observed output:
```json
{"header": "Content-Encoding", "raw_bytes": 3059, "page_limit": 2097152, "decoded_size": 3000145, "over_page_limit": true, "within_total_limit": true, "ingest_complete": true, "reason": null, "entries": 1}
{"header": "content-encoding", "exception": "SendDenied", "reason": "ENCODED_RESPONSE_DENIED"}
```

## Other reviewed boundaries / evidence

No other confirmed blockers in the bounded review. Traced current-secret row rejection/allowlisted reasons, exact IDs without normalization, numeric release-only continuation, counted completion and local 16-entry paging; immutable exact-entry preparation/current connection checks at admission and sink; shared Settings lock/admission and exclusive task gate; durable replay/no auto-resend, one-call SDK/pool retry settings, conservative UNKNOWN, Cancel/drain/Stop paths; old API versus new operation namespaces and encoded input/reply budgets. This is source review, not concurrency/runtime proof.

Executed unchanged candidate SOURCE command:
`env -u PYTHONPATH -u MYPYPATH -u PYTEST_ADDOPTS -u PYTEST_PLUGINS TMPDIR=/home/kali/.hermes/cache/scratch api/.venv/bin/python -I -B -m pytest -c api/pyproject.toml api/tests/test_provider_catalog.py api/tests/test_model_test_routes.py api/tests/test_model_test_v2_contract.py api/tests/test_model_sender.py -k 'not tls_handshake_cut and not sdk_tcp and not missing_broker' -q -s`

Result: **48 passed, 8 deselected in 2.26s; exit 0.** Actual writer budget output: legacy model 9021; native 8282; catalog command 1261; frame 1366; escaped frame 3433; reply 38247; entry body 277; frame 528; reply 54151.

No repository files edited, no commits, no PG/services/provider/target effects. Only own scratch identity/report created. Protected `tempkey.txt` and `documents/Omnis_Notite_Originale.html` were not read. Parent adjudicates and designated developer fixes; targeted re-review follows the fix. PG QA remains NOT_RUN, not a prerequisite already required to have passed. Reticle NOT_APPLICABLE; Chisel BLOCKED_NO_GO.

Not checked: PG/native/installed/browser/live provider compatibility or the later UI guard. Source doubles do not establish runtime Stop/quiescence or provider behavior; the confirmed byte-boundary defect remains a blocker.
