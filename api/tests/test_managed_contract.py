"""Scoped domain contracts; no runtime/native integration is claimed here."""

import importlib
from copy import deepcopy
from types import ModuleType
from uuid import uuid4

import pytest

from fixtures.b06b_publication.consumer import mapping, sequence
from omnis.modules.settings import candidate_store as records
from omnis.modules.settings.catalog_models import CatalogError


def api() -> ModuleType:
    try:
        return importlib.import_module("omnis.modules.tasks.managed_contract")
    except ModuleNotFoundError:
        pytest.fail("managed admission contract consumer missing")


def ref(kind: str) -> dict[str, object]:
    return records.reference(records.envelope(kind, {}))


def manifest() -> dict[str, object]:
    return records.envelope(
        "launch-manifest",
        {
            "run_id": str(uuid4()),
            "selection_ref": ref("execution-selection"),
            "resolution": "NO_MODEL",
            "effective": None,
            "entries": [
                {
                    "batch_index": i,
                    "task_id": str(uuid4()),
                    "attempt_id": str(uuid4()),
                    "brief_ref": ref("task-brief"),
                    "goal": "Same inert support goal",
                }
                for i in range(2)
            ],
        },
    )


def stage(value: dict[str, object]) -> dict[str, object]:
    return {
        "protocol": "omnis-managed-admission-v1",
        "status": "STAGED",
        "ticket": str(uuid4()),
        "manifest_ref": records.reference(value),
        "native_root_id": "root-opaque",
        "entries": [
            {
                **{k: v for k, v in e.items() if k != "goal"},
                "native_child_id": f"child-{i}",
                "native_session_id": f"session-{i}",
            }
            for i, raw in enumerate(sequence(mapping(value["payload"])["entries"]))
            for e in [mapping(raw)]
        ],
    }


def authority() -> dict[str, object]:
    return {"instance_id": str(uuid4()), "owner": str(uuid4()), "epoch": 1, "generation": 0}


def test_build_inert_context_all_requirements_then_blocked_check() -> None:
    from datetime import UTC, datetime

    from fixtures.b06b_publication.consumer import SOURCE
    from omnis.modules.settings.catalog_models import Procedure
    from omnis.modules.settings.catalog_schema import dto
    from omnis.modules.settings.skill_catalog import compile_catalog

    m = api()
    assert hasattr(m, "build_records"), "durable task graph builder missing"
    procedure = dto(
        (SOURCE / "b06b-publish-contract/templates/procedures/publication-map.yaml").read_bytes(),
        Procedure,
    )
    compiled = compile_catalog((SOURCE / "b06b-publish-contract",), SOURCE / "profile.yaml")
    bindings = [
        {
            "package_key": q.package_key,
            "entity_kind": q.entity_kind,
            "key": q.key,
            "ref": ref(q.entity_kind),
        }
        for q in compiled.refs
    ]
    procedure_ref = next(b["ref"] for b in bindings if b["entity_kind"] == "procedure")
    selection = records.envelope(
        "execution-selection",
        {"snapshot_ref": ref("run-snapshot"), "selected_package_refs": [ref("package")]},
    )
    graph = m.build_records(
        selection,
        ref("native-preparation-receipt"),
        procedure_ref,
        procedure,
        bindings,
        "b06b-publish-contract",
        "RECON",
        2,
        datetime(2026, 10, 9, tzinfo=UTC),
    )
    briefs = [r for r in graph if r["kind"] == "task-brief"]
    assert len(briefs) == 2
    assert briefs[0]["payload"]["objective_summary"] == procedure.objective
    assert briefs[0]["payload"]["header"]["task_id"] != briefs[1]["payload"]["header"]["task_id"]
    for brief in briefs:
        bound_record = next(
            r
            for r in graph
            if r["id"] == brief["payload"]["procedure_bindings"][0]["bound_procedure_ref"]["id"]
        )
        assert hasattr(m, "validate_assignment"), "bound requirement completeness validator missing"
        m.validate_assignment(brief, bound_record)
        bad = deepcopy(brief["payload"])
        bad["method_plan"]["requirements"][0]["required"] = False
        with pytest.raises(CatalogError):
            m.validate_assignment(records.envelope("task-brief", bad), bound_record)
        body = brief["payload"]
        assert body["criterion_bindings"] == [] and "SUPPORT" in body["priority_reason"]
        assert len(body["method_plan"]["requirements"]) == len(procedure.method_requirements)
        result = m.blocked_result(brief)
        from jsonschema import Draft202012Validator

        schema_record = next(
            r for r in graph if r["id"] == body["header"]["result_schema_ref"]["id"]
        )
        assert "$schema" in schema_record["payload"], "result schema is not JSON Schema"
        Draft202012Validator.check_schema(schema_record["payload"])
        Draft202012Validator(schema_record["payload"]).validate(result["payload"])
        for key, value in [
            ("role", "REVIEWER"),
            ("allowed_capability_ids", ["target.io"]),
            ("assessment_mode", "invented"),
            ("validation_reserve", {"actions": True, "seconds": 0}),
        ]:
            bad_body = {**body, key: value}
            corrupt_brief = records.envelope("task-brief", bad_body)
            with pytest.raises(CatalogError):
                m.validate_brief(corrupt_brief)
        assert result["payload"]["status"] == "BLOCKED"
        assert all(r["state"] == "NOT_RUN" for r in result["payload"]["method_results"])
        checker = next(r for r in graph if r["kind"] == "method-checker")
        check = m.method_check(brief, result, records.reference(checker))
        assert check["payload"]["status"] == "INCOMPLETE"
        assert len(check["payload"]["gap_refs"]) == len(procedure.method_requirements)
        corrupt = deepcopy(result)
        corrupt["payload"]["header"]["brief_revision"] = True
        with pytest.raises(CatalogError):
            m.method_check(brief, corrupt, records.reference(checker))
    unsupported = procedure.model_copy(update={"preconditions": (object(),)})
    with pytest.raises(CatalogError, match="UNSUPPORTED"):
        m.build_records(
            selection,
            ref("native-preparation-receipt"),
            procedure_ref,
            unsupported,
            bindings,
            "b06b-publish-contract",
            "RECON",
            1,
            datetime(2026, 10, 9, tzinfo=UTC),
        )


def test_two_equal_goals_preserve_exact_distinct_native_mapping() -> None:
    m = api()
    value = manifest()
    staged = stage(value)
    checked = m.validate_stage(staged, value)
    assert checked == staged
    binding = m.binding_record(value, staged, str(uuid4()), authority())
    final = {
        **staged,
        "status": "BLOCKED",
        "reason": "NO_MODEL",
        "binding_ref": records.reference(binding),
    }
    assert m.validate_final(final, value, binding) == final
    for path, bad in [
        ("batch_index", True),
        ("task_id", str(uuid4())),
        ("native_child_id", "foreign"),
        ("brief_ref", ref("task-brief")),
    ]:
        corrupt = deepcopy(final)
        mapping(sequence(corrupt["entries"])[0])[path] = bad
        with pytest.raises(CatalogError):
            m.validate_final(corrupt, value, binding)
    corrupt = deepcopy(staged)
    mapping(sequence(corrupt["entries"])[1])["native_child_id"] = mapping(
        sequence(corrupt["entries"])[0]
    )["native_child_id"]
    with pytest.raises(CatalogError):
        m.validate_stage(corrupt, value)
    with pytest.raises(CatalogError):
        m.binding_record(value, staged, str(uuid4()), {**authority(), "epoch": True})
