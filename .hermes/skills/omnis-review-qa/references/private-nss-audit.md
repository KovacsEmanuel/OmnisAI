# Private NSS recovery for a real dependency audit

Use only when the canonical package audit is blocked by the host's NSS resolver, not for an advisory, lock drift or package failure.

1. Use `terminal` for a bounded differential: normal `getent`/HTTPS and `getent -s dns`/`dig`. A working DNS answer with a stalled libc path localizes the prerequisite; a HEAD405 only proves transport, not an audit PASS.
2. Keep the pinned real audit binary. Use `write_file` to prepare a private scratch NSS file with only the `hosts` policy changed to `files dns myhostname`; preserve the other NSS database policies. Do not edit the host configuration or disable TLS verification.
3. Reuse the minimal reviewed audit-only dispatch shape: for exact first argv `audit`, `exec unshare --user --map-root-user --mount --propagation private`, bind the private file onto `/etc/nsswitch.conf`, remount that bind read-only, then `exec` the real binary with quoted original argv. Execute non-audit commands directly outside the namespace so product UID and process behavior are unchanged.
4. Use `terminal` to test real version/argv failure/nonzero propagation and an actual network audit. Hash the host NSS before/after and all helper inputs; preserve stdout/stderr and limitations. Missing user namespaces or a mount failure is BLOCKED, never a fake audit or insecure fallback.
5. Request independent read-only review of the exact helper/evidence; keep it distinct from product review. Then pass the helper explicitly as the existing canonical audit-tool parameter and run one fresh serial owned fixture. Require the canonical receipt, source hashes and owned cleanup before crediting PASS; a separate successful audit does not certify the suite.

The namespace is not a general hostile-code or network sandbox. This dispatch supports canonical `tool audit ...`, not global options before the subcommand. Trusted helper paths must remain unchanged through execution. Do not introduce a persistent daemon, global resolver change, dependency update or new generic harness to repair this prerequisite.

Verified Omnis example and complete helper bytes: `documents/verification/p1-web-a02-dns.json`; final canonical results belong in the slice register, not this procedure.
