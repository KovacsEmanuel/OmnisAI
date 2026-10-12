"""Native method assignment producer; SOURCE parity, not native execution proof."""

import sys
from importlib import import_module
from pathlib import Path

import pytest

from omnis.modules.settings import candidate_store as records
from omnis.modules.settings.catalog_schema import canonical
from omnis.modules.tasks import managed_composition, managed_contract
from omnis.modules.tasks.contract_case_input import material_section, produce_input
from omnis.modules.tasks.managed_contract import mapping, text
from test_c03_managed_capture import capture_source, material


def method_graph() -> list[dict[str, object]]:
    source = capture_source()
    _, cold_section = material(source, '[{"method":"GET","path":"/synthetic","status":200}]')
    prefix = source.build(context_only=True, method_execution=True)
    run = next(r for r in prefix if r["kind"] == "managed-run")
    body = mapping(run["payload"])
    context = records.envelope(
        "contract-input-context",
        {
            **mapping(mapping(cold_section["context"])["payload"]),
            "basis_ref": records.reference(run),
            "mission_ref": body["mission_ref"],
            "focus_ref": body["focus_ref"],
        },
    )
    schema_ref, raw, path = source.input_schema()
    item = produce_input(
        context,
        mapping(mapping(cold_section["input"])["payload"])["value"],
        raw,
        text(context["id"]),
    )
    prefix.extend([context, item])
    section = material_section(context, item, schema_ref, raw, schema_path=path)
    return source.build(prefix=prefix, case_input=section, method_execution=True)


def test_method_assignment_is_distinct_from_cold_and_native_valid() -> None:
    graph = method_graph()
    manifest = graph[-1]
    assert managed_contract.manifest_protocol(manifest) == "omnis-managed-admission-v4"
    stage = managed_composition.stage_payload(manifest, graph)
    path = str(Path(__file__).resolve().parents[2] / "integrations/hermes/src")
    sys.path.insert(0, path)
    try:
        native = import_module("omnis_hermes.managed_admission_contract")
        assert native.validate_stage(stage) == manifest
    finally:
        sys.path.remove(path)
    assert b'"resolution":"NO_MODEL"' in canonical(manifest["payload"])
    assert mapping(manifest["payload"])["effective"] is None
    assert not any(r["kind"] == "task-result" for r in graph)


def test_method_context_and_prepare_are_explicit_not_cold_promotion() -> None:
    from omnis.modules.runs.contract_inputs import validate_request as context_request
    from omnis.modules.runs.managed_admission import validate_request as assignment_request
    from test_c03_managed_capture import request

    req = request()
    context = {
        k: v
        for k, v in req.items()
        if k
        in {"schema_version", "owner_id", "command_id", "selection_ref", "preparation_command_id"}
    }
    context["schema_version"] = 1
    assert context_request("create-method-context", context) == context
    assert assignment_request("prepare-method", req) == req


def test_supervisor_lease_owner_is_not_the_catalog_input_owner() -> None:
    from uuid import uuid4

    from test_contract_method_checks import native_case, obj, rebind_mutation

    case = native_case()
    operator = obj(case.original["payload"])["owner_id"]
    supervisor = str(uuid4())
    assert operator != supervisor
    obj(obj(case.binding["payload"])["authority"])["owner"] = supervisor
    rebind_mutation(case)
    assert obj(case.check()["payload"])["status"] == "COMPLETE"


@pytest.mark.asyncio
async def test_host_consumes_v4_terminal_on_the_same_protocol_boundary() -> None:
    """SOURCE transport simulation, not authentic native/PG acceptance."""
    import time
    from types import SimpleNamespace

    from test_contract_method_checks import native_case, obj, rebind_mutation

    case = native_case()
    native = import_module("omnis_hermes.runtime_host")
    host = native.RuntimeHost(Path("/nonexistent"))
    obj(case.binding["payload"])["runtime_boot"] = host.boot
    rebind_mutation(case)
    body = obj(case.binding["payload"])
    manifest_ref = records.reference(records.envelope("launch-manifest", {}))
    response = {
        "protocol": "omnis-managed-admission-v4",
        "status": "SUCCEEDED",
        "reason": "CONTRACT_PURE",
        "ticket": body["ticket"],
        "manifest_ref": manifest_ref,
        "binding_ref": records.reference(case.binding),
        "native_root_id": body["native_root_id"],
        "entries": body["entries"],
        "executions": [case.execution],
    }
    calls: list[object] = []

    async def transport(method: str, params: object, **kwargs: object) -> object:
        calls.append(params)
        return response

    host.peer = SimpleNamespace(call=transport, failure=None)
    host.process = SimpleNamespace(returncode=None)
    host.state, host.epoch = "READY", 1
    host.deadline_ns = time.monotonic_ns() + 4_000_000_000
    request = {
        "op": "task_release",
        "deadline_ns": host.deadline_ns,
        "payload": {
            "protocol": response["protocol"],
            "ticket": body["ticket"],
            "manifest_ref": manifest_ref,
            "binding": case.binding,
        },
    }
    assert await host._managed(request) == response
    assert len(calls) == 1


def test_shared_result_schema_retains_exact_header_and_requirement_constraints() -> None:
    from copy import deepcopy
    from uuid import uuid4

    from jsonschema import Draft202012Validator, ValidationError

    from test_contract_method_checks import native_case, obj, rows

    case = native_case()
    brief = obj(case.brief["payload"])
    header = {k: v for k, v in obj(brief["header"]).items() if k != "result_schema_ref"}
    schema = managed_contract.result_json_schema(
        header,
        [obj(r) for r in rows(obj(brief["method_plan"])["requirements"])],
        method_execution=True,
    )
    validator = Draft202012Validator(schema)
    result = obj(obj(rows(case.execution["records"])[0])["payload"])
    validator.validate(result)
    assert "$defs" in schema
    for attack in (
        "foreign-header",
        "foreign-schema-kind",
        "foreign-bound",
        "duplicate-requirement",
        "reorder",
        "missing-field",
        "unknown-field",
        "false-na",
        "extra-result",
        "criterion",
        "review",
    ):
        bad = deepcopy(result)
        methods = [obj(r) for r in rows(bad["method_results"])]
        if attack == "foreign-header":
            obj(bad["header"])["attempt_id"] = str(uuid4())
        elif attack == "foreign-schema-kind":
            obj(obj(bad["header"])["result_schema_ref"])["kind"] = "artifact"
        elif attack == "foreign-bound":
            obj(obj(methods[0]["ref"])["bound_procedure_ref"])["id"] = str(uuid4())
        elif attack == "duplicate-requirement":
            methods[1]["ref"] = deepcopy(methods[0]["ref"])
        elif attack == "reorder":
            methods[0], methods[1] = methods[1], methods[0]
        elif attack == "missing-field":
            del methods[0]["artifact_refs"]
        elif attack == "unknown-field":
            methods[0]["extra"] = True
        elif attack == "false-na":
            methods[0]["state"] = "NOT_APPLICABLE"
        elif attack == "extra-result":
            methods.append(deepcopy(methods[0]))
        elif attack == "criterion":
            bad["criterion_results"] = [{}]
        else:
            bad["method_review"] = {}
        bad["method_results"] = methods
        with pytest.raises(ValidationError):
            validator.validate(bad)
