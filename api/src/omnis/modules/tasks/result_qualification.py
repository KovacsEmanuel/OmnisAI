"""Append-only CONTRACT qualification of retained evidence, never work admission.

The owning caller first validates the managed graph/checks and retained schemas.
This consumer binds that graph to the durable receive rows; digests alone are not
native authentication. No current external precondition producer exists here.
"""

import re
from hashlib import sha256
from uuid import UUID

from sqlalchemy import text as sql
from sqlalchemy.ext.asyncio import AsyncConnection

from omnis.modules.coverage import denominator
from omnis.modules.settings import candidate_store as records
from omnis.modules.settings.candidate_catalog import uuid_string
from omnis.modules.settings.catalog_models import CatalogError
from omnis.modules.settings.catalog_schema import canonical
from omnis.modules.tasks import managed_contract as contract
from omnis.modules.tasks import mission_revisions as missions

Data = dict[str, object]
KIND = "result-qualification"
MANIFEST = "result-evidence-manifest"
REASONS = ["COMPATIBILITY_PROOF_UNAVAILABLE", "CURRENT_PRECONDITION_PROOF_UNAVAILABLE"]
REQUEST_REFS = {
    "context_ref": "contract-input-context",
    "result_ref": "task-result",
    "assignment_ref": "task-brief",
    "mission_ref": "mission",
    "denominator_ref": denominator.KIND,
}
COMMON = set(
    "version namespace owner_id run_ref context_ref result_ref assignment_ref provenance".split()
)
QUALIFICATION_FIELDS = COMMON | set(
    "evaluated_against_mission_ref denominator_ref denominator_revision precondition_state_refs evidence_manifest_ref decision reason_codes".split()
)
MANIFEST_FIELDS = COMMON | set(
    "native_final_ref binding_ref method_check_ref bound_procedure_ref input_refs receipt_refs artifacts evidence_refs".split()
)


def payload(value: object, kind: str) -> Data:
    body = contract.exact(value, QUALIFICATION_FIELDS if kind == KIND else MANIFEST_FIELDS)
    contract.integer(body["version"], 1, 1)
    uuid_string(body["owner_id"])
    if body["namespace"] != "RUN":
        raise CatalogError("REF_UNAVAILABLE")
    for key, ref_kind in {
        "run_ref": "managed-run",
        "context_ref": "contract-input-context",
        "result_ref": "task-result",
        "assignment_ref": "task-brief",
        **(
            {
                "evaluated_against_mission_ref": "mission",
                "denominator_ref": denominator.KIND,
                "evidence_manifest_ref": MANIFEST,
            }
            if kind == KIND
            else {
                "native_final_ref": "native-task-receipt",
                "binding_ref": "runtime-binding",
                "method_check_ref": "method-check",
                "bound_procedure_ref": "bound-procedure",
            }
        ),
    }.items():
        contract.ref(body[key], ref_kind)
    provenance = contract.exact(
        body["provenance"], {"producer_key", "producer_revision", "command_id"}
    )
    uuid_string(provenance["command_id"])
    if provenance["producer_key"] != kind or provenance["producer_revision"] != kind + "-v1":
        raise CatalogError("QUALIFICATION_INVALID")
    if kind == KIND:
        contract.integer(body["denominator_revision"], 1, denominator.REVISION_LIMIT)
        for reference in contract.sequence(body["precondition_state_refs"]):
            contract.ref(reference)
        if (
            body["precondition_state_refs"] != []
            or body["decision"] != "REVALIDATION_REQUIRED"
            or body["reason_codes"] != REASONS
        ):
            raise CatalogError("QUALIFICATION_INVALID")
    else:
        for key, ref_kind in (
            ("input_refs", "contract-case-records"),
            ("receipt_refs", "contract-tool-receipt"),
            ("evidence_refs", "contract-artifact"),
        ):
            for reference in contract.sequence(body[key]):
                contract.ref(reference, ref_kind)
        for raw in contract.sequence(body["artifacts"]):
            item = contract.exact(raw, {"ref", "schema_ref", "value_digest"})
            contract.ref(item["ref"], "contract-artifact")
            contract.ref(item["schema_ref"], "schema")
            if re.fullmatch(r"[0-9a-f]{64}", contract.text(item["value_digest"], 64)) is None:
                raise CatalogError("QUALIFICATION_INVALID")
    if len(canonical(body)) > 16384:
        raise CatalogError("QUALIFICATION_INVALID")
    return body


def material(body: Data) -> Data:
    return {k: v for k, v in body.items() if k != "provenance"}


def provenance(kind: str, command: str) -> Data:
    return {"producer_key": kind, "producer_revision": kind + "-v1", "command_id": command}


def stored_uuid(value: object, expected: object) -> bool:
    """Accept driver UUIDs or exact canonical strings, never scalar coercion."""
    return (type(value) is UUID and str(value) == expected) or (
        type(value) is str and value == expected
    )


def derive_local(owner: str, run: str, graph: list[Data], request: Data) -> tuple[Data, Data]:
    """Reconstruct only available local material; no lookup or evaluator."""
    resolved = {
        k: missions.resolve(graph, contract.ref(request[k], kind))
        for k, kind in REQUEST_REFS.items()
    }
    context, result, brief, mission, item = (resolved[k] for k in REQUEST_REFS)
    ctx = contract.mapping(context["payload"])
    if (
        ctx.get("namespace") != "RUN"
        or ctx.get("owner_id") != owner
        or canonical(contract.ref(ctx.get("basis_ref"), "managed-run"))
        != canonical(records.reference(missions.resolve(graph, ctx["basis_ref"])))
        or contract.ref(ctx["basis_ref"])["id"] != run
    ):
        raise CatalogError("REF_UNAVAILABLE")
    d = denominator.payload(item["payload"])
    b, r = contract.mapping(brief["payload"]), contract.mapping(result["payload"])
    header = contract.validate_result_header(r["header"])
    if canonical(header) != canonical(b["header"]) or header["run_id"] != run:
        raise CatalogError("ASSIGNMENT_MISMATCH")
    original_mission = missions.resolve(graph, contract.ref(header["mission_revision"], "mission"))
    if canonical(records.reference(mission)) != canonical(records.reference(original_mission)):
        missions.validate_pair(original_mission, mission)
    inputs = [
        contract.ref(x, "contract-case-records")
        for x in contract.sequence(b["input_artifact_refs"])
    ]
    bound_ref = contract.ref(
        contract.mapping(contract.sequence(b["procedure_bindings"])[0])["bound_procedure_ref"],
        "bound-procedure",
    )
    bound = missions.resolve(graph, bound_ref)
    bound_body = contract.mapping(bound["payload"])
    if (
        d["owner_id"] != owner
        or canonical(d["run_ref"]) != canonical(ctx["basis_ref"])
        or canonical(d["context_ref"]) != canonical(request["context_ref"])
        or canonical(d["mission_ref"]) != canonical(request["mission_ref"])
        or inputs != [d["inventory_ref"]]
        or canonical(bound_body["procedure_ref"]) != canonical(d["procedure_ref"])
    ):
        raise CatalogError("QUALIFICATION_INPUT_MISMATCH")
    for reference in inputs:
        original = missions.resolve(graph, reference)
        if canonical(contract.mapping(original["payload"])["context_ref"]) != canonical(
            request["context_ref"]
        ):
            raise CatalogError("QUALIFICATION_INPUT_MISMATCH")
    manifests = [r for r in graph if r["kind"] == "launch-manifest"]
    bindings = [r for r in graph if r["kind"] == "runtime-binding"]
    finals = [r for r in graph if r["kind"] == "native-task-receipt"]
    checks = [
        r
        for r in graph
        if r["kind"] == "method-check"
        and canonical(contract.mapping(r["payload"]).get("task_result_ref"))
        == canonical(request["result_ref"])
    ]
    if any(len(values) != 1 for values in (manifests, bindings, finals, checks)):
        raise CatalogError("METHOD_RECEIPT_MISMATCH")
    manifest, binding, final, check = manifests[0], bindings[0], finals[0], checks[0]
    if contract.manifest_protocol(manifest) != "omnis-managed-admission-v4":
        raise CatalogError("QUALIFICATION_UNSUPPORTED")
    checked = contract.validate_final(final["payload"], manifest, binding)
    executions = [
        contract.mapping(e)
        for e in contract.sequence(checked["executions"])
        if canonical(contract.mapping(e)["brief_ref"]) == canonical(request["assignment_ref"])
    ]
    if len(executions) != 1:
        raise CatalogError("METHOD_RECEIPT_MISMATCH")
    emitted = [contract.record(r) for r in contract.sequence(executions[0]["records"])]
    if canonical(emitted[0]) != canonical(result) or any(
        canonical(missions.resolve(graph, records.reference(r))) != canonical(r) for r in emitted
    ):
        raise CatalogError("METHOD_RECEIPT_MISMATCH")
    common: Data = {
        "version": 1,
        "namespace": "RUN",
        "owner_id": owner,
        "run_ref": ctx["basis_ref"],
        **{k: request[k] for k in ("context_ref", "result_ref", "assignment_ref")},
    }
    evidence = {
        **common,
        "native_final_ref": records.reference(final),
        "binding_ref": records.reference(binding),
        "method_check_ref": records.reference(check),
        "bound_procedure_ref": bound_ref,
        "input_refs": inputs,
        "receipt_refs": [
            records.reference(r) for r in emitted if r["kind"] == "contract-tool-receipt"
        ],
        "artifacts": [
            {
                "ref": records.reference(a),
                "schema_ref": contract.mapping(a["payload"])["schema_ref"],
                "value_digest": sha256(
                    canonical(contract.mapping(a["payload"])["value"])
                ).hexdigest(),
            }
            for a in emitted
            if a["kind"] == "contract-artifact"
        ],
        "evidence_refs": r["evidence_refs"],
    }
    qualification = {
        **common,
        "evaluated_against_mission_ref": request["mission_ref"],
        "denominator_ref": request["denominator_ref"],
        "denominator_revision": d["denominator_revision"],
        "precondition_state_refs": [],
        "decision": "REVALIDATION_REQUIRED",
        "reason_codes": list(REASONS),
    }
    return evidence, qualification


async def validate_durable(
    conn: AsyncConnection, owner: str, run: str, graph: list[Data], evidence: Data
) -> None:
    """Bind historical receive identity, not current runtime authority."""
    request = evidence
    brief = missions.resolve(graph, evidence["assignment_ref"])
    result = missions.resolve(graph, evidence["result_ref"])
    binding = missions.resolve(graph, evidence["binding_ref"])
    final = missions.resolve(graph, evidence["native_final_ref"])
    check = missions.resolve(graph, evidence["method_check_ref"])
    manifest = missions.resolve(graph, contract.mapping(final["payload"])["manifest_ref"])
    header = contract.validate_result_header(contract.mapping(result["payload"])["header"])
    await conn.execute(sql("SET LOCAL search_path = pg_catalog, public, pg_temp"))
    state = (
        (
            await conn.execute(
                sql("SELECT * FROM public.managed_run WHERE owner_id=:owner AND run_id=:run"),
                {"owner": owner, "run": run},
            )
        )
        .mappings()
        .one_or_none()
    )
    tasks = (
        (
            await conn.execute(
                sql("SELECT * FROM public.managed_task WHERE run_id=:run ORDER BY batch_index"),
                {"run": run},
            )
        )
        .mappings()
        .all()
    )
    binding_body = contract.mapping(binding["payload"])
    entries = [
        contract.mapping(e)
        for e in contract.sequence(binding_body["entries"])
        if canonical(contract.mapping(e)["brief_ref"]) == canonical(request["assignment_ref"])
    ]
    matches = [t for t in tasks if stored_uuid(t.get("brief_id"), brief["id"])]
    if (
        state is None
        or state.get("release_started") is not True
        or len(matches) != 1
        or len(entries) != 1
        or len(tasks) != len(contract.sequence(binding_body["entries"]))
        or not stored_uuid(state.get("owner_id"), owner)
        or not stored_uuid(state.get("run_id"), header["run_id"])
        or any(
            not stored_uuid(state.get(key), record["id"])
            for key, record in (
                ("manifest_id", manifest),
                ("binding_id", binding),
                ("final_id", final),
            )
        )
        or any(
            not stored_uuid(state.get(key), binding_body[key]) for key in ("runtime_boot", "ticket")
        )
        or type(state.get("native_root_id")) is not str
        or state["native_root_id"] != binding_body["native_root_id"]
    ):
        raise CatalogError("METHOD_RECEIPT_MISMATCH")
    task, entry = matches[0], entries[0]
    if (
        any(
            not stored_uuid(task.get(key), header[key]) or entry[key] != header[key]
            for key in ("task_id", "attempt_id")
        )
        or not stored_uuid(task.get("run_id"), header["run_id"])
        or not stored_uuid(task.get("runtime_boot"), binding_body["runtime_boot"])
        or not stored_uuid(task.get("result_id"), result["id"])
        or not stored_uuid(task.get("check_id"), check["id"])
        or type(task.get("batch_index")) is not int
        or task["batch_index"] != entry["batch_index"]
        or any(
            type(task.get(key)) is not str or task[key] != entry[key]
            for key in ("native_child_id", "native_session_id")
        )
    ):
        raise CatalogError("METHOD_RECEIPT_MISMATCH")


async def derive(
    conn: AsyncConnection, owner: str, run: str, graph: list[Data], request: Data
) -> tuple[Data, Data]:
    """Retained schema/check proof precedes the durable authentication anchor."""
    evidence, qualification = derive_local(owner, run, graph, request)
    await validate_durable(conn, owner, run, graph, evidence)
    return evidence, qualification


def result_refs(body: Data, item: Data) -> Data:
    return {
        "context_ref": body["context_ref"],
        "result_ref": body["result_ref"],
        "assignment_ref": body["assignment_ref"],
        "mission_ref": body["evaluated_against_mission_ref"],
        "denominator_ref": body["denominator_ref"],
        "evidence_manifest_ref": body["evidence_manifest_ref"],
        "qualification_ref": records.reference(item),
    }


def validate_receipt(receipt: object, item: Data, command: str) -> None:
    body = contract.exact(
        contract.record(receipt, "contract-input-command")["payload"],
        set("version owner_id command_id operation request_digest result_refs".split()),
    )
    contract.integer(body["version"], 1, 1)
    q = payload(item["payload"], KIND)
    request = {
        "schema_version": 1,
        "owner_id": q["owner_id"],
        "command_id": command,
        **{k: result_refs(q, item)[k] for k in REQUEST_REFS},
    }
    if (
        body["owner_id"] != q["owner_id"]
        or body["command_id"] != command
        or body["operation"] != "create-qualification"
        or body["request_digest"] != sha256(canonical(request)).hexdigest()
        or canonical(body["result_refs"]) != canonical(result_refs(q, item))
    ):
        raise CatalogError("COMMAND_CONFLICT")


def validate_scope(owner: str, run: str, graph: list[Data]) -> None:
    """Reject foreign/malformed qualification material before external lookup."""
    available = missions.index(graph)
    identities = {contract.text(r["id"]) for r in graph}
    for item in graph:
        if item["kind"] in {KIND, MANIFEST}:
            checked = contract.record(item)
            body = payload(checked["payload"], contract.text(checked["kind"]))
            if body["owner_id"] != owner or contract.ref(body["run_ref"])["id"] != run:
                raise CatalogError("REF_UNAVAILABLE")
            local_refs = [value for key, value in body.items() if key.endswith("_ref")]
            if item["kind"] == MANIFEST:
                for field in ("input_refs", "receipt_refs", "evidence_refs"):
                    local_refs.extend(contract.sequence(body[field]))
                local_refs.extend(
                    contract.mapping(a)["ref"] for a in contract.sequence(body["artifacts"])
                )
            for reference in local_refs:
                checked_ref = contract.ref(reference)
                if canonical(checked_ref) not in available:
                    raise CatalogError(
                        "REF_MISMATCH" if checked_ref["id"] in identities else "REF_UNAVAILABLE"
                    )


def validate_local(owner: str, run: str, graph: list[Data]) -> None:
    """Reject decidable semantic/provenance tamper before any lookup."""
    validate_scope(owner, run, graph)
    retained = [contract.record(r, KIND) for r in graph if r["kind"] == KIND]
    manifests = [contract.record(r, MANIFEST) for r in graph if r["kind"] == MANIFEST]
    used: set[bytes] = set()
    used_receipts: set[bytes] = set()
    for item in retained:
        q = payload(item["payload"], KIND)
        if q["owner_id"] != owner or contract.ref(q["run_ref"])["id"] != run:
            raise CatalogError("REF_UNAVAILABLE")
        manifest = missions.resolve(graph, q["evidence_manifest_ref"])
        m = payload(manifest["payload"], MANIFEST)
        if m["owner_id"] != owner or contract.ref(m["run_ref"])["id"] != run:
            raise CatalogError("REF_UNAVAILABLE")
        request = {k: result_refs(q, item)[k] for k in REQUEST_REFS}
        evidence, qualification = derive_local(owner, run, graph, request)
        qualification["evidence_manifest_ref"] = records.reference(manifest)
        command = uuid_string(contract.mapping(q["provenance"])["command_id"])
        if (
            canonical(material(m)) != canonical(evidence)
            or canonical(material(q)) != canonical(qualification)
            or contract.mapping(m["provenance"])["command_id"] != command
        ):
            raise CatalogError("QUALIFICATION_INVALID")
        receipts = [
            r
            for r in graph
            if r["kind"] == "contract-input-command"
            and contract.mapping(r["payload"]).get("command_id") == command
        ]
        if len(receipts) != 1:
            raise CatalogError("COMMAND_CONFLICT")
        validate_receipt(receipts[0], item, command)
        used_receipts.add(canonical(records.reference(receipts[0])))
        key = canonical(q["evidence_manifest_ref"])
        if key in used:
            raise CatalogError("QUALIFICATION_INVALID")
        used.add(key)
    if used != {canonical(records.reference(m)) for m in manifests}:
        raise CatalogError("QUALIFICATION_INVALID")
    for receipt in (r for r in graph if r["kind"] == "contract-input-command"):
        body = contract.mapping(receipt["payload"])
        if (
            body.get("operation") == "create-qualification"
            or "qualification_ref" in contract.mapping(body.get("result_refs"))
        ) and canonical(records.reference(receipt)) not in used_receipts:
            raise CatalogError("COMMAND_CONFLICT")


async def validate_graph(conn: AsyncConnection, owner: str, run: str, graph: list[Data]) -> None:
    # Retain final semantic checks after schemas/catalog/checker, and DB proof.
    validate_local(owner, run, graph)
    for item in (r for r in graph if r["kind"] == KIND):
        q = payload(item["payload"], KIND)
        evidence = payload(missions.resolve(graph, q["evidence_manifest_ref"])["payload"], MANIFEST)
        await validate_durable(conn, owner, run, graph, evidence)
