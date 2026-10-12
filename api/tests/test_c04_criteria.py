"""C04 vertical SOURCE controls; authentic native PostgreSQL proof is separate."""

import sys
from pathlib import Path
from uuid import uuid4

import pytest

from omnis.modules.settings import candidate_store as records
from omnis.modules.settings.catalog_models import CatalogError
from omnis.modules.settings.catalog_schema import canonical
from omnis.modules.tasks import managed_composition
from omnis.modules.tasks import managed_contract as contract
from test_c03_managed_capture import capture_source, material


def criteria_graph(ids: list[str] | None = None) -> list[dict[str, object]]:
    source = capture_source()
    _, cold = material(source, '[{"method":"GET","path":"/synthetic","status":200}]')
    prefix = source.build(context_only=True, method_execution=True, criterion_ids=ids)
    run = next(r for r in prefix if r["kind"] == "managed-run")
    body = contract.mapping(run["payload"])
    context = records.envelope(
        "contract-input-context",
        {
            **contract.mapping(contract.mapping(cold["context"])["payload"]),
            "basis_ref": records.reference(run),
            "mission_ref": body["mission_ref"],
            "focus_ref": body["focus_ref"],
        },
    )
    from omnis.modules.tasks.contract_case_input import material_section, produce_input

    schema_ref, raw, path = source.input_schema()
    item = produce_input(
        context,
        contract.mapping(contract.mapping(cold["input"])["payload"])["value"],
        raw,
        str(uuid4()),
    )
    prefix.extend([context, item])
    section = material_section(context, item, schema_ref, raw, schema_path=path)
    return source.build(prefix=prefix, case_input=section, method_execution=True)


def test_outcome_requires_bounded_reason_before_payload_equality() -> None:
    """SOURCE payload-validator control, not native authenticity or persistence."""
    from omnis.modules.tasks import criterion_checks

    graph = criteria_graph([str(uuid4()), str(uuid4())])
    brief = next(r for r in graph if r["kind"] == "task-brief")
    body = contract.mapping(brief["payload"])
    binding = contract.mapping(contract.sequence(body["criterion_bindings"])[0])
    payload = {
        **{k: binding[k] for k in ("criterion_id", "bound_procedure_ref", "outcome_rule_ref")},
        "brief_ref": records.reference(brief),
        "task_result_ref": records.reference(records.envelope("task-result", {})),
        "method_check_ref": records.reference(records.envelope("method-check", {})),
        "mission_ref": contract.mapping(body["header"])["mission_revision"],
        "outcome": "BLOCKED",
        "control_step_ids": [],
        "evidence_refs": [],
        "gaps": list(criterion_checks.GAPS),
        "reason": "No trusted oracle or controls are available.",
    }
    criterion_checks.validate_outcomes([records.envelope("criterion-outcome", payload)], [payload])
    maximum = {**payload, "reason": "x" * 2048}
    criterion_checks.validate_outcomes([records.envelope("criterion-outcome", maximum)], [maximum])
    for reason in (None, True, "", "x" * 2049):
        bad = {**payload, "reason": reason}
        with pytest.raises(CatalogError):
            criterion_checks.validate_outcomes([records.envelope("criterion-outcome", bad)], [bad])
    missing = {k: v for k, v in payload.items() if k != "reason"}
    with pytest.raises(CatalogError):
        criterion_checks.validate_outcomes(
            [records.envelope("criterion-outcome", missing)], [missing]
        )


def test_backend_allocates_two_distinct_criteria_on_one_bound_procedure() -> None:
    ids = [str(uuid4()), str(uuid4())]
    graph = criteria_graph(ids)
    brief = next(r for r in graph if r["kind"] == "task-brief")
    mission = next(r for r in graph if r["kind"] == "mission")
    bindings = [
        contract.mapping(b)
        for b in contract.sequence(contract.mapping(brief["payload"])["criterion_bindings"])
    ]
    assert [b["criterion_id"] for b in bindings] == ids
    assert [
        contract.mapping(c)["id"]
        for c in contract.sequence(contract.mapping(mission["payload"])["criteria"])
    ] == ids
    assert bindings[0]["bound_procedure_ref"] == bindings[1]["bound_procedure_ref"]
    assert bindings[0]["outcome_rule_ref"] == bindings[1]["outcome_rule_ref"]
    assert len(canonical_graph := canonical(graph)) + 14828 <= 65536
    assert canonical_graph
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "integrations/hermes/src"))
    from omnis_hermes.managed_admission_contract import validate_stage

    assert validate_stage(managed_composition.stage_payload(graph[-1], graph)) == graph[-1]


def test_explicit_criteria_context_request_rejects_invalid_allocation() -> None:
    from omnis.modules.runs.contract_inputs import validate_request
    from test_c03_managed_capture import request

    value = {
        k: v
        for k, v in request().items()
        if k
        in {"schema_version", "owner_id", "command_id", "selection_ref", "preparation_command_id"}
    }
    value["schema_version"] = 1
    value["criterion_ids"] = [str(uuid4()), str(uuid4())]
    assert validate_request("create-method-context", value) == value
    for bad in (True, [], [True], ["foreign"], [contract.sequence(value["criterion_ids"])[0]] * 2):
        with pytest.raises(CatalogError):
            validate_request("create-method-context", {**value, "criterion_ids": bad})
    with pytest.raises(CatalogError):
        validate_request("create-context", value)


def test_real_native_result_contains_exact_allocated_pairs_and_method_check() -> None:
    from test_contract_method_checks import native_case

    ids = [str(uuid4()), str(uuid4())]
    case = native_case(criterion_ids=ids)
    result = contract.mapping(contract.sequence(case.execution["records"])[0])
    rows = [
        contract.mapping(r)
        for r in contract.sequence(contract.mapping(result["payload"])["criterion_results"])
    ]
    assert [r["criterion_id"] for r in rows] == ids
    assert all(r["proposed_outcome"] == "BLOCKED" and r["gaps"] for r in rows)
    assert rows[0]["bound_procedure_ref"] == rows[1]["bound_procedure_ref"]
    assert contract.mapping(case.check()["payload"])["status"] == "COMPLETE"


@pytest.mark.parametrize(
    "attack",
    [
        "bool-header",
        "bool-bound",
        "bad-criterion",
        "bad-proposal",
        "bad-control",
        "bad-evidence",
        "bad-gap",
        "duplicate-pair",
    ],
)
def test_native_wire_rejects_invalid_criterion_types_before_equality(attack: str) -> None:
    from copy import deepcopy

    from test_contract_method_checks import native_case

    case = native_case(criterion_ids=[str(uuid4()), str(uuid4())])
    from omnis_hermes.managed_admission_contract import validate_response

    body = contract.mapping(case.binding["payload"])
    final = {
        "protocol": "omnis-managed-admission-v4",
        "status": "SUCCEEDED",
        "reason": "CONTRACT_PURE",
        "ticket": body["ticket"],
        "manifest_ref": records.reference(records.envelope("launch-manifest", {})),
        "binding_ref": records.reference(case.binding),
        "native_root_id": body["native_root_id"],
        "entries": body["entries"],
        "executions": [case.execution],
    }
    assert validate_response(final) == final
    bad = deepcopy(final)
    output = contract.mapping(
        contract.sequence(contract.mapping(contract.sequence(bad["executions"])[0])["records"])[0]
    )
    payload = contract.mapping(output["payload"])
    criteria = contract.sequence(payload["criterion_results"])
    row = contract.mapping(criteria[0])
    if attack == "bool-header":
        header = contract.mapping(payload["header"])
        header["brief_revision"] = True
        payload["header"] = header
    elif attack == "bool-bound":
        bound = contract.mapping(row["bound_procedure_ref"])
        bound["revision"] = True
        row["bound_procedure_ref"] = bound
    elif attack == "bad-criterion":
        row["criterion_id"] = True
    elif attack == "bad-proposal":
        row["proposed_outcome"] = []
    elif attack == "bad-control":
        row["control_step_ids"] = [True]
    elif attack == "bad-evidence":
        row["evidence_refs"] = [True]
    elif attack == "bad-gap":
        row["gaps"] = [True]
    else:
        criteria[1] = deepcopy(row)
    if attack != "duplicate-pair":
        criteria[0] = row
    payload["criterion_results"] = criteria
    output["payload"] = payload
    output["digest"] = (
        __import__("hashlib")
        .sha256(canonical({k: v for k, v in output.items() if k != "digest"}))
        .hexdigest()
    )
    contract.mapping(contract.sequence(bad["executions"])[0])["records"] = [
        output,
        *contract.sequence(case.execution["records"])[1:],
    ]
    # mapping() returns a copy; replace execution explicitly.
    execution = contract.mapping(contract.sequence(bad["executions"])[0])
    execution["records"] = [output, *contract.sequence(case.execution["records"])[1:]]
    bad["executions"] = [execution]
    with pytest.raises(ValueError):
        validate_response(bad)


@pytest.mark.parametrize("attack", ["omit", "duplicate", "foreign", "header", "bool-bound"])
def test_backend_method_check_denies_nonexact_pairs(attack: str) -> None:
    from test_contract_method_checks import native_case, obj, rebind_mutation, rows

    case = native_case(criterion_ids=[str(uuid4()), str(uuid4())])
    payload = obj(obj(rows(case.execution["records"])[0])["payload"])
    criteria = rows(payload["criterion_results"])
    if attack == "omit":
        criteria.pop()
    elif attack == "duplicate":
        criteria[1] = criteria[0]
    elif attack == "foreign":
        obj(criteria[0])["criterion_id"] = str(uuid4())
    elif attack == "header":
        obj(payload["header"])["attempt_id"] = str(uuid4())
    else:
        obj(obj(criteria[0])["bound_procedure_ref"])["revision"] = True
    rebind_mutation(case)
    with pytest.raises(CatalogError):
        case.check()


def test_backend_assignment_refuses_unknown_rule_before_graph_writes() -> None:
    from copy import deepcopy

    from omnis.modules.tasks import criterion_checks

    graph = criteria_graph([str(uuid4()), str(uuid4())])
    brief, bound, mission, run, rule = [
        next(r for r in graph if r["kind"] == k)
        for k in (
            "task-brief",
            "bound-procedure",
            "mission",
            "managed-run",
            "criterion-outcome-rule",
        )
    ]
    criterion_checks.validate_assignment(brief, bound, mission, run, [rule])
    for attack in ("unknown-rule", "unknown-criterion", "bool-rule", "unknown-step"):
        bad = deepcopy(brief)
        payload = contract.mapping(bad["payload"])
        bindings = [contract.mapping(r) for r in contract.sequence(payload["criterion_bindings"])]
        if attack == "unknown-rule":
            bindings[0]["outcome_rule_ref"] = records.reference(
                records.envelope("criterion-outcome-rule", {})
            )
        elif attack == "unknown-criterion":
            bindings[0]["criterion_id"] = str(uuid4())
        elif attack == "bool-rule":
            reference = contract.mapping(bindings[0]["outcome_rule_ref"])
            reference["revision"] = True
            bindings[0]["outcome_rule_ref"] = reference
        else:
            bindings[0]["step_ids"] = ["unknown-step"]
        payload["criterion_bindings"] = bindings
        bad["payload"] = payload
        bad["digest"] = (
            __import__("hashlib")
            .sha256(canonical({k: v for k, v in bad.items() if k != "digest"}))
            .hexdigest()
        )
        with pytest.raises(CatalogError):
            criterion_checks.validate_assignment(bad, bound, mission, run, [rule])


def test_old_compact_pin_is_receive_compatible_only_for_zero_bindings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with monkeypatch.context() as old:
        old.setattr(
            managed_composition, "COMPOSER_REVISION", managed_composition.COMPACT_COMPOSER_REVISION
        )
        support = criteria_graph()
        nonempty = criteria_graph([str(uuid4()), str(uuid4())])
    import importlib

    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "integrations/hermes/src"))
    native = importlib.import_module("omnis_hermes.managed_admission_contract")
    stage = managed_composition.stage_payload(support[-1], support)
    assert native.validate_stage(stage) == support[-1]
    with pytest.raises(CatalogError):
        managed_composition.stage_payload(nonempty[-1], nonempty)
    # The unchanged native constructor also refuses the old-pin nonempty material.
    with monkeypatch.context() as old:
        old.setattr(
            managed_composition, "COMPOSER_REVISION", managed_composition.COMPACT_COMPOSER_REVISION
        )
        bad_stage = managed_composition.stage_payload(nonempty[-1], nonempty)
    with pytest.raises(ValueError):
        native.validate_stage(bad_stage)
