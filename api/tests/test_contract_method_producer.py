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


@pytest.mark.parametrize("empty", [False, True])
@pytest.mark.parametrize(
    "guard",
    [
        "precondition",
        "invalidation",
        "invalidation-old-pin",
        "evidence-full",
        "evidence-optional-prefix",
        "evidence-required-prefix",
        "evidence-all-optional-prefix",
    ],
)
def test_first_party_precondition_compiles_binds_and_refuses_before_brief(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, empty: bool, guard: str
) -> None:
    from uuid import uuid4

    from fixtures.b06a.consumer import write_yaml, yaml_object
    from fixtures.c03_records import EVALUATION_VALUE, PATHS, records_seed
    from omnis.modules.runs.managed_admission import BuildSource
    from omnis.modules.runs.native_preparation_models import prepare_packages
    from omnis.modules.settings.candidate_material import capture
    from omnis.modules.settings.catalog_models import CatalogError, Manifest, Procedure
    from omnis.modules.settings.catalog_schema import dto
    from omnis.modules.settings.skill_catalog import compile_catalog
    from test_managed_contract import ref

    seed = records_seed(tmp_path / "precondition")
    path = seed.package / "templates/procedures/map-records.yaml"
    authored = yaml_object(path)
    authored["preconditions"] = [
        {
            "predicate_id": "contract.records-nonempty",
            "input_refs": [{"kind": "CASE_SLOT_REF", "name": "records"}],
            "expected": True,
            "on_missing": "BLOCKED",
        }
    ]
    if guard.startswith("invalidation"):
        authored["preconditions"] = []
        authored["invalidation_predicate_ids"] = ["contract.records-empty"]
    if guard.startswith("evidence-"):
        authored["preconditions"] = []
        authored["method_requirements"] = [
            {
                **mapping(raw),
                "evidence_kinds": ["contract-artifact"] if index < 2 else [],
                "required": guard != "evidence-optional-prefix"
                if index == 1
                else mapping(raw)["required"],
            }
            for index, raw in enumerate(managed_contract.sequence(authored["method_requirements"]))
        ]
        if guard == "evidence-all-optional-prefix":
            authored["method_requirements"] = [
                {**mapping(r), "required": False}
                for r in managed_contract.sequence(authored["method_requirements"])
            ]
        authored["evidence_requirements"] = [
            {"kind": "contract-artifact", "minimum": 1, "mandatory": True}
        ]
    write_yaml(path, authored)
    compiled = compile_catalog((seed.package,), seed.profile)
    retained, sources, _ = capture([str(seed.package)], str(seed.profile))
    pairs = [
        ({**ref("package"), "digest": s["package_digest"]}, s)
        for s in sources
        if s["source_kind"] == "package"
    ]
    packages = prepare_packages(retained, pairs)
    bindings: list[dict[str, object]] = [
        {
            "package_key": r.package_key,
            "entity_kind": r.entity_kind,
            "key": r.key,
            "ref": {**ref(r.entity_kind), "digest": pairs[0][0]["digest"]},
        }
        for r in compiled.refs
    ]
    selection = records.envelope(
        "execution-selection",
        {"snapshot_ref": ref("run-snapshot"), "selected_package_refs": [p[0] for p in pairs]},
    )
    procedure_ref = mapping(next(b["ref"] for b in bindings if b["entity_kind"] == "procedure"))
    procedure = dto(path.read_bytes(), Procedure)
    source = BuildSource(
        selection,
        ref("native-preparation-receipt"),
        procedure_ref,
        procedure,
        bindings,
        "records-mapping-contract",
        "RECON",
        procedure.limits,
        packages,
        {p: (seed.package / p).read_bytes() for p in PATHS},
        dto((seed.package / "omnis.yaml").read_bytes(), Manifest),
    )
    with monkeypatch.context() as prior:
        if guard == "invalidation-old-pin":
            prior.setattr(
                managed_composition,
                "COMPOSER_REVISION",
                managed_composition.PRECONDITION_COMPOSER_REVISION,
            )
        prefix = source.build(context_only=True, method_execution=True)
    run = next(r for r in prefix if r["kind"] == "managed-run")
    body = mapping(run["payload"])
    schema_ref, raw, schema_path = source.input_schema()
    context = records.envelope(
        "contract-input-context",
        {
            "version": 2,
            "namespace": "RUN",
            "owner_id": str(uuid4()),
            "basis_ref": records.reference(run),
            "snapshot_ref": body["snapshot_ref"],
            "selection_ref": body["selection_ref"],
            "procedure_ref": procedure_ref,
            "mission_ref": body["mission_ref"],
            "focus_ref": body["focus_ref"],
            "schema_ref": schema_ref,
        },
    )
    item = produce_input(context, {"records": []} if empty else EVALUATION_VALUE, raw, str(uuid4()))
    section = material_section(context, item, schema_ref, raw, schema_path=schema_path)
    prefix.extend([context, item])
    before = canonical(prefix)
    if guard == "invalidation-old-pin":
        attempts: list[str] = []

        def forbidden_uuid() -> object:
            attempts.append("uuid")
            raise AssertionError("old pin refused after assignment allocation")

        monkeypatch.setattr(managed_contract, "uuid4", forbidden_uuid)
        with pytest.raises(CatalogError, match="^BOUND_PREDICATE_UNAVAILABLE$"):
            source.build(prefix=prefix, case_input=section, method_execution=True)
        assert attempts == [] and canonical(prefix) == before
        return
    if empty and not guard.startswith("evidence-"):
        reason = (
            "PROCEDURE_PRECONDITION_FALSE" if guard == "precondition" else "PROCEDURE_INVALIDATED"
        )
        with pytest.raises(CatalogError, match="^" + reason + "$"):
            source.build(prefix=prefix, case_input=section, method_execution=True)
        assert canonical(prefix) == before
        assert not any(
            r["kind"] in {"task-brief", "bound-procedure", "launch-manifest", "task-result"}
            for r in prefix
        )
    else:
        graph = source.build(
            prefix=prefix,
            case_input=section,
            method_execution=True,
            return_predicate_id="normalize-records" if guard.endswith("prefix") else None,
        )
        bound = next(r for r in graph if r["kind"] == "bound-procedure")
        resolved = mapping(mapping(bound["payload"])["resolved_procedure"])
        if guard == "precondition":
            assert mapping(managed_contract.sequence(resolved["preconditions"])[0])[
                "input_refs"
            ] == [records.reference(item)]
        elif guard.startswith("invalidation"):
            assert resolved["invalidation_predicate_ids"] == ["contract.records-empty"]
        brief = next(r for r in graph if r["kind"] == "task-brief")
        assert (
            len(
                managed_contract.sequence(
                    mapping(mapping(brief["payload"])["method_plan"])["requirements"]
                )
            )
            == 3
        )
        assert canonical(graph[: len(prefix)]) == before
        if guard.startswith("evidence-"):
            brief_body = mapping(brief["payload"])
            keys = (
                []
                if guard == "evidence-all-optional-prefix"
                else ["normalize-records"]
                + ([] if guard == "evidence-optional-prefix" else ["build-surface-map"])
            )
            assert len(managed_contract.sequence(brief_body["return_when"])) == 1
            assert [
                mapping(r)["predicate_id"]
                for r in managed_contract.sequence(brief_body["done_when"])
            ] == keys
            assert [
                mapping(r)["requirement_key"]
                for r in managed_contract.sequence(brief_body["required_evidence"])
            ] == keys
            stage = managed_composition.stage_payload(graph[-1], graph)
            import sys
            from importlib import import_module

            adapter = str(Path(__file__).resolve().parents[2] / "integrations/hermes/src")
            sys.path.insert(0, adapter)
            try:
                assert (
                    import_module("omnis_hermes.managed_admission_contract").validate_stage(stage)
                    == graph[-1]
                )
            finally:
                sys.path.remove(adapter)


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
@pytest.mark.parametrize("early_return", [False, True])
async def test_host_consumes_v4_terminal_on_the_same_protocol_boundary(early_return: bool) -> None:
    """SOURCE transport simulation, not authentic native/PG acceptance."""
    import time
    from types import SimpleNamespace

    from test_contract_method_checks import native_case, obj, rebind_mutation

    case = native_case(predicates=early_return, return_predicate="normalize-records")
    native = import_module("omnis_hermes.runtime_host")
    host = native.RuntimeHost(Path("/nonexistent"))
    obj(case.binding["payload"])["runtime_boot"] = host.boot
    rebind_mutation(case)
    body = obj(case.binding["payload"])
    manifest_ref = records.reference(records.envelope("launch-manifest", {}))
    response = {
        "protocol": "omnis-managed-admission-v4",
        "status": "INCONCLUSIVE" if early_return else "SUCCEEDED",
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
