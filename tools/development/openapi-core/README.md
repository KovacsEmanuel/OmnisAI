# OpenAPI matcher backport — development only

**ACCEPTED_SCOPED — developer-only local contract generation.** R1/R2 reviewed
the exact artifact at `fadf396`; the full canonical gate at `ba6c6ff` returned
exit0/drained and main installation audit0. [Acceptance and retained failures](../../../documents/verification/settings-c-evidence/models-polish-20261029/blocked-resume.md).
`openapi-typescript@7.13.0` still requires Redocly `^1.34.6`. The public metadata
refresh found no compatible official fix for GHSA-g3hv-75wg-m249 /
CVE-2026-118764. Do not replace the 1.x API with 2.x or force the resolver.

The complete 1.34.20 npm distribution is retained with the exact changes in
[matcher.patch](matcher.patch): source + CommonJS matcher, dependency/types and
honest local build metadata. The official replacement uses `picomatch.isMatch`;
we reuse already locked picomatch4.0.7. No validation, lint, bundle or AST path
is removed. [upstream.json](upstream.json) records original/local SRI, SHA,
source revisions and the [MIT license](LICENSE.md). [NOTICE.md](NOTICE.md) is
included as `OMNIS-PATCH.md`; the missing original root license is added to the
archive. Only the invalidated upstream incremental build cache is removed.

The direct developer-only tarball dependency satisfies the generator's normal
SemVer range with `1.34.20+omnis.picomatch.1`. npm11.19.0 resolves one shared
core, without overrides/force/legacy-peer-deps. The lock removes only minimatch,
brace-expansion and balanced-match; unrelated entries/pins remain identical.
The local version is **not** a published Redocly release or an advisory waiver.

## Reconstruct and check

Use a disposable checkout, Node24.21.0/npm11.19.0, Python3.13.15 and GNU patch.
Set `TMPDIR` to owned scratch storage. Run with an empty private HOME/npmrc,
private npm cache and allowlisted environment: no ambient credentials, proxies,
`.env`, operator data or lifecycle scripts. Downloads are public npm/GitHub
artifacts only; never execute downloaded scripts. Do not build in the live
operator checkout. The following commands assume that clean environment:

```sh
# Download the source.tarball URL from upstream.json into owned scratch.
# repack.py verifies the recorded SHA-512 before extraction or applying a patch.
python3.13 -B tools/development/openapi-core/repack.py \
  "$TMPDIR/openapi-core-1.34.20.tgz" "$TMPDIR/rebuilt-openapi-core.tgz"
cmp "$TMPDIR/rebuilt-openapi-core.tgz" \
  tools/development/openapi-core/openapi-core-1.34.20-omnis-picomatch.1.tgz

npm --prefix web ci --include=dev --ignore-scripts --no-audit --no-fund
npm --prefix tools/development/anti-slop ci --include=dev --ignore-scripts --no-audit --no-fund
npm --prefix web run test:tooling
npm --prefix web run typecheck
npm --prefix web run lint
npm --prefix web test
npm --prefix web run build
npm --prefix web audit --include=dev --json
```

`repack.py` refuses a wrong source SRI and an existing output path. Archive
ordering, timestamps, owner fields and gzip header are deterministic; original
file modes are retained. Use balanced context around patch hunks: shortening
only one side to avoid a whitespace-only context line made GNU patch reject the
hunk; the corrected patch reapplies with fuzz=0 and unchanged output bytes.
Reapplying with Python3.13.15 produced identical bytes.
The distributed `lib/utils.js` was also rebuilt byte-exact from `src/utils.ts`
using the project's TypeScript5.9.3 `transpileModule` (CommonJS/ES2021); this is
an emit check, **not** the complete upstream Redocly typecheck/test suite.

For installation QA, compare **every actual installed package.json version**
with its lock entry, including nested node_modules, and verify every installed
core file against the local archive. `npm ls` alone is insufficient to catch
actual package drift. Assert one core and zero minimatch packages/declarations;
missing foreign-platform optional dependencies are separate, not a blanket skip.
Compare all built public file hashes against a build of the frozen original
source. Keep the actual audit RED and GREEN outputs, not just their summaries.

## Scoped author evidence

Evidence directory in the author workspace:
`/home/kali/.hermes/cache/scratch/t1-openapi-backport-evidence/`.
It contains command/exit JSON plus separate stdout/stderr, original metadata,
archive manifests and source/distribution bindings. This scratch path is not a
long-term acceptance record; the parent retains evidence at integration.

- `audit-red`: original frozen install exit0; audit exit1, three moderate nodes
  in the same minimatch chain. `matcher-red`: expected local identity assertion
  fails; compatibility controls already pass on the original implementation.
- `candidate-final-ci`, `audit-final-green`: fresh `npm ci` exit0 and audit exit0,
  zero vulnerabilities including dev dependencies. All146 actually installed
  package versions match lock;25 foreign-platform optional packages are absent.
- `package-inspection.json`: every installed core file matches the tarball;
  only three original archive files changed, plus license/notice additions and
  stale build-cache removal. `final-origin-build-identity.json` binds every
  installed package path and unchanged generator/schema/generated contract.
- `tooling-final-green`:9 tests, including actual Redocly positive/negative
  synthetic URL-header selection, failed HTTP response propagation (customFetch,
  **no HTTP**), valid local `$ref`, missing-ref refusal, lint refusal and rejected
  Swagger2 input. Expected refusal diagnostics are emitted by the real library.
- Typecheck/lint/build exit0. Generated TypeScript is byte-identical. All built
  public files equal the original source build; JS/CSS also match the read-only
  live public files. No live build or write was performed.
- Documentation integration initially failed its historical probe pin equality
  when the new direct dependency was put in `frontend_build`. The fix keeps
  that historical map/fixture unchanged and admits the new exact pin only via
  `frontend_openapi_patch_t1.selected_pins`; no test assertion was weakened.
- Initial wide web run:353 PASS/1 FAIL waiting for an unrelated wizard button;
  retained in `web-tests-green` despite its label. Narrow localization:24 PASS.
  Final normal `npm test`:354 PASS, no timeout/worker/test changes. The initial
  failure's cause remains UNKNOWN; this patch does not claim to repair it.

## Limits and retirement

The input remains the trusted local Omnis schema and internal references.
Synthetic URL tests exercise the actual patched reader without granting remote
schema access. Arbitrary minimatch/picomatch pattern equivalence and upstream's
entire test suite are not certified. No API/CLI/PG/browser/lifecycle/canonical
probe, provider call, session/T2 work or operator mutation is part of this slice.
Reticle is NOT_APPLICABLE; Chisel remains BLOCKED_NO_GO.

Independent exact-snapshot reviews and the parent's integration/canonical gate
passed for the recorded scope; arbitrary remote-pattern equivalence and T2 are
not certified. When a compatible official fixed release exists, remove this
local dependency/patch after equivalent checks. Rollback: revert integration
before the baseline annotation, then fresh install from the reverted lock;
that restores the **known audit blocker**, not a safe accepted release.
