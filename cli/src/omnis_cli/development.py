"""Explicit mutable workspace binding, separate from immutable release identity."""

import hashlib
import json
import os
import re
import stat
from pathlib import Path

from .instance import unique_pairs
from .lifecycle import StartError
from .release import _bytes


def workspace(value: object) -> str:
    # Syntax only: changed/missing content must never prevent Stop receipt parsing.
    if (
        not isinstance(value, str)
        or not 1 < len(value) <= 512
        or any(not 32 <= ord(char) <= 126 for char in value)
        or not value.startswith("/")
        or value.startswith("//")
        or str(Path(value)) != value
        or ".." in Path(value).parts
    ):
        raise ValueError("Invalid development workspace")
    return value


def fields(record: dict[str, object]) -> set[str]:
    if "development_workspace" not in record:
        return set()
    try:
        if type(record.get("format")) is not int or record["format"] != 5:
            raise ValueError("Development requires format5")
        workspace(record["development_workspace"])
    except ValueError:
        raise StartError("RECOVERY_REQUIRED", 4) from None
    return {"development_workspace"}


def selection(record: dict[str, object]) -> str | None:
    return workspace(record["development_workspace"]) if fields(record) else None


def mode(record: dict[str, object]) -> str:
    return "DEVELOPMENT" if selection(record) is not None else "RELEASE"


def mounts(selected: str | None, role: str) -> list[dict[str, object]]:
    if selected is None or role not in {"api", "supervisor"}:
        return []
    root = Path(workspace(selected))
    return [
        {
            "type": "bind",
            "source": str(root / source),
            "target": target,
            "read_only": True,
            "bind": {"create_host_path": False, "propagation": "rprivate"},
        }
        for source, target in (
            ("api/src/omnis", "/usr/local/lib/python3.13/site-packages/omnis"),
            *((("web/dist", "/opt/omnis/web"),) if role == "api" else ()),
        )
    ]


def _owned_path(path: Path, *, directory: bool) -> None:
    if path.resolve(strict=True) != path:
        raise ValueError("Symlink in development path")
    protected = False
    for ancestor in (*reversed(path.parents), path):
        info = ancestor.lstat()
        is_directory = ancestor != path or directory
        if (
            not (stat.S_ISDIR(info.st_mode) if is_directory else stat.S_ISREG(info.st_mode))
            or info.st_uid not in ({os.getuid()} if ancestor == path else {0, os.getuid()})
            or info.st_mode & 0o002
            or info.st_mode & 0o020
            and not protected
            or not is_directory
            and info.st_nlink != 1
        ):
            raise ValueError("Unsafe development path")
        if info.st_uid == os.getuid() and info.st_mode & 0o077 == 0:
            protected = True


def web_files(selected: str) -> dict[str, bytes]:
    """Same finite manifest/byte budgets as API WebAssets; never cache mutable bytes."""
    try:
        root = Path(workspace(selected)) / "web/dist"
        _owned_path(root, directory=True)
        manifest_path = root / "omnis-web.json"
        _owned_path(manifest_path, directory=False)
        source = _bytes(manifest_path, limit=32768)
        manifest = json.loads(source, object_pairs_hook=unique_pairs)
        if (
            type(manifest) is not dict
            or set(manifest) != {"version", "files"}
            or type(manifest["version"]) is not int
            or manifest["version"] != 1
            or type(manifest["files"]) is not dict
            or not 2 <= len(manifest["files"]) <= 128
            or "index.html" not in manifest["files"]
            or not any(name.endswith(".js") for name in manifest["files"])
        ):
            raise ValueError("Invalid development manifest")
        result = {}
        total = 0
        for name, digest in manifest["files"].items():
            if (
                re.fullmatch(r"index\.html|assets/[A-Za-z0-9_-]+\.(?:js|css|woff2|txt)", name)
                is None
                or not isinstance(digest, str)
                or re.fullmatch(r"[0-9a-f]{64}", digest) is None
            ):
                raise ValueError("Invalid development asset")
            path = root / name
            _owned_path(path, directory=False)
            content = _bytes(path)
            total += len(content)
            if total > 8 * 1024 * 1024 or hashlib.sha256(content).hexdigest() != digest:
                raise ValueError("Development asset changed")
            result["web/" + name] = content
        if _bytes(manifest_path, limit=32768) != source:
            raise ValueError("Development manifest changed")
        return result
    except (OSError, ValueError, RecursionError):
        raise StartError("DEVELOPMENT_ASSETS_INVALID", 3) from None


def validate_new(selected: str) -> None:
    """Only new Start reads the package tree; Stop uses observed mount identity."""
    try:
        root = Path(workspace(selected))
        _owned_path(root, directory=True)
        package = root / "api/src/omnis"
        _owned_path(package, directory=True)
        _owned_path(package / "__init__.py", directory=False)
        count = 0
        for parent, dirs, files in os.walk(package, followlinks=False):
            for name in (*dirs, *files):
                count += 1
                if count > 4096:
                    raise ValueError("Development package tree limit")
                _owned_path(Path(parent) / name, directory=name in dirs)
    except (OSError, ValueError):
        raise StartError("DEVELOPMENT_PATH_INVALID", 2) from None
    web_files(selected)
