"""Qualified C10 receipt consumer. SOURCE only; PG/native owner separately."""

from copy import deepcopy
from uuid import uuid4

import pytest

from omnis.modules.settings.catalog_models import CatalogError
from test_contract_method_checks import native_case, obj, rebind_mutation, reseal_assignment, rows


@pytest.mark.parametrize("compact", [False, True])
@pytest.mark.parametrize("empty,expected", [(False, True), (True, False)])
def test_procedure_precondition_real_source_producer_keeps_all_obligations(
    compact: bool, empty: bool, expected: bool
) -> None:
    case = native_case(
        predicates=True, compact=compact, empty=empty, precondition_expected=expected
    )
    emitted = [obj(r) for r in rows(case.execution["records"])]
    assert [
        obj(r["payload"])["operation"] for r in emitted if r["kind"] == "contract-tool-receipt"
    ] == ["READ_INPUT", "PURE_ACTION", "PURE_ACTION"]
    results = rows(obj(emitted[0]["payload"])["method_results"])
    assert len(results) == 3 and all(obj(r)["state"] == "DONE" for r in results)
    assert obj(case.check()["payload"])["status"] == "COMPLETE"


@pytest.mark.parametrize("compact", [False, True])
def test_qualified_early_return_is_real_pure_prefix_incomplete(compact: bool) -> None:
    case = native_case(predicates=True, compact=compact, return_predicate="normalize-records")
    emitted = [obj(r) for r in rows(case.execution["records"])]
    assert len(emitted) == 4  # result, read, normalize receipt, actual operations artifact
    receipts = [obj(r["payload"]) for r in emitted if r["kind"] == "contract-tool-receipt"]
    assert [r["step_id"] for r in receipts] == [None, "normalize-operations"]
    body = obj(emitted[0]["payload"])
    assert body["status"] == "INCONCLUSIVE"
    methods = [obj(r) for r in rows(body["method_results"])]
    assert [obj(r["ref"])["requirement_key"] for r in methods] == [
        "normalize-records",
        "build-surface-map",
        "preserve-input-context",
    ]
    assert [r["state"] for r in methods] == ["DONE", "NOT_RUN", "DONE"]
    assert methods[1]["basis_refs"] == methods[1]["artifact_refs"] == []
    assert body["gaps"] == [methods[1]["reason"]]
    from jsonschema import Draft202012Validator

    from omnis.modules.tasks import managed_contract

    brief_body = obj(case.brief["payload"])
    header = {k: v for k, v in obj(brief_body["header"]).items() if k != "result_schema_ref"}
    Draft202012Validator(
        managed_contract.result_json_schema(
            header,
            [obj(r) for r in rows(obj(brief_body["method_plan"])["requirements"])],
            method_execution=True,
        )
    ).validate(body)
    checked = obj(case.check()["payload"])
    assert checked["status"] == "INCOMPLETE"
    assert checked["checked_results"] == methods
    assert checked["gap_refs"] == [methods[1]["ref"]]
    assert obj(case.check(receive_only=True)["payload"]) == checked


@pytest.mark.parametrize(
    "attack",
    ["done-claim", "success-claim", "omitted", "sequence-bool", "gap", "unsatisfied-return"],
)
def test_genuine_partial_cannot_promote_or_erase_missing_work(attack: str) -> None:
    case = native_case(predicates=True, return_predicate="normalize-records")
    body = obj(obj(rows(case.execution["records"])[0])["payload"])
    methods = rows(body["method_results"])
    if attack == "done-claim":
        obj(methods[1])["state"] = "DONE"
    elif attack == "success-claim":
        body["status"] = "SUCCEEDED"
    elif attack == "omitted":
        methods.pop()
    elif attack == "sequence-bool":
        obj(obj(rows(case.execution["records"])[2])["payload"])["sequence"] = True
    elif attack == "gap":
        body["gaps"] = []
    else:
        obj(rows(obj(case.brief["payload"])["return_when"])[0])["predicate_id"] = (
            "build-surface-map"
        )
    rebind_mutation(case)
    with pytest.raises(CatalogError):
        case.check()


def test_current_c10_historical_descriptor_is_receive_only_full_scope() -> None:
    from omnis.modules.settings import candidate_store as records
    from omnis.modules.settings.catalog_schema import canonical
    from omnis.modules.tasks.method_checker_identity import KEY, SEMANTICS

    historical = records.envelope(
        "method-checker",
        {
            "key": KEY,
            "semantics": SEMANTICS,
            "code_digest": "388fe9da680951249202045b10e10245d42352a0c194413d221d647b54a085db",
        },
    )
    case = native_case(
        predicates=True,
        composer_pin="4a3606b8e0354bceb8066f6de536932ee420d1147aa9311084ceafb4afbea850",
    )
    expected = obj(case.check()["payload"])
    case.checker = historical
    expected["checker_ref"] = records.reference(historical)
    assert obj(case.check()["payload"])["status"] == "UNKNOWN"
    assert canonical(obj(case.check(receive_only=True)["payload"])) == canonical(expected)
    partial = native_case(
        predicates=True,
        return_predicate="normalize-records",
        composer_pin="4a3606b8e0354bceb8066f6de536932ee420d1147aa9311084ceafb4afbea850",
    )
    partial.checker = historical
    with pytest.raises(CatalogError, match="METHOD_CHECKER_UNAVAILABLE"):
        partial.check(receive_only=True)


@pytest.mark.parametrize("empty", [False, True])
def test_former_applicability_checker_is_receive_only_and_preserves_reason(empty: bool) -> None:
    from omnis.modules.settings import candidate_store as records
    from omnis.modules.tasks.method_checker_identity import KEY, SEMANTICS

    case = native_case(
        predicates=True,
        empty=empty,
        applies_expected=True,
        composer_pin="bcc1cdbf7b3546e1269e22875bbec2670504e73f25a3e198f65990fb56f31d99",
    )
    case.checker = records.envelope(
        "method-checker",
        {
            "key": KEY,
            "semantics": SEMANTICS,
            "code_digest": "32b3621379b10d20415a09ebb3e7cdda4c6754f5135ff943e639711a44de9036",
        },
    )
    assert obj(case.check()["payload"])["status"] == "UNKNOWN"
    received = obj(case.check(receive_only=True)["payload"])
    assert received["status"] == ("INCOMPLETE" if empty else "COMPLETE")
    if empty:
        assert (
            received["reason"]
            == "Qualified early return; missing done predicates remain unexecuted."
        )


def test_full_not_applicable_check_reason_does_not_invent_early_return() -> None:
    case = native_case(predicates=True, empty=True, applies_expected=True)
    checked = obj(case.check()["payload"])
    assert checked["status"] == "INCOMPLETE"
    assert (
        checked["reason"] == "Bound input predicate is NOT_APPLICABLE; all method steps executed."
    )


@pytest.mark.parametrize("compact", [False, True])
def test_procedure_precondition_false_refuses_same_native_channel_before_access(
    monkeypatch: pytest.MonkeyPatch, compact: bool
) -> None:
    import importlib

    native_case(predicates=True)  # Import consumers before patching, no leaked aliases.
    native = importlib.import_module("agent.contract_execution")
    method = importlib.import_module("omnis_hermes.contract_method")
    attempts: list[str] = []

    def forbidden(*args: object, **kwargs: object) -> object:
        attempts.append("access")
        raise AssertionError("precondition refused too late")

    monkeypatch.setattr(native.BoundContractTools, "_read_bound_input", forbidden)
    monkeypatch.setattr(method, "run_handler", forbidden)
    with pytest.raises(ValueError, match="^PROCEDURE_PRECONDITION_FALSE$"):
        native_case(predicates=True, compact=compact, empty=True, precondition_expected=True)
    assert attempts == []


@pytest.mark.parametrize("on_missing", ["BLOCKED", "INCONCLUSIVE"])
def test_procedure_precondition_unknown_has_explicit_missing_policy(on_missing: str) -> None:
    from omnis.modules.tasks import managed_contract

    case = native_case(predicates=True, precondition_expected=True)
    from omnis_hermes.prompt_bundle import require_preconditions

    p = deepcopy(obj(obj(case.bound["payload"])["resolved_procedure"]))
    obj(rows(p["preconditions"])[0])["on_missing"] = on_missing
    reason = "PROCEDURE_PRECONDITION_UNKNOWN_" + on_missing
    with pytest.raises(CatalogError, match="^" + reason + "$"):
        managed_contract.require_preconditions(p)
    with pytest.raises(ValueError, match="^" + reason + "$"):
        require_preconditions(p)


@pytest.mark.parametrize(
    "attack", ["expected-int", "foreign-ref", "unknown", "duplicate", "missing-policy"]
)
def test_procedure_precondition_untrusted_forms_refuse(attack: str) -> None:
    from omnis.modules.tasks import managed_contract

    case = native_case(predicates=True, precondition_expected=True)
    from omnis_hermes.prompt_bundle import require_preconditions

    p = deepcopy(obj(obj(case.bound["payload"])["resolved_procedure"]))
    c = obj(rows(p["preconditions"])[0])
    if attack == "expected-int":
        c["expected"] = 1
    elif attack == "foreign-ref":
        obj(rows(c["input_refs"])[0])["revision"] = True
    elif attack == "unknown":
        c["predicate_id"] = "lambda: True"
    elif attack == "duplicate":
        rows(p["preconditions"]).append(deepcopy(c))
    else:
        c.pop("on_missing")
    with pytest.raises(CatalogError):
        managed_contract.require_preconditions(p, case.original)
    with pytest.raises(ValueError):
        require_preconditions(p, case.original)


def test_checker_refuses_genuine_receipts_when_procedure_precondition_is_false() -> None:
    case = native_case(predicates=True, precondition_expected=True)
    p = obj(obj(case.bound["payload"])["resolved_procedure"])
    obj(rows(p["preconditions"])[0])["expected"] = False
    rebind_mutation(case)
    with pytest.raises(CatalogError, match="^PROCEDURE_PRECONDITION_FALSE$"):
        case.check()


def test_missing_native_precondition_material_refuses_before_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import importlib
    import json

    from omnis.modules.settings.catalog_schema import canonical

    case = native_case(predicates=True, precondition_expected=True)
    from omnis_hermes.contract_method import assignment

    native = importlib.import_module("agent.contract_execution")
    method = importlib.import_module("omnis_hermes.contract_method")
    attempts: list[str] = []

    def forbidden(*args: object, **kwargs: object) -> object:
        attempts.append("access")
        raise AssertionError("missing material refused too late")

    monkeypatch.setattr(native.BoundContractTools, "_read_bound_input", forbidden)
    monkeypatch.setattr(method, "run_handler", forbidden)
    payload = obj(obj(rows(case.stage["compositions"])[0])["payload"])
    sections = rows(json.loads(str(payload["text"])))
    obj(sections[4]).pop("input")
    reseal_assignment(case.stage, sections, case.prompt_bundle)
    with pytest.raises(ValueError):
        assignment(canonical(case.stage))
    assert attempts == []


def test_bound_predicates_real_native_receipts_complete() -> None:
    case = native_case(predicates=True)
    brief = obj(case.brief["payload"])
    assert len(rows(brief["done_when"])) == 3
    assert len(rows(brief["return_when"])) == 1
    assert obj(case.check()["payload"])["status"] == "COMPLETE"


@pytest.mark.parametrize(
    "method_status,method_gap",
    [("COMPLETE", None), ("INCOMPLETE", "METHOD_INCOMPLETE"), ("UNKNOWN", "METHOD_UNKNOWN")],
)
def test_incomplete_check_rule_is_blocked_not_functional_pass(
    method_status: str, method_gap: str | None
) -> None:
    """SOURCE rule control only; this is not a native/partial execution positive."""
    from omnis.modules.settings import candidate_store as records
    from omnis.modules.tasks import criterion_checks, managed_contract
    from test_c04_criteria import criteria_graph

    graph = criteria_graph([str(uuid4()), str(uuid4())])
    brief = next(r for r in graph if r["kind"] == "task-brief")
    body = obj(brief["payload"])
    cold = managed_contract.blocked_result(brief)
    payload = obj(cold["payload"])
    payload["criterion_results"] = [
        {
            "criterion_id": obj(b)["criterion_id"],
            "bound_procedure_ref": obj(b)["bound_procedure_ref"],
            "control_step_ids": [],
            "evidence_refs": [],
            "proposed_outcome": "PASS",
            "gaps": list(criterion_checks.GAPS),
        }
        for b in rows(body["criterion_bindings"])
    ]
    result = records.envelope("task-result", payload)
    checker = next(r for r in graph if r["kind"] == "method-checker")
    check = records.envelope(
        "method-check",
        {
            "brief_ref": records.reference(brief),
            "task_result_ref": records.reference(result),
            "checker_ref": records.reference(checker),
            "status": method_status,
            "checked_results": payload["method_results"],
            "gap_refs": [obj(r)["ref"] for r in rows(payload["method_results"])],
            "reason": "SOURCE rule control: no completion is being certified.",
        },
    )
    outcomes = criterion_checks.outcome_payloads(brief, result, check, graph)
    assert len(outcomes) == 2
    assert all(o["outcome"] == "BLOCKED" for o in outcomes)
    assert all(
        o["gaps"] == [*criterion_checks.GAPS, *([method_gap] if method_gap else [])]
        for o in outcomes
    )
    assert all(o["method_check_ref"] == records.reference(check) for o in outcomes)
    assert [o["criterion_id"] for o in outcomes] == [
        obj(b)["criterion_id"] for b in rows(body["criterion_bindings"])
    ]
    if method_status == "UNKNOWN":
        assert all("UNKNOWN" in str(o["reason"]) for o in outcomes)


def test_partial_final_wire_and_backend_accept_same_authentic_prefix() -> None:
    from omnis.modules.settings import candidate_store as records
    from omnis.modules.tasks import managed_contract

    case = native_case(predicates=True, return_predicate="normalize-records")
    from omnis_hermes.managed_admission_contract import validate_response

    binding = obj(case.binding["payload"])
    final = {
        "protocol": "omnis-managed-admission-v4",
        "status": "INCONCLUSIVE",
        "reason": "CONTRACT_PURE",
        "ticket": binding["ticket"],
        "manifest_ref": records.reference(obj(case.stage["manifest"])),
        "binding_ref": records.reference(case.binding),
        "native_root_id": binding["native_root_id"],
        "entries": binding["entries"],
        "executions": [case.execution],
    }
    assert validate_response(final) == final
    assert managed_contract.validate_final(final, case.stage["manifest"], case.binding) == final
    for attack in ("success", "omission", "late-artifact"):
        bad = deepcopy(final)
        if attack == "success":
            bad["status"] = "SUCCEEDED"
        elif attack == "omission":
            rows(obj(rows(bad["executions"])[0])["records"]).pop(2)
        else:
            other = native_case(predicates=True)
            bad["executions"] = [other.execution]
        with pytest.raises(ValueError):
            validate_response(bad)
        with pytest.raises(CatalogError):
            managed_contract.validate_final(bad, case.stage["manifest"], case.binding)


def test_explicit_return_selection_is_bounded_existing_prepare_request() -> None:
    from omnis.modules.runs.managed_admission import validate_request
    from test_c03_managed_capture import request

    case = native_case(predicates=True)
    value = request()
    value.update(
        schema_version=3,
        return_predicate_id="normalize-records",
        slot_values=[
            {
                "slot_name": "records",
                "refs": [rows(obj(case.brief["payload"])["input_artifact_refs"])[0]],
            }
        ],
    )
    assert validate_request("prepare-method", value) == value
    for invalid in (None, True, "unknown", "foreign.normalize-records", "lambda: True"):
        with pytest.raises(CatalogError):
            validate_request("prepare-method", {**value, "return_predicate_id": invalid})
    with pytest.raises(CatalogError):
        validate_request("prepare-composed", value)


@pytest.mark.parametrize("attack", ["unknown", "foreign", "collision", "missing", "bool-ref"])
def test_bound_predicates_refuse_qualified_scope_errors(attack: str) -> None:
    case = native_case(predicates=True)
    body = obj(case.brief["payload"])
    done = rows(body["done_when"])
    if attack == "unknown":
        obj(done[0])["predicate_id"] = "unknown"
    elif attack == "foreign":
        obj(obj(done[0])["bound_procedure_ref"])["id"] = str(uuid4())
    elif attack == "collision":
        done.append(deepcopy(done[0]))
    elif attack == "missing":
        done.pop(0)
    else:
        obj(obj(done[0])["bound_procedure_ref"])["revision"] = True
    rebind_mutation(case)
    from omnis_hermes.prompt_bundle import validate_predicates

    with pytest.raises(ValueError):
        validate_predicates(body, case.bound)
    with pytest.raises(CatalogError):
        case.check()


def test_return_predicate_does_not_credit_missing_done_receipt() -> None:
    case = native_case(predicates=True)
    from omnis_hermes.contract_method import predicate_values, task_result

    emitted = [obj(r) for r in rows(case.execution["records"])]
    receipts = [r for r in emitted if r["kind"] == "contract-tool-receipt"]
    artifacts = [r for r in emitted if r["kind"] == "contract-artifact"]
    receipts = [r for r in receipts if obj(r["payload"])["step_id"] != "normalize-operations"]
    values = predicate_values(
        case.brief, case.bound, case.original, receipts, artifacts, prompt_bundle=case.prompt_bundle
    )
    assert values["build-surface-map"] is True  # return predicate really holds
    assert values["normalize-records"] is False  # a done predicate does not
    with pytest.raises(ValueError, match="BOUND_DONE_UNSATISFIED"):
        task_result(
            case.brief,
            case.bound,
            case.original,
            receipts,
            artifacts,
            prompt_bundle=case.prompt_bundle,
        )


@pytest.mark.parametrize("attack", ["key", "digest"])
def test_checker_identity_must_match_executing_checker(attack: str) -> None:
    from omnis.modules.settings import candidate_store as records

    case = native_case(predicates=True)
    descriptor = deepcopy(obj(case.checker["payload"]))
    descriptor["key" if attack == "key" else "code_digest"] = (
        "unknown" if attack == "key" else "0" * 64
    )
    case.checker = records.envelope("method-checker", descriptor)
    checked = obj(case.check()["payload"])
    assert checked["status"] == "UNKNOWN"
    assert len(rows(checked["gap_refs"])) == 3
    assert "METHOD_CHECKER_UNAVAILABLE" in str(checked["reason"])


def test_arbitrary_checker_ref_alone_never_grants_complete() -> None:
    from omnis.modules.settings import candidate_store as records

    case = native_case(predicates=True)
    case.checker = records.reference(
        records.envelope("method-checker", {"key": "unknown", "code_digest": "0" * 64})
    )
    with pytest.raises(CatalogError):
        case.check()


@pytest.mark.parametrize("erase_requirements", [False, True])
def test_current_empty_predicates_cannot_erase_obligations(erase_requirements: bool) -> None:
    case = native_case(predicates=True)
    body = obj(case.brief["payload"])
    body["done_when"] = []
    body["return_when"] = []
    if erase_requirements:
        procedure = obj(obj(case.bound["payload"])["resolved_procedure"])
        procedure["method_requirements"] = rows(procedure["method_requirements"])[1:2]
        plan = obj(body["method_plan"])
        plan["requirements"] = rows(plan["requirements"])[1:2]
        result = obj(obj(rows(case.execution["records"])[0])["payload"])
        result["method_results"] = rows(result["method_results"])[1:2]
    rebind_mutation(case)
    with pytest.raises(CatalogError):
        case.check()


@pytest.mark.parametrize("location", ["input", "step", "requirement"])
@pytest.mark.parametrize("attack", ["bool", "kind", "extra", "missing"])
def test_nested_schema_refs_denied_before_predicate_comparison(location: str, attack: str) -> None:
    case = native_case(predicates=True)
    p = deepcopy(obj(obj(case.bound["payload"])["resolved_procedure"]))
    schema = (
        obj(p["input_schema_ref"])
        if location == "input"
        else obj(obj(rows(p["probe"])[0])["output_schema_ref"])
        if location == "step"
        else obj(rows(obj(rows(p["method_requirements"])[0])["artifact_schema_refs"])[0])
    )
    if attack == "bool":
        schema["revision"] = True
    elif attack == "kind":
        schema["kind"] = "procedure"
    elif attack == "extra":
        schema["extra"] = 1
    else:
        del schema["digest"]
    from omnis_hermes.prompt_bundle import predicate_closure as native_closure

    from omnis.modules.tasks.managed_contract import predicate_closure as api_closure

    with pytest.raises(CatalogError):
        api_closure(p)
    with pytest.raises(ValueError):
        native_closure(p)


@pytest.mark.parametrize("attack", ["missing", "unknown", "duplicate", "bad-key"])
def test_predicate_steps_deny_before_registry_lookup(attack: str) -> None:
    case = native_case(predicates=True)
    p = deepcopy(obj(obj(case.bound["payload"])["resolved_procedure"]))
    steps = rows(p["probe"])
    if attack == "missing":
        steps.pop(0)
    elif attack == "unknown":
        obj(steps[0])["id"] = "foreign-step"
    elif attack == "duplicate":
        obj(steps[0])["id"] = obj(steps[1])["id"]
    else:
        obj(steps[0])["id"] = True
    from omnis_hermes.prompt_bundle import predicate_closure as native_closure

    from omnis.modules.tasks.managed_contract import predicate_closure as api_closure

    with pytest.raises(CatalogError):
        api_closure(p)
    with pytest.raises(ValueError):
        native_closure(p)


@pytest.mark.parametrize(
    "pin",
    [
        "717549a613365ec95c40276903a92bf9b603092232947e0ee79bf5e1745854ed",
        "1d32db3dcd15ee65d9d479d0401675d255a856b36beaca1bde1093ed0fb0b00a",
        "2cec176a5e622df2751e069b2a676c7e64578bea33b768aab63b09c78698f473",
    ],
)
def test_explicit_legacy_zero_and_historical_check_payload_are_receive_compatible(pin: str) -> None:
    from omnis.modules.settings import candidate_store as records
    from omnis.modules.settings.catalog_schema import canonical
    from omnis.modules.tasks.method_checker_identity import SEMANTICS

    case = native_case(
        criterion_ids=[str(uuid4())] if pin.startswith("717") else None, composer_pin=pin
    )
    assert obj(case.brief["payload"])["done_when"] == []
    current = obj(case.check()["payload"])
    case.checker = records.envelope(
        "method-checker",
        {
            "key": "managed.contract-pure",
            "semantics": SEMANTICS,
            "code_digest": "9b87dc17293895299fa5088991afa16a0d73639e4bd400c28e4a80544dfe80e3"
            if pin.startswith("717")
            else "125c9f79457f2e1437d7de7b31a81eb659062ee4a8e398a25ec670fb503aa611",
        },
    )
    assert obj(case.check()["payload"])["status"] == "UNKNOWN"  # Never first COMPLETE.
    current["checker_ref"] = records.reference(case.checker)
    assert canonical(obj(case.check(receive_only=True)["payload"])) == canonical(current)


@pytest.mark.parametrize("attack", ["empty", "schema-bool", "unknown-step", "missing-step"])
def test_resealed_full_composition_denies_before_native_allocation(attack: str) -> None:
    import json

    from omnis.modules.settings.catalog_schema import canonical
    from omnis.modules.tasks import managed_composition

    case = native_case(predicates=True)
    from omnis_hermes.contract_method import assignment, task_result

    stage = case.stage
    payload = obj(obj(rows(stage["compositions"])[0])["payload"])
    sections = json.loads(str(payload["text"]))
    brief = obj(obj(sections[2])["record"])
    bound = obj(obj(sections[3])["record"])
    procedure = obj(obj(bound["payload"])["resolved_procedure"])
    if attack == "empty":
        obj(brief["payload"])["done_when"] = []
        obj(brief["payload"])["return_when"] = []
    elif attack == "schema-bool":
        obj(obj(rows(procedure["probe"])[0])["output_schema_ref"])["revision"] = True
    elif attack == "unknown-step":
        obj(rows(procedure["probe"])[0])["id"] = "foreign-step"
    else:
        rows(procedure["probe"]).pop(0)
    reseal_assignment(stage, sections, case.prompt_bundle)
    with pytest.raises(ValueError):
        assignment(canonical(stage))  # Same guard used before constructor identity allocation.
    manifest = obj(stage["manifest"])
    with pytest.raises(CatalogError):
        managed_composition.validate(
            rows(stage["compositions"])[0], rows(obj(manifest["payload"])["entries"])[0], manifest
        )
    if attack == "empty":
        with pytest.raises(ValueError):
            task_result(brief, bound, case.original, [], [], prompt_bundle=case.prompt_bundle)


def test_bound_predicate_false_na_and_foreign_header_refuse() -> None:
    for attack in ("false-na", "header", "gap"):
        case = native_case(predicates=True)
        result = obj(rows(case.execution["records"])[0])
        body = obj(result["payload"])
        if attack == "false-na":
            obj(rows(body["method_results"])[0])["state"] = "NOT_APPLICABLE"
        elif attack == "header":
            obj(body["header"])["task_id"] = str(uuid4())
        else:
            rows(body["method_results"]).pop()
        rebind_mutation(case)
        with pytest.raises(CatalogError):
            case.check()


@pytest.mark.asyncio
@pytest.mark.parametrize("unavailable", ["checker", "schema"])
@pytest.mark.parametrize("tamper", [None, "gap", "reason-list", "duplicate"])
async def test_owner_retains_current_unknown_without_historical_promotion(
    monkeypatch: pytest.MonkeyPatch, unavailable: str, tamper: str | None
) -> None:
    """Actual owner seam over SOURCE execution; synthetic graph/schema reader, no DB."""
    from unittest.mock import Mock

    from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

    from omnis.modules.runs.managed_admission import ManagedAdmission
    from omnis.modules.settings import candidate_store as records
    from omnis.modules.settings.catalog_schema import canonical
    from omnis.modules.tasks.method_checker_identity import KEY, SEMANTICS

    case = native_case(
        predicates=True,
        composer_pin="4a3606b8e0354bceb8066f6de536932ee420d1147aa9311084ceafb4afbea850",
    )
    if unavailable == "checker":
        case.checker = records.envelope(
            "method-checker",
            {
                "key": KEY,
                "semantics": SEMANTICS,
                "code_digest": "388fe9da680951249202045b10e10245d42352a0c194413d221d647b54a085db",
            },
        )
    manifest = obj(case.stage["manifest"])
    binding = obj(case.binding["payload"])
    emitted = [obj(r) for r in rows(case.execution["records"])]
    final = records.envelope(
        "native-task-receipt",
        {
            "protocol": "omnis-managed-admission-v4",
            "status": "SUCCEEDED",
            "reason": "CONTRACT_PURE",
            "ticket": binding["ticket"],
            "manifest_ref": records.reference(manifest),
            "binding_ref": records.reference(case.binding),
            "native_root_id": binding["native_root_id"],
            "entries": binding["entries"],
            "executions": [case.execution],
        },
    )
    run = records.envelope("managed-run", {})
    graph = [
        run,
        manifest,
        case.brief,
        case.bound,
        case.binding,
        case.original,
        case.prompt_bundle,
        case.checker,
        *case.actions,
        *emitted,
        final,
    ]
    domain = ManagedAdmission(Mock(spec=AsyncEngine))
    available = unavailable != "schema"

    async def schemas(*args: object, **kwargs: object) -> dict[str, dict[str, object]]:
        return case.schemas if available else {}

    monkeypatch.setattr(domain, "_method_schemas", schemas)
    conn = Mock(spec=AsyncConnection)
    checker_ref = records.reference(case.checker)
    first = await domain._result_check(
        conn, case.owner_id, str(run["id"]), case.brief, emitted[0], checker_ref, graph=graph
    )
    assert obj(first["payload"])["status"] == "UNKNOWN"
    assert len(rows(obj(first["payload"])["gap_refs"])) == 3
    prior_payload = obj(first["payload"])
    if tamper == "gap":
        prior_payload = {**prior_payload, "gap_refs": []}
    elif tamper == "reason-list":
        prior_payload = {**prior_payload, "reason": [prior_payload["reason"]]}
    retained = records.envelope("method-check", prior_payload)
    graph.append(retained)
    if tamper == "duplicate":
        graph.append(records.envelope("method-check", prior_payload))
    available = True
    if tamper is not None:
        with pytest.raises(CatalogError, match="RESULT_CONFLICT"):
            await domain._result_check(
                conn,
                case.owner_id,
                str(run["id"]),
                case.brief,
                emitted[0],
                checker_ref,
                graph=graph,
            )
        return
    second = await domain._result_check(
        conn, case.owner_id, str(run["id"]), case.brief, emitted[0], checker_ref, graph=graph
    )
    assert canonical(second["payload"]) == canonical(first["payload"])
    assert obj(second["payload"])["status"] == "UNKNOWN"


@pytest.mark.parametrize(
    "digest,status",
    [
        ("df2babe1e5c12c19f9abfad75312086e11e4d4485708ed0709d8f438f510dc5b", "INCOMPLETE"),
        ("df2babe1e5c12c19f9abfad75312086e11e4d4485708ed0709d8f438f510dc5b", "COMPLETE"),
        ("30cf2d058b7ed7c3693592ad68d6cd5b0040c5f65a7b81a4452ecf9e2f05f7a8", "COMPLETE"),
    ],
)
def test_historical_no_oracle_rule_is_receive_only(
    monkeypatch: pytest.MonkeyPatch, digest: str, status: str
) -> None:
    """Exact historical SOURCE identities; not an installed historical reader proof."""
    from omnis.modules.settings import candidate_store as records
    from omnis.modules.tasks import criterion_checks, managed_contract
    from test_c04_criteria import criteria_graph

    original_rule = criterion_checks.rule_payload

    def old_rule(procedure_ref: object, procedure: object) -> dict[str, object]:
        return {**original_rule(procedure_ref, procedure), "code_digest": digest}

    with monkeypatch.context() as old:
        old.setattr(criterion_checks, "rule_payload", old_rule)
        graph = criteria_graph([str(uuid4()), str(uuid4())])
    brief = next(r for r in graph if r["kind"] == "task-brief")
    payload = obj(managed_contract.blocked_result(brief)["payload"])
    payload["criterion_results"] = [
        {
            "criterion_id": obj(b)["criterion_id"],
            "bound_procedure_ref": obj(b)["bound_procedure_ref"],
            "proposed_outcome": "BLOCKED",
            "control_step_ids": [],
            "evidence_refs": [],
            "gaps": list(criterion_checks.GAPS),
        }
        for b in rows(obj(brief["payload"])["criterion_bindings"])
    ]
    result = records.envelope("task-result", payload)
    check = records.envelope(
        "method-check",
        {
            "brief_ref": records.reference(brief),
            "task_result_ref": records.reference(result),
            "status": status,
        },
    )
    with pytest.raises(CatalogError, match="CRITERION_RULE_UNAVAILABLE"):
        criterion_checks.outcome_payloads(brief, result, check, graph)
    outcomes = criterion_checks.outcome_payloads(brief, result, check, graph, receive_only=True)
    assert len(outcomes) == 2 and all(o["outcome"] == "BLOCKED" for o in outcomes)
    assert all(
        o["gaps"]
        == [*criterion_checks.GAPS, *(["METHOD_INCOMPLETE"] if status == "INCOMPLETE" else [])]
        for o in outcomes
    )
    unknown = records.envelope("method-check", {**obj(check["payload"]), "status": "UNKNOWN"})
    with pytest.raises(CatalogError, match="CRITERION_CHECK_REQUIRED"):
        criterion_checks.outcome_payloads(brief, result, unknown, graph, receive_only=True)


@pytest.mark.asyncio
async def test_owner_keeps_available_schemas_after_missing_binding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Actual schema-reader SOURCE seam; SQL/preparation are explicit test doubles."""
    import base64
    from pathlib import Path
    from unittest.mock import AsyncMock, Mock

    from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

    from omnis.modules.runs import native_preparation
    from omnis.modules.runs.managed_admission import ManagedAdmission
    from omnis.modules.settings import candidate_store as records
    from omnis.modules.settings.catalog_models import Manifest
    from omnis.modules.settings.catalog_schema import canonical, dto, load_json

    case = native_case(predicates=True)
    root = Path(__file__).resolve().parents[2] / "skills/records-mapping-contract"
    manifest = dto((root / "omnis.yaml").read_bytes(), Manifest)
    schema_bindings = [b for b in manifest.file_bindings if b.entity_kind == "schema"]
    files = {"omnis.yaml": (root / "omnis.yaml").read_bytes()}
    files.update({b.path: (root / b.path).read_bytes() for b in schema_bindings})
    identity_keys: dict[str, str] = {}
    for key, document in case.schemas.items():
        matching = [
            b for b in schema_bindings if canonical(load_json(files[b.path])) == canonical(document)
        ]
        assert len(matching) == 1
        identity_keys[str(obj(load_json(key))["id"])] = matching[0].key
    missing = obj(case.original["payload"])["schema_ref"]
    missing_id = str(obj(missing)["id"])
    receipt = records.envelope(
        "native-preparation-receipt",
        {"bundle_ref": records.reference(records.envelope("native-document-bundle", {}))},
    )
    run = records.envelope("managed-run", {"preparation_receipt_ref": records.reference(receipt)})
    bundle = records.envelope(
        "native-document-bundle",
        {
            "packages": [
                {
                    "package_key": manifest.package_key,
                    "files": [
                        {"path": path, "content_b64": base64.b64encode(raw).decode()}
                        for path, raw in files.items()
                    ],
                }
            ]
        },
    )
    monkeypatch.setattr(records, "get", AsyncMock(return_value=(None, receipt)))
    monkeypatch.setattr(
        native_preparation,
        "read_receipt",
        AsyncMock(return_value={"receipt_ref": records.reference(receipt), "bundle": bundle}),
    )
    conn = Mock(spec=AsyncConnection)

    async def execute(statement: object, parameters: dict[str, object]) -> Mock:
        value = (
            None
            if parameters["id"] == missing_id
            else {
                "package_key": manifest.package_key,
                "entity_key": identity_keys[str(parameters["id"])],
            }
        )
        query = Mock()
        query.mappings.return_value.one_or_none.return_value = value
        return query

    conn.execute = execute
    domain = ManagedAdmission(Mock(spec=AsyncEngine))
    available = await domain._method_schemas(conn, case.owner_id, run, case.bound)
    assert available == {k: v for k, v in case.schemas.items() if k != canonical(missing).decode()}
    assert available
