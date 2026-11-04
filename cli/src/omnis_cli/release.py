"""Explicit installation of a locally built, checksum-bound P0 control bundle."""

import ctypes
import fcntl
import hashlib
import io
import json
import os
import re
import shutil
import stat
import tempfile
from email.parser import BytesParser
from pathlib import Path
from zipfile import BadZipFile, ZipFile

from .instance import private_dir, unique_pairs


class ReleaseError(ValueError):
    """Refuse an untrusted, incompatible or already changed local release."""


_RELEASE = "0.1.0"
T1_RELEASE = "0.1.1"
S1_RELEASE = "0.1.2"
S1_SCHEMA = "0019_agent_runs"
_SCHEMA = "0017_model_removal"
PROVIDER_SETTINGS_PROFILE = "t1-provider-settings"
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
    try:
        raw: object = json.loads(source, object_pairs_hook=unique_pairs)
    except RecursionError:
        raise ReleaseError("Invalid release manifest") from None
    if not isinstance(raw, dict):
        raise ReleaseError("Invalid release manifest")
    native = type(raw.get("format")) is int and raw["format"] == 2
    provider_settings = type(raw.get("format")) is int and raw["format"] == 3
    fields = {"format", "release", "schema", "platform", "files"}
    if set(raw) != fields | ({"profile"} if native or provider_settings else set()):
        raise ReleaseError("Invalid release manifest")
    if native and raw["profile"] not in {"p4a-settings-offline", "p4a-codex-auth"}:
        raise ReleaseError("Unsupported release profile")
    if provider_settings and raw["profile"] != PROVIDER_SETTINGS_PROFILE:
        raise ReleaseError("Unsupported release profile")
    if (
        type(raw["format"]) is not int
        or raw["format"] not in (1, 2, 3)
        or (raw["release"], raw["schema"])
        not in (
            (_RELEASE, _SCHEMA),
            (_RELEASE, "0016_provider_models"),
            (T1_RELEASE, _SCHEMA),
            (S1_RELEASE, S1_SCHEMA),
        )
        or raw["release"] in (T1_RELEASE, S1_RELEASE)
        and not provider_settings
        or raw["schema"] == "0016_provider_models"
        and not provider_settings
        or raw["platform"] != "linux/amd64"
        or not isinstance(raw["files"], dict)
    ):
        raise ReleaseError("Incompatible release")
    files = raw["files"]
    version = raw["release"]
    base = {name.replace(_RELEASE, version) for name in _BASE_FILES}
    if native:
        from .native_artifacts import FILES

        base = base | FILES
    model_test = native and "model-test/profile.yaml" in files
    if model_test:
        from .model_test_source import SOURCE_FILES

        if raw["profile"] != "p4a-codex-auth":
            raise ReleaseError("Invalid model test profile")
        base = base | SOURCE_FILES
    if (
        not base <= set(files)
        or not len(base) <= len(files) <= 128
        or not any(name.endswith(".js") for name in files)
        or any(name not in base and not _ASSET.fullmatch(name) for name in files)
    ):
        raise ReleaseError("Unsupported release file set")
    expected_dirs = {"api", "cli", "ops", "web", "web/assets"} | ({"native"} if native else set())
    if model_test:
        from .model_test_source import SOURCE_DIRS

        expected_dirs |= SOURCE_DIRS
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
    if native:
        from .native_artifacts import closure

        closure(result)
    if provider_settings:
        required = {
            "omnis/modules/settings/provider_key_models.py",
            "omnis/modules/settings/provider_key_routes.py",
            "omnis/modules/settings/provider_key_service.py",
            "omnis/modules/settings/provider_vault.py",
            "omnis/migrations/versions/0014_provider_settings.py",
            "omnis/migrations/versions/0015_model_test_v2.py",
            "omnis/migrations/versions/0016_provider_models.py",
            "omnis/migrations/versions/0017_model_removal.py",
            "omnis/modules/settings/provider_model_models.py",
            "omnis/modules/settings/provider_model_routes.py",
            "omnis/modules/settings/provider_model_service.py",
            "omnis/modules/runs/model_test_runtime.py",
            "omnis/modules/runs/model_test_contract.py",
            "omnis/modules/runs/model_test_store.py",
            "omnis/supervisor/model_sender.py",
        }
        if raw["schema"] == "0016_provider_models":
            required.remove("omnis/migrations/versions/0017_model_removal.py")
        if version in (T1_RELEASE, S1_RELEASE):
            required |= {"omnis/migrate.py", "omnis/stop_reconcile.py"}
        if version == S1_RELEASE:
            required |= {
                "omnis/migrations/versions/0018_model_relay_authority.py",
                "omnis/migrations/versions/0019_agent_runs.py",
                "omnis/core/run_schema.py",
                "omnis/modules/runs/run_contract.py",
                "omnis/modules/runs/run_routes.py",
                "omnis/modules/runs/run_runtime.py",
                "omnis/modules/runs/run_store.py",
                "omnis/modules/runs/projections.py",
                "omnis/supervisor/agent_runner.py",
            }
        try:
            with ZipFile(io.BytesIO(result[f"api/omnis_api-{version}-py3-none-any.whl"])) as wheel:
                metadata_name = f"omnis_api-{version}.dist-info/METADATA"
                if (
                    wheel.getinfo(metadata_name).file_size > 32768
                    or wheel.namelist().count(metadata_name) != 1
                ):
                    raise ReleaseError("Provider Settings production closure required")
                api_metadata = BytesParser().parsebytes(wheel.read(metadata_name), headersonly=True)
                core: list[str] = []
                for dependency in api_metadata.get_all("Requires-Dist", []):
                    if not isinstance(dependency, str):
                        raise ReleaseError("Provider Settings production closure required")
                    package = re.match(r"[A-Za-z0-9][A-Za-z0-9._-]*", dependency.lstrip())
                    if package is None:
                        raise ReleaseError("Provider Settings production closure required")
                    # Recognize aliases for refusal, never normalize an accepted pin.
                    if re.sub(r"[-_.]+", "-", package[0]).lower() in {
                        "cryptography",
                        "httpx",
                        "httpcore",
                        "openai",
                        "openai-agents",
                    }:
                        core.append(dependency)
                common = {"cryptography==50.0.1", "httpx==0.28.1", "httpcore==1.0.9"}
                supported = [] if version == S1_RELEASE else [common | {"openai==2.24.0"}]
                if version in (T1_RELEASE, S1_RELEASE):
                    supported.append(common | {"openai==2.45.0", "openai-agents==0.19.0"})
                if (
                    not required <= set(wheel.namelist())
                    or api_metadata.defects
                    or len(core) != len(set(core))
                    or set(core) not in supported
                ):
                    raise ReleaseError("Provider Settings production closure required")
        except (BadZipFile, KeyError):
            raise ReleaseError("Provider Settings wheel required") from None
        if version in (T1_RELEASE, S1_RELEASE):
            try:
                with ZipFile(
                    io.BytesIO(result[f"cli/omnis_cli-{version}-py3-none-any.whl"])
                ) as wheel:
                    metadata = wheel.read(f"omnis_cli-{version}.dist-info/METADATA")
                    if (
                        "omnis_cli/upgrade.py" not in wheel.namelist()
                        or f"Version: {version}\n".encode() not in metadata
                        or b"Requires-Dist:" in metadata
                    ):
                        raise ReleaseError("Standalone upgrade CLI required")
            except (BadZipFile, KeyError):
                raise ReleaseError("Standalone upgrade CLI required") from None
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
        _sync_dir(path.parent)


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


def _sync_dir(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _sync_tree(root: Path) -> None:
    # Files were fsynced on write; make every nested directory entry durable too.
    dirs = [Path(parent) for parent, _, _ in os.walk(root, followlinks=False)]
    for directory in reversed(dirs):
        _sync_dir(directory)


def install_release(bundle: Path, data_home: Path) -> Path:
    """Install only a verified, immutable-version bundle; never start or migrate."""
    try:
        from .start_runtime import refuse_upgrade

        refuse_upgrade(data_home / "omnis")
        manifest, payloads = _manifest(bundle)
        if bundle == data_home or bundle in data_home.parents or data_home in bundle.parents:
            raise ReleaseError("Bundle and data home must not overlap")
        _owned_data_home(data_home)
        root = data_home / "omnis"
        root.mkdir(mode=0o700, exist_ok=True)
        private_dir(root)
        _sync_dir(data_home)
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
    if (
        not isinstance(value, dict)
        or set(value) != {"format", "release"}
        or type(value["format"]) is not int
        or value["format"] != 1
        or value["release"] not in (_RELEASE, T1_RELEASE, S1_RELEASE)
    ):
        raise ReleaseError("Another release is installed")
    return True


def installed_version(root: Path) -> str:
    if not _installed_pointer(root / "installed.json"):
        raise ReleaseError("Release required")
    return str(json.loads(_bytes(root / "installed.json"))["release"])


def _install_locked(
    root: Path, manifest: bytes, payloads: dict[str, bytes], *, activate: bool = True
) -> Path:
    try:
        if activate:
            from .start_runtime import refuse_upgrade

            refuse_upgrade(root)
        releases = root / "releases"
        releases.mkdir(mode=0o700, exist_ok=True)
        private_dir(releases)
        _sync_dir(root)
        version = str(json.loads(manifest)["release"])
        destination = releases / version
        pointer = root / "installed.json"
        present = _installed_pointer(pointer)
        if activate and present and installed_version(root) != version:
            raise ReleaseError("Use explicit upgrade for a different release")
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
        _sync_tree(destination)
        _sync_dir(releases)
        if not activate:
            return destination
        if not present:
            fd, name = tempfile.mkstemp(prefix=".installed-", dir=root)
            try:
                with os.fdopen(fd, "wb") as output:
                    output.write((json.dumps({"format": 1, "release": version}) + "\n").encode())
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
        _sync_dir(root)
        return destination
    except (OSError, ValueError, UnicodeError, RecursionError) as exc:
        raise ReleaseError("Release installation refused") from exc
