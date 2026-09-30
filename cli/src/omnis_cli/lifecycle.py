"""Private startup journal, bounded lifecycle lock, and pinned host identity."""

import errno
import fcntl
import json
import os
import socket
import stat
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from .instance import private_dir, private_file, unique_pairs
from .release import _owned_data_home, _sync_dir, publish_directory


class StartError(ValueError):
    def __init__(self, reason: str, code: int = 2) -> None:
        super().__init__(reason)
        self.reason = reason
        self.code = code


def remaining(deadline: float, cap: float = 15) -> float:
    value = min(cap, deadline - time.monotonic())
    if value <= 0:
        raise StartError("STARTUP_TIMEOUT", 3)
    return value


def ensure_private(path: Path) -> None:
    try:
        _owned_data_home(path)
        path.mkdir(mode=0o700, exist_ok=True)
        private_dir(path)
        _sync_dir(path.parent)
    except (OSError, ValueError):
        raise StartError("PRIVATE_PATH_INVALID") from None


@contextmanager
def lifecycle_lock(root: Path, deadline: float) -> Iterator[None]:
    private_dir(root)
    fd = os.open(
        root / "lifecycle.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600
    )
    try:
        info = os.fstat(fd)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o600
            or info.st_nlink != 1
        ):
            raise StartError("UNSAFE_LIFECYCLE_LOCK")
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise StartError("LIFECYCLE_BUSY") from None
                time.sleep(min(0.05, deadline - time.monotonic()))
        yield  # Lock contents/PIDs are never authority; do not delete stale locks.
    finally:
        os.close(fd)


def read_record(path: Path) -> dict[str, object]:
    private_dir(path.parent)
    raw: object = json.loads(private_file(path, limit=16384), object_pairs_hook=unique_pairs)
    return mapping(raw)


def mapping(raw: object) -> dict[str, object]:
    if not isinstance(raw, dict) or any(not isinstance(key, str) for key in raw):
        raise StartError("INVALID_RECORD")
    return dict(raw)


def write_record(path: Path, value: dict[str, object], *, replace: bool = False) -> None:
    private_dir(path.parent)
    if replace:
        read_record(path)
    fd, name = tempfile.mkstemp(prefix=".startup-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as output:
            json.dump(value, output, sort_keys=True)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        if replace:
            os.replace(name, path)
        else:
            publish_directory(Path(name), path)
        _sync_dir(path.parent)
    finally:
        Path(name).unlink(missing_ok=True)


def process_identity(pid: int) -> dict[str, object]:
    if type(pid) is not int or pid <= 1:
        raise StartError("FORWARDER_IDENTITY_INVALID", 3)
    root = Path(f"/proc/{pid}")
    details = (root / "stat").read_text().rsplit(")", 1)[1].split()
    if details[0] == "Z" or root.stat().st_uid != os.getuid():
        raise StartError("FORWARDER_NOT_LIVE", 3)
    return {
        "pid": pid,
        "start_ticks": details[19],
        "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
        "executable": str((root / "exe").resolve(strict=True)),
        "argv": (root / "cmdline").read_bytes().decode().rstrip("\0").split("\0"),
    }


def process_sockets(pid: int) -> set[int]:
    sockets: set[int] = set()
    for fd in Path(f"/proc/{pid}/fd").iterdir():
        try:
            link = os.readlink(fd)
        except FileNotFoundError:
            continue  # An unrelated FD can close during this bounded snapshot.
        if link.startswith("socket:["):
            sockets.add(int(link[8:-1]))
    return sockets


def listener_owned(identity: dict[str, object], port: int, inode: int) -> None:
    pid = identity.get("pid")
    if type(pid) is not int or process_identity(pid) != identity:
        raise StartError("FORWARDER_IDENTITY_MISMATCH", 3)
    if inode not in process_sockets(pid):
        raise StartError("FORWARDER_SOCKET_MISMATCH", 3)
    expected = f"0100007F:{port:04X}"
    rows = Path("/proc/net/tcp").read_text().splitlines()[1:]
    if not any(
        row.split()[1] == expected and row.split()[3] == "0A" and row.split()[9] == str(inode)
        for row in rows
    ):
        raise StartError("FORWARDER_LISTENER_MISMATCH", 3)


def cleanup_startup_ipc(root: Path, control: Path) -> list[str]:
    """Only after this fresh attempt's containers and daemon operations are settled.

    Reuse the P0 socket rule: private inode + exclusive service lock + refused
    connection. Never delete lock files, signal metadata PIDs, or touch a live peer.
    """
    problems = []
    for directory, stem in ((root / "http", "api"), (control, "control")):
        path = directory / f"{stem}.sock"
        cap = directory / "control.cap" if stem == "control" else None
        if not os.path.lexists(path) and not (cap and os.path.lexists(cap)):
            continue
        try:
            private_dir(directory)
            fd = os.open(directory / f"{stem}.lock", os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK)
            try:
                info = os.fstat(fd)
                if (
                    not stat.S_ISREG(info.st_mode)
                    or info.st_uid != os.getuid()
                    or stat.S_IMODE(info.st_mode) != 0o600
                    or info.st_nlink != 1
                ):
                    raise StartError("UNSAFE_IPC_LOCK", 4)
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                if os.path.lexists(path):
                    identity = socket_identity(path)
                    with socket.socket(socket.AF_UNIX) as peer:
                        peer.settimeout(0.2)
                        try:
                            peer.connect(str(path))
                        except OSError as exc:
                            if exc.errno != errno.ECONNREFUSED:
                                raise StartError("IPC_OWNERSHIP_UNCERTAIN", 4) from None
                        else:
                            raise StartError("IPC_PEER_STILL_LIVE", 4)
                    if socket_identity(path) != identity:
                        raise StartError("IPC_REPLACED", 4)
                    path.unlink()
                if cap is not None and os.path.lexists(cap):
                    before = cap.lstat()
                    private_file(cap, limit=64)  # Also admits our interrupted/empty private write.
                    after = cap.lstat()
                    if (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino):
                        raise StartError("IPC_REPLACED", 4)
                    cap.unlink()
                _sync_dir(directory)
            finally:
                os.close(fd)
        except (OSError, ValueError):
            problems.append("IPC ownership uncertain")
    return problems


def socket_identity(path: Path) -> list[int]:
    private_dir(path.parent)
    info = path.lstat()
    if (
        not stat.S_ISSOCK(info.st_mode)
        or info.st_uid != os.getuid()
        or stat.S_IMODE(info.st_mode) != 0o600
    ):
        raise StartError("UNSAFE_IPC", 3)
    return [info.st_dev, info.st_ino]
