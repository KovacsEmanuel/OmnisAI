---
name: omnis-chisel
description: "Use when evaluating Chisel for Omnis file tooling."
version: 0.1.0
author: OmnisAI (KovacsEmanuel), Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [omnis, development, mcp, security]
---

# Chisel adoption gate

## When to Use
A task proposes Chisel for compact file edits/search or reevaluates a new upstream release. This skill is an Omnis-authored evaluation procedure, not a copy of Chisel's license or an active MCP installation.

## Current prerequisite: NO-GO
Read `tools/development/chisel/README.md` and `audit.json`. The audited release failed real root/read-only/subprocess/body-limit controls. It is not enabled on Omnis. Keep native Hermes file/search/patch tools as the default; do not instantiate Chisel over the repo, home or runtime profile.

## Procedure
1. Check the exact requested revision and license text with `read_file`/`terminal`; release tags and embedded versions differ in the audited artifact. A 'latest' URL or root flag is not evidence of safety.
2. Compare relevant upstream changes against the failed controls, not marketing claims. Do not treat a new version number, install success or MCP tools/list response as remediation.
3. If a bounded reevaluation is authorized, prepare an OS-isolated disposable fixture: no host home/credentials, explicit writable mount, network denial, bounded process/output and exact artifact digest. Test read-only with a read-only mount. There is no unsandboxed fallback.
4. Prove valid file/patch/read behavior and separately challenge root/symlink handling, read-only mutation, subprocess authority, HTTP authentication/body cap where applicable. Read real file bytes/sinks back. A denied direct command does not prove a utility cannot spawn a child.
5. Keep shell_exec out of any proposed normal tool surface until its authority is independently constrained and verified. Do not use it to replace approved terminal/test commands or the assessment broker.
6. Record passed/failed/inconclusive per check and raw evidence location. Harness exit zero means completed measurement, not all guarantees passed. Clarify the redistribution license before copying upstream code/binary into the project.
7. Only after a new reviewed acceptance decision consider project-scoped MCP configuration on a disposable worktree. Preserve inverse config commands; no global auto-registration or credential inheritance.

## Pitfalls
The inspected implementation is a file-tool adapter, not a Rust refactoring engine, build system or pentest platform. README claims and examples disagreed with live behavior. Prompts and command-name allowlists are not filesystem/network sandboxes.

## Verification
The failure classes in audit.json must be resolved by real tests before activation; until then the correct result is BLOCKED with native tools available. Never claim the skill's presence makes Chisel installed, enabled or safe.
