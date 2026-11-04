"""Canonical materialized index of the existing read-only STATIC compiler."""

from dataclasses import asdict, replace
from pathlib import Path
from typing import TYPE_CHECKING

from .candidate_material import digest
from .catalog_models import CatalogError, CompiledCatalog
from .catalog_schema import canonical
from .skill_catalog import compile_catalog

if TYPE_CHECKING:
    from .candidate_resolution import ReleasePackage

INDEX_FILE = "resolved-index.json"


def resolved_index(compiled: CompiledCatalog) -> dict[str, object]:
    index: dict[str, object] = {
        "refs": [
            asdict(r)
            for r in sorted(compiled.refs, key=lambda r: (r.package_key, r.entity_kind, r.key))
        ],
        "steps": [
            {
                "id": s.id,
                "handler": s.handler,
                "input_schema_sha256": digest(s.input_schema),
                "output_schema_sha256": digest(s.output_schema),
            }
            for s in compiled.steps
        ],
        "requested": compiled.requested.model_dump(mode="json"),
        "resolution": "NO_MODEL",
        "dependency_closure_refs": list(compiled.dependency_closure_refs),
        "dependency_artifact_refs": list(compiled.dependency_artifact_refs),
        "catalog_bindings": list(compiled.catalog_bindings),
    }
    if compiled.core_text:
        index["catalog_schema_version"] = 2
    if digest(canonical(index)) != compiled.resolved_index_digest:
        raise CatalogError("RESOLVED_INDEX_MISMATCH")
    return index


def bind_catalog(compiled: CompiledCatalog, bindings: list[dict[str, object]]) -> CompiledCatalog:
    from .candidate_resolution import exact

    identities: dict[tuple[str, str, str], dict[str, object]] = {}
    tokens: set[bytes] = set()
    for binding in [*bindings, *compiled.catalog_bindings]:
        if set(binding) != {"package_key", "entity_kind", "key", "ref"}:
            raise CatalogError("REF_MISMATCH")
        ref = exact(binding["ref"])
        identity = (str(binding["package_key"]), str(binding["entity_kind"]), str(binding["key"]))
        if identity in identities or canonical(ref) in tokens or ref["kind"] != identity[1]:
            raise CatalogError("REF_MISMATCH")
        identities[identity] = binding
        tokens.add(canonical(ref))
    for qualified in compiled.refs:
        bound = identities.get((qualified.package_key, qualified.entity_kind, qualified.key))
        if bound is None or exact(bound["ref"])["digest"] != qualified.digest:
            raise CatalogError("REF_MISMATCH")
    index = resolved_index(compiled)
    ordered = tuple(sorted(identities.values(), key=canonical))
    index["catalog_bindings"] = list(ordered)
    return replace(
        compiled, catalog_bindings=ordered, resolved_index_digest=digest(canonical(index))
    )


def compile_material(
    directory: Path,
    sources: list[dict[str, object]],
    *,
    dependencies: tuple["ReleasePackage", ...] = (),
) -> CompiledCatalog:
    compiled = compile_catalog(
        tuple(directory / str(s["prefix"]) for s in sources if s["source_kind"] == "package"),
        directory / "profile.yaml",
        dependencies=dependencies,
    )
    if any(s["material_digest"] != compiled.material_digest for s in sources):
        raise CatalogError("FROZEN_MATERIAL_MISMATCH")
    return compiled


def index_source(index: dict[str, object]) -> dict[str, object]:
    raw = canonical(index)
    return {"prefix": "", "files": [{"path": INDEX_FILE, "sha256": digest(raw), "size": len(raw)}]}
