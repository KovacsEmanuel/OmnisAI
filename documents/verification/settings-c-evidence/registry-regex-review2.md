# Settings registry — independent focused re-review 2, PostgreSQL regex repair

## Verdict

**APPROVED_SOURCE_SCOPED — zero concrete blocking findings in the three-file repair.** The changed source is admissible to fresh, isolated PostgreSQL QA after parent adjudication. This is not a PG PASS, integration approval, full Prompt A acceptance or approval of later UI/catalog/exact-entry model-test work.

**AICI:** implemented uncommitted candidate / affected SOURCE checks PASS / focused security re-review APPROVED_SOURCE_SCOPED / postfix real PG NOT_RUN. The original PG failures remain FAIL, not retrospectively green.

## Snapshot and ownership

- Repository `/home/kali/OmnisAI`; base/HEAD `ed9091caeff29572d9f42861ae548a6094f732d6`; branch `checkpoint/p2-batch2-pause-20261015`.
- Reviewed manifest `/home/kali/.hermes/cache/scratch/srfix/source-candidate-freeze.json`, SHA256 `537b949b6851d698691a7ebb045dee99017552c76e992f42632061a6e15cf0c2`. Byte-exact copy: `source-snapshot.json` beside this original report.
- Independently checked **43/43 current hashes**, zero mismatches, both during review and at handoff. Compared with prior freeze SHA256 `60d1796a77f71e7178969248ed21036caa8ada723995ff15bd2a2b76e9307a84`: exactly **3 changed / 40 unchanged** paths.
- Focus patch SHA256 `cc8f8dad7b2d88bfced8df806f90dc4a02a5e4e6ebd965f637a7730abc7b5d8b`. Reversed its hunks strictly **in memory** against current source; all three reconstructed old files match the prior manifest hashes. No patch applied to the checkout.
- Three reviewed hashes: `core/provider_schema.py` = `56f980b9a76b491ed233cf17ad35f0feeda80a10b9ed6184688f1dfc0d1c1751`; `migrations/versions/0016_provider_models.py` = `f1abe1bb40ce92727b53b4f75995e8a418fead9fa7017f563bb576d05a1e4c7e`; `api/tests/test_provider_key_settings.py` = `6fd2a07838abf109c3d1f8d6bce84797d5ff89313b90da05a093025344de58ff` (first two relative to `api/src/omnis/`).
- Read-only reviewer: no repository edit, staging, commit, DB/provider/target call or service launch. Protected `tempkey.txt` and `documents/Omnis_Notite_Originale.html` were neither content-read nor hashed. Preexisting WIP remains owned by the parent/developer.

## Requirement → source → assessment

| Criterion | Source | Assessment |
|---|---|---|
| Preserve exact ID domain | `0016_provider_models.py:22`; `provider_model_models.py:23–27`; `provider_key_models.py:48–52` | `^[!-~]{1,255}[!-~]?$` accepts exactly 1..256 printable ASCII characters under the retained C collation: 1..255 required, then zero or one from the same class. Empty, length257, space/control/DEL/non-ASCII remain excluded. Anchors/class are unchanged; no trim, case folding, escaping reinterpretation or identity conversion was introduced. |
| Preserve stored identity/security | `0016_provider_models.py:18–62,67–101`; `provider_model_service.py:57–90,142–222` | Only the CHECK pattern changed. C collation, exact connection+model uniqueness, typed identity/revision FKs, immutable history, backfill and parameterized owner inserts are byte-unchanged. The service still forwards the exact DTO model. No auth, owner/epoch/Stop/admission/transaction/timeout or error-policy delta. |
| Preserve readiness fidelity | `core/provider_schema.py:70–76`; regression `test_provider_key_settings.py:724–786` | Readiness uses the same exact pattern/constraint text as emitted migration DDL. It is not relaxed to ignore the constraint. Actual `pg_get_constraintdef` readback remains for PG QA. |
| Regression catches this cause | `test_provider_key_settings.py:724–786` | Captures the real emitted DDL without a DB, rejects numeric ARE bounds over255, compares readiness, checks real SaveModels DTOs at1/255/256 and denial at0/257/space/newline/non-ASCII/DEL. Author RED log fails at bound assertion; GREEN log passes. This is a focused source regression, not a native ARE parser certificate. |
| Preserve unaffected scope/bounds | 40 unchanged manifest paths; original complementary review | Original security approval is inherited only at its original scope. HTTP/session/CSRF, legacy transport bounds, registry batch64/page16/full-frame65536, output caps and durable read/replay behavior are unchanged by this repair. Affected SOURCE tests pass; no claim that earlier source review already proved PostgreSQL enforcement. |

PostgreSQL 18 documentation was independently retrieved: https://www.postgresql.org/docs/18/functions-matching.html#POSIX-QUANTIFIERS states bounds permit unsigned integers0..255 inclusive. This supports the identified source defect and the legal replacement, without substituting for running PostgreSQL.

## Independent execution

1. Python stdlib manifest/hash comparison and in-memory inverse patch validation described above: **exit0**. `git rev-parse HEAD`, `git status --short --branch`, `git diff --stat`, `git diff --cached --stat`, `git diff --check`: inspected; HEAD unchanged, index empty, diff check **exit0**. Initial attempt to read prior computed blob IDs with `git cat-file blob` failed (`bad file`, exit128 inside validation/overall exit1): those objects were not stored. The subsequent in-memory inverse/hash validation succeeded; no Git object/source writes were used to work around it.

2. Focused affected SOURCE tests, exact command (repository cwd):

```sh
env -i HOME=/home/kali PATH=/home/kali/.local/share/omnis-toolchains/bin:/usr/bin:/bin TMPDIR=/home/kali/.hermes/cache/scratch PYTHONDONTWRITEBYTECODE=1 api/.venv/bin/python -I -B -m pytest -p no:cacheprovider -c api/pyproject.toml api/tests/test_provider_key_settings.py::test_registry_model_sql_bounds_match_dto_and_readiness api/tests/test_provider_key_settings.py::test_registry_authority_uses_typed_identity_revision_and_foreign_keys api/tests/test_provider_key_settings.py::test_registry_http_body_exception_is_exact_and_keeps_auth api/tests/test_provider_key_settings.py::test_registry_has_separate_bounded_api_contract api/tests/test_provider_key_settings.py::test_registry_merge_is_additive_exact_and_revision_checked api/tests/test_provider_key_settings.py::test_registry_maximum_actual_dto_and_complete_wire_budgets api/tests/test_provider_key_settings.py::test_registry_capacity_and_bound_pages api/tests/test_provider_key_settings.py::test_registry_frame_exception_never_relaxes_legacy_limits -q -s --tb=short
```

**8 passed in1.02s, exit0.** Actual maximum fixture sizes: body41001 / command41036 / full frame41141 / view11800 / full reply12096 bytes. No DB variables, pytest cache or bytecode writes.

3. Direct in-memory domain comparison: same clean environment/interpreter with `-I -B -c`, AST-extracted current migration DDL pattern, actual SaveModel DTO and old/new Python regex. Cases comprise every printable ASCII character repeated at each length0..258, invalid byte characters at start/end and the256-character boundary, Unicode/newline controls and exact mixed-case/quoted IDs. **25,076 cases:24,067 valid /1,009 invalid; zero old/new/DTO disagreements; every accepted DTO preserves the exact string; exit0.** This is SOURCE/Python evidence, not PostgreSQL execution. The exact inline program used was:

```python
import ast,json,pathlib,re,sys
sys.path.insert(0,"/home/kali/OmnisAI/api/src")
from omnis.modules.settings.provider_model_models import SaveModel
from omnis.core.provider_schema import PROVIDER_TABLES
source=ast.parse(pathlib.Path("api/src/omnis/migrations/versions/0016_provider_models.py").read_text())
fn=next(n for n in source.body if isinstance(n,ast.FunctionDef) and n.name=="upgrade")
ddl=ast.literal_eval(fn.body[0].value.args[0])
pattern=re.search(r"model ~ .([^\x27]+).",ddl).group(1)
assert pattern=="^[!-~]{1,255}[!-~]?$"
old="^[!-~]{1,256}$"
spec=next(row[2] for row in PROVIDER_TABLES["provider_model_entry"][1] if row[0]=="provider_model_entry_model_check")
assert pattern in spec
cases={chr(c)*n for c in range(33,127) for n in range(259)}
bad=[chr(c) for c in range(256) if not 33<=c<=126]+["é","😀","\u2028"]
cases.update(part for char in bad for part in (char,"x"+char,char+"x","x"*255+char,char+"x"*255))
cases.update(["Exact/Case:Model", "exact/case:model", "quote\"\\id", "!"*256, "~"*256])
valid=0
for model in cases:
    expected=1<=len(model)<=256 and all(33<=ord(c)<=126 for c in model)
    assert (re.fullmatch(old,model) is not None)==expected
    assert (re.fullmatch(pattern,model) is not None)==expected
    try:
        parsed=SaveModel.model_validate({"entry_id":"00000000-0000-0000-0000-000000000001","expected_revision":0,"model":model,"output_tokens":64})
    except ValueError:
        assert not expected
    else:
        assert expected and parsed.model==model
        valid+=1
print(json.dumps({"source_only":True,"cases":len(cases),"valid":valid,"invalid":len(cases)-valid,"old_new_python_regex_and_actual_dto_match":True,"exact_string_preserved":True,"ddl_readiness_pattern":pattern},indent=2))
```

Author123SOURCE/Ruff/mypy and original diagnostic50PASS/2FAIL remain attributed evidence, not independent reruns here. Author's RED/GREEN logs were read. Diagnostic instrumentation removal is supported by the unchanged `test_provider_key_api.py` hash. The original source approval did not promise native PG execution and does not erase the later real failure.

## Limits and next decision

Admit the same bounded `test-provider-settings-pg` consumer on a **NEW attested fixture**, under the parent's authority. The invalid-bound source blocker is repaired; actual63/64-entry API success, seeded0015→0016 migration, physical readiness and downstream assertions are still unverified after this fix. Do not label that gate GREEN until executed. No widened timeout, weakened CHECK, backfill rewrite, new owner or harness is needed for this source repair.

No repository files changed. Created only this original report and byte-exact source snapshot in the reviewer-owned scratch directory. Reticle NOT_APPLICABLE; Chisel BLOCKED_NO_GO, not invoked.

Not checked: fresh PG/provider/installed/UI/canonical execution, Prompt B/auth changes, catalog or exact-entry inference; outside this focused mandate.
Risk: SOURCE approval is not runtime acceptance; parent must preserve this original report/snapshot before scratch expiry and adjudicate fresh PG QA separately.
