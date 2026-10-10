---
name: records-mapping-contract
description: Map structured synthetic records without network or model.
version: 0.1.0
provenance: OmnisAI first-party parent 5ccf90af410e14abf5bf5d9e9807a44824323b9b
---

# Records mapping contract

## When to use / not use
Supplied synthetic method/path/status records only. Not scanning or security findings.

## Inputs / preconditions
One persistent contract-case-records Ref; value records is an ordered list of zero to128 strict records. No credentials or inferred parse provenance.

## Method / baseline / control
Normalize operations, then build map using the declared operations output. No parse step. Baseline/control have explicit non-applicable reasons; invalid/hostile inputs are evaluated separately.

## Evidence / gaps / output
Sorted synthetic surface_map, not Observation, Artifact or assessment evidence. Binding/preflight never counts as method execution.

## Effects / limits / Stop / cleanup
Two installed PURE transformations. No IO, provider, target or granted capabilities. Existing aggregate input/context/frame limits apply separately from list cardinality. Invalid or oversized data blocks; no truncation.

## Sources / compatibility / evaluation
First-party NOTICE and pinned Hermes compatibility. New candidate requires real STATIC/PURE qualification and explicit operator confirmation before private Publish. This source does not self-publish.
