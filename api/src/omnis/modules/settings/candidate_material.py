"""Exact source capture and fsync/no-overwrite private material finalization."""

import ctypes
import hashlib
import os
import stat
from pathlib import Path
from uuid import uuid4

from .catalog_models import CatalogError, Manifest, Procedure, Profile
from .catalog_schema import canonical, dto
from .skill_catalog import read_file, safe_path

MAX_MATERIAL_BYTES = 8 * 1048576
MAX_SOURCE_PACKAGES = 127  # The mandatory profile occupies the 128th source-ref slot.


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def private_root(root: Path) -> Path:
    if not root.is_absolute() or root != root.resolve():
        raise CatalogError("UNSAFE_CATALOG_ROOT")
    if not root.exists():
        root.mkdir(mode=0o700)
    info = root.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise CatalogError("UNSAFE_CATALOG_ROOT")
    for name in ("drafts", "candidates", "staging"):
        directory = root / name
        directory.mkdir(mode=0o700, exist_ok=True)
        info = directory.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise CatalogError("UNSAFE_CATALOG_ROOT")
        sync_directory(directory)
    # Flush namespace entries bottom-up before any DB record can cite material.
    sync_directory(root)
    sync_directory(root.parent)
    return root


def files_at(root: Path) -> set[str]:
    result: set[str] = set()
    count = 0
    for directory, directories, files in os.walk(root, followlinks=False):
        for name in [*directories, *files]:
            count += 1
            path = Path(directory) / name
            info = path.lstat()
            if (
                count > 256
                or path.is_symlink()
                or not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode))
            ):
                raise CatalogError("UNSAFE_FILE")
        for name in files:
            result.add(str((Path(directory) / name).relative_to(root)))
    return result


def capture(
    packages: list[str], profile: str
) -> tuple[dict[str, bytes], list[dict[str, object]], str]:
    if not 1 <= len(packages) <= MAX_SOURCE_PACKAGES:
        raise CatalogError("COUNT_LIMIT")
    material: dict[str, bytes] = {}
    sources: list[dict[str, object]] = []
    seen: set[str] = set()
    for number, path in enumerate(packages):
        root = Path(path)
        raw = read_file(root / "omnis.yaml", 262144)
        manifest = dto(raw, Manifest)
        if manifest.package_key in seen:
            raise CatalogError("PACKAGE_SHADOW")
        seen.add(manifest.package_key)
        names = ["omnis.yaml", manifest.skill_path, *manifest.procedures, *manifest.support_files]
        if len(names) > 128 or len(set(names)) != len(names):
            raise CatalogError("DUPLICATE_FILE")
        if files_at(root) != set(names):
            raise CatalogError("UNDECLARED_FILE")
        listing: list[dict[str, object]] = []
        identities = [("package", manifest.package_key)]
        identities.extend((b.entity_kind, b.key) for b in manifest.file_bindings)
        identities.extend(("technique", t.key) for t in manifest.techniques)
        prefix = f"packages/{number}"
        for name in sorted(names, key=lambda name: name.encode("utf-8")):
            safe_path(name)
            value = raw if name == "omnis.yaml" else read_file(root / name)
            if name in manifest.procedures:
                identities.append(("procedure", dto(value, Procedure).key))
            material[f"{prefix}/{name}"] = value
            listing.append({"path": name, "sha256": digest(value), "size": len(value)})
        if len(set(identities)) != len(identities):
            raise CatalogError("DUPLICATE_ENTITY")
        sources.append(
            {
                "source_kind": "package",
                "package_key": manifest.package_key,
                "prefix": prefix,
                "files": listing,
                "package_digest": digest(canonical(listing)),
                "identities": [list(item) for item in sorted(identities)],
            }
        )
    raw = read_file(Path(profile), 262144)
    parsed = dto(raw, Profile)
    material["profile.yaml"] = raw
    sources.append(
        {
            "source_kind": "profile",
            "key": parsed.key,
            "prefix": "",
            "files": [{"path": "profile.yaml", "sha256": digest(raw), "size": len(raw)}],
            "identities": [["profile", parsed.key]],
        }
    )
    if sum(len(raw) for raw in material.values()) > MAX_MATERIAL_BYTES:
        raise CatalogError("SIZE_LIMIT")
    package_digests: list[dict[str, object]] = [
        {"package_key": s["package_key"], "digest": s["package_digest"]} for s in sources[:-1]
    ]
    package_digests.sort(key=lambda item: str(item["package_key"]))
    material_digest = digest(
        canonical({"packages": package_digests, "profile_sha256": digest(raw)})
    )
    return material, sources, material_digest


def sync_directory(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def finalize(root: Path, namespace: str, identity: str, material: dict[str, bytes]) -> Path:
    """Orphans remain inert on any exception; never adopt or overwrite a prior directory."""
    stage = root / "staging" / str(uuid4())
    stage.mkdir(mode=0o700)
    for name, raw in material.items():
        safe_path(name)
        path = stage / name
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try:
            with os.fdopen(fd, "wb", closefd=False) as sink:
                sink.write(raw)
                sink.flush()
                os.fchmod(fd, 0o400)
                os.fsync(fd)
        finally:
            os.close(fd)
    for directory, _, _ in os.walk(stage, topdown=False):
        os.chmod(directory, 0o700 if Path(directory) == stage else 0o500)
        sync_directory(Path(directory))
    target = root / namespace / identity
    libc = ctypes.CDLL(None, use_errno=True)
    rename = libc.renameat2
    rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    rename.restype = ctypes.c_int
    if rename(-100, os.fsencode(stage), -100, os.fsencode(target), 1) != 0:
        raise CatalogError("MATERIAL_FINALIZATION_FAILED")
    os.chmod(target, 0o500)
    sync_directory(target)
    sync_directory(root / namespace)
    sync_directory(root / "staging")
    return target


def read_material(
    root: Path, namespace: str, identity: str, sources: list[dict[str, object]]
) -> dict[str, bytes]:
    target = root / namespace / identity
    expected: dict[str, tuple[str, int]] = {}
    for source in sources:
        prefix = source["prefix"]
        files = source["files"]
        if not isinstance(prefix, str) or not isinstance(files, list):
            raise CatalogError("STORAGE_INCOMPATIBLE")
        for item in files:
            if not isinstance(item, dict):
                raise CatalogError("STORAGE_INCOMPATIBLE")
            name, sha, size = item["path"], item["sha256"], item["size"]
            if not isinstance(name, str) or not isinstance(sha, str) or type(size) is not int:
                raise CatalogError("STORAGE_INCOMPATIBLE")
            safe_path(name)
            expected[f"{prefix}/{name}" if prefix else name] = (sha, size)
    if files_at(target) != set(expected):
        raise CatalogError("FROZEN_MATERIAL_MISMATCH")
    for directory, directories, files in os.walk(target):
        for path in [Path(directory), *(Path(directory) / n for n in [*directories, *files])]:
            info = path.lstat()
            if info.st_uid != os.getuid() or info.st_mode & 0o277:
                raise CatalogError("FROZEN_MATERIAL_WRITABLE")
    material: dict[str, bytes] = {}
    for name, (sha, size) in expected.items():
        raw = read_file(target / name)
        if digest(raw) != sha or len(raw) != size:
            raise CatalogError("FROZEN_MATERIAL_MISMATCH")
        material[name] = raw
    return material
