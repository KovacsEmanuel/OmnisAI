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
from .start_runtime import ControlRuntime, private_identity
from .stop import readback_stopped
from .stop_receipt import completed_receipt, encoded, receipt_path, uuid, validate_grant

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

    private_dir(root)
    if "," in str(root) or "\n" in str(root):
        raise StartError("COLD_MOUNT_PATH_INVALID", 4)
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

    if restore:
        helper(runtime, root, "sync", "-f", "/data", writable=True)


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
    remaining(runtime.deadline, 180)
    _sync_dir(stage)
    publish_directory(stage, output)
    _sync_dir(output.parent)


def snapshot_metadata(
    runtime: ControlRuntime, snapshot: Path, *, full: bool
) -> tuple[dict[str, object], dict[str, object]]:
    from .stop import _stopping_record

    private_dir(snapshot)
    manifest = read_record(snapshot / "manifest.json")
    if (
        set(manifest)
        != {
            "version",
            "profile",
            "release",
            "schema",
            "release_digest",
            "instance_id",
            "system_id",
            "files",
        }
        or type(manifest["version"]) is not int
        or manifest["version"] != 1
        or manifest["profile"] != PROVIDER_SETTINGS_PROFILE
        or not runtime.provider_settings
        or manifest["release"] != "0.1.0"
        or manifest["schema"] != "0015_model_test_v2"
        or manifest["release_digest"] != runtime.digest
    ):
        raise StartError("COLD_SNAPSHOT_INCOMPATIBLE", 4)
    uuid(manifest["instance_id"])
    files = mapping(manifest["files"])
    if set(files) != set(LIMITS):
        raise StartError("COLD_MANIFEST_INVALID", 4)
    expected_names = (
        set(LIMITS) | {"manifest.json"}
        if full
        else {"startup.json", "completion.json", "manifest.json"}
    )
    if {p.name for p in snapshot.iterdir()} != expected_names:
        raise StartError("COLD_FILE_SET_INVALID", 4)
    for name, limit in LIMITS.items():
        expected = mapping(files[name])
        if (
            set(expected) != {"size", "sha256"}
            or type(expected["size"]) is not int
            or not 0 <= int(str(expected["size"])) <= limit
            or not isinstance(expected["sha256"], str)
            or re.fullmatch(r"[0-9a-f]{64}", str(expected["sha256"])) is None
        ):
            raise StartError("COLD_MANIFEST_INVALID", 4)
        if (full or name in {"startup.json", "completion.json"}) and encoded(
            digest(snapshot / name, limit)
        ) != encoded(expected):
            raise StartError("COLD_SNAPSHOT_TAMPERED", 4)
    old = read_record(snapshot / "startup.json")
    _stopping_record(old)
    completion = read_record(snapshot / "completion.json")
    grant = mapping(completion.get("grant"))
    validate_grant(grant, old, mapping(grant.get("inventory")))
    completed_receipt(snapshot / "completion.json", grant)
    if (
        old.get("phase") != "STOPPED"
        or old.get("format") != 5
        or old.get("instance_id") != manifest["instance_id"]
        or old.get("system_id") != manifest["system_id"]
        or old.get("release_digest") != manifest["release_digest"]
        or old.get("project") != runtime.receipt.project
    ):
        raise StartError("COLD_SNAPSHOT_INCOMPATIBLE", 4)
    return manifest, old


def restore(runtime: ControlRuntime, root: Path, snapshot: Path, key: Path | None) -> None:
    from .start import _pgdata_identity

    if not os.environ.get("XDG_STATE_HOME"):
        raise StartError("COLD_EXPLICIT_TARGET_REQUIRED", 4)
    private_dir(root.parent)
    if not root.is_absolute() or root.resolve() != root or os.path.lexists(root):
        raise StartError("COLD_DESTINATION_EXISTS", 4)
    manifest, old = snapshot_metadata(runtime, snapshot, full=True)
    config = load_config()
    config.check_port(old["port"])
    validate_tar(snapshot / "postgres.tar", runtime.deadline)
    master = private_bytes(key, 32) if key is not None else None
    if master is not None and len(master) != 32:
        raise StartError("COLD_KEY_INVALID", 4)
    if (
        runtime.ids()
        or runtime.inspect("network", runtime.receipt.project + "_control") is not None
    ):
        raise StartError("PREEXISTING_RESOURCES_REFUSED", 4)
    stage = Path(tempfile.mkdtemp(prefix=".cold-restore-", dir=root.parent))
    for name in ("vault", "vault-key", "restore-source"):
        (stage / name).mkdir(mode=0o700)
    (stage / "postgres").mkdir(mode=0o711)
    (stage / "postgres").chmod(0o711)
    for name in ("startup.json", "completion.json", "manifest.json"):
        _put(stage / "restore-source" / name, private_bytes(snapshot / name, 16384))
    password = private_bytes(snapshot / "db-password", 64)
    if re.fullmatch(rb"[0-9a-f]{48}\n?", password) is None:
        raise StartError("DATABASE_SECRET_INVALID", 4)
    _put(stage / "db-password", password)
    ciphertext = private_bytes(snapshot / "vault.json", LIMITS["vault.json"])
    if ciphertext:
        _put(stage / "vault/vault.json", ciphertext)
    if master is not None:
        _put(stage / "vault-key/master.key", master)
    fd = os.open(snapshot / "postgres.tar", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        # The opened payload must still be the exact hash admitted above.
        if (
            digest(snapshot / "postgres.tar", ARCHIVE_LIMIT)
            != mapping(manifest["files"])["postgres.tar"]
        ):
            raise StartError("COLD_SNAPSHOT_TAMPERED", 4)
        admitted_info = os.fstat(fd)
        path_info = (snapshot / "postgres.tar").lstat()
        if (
            admitted_info.st_dev,
            admitted_info.st_ino,
            admitted_info.st_size,
            admitted_info.st_mtime_ns,
            admitted_info.st_ctime_ns,
        ) != (
            path_info.st_dev,
            path_info.st_ino,
            path_info.st_size,
            path_info.st_mtime_ns,
            path_info.st_ctime_ns,
        ):
            raise StartError("COLD_SNAPSHOT_TAMPERED", 4)
        archive(runtime, stage, fd, restore=True)
        after = os.fstat(fd)
        if any(
            getattr(admitted_info, key) != getattr(after, key)
            for key in (
                "st_dev",
                "st_ino",
                "st_size",
                "st_mtime_ns",
                "st_ctime_ns",
                "st_nlink",
                "st_mode",
            )
        ):
            raise StartError("COLD_SNAPSHOT_TAMPERED", 4)
    finally:
        os.close(fd)
    if cold_identity(runtime, stage) != old["system_id"]:
        raise StartError("DATABASE_IDENTITY_MISMATCH", 4)
    snapshot_metadata(runtime, snapshot, full=True)
    write_record(
        stage / "instance.json",
        {
            "version": 1,
            "instance_id": manifest["instance_id"],
            "release": manifest["release"],
            "schema": manifest["schema"],
            "project": runtime.receipt.project,
            "origin": f"http://127.0.0.1:{old['port']}",
        },
    )
    paths = [
        "db-password",
        *(["vault/vault.json"] if ciphertext else []),
        *(["vault-key/master.key"] if master is not None else []),
    ]
    marker: dict[str, object] = {
        "version": 1,
        "state": "STOPPED",
        "restore_id": str(uuid4()),
        "manifest_sha256": hashlib.sha256(
            private_bytes(stage / "restore-source/manifest.json", 16384)
        ).hexdigest(),
        "root_identity": private_identity(stage),
        "pgdata_identity": _pgdata_identity(stage),
        "vault_identity": private_identity(stage / "vault"),
        "vault_key_identity": private_identity(stage / "vault-key"),
        "files": {name: digest(stage / name, 8 * 1024 * 1024) for name in paths},
    }
    write_record(stage / "restore.json", marker)
    for directory in (stage / "vault", stage / "vault-key", stage / "restore-source", stage):
        _sync_dir(directory)
    admit_restore(runtime, stage)
    remaining(runtime.deadline, 180)
    publish_directory(stage, root)
    _sync_dir(root.parent)
    admit_restore(runtime, root)


def admit_restore(runtime: ControlRuntime, root: Path) -> dict[str, object]:
    from .start import _pgdata_identity

    marker = read_record(root / "restore.json")
    if {p.name for p in root.iterdir()} - {
        "restore.json",
        "restore-source",
        "instance.json",
        "db-password",
        "postgres",
        "vault",
        "vault-key",
        "lifecycle.lock",
    }:
        raise StartError("RESTORE_ADMISSION_INVALID", 4)
    if (
        set(marker)
        != {
            "version",
            "state",
            "restore_id",
            "manifest_sha256",
            "root_identity",
            "pgdata_identity",
            "vault_identity",
            "vault_key_identity",
            "files",
        }
        or type(marker["version"]) is not int
        or marker["version"] != 1
        or marker["state"] != "STOPPED"
        or marker["root_identity"] != private_identity(root)
        or marker["pgdata_identity"] != _pgdata_identity(root)
        or marker["vault_identity"] != private_identity(root / "vault")
        or marker["vault_key_identity"] != private_identity(root / "vault-key")
        or marker["manifest_sha256"]
        != hashlib.sha256(private_bytes(root / "restore-source/manifest.json", 16384)).hexdigest()
        or os.path.lexists(root / "unreconciled.json")
    ):
        raise StartError("RESTORE_ADMISSION_INVALID", 4)
    uuid(marker["restore_id"])
    manifest, old = snapshot_metadata(runtime, root / "restore-source", full=False)
    files = mapping(marker["files"])
    actual = {"db-password"}
    for directory, allowed in (("vault", "vault.json"), ("vault-key", "master.key")):
        entries = {p.name for p in (root / directory).iterdir()}
        if entries - {allowed}:
            raise StartError("RESTORE_ADMISSION_INVALID", 4)
        actual.update(directory + "/" + name for name in entries)
    if set(files) != actual or any(
        encoded(digest(root / name, 8 * 1024 * 1024)) != encoded(files[name]) for name in files
    ):
        raise StartError("RESTORE_ADMISSION_INVALID", 4)
    source_files = mapping(manifest["files"])
    instance = load_instance(root)
    if (
        files["db-password"] != source_files["db-password"]
        or ("vault/vault.json" in files and files["vault/vault.json"] != source_files["vault.json"])
        or ("vault/vault.json" not in files and mapping(source_files["vault.json"])["size"] != 0)
        or instance.instance_id != old["instance_id"]
        or instance.project != runtime.receipt.project
        or instance.release != manifest["release"]
        or instance.schema != manifest["schema"]
        or instance.origin != f"http://127.0.0.1:{old['port']}"
    ):
        raise StartError("RESTORE_ADMISSION_INVALID", 4)
    # This is current admission data, not a replacement historical startup receipt.
    admitted = {
        key: old[key]
        for key in (
            "format",
            "attempt",
            "instance_id",
            "system_id",
            "port",
            "stop_command",
            "stop_generation",
            "supervisor_epoch",
        )
    }
    admitted.update(
        pgdata_identity=marker["pgdata_identity"],
        vault_identity=marker["vault_identity"],
        vault_key_identity=marker["vault_key_identity"],
    )
    return admitted


def prepare_restore(runtime: ControlRuntime, root: Path, attempt: str) -> dict[str, object]:
    from .restart import _prepare_reconciliation

    current = admit_restore(runtime, root)
    if cold_identity(runtime, root) != current["system_id"]:
        raise StartError("DATABASE_IDENTITY_MISMATCH", 4)
    raw = private_bytes(root / "restore-source/startup.json", 16384)
    completion = private_bytes(root / "restore-source/completion.json", 16384)
    command = uuid(current["stop_command"])
    _put(root / f"stop-{command}.json", completion)  # Byte-exact provenance only.
    marker = read_record(root / "restore.json")
    intent = _prepare_reconciliation(
        root, current, attempt, raw, completion, restore_id=uuid(marker["restore_id"])
    )
    marker["state"] = "STARTING"
    write_record(root / "restore.json", marker, replace=True)
    return intent


def cold_command(command: str, path: Path, key: Path | None = None) -> int:
    try:
        config = load_config()
        root = state_dir()
        config.check_instance(root)
        data = os.environ.get("XDG_DATA_HOME")
        data_home = Path(data) if data else Path.home() / ".local/share"
        runtime = ControlRuntime(data_home, time.monotonic() + 180)
        with lifecycle_lock(data_home / "omnis", runtime.deadline):
            if command == "restore":
                restore(runtime, root, path, key)
            else:
                with lifecycle_lock(root, runtime.deadline):
                    backup(runtime, root, path)
        print(
            (
                "RESTORE_COMPLETED: target STOPPED; Start explicit necesar; cheia absentă rămâne LOCKED."
                if command == "restore"
                else "BACKUP_COMPLETED: snapshot privat; cheia master este separată; sursa rămâne STOPPED."
            )
        )
        return 0
    except (OSError, ValueError, tarfile.TarError, KeyboardInterrupt) as exc:
        reason = exc.reason if isinstance(exc, StartError) else "COLD_OPERATION_REFUSED"
        print(f"{reason}: datele sunt păstrate; nu relansați automat.")
        return 4
