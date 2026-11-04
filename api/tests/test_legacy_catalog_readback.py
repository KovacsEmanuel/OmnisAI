"""SOURCE storage/dependency joins only; real retained compiler, no native/PG IO."""

from pathlib import Path
from uuid import uuid4

import pytest
import yaml
from sqlalchemy.ext.asyncio import AsyncEngine

from omnis.modules.settings import candidate_catalog as candidates
from omnis.modules.settings import candidate_store as store
from omnis.modules.settings import skill_catalog
from omnis.modules.settings.candidate_index import resolved_index
from omnis.modules.settings.candidate_resolution import ReleasePackage
from omnis.modules.settings.catalog_models import CatalogError, CompiledCatalog, PureEvaluation
from omnis.modules.settings.catalog_schema import canonical
from test_agent_core_publication import storage_seam as storage_seam
from test_b06a_release_product import binding, external, seed


@pytest.mark.asyncio
@pytest.mark.parametrize("legacy", [False, True])
async def test_retained_release_closure_readback_never_reruns_evaluator(
    storage_seam: AsyncEngine,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    legacy: bool,
) -> None:
    instance = candidates.CandidateCatalog(storage_seam, tmp_path / "catalog")
    package, profile = seed(tmp_path, "external")
    owner = str(uuid4())

    def command(**values: object) -> dict[str, object]:
        return {"schema_version": 1, "owner_id": owner, "command_id": str(uuid4()), **values}

    with monkeypatch.context() as revisions:
        if legacy:
            revisions.setattr(candidates, "COMPILER_REVISION", candidates.LEGACY_COMPILER_REVISION)
            revisions.setattr(
                candidates, "EVALUATOR_REVISION", candidates.LEGACY_EVALUATOR_REVISION
            )
        dependency = external(instance.root, package, profile)
        local, local_profile = seed(tmp_path, "local")
        manifest_path = local / "omnis.yaml"
        manifest = yaml.safe_load(manifest_path.read_bytes())
        manifest["input_schema_ref"] = {
            "kind": "RELEASE",
            "ref": binding(dependency, "schema", "capture"),
        }
        manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False))

        async def dependency_join(*args: object, **kwargs: object) -> tuple[ReleasePackage, ...]:
            return (dependency,)

        monkeypatch.setattr(candidates, "load_dependencies", dependency_join)
        captured = await instance.dispatch(
            "capture",
            command(author_kind="IMPORT", packages=[str(local)], profile=str(local_profile)),
        )
        source = {key: captured[key] for key in ("draft_ref", "source_draft_refs")}
        reviewed = await instance.dispatch("review", command(**source))
        assert reviewed["status"] == "STATIC_PASS"
        frozen = await instance.dispatch(
            "freeze", command(**source, technical_review_ref=reviewed["technical_review_ref"])
        )
        snapshot_ref = candidates.valid_ref(frozen["snapshot_ref"])
        evaluation_request = command(
            snapshot_ref=snapshot_ref, evaluation_kind="PURE", input={"capture": "[]"}
        )
        evaluated = await instance.dispatch("evaluate", evaluation_request)
        assert evaluated["status"] == "PURE_PASS"
        read_request = {"schema_version": 1, "owner_id": owner, "snapshot_ref": snapshot_ref}
        before = await instance.dispatch("readback", read_request)
    before_bytes = canonical(before)
    files_before = {str(p): p.read_bytes() for p in instance.root.rglob("*") if p.is_file()}
    calls: list[object] = []
    real_evaluate = skill_catalog.evaluate_pure

    def no_evaluation(*args: object, **kwargs: object) -> None:
        calls.append(args)
        raise AssertionError("retained closure dispatched dependency PURE")

    with monkeypatch.context() as sinks:
        sinks.setattr(skill_catalog, "evaluate_pure", no_evaluation)
        sinks.setattr(candidates, "evaluate_pure", no_evaluation)
        sinks.setattr(store, "put", no_evaluation)
        sinks.setattr(store, "complete", no_evaluation)
        after = await instance.dispatch("readback", read_request)
        assert before_bytes == canonical(after)
        assert await instance.dispatch("evaluate", evaluation_request) == evaluated
        async with storage_seam.connect() as connection:
            _, records = await instance.sources(connection, owner, source)
            index = before["resolved_index"]
            refs = reviewed["candidate_refs"]
            assert isinstance(index, dict) and isinstance(refs, list)
            if legacy:
                # The same closure cannot become new executable qualification.
                with pytest.raises(CatalogError, match="^RELEASE_UNQUALIFIED$"):
                    await instance.compile_pinned(
                        connection,
                        owner,
                        instance.root / "candidates" / str(snapshot_ref["id"]),
                        records,
                        [candidates.valid_ref(r) for r in refs],
                        index,
                    )
    assert not calls
    assert files_before == {str(p): p.read_bytes() for p in instance.root.rglob("*") if p.is_file()}

    if not legacy:

        def observed_evaluate(compiled: CompiledCatalog, value: object) -> PureEvaluation:
            calls.append(value)
            return real_evaluate(compiled, value)

        monkeypatch.setattr(skill_catalog, "evaluate_pure", observed_evaluate)
        async with storage_seam.connect() as connection:
            qualified = await instance.compile_pinned(
                connection,
                owner,
                instance.root / "candidates" / str(snapshot_ref["id"]),
                records,
                [candidates.valid_ref(r) for r in refs],
                index,
            )
        assert resolved_index(qualified) == index
        assert calls == [{"capture": '[{"method":"GET","path":"/synthetic","status":200}]'}]


@pytest.mark.asyncio
@pytest.mark.parametrize("legacy", [False, True])
async def test_evaluation_admission_replays_legacy_but_denies_new_input(
    storage_seam: AsyncEngine,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    legacy: bool,
) -> None:
    from fixtures.c03_capture import capture_seed
    from omnis.modules.settings import candidate_store as store

    fixture = capture_seed(tmp_path / "source")
    instance = candidates.CandidateCatalog(storage_seam, tmp_path / "catalog")
    owner = str(uuid4())

    def command(**values: object) -> dict[str, object]:
        return {"schema_version": 1, "owner_id": owner, "command_id": str(uuid4()), **values}

    with monkeypatch.context() as revisions:
        if legacy:
            revisions.setattr(candidates, "COMPILER_REVISION", candidates.LEGACY_COMPILER_REVISION)
            revisions.setattr(
                candidates, "EVALUATOR_REVISION", candidates.LEGACY_EVALUATOR_REVISION
            )
        captured = await instance.dispatch(
            "capture",
            command(
                author_kind="IMPORT", packages=[str(fixture.package)], profile=str(fixture.profile)
            ),
        )
        source = {key: captured[key] for key in ("draft_ref", "source_draft_refs")}
        reviewed = await instance.dispatch("review", command(**source))
        frozen = await instance.dispatch(
            "freeze", command(**source, technical_review_ref=reviewed["technical_review_ref"])
        )
        request = command(
            schema_version=2, snapshot_ref=frozen["snapshot_ref"], value={"capture": "[]"}
        )
        admitted = await instance.dispatch("admit-evaluation-capture", request)

    def no_write(*args: object, **kwargs: object) -> None:
        raise AssertionError("legacy input admission reached write sink")

    with monkeypatch.context() as sinks:
        sinks.setattr(store, "put", no_write)
        sinks.setattr(store, "complete", no_write)
        assert await instance.dispatch("admit-evaluation-capture", request) == admitted
        if legacy:
            with pytest.raises(CatalogError, match="^LEGACY_READ_ONLY$"):
                await instance.dispatch(
                    "admit-evaluation-capture", {**request, "command_id": str(uuid4())}
                )
    if not legacy:
        assert (
            await instance.dispatch(
                "admit-evaluation-capture", {**request, "command_id": str(uuid4())}
            )
            != admitted
        )


@pytest.mark.parametrize(
    "mutation",
    [
        "compiler",
        "evaluator",
        "output_type",
        "output_count",
        "output_schema",
        "canonical",
        "limit",
        "input",
    ],
)
def test_retained_release_validation_remains_strict_without_execution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    from dataclasses import replace

    from omnis.modules.settings import candidate_store as store
    from omnis.modules.settings.candidate_material import digest, private_root
    from omnis.modules.settings.catalog_schema import load_json

    root = private_root(tmp_path / "catalog")
    package, profile = seed(tmp_path, "external")
    dependency = external(root, package, profile)
    local, local_profile = seed(tmp_path, "local")
    path = local / "omnis.yaml"
    manifest = yaml.safe_load(path.read_bytes())
    manifest["input_schema_ref"] = {
        "kind": "RELEASE",
        "ref": binding(dependency, "schema", "capture"),
    }
    path.write_text(yaml.safe_dump(manifest, sort_keys=False))
    qualification = store.checked(load_json(dependency.qualification_json))
    data = candidates.payload(qualification)
    outputs = data["outputs"]
    assert isinstance(outputs, list)
    if mutation == "compiler":
        data["compiler_revision"] = candidates.LEGACY_COMPILER_REVISION
    elif mutation == "evaluator":
        data["evaluator_revision"] = "sha256:" + "0" * 64
    elif mutation == "output_type":
        outputs[0] = {}
    elif mutation == "output_count":
        outputs.pop()
    elif mutation == "output_schema":
        outputs[-1] = "{}"
    elif mutation == "canonical":
        outputs[0] = " " + str(outputs[0])
    elif mutation == "limit":
        outputs[0] = " " * 65536
    else:
        data["pure_input"] = {"wrong": "input"}
    qualification["digest"] = digest(
        canonical({k: v for k, v in qualification.items() if k != "digest"})
    )
    artifact = store.checked(load_json(dependency.artifact_json))
    candidates.payload(artifact)["qualification_ref"] = store.reference(qualification)
    artifact["digest"] = digest(canonical({k: v for k, v in artifact.items() if k != "digest"}))
    forged = replace(
        dependency, artifact_json=canonical(artifact), qualification_json=canonical(qualification)
    )

    def no_evaluation(*args: object, **kwargs: object) -> None:
        raise AssertionError("retained verification dispatched PURE")

    monkeypatch.setattr(skill_catalog, "evaluate_pure", no_evaluation)
    skill_catalog.compile_catalog(
        (local,), local_profile, dependencies=(dependency,), read_only=True
    )
    with pytest.raises(CatalogError, match="^RELEASE_UNQUALIFIED$"):
        skill_catalog.compile_catalog(
            (local,), local_profile, dependencies=(forged,), read_only=True
        )
