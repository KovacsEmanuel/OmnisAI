"""Finite additive mission history. No qualification, freshness or work grant."""

from hashlib import sha256

from omnis.modules.settings import candidate_store as records
from omnis.modules.settings.candidate_catalog import uuid_string
from omnis.modules.settings.catalog_models import CatalogError
from omnis.modules.settings.catalog_schema import canonical
from omnis.modules.tasks import managed_contract as contract

Data = dict[str, object]
FIELDS: set[str] = set(
    "snapshot_ref assessment_mode summary criteria non_goals required_operation_refs basis_refs gaps done_when".split()
)
DESCRIPTION = "Independent retained-data obligation; no execution or functional verdict authorized."


def payload(value: object) -> Data:
    body = contract.exact(value, FIELDS)
    contract.ref(body["snapshot_ref"], "run-snapshot")
    if body["assessment_mode"] not in ("FULL_ASSESSMENT", "FOCUSED_TEST"):
        raise CatalogError("MISSION_REVISION_INVALID")
    contract.text(body["summary"])
    for key in ("non_goals", "gaps"):
        values = contract.sequence(body[key])
        if len(values) > 128:
            raise CatalogError("MISSION_REVISION_INVALID")
        for value in values:
            contract.text(value)
    for key in ("required_operation_refs", "basis_refs"):
        values = [contract.ref(r) for r in contract.sequence(body[key])]
        if len(values) > 128 or len({canonical(r) for r in values}) != len(values):
            raise CatalogError("MISSION_REVISION_INVALID")
    ids = []
    for raw in contract.sequence(body["criteria"]):
        row = contract.exact(raw, {"id", "description", "kind", "oracle_ref"})
        ids.append(uuid_string(row["id"]))
        contract.text(row["description"], 1024)
        if row["kind"] not in ("SECURITY", "FUNCTIONAL"):
            raise CatalogError("MISSION_REVISION_INVALID")
        if row["oracle_ref"] is not None:
            contract.ref(row["oracle_ref"])
    if not 1 <= len(ids) <= 64 or len(set(ids)) != len(ids):
        raise CatalogError("MISSION_REVISION_INVALID")
    done = []
    for raw in contract.sequence(body["done_when"]):
        row = contract.exact(raw, {"criterion_id", "required"})
        done.append(uuid_string(row["criterion_id"]))
        if type(row["required"]) is not bool:
            raise CatalogError("MISSION_REVISION_INVALID")
    if done != ids:
        raise CatalogError("MISSION_REVISION_INVALID")
    return body


def validate_pair(original: object, revised: object) -> None:
    m1, m2 = contract.record(original, "mission"), contract.record(revised, "mission")
    before, after = payload(m1["payload"]), payload(m2["payload"])
    old = contract.sequence(before["criteria"])
    new = contract.sequence(after["criteria"])
    added = contract.mapping(new[-1])
    if (
        m1["revision"] != 1
        or m2["revision"] != 2
        or m1["id"] != m2["id"]
        or before["assessment_mode"] != "FULL_ASSESSMENT"
        or before["required_operation_refs"] != []
        or len(new) != len(old) + 1
        or new[:-1] != old
        or added["kind"] != "FUNCTIONAL"
        or added["oracle_ref"] is not None
        or after["done_when"]
        != [
            *contract.sequence(before["done_when"]),
            {"criterion_id": added["id"], "required": True},
        ]
        or after["basis_refs"] != [*contract.sequence(before["basis_refs"]), records.reference(m1)]
        or any(
            contract.ref(r)["kind"] == "mission" for r in contract.sequence(before["basis_refs"])
        )
        or any(after[k] != before[k] for k in FIELDS - {"criteria", "done_when", "basis_refs"})
    ):
        raise CatalogError("MISSION_REVISION_INVALID")


def append(original: object, criterion_id: object) -> Data:
    m1 = contract.record(original, "mission")
    body = payload(m1["payload"])
    identity = uuid_string(criterion_id)
    body["criteria"] = [
        *contract.sequence(body["criteria"]),
        {"id": identity, "description": DESCRIPTION, "kind": "FUNCTIONAL", "oracle_ref": None},
    ]
    body["done_when"] = [
        *contract.sequence(body["done_when"]),
        {"criterion_id": identity, "required": True},
    ]
    body["basis_refs"] = [*contract.sequence(body["basis_refs"]), records.reference(m1)]
    result = {**m1, "revision": 2, "payload": body}
    result["digest"] = sha256(
        canonical({k: v for k, v in result.items() if k != "digest"})
    ).hexdigest()
    validate_pair(m1, result)
    return result


def index(graph: list[Data]) -> dict[bytes, Data]:
    result = {}
    keys = set()
    for raw in graph:
        item = contract.record(raw)
        key = (item["id"], item["revision"])
        if key in keys:
            raise CatalogError("REF_MISMATCH")
        keys.add(key)
        result[canonical(records.reference(item))] = item
    return result


def legacy_index(graph: list[Data]) -> dict[str, Data]:
    """ID-only callers retain explicit revision1 semantics, never latest."""
    return {uuid_string(r["id"]): r for r in index(graph).values() if r["revision"] == 1}


def resolve(graph: list[Data], reference: object) -> Data:
    checked = contract.ref(reference)
    result = index(graph).get(canonical(checked))
    if result is None:
        raise CatalogError("REF_UNAVAILABLE")
    return result


def validate_graph(graph: list[Data]) -> None:
    index(graph)
    for revised in (r for r in graph if r["revision"] == 2):
        body = payload(revised["payload"])
        predecessors = [
            r for r in contract.sequence(body["basis_refs"]) if contract.ref(r)["kind"] == "mission"
        ]
        if len(predecessors) != 1:
            raise CatalogError("MISSION_REVISION_INVALID")
        validate_pair(resolve(graph, predecessors[0]), revised)


def require_supported(graph: list[Data], context: object, mission: object) -> None:
    ctx = contract.exact(
        contract.record(context, "contract-input-context")["payload"],
        set(
            "version namespace owner_id basis_ref snapshot_ref procedure_ref schema_ref selection_ref mission_ref focus_ref".split()
        ),
    )
    uuid_string(ctx["owner_id"])
    contract.integer(ctx["version"], 2, 2)
    m1 = contract.record(mission, "mission")
    body = payload(m1["payload"])
    root = resolve(graph, ctx["basis_ref"])
    run = contract.mapping(root["payload"])
    focus = contract.mapping(resolve(graph, run["focus_ref"])["payload"])
    policy = contract.mapping(resolve(graph, run["policy_ref"])["payload"])
    scope = contract.mapping(resolve(graph, run["scope_ref"])["payload"])
    if (
        ctx["version"] != 2
        or ctx["namespace"] != "RUN"
        or m1["revision"] != 1
        or ctx["snapshot_ref"] != body["snapshot_ref"]
        or run["snapshot_ref"] != body["snapshot_ref"]
        or ctx["focus_ref"] != run["focus_ref"]
        or ctx["selection_ref"] != run["selection_ref"]
        or ctx["mission_ref"] != records.reference(m1)
        or run["mission_ref"] != ctx["mission_ref"]
        or root["kind"] != "managed-run"
        or run["purpose"] != "CONTRACT_PROBE"
        or body["assessment_mode"] != "FULL_ASSESSMENT"
        or body["required_operation_refs"] != []
        or focus["mission_ref"] != ctx["mission_ref"]
        or focus["bootstrap_budget_ref"] is not None
        or focus["test_operation_refs"] != []
        or focus["support_operation_refs"] != []
        or focus["excluded_operation_refs"] != []
        or focus["discovery_bootstrap"]
        != {"seed_refs": [], "max_actions": 0, "deadline_seconds": 0}
        or policy
        != {
            "purpose": "CONTRACT_PROBE",
            "target_actions": 0,
            "model_calls": 0,
            "allowed_capability_ids": [],
        }
        or scope["target_operation_refs"] != []
    ):
        raise CatalogError("MISSION_REVISION_UNSUPPORTED")


def require_no_revision(graph: list[Data]) -> None:
    validate_graph(graph)
    if any(r["revision"] == 2 for r in graph):
        raise CatalogError("MISSION_REVISION_NEW_WORK_UNSUPPORTED")
