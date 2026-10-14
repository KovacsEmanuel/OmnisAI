"""Bounded SOURCE ordering repro; no PG/native/network/provider."""
import asyncio
import json
import sys
from copy import deepcopy
from hashlib import sha256
from uuid import uuid4

sys.path[:0] = ["/home/kali/OmnisAI/api/src", "/home/kali/OmnisAI/api/tests"]
import pytest
from omnis.modules.runs.contract_inputs import ContractInputs
from omnis.modules.settings import candidate_store as records
from omnis.modules.settings.catalog_models import CatalogError
from omnis.modules.settings.catalog_schema import canonical
from test_result_qualification import source_fixture, reseal_graph

out = {"boundary": "SOURCE_DOUBLE_NOT_PG_NATIVE", "checks": []}
with pytest.MonkeyPatch.context() as mp:
    conn, request = source_fixture(mp)
    service = ContractInputs(conn)
    created = asyncio.run(service.create_qualification(request))
    read_request = {k: request[k] for k in ("schema_version", "owner_id", "command_id")}
    positive = asyncio.run(service.read("read-qualification", read_request))
    out["positive"] = {"created": created["created"], "decision": positive["qualification"]["payload"]["decision"]}
    baseline = deepcopy(conn.graph)
    body = deepcopy(next(r for r in conn.graph if r["kind"] == "result-evidence-manifest")["payload"])
    ghost = str(uuid4())
    body["artifacts"][0]["schema_ref"] = {**body["artifacts"][0]["schema_ref"], "id": ghost}
    reseal_graph(conn, "result-evidence-manifest", body)
    mutated = canonical(conn.graph)
    try:
        asyncio.run(service.read("read-qualification", read_request))
        reason = "ACCEPTED"
    except CatalogError as error:
        reason = error.reason
    attempts = []
    original_execute = conn.execute
    async def observe(statement, args=None):
        if "SELECT i.entity_kind" in str(statement) and args is not None and args.get("id") == ghost:
            attempts.append("CATALOG_LOOKUP_OF_FORGED_MANIFEST_SCHEMA")
            raise CatalogError("OBSERVED_UNTRUSTED_SCHEMA_LOOKUP")
        return await original_execute(statement, args)
    with pytest.MonkeyPatch.context() as spy:
        spy.setattr(conn, "execute", observe)
        try:
            asyncio.run(service.read("read-qualification", read_request))
            guarded = "ACCEPTED"
        except CatalogError as error:
            guarded = error.reason
    out["checks"].append({"attack": "fully_resealed_manifest_artifact_schema_ref", "normal_denial": reason, "observed_reason": guarded, "lookup_attempts": attempts, "writes_unchanged": canonical(conn.graph) == mutated})
    conn.graph = deepcopy(baseline)
    receipt = next(r for r in conn.graph if r["kind"] == "contract-input-command" and r["payload"]["command_id"] == request["command_id"])
    receipt["payload"]["request_digest"] = "0" * 64
    receipt["digest"] = sha256(canonical({k:v for k,v in receipt.items() if k != "digest"})).hexdigest()
    mutated = canonical(conn.graph)
    try:
        asyncio.run(service.read("read-qualification", read_request))
        reason = "ACCEPTED"
    except CatalogError as error:
        reason = error.reason
    attempts = []
    async def observed_get(*args):
        attempts.append("EXTERNAL_GET_BEFORE_RECEIPT_DIGEST_DENIAL")
        raise CatalogError("OBSERVED_LOOKUP_BEFORE_RECEIPT_DENIAL")
    with pytest.MonkeyPatch.context() as spy:
        spy.setattr(records, "get", observed_get)
        try:
            asyncio.run(service.read("read-qualification", read_request))
            guarded = "ACCEPTED"
        except CatalogError as error:
            guarded = error.reason
    out["checks"].append({"attack": "fully_resealed_qualification_receipt_request_digest", "normal_denial": reason, "observed_reason": guarded, "lookup_attempts": attempts, "writes_unchanged": canonical(conn.graph) == mutated})
print(json.dumps(out, indent=2))
assert out["positive"] == {"created": True, "decision": "REVALIDATION_REQUIRED"}
assert out["checks"][0]["normal_denial"] == "QUALIFICATION_INVALID"
assert out["checks"][0]["observed_reason"] == "OBSERVED_UNTRUSTED_SCHEMA_LOOKUP"
assert out["checks"][1]["normal_denial"] == "COMMAND_CONFLICT"
assert out["checks"][1]["observed_reason"] == "OBSERVED_LOOKUP_BEFORE_RECEIPT_DENIAL"
assert all(c["lookup_attempts"] and c["writes_unchanged"] for c in out["checks"])
