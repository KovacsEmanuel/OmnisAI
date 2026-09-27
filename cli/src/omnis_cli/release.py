"""Explicit installation of a locally built, checksum-bound P0 control bundle."""

import ctypes
import fcntl
import hashlib
import json
import os
import re
import shutil
import stat
import tempfile
from pathlib import Path

from .instance import private_dir, unique_pairs


class ReleaseError(ValueError):
    """Refuse an untrusted, incompatible or already changed local release."""


_RELEASE = "0.1.0"
_SCHEMA = "0004_pairing_receipts"
_BASE_FILES = {
    f"api/omnis_api-{_RELEASE}-py3-none-any.whl",
    f"cli/omnis_cli-{_RELEASE}-py3-none-any.whl",
    "api/requirements.txt",
    "ops/Dockerfile",
    "ops/compose.yaml",
    "web/omnis-web.json",
    "web/index.html",
}
_ASSET = re.compile(r"web/assets/[A-Za-z0-9_-]+\.(?:js|css|woff2|txt)\Z")
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")


def _bytes(path: Path, *, limit: int = 2 * 1024 * 1024) -> bytes:
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as source:
        info = os.fstat(source.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ReleaseError("Invalid release file")
        content = source.read(limit + 1)
        if len(content) > limit:
            raise ReleaseError("Release file exceeds limit")
        return content


def _manifest(root: Path) -> tuple[bytes, dict[str, bytes]]:
    private_dir(root)
    source = _bytes(root / "release.json", limit=32768)
    raw: object = json.loads(source, object_pairs_hook=unique_pairs)
    if not isinstance(raw, dict) or set(raw) != {
        "format",
        "release",
        "schema",
        "platform",
        "files",
    }:
        raise ReleaseError("Invalid release manifest")
    if (
        type(raw["format"]) is not int
        or raw["format"] != 1
        or raw["release"] != _RELEASE
        or raw["schema"] != _SCHEMA
        or raw["platform"] != "linux/amd64"
        or not isinstance(raw["files"], dict)
    ):
        raise ReleaseError("Incompatible release")
    files = raw["files"]
    if (
        not _BASE_FILES <= set(files)
        or not len(_BASE_FILES) <= len(files) <= 128
        or not any(name.endswith(".js") for name in files)
        or any(name not in _BASE_FILES and not _ASSET.fullmatch(name) for name in files)
    ):
        raise ReleaseError("Unsupported release file set")
    expected_dirs = {"api", "cli", "ops", "web", "web/assets"}
    found: set[str] = set()
    for parent, dirs, entries in os.walk(root, followlinks=False):
        relative = Path(parent).relative_to(root)
        for directory in dirs:
            child = Path(parent) / directory
            name = (relative / directory).as_posix()
            if name not in expected_dirs or not stat.S_ISDIR(child.lstat().st_mode):
                raise ReleaseError("Unexpected release directory")
        for entry in entries:
            name = (relative / entry).as_posix()
            if name != "release.json":
                found.add(name)
    if found != set(files):
        raise ReleaseError("Unlisted or missing release file")
    result: dict[str, bytes] = {}
    total = 0
    for name, expected in files.items():
        if not isinstance(expected, str) or not _DIGEST.fullmatch(expected):
            raise ReleaseError("Invalid release checksum")
        content = _bytes(root / name)
        total += len(content)
        if total > 8 * 1024 * 1024 or hashlib.sha256(content).hexdigest() != expected:
            raise ReleaseError("Release checksum mismatch")
        result[name] = content
    return source, result


def _owned_data_home(data_home: Path) -> None:
    if not data_home.is_absolute() or data_home.resolve() != data_home:
        raise ReleaseError("Invalid data home")
    missing = []
    existing = data_home
    while not existing.exists():
        if existing.is_symlink():
            raise ReleaseError("Symlink in data home")
        missing.append(existing)
        existing = existing.parent
    info = existing.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o002:
        raise ReleaseError("Unsafe data home")
    # The private release root is created only under a canonical owner directory.
    protected = False
    for parent in reversed(existing.parents):
        ancestor = parent.lstat()
        if (
            not stat.S_ISDIR(ancestor.st_mode)
            or ancestor.st_uid not in {0, os.getuid()}
            or ancestor.st_mode & 0o002
            or (ancestor.st_mode & 0o020 and not protected)
        ):
            raise ReleaseError("Replaceable data home ancestor")
        if ancestor.st_uid == os.getuid() and ancestor.st_mode & 0o077 == 0:
            protected = True
    for path in reversed(missing):
        path.mkdir(mode=0o700)
        private_dir(path)


def publish_directory(stage: Path, destination: Path) -> None:
    """Linux atomic rename with NOREPLACE; a new empty target is still a conflict."""
    libc = ctypes.CDLL(None, use_errno=True)
    operation = libc.renameat2
    operation.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    ]
    operation.restype = ctypes.c_int
    if operation(-100, os.fsencode(stage), -100, os.fsencode(destination), 1) != 0:
        code = ctypes.get_errno()
        raise OSError(code, os.strerror(code))


def _put(path: Path, content: bytes) -> None:
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as output:
        output.write(content)
        output.flush()
        os.fsync(output.fileno())


def install_release(bundle: Path, data_home: Path) -> Path:
    """Install only a verified, immutable-version bundle; never start or migrate."""
    try:
        manifest, payloads = _manifest(bundle)
        if bundle == data_home or bundle in data_home.parents or data_home in bundle.parents:
            raise ReleaseError("Bundle and data home must not overlap")
        _owned_data_home(data_home)
        root = data_home / "omnis"
        root.mkdir(mode=0o700, exist_ok=True)
        private_dir(root)
        fd = os.open(root / "install.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            info = os.fstat(fd)
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) != 0o600
                or info.st_nlink != 1
            ):
                raise ReleaseError("Unsafe install lock")
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise ReleaseError("Another install is active") from None
            return _install_locked(root, manifest, payloads)
        finally:
            os.close(fd)
    except (OSError, ValueError, UnicodeError, RecursionError) as exc:
        raise ReleaseError("Release installation refused") from exc


def _installed_pointer(path: Path) -> bool:
    if not path.exists() and not path.is_symlink():
        return False
    info = path.lstat()
    if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600:
        raise ReleaseError("Unsafe installed pointer")
    value: object = json.loads(_bytes(path, limit=1024), object_pairs_hook=unique_pairs)
    if value != {"format": 1, "release": _RELEASE}:
        raise ReleaseError("Another release is installed")
    return True


def _install_locked(root: Path, manifest: bytes, payloads: dict[str, bytes]) -> Path:
    try:
        releases = root / "releases"
        releases.mkdir(mode=0o700, exist_ok=True)
        private_dir(releases)
        destination = releases / _RELEASE
        pointer = root / "installed.json"
        present = _installed_pointer(pointer)
        if destination.exists() or destination.is_symlink():
            existing, existing_files = _manifest(destination)
            if existing != manifest or existing_files != payloads:
                raise ReleaseError("Installed release differs from bundle")
        else:
            stage = Path(tempfile.mkdtemp(prefix=".install-", dir=releases))
            try:
                for name, content in payloads.items():
                    target = stage / name
                    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                    _put(target, content)
                _put(stage / "release.json", manifest)
                # A competing empty directory cannot be silently replaced either.
                try:
                    publish_directory(stage, destination)
                except FileExistsError:
                    existing, existing_files = _manifest(destination)
                    if existing != manifest or existing_files != payloads:
                        raise ReleaseError("Concurrent release differs") from None
            finally:
                if stage.exists():
                    shutil.rmtree(stage)
        if not present:
            fd, name = tempfile.mkstemp(prefix=".installed-", dir=root)
            try:
                with os.fdopen(fd, "wb") as output:
                    output.write(b'{"format":1,"release":"0.1.0"}\n')
                    output.flush()
                    os.fsync(output.fileno())
                try:
                    os.link(name, pointer, follow_symlinks=False)
                except FileExistsError:
                    if not _installed_pointer(pointer):
                        raise ReleaseError("Competing installed pointer disappeared") from None
            finally:
                Path(name).unlink(missing_ok=True)
        if not _installed_pointer(pointer):
            raise ReleaseError("Installed pointer disappeared before readback")
        return destination
    except (OSError, ValueError, UnicodeError, RecursionError) as exc:
        raise ReleaseError("Release installation refused") from exc
