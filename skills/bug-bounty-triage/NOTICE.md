# OmnisAI product source import — bug-bounty-triage

State: **IMPORTED_UNPUBLISHED / NOT_QUALIFIED / NOT_ACTIVATED**.
These are descriptive import metadata, not runtime enforcement or activation controls.

## Destination and ownership

This directory belongs to the existing top-level OmnisAI **product** source library
`skills/`, alongside `skills/recon-mapping-contract/`; it is NOT a development-agent
skill in `.hermes/skills/`, a global Hermes profile, or a newly discovered runtime root.
Integration target (not written by this task): `/home/kali/OmnisAI/skills/bug-bounty-triage/`.
Worktree: `/home/kali/.hermes/cache/scratch/hermes-triage-import-4edbc534a0a0`; local base `2f749a8bdef6e8a0d86fc06da3389c44a9e5ead5` (detached HEAD).
The parent owns independent review, integration and any later qualification decision.
Do not copy this source into the main checkout until its frozen gate has ended and
review has approved the exact artifacts. No commit, push, publish or activation is part
of this import.

## Upstream and preserved files

Original URL: https://github.com/Sequester-AG/bug-bounty-triage/blob/main/SKILL.md
Pinned upstream commit: `9684e1bfc876e841f9c789f0b258902b43d461e4`.
Pinned source: https://raw.githubusercontent.com/Sequester-AG/bug-bounty-triage/9684e1bfc876e841f9c789f0b258902b43d461e4/SKILL.md
Git blob: `f97b8fd6d7452eb696d42edbf56261143f997ec6`.
Complete SKILL.md: 25795 bytes;
SHA256 `6c7a275d199f9ebe5192980f4ce3843360ae51b89b1fefa9d9789ac87b523002`.

`SKILL.md`, `LICENSE` and `README.upstream.md` preserve upstream bytes unchanged.
`README.upstream.md` is upstream `README.md`, renamed only to keep provenance separate.
`NOTICE.md` and `provenance.json` are local import documentation, not upstream content.

## License and references

The pinned repository supplies MIT License, Copyright (c) 2026 Sequester-AG.
The full copyright, permission notice and disclaimer are retained unchanged in `LICENSE`.
No license is inferred from popularity or a missing file; the actual license was fetched
and checked against the pinned Git blob. The upstream tree contains only `.gitignore`,
`LICENSE`, `README.md` and `SKILL.md`, with no additional local references or notice files.
`.gitignore` is not imported because it is repository configuration, not skill content.

The upstream README names supporting skills `agent-browser` and `agent-email-cli`,
and executable CLIs `agent-browser` and `@zaddy6/agentemail`; SKILL.md also mentions
`agent-email`, an in-app browser and direct HTTP tooling. These external dependencies
were **not downloaded, installed, pinned, permission-granted, or exercised**. Their URLs
and requirement context are recorded in provenance.json; their licensing and Omnis
compatibility remain unverified. No remote commands or imported skill instructions
were executed to create this import.

## Format and policy gaps — not a qualified Omnis package

The preserved frontmatter contains `name`, `description`, `argument-hint` and
`allowed-tools`; the inspected current product compiler expects exactly `name`,
`description`, `version` and `provenance`, plus an explicit `omnis.yaml` package and
declared contracts/procedures. This directory intentionally supplies no manifest,
adapter, loader, schema, migration or alternative publication pipeline. Static source
comparison identifies format gaps; the compiler/runtime was NOT executed for this import.
The Claude-style `allowed-tools` declaration stays verbatim and grants no Hermes or
Omnis capabilities. No assumed tool-name translation is supplied.

The source's blanket instruction to retain secrets/PII and its assumption that supplied
report evidence is authoritative need explicit product data-policy/trust-boundary review.
They remain in the byte-exact source; preservation does not approve them or override
Omnis scope, safety, secrets, authorization, reporting, or evidence-handling policy.

Candidate records, qualification, publication, selection and RunSnapshot remain owned
by existing product paths. The source creates none of those records. Security verdicts
remain owned by product validators/oracles: a prompt's GREEN/CONFIRMED or escalation
instructions are not an Omnis finding, evidence of efficacy, or authorization to test.
Reducing false positives is the intended future use, not an empirically verified result.
Live targets, exploit reproduction, account provisioning, inference, reports/submission,
DB/services/runtime configuration and activation were all outside this task.

## Verification scope

GitHub API resolved main to the full commit; `git ls-remote` independently matched it.
The complete untruncated tree was inspected. Each of the three imported upstream files
was downloaded from its pinned RAW URL (HTTP 200), matched byte-for-byte against the
API Git blob, checked for exact tree/API/raw size agreement, and hashed with SHA256
and the Git blob SHA1 framing. Final local readback checks all five files, original-byte
identity, Git `hash-object`, JSON validity, scope-only status and `git diff --check`.
This verifies source integrity and isolation, NOT runtime compatibility, security
qualification, publication, availability in a run, or triage effectiveness.
