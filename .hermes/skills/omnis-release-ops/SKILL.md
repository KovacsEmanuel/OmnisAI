---
name: omnis-release-ops
description: "Use when packaging or releasing an Omnis slice."
version: 0.1.0
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

## Verification
A clean checkout reproduces checks/build from locked inputs, deployment scope remains private, restoration has been exercised and every blocked gate is visible. Versioned instructions state what actually ran and how to undo external changes.
