"""Trusted finite C04 rules; descriptors are data, never imported executable code."""

import re
from hashlib import sha256
from pathlib import Path

from omnis.modules.settings import candidate_store as records
from omnis.modules.settings.candidate_catalog import uuid_string
from omnis.modules.settings.catalog_models import CatalogError
from omnis.modules.settings.catalog_schema import canonical
from omnis.modules.tasks import managed_contract as contract

Data = dict[str, object]
RULE_KEY = "contract.no-oracle-v1"
GAPS = ["ORACLE_UNAVAILABLE", "CONTROLS_UNAVAILABLE"]
REASON = (
    "No trusted oracle or control receipts are available; "
    "PURE method completion is not a functional verdict."
)


def allocation(value: object) -> list[str]:
    ids = [uuid_string(i) for i in contract.sequence(value)]
    if not 1 <= len(ids) <= 16 or len(set(ids)) != len(ids):
        raise CatalogError("CRITERION_ALLOCATION_MISMATCH")
    return ids


def step_ids(value: object) -> list[str]:
    values = [contract.text(i, 128) for i in contract.sequence(value)]
    if (
        len(values) > 128
        or len(set(values)) != len(values)
        or any(re.fullmatch(r"[a-z][a-z0-9_.-]{0,127}", i) is None for i in values)
    ):
        raise CatalogError("CRITERION_BINDING_MISMATCH")
    return values


def rule_payload(procedure_ref: object, procedure: object) -> Data:
    body = contract.mapping(procedure)
    if body["verification_kind"] != "CONTRACT" or body["key"] not in ("map-capture", "map-records"):
        raise CatalogError("CRITERION_RULE_UNAVAILABLE")
    return {
        "key": RULE_KEY,
        "procedure_ref": contract.ref(procedure_ref, "procedure"),
        "procedure_key": body["key"],
        "code_digest": sha256(Path(__file__).read_bytes()).hexdigest(),
        "oracle_ref": None,
        "control_step_ids": [],
        "permitted_outcomes": ["BLOCKED", "INCONCLUSIVE"],
    }


def bindings(value: object) -> list[Data]:
    rows: list[Data] = []
    seen: set[bytes] = set()
    for raw in contract.sequence(value):
        row = contract.exact(
            raw, {"criterion_id", "bound_procedure_ref", "step_ids", "outcome_rule_ref"}
        )
        uuid_string(row["criterion_id"])
        contract.ref(row["bound_procedure_ref"], "bound-procedure")
        contract.ref(row["outcome_rule_ref"], "criterion-outcome-rule")
        step_ids(row["step_ids"])
        pair = canonical([row["criterion_id"], row["bound_procedure_ref"]])
        if pair in seen or len(rows) >= 16:
            raise CatalogError("CRITERION_BINDING_MISMATCH")
        seen.add(pair)
        rows.append(row)
    return rows


def result_rows(result: object, brief: object) -> list[Data]:
    body = contract.mapping(contract.record(result, "task-result")["payload"])
    brief_body = contract.mapping(contract.validate_brief(brief)["payload"])
    contract.validate_result_header(body["header"])
    if canonical(body["header"]) != canonical(brief_body["header"]):
        raise CatalogError("CRITERION_RESULT_MISMATCH")
    assigned = bindings(brief_body["criterion_bindings"])
    rows = []
    for raw in contract.sequence(body["criterion_results"]):
        row = contract.exact(
            raw,
            {
                "criterion_id",
                "bound_procedure_ref",
                "control_step_ids",
                "evidence_refs",
                "proposed_outcome",
                "gaps",
            },
        )
        uuid_string(row["criterion_id"])
        contract.ref(row["bound_procedure_ref"], "bound-procedure")
        step_ids(row["control_step_ids"])
        evidence = [contract.ref(r) for r in contract.sequence(row["evidence_refs"])]
        if len(evidence) > 128 or len({canonical(r) for r in evidence}) != len(evidence):
            raise CatalogError("CRITERION_RESULT_MISMATCH")
        outcome = contract.text(row["proposed_outcome"], 16)
        if outcome not in ("PASS", "FAIL", "BLOCKED", "INCONCLUSIVE"):
            raise CatalogError("CRITERION_RESULT_MISMATCH")
        gaps = [contract.text(g) for g in contract.sequence(row["gaps"])]
        if len(gaps) > 128:
            raise CatalogError("CRITERION_RESULT_MISMATCH")
        rows.append(row)
    if [(r["criterion_id"], r["bound_procedure_ref"]) for r in rows] != [
        (r["criterion_id"], r["bound_procedure_ref"]) for r in assigned
    ]:
        raise CatalogError("CRITERION_RESULT_MISMATCH")
    # This trusted finite rule admits no control/evidence claims; PURE outputs are not an oracle.
    if any(r["control_step_ids"] != [] or r["evidence_refs"] != [] for r in rows):
        raise CatalogError("CRITERION_RESULT_MISMATCH")
    return rows


def validate_assignment(
    brief: object, bound: object, mission: object, run: object, rules: list[Data]
) -> None:
    body = contract.mapping(contract.validate_brief(brief)["payload"])
    rows = bindings(body["criterion_bindings"])
    bound_record = contract.record(bound, "bound-procedure")
    mission_record = contract.record(mission, "mission")
    run_record = contract.record(run, "managed-run")
    run_body = contract.mapping(run_record["payload"])
    header = contract.mapping(body["header"])
    if (
        contract.ref(header["mission_revision"], "mission") != records.reference(mission_record)
        or header["run_id"] != run_record["id"]
    ):
        raise CatalogError("CRITERION_ALLOCATION_MISMATCH")
    allocated = (
        allocation(run_body["allocated_criterion_ids"])
        if "allocated_criterion_ids" in run_body
        else []
    )
    mission_ids = [
        uuid_string(contract.mapping(c)["id"])
        for c in contract.sequence(contract.mapping(mission_record["payload"])["criteria"])
    ]
    if (
        len(set(mission_ids)) != len(mission_ids)
        or any(i not in mission_ids for i in allocated)
        or [r["criterion_id"] for r in rows] != allocated
    ):
        raise CatalogError("CRITERION_ALLOCATION_MISMATCH")
    if not rows:
        return
    bound_body = contract.mapping(bound_record["payload"])
    procedure = contract.mapping(bound_body["resolved_procedure"])
    known = [contract.mapping(s)["id"] for s in contract.sequence(procedure["probe"])]
    expected_rule = contract.ref(run_body["criterion_outcome_rule_ref"], "criterion-outcome-rule")
    checked_rules = [contract.record(r, "criterion-outcome-rule") for r in rules]
    matches = [r for r in checked_rules if records.reference(r) == expected_rule]
    if len(matches) != 1:
        raise CatalogError("CRITERION_RULE_UNAVAILABLE")
    descriptor = contract.exact(
        matches[0]["payload"],
        {
            "key",
            "procedure_ref",
            "procedure_key",
            "code_digest",
            "oracle_ref",
            "control_step_ids",
            "permitted_outcomes",
        },
    )
    contract.text(descriptor["key"], 128)
    contract.ref(descriptor["procedure_ref"], "procedure")
    contract.text(descriptor["procedure_key"], 128)
    if re.fullmatch(r"[0-9a-f]{64}", contract.text(descriptor["code_digest"], 64)) is None:
        raise CatalogError("CRITERION_RULE_UNAVAILABLE")
    step_ids(descriptor["control_step_ids"])
    for outcome in contract.sequence(descriptor["permitted_outcomes"]):
        contract.text(outcome, 16)
    if canonical(descriptor) != canonical(rule_payload(bound_body["procedure_ref"], procedure)):
        raise CatalogError("CRITERION_RULE_UNAVAILABLE")
    for row in rows:
        if (
            row["bound_procedure_ref"] != records.reference(bound_record)
            or row["outcome_rule_ref"] != expected_rule
            or row["step_ids"] != known
        ):
            raise CatalogError("CRITERION_BINDING_MISMATCH")


def outcome_payloads(brief: object, result: object, check: object, graph: list[Data]) -> list[Data]:
    """Apply only the pinned finite backend rule, after owner-authenticated MethodCheck."""
    brief_record = contract.validate_brief(brief)
    result_record = contract.record(result, "task-result")
    check_record = contract.record(check, "method-check")
    body = contract.mapping(brief_record["payload"])
    assigned = bindings(body["criterion_bindings"])
    if not assigned:
        if result_rows(result_record, brief_record):
            raise CatalogError("CRITERION_RESULT_MISMATCH")
        return []
    header = contract.validate_result_header(body["header"])
    local = {contract.text(r["id"]): contract.record(r) for r in graph}
    bound = local[
        uuid_string(contract.ref(assigned[0]["bound_procedure_ref"], "bound-procedure")["id"])
    ]
    mission = local[uuid_string(contract.ref(header["mission_revision"], "mission")["id"])]
    run = local[uuid_string(header["run_id"])]
    validate_assignment(
        brief_record,
        bound,
        mission,
        run,
        [r for r in graph if r["kind"] == "criterion-outcome-rule"],
    )
    result_rows(result_record, brief_record)
    checked = contract.mapping(check_record["payload"])
    if (
        contract.ref(checked["brief_ref"], "task-brief") != records.reference(brief_record)
        or contract.ref(checked["task_result_ref"], "task-result")
        != records.reference(result_record)
        or checked["status"] not in {"COMPLETE", "INCOMPLETE"}
    ):
        raise CatalogError("CRITERION_CHECK_REQUIRED")
    procedure = contract.mapping(contract.mapping(bound["payload"])["resolved_procedure"])
    # No trusted positive oracle/control consumer is implemented in this subset.
    # Refuse unsupported material rather than treating child proposals as authority.
    if procedure["oracle_ref"] is not None or procedure["control"] != []:
        raise CatalogError("CRITERION_RULE_UNAVAILABLE")
    return [
        {
            "criterion_id": b["criterion_id"],
            "bound_procedure_ref": b["bound_procedure_ref"],
            "outcome_rule_ref": b["outcome_rule_ref"],
            "brief_ref": records.reference(brief_record),
            "task_result_ref": records.reference(result_record),
            "method_check_ref": records.reference(check_record),
            "mission_ref": header["mission_revision"],
            "outcome": "BLOCKED",
            "control_step_ids": [],
            "evidence_refs": [],
            "gaps": [*GAPS, *(["METHOD_INCOMPLETE"] if checked["status"] == "INCOMPLETE" else [])],
            "reason": REASON,
        }
        for b in assigned
    ]


def validate_outcomes(values: list[Data], expected: list[Data]) -> None:
    """Validate exact types/pins before equality; duplicates/foreign rows never project."""
    payloads = []
    fields = {
        "criterion_id",
        "bound_procedure_ref",
        "outcome_rule_ref",
        "brief_ref",
        "task_result_ref",
        "method_check_ref",
        "mission_ref",
        "outcome",
        "control_step_ids",
        "evidence_refs",
        "gaps",
        "reason",
    }
    for value in values:
        row = contract.exact(contract.record(value, "criterion-outcome")["payload"], fields)
        uuid_string(row["criterion_id"])
        for key, kind in (
            ("bound_procedure_ref", "bound-procedure"),
            ("outcome_rule_ref", "criterion-outcome-rule"),
            ("brief_ref", "task-brief"),
            ("task_result_ref", "task-result"),
            ("method_check_ref", "method-check"),
            ("mission_ref", "mission"),
        ):
            contract.ref(row[key], kind)
        contract.text(row["outcome"], 16)
        contract.text(row["reason"], 2048)
        step_ids(row["control_step_ids"])
        for r in contract.sequence(row["evidence_refs"]):
            contract.ref(r)
        for g in contract.sequence(row["gaps"]):
            contract.text(g)
        payloads.append(canonical(row))
    if sorted(payloads) != sorted(canonical(p) for p in expected):
        raise CatalogError("CRITERION_OUTCOME_MISMATCH")
