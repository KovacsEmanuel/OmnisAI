"""Explicit T1 cold snapshots. No key export, implicit Stop, or live database copy.

shortcut: tar and expanded payload are capped at 1 GiB; larger clusters need a
separately admitted streaming backup format, not a truncated T1 snapshot.
"""

import hashlib
import os
import re
import stat
import tarfile
import tempfile
import time
from pathlib import Path, PurePosixPath
from uuid import uuid4

from .config import load_config
from .instance import control_dir, load_instance, private_dir, state_dir
from .lifecycle import StartError, lifecycle_lock, mapping, read_record, remaining, write_record
from .release import PROVIDER_SETTINGS_PROFILE, _put, _sync_dir, publish_directory
from .start_runtime import ControlRuntime
from .stop import readback_stopped
from .stop_receipt import completed_receipt, receipt_path

ARCHIVE_LIMIT = 1024**3
LIMITS = {
    "db-password": 64,
    "vault.json": 8 * 1024 * 1024,
    "startup.json": 16384,
    "completion.json": 16384,
    "postgres.tar": ARCHIVE_LIMIT,
}


def private_bytes(path: Path, limit: int) -> bytes:
    private_dir(path.parent)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as source:
        info = os.fstat(source.fileno())
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o600
            or info.st_nlink != 1
            or info.st_size > limit
        ):
            raise StartError("COLD_FILE_INVALID", 4)
        data = source.read(limit + 1)
        if len(data) > limit:
            raise StartError("COLD_FILE_INVALID", 4)
    return data


def helper(
    runtime: ControlRuntime,
    root: Path,
    *command: str,
    writable: bool = False,
    stdin_fd: int | None = None,
    stdout_fd: int | None = None,
) -> None:
    """Only the pinned PG image and this owned postgres bind; no input commands."""
    from .start import _pgdata_identity

    identity = _pgdata_identity(root)
    name = runtime.receipt.project + "-cold-" + str(uuid4())
    runtime.check_daemon()
    result = runtime.run(
        "run",
        "--rm",
        "--name",
        name,
        "--label",
        f"com.docker.compose.project={runtime.receipt.project}",
        "--network",
        "none",
        "--pull",
        "never",
        "--platform",
        "linux/amd64",
        "--restart",
        "no",
        "--read-only",
        "--cap-drop",
        "ALL",
        "--cap-add",
        "DAC_OVERRIDE",
        *(("--cap-add", "CHOWN", "--cap-add", "FOWNER") if writable else ()),
        "--security-opt",
        "no-new-privileges:true",
        "--user",
        "0:0",
        *(("--interactive",) if stdin_fd is not None else ()),
        "--mount",
        f"type=bind,src={root / 'postgres'},dst=/data" + ("" if writable else ",readonly"),
        "--entrypoint",
        command[0],
        runtime.pg_image,
        *command[1:],
        stdin_fd=stdin_fd,
        stdout_fd=stdout_fd,
        cap=180,
        effect=True,
    )
    if (
        result.stderr
        or runtime.inspect("container", name) is not None
        or runtime.uncertain
        or not runtime.family_drained
        or _pgdata_identity(root) != identity
    ):
        raise StartError("COLD_HELPER_UNCERTAIN", 4)


def archive(runtime: ControlRuntime, root: Path, fd: int, *, restore: bool = False) -> None:
    helper(
        runtime,
        root,
        "tar",
        "--extract" if restore else "--create",
        "--file=-",
        "--directory=/data",
        *(("--same-owner", "--same-permissions") if restore else (".",)),
        writable=restore,
        stdin_fd=fd if restore else None,
        stdout_fd=None if restore else fd,
    )


def cold_identity(runtime: ControlRuntime, root: Path) -> str:
    # pg_controldata is read-only; capture its finite output through the same owner.
    fd, name = tempfile.mkstemp(prefix=".cold-control-", dir=root)
    try:
        helper(runtime, root, "pg_controldata", "/data/18/docker", stdout_fd=fd)
        os.fsync(fd)
        raw = private_bytes(Path(name), 16384).decode("ascii")
        fields = dict(line.split(":", 1) for line in raw.splitlines() if ":" in line)
        system = fields.get("Database system identifier", "").strip()
        if (
            fields.get("Database cluster state", "").strip() != "shut down"
            or re.fullmatch(r"[0-9]{1,20}", system) is None
        ):
            raise StartError("COLD_CLUSTER_NOT_STOPPED", 4)
        return system
    finally:
        os.close(fd)
        Path(name).unlink(missing_ok=True)


def digest(path: Path, limit: int) -> dict[str, object]:
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as source:
        before = os.fstat(source.fileno())
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_uid != os.getuid()
            or stat.S_IMODE(before.st_mode) != 0o600
            or before.st_nlink != 1
            or before.st_size > limit
        ):
            raise StartError("COLD_FILE_INVALID", 4)
        value, size = hashlib.sha256(), 0
        while part := source.read(65536):
            size += len(part)
            if size > limit:
                raise StartError("COLD_ARCHIVE_LIMIT", 4)
            value.update(part)
        after = os.fstat(source.fileno())
        if any(
            getattr(before, key) != getattr(after, key)
            for key in (
                "st_dev",
                "st_ino",
                "st_mode",
                "st_nlink",
                "st_size",
                "st_mtime_ns",
                "st_ctime_ns",
            )
        ):
            raise StartError("COLD_FILE_CHANGED", 4)
        return {"size": size, "sha256": value.hexdigest()}


def validate_tar(path: Path, deadline: float) -> None:
    names: set[str] = set()
    size = 0
    with tarfile.open(path, mode="r:") as source:
        for member in source:
            remaining(deadline, 180)
            name = member.name.removeprefix("./").rstrip("/")
            parts = PurePosixPath(name).parts
            if name == "." and member.isdir():
                continue
            if (
                not parts
                or parts[0] != "18"
                or any(p in {".", ".."} for p in parts)
                or name.startswith("/")
                or name in names
                or len(names) >= 100000
                or not (member.isfile() or member.isdir())
                or member.pax_headers
                or member.mode & ~0o777
                or member.size < 0
            ):
                raise StartError("COLD_ARCHIVE_INVALID", 4)
            names.add(name)
            size += member.size
            if size > ARCHIVE_LIMIT:
                raise StartError("COLD_ARCHIVE_LIMIT", 4)
    if not {"18/docker/PG_VERSION", "18/docker/global/pg_control"} <= names:
        raise StartError("COLD_ARCHIVE_INVALID", 4)


def backup(runtime: ControlRuntime, root: Path, output: Path) -> None:
    private_dir(output.parent)
    if not output.is_absolute() or output.resolve() != output or os.path.lexists(output):
        raise StartError("COLD_DESTINATION_EXISTS", 4)
    control = control_dir(root)
    record = read_record(root / "startup.json")
    readback_stopped(runtime, root, control, record)
    if not runtime.provider_settings or record.get("format") != 5:
        raise StartError("COLD_PROFILE_INCOMPATIBLE", 4)
    instance = load_instance(root)
    raw = private_bytes(root / "startup.json", 16384)
    completion = private_bytes(receipt_path(root, record), 16384)
    completed_receipt(
        receipt_path(root, record), mapping(read_record(receipt_path(root, record))["grant"])
    )
    if cold_identity(runtime, root) != record["system_id"]:
        raise StartError("DATABASE_IDENTITY_MISMATCH", 4)
    # Failed/uncertain stages are retained privately, never recursively deleted.
    stage = Path(tempfile.mkdtemp(prefix=".cold-backup-", dir=output.parent))
    vault = root / "vault/vault.json"
    payloads = {
        "startup.json": raw,
        "completion.json": completion,
        "db-password": private_bytes(root / "db-password", 64),
        "vault.json": private_bytes(vault, LIMITS["vault.json"]) if os.path.lexists(vault) else b"",
    }
    for name, value in payloads.items():
        _put(stage / name, value)
    fd = os.open(stage / "postgres.tar", os.O_CREAT | os.O_EXCL | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        archive(runtime, root, fd)
        os.fsync(fd)
    finally:
        os.close(fd)
    validate_tar(stage / "postgres.tar", runtime.deadline)
    files = {name: digest(stage / name, limit) for name, limit in LIMITS.items()}
    manifest: dict[str, object] = {
        "version": 1,
        "profile": PROVIDER_SETTINGS_PROFILE,
        "release": instance.release,
        "schema": instance.schema,
        "release_digest": runtime.digest,
        "instance_id": instance.instance_id,
        "system_id": record["system_id"],
        "files": files,
    }
    write_record(stage / "manifest.json", manifest)
    if (
        len(private_bytes(stage / "manifest.json", 16384)) > 16384
        or private_bytes(root / "startup.json", 16384) != raw
        or private_bytes(receipt_path(root, record), 16384) != completion
        or any(
            private_bytes(
                root / ("vault/vault.json" if name == "vault.json" else name), LIMITS[name]
            )
            != value
            for name, value in payloads.items()
            if name in {"db-password", "vault.json"} and value
        )
    ):
        raise StartError("COLD_SOURCE_CHANGED", 4)
    readback_stopped(runtime, root, control, record)
    _sync_dir(stage)
    publish_directory(stage, output)
    _sync_dir(output.parent)


def cold_command(command: str, path: Path, key: Path | None = None) -> int:
    try:
        config = load_config()
        root = state_dir()
        config.check_instance(root)
        data = os.environ.get("XDG_DATA_HOME")
        data_home = Path(data) if data else Path.home() / ".local/share"
        runtime = ControlRuntime(data_home, time.monotonic() + 180)
        with lifecycle_lock(data_home / "omnis", runtime.deadline):
            if command != "backup":
                raise StartError("COLD_RESTORE_NOT_IMPLEMENTED", 4)
            with lifecycle_lock(root, runtime.deadline):
                backup(runtime, root, path)
        print(
            "BACKUP_COMPLETED: snapshot privat; cheia master este separată; sursa rămâne STOPPED."
        )
        return 0
    except (OSError, ValueError, tarfile.TarError, KeyboardInterrupt) as exc:
        reason = exc.reason if isinstance(exc, StartError) else "COLD_OPERATION_REFUSED"
        print(f"{reason}: datele sunt păstrate; nu relansați automat.")
        return 4
