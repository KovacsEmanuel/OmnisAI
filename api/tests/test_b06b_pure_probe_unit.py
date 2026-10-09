"""No-DB selection/PURE behavior; not PostgreSQL durability evidence."""

from dataclasses import replace
from importlib import import_module, util
from pathlib import Path
from uuid import uuid4

import pytest

from omnis.modules.settings import candidate_store as store
from omnis.modules.settings.catalog_models import DEFAULT_PREFERENCE, Profile
from omnis.modules.settings.catalog_schema import dto
from omnis.modules.settings.skill_catalog import compile_catalog

SOURCE = Path(__file__).parent / "fixtures/b06b_publication/source"


def test_public_probe_seam_and_strict_cli_before_database(
    tmp_path: Path, capsys: "pytest.CaptureFixture[str]", monkeypatch: "pytest.MonkeyPatch"
) -> None:
    from omnis.modules.runs import pure_probe
    from omnis.modules.settings.catalog_publication import PublicationCatalog
    from omnis.modules.settings.catalog_schema import canonical

    assert callable(getattr(PublicationCatalog, "load_probe", None)), "public probe loader missing"
    monkeypatch.delenv("OMNIS_DATABASE_URL", raising=False)
    request = tmp_path / "request.json"
    request.write_bytes(
        canonical({"schema_version": True, "owner_id": str(uuid4()), "receipt_ref": {}})
    )
    assert (
        pure_probe.main(
            ["readback", "--request", str(request), "--catalog-root", str(tmp_path / "absent")]
        )
        == 2
    )
    assert '"reason":"INVALID_REQUEST"' in capsys.readouterr().err
    assert not (tmp_path / "absent").exists()


@pytest.mark.parametrize(
    "field,value",
    [
        ("schema_version", True),
        ("schema_version", "1"),
        ("owner_id", "INVALID"),
        ("command_id", False),
        ("recipe_key", "publication-probe\n"),
        ("recipe_key", "Publication-Probe"),
        ("recipe_key", "x" * 129),
        ("effective", None),
        ("model", "ambient"),
        ("input", {"secret": "NO"}),
    ],
)
def test_select_rejects_overrides_and_invalid_authority(field: str, value: object) -> None:
    from omnis.modules.runs.pure_probe import validate_request
    from omnis.modules.settings.catalog_models import CatalogError

    request: dict[str, object] = {
        "schema_version": 1,
        "owner_id": str(uuid4()),
        "command_id": str(uuid4()),
        "snapshot_ref": store.reference(store.envelope("run-snapshot", {})),
        "recipe_key": "publication-probe",
    }
    assert validate_request("select", request) == request
    request[field] = value
    with pytest.raises(CatalogError, match="^INVALID_REQUEST$"):
        validate_request("select", request)


@pytest.mark.parametrize("input_object", [None, [], {"capture": "bad\x00"}, {"capture": "\ud800"}])
def test_execute_rejects_non_json_or_non_object_input(input_object: object) -> None:
    from omnis.modules.runs.pure_probe import validate_request
    from omnis.modules.settings.catalog_models import CatalogError

    with pytest.raises(CatalogError, match="^INVALID_REQUEST$"):
        validate_request(
            "execute",
            {
                "schema_version": 1,
                "owner_id": str(uuid4()),
                "command_id": str(uuid4()),
                "selection_ref": store.reference(store.envelope("execution-selection", {})),
                "input": input_object,
            },
        )


def test_executor_fingerprint_binds_evaluator_and_consumer_bytes() -> None:
    from omnis.modules.runs import pure_probe
    from omnis.modules.settings.candidate_catalog import EVALUATOR_REVISION
    from omnis.modules.settings.candidate_material import digest
    from omnis.modules.settings.catalog_schema import canonical

    root = Path(pure_probe.__file__).parents[1]
    expected = "sha256:" + digest(
        canonical(
            {
                "domain": "omnis-contract-probe-pure-v1",
                "evaluator_revision": EVALUATOR_REVISION,
                "files": {
                    name: digest((root / name).read_bytes())
                    for name in (
                        "runs/pure_probe.py",
                        "runs/plan_snapshot.py",
                        "tasks/execution_selection.py",
                        "settings/catalog_publication.py",
                        "settings/publication_models.py",
                        "settings/publication_store.py",
                    )
                },
            }
        )
    )
    assert pure_probe.EXECUTOR_REVISION == expected


def test_new_input_runs_the_real_pure_executor() -> None:
    name = "omnis.modules.runs.pure_probe"
    assert util.find_spec(name) is not None, "PURE probe consumer is missing"
    module = import_module(name)
    compiled = compile_catalog((SOURCE / "b06b-publish-contract",), SOURCE / "profile.yaml")
    output = module.execute_outputs(
        compiled, {"capture": '[{"method":"GET","path":"/new-input","status":200}]'}
    )
    assert len(output) == 3
    assert output[-1]["output"] == {
        "surface_map": [{"path": "/new-input", "methods": ["GET"], "operation_count": 1}]
    }
    from omnis.modules.settings.candidate_material import digest
    from omnis.modules.settings.catalog_schema import canonical

    for step, item in zip(compiled.steps, output, strict=True):
        assert item == {
            "step_id": step.id,
            "output": item["output"],
            "digest": digest(canonical(item["output"])),
        }


def test_selection_materializes_compiler_default_and_only_recipe_packages() -> None:
    name = "omnis.modules.tasks.execution_selection"
    assert util.find_spec(name) is not None, "ExecutionSelection consumer is missing"
    module = import_module(name)
    compiled = compile_catalog((SOURCE / "b06b-publish-contract",), SOURCE / "profile.yaml")
    profile = dto((SOURCE / "profile.yaml").read_bytes(), Profile)
    package: dict[str, object] = {
        "kind": "package",
        "id": str(uuid4()),
        "revision": 1,
        "digest": "a" * 64,
    }
    unrelated = {**package, "id": str(uuid4())}
    compiled = replace(
        compiled,
        catalog_bindings=(
            {
                "package_key": "b06b-publish-contract",
                "entity_kind": "package",
                "key": "b06b-publish-contract",
                "ref": package,
            },
            {"package_key": "other", "entity_kind": "package", "key": "other", "ref": unrelated},
        ),
        dependency_closure_refs=(unrelated,),
    )
    snapshot_ref = store.reference(store.envelope("run-snapshot", {}))
    selected = module.selection_payload(snapshot_ref, "publication-probe", profile, compiled)
    from omnis.modules.settings.catalog_models import CatalogError, ReleaseRef

    for wrong_key in ("unknown", "publication-probe\n"):
        with pytest.raises(CatalogError, match="^RECIPE_UNAVAILABLE$"):
            module.selection_payload(snapshot_ref, wrong_key, profile, compiled)
    with pytest.raises(CatalogError, match="^UNSUPPORTED_RECIPE_COUNT$"):
        module.selection_payload(
            snapshot_ref,
            "publication-probe",
            profile.model_copy(update={"agent_recipes": profile.agent_recipes * 2}),
            compiled,
        )
    with pytest.raises(CatalogError, match="^UNSUPPORTED_RECIPE$"):
        module.selection_payload(
            snapshot_ref,
            "publication-probe",
            profile,
            replace(compiled, verification_kind="SECURITY"),
        )
    external = profile.model_copy(
        update={
            "agent_recipes": (
                profile.agent_recipes[0].model_copy(
                    update={
                        "package_refs": (
                            ReleaseRef.model_validate({"kind": "RELEASE", "ref": package}),
                        )
                    }
                ),
            )
        }
    )
    assert (
        module.selection_payload(snapshot_ref, "publication-probe", external, compiled) == selected
    )
    assert selected == {
        "snapshot_ref": snapshot_ref,
        "recipe_key": "publication-probe",
        "selected_package_refs": [package],
        "requested": DEFAULT_PREFERENCE.model_dump(mode="json"),
        "effective": None,
        "resolution": "NO_MODEL",
        "reason": "CONTRACT_PROBE_PURE",
        "compatibility_receipt_refs": [],
    }
