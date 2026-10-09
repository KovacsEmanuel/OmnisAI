"""Stdlib-only bounded wire contract; no native imports or executable metadata."""

import base64
import binascii
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import cast
from uuid import UUID

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
SKILLS_SHA256 = "0d47bda41ed9d1ec84856df3d336a42bb94161e89bd9a8b857e76ec76be9f7b7"


def reject() -> ValueError:
    return ValueError("Invalid native preparation")


def canonical(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def bounded(value: object, depth: int = 0) -> None:
    if depth > 20:
        raise reject()
    if isinstance(value, dict):
        if len(value) > 128:
            raise reject()
        for key, child in value.items():
            if not isinstance(key, str):
                raise reject()
            bounded(key, depth + 1)
            bounded(child, depth + 1)
    elif isinstance(value, list):
        if len(value) > 128:
            raise reject()
        for child in value:
            bounded(child, depth + 1)
    elif isinstance(value, str):
        if len(value.encode("utf-8")) > 65536 or "\0" in value:
            raise reject()
    elif value is not None and type(value) not in (int, bool):
        raise reject()


def pairs(values: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in values:
        if key in result:
            raise reject()
        result[key] = value
    return result


def no_number(_: str) -> object:
    raise reject()


def loads(raw: bytes | str, limit: int) -> object:
    try:
        if len(raw.encode("utf-8") if isinstance(raw, str) else raw) > limit:
            raise reject()
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        value: object = json.loads(
            raw, object_pairs_hook=pairs, parse_float=no_number, parse_constant=no_number
        )
        bounded(value)
        return value
    except (ValueError, UnicodeError, RecursionError):
        raise reject() from None


def obj(value: object, keys: set[str]) -> dict[str, object]:
    if type(value) is not dict or set(value) != keys:
        raise reject()
    return cast(dict[str, object], value)


def text(value: object, maximum: int = 128) -> str:
    if type(value) is not str or not 0 < len(value.encode("utf-8")) <= maximum:
        raise reject()
    if any(ord(c) < 32 or 127 <= ord(c) <= 159 or c in "\u2028\u2029" for c in value):
        raise reject()
    return value


def uuid(value: object) -> str:
    value = text(value, 36)
    if str(UUID(value)) != value:
        raise reject()
    return value


def sha(value: object) -> str:
    value = text(value, 64)
    if re.fullmatch("[0-9a-f]{64}", value) is None:
        raise reject()
    return value


def reference(value: object, kind: str | None = None) -> dict[str, object]:
    value = obj(value, {"kind", "id", "revision", "digest"})
    text(value["kind"])
    uuid(value["id"])
    sha(value["digest"])
    if type(value["revision"]) is not int or not 1 <= value["revision"] < 2**63:
        raise reject()
    if kind is not None and value["kind"] != kind:
        raise reject()
    return value


def raw_text(raw: bytes) -> str:
    content = raw.decode("utf-8")
    if content.startswith("\ufeff") or any(
        (ord(c) < 32 and c not in "\n\t") or 127 <= ord(c) <= 159 for c in content
    ):
        raise reject()
    return content


def scalar(value: str) -> str:
    # Deliberately small YAML lexical subset, not a second permissive YAML parser.
    if value.startswith('"'):
        decoded = loads(value, 2048)
        return text(decoded, 1024)
    if value.startswith("'"):
        if not value.endswith("'"):
            raise reject()
        value = value[1:-1].replace("''", "'")
    elif (
        not value
        or value[0] in "!&*|>{[?@`"
        or ": " in value
        or " #" in value
        or value.lower() in {"null", "true", "false", "yes", "no", "on", "off", "~"}
    ):
        raise reject()
    return text(value, 1024)


def frontmatter(raw: bytes, name: str) -> None:
    content = raw_text(raw)
    lines = content.split("\n")
    if lines[0] != "---" or "---" not in lines[1:]:
        raise reject()
    end = lines.index("---", 1)
    allowed = {
        "name",
        "description",
        "version",
        "provenance",
        "author",
        "license",
        "tags",
        "related_skills",
        "platforms",
    }
    values: dict[str, object] = {}
    list_key: str | None = None
    for line in lines[1:end]:
        if not line.strip():
            continue
        if line.startswith("  - ") and list_key is not None:
            items = cast(list[str], values[list_key])
            items.append(scalar(line[4:]))
            if len(items) > 32:
                raise reject()
            continue
        match = re.fullmatch(r"([a-z_]+):(?: (.*))?", line)
        if match is None or match[1] not in allowed or match[1] in values:
            raise reject()
        key, value = match[1], match[2] or ""
        list_key = None
        if key in {"tags", "related_skills", "platforms"}:
            if not value:
                values[key] = []
                list_key = key
            elif value.startswith("[") and value.endswith("]"):
                values[key] = [scalar(v.strip()) for v in value[1:-1].split(",") if v.strip()]
                if len(cast(list[str], values[key])) > 32:
                    raise reject()
            else:
                raise reject()
        else:
            values[key] = scalar(value)
    if values.get("name") != name or not values.get("description"):
        raise reject()


@dataclass(frozen=True)
class BundleFile:
    package_ref: dict[str, object]
    native_name: str
    path: str
    raw: bytes

    def loaded(self) -> dict[str, object]:
        return {
            "package_ref": self.package_ref,
            "native_name": self.native_name,
            "path": self.path,
            "size": len(self.raw),
            "sha256": digest(self.raw),
            "content_b64": base64.b64encode(self.raw).decode("ascii"),
        }


def validate_payload(value: object) -> tuple[dict[str, object], tuple[BundleFile, ...]]:
    try:
        return _validate_payload(value)
    except (ValueError, UnicodeError, RecursionError, binascii.Error):
        raise reject() from None


def _validate_payload(value: object) -> tuple[dict[str, object], tuple[BundleFile, ...]]:
    bounded(value)
    value = obj(value, {"bundle_ref", "bundle"})
    ref = reference(value["bundle_ref"], "native-preparation-bundle")
    envelope = obj(
        value["bundle"], {"schema_version", "kind", "id", "revision", "payload", "digest"}
    )
    if (
        type(envelope["schema_version"]) is not int
        or envelope["schema_version"] != 1
        or type(envelope["revision"]) is not int
        or envelope["revision"] != 1
        or {k: envelope[k] for k in ref} != ref
        or digest(canonical({k: v for k, v in envelope.items() if k != "digest"})) != ref["digest"]
        or len(canonical(envelope)) > LIMITS["max_bundle_envelope_bytes"]
    ):
        raise reject()
    payload = obj(
        envelope["payload"],
        {
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
        },
    )
    uuid(payload["owner_id"])
    for key, kind in (
        ("selection_ref", "execution-selection"),
        ("snapshot_ref", "run-snapshot"),
        ("publication_ref", "catalog-publication"),
        ("candidate_snapshot_ref", "candidate-snapshot"),
    ):
        reference(payload[key], kind)
    text(payload["recipe_key"])
    sha(payload["material_digest"])
    sha(payload["resolved_index_digest"])
    limits = obj(payload["limits"], set(LIMITS))
    if (
        payload["protocol"] != "omnis-native-preparation-v1"
        or payload["resolution"] != "NO_MODEL"
        or payload["effective"] is not None
        or payload["preprocess"] is not False
        or limits != LIMITS
        or any(type(v) is not int for v in limits.values())
    ):
        raise reject()
    packages = payload["packages"]
    if not isinstance(packages, list) or not 1 <= len(packages) <= LIMITS["max_packages"]:
        raise reject()
    result: list[BundleFile] = []
    names: list[str] = []
    package_keys: set[str] = set()
    package_refs: set[bytes] = set()
    for item in packages:
        package = obj(item, {"package_ref", "package_key", "native_name", "files"})
        package_ref = reference(package["package_ref"])
        key = text(package["package_key"])
        name = text(package["native_name"], 64)
        if (
            re.fullmatch("[a-z][a-z0-9_-]{0,63}", name) is None
            or name in names
            or key in package_keys
            or canonical(package_ref) in package_refs
        ):
            raise reject()
        names.append(name)
        package_keys.add(key)
        package_refs.add(canonical(package_ref))
        files = package["files"]
        if not isinstance(files, list) or not 2 <= len(files) <= LIMITS["max_files"]:
            raise reject()
        paths: list[str] = []
        for entry in files:
            file = obj(entry, {"path", "size", "sha256", "content_b64"})
            path = text(file["path"], 256)
            parts = path.split("/")
            if (
                PurePosixPath(path).is_absolute()
                or any(re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]*", part) is None for part in parts)
                or path in paths
                or (
                    len(parts) > 1
                    and (
                        parts[0] not in {"references", "templates", "assets", "scripts"}
                        or "SKILL.md" in parts
                    )
                )
            ):
                raise reject()
            paths.append(path)
            encoded = file["content_b64"]
            if type(encoded) is not str or len(encoded) > 10924:
                raise reject()
            raw = base64.b64decode(encoded, validate=True)
            if (
                base64.b64encode(raw).decode() != encoded
                or type(file["size"]) is not int
                or file["size"] != len(raw)
                or len(raw) > LIMITS["max_file_bytes"]
                or digest(raw) != sha(file["sha256"])
            ):
                raise reject()
            raw_text(raw)
            if path == "SKILL.md":
                frontmatter(raw, name)
            result.append(BundleFile(package_ref, name, path, raw))
        if paths != sorted(paths) or not {"SKILL.md", "omnis.yaml"} <= set(paths):
            raise reject()
    if (
        names != sorted(names)
        or len(result) > LIMITS["max_files"]
        or sum(len(file.raw) for file in result) > LIMITS["max_total_raw_bytes"]
    ):
        raise reject()
    return ref, tuple(result)


def validate_result(value: object, payload: object, worker_revision: str) -> dict[str, object]:
    ref, files = validate_payload(payload)
    bounded(value)
    value = obj(
        value,
        {"schema_version", "status", "bundle_ref", "loader", "preprocess", "loaded", "native"},
    )
    if (
        type(value["schema_version"]) is not int
        or value["schema_version"] != 1
        or value["status"] != "PREPARED"
        or reference(value["bundle_ref"], "native-preparation-bundle") != ref
        or value["loader"] != "tools.skills_tool.skill_view"
        or value["preprocess"] is not False
        or canonical(value["loaded"]) != canonical([file.loaded() for file in files])
        or value["native"]
        != {
            "base_commit": BASE_COMMIT,
            "patch_sha256": PATCH_SHA256,
            "skills_tool_sha256": SKILLS_SHA256,
            "worker_revision": worker_revision,
        }
        or len(canonical(value)) + 1 > LIMITS["max_worker_result_bytes"]
    ):
        raise reject()
    return value
