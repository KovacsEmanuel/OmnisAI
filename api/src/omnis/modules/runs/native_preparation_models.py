"""Bounded inert document bundle, independent of native imports and execution."""

import base64
import binascii
import re
from pathlib import PurePosixPath

from omnis.modules.settings import candidate_store as store
from omnis.modules.settings.candidate_catalog import payload, uuid_string, valid_ref
from omnis.modules.settings.candidate_material import digest
from omnis.modules.settings.catalog_models import CatalogError, Manifest
from omnis.modules.settings.catalog_schema import bounded, canonical, dto, load_json, load_yaml
from omnis.modules.settings.publication_models import clean_text
from omnis.modules.settings.skill_catalog import safe_path

LIMITS = {
    "max_packages": 2,
    "max_files": 16,
    "max_file_bytes": 8192,
    "max_total_raw_bytes": 16384,
    "max_bundle_envelope_bytes": 32768,
    "max_runtime_request_bytes": 49152,
    "max_worker_result_bytes": 32768,
    "max_runtime_response_bytes": 65536,
}
BASE_COMMIT = "ee5ee84a345204a3b1d6ef6ba1ab747e602867b9"
PATCH_SHA256 = "481c19d07c9309f18f61b0c2bdab0b6c6533a384e5aebd27d4add219b052f223"
SKILLS_TOOL_SHA256 = "0d47bda41ed9d1ec84856df3d336a42bb94161e89bd9a8b857e76ec76be9f7b7"


def mapping(value: object) -> dict[str, object]:
    if not isinstance(value, dict) or any(type(k) is not str for k in value):
        raise CatalogError("PREPARATION_REJECTED")
    return {k: v for k, v in value.items()}


def sequence(value: object) -> list[object]:
    if type(value) is not list:
        raise CatalogError("PREPARATION_REJECTED")
    return list(value)


def text(value: object) -> str:
    if type(value) is not str:
        raise CatalogError("PREPARATION_REJECTED")
    clean_text(value)
    return value


def sha(value: object) -> str:
    result = text(value)
    if re.fullmatch(r"[0-9a-f]{64}", result) is None:
        raise CatalogError("PREPARATION_REJECTED")
    return result


def native_name(value: object) -> str:
    result = text(value)
    if re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", result) is None:
        raise CatalogError("PREPARATION_REJECTED")
    return result


def document(raw: bytes) -> str:
    try:
        result = raw.decode("utf-8", errors="strict")
    except UnicodeError:
        raise CatalogError("PREPARATION_REJECTED") from None
    if (
        len(raw) > LIMITS["max_file_bytes"]
        or result.startswith("\ufeff")
        or any(ord(c) < 32 and c not in "\n\t" or ord(c) == 127 for c in result)
    ):
        raise CatalogError("PREPARATION_REJECTED")
    return result


def path_name(value: object) -> str:
    name = text(value)
    safe_path(name)
    parts = PurePosixPath(name).parts
    if (
        not parts
        or any(p.startswith(".") for p in parts)
        or (
            len(parts) > 1
            and (
                parts[0] not in {"references", "templates", "assets", "scripts"}
                or parts[-1] == "SKILL.md"
            )
        )
    ):
        raise CatalogError("PREPARATION_REJECTED")
    return name


def frontmatter(raw: bytes, expected: str) -> None:
    content = document(raw)
    if not content.startswith("---\n") or "\n---\n" not in content[4:]:
        raise CatalogError("PREPARATION_REJECTED")
    fields = mapping(load_yaml(content[4:].split("\n---\n", 1)[0].encode()))
    descriptive = {"name", "description", "version", "provenance", "author", "license"}
    lists = {"tags", "related_skills", "platforms"}
    if not {"name", "description"} <= set(fields) or set(fields) - descriptive - lists:
        raise CatalogError("PREPARATION_REJECTED")
    for key, value in fields.items():
        values = sequence(value) if key in lists else [value]
        if len(values) > 32:
            raise CatalogError("PREPARATION_REJECTED")
        for item in values:
            if not 0 < len(text(item)) <= 4096:
                raise CatalogError("PREPARATION_REJECTED")
    if native_name(fields["name"]) != expected:
        raise CatalogError("PREPARATION_REJECTED")


def prepare_packages(
    material: dict[str, bytes], selected: list[tuple[dict[str, object], dict[str, object]]]
) -> list[dict[str, object]]:
    if not 1 <= len(selected) <= LIMITS["max_packages"]:
        raise CatalogError("PREPARATION_REJECTED")
    packages: list[dict[str, object]] = []
    total = count = 0
    names: set[str] = set()
    refs: set[bytes] = set()
    for ref, source in selected:
        valid_ref(ref)
        prefix = text(source.get("prefix"))
        if re.fullmatch(r"packages/(0|[1-9][0-9]*)", prefix) is None:
            raise CatalogError("PREPARATION_REJECTED")
        manifest_raw = material.get(prefix + "/omnis.yaml")
        if manifest_raw is None:
            raise CatalogError("PREPARATION_REJECTED")
        document(manifest_raw)
        manifest = dto(manifest_raw, Manifest)
        name = native_name(manifest.native_name)
        expected = ["omnis.yaml", "SKILL.md", *manifest.procedures, *manifest.support_files]
        if (
            name in names
            or canonical(ref) in refs
            or len(set(expected)) != len(expected)
            or source.get("package_key") != manifest.package_key
            or ref["kind"] != "package"
        ):
            raise CatalogError("PREPARATION_REJECTED")
        names.add(name)
        refs.add(canonical(ref))
        listing: list[dict[str, object]] = []
        files: list[dict[str, object]] = []
        for path in sorted(expected, key=lambda p: p.encode("utf-8")):
            path_name(path)
            raw = material.get(prefix + "/" + path)
            if raw is None:
                raise CatalogError("PREPARATION_REJECTED")
            document(raw)
            if path == "SKILL.md":
                frontmatter(raw, name)
            total += len(raw)
            count += 1
            if total > LIMITS["max_total_raw_bytes"] or count > LIMITS["max_files"]:
                raise CatalogError("PREPARATION_REJECTED")
            entry: dict[str, object] = {"path": path, "size": len(raw), "sha256": digest(raw)}
            listing.append(entry)
            files.append({**entry, "content_b64": base64.b64encode(raw).decode("ascii")})
        if (
            source.get("files") != listing
            or source.get("package_digest") != digest(canonical(listing))
            or ref["digest"] != source["package_digest"]
        ):
            raise CatalogError("PREPARATION_REJECTED")
        packages.append(
            {
                "package_ref": ref,
                "package_key": manifest.package_key,
                "native_name": name,
                "files": files,
            }
        )
    return sorted(packages, key=lambda p: text(p["native_name"]).encode("utf-8"))


def validate_bundle(reference: object, value: object) -> dict[str, object]:
    bounded(value)
    clean_text(value)
    if len(canonical(value)) > LIMITS["max_bundle_envelope_bytes"]:
        raise CatalogError("PREPARATION_REJECTED")
    record = store.checked(value)
    ref = valid_ref(reference)
    if (
        record["kind"] != "native-preparation-bundle"
        or store.reference(record) != ref
        or type(record["schema_version"]) is not int
        or record["schema_version"] != 1
        or type(record["revision"]) is not int
        or record["revision"] != 1
    ):
        raise CatalogError("PREPARATION_REJECTED")
    body = payload(record)
    if set(body) != {
        "protocol",
        "owner_id",
        "selection_ref",
        "snapshot_ref",
        "publication_ref",
        "candidate_snapshot_ref",
        "recipe_key",
        "material_digest",
        "resolved_index_digest",
        "resolution",
        "effective",
        "preprocess",
        "limits",
        "packages",
    }:
        raise CatalogError("PREPARATION_REJECTED")
    if (
        body["protocol"] != "omnis-native-preparation-v1"
        or body["resolution"] != "NO_MODEL"
        or body["effective"] is not None
        or body["preprocess"] is not False
        or canonical(body["limits"]) != canonical(LIMITS)
    ):
        raise CatalogError("PREPARATION_REJECTED")
    uuid_string(body["owner_id"])
    sha(body["material_digest"])
    sha(body["resolved_index_digest"])
    if re.fullmatch(r"[a-z][a-z0-9_.-]{0,127}", text(body["recipe_key"])) is None:
        raise CatalogError("PREPARATION_REJECTED")
    for field, kind in (
        ("selection_ref", "execution-selection"),
        ("snapshot_ref", "run-snapshot"),
        ("publication_ref", "catalog-publication"),
        ("candidate_snapshot_ref", "candidate-snapshot"),
    ):
        if valid_ref(body[field])["kind"] != kind:
            raise CatalogError("PREPARATION_REJECTED")
    material: dict[str, bytes] = {}
    selected: list[tuple[dict[str, object], dict[str, object]]] = []
    packages = sequence(body["packages"])
    for number, item in enumerate(packages):
        package = mapping(item)
        if set(package) != {"package_ref", "package_key", "native_name", "files"}:
            raise CatalogError("PREPARATION_REJECTED")
        prefix = f"packages/{number}"
        listing: list[dict[str, object]] = []
        for entry in sequence(package["files"]):
            file = mapping(entry)
            if set(file) != {"path", "size", "sha256", "content_b64"}:
                raise CatalogError("PREPARATION_REJECTED")
            path = path_name(file["path"])
            encoded = text(file["content_b64"])
            try:
                raw = base64.b64decode(encoded, validate=True)
            except (ValueError, binascii.Error):
                raise CatalogError("PREPARATION_REJECTED") from None
            if (
                base64.b64encode(raw).decode("ascii") != encoded
                or type(file["size"]) is not int
                or file["size"] != len(raw)
                or sha(file["sha256"]) != digest(raw)
                or prefix + "/" + path in material
            ):
                raise CatalogError("PREPARATION_REJECTED")
            material[prefix + "/" + path] = raw
            listing.append({k: file[k] for k in ("path", "size", "sha256")})
        package_ref = valid_ref(package["package_ref"])
        selected.append(
            (
                package_ref,
                {
                    "prefix": prefix,
                    "package_key": package["package_key"],
                    "files": listing,
                    "package_digest": package_ref["digest"],
                },
            )
        )
    if prepare_packages(material, selected) != packages:
        raise CatalogError("PREPARATION_REJECTED")
    return mapping(load_json(canonical(record)))


def validate_worker(value: object, reference: object, bundle: object) -> dict[str, object]:
    record = validate_bundle(reference, bundle)
    bounded(value)
    clean_text(value)
    if len(canonical(value)) > LIMITS["max_worker_result_bytes"]:
        raise CatalogError("PREPARATION_REJECTED")
    result = mapping(value)
    if (
        set(result)
        != {"schema_version", "status", "bundle_ref", "loader", "preprocess", "loaded", "native"}
        or type(result["schema_version"]) is not int
        or result["schema_version"] != 1
        or result["status"] != "PREPARED"
        or valid_ref(result["bundle_ref"]) != reference
        or result["loader"] != "tools.skills_tool.skill_view"
        or result["preprocess"] is not False
    ):
        raise CatalogError("PREPARATION_REJECTED")
    expected: list[dict[str, object]] = []
    for item in sequence(payload(record)["packages"]):
        package = mapping(item)
        for file in sequence(package["files"]):
            expected.append(
                {
                    "package_ref": package["package_ref"],
                    "native_name": package["native_name"],
                    **mapping(file),
                }
            )
    # Canonical comparison rejects bool-as-int and compares every raw byte and field.
    if canonical(result["loaded"]) != canonical(expected):
        raise CatalogError("PREPARATION_REJECTED")
    native = mapping(result["native"])
    if (
        set(native) != {"base_commit", "patch_sha256", "skills_tool_sha256", "worker_revision"}
        or native["base_commit"] != BASE_COMMIT
        or native["patch_sha256"] != PATCH_SHA256
        or native["skills_tool_sha256"] != SKILLS_TOOL_SHA256
    ):
        raise CatalogError("PREPARATION_REJECTED")
    sha(native["worker_revision"])
    return mapping(load_json(canonical(result)))
