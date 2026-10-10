"""Content identity probes; no PostgreSQL integration is claimed."""

import hashlib
import json
from pathlib import Path
from typing import Self
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from fixtures.b06a.consumer import CatalogSeed
from fixtures.b06a.consumer import seed as seed
from omnis.modules.settings import candidate_catalog as catalog
from omnis.modules.settings import candidate_store as store
from omnis.modules.settings.candidate_index import INDEX_FILE, compile_material, resolved_index
from omnis.modules.settings.candidate_material import capture, finalize, private_root
from omnis.modules.settings.catalog_models import CatalogError, CompiledCatalog
from omnis.modules.settings.catalog_schema import canonical
from omnis.modules.settings.skill_catalog import read_file

DEPENDENCIES = (
    "settings/candidate_catalog.py",
    "settings/candidate_index.py",
    "settings/candidate_material.py",
    "settings/candidate_store.py",
    "settings/candidate_resolution.py",
    "settings/catalog_models.py",
    "settings/catalog_schema.py",
    "settings/skill_catalog.py",
    "tasks/module_registry.py",
    "tasks/contract_case_input.py",
)


def expected_revision(domain: str, root: Path) -> str:
    # Independent oracle: exact file bytes, relative labels, canonical JSON.
    manifest = {
        "domain": domain,
        "files": {
            name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in DEPENDENCIES
        },
    }
    raw = json.dumps(
        manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def test_compiler_revision_identifies_actual_trusted_behavior_bytes() -> None:
    assert catalog.COMPILER_REVISION == expected_revision(
        "omnis-candidate-compiler-v1", Path(catalog.__file__).parent.parent
    )


class ReceiptRows:
    def __init__(self, records: list[dict[str, object]]) -> None:
        self.records = records

    def scalars(self) -> Self:
        return self

    def all(self) -> list[dict[str, object]]:
        return self.records


@pytest.mark.asyncio
async def test_evaluation_revision_and_stale_readback_storage_seam(
    seed: CatalogSeed,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Only storage/authority seams are replaced: compilation, handlers, envelopes,
    # material finalization and receipt readback all execute real product code.
    # This is NOT PostgreSQL, reservation or transaction integration evidence.
    instance = object.__new__(catalog.CandidateCatalog)
    instance.root = private_root(seed.directory / "catalog")
    owner, group = str(uuid4()), str(uuid4())
    material, sources, material_digest = capture([str(seed.package)], str(seed.profile))
    for source in sources:
        source["material_digest"] = material_digest
    draft_dir = finalize(instance.root, "drafts", group, material)
    compiled = compile_material(draft_dir, sources)
    index = resolved_index(compiled)
    profile_ref = store.reference(store.envelope("profile", {}))
    source_records = [store.envelope("source-draft", s) for s in sources]
    review = store.envelope(
        "technical-review",
        {"resolved_index": index, "candidate_refs": [profile_ref], "dependency_closure_refs": []},
    )
    snapshot = store.envelope(
        "candidate-snapshot",
        {
            "draft_ref": store.reference(source_records[0]),
            "source_draft_refs": [store.reference(r) for r in source_records],
            "material_digest": compiled.material_digest,
            "resolved_index_digest": compiled.resolved_index_digest,
            "candidate_refs": [profile_ref],
            "dependency_closure_refs": [],
            "profile_ref": profile_ref,
            "compiler_revision": catalog.COMPILER_REVISION,
            "technical_review_ref": store.reference(review),
            "created_by": owner,
        },
    )
    material[INDEX_FILE] = canonical(index)
    finalize(instance.root, "candidates", str(snapshot["id"]), material)
    records = {str(snapshot["id"]): snapshot}

    async def get(
        connection: AsyncConnection, who: str, ref: dict[str, object]
    ) -> tuple[str, dict[str, object]]:
        assert who == owner
        record = store.checked(records[str(ref["id"])])
        assert store.reference(record) == ref
        return group, record

    async def put(
        connection: AsyncConnection, who: str, selected_group: str, record: dict[str, object]
    ) -> None:
        assert who == owner and selected_group == group
        records[str(record["id"])] = store.checked(record)

    async def selected_sources(
        self: catalog.CandidateCatalog,
        connection: AsyncConnection,
        who: str,
        value: dict[str, object],
    ) -> tuple[str, list[dict[str, object]]]:
        return group, source_records

    async def selected_review(
        self: catalog.CandidateCatalog,
        connection: AsyncConnection,
        who: str,
        selected_group: str,
        value: dict[str, object],
        selected: list[dict[str, object]],
    ) -> dict[str, object]:
        return review

    async def selected_compile(
        self: catalog.CandidateCatalog,
        connection: AsyncConnection,
        who: str,
        directory: Path,
        selected: list[dict[str, object]],
        refs: list[dict[str, object]],
        selected_index: dict[str, object] | None = None,
    ) -> CompiledCatalog:
        # Extend only the existing storage seam to the new reservation/dependency
        # join. Real compiler/material/handler behavior remains under test here;
        # actual DB bindings and RELEASE authority are proved in the PG tests.
        assert who == owner and selected == source_records and refs == [profile_ref]
        assert selected_index == index
        return compile_material(directory, sources)

    async def execute(
        self: AsyncConnection, statement: object, parameters: object = None
    ) -> ReceiptRows:
        return ReceiptRows([r for r in records.values() if r["kind"] == "evaluation-receipt"])

    monkeypatch.setattr(store, "get", get)
    monkeypatch.setattr(store, "put", put)
    monkeypatch.setattr(catalog.CandidateCatalog, "sources", selected_sources)
    monkeypatch.setattr(catalog.CandidateCatalog, "review_record", selected_review)
    monkeypatch.setattr(catalog.CandidateCatalog, "compile_pinned", selected_compile)
    monkeypatch.setattr(AsyncConnection, "execute", execute)
    connection = object.__new__(AsyncConnection)  # No socket/engine/DB is constructed.
    ref = store.reference(snapshot)
    result = await instance.evaluate(
        connection,
        owner,
        {
            "schema_version": 1,
            "snapshot_ref": ref,
            "evaluation_kind": "PURE",
            "input": {"capture": "[]"},
        },
    )
    evaluation = result["evaluation"]
    assert isinstance(evaluation, dict)
    receipt = catalog.payload(evaluation)
    assert receipt["evaluator_revision"] == expected_revision(
        "omnis-candidate-evaluator-v1", Path(catalog.__file__).parent.parent
    )
    assert result["status"] == "PURE_PASS"
    evaluations = (await instance.snapshot_readback(connection, owner, ref))["evaluations"]
    assert isinstance(evaluations, list) and len(evaluations) == 1
    monkeypatch.setattr(catalog, "EVALUATOR_REVISION", "sha256:" + "0" * 64)
    with pytest.raises(CatalogError, match="SNAPSHOT_MISMATCH"):
        await instance.snapshot_readback(connection, owner, ref)
    monkeypatch.setattr(catalog, "EVALUATOR_REVISION", receipt["evaluator_revision"])
    monkeypatch.setattr(catalog, "COMPILER_REVISION", "sha256:" + "0" * 64)
    with pytest.raises(CatalogError, match="SNAPSHOT_MISMATCH"):
        await instance.snapshot_readback(connection, owner, ref)


@pytest.mark.parametrize("dependency", DEPENDENCIES)
@pytest.mark.parametrize("domain", ["omnis-candidate-compiler-v1", "omnis-candidate-evaluator-v1"])
def test_each_dependency_changes_identity_delegated_read_seam(
    dependency: str,
    domain: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = Path(catalog.__file__).parent.parent
    before = catalog.behavior_revision(domain)
    real_read = read_file
    reads: list[str] = []

    def changed_read(path: Path, maximum: int = 1048576) -> bytes:
        # Narrow perturbation seam: delegate every real file read first.
        raw = real_read(path, maximum)
        name = path.relative_to(root).as_posix()
        reads.append(name)
        return raw + b"\n# fingerprint sensitivity probe\n" if name == dependency else raw

    monkeypatch.setattr(catalog, "read_file", changed_read)
    assert catalog.behavior_revision(domain) != before
    assert reads == list(DEPENDENCIES)


def test_unreadable_dependency_refuses_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    real_read = read_file

    def denied_read(path: Path, maximum: int = 1048576) -> bytes:
        if path.name == "module_registry.py":
            raise CatalogError("UNSAFE_FILE")
        return real_read(path, maximum)

    monkeypatch.setattr(catalog, "read_file", denied_read)
    with pytest.raises(CatalogError, match="UNSAFE_FILE"):
        catalog.behavior_revision("omnis-candidate-evaluator-v1")
