"""Native method assignment producer; SOURCE parity, not native execution proof."""

import sys
from importlib import import_module
from pathlib import Path

import pytest

from omnis.modules.runs.managed_admission import BuildSource
from omnis.modules.settings import candidate_store as records
from omnis.modules.settings.catalog_schema import canonical
from omnis.modules.tasks import managed_composition, managed_contract
from omnis.modules.tasks.contract_case_input import material_section, produce_input
from omnis.modules.tasks.managed_contract import mapping, text
from test_c03_managed_capture import capture_source, material


async def batch2_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[list[dict[str, object]], dict[str, object], BuildSource, str]:
    """Real compile/capture/preparation/source/build; storage/publication doubles only."""
    from types import SimpleNamespace
    from typing import cast
    from unittest.mock import AsyncMock, Mock
    from uuid import uuid4

    from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

    from fixtures.c03_records import EVALUATION_VALUE, records_seed
    from omnis.modules.instance.schemas import NativePrepareCommand
    from omnis.modules.runs import native_preparation as preparation
    from omnis.modules.runs.contract_inputs import ContractInputs
    from omnis.modules.runs.managed_admission import ManagedAdmission, validate_request
    from omnis.modules.runs.pure_probe import PureProbe
    from omnis.modules.settings.candidate_index import bind_catalog
    from omnis.modules.settings.candidate_material import capture
    from omnis.modules.settings.catalog_models import Profile
    from omnis.modules.settings.catalog_publication import PublicationCatalog
    from omnis.modules.settings.catalog_schema import dto
    from omnis.modules.settings.skill_catalog import compile_catalog
    from omnis.modules.tasks import managed_store
    from omnis.modules.tasks.execution_selection import selection_payload
    from test_managed_contract import ref
    from test_native_preparation import command

    seed = records_seed(tmp_path / "batch2")
    compiled = compile_catalog((seed.package,), seed.profile)
    retained, sources, _ = capture([str(seed.package)], str(seed.profile))
    compiled = bind_catalog(
        compiled,
        [
            {
                "package_key": r.package_key,
                "entity_kind": r.entity_kind,
                "key": r.key,
                "ref": {**ref(r.entity_kind), "digest": r.digest},
            }
            for r in compiled.refs
        ],
    )
    profile = dto(seed.profile.read_bytes(), Profile)
    candidate = records.envelope("candidate-snapshot", {})
    snapshot = records.envelope(
        "run-snapshot",
        {
            "snapshot_ref": records.reference(candidate),
            "publication_ref": ref("catalog-publication"),
            "profile_ref": ref("profile"),
            "package_refs": [
                b["ref"] for b in compiled.catalog_bindings if b["entity_kind"] == "package"
            ],
            "candidate_refs": [b["ref"] for b in compiled.catalog_bindings],
            "dependency_closure_refs": [],
            "dependency_artifact_refs": [],
            "dependency_closure_digest": "a" * 64,
            "created_by": seed.owner,
            "material_digest": compiled.material_digest,
            "resolved_index_digest": compiled.resolved_index_digest,
        },
    )
    selection = records.envelope(
        "execution-selection",
        selection_payload(
            records.reference(snapshot),
            profile.agent_recipes[0].key,
            profile,
            compiled,
        ),
    )
    group = str(uuid4())

    async def get(
        connection: object, owner: str, reference: object
    ) -> tuple[str, dict[str, object]]:
        assert owner == seed.owner
        return group, next(r for r in (candidate, selection) if records.reference(r) == reference)

    publications = SimpleNamespace(
        load_probe=AsyncMock(return_value=(group, snapshot, profile, compiled)),
        candidates=SimpleNamespace(
            sources=AsyncMock(
                return_value=(None, [records.envelope("source-draft", s) for s in sources])
            )
        ),
    )
    # No constructor/runtime/DB authority is claimed by these SOURCE storage doubles.
    producer = object.__new__(preparation.NativePreparation)
    producer.root = seed.root
    monkeypatch.setattr(producer, "publications", publications, raising=False)
    monkeypatch.setattr(records, "get", get)
    monkeypatch.setattr(preparation, "read_material", lambda *args: retained)
    connection = cast(AsyncConnection, Mock(spec=AsyncConnection))
    engine = cast(AsyncEngine, Mock(spec=AsyncEngine))
    _, bundle = await producer.build(
        connection,
        NativePrepareCommand.model_validate(
            {
                **command(),
                "owner_id": seed.owner,
                "selection_ref": records.reference(selection),
            }
        ),
    )
    prepared = {"bundle": bundle, "receipt_ref": ref("native-preparation-receipt")}
    monkeypatch.setattr(
        preparation, "reservation", AsyncMock(return_value=records.reference(bundle))
    )
    monkeypatch.setattr(preparation, "read_receipt", AsyncMock(return_value=prepared))
    monkeypatch.setattr(
        PureProbe, "_selection", AsyncMock(return_value=(group, selection, compiled))
    )
    monkeypatch.setattr(PublicationCatalog, "load_probe", publications.load_probe)
    consumer = ManagedAdmission(engine, seed.root)
    request = {
        "schema_version": 3,
        "owner_id": seed.owner,
        "command_id": str(uuid4()),
        "selection_ref": records.reference(selection),
        "preparation_command_id": str(uuid4()),
        "task_count": 2,
        "composition_version": 4,
    }
    source = await consumer._source(connection, seed.owner, request)
    assert source.preparation_bytes == len(canonical(bundle)) > 14000
    prefix = source.build(context_only=True, method_execution=True)
    run = next(r for r in prefix if r["kind"] == "managed-run")
    body = mapping(run["payload"])
    schema_ref, raw, path = source.input_schema()
    context = records.envelope(
        "contract-input-context",
        {
            "version": 2,
            "namespace": "RUN",
            "owner_id": seed.owner,
            "basis_ref": records.reference(run),
            "snapshot_ref": body["snapshot_ref"],
            "selection_ref": body["selection_ref"],
            "procedure_ref": source.procedure_ref,
            "mission_ref": body["mission_ref"],
            "focus_ref": body["focus_ref"],
            "schema_ref": schema_ref,
        },
    )
    item = produce_input(context, EVALUATION_VALUE, raw, str(uuid4()))
    prefix.extend([context, item])
    request.update(
        context_ref=records.reference(context),
        slot_values=[
            {
                "slot_name": "records",
                "refs": [records.reference(item)],
            }
        ],
    )
    validate_request(
        "prepare-method", {k: v for k, v in request.items() if k != "composition_version"}
    )
    monkeypatch.setattr(managed_store, "owned", AsyncMock(return_value=(run["id"], context)))
    monkeypatch.setattr(managed_store, "graph", AsyncMock(return_value=prefix))
    monkeypatch.setattr(managed_store, "get", AsyncMock(return_value=item))
    monkeypatch.setattr(ContractInputs, "current_source", AsyncMock(return_value=source))
    monkeypatch.setattr(
        connection,
        "execute",
        AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: None)),
    )
    graph = await consumer._build(connection, seed.owner, request)
    return graph, bundle, source, seed.owner


@pytest.mark.asyncio
async def test_batch2_complete_producer_stage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    graph, bundle, source, _ = await batch2_source(tmp_path, monkeypatch)
    stage = managed_composition.stage_payload(graph[-1], graph)
    assert len(canonical(graph)) + len(canonical(bundle)) <= 65536
    assert len(canonical(stage)) <= 32768
    entries = managed_contract.sequence(mapping(graph[-1]["payload"])["entries"])
    assert len(entries) == 2 and mapping(entries[0])["goal"] == mapping(entries[1])["goal"]
    assert len([r for r in graph if r["kind"] == "bound-procedure"]) == 1
    briefs = [r for r in graph if r["kind"] == "task-brief"]
    assert len({text(mapping(mapping(b["payload"])["header"])["task_id"]) for b in briefs}) == 2
    assert (
        len(
            {
                text(mapping(mapping(mapping(b["payload"])["header"])["result_schema_ref"])["id"])
                for b in briefs
            }
        )
        == 2
    )
    monkeypatch.syspath_prepend(
        str(Path(__file__).resolve().parents[2] / "integrations/hermes/src")
    )
    native = import_module("omnis_hermes.managed_admission_contract")
    assert native.validate_stage(stage) == graph[-1]
    from copy import deepcopy

    from omnis.modules.settings.candidate_material import digest

    single = deepcopy(stage)
    single["compositions"] = managed_contract.sequence(single["compositions"])[:1]
    manifest = mapping(single["manifest"])
    body = mapping(manifest["payload"])
    body["entries"] = managed_contract.sequence(body["entries"])[:1]
    manifest["payload"] = body
    manifest["digest"] = digest(canonical({k: v for k, v in manifest.items() if k != "digest"}))
    single["manifest"] = manifest
    single["record_pool"] = managed_composition.composition_pool(
        mapping(managed_contract.sequence(single["compositions"])[0])["payload"],
        single["record_pool"],
    )
    with pytest.raises(ValueError):
        native.validate_stage(single)
    method = import_module("omnis_hermes.contract_method")
    for i, brief in enumerate(briefs):
        assert method.assignment(canonical(stage), i)[0] == brief
    assert source.preparation_bytes == len(canonical(bundle))
    from omnis.modules.tasks import method_checker_identity

    old = records.envelope(
        "method-checker",
        {
            **method_checker_identity.descriptor(),
            "code_digest": "5a0f0d58bd76dee9985b7f127e034e85817fedf2a2f9a4ebd8e1bbad1a77a5b5",
        },
    )
    for empty in (False, True):
        assert (
            method_checker_identity.verify(
                old,
                pin=managed_composition.SINGLETON_COMPOSER_REVISION,
                receive_only=True,
                zero_predicates=empty,
            )
            == old
        )


@pytest.mark.asyncio
async def test_batch2_native_source_to_two_checks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import json
    import subprocess

    from omnis.modules.settings.catalog_schema import load_json
    from omnis.modules.tasks.method_checks import check_execution

    graph, bundle, source, owner = await batch2_source(tmp_path, monkeypatch)
    stage = managed_composition.stage_payload(graph[-1], graph)
    fixture = tmp_path / "batch2.json"
    fixture.write_bytes(
        canonical(
            {
                "stage": stage,
                "bundle": bundle,
                "metrics": {
                    "graph_bytes": len(canonical(graph)),
                    "preparation_bytes": len(canonical(bundle)),
                    "total_bytes": len(canonical(graph)) + len(canonical(bundle)),
                    "stage_bytes": len(canonical(stage)),
                },
            }
        )
    )
    home = tmp_path / "native-home"
    home.mkdir(mode=0o700)
    root = Path(__file__).resolve().parents[2]
    process = subprocess.run(
        [
            "/usr/bin/python3",
            "-I",
            "-B",
            str(root / "integrations/hermes/tests/contract_method_native_probe.py"),
            "/home/kali/.hermes/cache/scratch/contract-method-evidence/pinned",
            str(root / "integrations/hermes/upstream/managed-source"),
            str(root / "integrations/hermes/src"),
            str(home),
            str(fixture),
        ],
        capture_output=True,
        timeout=20,
        check=False,
    )
    (tmp_path / "native-source.log").write_bytes(process.stdout + process.stderr)
    assert process.returncode == 0, process.stderr.decode()[-5000:]
    back = json.loads(fixture.with_name("batch2-native-result.json").read_bytes())
    binding, final = back["binding"], back["final"]
    managed_contract.validate_final(final, graph[-1], binding)
    briefs = [r for r in graph if r["kind"] == "task-brief"]
    bound = next(r for r in graph if r["kind"] == "bound-procedure")
    original = next(r for r in graph if r["kind"] == "contract-case-records")
    checker = next(r for r in graph if r["kind"] == "method-checker")
    actions = [r for r in graph if r["kind"] == "action_definition"]
    schemas = {}
    for entry in source.bindings:
        if entry["entity_kind"] == "schema":
            matches = [
                b.path
                for b in source.manifest.file_bindings
                if b.entity_kind == "schema" and b.key == entry["key"]
            ]
            if matches:
                schemas[canonical(entry["ref"]).decode()] = mapping(
                    load_json(source.files[matches[0]])
                )
    prompt = next(r for r in graph if r["kind"] == "prompt-bundle")
    checks = [
        check_execution(
            brief,
            bound,
            binding,
            execution,
            checker,
            original,
            actions,
            schemas,
            owner,
            prompt_bundle=prompt,
            composition_version=4,
        )
        for brief, execution in zip(briefs, final["executions"], strict=True)
    ]
    assert [mapping(c["payload"])["status"] for c in checks] == ["COMPLETE", "COMPLETE"]
    assert [mapping(c["payload"])["brief_ref"] for c in checks] == [
        records.reference(b) for b in briefs
    ]
    from copy import deepcopy

    from jsonschema import Draft202012Validator

    from omnis.modules.settings.catalog_models import CatalogError

    for i, brief in enumerate(briefs):
        execution = final["executions"][i]
        schema_ref = mapping(mapping(brief["payload"])["header"])["result_schema_ref"]
        schema = next(r["payload"] for r in graph if records.reference(r) == schema_ref)
        validator = Draft202012Validator(mapping(schema))
        assert validator.is_valid(execution["records"][0]["payload"])
        assert not validator.is_valid(final["executions"][1 - i]["records"][0]["payload"])
        for attack in (
            "execution",
            "receipt",
            "artifact",
            "task",
            "attempt",
            "session",
            "root",
            "brief",
            "row",
        ):
            bad_execution, bad_binding = deepcopy(execution), deepcopy(binding)
            sibling = final["executions"][1 - i]
            if attack == "execution":
                bad_execution = deepcopy(sibling)
            elif attack == "receipt":
                bad_execution["records"][1] = sibling["records"][1]
            elif attack == "artifact":
                bad_execution["records"][-1] = sibling["records"][-1]
            else:
                body = bad_binding["payload"]
                row = body["entries"][i]
                if attack == "root":
                    body["native_root_id"] = row["native_child_id"]
                elif attack == "row":
                    body["entries"].reverse()
                else:
                    field = {
                        "task": "task_id",
                        "attempt": "attempt_id",
                        "session": "native_session_id",
                        "brief": "brief_ref",
                    }[attack]
                    row[field] = body["entries"][1 - i][field]
                bad_binding = records.envelope("runtime-binding", body)
            with pytest.raises(CatalogError):
                check_execution(
                    brief,
                    bound,
                    bad_binding,
                    bad_execution,
                    checker,
                    original,
                    actions,
                    schemas,
                    owner,
                    prompt_bundle=prompt,
                    composition_version=4,
                )


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
        "partial-requirement-full",
        "partial-requirement-prefix",
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
    if guard.startswith("partial-requirement-"):
        authored["preconditions"] = []
        requirements = [
            mapping(r) for r in managed_contract.sequence(authored["method_requirements"])
        ]
        requirements[0]["step_ids"] = ["normalize-operations", "build-map"]
        from copy import deepcopy

        requirements[0]["artifact_schema_refs"] = deepcopy(
            [
                *managed_contract.sequence(requirements[0]["artifact_schema_refs"]),
                *managed_contract.sequence(requirements[1]["artifact_schema_refs"]),
            ]
        )
        authored["method_requirements"] = requirements
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
    if empty and not guard.startswith(("evidence-", "partial-requirement-")):
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
            return_predicate_id=(
                "preserve-input-context"
                if guard == "partial-requirement-prefix"
                else "normalize-records"
                if guard.endswith("prefix")
                else None
            ),
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
        if guard.startswith("partial-requirement-"):
            requirement = mapping(managed_contract.sequence(resolved["method_requirements"])[0])
            steps = [mapping(s) for s in managed_contract.sequence(resolved["probe"])]
            assert requirement["step_ids"] == [s["id"] for s in steps]
            assert requirement["artifact_schema_refs"] == [s["output_schema_ref"] for s in steps]
            brief_body = mapping(brief["payload"])
            assert [
                mapping(r)["predicate_id"]
                for r in managed_contract.sequence(brief_body["done_when"])
            ] == ["normalize-records", "build-surface-map"]
            assert mapping(managed_contract.sequence(brief_body["return_when"])[0])[
                "predicate_id"
            ] == ("preserve-input-context" if guard.endswith("prefix") else "build-surface-map")
            stage = managed_composition.stage_payload(graph[-1], graph)
            adapter = str(Path(__file__).resolve().parents[2] / "integrations/hermes/src")
            sys.path.insert(0, adapter)
            try:
                assert (
                    import_module("omnis_hermes.managed_admission_contract").validate_stage(stage)
                    == graph[-1]
                )
            finally:
                sys.path.remove(adapter)
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
