"""Bounded SOURCE review; existing SQL/catalog/material doubles, no PG/Host."""
import asyncio
import json
import sys
from copy import deepcopy
from pathlib import Path
from uuid import uuid4

sys.path[:0] = ["/home/kali/OmnisAI/api/src", "/home/kali/OmnisAI/api/tests"]
import pytest
from test_result_qualification import source_fixture, reseal_graph
from omnis.modules.runs.contract_inputs import ContractInputs
from omnis.modules.settings import candidate_store as records
from omnis.modules.settings.catalog_models import CatalogError
from omnis.modules.settings.catalog_schema import canonical
from omnis.modules.tasks import managed_contract as contract

OUT = Path("/home/kali/.hermes/cache/scratch/p2-result-qualification-input-reproducer.json")
rows = []
patch = pytest.MonkeyPatch()
try:
    conn, request = source_fixture(patch)
    service = ContractInputs(conn)
    binding = next(r["payload"] for r in conn.graph if r["kind"] == "runtime-binding")
    entry = binding["entries"][0]
    conn.state.update({k: binding[k] for k in ("runtime_boot", "ticket", "native_root_id")})
    conn.state.update(owner_id=conn.owner, run_id=conn.run, stage_started=True)
    conn.tasks[0].update({k: entry[k] for k in ("task_id", "attempt_id", "batch_index", "native_child_id", "native_session_id")})
    conn.tasks[0].update(run_id=conn.run, runtime_boot=binding["runtime_boot"], state="SUCCEEDED")
    base_graph, base_writes = deepcopy(conn.graph), list(conn.writes)
    base_state, base_tasks = deepcopy(conn.state), deepcopy(conn.tasks)
    def reset():
        conn.graph, conn.writes = deepcopy(base_graph), list(base_writes)
        conn.state, conn.tasks = deepcopy(base_state), deepcopy(base_tasks)
    for scenario, target, field, value in (
        ("positive-full-rows", "none", "", None),
        ("release-int-refused", "state", "release_started", 1),
        ("result-id-refused", "task", "result_id", str(uuid4())),
        ("task-id-foreign", "task", "task_id", str(uuid4())),
        ("attempt-id-foreign", "task", "attempt_id", str(uuid4())),
        ("task-runtime-boot-foreign", "task", "runtime_boot", str(uuid4())),
        ("task-native-child-foreign", "task", "native_child_id", str(uuid4())),
        ("run-runtime-boot-foreign", "state", "runtime_boot", str(uuid4())),
        ("run-ticket-foreign", "state", "ticket", str(uuid4())),
    ):
        reset()
        if target == "state": conn.state[field] = value
        if target == "task": conn.tasks[0][field] = value
        before = canonical(conn.graph)
        try:
            created = asyncio.run(service.create_qualification(request))
            read_request = {k: request[k] for k in ("schema_version", "owner_id", "command_id")}
            back = asyncio.run(service.read("read-qualification", read_request))
            replay = asyncio.run(service.create_qualification(request))
            rows.append({"scenario": scenario, "outcome": "ACCEPTED", "decision": back["qualification"]["payload"]["decision"], "created": created["created"], "replayed": replay["created"] is False})
        except CatalogError as error:
            rows.append({"scenario": scenario, "outcome": "REFUSED", "reason": error.reason, "graph_unchanged": canonical(conn.graph) == before})
    reset()
    asyncio.run(service.create_qualification(request))
    retained_graph, retained_writes = deepcopy(conn.graph), list(conn.writes)
    original_get = records.get
    lookups = []
    async def counted(*args, **kwargs):
        lookups.append("catalog.get")
        return await original_get(*args, **kwargs)
    patch.setattr(records, "get", counted)
    for scenario in ("positive-retained-read", "foreign-owner", "orphan-command-provenance", "manifest-value-tamper"):
        conn.graph, conn.writes = deepcopy(retained_graph), list(retained_writes)
        lookups.clear()
        if scenario != "positive-retained-read":
            kind = "result-evidence-manifest" if scenario == "manifest-value-tamper" else "result-qualification"
            body = deepcopy(next(r["payload"] for r in conn.graph if r["kind"] == kind))
            if scenario == "foreign-owner": body["owner_id"] = str(uuid4())
            if scenario == "orphan-command-provenance": body["provenance"]["command_id"] = str(uuid4())
            if scenario == "manifest-value-tamper": body["artifacts"][0]["value_digest"] = "0" * 64
            reseal_graph(conn, kind, body)
        before = canonical(conn.graph)
        try:
            back = asyncio.run(service.read("read-qualification", {k: request[k] for k in ("schema_version", "owner_id", "command_id")}))
            rows.append({"scenario": scenario, "outcome": "ACCEPTED", "external_lookups": len(lookups), "graph_unchanged": canonical(conn.graph) == before})
        except CatalogError as error:
            rows.append({"scenario": scenario, "outcome": "REFUSED", "reason": error.reason, "external_lookups_before_refusal": len(lookups), "graph_unchanged": canonical(conn.graph) == before})
    result = {"status": "COMPLETED_SOURCE_ONLY", "cases": rows, "count": len(rows), "limits": ["SQL/transaction/catalog/material/composition doubles reused from source_fixture", "No PostgreSQL, Host launch, runtime RPC, provider or network", "Foreign-row mutations are SOURCE integrity controls, not demonstrated reachable writes through ordinary public commands"]}
except BaseException as error:
    result = {"status": "REPRODUCER_ERROR", "exception_type": type(error).__name__, "cases": rows}
finally:
    patch.undo()
OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
OUT.chmod(0o600)
print(json.dumps(result, ensure_ascii=False))
raise SystemExit(0 if result["status"] == "COMPLETED_SOURCE_ONLY" else 1)
