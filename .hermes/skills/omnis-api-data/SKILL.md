---
name: omnis-api-data
description: "Use when building Omnis API and persistence."
version: 0.1.29
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
Read the active architecture, relevant ticket and stack pins. Inspect actual manifests before commands: the application may still be unimplemented. Keep API, runtime/executor and proxy dependency environments separate. Use `terminal`, `read_file`, `write_file`, `patch` and `search_files`.

## Procedure
1. Name the domain invariant and owning transaction before defining a route. Separate HTTP validation, domain decisions and storage; use typed Pydantic DTOs with explicit state/error enums. Do not expose ORM objects as an accidental API.
2. Write an integration test with synthetic data for the desired behavior and its denial/invalid-input control; demonstrate RED. Validate boundary input, authorization, Host/Origin/CSRF and local bootstrap policy where relevant.
3. Implement only the required transaction. Use optimistic concurrency and a real 409 test for concurrent edits; run/task revisions, evidence state and event sequence cannot be owned by a React cache or model conversation.
4. Add the migration with the feature. Test an empty PostgreSQL database and upgrade from the previous revision. SQLite is not proof of PostgreSQL behavior. Inspect the actual image's PGDATA/mount contract, not a remembered older major.
5. For idempotent commands test duplicate/reordered delivery and competing writers. Use a transactional outbox/durable event contract only where the architecture requires it; SSE cursor replay must agree with canonical persisted state after restart.
   Bind finite UI consent to the existing instance generation before consent/Save and carry that unchanged precondition into locked server admission: a persistent session or fresh owner status must not silently reauthorize unsent work after Stop→Start. Cover before-first-call and between-call windows; distinguish refused HTTP attempts from new operations/SENT/provider I/O. Reuse the existing owner, not a queue or session-reset workaround.
6. For evidence writes test the file/DB finalization protocol, partial writes and crash windows; render untrusted content inertly. Bound raw, decompressed and retained bytes separately. Do not use the trusted-doc renderer for target data.
7. Generate frontend types from the local Omnis OpenAPI contract when introduced; verify drift in CI. Exercise the real route via HTTPX/ASGI plus database integration, not a mocked repository returning the expected answer.
8. Run targeted tests then the affected suite, type/lint checks and migration probes. Use the committed commands actually present in the component manifest. Document data migration rollback limitations, not merely `git revert`.

## Pitfalls
Do not swallow exceptions, retry uncertain external effects as if they were safe, return success for queued completion, or weaken validation to satisfy a linter. An in-memory smoke is not durability; a restart test must restart the owning process and read real state.

Păstrează validarea strictă a tuturor schemelor/Ref/identităților, replay receive-only fără reexecuție și cauzele UNKNOWN imuabile. Verifică paritatea producer/consumer și callerii reali înainte de a promova dovada helperului.

## Verification
Acceptance includes valid/invalid input, concurrency, persistence/restart and schema compatibility. Record exact DB/Python versions and commands. Commit code, schema, tests and necessary docs as one coherent behavior change.

## Referințe la cerere

- [postgresql-transactions](references/postgresql-transactions.md)
- [retained-native-contracts](references/retained-native-contracts.md)
