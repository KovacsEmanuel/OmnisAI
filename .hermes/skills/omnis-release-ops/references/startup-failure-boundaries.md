# Startup failure boundaries

Use with the installed-start acceptance and `omnis-review-qa`; this is a focused
failure matrix, not a new process-owner framework or authorization for Docker/DB.

## Observe the source of uncertainty

1. List the subprocess outcomes that can reach cleanup: exception/timeout before
   or after send, signal termination, ordinary nonzero refusal, successful exit,
   and malformed output/decoding after exit. Distinguish a known refusal from a
   lost acknowledgement. A failed client does not prove a daemon cancelled work.
2. Trigger the producer's actual branch. A test starting with `uncertain=true`
   only proves the consumer's predicate; it cannot show that a signalled child
   sets the flag. A narrow real local child can exercise wait/returncode safely,
   while daemon seams remain explicitly substituted.
3. Feed the observed state into cleanup and assert **zero DB stop/remove** under
   uncertainty, not merely a final exit 4 after an unsafe effect. Recheck after
   non-DB removal because that operation can introduce new uncertainty.
4. Do not infer the full family is drained from `wait()` of the direct child.
   Keep an unknown family/daemon outcome conservative. Never repair this by
   signalling a numeric PID/PGID after reap; preserve owned identity through any
   signal operation. Follow the existing ownership model and do not promote a
   WIP owner merely to make this regression green.
   - Inject interruption at pipe close/finally as well as inside wait: an exception
     in finally can bypass the preceding handler. Establish conservative flags
     before effects and keep them until acknowledgement, decoding and cleanup
     all complete; successful later commands must preserve earlier uncertainty.
   - Revoke numeric signal authority before entering a reap-capable operation.
     `Popen.returncode is None` is not proof of an unreaped child: Python can be
     interrupted between kernel waitpid and publishing returncode, including
     during its KeyboardInterrupt retry. Test one and repeated interrupts there
     with real reap and intercepted signal attempts. If using WNOWAIT to retain
     identity, bound the pre-reap wait and test EOF before a still-live child exits.
     This assumes the existing exclusive child owner, not an arbitrary concurrent
     reaper or proof of daemon cancellation/detached-descendant drainage.
5. Keep boundary evidence separate: real child termination + mocked daemon
   proves a branch and its consumer, not Docker-side cancellation. A delayed
   daemon effect needs its own authorized isolated probe and exact cleanup
   readback. Retain diagnostics/data rather than rescuing uncertainty into PASS.

6. Bind an installed interruption oracle to the actual phase boundary, not just
   its name. Publish an HTTP/control-wait marker only after preceding subprocess
   attestations complete: even a read-only Docker client can leave an unknown
   family if interrupted. Reproduce the ordering with real journal reads and
   rerun the installed command; keep missed-phase and UNCERTAIN outcomes failing,
   without reset/rescue of an older uncertain attempt or weakening its DB gate.

## Verify the installed refusal protocol

1. Choose malformed input that reaches the intended decoder/validation branch
   **within** the accepted byte cap; an oversized file rejected earlier is not
   coverage of excessive nesting, encoding or structural expansion.
2. Invoke the real installed console script from an external cwd with disposable
   private XDG paths. Check its module/artifact revision before attributing the
   result. An import error or missing prerequisite is not the expected denial.
3. Assert the contractual exit, parseable sanitized JSON and readiness flags,
   absence of raw payload/secret/traceback, and no unintended state/resources.
   Catch a specific boundary exception rather than hiding arbitrary programming
   errors under a blanket handler.
4. Demonstrate ordinary valid and invalid controls through the same parser and
   retain its strict schema/path/checksum checks. A byte cap is not a nesting
   bound, an internal checksum is not independent provenance, and a refusal is
   not correct just because no service started.

## Close the review, not just its last finding

Bind evidence to revision/files/scenario. A focused re-review closes that fix;
it does not cover untouched acceptance requirements. Preserve historical PASS,
record genuinely new defects as CHANGES_REQUESTED, and name both the immediate
correction in the current SL and the next **new** SL from the unchanged plan.
Do not rerun a broad gate as a substitute for first reproducing the uncovered
branch, or call documentation checks a product repair.
