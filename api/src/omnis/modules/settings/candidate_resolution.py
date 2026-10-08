"""Exact read-only external artifact inventory; no release producer or publication."""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import cast
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from . import candidate_store as store
from .candidate_material import digest, read_material
from .catalog_models import CatalogError, ExactRef
from .catalog_schema import canonical, load_json, load_yaml

MAX_RELEASES = 128


@dataclass(frozen=True, slots=True)
class ReleasePackage:
    root: Path
    artifact_json: bytes
    qualification_json: bytes


def exact(value: object) -> dict[str, object]:
    try:
        parsed = ExactRef.model_validate(value, strict=True)
        if str(UUID(parsed.id)) != parsed.id or parsed.revision >= 2147483647:
            raise ValueError()
    except ValueError:
        raise CatalogError("REF_TYPE") from None
    return parsed.model_dump(mode="json")


def body(record: dict[str, object]) -> dict[str, object]:
    value = record.get("payload")
    if not isinstance(value, dict):
        raise CatalogError("STORAGE_INCOMPATIBLE")
    return value


def artifact(dependency: ReleasePackage) -> dict[str, object]:
    return store.checked(load_json(dependency.artifact_json))


def verify(dependency: ReleasePackage) -> dict[str, object]:
    # Code identities are imported lazily to avoid a compiler/storage import cycle.
    from .candidate_catalog import COMPILER_REVISION, EVALUATOR_REVISION

    record = artifact(dependency)
    exact(store.reference(record))
    data = body(record)
    qualification = store.checked(load_json(dependency.qualification_json))
    exact(store.reference(qualification))
    qualified = body(qualification)
    if (
        record["kind"] != "qualified-release"
        or set(data)
        != {
            "authority",
            "package_key",
            "package_digest",
            "sources",
            "bindings",
            "qualification_ref",
            "dependency_artifact_refs",
        }
        or data["authority"] != "EXTERNAL_PREQUALIFIED"
        or qualification["kind"] != "release-qualification"
        or store.reference(qualification) != exact(data["qualification_ref"])
        or set(qualified)
        != {
            "material_digest",
            "resolved_index_digest",
            "dependency_closure_refs",
            "dependency_closure_digest",
            "compiler_revision",
            "evaluator_revision",
            "static_status",
            "pure_status",
            "resolution",
            "effective",
            "outputs",
            "pure_input",
        }
        or qualified["compiler_revision"] != COMPILER_REVISION
        or qualified["evaluator_revision"] != EVALUATOR_REVISION
        or qualified["static_status"] != "STATIC_PASS"
        or qualified["pure_status"] != "PURE_PASS"
        or qualified["resolution"] != "NO_MODEL"
        or qualified["effective"] is not None
        or not isinstance(qualified["outputs"], list)
        or len(qualified["outputs"]) != 3
        or not isinstance(qualified["pure_input"], dict)
    ):
        raise CatalogError("RELEASE_UNQUALIFIED")
    sources = data["sources"]
    bindings = data["bindings"]
    edges = data["dependency_artifact_refs"]
    closure = qualified["dependency_closure_refs"]
    if (
        not isinstance(sources, list)
        or len(sources) != 3
        or not all(isinstance(s, dict) for s in sources)
        or not isinstance(bindings, list)
        or not 1 <= len(bindings) <= 128
        or not isinstance(edges, list)
        or len(edges) > MAX_RELEASES
        or not isinstance(closure, list)
        or len(closure) > MAX_RELEASES * 128
    ):
        raise CatalogError("STORAGE_INCOMPATIBLE")
    from .skill_catalog import safe_path

    total = 0
    paths: set[str] = set()
    for source in sources:
        prefix, files = source.get("prefix"), source.get("files")
        if not isinstance(prefix, str) or not isinstance(files, list) or not 1 <= len(files) <= 128:
            raise CatalogError("RELEASE_MISMATCH")
        if prefix:
            safe_path(prefix)
        for item in files:
            if not isinstance(item, dict) or set(item) != {"path", "sha256", "size"}:
                raise CatalogError("RELEASE_MISMATCH")
            name, sha, size = item["path"], item["sha256"], item["size"]
            if (
                not isinstance(name, str)
                or not isinstance(sha, str)
                or re.fullmatch(r"[0-9a-f]{64}", sha) is None
                or type(size) is not int
                or not 0 <= size <= 1048576
            ):
                raise CatalogError("RELEASE_MISMATCH")
            safe_path(name)
            token = f"{prefix}/{name}" if prefix else name
            if token in paths:
                raise CatalogError("RELEASE_MISMATCH")
            paths.add(token)
            total += size
    if total > 8 * 1048576:
        raise CatalogError("SIZE_LIMIT")
    if (
        not isinstance(data["package_key"], str)
        or re.fullmatch(r"[a-z][a-z0-9_.-]{0,127}", data["package_key"]) is None
    ):
        raise CatalogError("RELEASE_MISMATCH")
    for ref in [*edges, *closure]:
        exact(ref)
    if qualified["dependency_closure_digest"] != digest(canonical(closure)):
        raise CatalogError("RELEASE_UNQUALIFIED")
    material = read_material(dependency.root, "candidates", str(record["id"]), sources)
    package, profile, index = sources
    if (
        package.get("source_kind") != "package"
        or package.get("prefix") != "packages/0"
        or package.get("package_key") != data["package_key"]
        or package.get("package_digest") != data["package_digest"]
        or digest(canonical(package.get("files"))) != data["package_digest"]
        or profile.get("source_kind") != "profile"
        or profile.get("prefix") != ""
        or index.get("prefix") != ""
        or set(material)
        != {
            *("packages/0/" + str(f["path"]) for f in package["files"]),
            "profile.yaml",
            "resolved-index.json",
        }
        or digest(material["resolved-index.json"]) != qualified["resolved_index_digest"]
        or digest(
            canonical(
                {
                    "packages": [
                        {"package_key": data["package_key"], "digest": data["package_digest"]}
                    ],
                    "profile_sha256": digest(material["profile.yaml"]),
                }
            )
        )
        != qualified["material_digest"]
    ):
        raise CatalogError("RELEASE_MISMATCH")
    identities: set[tuple[str, str]] = set()
    ids: set[str] = set()
    for binding in bindings:
        if not isinstance(binding, dict) or set(binding) != {
            "package_key",
            "entity_kind",
            "key",
            "ref",
        }:
            raise CatalogError("RELEASE_MISMATCH")
        ref = exact(binding["ref"])
        identity = (str(binding["entity_kind"]), str(binding["key"]))
        if (
            binding["package_key"] != data["package_key"]
            or ref["kind"] != identity[0]
            or ref["digest"] != data["package_digest"]
            or identity in identities
            or str(ref["id"]) in ids
        ):
            raise CatalogError("RELEASE_MISMATCH")
        identities.add(identity)
        ids.add(str(ref["id"]))
    if sorted([list(i) for i in identities]) != package.get("identities"):
        raise CatalogError("RELEASE_MISMATCH")
    return data


def release_refs(directory: Path, sources: list[dict[str, object]]) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []

    def walk(value: object) -> None:
        if isinstance(value, dict):
            if value.get("kind") == "RELEASE":
                if set(value) != {"kind", "ref"}:
                    raise CatalogError("REF_TYPE")
                ref = exact(value["ref"])
                if ref not in result:
                    result.append(ref)
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    from .skill_catalog import read_file

    for source in sources:
        files = source.get("files")
        if not isinstance(files, list):
            raise CatalogError("STORAGE_INCOMPATIBLE")
        for item in files:
            if not isinstance(item, dict) or not isinstance(item.get("path"), str):
                raise CatalogError("STORAGE_INCOMPATIBLE")
            name = str(item["path"])
            # Only template documents own selectors, never arbitrary support text.
            if (
                name == "omnis.yaml"
                or name == "profile.yaml"
                or name.startswith("templates/procedures/")
            ):
                walk(load_yaml(read_file(directory / str(source["prefix"]) / name)))
    return result


async def load_dependencies(
    connection: AsyncConnection,
    owner: str,
    root: Path,
    directory: Path,
    sources: list[dict[str, object]],
    pinned: list[dict[str, object]] | None = None,
) -> tuple[ReleasePackage, ...]:
    """Initial exact selector joins; pinned reads never query a latest/replacement."""
    queue: list[dict[str, object]] = []
    if pinned is not None:
        queue = [exact(ref) for ref in pinned]
    else:
        for ref in release_refs(directory, sources):
            value = await connection.scalar(
                text(
                    "SELECT c.envelope FROM catalog_reservation r "
                    "JOIN catalog_identity i ON i.id=r.id JOIN catalog_record c ON c.id=r.draft_id "
                    "WHERE r.id=:id AND r.revision=:revision AND r.digest=:digest "
                    "AND i.entity_kind=:kind AND i.owner_id=:owner AND c.owner_id=:owner "
                    "AND c.kind='qualified-release'"
                ),
                {**ref, "owner": owner},
            )
            if value is None:
                raise CatalogError("DEPENDENCY_UNAVAILABLE")
            queue.append(store.reference(store.checked(value)))
    inventory: dict[str, ReleasePackage] = {}
    total_bytes = 0
    for ref in queue:
        if len(queue) > MAX_RELEASES * MAX_RELEASES:
            raise CatalogError("COUNT_LIMIT")
        identifier = str(ref["id"])
        if identifier in inventory:
            if store.reference(artifact(inventory[identifier])) != ref:
                raise CatalogError("RELEASE_MISMATCH")
            continue
        if len(inventory) >= MAX_RELEASES:
            raise CatalogError("COUNT_LIMIT")
        _, record = await store.get(connection, owner, ref)
        if record["kind"] != "qualified-release":
            raise CatalogError("RELEASE_UNQUALIFIED")
        _, qualification = await store.get(
            connection, owner, exact(body(record).get("qualification_ref"))
        )
        dependency = ReleasePackage(root, canonical(record), canonical(qualification))
        data = verify(dependency)
        total_bytes += sum(
            cast(int, item["size"])
            for source in cast(list[dict[str, object]], data["sources"])
            for item in cast(list[dict[str, object]], source["files"])
        )
        if total_bytes > 8 * 1048576:
            raise CatalogError("SIZE_LIMIT")
        bindings = data["bindings"]
        if not isinstance(bindings, list):
            raise CatalogError("RELEASE_MISMATCH")
        for binding in bindings:
            if not isinstance(binding, dict):
                raise CatalogError("RELEASE_MISMATCH")
            reservation = await connection.scalar(
                text(
                    "SELECT EXISTS(SELECT 1 FROM catalog_reservation r JOIN catalog_identity i ON i.id=r.id "
                    "WHERE r.id=:id AND r.revision=:revision AND r.digest=:digest AND r.draft_id=:artifact "
                    "AND i.owner_id=:owner AND i.entity_kind=:kind AND i.package_key=:package "
                    "AND i.entity_key=:key)"
                ),
                {
                    **exact(binding["ref"]),
                    "owner": owner,
                    "artifact": identifier,
                    "package": binding["package_key"],
                    "key": binding["key"],
                },
            )
            if reservation is not True:
                raise CatalogError("RELEASE_MISMATCH")
        inventory[identifier] = dependency
        edges = data["dependency_artifact_refs"]
        if not isinstance(edges, list):
            raise CatalogError("RELEASE_MISMATCH")
        queue.extend(exact(edge) for edge in edges)
    result = tuple(inventory[key] for key in sorted(inventory))
    if pinned is not None and sorted(pinned, key=canonical) != sorted(
        [store.reference(artifact(d)) for d in result], key=canonical
    ):
        raise CatalogError("RELEASE_MISMATCH")
    return result
