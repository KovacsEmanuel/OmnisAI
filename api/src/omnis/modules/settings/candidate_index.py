"""Canonical materialized index of the existing read-only STATIC compiler."""

from dataclasses import asdict
from pathlib import Path

from .candidate_material import digest
from .catalog_models import CatalogError, CompiledCatalog
from .catalog_schema import canonical
from .skill_catalog import compile_catalog

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
    }
    if digest(canonical(index)) != compiled.resolved_index_digest:
        raise CatalogError("RESOLVED_INDEX_MISMATCH")
    return index


def compile_material(directory: Path, sources: list[dict[str, object]]) -> CompiledCatalog:
    compiled = compile_catalog(
        tuple(directory / str(s["prefix"]) for s in sources if s["source_kind"] == "package"),
        directory / "profile.yaml",
    )
    if any(s["material_digest"] != compiled.material_digest for s in sources):
        raise CatalogError("FROZEN_MATERIAL_MISMATCH")
    return compiled


def index_source(index: dict[str, object]) -> dict[str, object]:
    raw = canonical(index)
    return {"prefix": "", "files": [{"path": INDEX_FILE, "sha256": digest(raw), "size": len(raw)}]}
