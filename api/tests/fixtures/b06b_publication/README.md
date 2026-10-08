# Independent B06b C01 consumer

`source/` contains newly authored synthetic source bytes, not copied B06a data,
accepted evaluation receipts or an operator profile. `consumer.py` copies only
its explicit file inventory into a fresh private scratch root. It independently
computes package/material/index/closure and RecordEnvelope digests; it does not
import product hashing or historical fixture helpers.

## Execution

- Source gate: the parent integrates product + tests, then runs the existing
  private attested runner with `--target test-b06b-publish-pg`. No test provisions
  a service; the existing `conftest.py` owns attested UUID database acquisition.
- Separately installed QA: set `OMNIS_B06B_PYTHON` to the installed copy's exact
  interpreter and `OMNIS_B06B_INSTALLED=1`. CLI subprocesses use `-I -B -m` from
  the new scratch directory, not the checkout. For tests exercising in-process
  fault/dispatch seams, run pytest in that installed interpreter and override
  the checkout path with `-o pythonpath=`. Ensure its test dependencies exist;
  never silently fall back to source imports.
- `OMNIS_B06B_SOURCE_ROOT` selects an explicit source tree for CLI subprocesses
  during a source-only consumer check. This is not installed-wheel evidence.

The trusted confirmation consumer opens a real PTY for stdin/stderr, leaves
stdout as a distinct JSON pipe, verifies all selected IDs/digests and both PASS
statuses before sending the exact `yes`, and bounds/reaps its subprocess.
Concurrent Publish tests hold the real owner advisory lock and require two
backends observed through `pg_blocking_pids` before releasing the blocker.

`test_b06b_publication_migrations.py` creates only a new, deliberately
unqualified migration sentinel under 0009; it never adopts an old release.
The upgrade must preserve this row and then exercise fresh qualification,
confirmation, Publish and readback under 0010.

The precommit exception and postcommit consumer response discard are explicitly
software faults. They are not physical crash/power-loss or server ACK-loss
proof. Source compiler/PURE success, collection and static checks do not claim
PG/TTY/CAS integration PASS. Those require the parent's actual private gate.
