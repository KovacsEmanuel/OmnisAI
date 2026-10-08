---
name: recon-mapping-contract
description: Map supplied synthetic HTTP metadata without network or model.
version: 0.1.0
provenance: OmnisAI first-party parent 276927b530f68ab00739046296a9372284f408c7
---

# Recon mapping contract

## When to use / not use
Use for synthetic supplied capture metadata. Not for scanning or security findings.

## Inputs / preconditions
Exact capture string containing JSON records; no credentials.

## Hypothesis / invariant / method
Strict parse, normalize operations, build surface map; no IO.

## Baseline / probe / control
Baseline/control not applicable with explicit procedure reasons; three PURE probe steps.

## Evidence / oracle / proof gaps
JSON Schema contract only. Status codes are not findings; no coverage guarantee.

## Effects / limits / Stop / cleanup
No requests/model/files written. 128 records, bounded input/output. Invalid data blocks; cleanup not needed.

## Output / handoff
Sorted synthetic surface_map. Not assessment evidence.

## Sources / compatibility / evaluation
First-party NOTICE; STATIC/PURE consumer only. No published release, durable freeze or review receipt.
