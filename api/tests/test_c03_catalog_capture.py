"""C03 bounded source compiler and genuine PURE behavior."""

from dataclasses import replace
from pathlib import Path

import pytest

from fixtures.b06a_durable.consumer import copy_seed
from fixtures.c03_capture import CAPTURE_SLOT, capture_seed
from omnis.modules.settings.catalog_models import CaseSlot, CatalogError
from omnis.modules.settings.skill_catalog import compile_catalog, evaluate_pure


def test_capture_source_compiles_first_slot_binding(tmp_path: Path) -> None:
    seed = capture_seed(tmp_path / "capture")
    compiled = compile_catalog((seed.package,), seed.profile)
    assert [slot.model_dump(mode="json") for slot in compiled.slots] == [CAPTURE_SLOT]
    assert compiled.steps[0].bindings[0].selector == "capture"
    with pytest.raises(CatalogError, match="UNBOUND_SLOT"):
        evaluate_pure(compiled, {"capture": "GET /synthetic 200"})


def test_admitted_material_drives_actual_pure_outputs(tmp_path: Path) -> None:
    import importlib.util

    assert importlib.util.find_spec("omnis.modules.tasks.contract_case_input") is not None, (
        "C03 validated material producer missing"
    )
    from uuid import uuid4

    from omnis.modules.settings import candidate_store as store
    from omnis.modules.tasks.contract_case_input import material_section, produce_input

    seed = capture_seed(tmp_path / "admitted", extra_requirement=True)
    compiled = compile_catalog((seed.package,), seed.profile)
    # Pure-helper fixture only, not service admission authority; PG proves persisted authority.
    owner = str(uuid4())

    def reference(kind: str) -> dict[str, object]:
        return store.reference(store.envelope(kind, {}))

    schema_ref = reference("schema")
    context = store.envelope(
        "contract-input-context",
        {
            "version": 1,
            "namespace": "PACKAGE_EVAL",
            "owner_id": owner,
            "basis_ref": reference("evaluation-admission"),
            "snapshot_ref": reference("candidate-snapshot"),
            "procedure_ref": reference("procedure"),
            "schema_ref": schema_ref,
            "selection_ref": None,
            "mission_ref": None,
            "focus_ref": None,
        },
    )
    value = {
        "capture": '[{"method":"GET","path":"/c03","status":200},{"method":"POST","path":"/c03","status":201}]'
    }
    input_record = produce_input(context, value, compiled.input_schema, str(uuid4()))
    material = material_section(
        context,
        input_record,
        schema_ref,
        compiled.input_schema,
        schema_path="templates/schemas/capture.schema.json",
    )
    before = (seed.package / "templates/procedures/map-capture.yaml").read_bytes()
    actual = evaluate_pure(compiled, None, capture_material=material)
    assert (seed.package / "templates/procedures/map-capture.yaml").read_bytes() == before
    assert compiled.slots and compiled.steps[0].bindings[0].source_ref.kind == "CASE_SLOT_REF"
    assert actual.outputs[-1] == {
        "surface_map": [{"path": "/c03", "methods": ["GET", "POST"], "operation_count": 2}]
    }
    with pytest.raises(CatalogError):
        evaluate_pure(compiled, value, capture_material=material)


def test_private_service_exposes_capture_admission_before_db() -> None:
    from omnis.modules.settings.candidate_catalog import CandidateCatalog

    assert callable(getattr(CandidateCatalog, "admit_evaluation_capture", None)), (
        "Persistent PACKAGE_EVAL admission is missing"
    )


def test_capture_admission_record_rejects_nested_bool_revision() -> None:
    from uuid import uuid4

    from omnis.modules.settings import candidate_catalog as module
    from omnis.modules.settings import candidate_store as store

    assert callable(getattr(module, "check_capture_admission", None)), (
        "Strict admission record checker missing"
    )
    expected = {
        "version": 1,
        "namespace": "PACKAGE_EVAL",
        "owner_id": str(uuid4()),
        "snapshot_ref": store.reference(store.envelope("candidate-snapshot", {})),
        "procedure_ref": store.reference(store.envelope("procedure", {})),
        "schema_ref": store.reference(store.envelope("schema", {})),
        "material_digest": "a" * 64,
        "resolved_index_digest": "b" * 64,
        "compiler_revision": module.COMPILER_REVISION,
    }
    module.check_capture_admission(store.envelope("evaluation-admission", expected), expected)
    from copy import deepcopy

    bad = deepcopy(expected)
    ref = bad["snapshot_ref"]
    assert isinstance(ref, dict)
    ref["revision"] = True
    with pytest.raises(CatalogError):
        module.check_capture_admission(store.envelope("evaluation-admission", bad), expected)


def test_private_capture_admission_has_explicit_request_version() -> None:
    from uuid import uuid4

    from omnis.modules.settings import candidate_store as store
    from omnis.modules.settings.candidate_catalog import validate_request

    value = {
        "schema_version": 2,
        "owner_id": str(uuid4()),
        "command_id": str(uuid4()),
        "snapshot_ref": store.reference(store.envelope("candidate-snapshot", {})),
        "value": {"capture": "GET /c03 200"},
    }
    assert validate_request("admit-evaluation-capture", value) == value


def test_no_model_selection_accepts_only_exact_capture_subset(tmp_path: Path) -> None:
    from omnis.modules.settings import candidate_store as store
    from omnis.modules.settings.candidate_index import bind_catalog
    from omnis.modules.settings.catalog_models import Profile
    from omnis.modules.settings.catalog_schema import dto
    from omnis.modules.tasks.execution_selection import selection_payload

    seed = capture_seed(tmp_path / "selected")
    compiled = compile_catalog((seed.package,), seed.profile)
    bindings: list[dict[str, object]] = []
    for ref in compiled.refs:
        exact = store.reference(store.envelope(ref.entity_kind, {}))
        exact["digest"] = ref.digest
        bindings.append(
            {
                "package_key": ref.package_key,
                "entity_kind": ref.entity_kind,
                "key": ref.key,
                "ref": exact,
            }
        )
    compiled = bind_catalog(compiled, bindings)
    profile = dto(seed.profile.read_bytes(), Profile)
    selected = selection_payload(
        store.reference(store.envelope("run-snapshot", {})),
        profile.agent_recipes[0].key,
        profile,
        compiled,
    )
    assert selected["resolution"] == "NO_MODEL"
    bad = replace(
        compiled,
        slots=(
            CaseSlot(name="other", expected_kind="contract-case-input", min_items=1, max_items=1),
        ),
    )
    with pytest.raises(CatalogError):
        selection_payload(
            store.reference(store.envelope("run-snapshot", {})),
            profile.agent_recipes[0].key,
            profile,
            bad,
        )


def test_evaluator_refuses_non_previous_step_output(tmp_path: Path) -> None:
    from omnis.modules.settings.catalog_models import Binding, StepOutputRef

    seed = copy_seed(tmp_path / "cross-step")
    compiled = compile_catalog((seed.package,), seed.profile)
    binding = Binding(
        name="operations",
        source_ref=StepOutputRef(
            kind="STEP_OUTPUT", step_id=compiled.steps[0].id, output_name="records"
        ),
        selector=None,
    )
    forged = replace(
        compiled, steps=(*compiled.steps[:2], replace(compiled.steps[2], bindings=(binding,)))
    )
    with pytest.raises(CatalogError, match="MISSING_STEP_OUTPUT"):
        evaluate_pure(forged, {"capture": "[]"})


def test_capture_dependency_refused_before_release_replay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from omnis.modules.settings import skill_catalog
    from omnis.modules.settings.candidate_resolution import ReleasePackage

    seed = capture_seed(tmp_path / "no-release-replay")
    compiled = compile_catalog((seed.package,), seed.profile)
    # Isolate the post-STATIC boundary: no release/admission authority is minted.
    # An empty, unqualified descriptor must never reach artifact() or PURE replay.
    monkeypatch.setattr(skill_catalog, "_compile_catalog", lambda *args, **kwargs: compiled)
    with pytest.raises(CatalogError, match="UNSUPPORTED_CAPTURE_DEPENDENCY"):
        skill_catalog.compile_catalog(
            (seed.package,), seed.profile, dependencies=(ReleasePackage(tmp_path, b"", b""),)
        )


def test_raw_input_cannot_bind_declared_slot(tmp_path: Path) -> None:
    seed = copy_seed(tmp_path / "legacy")
    compiled = compile_catalog((seed.package,), seed.profile)
    unbound = replace(compiled, slots=(CaseSlot.model_validate(CAPTURE_SLOT),))
    with pytest.raises(CatalogError, match="UNBOUND_SLOT"):
        evaluate_pure(unbound, {"capture": "GET /synthetic 200"})
