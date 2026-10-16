"""Finite prepared-native closure for the explicit installed Settings profile.

Reads producer metadata; never imports Hermes, installs packages or discovers inputs.
Only runtime-source, wheelhouse and exact root metadata enter the OCI context.
The producer's source/build environments and command logs never enter that context.
"""

import hashlib
import json
import os
import re
import stat
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

from .instance import private_dir, unique_pairs
from .release import ReleaseError, _bytes, _put, _sync_tree

PROFILE = "p4a-settings-offline"
METADATA = (
    "source-manifest.json",
    "build-manifest.json",
    "requirements-native.txt",
    "requirements-artifacts.txt",
)
FILES = {*("native/" + name for name in METADATA), "ops/Dockerfile.hermes"}
# These are producer workspace outputs, not executable image inputs. Do not read
# logs or recurse into venvs/caches; their legitimate internal symlinks are irrelevant.
PRODUCER_ONLY = {
    "source",
    "dependency-override",
    "build-home",
    "build-venv",
    "native-venv",
    "commands.jsonl",
    "requirements-build.txt",
    "tmp",
    "uv-cache",
}
SOURCE_ROOTS = {
    "agent",
    "tools",
    "hermes_cli",
    "gateway",
    "tui_gateway",
    "cron",
    "acp_adapter",
    "plugins",
    "providers",
    "hermes_platform",
    "locales",
    "skills",
    "optional-skills",
    "optional-mcps",
    "web_dist",
    "tui_dist",
}


def _object(value: object) -> dict[str, object]:
    if type(value) is not dict or any(type(key) is not str for key in value):
        raise ReleaseError("Invalid native metadata")
    return value


def _digest(value: object) -> str:
    if type(value) is not str or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ReleaseError("Invalid native checksum")
    return value


def _name(value: object) -> str:
    if (
        type(value) is not str
        or not value
        or len(value.encode()) > 1024
        or "\\" in value
        or any(ord(c) < 32 or ord(c) == 127 for c in value)
        or value.startswith("/")
        or any(p in {"", ".", ".."} for p in value.split("/"))
    ):
        raise ReleaseError("Invalid native path")
    return value


def _hashes(value: object) -> dict[str, str]:
    result = {_name(name): _digest(digest) for name, digest in _object(value).items()}
    if not result or len(result) > 20000:
        raise ReleaseError("Native file inventory limit")
    return result


def closure(payloads: dict[str, bytes]) -> dict[str, tuple[str, int | None]]:
    """Validate the standard build_native/inject_adapter shape, not derivatives."""
    if not FILES <= payloads.keys():
        raise ReleaseError("Native metadata required")
    source = _object(
        json.loads(payloads["native/source-manifest.json"], object_pairs_hook=unique_pairs)
    )
    build = _object(
        json.loads(payloads["native/build-manifest.json"], object_pairs_hook=unique_pairs)
    )
    if (
        set(source)
        != {
            "schema_version",
            "pin",
            "original_files",
            "patched_files",
            "managed_patched_files",
            "management_patched_files",
            "dependency_override",
            "native_started",
            "provider_calls",
            "assessment_ready",
        }
        or set(build)
        != {
            "schema_version",
            "python",
            "dependency_wheels",
            "native_source_files",
            "native_distribution",
            "dependency_override",
            "native_started",
            "adapter_injected",
            "adapter_wheel",
        }
        or type(source["schema_version"]) is not int
        or source["schema_version"] != 1
        or type(build["schema_version"]) is not int
        or build["schema_version"] != 1
        or source["native_started"] is not False
        or build["native_started"] is not False
        or source["provider_calls"] != "NOT_RUN"
        or source["assessment_ready"] is not False
        or build["adapter_injected"] is not True
        or build["python"] != "3.13.15"
        or build["native_distribution"] != "supported source layout (not a Nix wheel)"
    ):
        raise ReleaseError("Unsupported native producer")
    pin = _object(source["pin"])
    if (
        pin.get("python") != build["python"]
        or source["dependency_override"] != build["dependency_override"]
    ):
        raise ReleaseError("Native dependency identity mismatch")
    deps = _object(_object(source["dependency_override"]).get("files"))
    if hashlib.sha256(payloads["native/requirements-native.txt"]).hexdigest() != _digest(
        deps.get("requirements-native.txt")
    ):
        raise ReleaseError("Native requirements mismatch")
    combined = _hashes(source["original_files"])
    for layer in ("patched_files", "managed_patched_files", "management_patched_files"):
        for name, raw in _object(source[layer]).items():
            name, row = _name(name), _object(raw)
            if (
                set(row) != {"original_sha256", "patched_sha256"}
                or combined.get(name) != row["original_sha256"]
            ):
                raise ReleaseError("Native overlay lineage mismatch")
            combined[name] = _digest(row["patched_sha256"])
    expected_source = {
        name: digest
        for name, digest in combined.items()
        if (
            name.split("/")[0] in SOURCE_ROOTS
            and "__pycache__" not in PurePosixPath(name).parts
            and not name.endswith(".pyc")
        )
        or ("/" not in name and (name.endswith(".py") or name in {"pyproject.toml", "LICENSE"}))
    }
    files = _hashes(build["native_source_files"])
    if files != expected_source:
        raise ReleaseError("Native source closure mismatch")
    result: dict[str, tuple[str, int | None]] = {
        "runtime-source/" + name: (digest, None) for name, digest in files.items()
    }
    wheels = build["dependency_wheels"]
    if type(wheels) is not list or not 1 <= len(wheels) <= 128:
        raise ReleaseError("Native wheel inventory limit")
    for raw in wheels:
        row = _object(raw)
        if set(row) != {"url", "hash", "size", "upload-time"} or type(row["url"]) is not str:
            raise ReleaseError("Invalid native wheel metadata")
        url = urlsplit(row["url"])
        name = _name(url.path.rsplit("/", 1)[-1])
        digest = _digest(
            row["hash"][7:]
            if type(row["hash"]) is str and row["hash"].startswith("sha256:")
            else None
        )
        if (
            url.scheme != "https"
            or url.netloc != "files.pythonhosted.org"
            or url.query
            or url.fragment
            or not re.fullmatch(r"[A-Za-z0-9_.+-]+\.whl", name)
            or type(row["size"]) is not int
            or not 0 < row["size"] <= 256 * 1024 * 1024
            or ("--hash=sha256:" + digest).encode()
            not in payloads["native/requirements-native.txt"]
            or "wheelhouse/" + name in result
        ):
            raise ReleaseError("Native wheel binding mismatch")
        result["wheelhouse/" + name] = (digest, row["size"])
    adapter = _object(build["adapter_wheel"])
    if (
        set(adapter) != {"name", "sha256"}
        or adapter["name"] != "omnis_hermes-0.1.0-py3-none-any.whl"
    ):
        raise ReleaseError("Invalid native adapter")
    adapter_name = _name(adapter["name"])
    adapter_digest = _digest(adapter["sha256"])
    expected_req = (
        "# Separate Omnis adapter input required for OCI.\n"
        + adapter_name
        + " --hash=sha256:"
        + adapter_digest
        + "\n"
    ).encode()
    if (
        payloads["native/requirements-artifacts.txt"] != expected_req
        or "wheelhouse/" + adapter_name in result
    ):
        raise ReleaseError("Native adapter requirement mismatch")
    result["wheelhouse/" + adapter_name] = (adapter_digest, None)
    result["LICENSE.hermes"] = (_digest(pin.get("license_sha256")), None)
    for name in METADATA:
        body = payloads["native/" + name]
        result[name] = (hashlib.sha256(body).hexdigest(), len(body))
    return result


def _inventory(root: Path, expected: set[str], *, prepared: bool) -> None:
    info = root.lstat()
    private_ancestor = any(
        parent.stat().st_uid == os.getuid() and parent.stat().st_mode & 0o077 == 0
        for parent in root.parents
    )
    if (
        not root.is_absolute()
        or root.resolve() != root
        or not stat.S_ISDIR(info.st_mode)
        or info.st_uid != os.getuid()
        or info.st_mode & 0o002
        or info.st_mode & 0o020
        and not private_ancestor
    ):
        raise ReleaseError("Unsafe prepared context root")
    if not prepared:
        private_dir(root)
    allowed_root = set(METADATA) | {"LICENSE.hermes", "runtime-source", "wheelhouse"}
    if prepared:
        allowed_root |= PRODUCER_ONLY
    else:
        allowed_root.add("Dockerfile")
    if {p.name for p in root.iterdir()} - allowed_root:
        raise ReleaseError("Unlisted native context entry")
    found: set[str] = set()
    expected_dirs = {
        str(parent)
        for name in expected
        for parent in PurePosixPath(name).parents
        if str(parent) != "."
    }
    for top in ("runtime-source", "wheelhouse"):
        if not stat.S_ISDIR((root / top).lstat().st_mode):
            raise ReleaseError("Invalid native context directory")
        for parent, dirs, files in os.walk(root / top, followlinks=False):
            for name in dirs:
                path = Path(parent) / name
                if (
                    not stat.S_ISDIR(path.lstat().st_mode)
                    or path.relative_to(root).as_posix() not in expected_dirs
                ):
                    raise ReleaseError("Unexpected native context directory")
            found.update((Path(parent) / name).relative_to(root).as_posix() for name in files)
    for name in expected:
        info = (root / name).lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ReleaseError("Unsafe native executable input")
    if found != {name for name in expected if name.startswith(("runtime-source/", "wheelhouse/"))}:
        raise ReleaseError("Unlisted native executable input")


def validate_context(root: Path, payloads: dict[str, bytes]) -> dict[str, tuple[str, int | None]]:
    expected = closure(payloads)
    _inventory(root, set(expected), prepared=True)
    total = 0
    for name, (digest, size) in expected.items():
        content = _bytes(root / name, limit=size if size is not None else 256 * 1024 * 1024)
        total += len(content)
        if (
            total > 1024 * 1024 * 1024
            or hashlib.sha256(content).hexdigest() != digest
            or (size is not None and len(content) != size)
        ):
            raise ReleaseError("Native executable input mismatch")
    return expected


def stage_context(root: Path, payloads: dict[str, bytes], destination: Path) -> None:
    expected = validate_context(root, payloads)  # Refuse before writing any input.
    destination.mkdir(mode=0o700)
    for name, (digest, size) in expected.items():
        content = _bytes(root / name, limit=size if size is not None else 256 * 1024 * 1024)
        if hashlib.sha256(content).hexdigest() != digest or (
            size is not None and len(content) != size
        ):
            raise ReleaseError("Changed native input while staging")
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        _put(target, content)
    _put(destination / "Dockerfile", payloads["ops/Dockerfile.hermes"])
    _inventory(destination, set(expected), prepared=False)
    _sync_tree(destination)
