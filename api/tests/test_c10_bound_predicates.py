"""Qualified C10 receipt consumer. SOURCE only; PG/native owner separately."""

from copy import deepcopy
from uuid import uuid4

import pytest

from omnis.modules.settings.catalog_models import CatalogError
from test_contract_method_checks import native_case, obj, rebind_mutation, rows


def test_bound_predicates_real_native_receipts_complete() -> None:
    case = native_case(predicates=True)
    brief = obj(case.brief["payload"])
    assert len(rows(brief["done_when"])) == 3
    assert len(rows(brief["return_when"])) == 1
    assert obj(case.check()["payload"])["status"] == "COMPLETE"


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
    with pytest.raises(CatalogError):
        case.check()


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
    with pytest.raises(CatalogError, match="METHOD_CHECKER_UNAVAILABLE"):
        case.check()  # A historical descriptor never grants a first COMPLETE.
    current["checker_ref"] = records.reference(case.checker)
    assert canonical(obj(case.check(receive_only=True)["payload"])) == canonical(current)


@pytest.mark.parametrize("attack", ["empty", "schema-bool", "unknown-step", "missing-step"])
def test_resealed_full_composition_denies_before_native_allocation(attack: str) -> None:
    import json

    from omnis.modules.settings.catalog_schema import canonical
    from omnis.modules.tasks import managed_composition

    case = native_case(predicates=True)
    from omnis_hermes.contract_method import assignment, task_result
    from test_prompt_bundle import reseal_graph

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
    reseal_graph(stage, sections, case.prompt_bundle)
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
