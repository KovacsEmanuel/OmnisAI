---
name: omnis-api-data
description: "Use when building Omnis API and persistence."
version: 0.1.7
author: OmnisAI (KovacsEmanuel), Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [omnis, development]
---

# Omnis API and persistence

## When to Use
P0/P1 and later FastAPI endpoints, domain state, SQLAlchemy models, Alembic migrations, SSE or evidence metadata. Not for changing the stack by preference.

## Prerequisites
Read the active architecture, relevant ticket and stack pins. Inspect actual manifests before commands: the application may still be unimplemented. Keep API, Hermes and proxy dependency environments separate. Use `terminal`, `read_file`, `write_file`, `patch` and `search_files`.

## Procedure
1. Name the domain invariant and owning transaction before defining a route. Separate HTTP validation, domain decisions and storage; use typed Pydantic DTOs with explicit state/error enums. Do not expose ORM objects as an accidental API.
2. Write an integration test with synthetic data for the desired behavior and its denial/invalid-input control; demonstrate RED. Validate boundary input, authorization, Host/Origin/CSRF and local bootstrap policy where relevant.
3. Implement only the required transaction. Use optimistic concurrency and a real 409 test for concurrent edits; run/task revisions, evidence state and event sequence cannot be owned by a React cache or Hermes conversation.
4. Add the migration with the feature. Test an empty PostgreSQL database and upgrade from the previous revision. SQLite is not proof of PostgreSQL behavior. Inspect the actual image's PGDATA/mount contract, not a remembered older major.
5. For idempotent commands test duplicate/reordered delivery and competing writers. Use a transactional outbox/durable event contract only where the architecture requires it; SSE cursor replay must agree with canonical persisted state after restart.
6. For evidence writes test the file/DB finalization protocol, partial writes and crash windows; render untrusted content inertly. Bound raw, decompressed and retained bytes separately. Do not use the trusted-doc renderer for target data.
7. Generate frontend types from the local Omnis OpenAPI contract when introduced; verify drift in CI. Exercise the real route via HTTPX/ASGI plus database integration, not a mocked repository returning the expected answer.
8. Run targeted tests then the affected suite, type/lint checks and migration probes. Use the committed commands actually present in the component manifest. Document data migration rollback limitations, not merely `git revert`.

## Pitfalls
Do not swallow exceptions, retry uncertain external effects as if they were safe, return success for queued completion, or weaken validation to satisfy a linter. An in-memory smoke is not durability; a restart test must restart the owning process and read real state.

- Before fixture CREATE/DROP, use the shared private-manifest attestor: exact local daemon/CID/image/project/binds/UID/no-network/UDS, then compare the **connected PostgreSQL system identifier**. Keep the encoded URI in fixtures and decode only at the engine or explicit driver kwargs; serializing an already-decoded Unix host loses URI authority. Reject query/PG overrides, noncanonical paths and commas (libpq multi-host semantics) before connection. Never adopt an existing DB or fall back to TCP; re-attest before migration and teardown.
- A migration *failure* test must not send a valid DSN to an arbitrary fixed port hoping the connection fails: an unrelated DB there could accept it and receive DDL before the assertion. Exercise wrong-password failure on an attested UUID-named disposable DB; for config denials use inputs rejected before socket I/O. Re-attest ownership immediately before a long build-to-migration handoff.
- On PostgreSQL 18, `attnotnull=true` can coexist with `NOT NULL NOT VALID` and existing NULL rows. A compatible-schema probe must compare the exact authority column/**every default**/constraint set including `pg_constraint.convalidated` and `conenforced`; a revision stamp, partial default map or subset check can report a false ready. Exercise the real DDL mutation on an isolated DB before trusting the negative test.
- Bound connection, lock and statement waits **and the downstream coroutine** for every DB-backed HTTP operation. A PostgreSQL statement timeout does not bound a stalled client connection. Fault-inject a stall after a real transactional write; require bounded sanitized failure, rollback readback and no success cookie. Keep test subprocess deadlines finite.
- Preserve one-use issuance as well as consumption: retain an immutable receipt binding issuance ID, digest and original expiry. Replay after consumption, supersession or expiry must neither reactivate a code nor extend its TTL; a fresh ID must not reuse the same code. Commit failed-attempt counters before raising denial, and check expiry with current DB time after acquiring the lock.
- A private issuer's initial owner/lease check is not authority through a later blocking challenge-row lock: recheck the same pinned owner/epoch with PostgreSQL's current time **after** the wait and before transaction commit, so expiry rolls back both challenge and issuance receipt. Prove it with a real locked disposable DB row, an observed successful first check, real DB-clock expiry, and a rollback readback; a short production statement timeout may hide this race by failing earlier, so any test-only `SET LOCAL` timeout extension must be labeled and must never change production admission limits.
- Establish listener ownership, inode and permissions before an asynchronous serving call can yield. On the pinned Python, create a non-serving Unix server first, then start serving; inject cancellation at the first yield and verify the listener is gone and restart succeeds. A successful normal shutdown does not cover partial startup.
- When typing SQL results, validate driver values into strict records/scalars rather than casting dynamic values. Strict Pydantic models may reject `RowMapping` even when its fields are correct: normalize only the Mapping container to a dict, preserve every field, and retain strict value checks. Prove acceptance on real driver rows and rejection of coercions; sanitize validation failures as storage failures, not invalid client requests.
- Test cancellation together with a transport-close failure. A `return` inside cleanup can erase the original exception; suppress only the expected close error without returning from `finally`, and require the original cancellation to propagate.
- Keep health/status observation separate from authority renewal. Inspect the entire reused IPC handler, not only its command name: a status dispatch may call heartbeat. Reproduce with PostgreSQL expiry readback, continue polling across expiry without the owner loop, and require the lease to expire unchanged; validate owner/epoch without extending it.
- Require container-local TCP health for the final PostgreSQL server when the image initializes through a temporary Unix-only server. Prove the distinction with a fresh owned PG18 init marker: Unix pg_isready may exit0 before init completes while localhost TCP refuses, then the same TCP health must pass on the final server. Keep ports unpublished and the network private; pg_isready proves connection admission, not authentication/schema/identity. A phase spike does not establish an unrelated historical command failure or certify the installed bundle; rebuild and run its canonical gate separately.

## Verification
Acceptance includes valid/invalid input, concurrency, persistence/restart and schema compatibility. Record exact DB/Python versions and commands. Commit code, schema, tests and necessary docs as one coherent behavior change.
