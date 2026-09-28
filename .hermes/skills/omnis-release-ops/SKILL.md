---
name: omnis-release-ops
description: "Use when packaging or releasing an Omnis slice."
version: 0.1.5
author: OmnisAI (KovacsEmanuel), Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [omnis, development]
---

# Omnis reproducible delivery and operations

## When to Use
P0 and P8: dependency pinning, CI, containers, readiness, backup/restore, packaging and release decisions. Do not deploy or publish merely because the package builds.

## Prerequisites
Read stack baseline and rejected dependencies; inspect current manifests/locks and the exact phase acceptance gate. Use `terminal` for real system/git state. No install into the global Hermes environment to solve an application dependency problem.

## Procedure
1. Reproduce the relevant environment from exact locks in an isolated location. Keep Node, API, Hermes, proxy and browser executor environments distinct. Verify package registry metadata and immutable image identity when selecting a new pin; never silently replace the baseline with latest.
2. Audit the resolved dependency graph and licensing. A clean resolver/build is not a security approval. Record rejected versions, advisories and the remediation/retest gate. No forced resolver override or weaker TLS as a shortcut.
3. Add commands only for implemented components; CI uses the same commands, no real credentials, no live LLM, no external target traffic. Avoid network installations as a hidden step in lint/test. Mock protocol tests remain separately labeled.
4. For containers check actual listening interfaces, ports, volumes, UID, health, shutdown and egress topology. Do not expose Hermes/MCP/admin services publicly. Verify application dev instrumentation is absent from the production artifact.
5. Before migrations or storage changes describe backup consistency and recovery compatibility. Test restore into a fresh isolated instance, lease/capability revocation and stopped startup. Include encryption-key availability without copying secrets into Git.
6. At release require backend state, UI counts, reports and evidence hashes to match one immutable snapshot. Run documented gates, dependency audit and fault recovery; label unsupported auth/browser/provider paths rather than advertising them.
7. Review final history/status and changed artifacts. Push/deploy only if separately requested; then read the exact remote SHA/service state back. For failure, preserve diagnostics and execute the predeclared rollback, not an unreviewed downgrade.

## Pitfalls
Host Playwright/Chromium validation is not certification of the planned executor version. Docker tags can move. Git rollback does not restore DB or secrets. Documentation readiness is not runtime readiness.

- A wheel that imports its app factory may still omit migrations or process entrypoints. Build/install with dependencies exported/hash-checked from the lock in a fresh scratch venv, then migrate a disposable PostgreSQL DB **outside the checkout**. Exercise the installed supervisor, real Unix IPC and actual HTTP process, including restart and state readback; reserve the loopback listener rather than adopting whatever answers on a free-port guess. A Python audit guard needs a negative control and remains distinct from OS confinement. Source-tree/ASGI success or an archive filename check is not release evidence.
- Before rerunning an integration gate after a session handoff, verify required environment presence without printing values. Missing ephemeral test credentials are a failed prerequisite, not permission to read personal stores or weaken tests. Recreate a uniquely named disposable project when needed; keep setup/test/cleanup in one process if environment continuity is uncertain, and stop only resources whose ownership was verified.
- Bound trusted asset I/O as well as DB/control probes. Byte/hash limits do not bound filesystem latency; cancelling `to_thread` leaves its worker alive. Fault-inject repeated concurrent waits and cancellation, require one shared outstanding read per app, preserve API-ready versus assets-unavailable semantics, and verify a permanently stalled worker cannot hold interpreter exit.
- Assert that source tests import the current checkout, especially with worktrees and editable installs. Neutralize ambient Python/mypy paths and pytest selection/plugin settings in canonical commands; use explicit project config and isolated interpreters. Reproduce from a clean local-HEAD worktree with its own locked environment, not a shared editable package or an accidentally narrowed test selection.
- For an installed launcher gate, assert the CLI exit code separately from parsed JSON: shell pipelines can hide a failing producer. Make live integration tests depend on the current wheel build even with parallel Make; a previous scratch venv is not the artifact under review. Per-recv socket timeouts are not total IPC deadlines: use a monotonic budget across connect/send/read and prove it with a peer that trickles fragments.
- For OCI artifact probes, name and label every resource before launch, then in `finally` inspect and attempt all owned-container cleanup before image-tag cleanup, even if build/run times out or the driver exits early. `--rm` alone cannot clean a container whose CLI was killed. Read back exact absence; report uncertainty if Docker is unavailable mid-cleanup. Explicitly strip an inherited image-probe flag from ordinary release gates and enable it only in the requested image target. Test a second nonroot UID against bundled public assets, not only the image default UID.
- For an installed-image timeout, `subprocess.run` kills only its direct child; own a process group before launch and terminate/reap it before inspecting Docker. An absent tag after finite inspections does not prove the daemon-side build finished: retain the private intent, refuse automatic retry even while the tag is absent, and report manual recovery rather than PASS. Recheck the canonical Unix socket, daemon ID and random ownership labels around cleanup, but do not call distinct Docker CLI invocations an atomic identity binding; same-UID/root socket replacement is outside the declared local threat model. Exercise a TERM-resistant real descendant and a tag appearing after the first inspect as separate negative controls.

## Verification
A clean checkout reproduces checks/build from locked inputs, deployment scope remains private, restoration has been exercised and every blocked gate is visible. Versioned instructions state what actually ran and how to undo external changes.
