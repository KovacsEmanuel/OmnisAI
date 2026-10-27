"""Explicit, finite T1 UI-only binding transition; never migrate, restore or start."""

import fcntl
import hashlib
import json
import os
import stat
import subprocess
import time
from pathlib import Path
from uuid import uuid4

from . import compose
from .backup import LIMITS, digest, snapshot_metadata, validate_tar
from .config import load_config
from .instance import control_dir, private_dir
from .lifecycle import StartError, lifecycle_lock, read_record, write_record
from .release import (
    _DIGEST,
    PROVIDER_SETTINGS_PROFILE,
    ReleaseError,
    _install_locked,
    _manifest,
    _sync_dir,
    binding_paths,
)
from .restart import _bytes
from .start_runtime import ControlRuntime
from .stop_receipt import receipt_path, uuid


def compatible(old: tuple[bytes, dict[str, bytes]], new: tuple[bytes, dict[str, bytes]]) -> None:
    manifests = (old, new)
    for raw, _ in manifests:
        value = json.loads(raw)
        if value.get("format") != 3 or value.get("profile") != PROVIDER_SETTINGS_PROFILE:
            raise ReleaseError("Manual upgrade is only for Provider Settings")
    fixed = [
        {name: body for name, body in files.items() if not name.startswith(("web/", "cli/"))}
        for _, files in manifests
    ]
    if fixed[0] != fixed[1]:
        raise ReleaseError("Only web assets and the reviewed CLI wheel may change")


def stopped_runtime(
    runtime: ControlRuntime, root: Path, record: dict[str, object]
) -> ControlRuntime:
    """Use the authentic old binding for Stop proof, not a rewritten old receipt."""
    if runtime.digest == record.get("release_digest"):
        return runtime
    if runtime.uncertain or not runtime.family_drained:
        raise StartError("STOP_READBACK_UNCERTAIN", 4)
    if record.get("phase") != "STOPPED" or record.get("format") != 5:
        raise StartError("RECOVERY_REQUIRED", 4)
    command = uuid(record.get("stop_command"))
    marker = read_record(root / f"upgrade-{command}.json")
    data_root = runtime.release.parent.parent
    pointer = read_record(data_root / "installed.json")
    if (
        set(marker)
        != {
            "version",
            "transition",
            "from",
            "to",
            "state_root",
            "stopped_sha256",
            "completion_sha256",
            "backup_sha256",
        }
        or type(marker["version"]) is not int
        or marker["version"] != 1
        or marker["transition"] != pointer.get("transition")
        or marker["from"] != record.get("release_digest")
        or marker["to"] != runtime.digest
        or marker["state_root"] != str(root)
        or marker["stopped_sha256"] != hashlib.sha256(_bytes(root / "startup.json")).hexdigest()
        or marker["completion_sha256"]
        != hashlib.sha256(_bytes(receipt_path(root, record))).hexdigest()
        or not isinstance(marker["backup_sha256"], str)
        or not _DIGEST.fullmatch(marker["backup_sha256"])
    ):
        raise StartError("UPGRADE_BINDING_INVALID", 4)
    uuid(marker["transition"])
    old = ControlRuntime(data_root.parent, runtime.deadline, release_digest=str(marker["from"]))
    compatible(_manifest(old.release), _manifest(runtime.release))
    if (
        old.receipt.project != runtime.receipt.project
        or old.host != runtime.host
        or old.receipt.docker_id != runtime.receipt.docker_id
        or old.pg_image != runtime.pg_image
    ):
        raise StartError("UPGRADE_BINDING_INVALID", 4)
    return old


def manual_upgrade(bundle: Path, data_home: Path, root: Path, expected: str, backup: Path) -> None:
    from .stop import readback_stopped

    try:
        if not _DIGEST.fullmatch(expected):
            raise ReleaseError("Expected digest required")
        manifest, payloads = _manifest(bundle)
        target = hashlib.sha256(manifest).hexdigest()
        data_root = data_home / "omnis"
        for path in (data_root, root):
            private_dir(path)
        if root == data_root or root in data_root.parents or data_root in root.parents:
            raise ReleaseError("Overlapping state/data roots")
        if bundle == data_home or bundle in data_home.parents:
            raise ReleaseError("Overlapping input")
        deadline = time.monotonic() + 300
        fd = os.open(data_root / "install.lock", os.O_RDWR | os.O_NOFOLLOW)
        try:
            info = os.fstat(fd)
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) != 0o600
                or info.st_nlink != 1
            ):
                raise ReleaseError("Unsafe install lock")
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with lifecycle_lock(data_root, deadline), lifecycle_lock(root, deadline):
                runtime = ControlRuntime(data_home, deadline)
                if runtime.digest != expected or target == expected:
                    raise ReleaseError("Installed digest changed or target is current")
                config = load_config()
                config.check_instance(root)
                record = read_record(root / "startup.json")
                config.check_port(record.get("port"))
                control = control_dir(root)
                readback_stopped(runtime, root, control, record)
                command = uuid(record.get("stop_command"))
                if os.path.lexists(root / f"restart-{command}.json"):
                    raise ReleaseError("Stop grant already admitted for restart")
                old = stopped_runtime(runtime, root, record)
                compatible(_manifest(runtime.release), (manifest, payloads))
                _, saved = snapshot_metadata(old, backup, full=True)
                if saved != record or _bytes(backup / "completion.json") != _bytes(
                    receipt_path(root, record)
                ):
                    raise ReleaseError("Backup is not this Stop completion")
                validate_tar(backup / "postgres.tar", deadline)
                for source, archived, limit in (
                    (root / "db-password", "db-password", 64),
                    (root / "vault/vault.json", "vault.json", LIMITS["vault.json"]),
                ):
                    if os.path.lexists(source):
                        if digest(source, limit) != digest(backup / archived, limit):
                            raise ReleaseError("Backup differs from stopped data")
                    elif (backup / archived).stat().st_size:
                        raise ReleaseError("Backup differs from stopped data")
                # A pre-Start rollback cancels the binding, not the unconsumed Stop grant.
                cancelling = target == old.digest and runtime.digest != old.digest
                if runtime.digest != old.digest and not cancelling:
                    raise ReleaseError("Pending upgrade must be started or rolled back first")
                if cancelling:
                    destination, images = binding_paths(data_root, target)
                    final = compose._record(images / "image.json", target, complete=True)
                    if final != old.receipt:
                        raise ReleaseError("Old image receipt changed")
                else:
                    legacy = data_root / "releases/0.1.0"
                    if hashlib.sha256(_manifest(legacy)[0]).hexdigest() == target:
                        destination, images = binding_paths(data_root, target)
                    else:
                        destination = _install_locked(data_root, manifest, payloads, digest=target)
                        images = data_root / "images"
                        images.mkdir(mode=0o700, exist_ok=True)
                        private_dir(images)
                        _sync_dir(data_root)
                        images = images / target
                        images.mkdir(mode=0o700, exist_ok=True)
                        private_dir(images)
                        _sync_dir(images.parent)
                    final = compose._install_locked(
                        images,
                        destination,
                        target,
                        profile=PROVIDER_SETTINGS_PROFILE,
                        project=runtime.receipt.project,
                    )
                if final is None or (final.project, final.docker_host, final.docker_id) != (
                    runtime.receipt.project,
                    runtime.host,
                    runtime.receipt.docker_id,
                ):
                    raise ReleaseError("Image binding changed")
                readback_stopped(runtime, root, control, record)
                transition = str(uuid4())
                marker = {
                    "version": 1,
                    "transition": transition,
                    "from": old.digest,
                    "to": target,
                    "state_root": str(root),
                    "stopped_sha256": hashlib.sha256(_bytes(root / "startup.json")).hexdigest(),
                    "completion_sha256": hashlib.sha256(
                        _bytes(receipt_path(root, record))
                    ).hexdigest(),
                    "backup_sha256": hashlib.sha256(_bytes(backup / "manifest.json")).hexdigest(),
                }
                if not cancelling:
                    path = root / f"upgrade-{command}.json"
                    if os.path.lexists(path):
                        existing = read_record(path)
                        marker["transition"] = existing.get("transition")
                        uuid(marker["transition"])
                        if existing != marker:
                            raise ReleaseError("Interrupted transition differs")
                        transition = str(marker["transition"])
                    else:
                        write_record(path, marker)
                    if read_record(path) != marker:
                        raise ReleaseError("Transition not durable")
                pointer = {
                    "format": 2,
                    "release": "0.1.0",
                    "digest": target,
                    "transition": transition,
                }
                write_record(data_root / "installed.json", pointer, replace=True)
                if (
                    read_record(data_root / "installed.json") != pointer
                    or binding_paths(data_root)[0] != destination
                ):
                    raise ReleaseError("Installed binding readback failed")
        finally:
            os.close(fd)
    except (OSError, ValueError, UnicodeError, RecursionError, subprocess.SubprocessError) as exc:
        raise ReleaseError("Manual upgrade refused; preserve receipts and data") from exc
