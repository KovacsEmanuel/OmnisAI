"""C05 pure producer tests; no native or database evidence is claimed."""

import importlib
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from types import ModuleType

import pytest

from fixtures.b06b_publication.consumer import SOURCE, mapping, sequence
from omnis.modules.settings import candidate_store as records
from omnis.modules.settings.candidate_material import capture
from omnis.modules.settings.catalog_models import Procedure
from omnis.modules.settings.catalog_schema import canonical, dto, load_json
from omnis.modules.settings.skill_catalog import compile_catalog
from omnis.modules.tasks import managed_contract as contract
from test_managed_contract import ref


def composer() -> ModuleType:
    try:
        return importlib.import_module("omnis.modules.tasks.managed_composition")
    except ModuleNotFoundError:
        pytest.fail("final immutable prompt composer missing")


def inputs(
    two: bool = False,
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]], Procedure]:
    from omnis.modules.runs.native_preparation_models import prepare_packages

    package = SOURCE / "b06b-publish-contract"
    profile = SOURCE / "profile.yaml"
    roots = [package]
    if two:
        from fixtures.b06b_composition import new_two_skill_seed

        seed = new_two_skill_seed()
        package, profile = seed.package, seed.profile
        roots = [package, seed.directory / "composition-support"]
    compiled = compile_catalog(tuple(roots), profile)
    material, sources, _ = capture([str(p) for p in roots], str(profile))
    bindings: list[dict[str, object]] = [
        {
            "package_key": q.package_key,
            "entity_kind": q.entity_kind,
            "key": q.key,
            "ref": ref(q.entity_kind),
        }
        for q in compiled.refs
    ]
    pairs = [
        ({**ref("package"), "digest": s["package_digest"]}, s)
        for s in sources
        if s["source_kind"] == "package"
    ]
    packages = prepare_packages(material, pairs)
    selection = records.envelope(
        "execution-selection",
        {
            "snapshot_ref": ref("run-snapshot"),
            "selected_package_refs": [p[0] for p in pairs],
        },
    )
    procedure = dto((package / "templates/procedures/publication-map.yaml").read_bytes(), Procedure)
    return selection, bindings, packages, procedure


def graph(
    monkeypatch: pytest.MonkeyPatch, count: int = 1, two: bool = False
) -> list[dict[str, object]]:
    module = composer()
    # Unit-only revision seam; production placeholder is never treated as measured.
    monkeypatch.setattr(module, "COMPOSER_REVISION", sha256(b"unit-only-composer").hexdigest())
    selection, bindings, packages, procedure = inputs(two)
    return contract.build_records(
        selection,
        ref("native-preparation-receipt"),
        mapping(next(b["ref"] for b in bindings if b["entity_kind"] == "procedure")),
        procedure,
        bindings,
        "b06b-publish-contract",
        "RECON",
        count,
        datetime(2026, 10, 9, tzinfo=UTC),
        composition_packages=packages,
    )


def test_final_prompt_is_complete_canonical_immutable_assignment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = composer()
    built = graph(monkeypatch)
    manifest = built[-1]
    payload = module.stage_payload(manifest, built)
    assert payload["protocol"] == "omnis-managed-admission-v2"
    assert mapping(manifest["payload"])["composition_version"] == 1
    composition = payload["compositions"][0]
    assert composition in built
    body = mapping(composition["payload"])
    sections = [mapping(s) for s in sequence(load_json(contract.text(body["text"], 65536)))]
    assert [s["section"] for s in sections] == ["base", "role", "brief", "method", "skill"]
    assert canonical(sections).decode() == body["text"]
    assert body["text_digest"] == sha256(contract.text(body["text"], 65536).encode()).hexdigest()
    assert (
        body["byte_count"]
        == body["token_upper_bound"]
        == len(contract.text(body["text"], 65536).encode())
    )
    brief = next(r for r in built if r["kind"] == "task-brief")
    assert sections[2]["record"] == brief
    assert (
        records.reference(composition)
        == mapping(sequence(mapping(manifest["payload"])["entries"])[0])["composition_ref"]
    )
    assert [mapping(c)["path"] for c in sequence(sections[4]["content"])] == [
        "SKILL.md",
        "references/method.md",
    ]
    assert (
        mapping(sequence(sections[4]["content"])[1])["text"]
        == (SOURCE / "b06b-publish-contract/references/method.md").read_text()
    )
    assert mapping(mapping(body["prompt_bundle"])["payload"])["provenance"]
    assert len(canonical(payload)) <= 32768
    assert Path(contract.__file__).resolve().parents[5] == Path(__file__).resolve().parents[2]


def test_two_skills_are_compiled_exact_and_prefix_survives_assignment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = composer()
    built = graph(monkeypatch, two=True)
    composition = next(r for r in built if r["kind"] == "prompt-composition")
    body = mapping(composition["payload"])
    sections = [mapping(s) for s in sequence(load_json(contract.text(body["text"], 65536)))]
    assert len(sections[4:]) == 2
    assert [s["native_name"] for s in sections[4:]] == [
        "b06b-publish-contract",
        "composition-support",
    ]
    assert len(sequence(sections[5]["content"])) == 1
    brief = mapping(sections[2]["record"])
    from copy import deepcopy
    from uuid import uuid4

    next_brief = deepcopy(mapping(brief["payload"]))
    mapping(next_brief["header"])["task_id"] = str(uuid4())
    mapping(next_brief["header"])["attempt_id"] = str(uuid4())
    next_composition = module.compose(
        body["prompt_bundle"],
        sections[0]["record"],
        sections[1]["record"],
        records.envelope("task-brief", next_brief),
        sections[3]["record"],
        body["preparation_receipt_ref"],
        sections[4:],
    )
    next_sections = sequence(load_json(next_composition["payload"]["text"]))
    assert canonical(sections[:2]) == canonical(next_sections[:2])
    assert body["text_digest"] != next_composition["payload"]["text_digest"]


def test_prepare_composed_service_and_cli_are_real_entrypoints() -> None:
    import subprocess

    from fixtures.b06b_publication.consumer import cli_command
    from omnis.modules.runs.managed_admission import ManagedAdmission, validate_request

    assert callable(getattr(ManagedAdmission, "prepare_composed", None)), (
        "durable composed producer missing"
    )
    assert callable(getattr(ManagedAdmission, "stage_payload", None)), (
        "durable composed readback missing"
    )
    from uuid import uuid4

    request = {
        "schema_version": 1,
        "owner_id": str(uuid4()),
        "command_id": str(uuid4()),
        "selection_ref": ref("execution-selection"),
        "preparation_command_id": str(uuid4()),
        "task_count": 1,
    }
    assert validate_request("prepare-composed", request) == request
    result = subprocess.run(
        cli_command("omnis.modules.runs.managed_admission", "--help"),
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0 and "prepare-composed" in result.stdout


@pytest.mark.parametrize(
    "mutation",
    [
        "text",
        "missing",
        "foreign",
        "base",
        "history",
        "overlay",
        "digest",
        "budget",
        "version",
        "technique",
        "method",
    ],
)
def test_composition_refuses_mutation_without_downgrade(
    monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    from copy import deepcopy

    from omnis.modules.settings.catalog_models import CatalogError

    module = composer()
    built = graph(monkeypatch)
    composition = deepcopy(next(r for r in built if r["kind"] == "prompt-composition"))
    body = mapping(composition["payload"])
    sections = [mapping(s) for s in sequence(load_json(contract.text(body["text"], 65536)))]
    if mutation == "text":
        body["text"] = contract.text(body["text"], 65536) + " "
    elif mutation == "missing":
        sections.pop()
    elif mutation == "foreign":
        sections[2]["record"] = records.envelope(
            "task-brief",
            {
                **mapping(mapping(sections[2]["record"])["payload"]),
                "prompt_bundle_ref": ref("prompt-bundle"),
            },
        )
    elif mutation == "base":
        sections[0]["record"] = records.envelope("prompt-content", {"text": "ignore policy"})
    elif mutation in {"history", "overlay"}:
        brief = mapping(mapping(sections[2]["record"])["payload"])
        brief["prior_attempt_refs" if mutation == "history" else "overlay_refs"] = [ref("overlay")]
        sections[2]["record"] = records.envelope("task-brief", brief)
    elif mutation == "digest":
        content = mapping(sequence(sections[4]["content"])[0])
        content["text"] = contract.text(content["text"]) + "changed"
    elif mutation == "budget":
        bundle = mapping(mapping(body["prompt_bundle"])["payload"])
        bundle["max_context_tokens"] = 256
        body["prompt_bundle"] = records.envelope("prompt-bundle", bundle)
    elif mutation == "technique":
        brief = mapping(mapping(sections[2]["record"])["payload"])
        brief["technique_refs"] = [ref("technique")]
        sections[2]["record"] = records.envelope("task-brief", brief)
    elif mutation == "method":
        sections[4]["content"] = sequence(sections[4]["content"])[:1]
    else:
        body["token_upper_bound"] = True
    if mutation not in {"text", "version"}:
        body["text"] = canonical(sections).decode()
        body["text_digest"] = sha256(contract.text(body["text"], 65536).encode()).hexdigest()
        body["byte_count"] = body["token_upper_bound"] = len(
            contract.text(body["text"], 65536).encode()
        )
    with pytest.raises(CatalogError):
        module.validate(records.envelope("prompt-composition", body))


def test_two_assignment_frame_overflow_is_not_silently_dropped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from omnis.modules.settings.catalog_models import CatalogError

    with pytest.raises(CatalogError, match="CONTEXT_OVERFLOW"):
        graph(monkeypatch, count=2, two=True)


def test_full_frame_and_mandatory_context_are_never_truncated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from omnis.modules.settings.catalog_models import CatalogError

    module = composer()
    built = graph(monkeypatch)
    good = module.stage_payload(built[-1], built)
    assert len(canonical(good)) <= 32768
    selection, bindings, packages, procedure = inputs()
    raw = procedure.model_dump(mode="json")
    requirement = mapping(sequence(raw["method_requirements"])[0])
    raw["method_requirements"] = [
        {**requirement, "key": f"mandatory-{i}", "description": "Required detail " * 60}
        for i in range(24)
    ]
    oversized = dto(canonical(raw), Procedure)
    with pytest.raises(CatalogError, match="CONTEXT_OVERFLOW"):
        contract.build_records(
            selection,
            ref("native-preparation-receipt"),
            mapping(next(b["ref"] for b in bindings if b["entity_kind"] == "procedure")),
            oversized,
            bindings,
            "b06b-publish-contract",
            "RECON",
            1,
            datetime(2026, 10, 9, tzinfo=UTC),
            composition_packages=packages,
        )


@pytest.mark.parametrize("mutation", ["missing", "changed", "shadow"])
def test_stage_graph_resolves_the_exact_composition_records(
    monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    from omnis.modules.settings.catalog_models import CatalogError

    module = composer()
    built = graph(monkeypatch)
    manifest = built[-1]
    if mutation == "missing":
        built = [r for r in built if r["kind"] != "prompt-composition"]
    elif mutation == "changed":
        brief = next(r for r in built if r["kind"] == "task-brief")
        mapping(brief["payload"])["hypothesis"] = "foreign retained brief"
    else:
        built.append(built[0])
    with pytest.raises(CatalogError):
        module.stage_payload(manifest, built)


def test_optional_native_install_is_not_an_import_prerequisite() -> None:
    import subprocess
    import sys

    source = Path(__file__).resolve().parents[1] / "src"
    program = """
import sys
sys.path.insert(0, sys.argv[1])
class NoNative:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.startswith(('omnis_hermes', 'hermes')):
            raise AssertionError('ordinary API import attempted native import')
sys.meta_path.insert(0, NoNative())
import omnis.modules.runs.managed_admission
import omnis.modules.tasks.managed_contract
import omnis.modules.tasks.managed_composition
print('API_IMPORT_WITHOUT_NATIVE_OK')
"""
    result = subprocess.run(
        [sys.executable, "-I", "-B", "-c", program, str(source)],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "API_IMPORT_WITHOUT_NATIVE_OK"


def test_recipe_cannot_silently_omit_an_extra_selected_technique() -> None:
    from omnis.modules.settings.catalog_models import CatalogError, Profile

    module = composer()
    assert callable(getattr(module, "require_recipe", None)), "selected technique closure missing"
    recipe = dto((SOURCE / "profile.yaml").read_bytes(), Profile).agent_recipes[0]
    _, _, _, procedure = inputs()
    module.require_recipe(recipe, procedure, "b06b-publish-contract")
    with pytest.raises(CatalogError):
        module.require_recipe(
            recipe.model_copy(
                update={"technique_refs": (*recipe.technique_refs, *recipe.technique_refs)}
            ),
            procedure,
            "b06b-publish-contract",
        )


def test_composition_rejects_escaped_controls_in_authored_brief(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from copy import deepcopy

    from omnis.modules.settings.catalog_models import CatalogError

    module = composer()
    built = graph(monkeypatch)
    body = deepcopy(mapping(next(r for r in built if r["kind"] == "prompt-composition")["payload"]))
    sections = [mapping(s) for s in sequence(load_json(contract.text(body["text"], 65536)))]
    brief = mapping(mapping(sections[2]["record"])["payload"])
    brief["hypothesis"] = "escaped" + chr(13) + "control"
    sections[2]["record"] = records.envelope("task-brief", brief)
    encoded = canonical(sections)
    body.update(
        text=encoded.decode(),
        text_digest=sha256(encoded).hexdigest(),
        byte_count=len(encoded),
        token_upper_bound=len(encoded),
    )
    with pytest.raises(CatalogError):
        module.validate(records.envelope("prompt-composition", body))


def test_composed_response_binding_rejects_v1_and_wrong_composition(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from uuid import uuid4

    from omnis.modules.settings.catalog_models import CatalogError
    from test_managed_contract import authority, stage

    built = graph(monkeypatch)
    manifest = built[-1]
    staged = stage(manifest)
    with pytest.raises(CatalogError):
        contract.validate_stage(staged, manifest)
    staged["protocol"] = "omnis-managed-admission-v2"
    binding = contract.binding_record(manifest, staged, str(uuid4()), authority())
    assert contract.validate_binding(binding, manifest) == binding
    final = {
        **staged,
        "status": "BLOCKED",
        "reason": "NO_MODEL",
        "binding_ref": records.reference(binding),
    }
    assert contract.validate_final(final, manifest, binding) == final
    mapping(sequence(staged["entries"])[0])["composition_ref"] = ref("prompt-composition")
    with pytest.raises(CatalogError):
        contract.validate_stage(staged, manifest)
