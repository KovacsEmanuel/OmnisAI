# Registry regex fix — independent focused re-review 1

## Verdict

**APPROVED_SOURCE_SCOPED; ADMIT_POSTFIX_PG_QA.** Findings: `[]` (no confirmed blocking defect in the three-file delta). The replacement preserves exactly 1–256 non-space printable ASCII characters and uses legal PostgreSQL ARE bounds. Migration DDL and the exact physical readiness expectation agree. This admits the already-defined fresh private-PG consumer after the parent's complementary-review adjudication; it is not PostgreSQL acceptance or full Prompt A acceptance.

## Exact snapshot / ownership

- Repository `/home/kali/OmnisAI`; base and observed HEAD `ed9091caeff29572d9f42861ae548a6094f732d6`.
- Current freeze `/home/kali/.hermes/cache/scratch/srfix/source-candidate-freeze.json`, independently verified SHA256 `537b949b6851d698691a7ebb045dee99017552c76e992f42632061a6e15cf0c2`.
- Prior freeze `/home/kali/.hermes/cache/scratch/settings-registry-dev/source-candidate-freeze.json`, independently verified SHA256 `60d1796a77f71e7178969248ed21036caa8ada723995ff15bd2a2b76e9307a84`.
- All 43 owned current paths independently checked: zero size/hash mismatches at entry; zero hash mismatches at handoff. Same path set; exactly three changed hashes, 40 unchanged.
- Exact changed files:
  - `api/src/omnis/migrations/versions/0016_provider_models.py`: SHA256 `f1abe1bb40ce92727b53b4f75995e8a418fead9fa7017f563bb576d05a1e4c7e`.
  - `api/src/omnis/core/provider_schema.py`: SHA256 `56f980b9a76b491ed233cf17ad35f0feeda80a10b9ed6184688f1dfc0d1c1751`.
  - `api/tests/test_provider_key_settings.py`: SHA256 `6fd2a07838abf109c3d1f8d6bce84797d5ff89313b90da05a093025344de58ff`.
- Focused delta `/home/kali/.hermes/cache/scratch/srfix/source-fix.patch`, independently verified SHA256 `cc8f8dad7b2d88bfced8df806f90dc4a02a5e4e6ebd965f637a7730abc7b5d8b`; `git apply --reverse --check` succeeded on the current bytes.
- Candidate is preexisting/uncommitted. No repository file edits, staging or commits. Only this report was created in owned scratch. No DB access, services, provider/target effects, installations or credential reads. Protected `tempkey.txt` and `documents/Omnis_Notite_Originale.html` excluded before any content/hash access.

## Requirement → affected consumer → assessment

| Criterion | Inspected source / test | Assessment |
|---|---|---|
| Preserve exact model domain | `0016_provider_models.py:22`; `provider_model_models.py:23–27`; old `provider_key_models.py:48–52` | `^[!-~]{1,255}[!-~]?$` consumes 1–255 class characters followed by zero/one same-class character: no gap at 255/256, no empty/257 acceptance. `COLLATE "C"` remains on the column; `~` remains case-sensitive and both anchors remain. No trim/case normalization or different identity domain. |
| Legal PostgreSQL syntax, not merely Python acceptance | PostgreSQL 18 §9.7.3.1/2/4 and actual emitted DDL | Authoritative docs independently retrieved: brace bounds are 0..255 inclusive; `?` is zero/one; `^`/`$` anchor the string and default is non-newline-sensitive. The optional quantifier applies to a second bracket atom, not directly to another quantifier. Thus the change removes the invalid bound rather than weakening input validation. |
| Readiness parity / strict refusal | `provider_schema.py:70–76`; `core/schema.py:433–461`; new test `test_provider_key_settings.py:724–786` | Exact expected `pg_get_constraintdef` text changes in lockstep. Validated/enforced flags and equality-based physical checks are untouched. Old/bad constraint definitions are not newly accepted. Actual catalog rendering remains for PG QA. |
| Empty and seeded 0015→0016 upgrade; preserve history | Entire migration, especially lines 64–101; `test_provider_key_api.py:399–578` | Only CHECK text changes. Backfill CTE, latest-selection deduplication, Default cap precedence, old historical tables, connection-revision references, triggers and transactions are unchanged. Same corrected CHECK is reached by API insertion and seeded backfill. Empty upgrade alone could not have caught the earlier lazy evaluation failure. |
| Preserve persistence / owner transaction | `provider_model_service.py:164–222`; prior complementary reports | New identities still use the same INSERT at lines 194–200 inside the existing owner/admission transaction; no service, timeout, batch, receipt, backfill or older-migration workaround. The 40 unchanged-file approvals are inherited only within their original scope. |
| Regression proves what it claims | New source test plus unchanged native consumer | Test captures emitted migration SQL, rejects numeric bound256, binds readiness and checks DTO agreement. It does not execute PostgreSQL: Python `re.fullmatch` is not evidence for PostgreSQL `~`, CHECK enforcement or catalog deparsing. Existing PG target exercises real API INSERT, empty/seeded upgrade, invalid-space CHECK refusal, history and readiness; its model strings are short, so passing that target must not be described as an exhaustive native 256-boundary test. This limit does not block admission to QA. |

SQL semantics reference independently read: https://www.postgresql.org/docs/18/functions-matching.html#POSIX-QUANTIFIERS (bounds/quantifiers), #POSIX-BRACKET-EXPRESSIONS (collation), #POSIX-METASYNTAX (default newline mode). No native PostgreSQL execution by this reviewer.

## Original failures / disposition

Read the author's `/home/kali/.hermes/cache/scratch/srfix/report.md` and both original complementary reports (`settings-registry-review1-60d1796a-original.md` and `settings-registry-review2-complementary/report.md`). Parent's 50PASS/2FAIL35.91s and author's diagnostic 50PASS/2FAIL35.20s remain FAIL evidence, not independent reruns here. Their reported `InvalidRegularExpression`/SQLSTATE2201B has a source-confirmed cause in the old unsupported brace bound. Both affected callers evaluate the same CHECK. This delta addresses that source cause; downstream API63/64, seeded upgrade and catalog/readiness success remain pending actual post-fix QA. No retrospective PG PASS and no demand that QA must already pass before it is admitted.

Editing 0016 is scoped to this unshipped candidate. This is not an in-place repair procedure for an already deployed database claiming the same revision; Git changes do not mutate such a database.

## Independent commands / exits

1. `git status --short --branch && git rev-parse HEAD && git diff --stat` — exit0; observed preexisting dirty candidate, base above. `git diff --cached --stat` — exit0/empty.
2. Direct Python SHA256/size comparison over both manifest-owned path maps — exit0; both manifest hashes above, 43 matched, exact three-file delta/40 unchanged. Handoff SHA256 check — exit0/43 matched, same HEAD, staged NONE. No protected/unowned content read.
3. `git apply --reverse --check /home/kali/.hermes/cache/scratch/srfix/source-fix.patch` — exit0. `git diff --check` — exit0 at entry/handoff.
4. Exact SOURCE test command:

```sh
env -i HOME=/home/kali PATH=/home/kali/.local/share/omnis-toolchains/bin:/usr/bin:/bin TMPDIR=/home/kali/.hermes/cache/scratch api/.venv/bin/python -I -B -m pytest -p no:cacheprovider -c api/pyproject.toml api/tests/test_provider_key_settings.py::test_registry_model_sql_bounds_match_dto_and_readiness api/tests/test_provider_key_settings.py::test_registry_authority_uses_typed_identity_revision_and_foreign_keys api/tests/test_provider_key_settings.py::test_registry_has_separate_bounded_api_contract api/tests/test_provider_key_settings.py::test_registry_merge_is_additive_exact_and_revision_checked api/tests/test_provider_key_settings.py::test_registry_capacity_and_bound_pages -q --tb=short
```

Exit0: **5 passed in 0.99s**. No DB, listener or service tests selected.

5. Additional direct emitted-DDL/DTO oracle command:

```sh
env -i HOME=/home/kali PATH=/usr/bin:/bin TMPDIR=/home/kali/.hermes/cache/scratch api/.venv/bin/python -I -B -c 'import importlib,re,sys; sys.path.insert(0,"/home/kali/OmnisAI/api/src"); from omnis.modules.settings.provider_model_models import SaveModel; m=importlib.import_module("omnis.migrations.versions.0016_provider_models"); statements=[]; original=m.op.execute; m.op.execute=statements.append; m.upgrade(); m.op.execute=original; p=re.search("model ~ \x27([^\x27]+)\x27",statements[0]).group(1); rx=re.compile(p); n=0; base={"entry_id":"00000000-0000-0000-0000-000000000001","expected_revision":0,"output_tokens":64}; cases=["x"*length for length in range(259)]+[chr(code) for code in range(256)]+["x"*position+bad+"x"*(255-position) for bad in (" ","\n","\r","\t","\x7f","é") for position in (0,127,255)]; from pydantic import ValidationError;
for text in cases:
 expected=1<=len(text)<=256 and all(33<=ord(char)<=126 for char in text)
 assert (rx.fullmatch(text) is not None)==expected
 try: value=SaveModel.model_validate({**base,"model":text}); accepted=True
 except ValidationError: accepted=False
 assert accepted==expected
 n+=1
print("SOURCE domain oracle",n,"cases PASS; lengths0..258, byte codepoints0..255, embedded/boundary denials; Python regex + DTO, NOT native PostgreSQL"); print("emitted_pattern",p); print("migration_statements",len(statements)); assert len(statements)==2'
```

Exit0: **533 SOURCE cases PASS**, emitted pattern `^[!-~]{1,255}[!-~]?$`, two migration execute calls captured. Checks lengths0..258, codepoints0..255, and invalid characters at beginning/middle/end of 256-character strings. Neither Python regex nor DTO is presented as PostgreSQL execution.

## Boundaries / next decision

AICI: SOURCE candidate implemented; focused delta APPROVED_SOURCE_SCOPED; post-fix PG NOT_RUN. Parent may admit the same `test-provider-settings-pg` target on a NEW attested disposable fixture, with required complementary review and existing safety/cleanup controls. No additional product feature, harness, timeout change or prior-PG-PASS prerequisite is requested.

Reticle NOT_APPLICABLE; Chisel BLOCKED_NO_GO, neither invoked. No full audit/repeated CLI/web/quality gates on unchanged bytes. Plugin lookup `plugin:ponytail` returned not found; supplied inline Ponytail rules were followed without installation/config changes.

Skipped: native PostgreSQL/installed/provider/browser/canonical QA, Prompt B/auth, catalog/UI and unrelated 40-file re-audit. Risk: SOURCE approval does not establish runtime migration/readiness success; preserve original FAIL evidence and this scratch report before expiry.
