# Local modification notice

This is **not an official Redocly release**. Omnis modifies the MIT-licensed
`@redocly/openapi-core@1.34.20` npm distribution, keeping its complete source,
compiled implementation, declarations and existing notices. The npm archive
omits the root license file; this repack includes the original `LICENSE.md`
from its registry-declared source commit `b563864727f1c7524021196d27bad4524f32e667`.

Local version: `1.34.20+omnis.picomatch.1` (SemVer build metadata).
The only behavior change backports the URL-header matcher replacement from
Redocly commit `f5ce2e82c72034b893e19bfcaad198930a685399` (published in 2.7.0):
`minimatch(url, pattern)` becomes `picomatch.isMatch(url, pattern)`.
The 2.x module reorganization and public API changes are NOT backported.
Source and CommonJS output receive the same two-line change. Package metadata
replaces minimatch with exact picomatch 4.0.7 (already in Omnis's frozen lock),
updates the corresponding development types, and identifies the local version.
The invalidated `tsconfig.tsbuildinfo` cache is omitted, not reused as build proof.

Reason: GHSA-g3hv-75wg-m249 / CVE-2026-118764. Upstream license and copyright
remain unchanged; this notice declares local changes, not upstream endorsement.
Omnis uses this only for developer-side trusted local contract generation.
Generic remote-schema behavior and arbitrary minimatch pattern equivalence are
not certified. No product runtime network permission is introduced.
