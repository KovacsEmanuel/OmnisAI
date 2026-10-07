"""Source-bound single slot. PREPARED is a refusal, not an automatic recovery queue.

Only drained, private trees are renamed. DB and filesystem are NOT one atomic
transaction; a failed post-move check leaves a durable incomplete journal.
"""

import asyncio
import ctypes
import fcntl
import hashlib
import json
import os
import re
import stat
import time
from collections.abc import Callable
from pathlib import Path
from typing import Literal, TypeVar
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from omnis.modules.instance.service import InstanceService

LEAVES = (
    "active",
    "active-support/work",
    "active-support/os-home",
    "active-support/codex",
    "active-support/tmp",
    "active-support/managed-empty",
    "active-support/xdg/config",
    "active-support/xdg/cache",
    "active-support/xdg/state",
    "active-support/xdg/data",
)
ROOTS = (".", "control", "archives", "active-support", "active-support/xdg", *LEAVES)
SOURCE_FILES = {
    "hermes_state.py": "134fb1af988fd49407433cf54afa74f2188c93021fc4576bcf2c7174e787c2eb",
    "hermes_state_repair.py": "7af22ad9aa7cf3823e768177c4d56d1827b53f7253d0549e0bd7e3195ff0b14e",
    "hermes_logging.py": "19deccd2c8a71cf0c9cf94f9cc44021a5fb9e8f4dc29df4da30ea7605b9ab84a",
    "hermes_cli/config.py": "854c01bd0e7564dc8e1ff59774993ad2769d1b26ffe6a52a11d91dab5693ff14",
    "hermes_cli/auth.py": "1565d014485f1316e9ed0cf213fa6049c8db3bf6f449b15bfe675219734396b1",
}
MAX_ENTRIES = 4096
MAX_BYTES = 64 * 1024 * 1024
MAX_SECONDS = 1.5
SHARED = {"auth.json", "auth.lock", "config.yaml"}
T = TypeVar("T")


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class Identity(Strict):
    dev: int = Field(ge=0)
    ino: int = Field(gt=0)


class Policy(Strict):
    schema_version: Literal[1]
    instance_id: str
    approval: Literal["B05_INERT"]
    native_commit: Literal["ee5ee84a345204a3b1d6ef6ba1ab747e602867b9"]
    inventory_sha256: Literal["a2020b35cf5cee08d671c3421b81119b8fc7b1beaae4b39cc488eab4c1874cad"]
    source_files: dict[str, str]
    families: list[str]
    support_children: dict[str, list[str]]
    config_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    roots: dict[str, Identity]

    @model_validator(mode="after")
    def bound(self) -> "Policy":
        if (
            self.source_files != SOURCE_FILES
            or set(self.roots) != set(ROOTS)
            or self.families != ["sqlite", "sessions", "logs", "cache", "support"]
            or str(UUID(self.instance_id)) != self.instance_id
        ):
            raise ValueError("Unbound state policy")
        if set(self.support_children) != set(LEAVES) - {"active"}:
            raise ValueError("Unbound support policy")
        for leaf, names in self.support_children.items():
            if (
                len(names) > 128
                or len(set(names)) != len(names)
                or any(
                    not _safe_name(n)
                    or n in {"skills", "plugins", ".hermes"}
                    or n in SHARED
                    or n.startswith(".")
                    for n in names
                )
                or (
                    leaf
                    in {
                        "active-support/os-home",
                        "active-support/codex",
                        "active-support/managed-empty",
                    }
                    and names
                )
            ):
                raise ValueError("Unapproved support children")
        return self


class Node(Identity):
    size: int = Field(ge=0)
    directory: bool
    digest: str | None


class Move(Strict):
    leaf: str
    name: str
    tree: dict[str, Node]


class Receipt(Strict):
    schema_version: Literal[1]
    state: Literal["ACTIVE", "ARCHIVED"]
    instance_id: str
    case_id: str
    owner: str
    epoch: int = Field(ge=1)
    launch_generation: int = Field(ge=0)
    current_generation: int = Field(ge=0)
    boot: str
    policy_sha256: str
    inventory: dict[str, object] | None
    moves: list[Move]

    @model_validator(mode="after")
    def identities(self) -> "Receipt":
        for value in (self.instance_id, self.case_id, self.owner, self.boot):
            if str(UUID(value)) != value:
                raise ValueError("Invalid case receipt identity")
        return self


class Journal(Strict):
    schema_version: Literal[1]
    state: Literal["PREPARED", "COMMITTED"]
    operation: Literal["RESTORE", "ARCHIVE"]
    receipt: Receipt
    parents: dict[str, Identity]


def _unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate state metadata")
        result[key] = value
    return result


def _object(raw: bytes) -> dict[str, object]:
    value: object = json.loads(raw, object_pairs_hook=_unique)
    if not isinstance(value, dict) or any(type(k) is not str for k in value):
        raise ValueError("Invalid state metadata")
    return dict(value)


def inventory(value: object) -> dict[str, object]:
    """Validate the exact frozen projection without importing the native runtime."""
    if type(value) is not dict:
        raise ValueError("Missing bootstrap inventory")
    raw = json.dumps(value, separators=(",", ":"), allow_nan=False).encode()
    if len(raw) > 24 * 1024:
        raise ValueError("Inventory budget")
    obj = _object(raw)
    if (
        set(obj) != {"schema_version", "observation", "scope", "registry", "plugins"}
        or type(obj["schema_version"]) is not int
        or obj["schema_version"] != 1
        or obj["observation"] != "NATIVE_BOOTSTRAP"
        or obj["scope"] != "/state/active"
    ):
        raise ValueError("Invalid bootstrap inventory")
    for family, limit, success, denied in (
        (
            "registry",
            256,
            "REGISTERED_SNAPSHOT",
            {"NOT_INITIALIZED", "NOT_OBSERVED_BUSY", "LIMIT_EXCEEDED", "NOT_OBSERVED_INVALID"},
        ),
        (
            "plugins",
            128,
            "PLUGIN_SNAPSHOT",
            {
                "NOT_INITIALIZED",
                "NOT_OBSERVED_BUSY",
                "NOT_OBSERVED_IN_PROGRESS",
                "LIMIT_EXCEEDED",
                "NOT_OBSERVED_INVALID",
            },
        ),
    ):
        part = obj[family]
        keys = {"status", "count", "entries"} | ({"generation"} if family == "registry" else set())
        if not isinstance(part, dict) or set(part) != keys:
            raise ValueError("Invalid inventory family")
        status_value = part["status"]
        if not isinstance(status_value, str):
            raise ValueError("Invalid inventory status")
        if status_value in denied:
            if any(part[k] is not None for k in keys - {"status"}):
                raise ValueError("Invalid unobserved inventory")
            continue
        entries, count = part["entries"], part["count"]
        if (
            status_value != success
            or type(count) is not int
            or not 0 <= count <= limit
            or not isinstance(entries, list)
            or len(entries) != count
        ):
            raise ValueError("Invalid inventory count")
        if family == "registry" and (type(part["generation"]) is not int or part["generation"] < 0):
            raise ValueError("Invalid registry generation")
        names: list[str] = []
        for row in entries:
            row_keys = (
                {"name", "toolset"}
                if family == "registry"
                else {"name", "loaded", "enabled", "deferred", "error_present"}
            )
            if not isinstance(row, dict) or set(row) != row_keys:
                raise ValueError("Invalid inventory entry")
            for key in row_keys:
                item = row[key]
                if key in {"name", "toolset"}:
                    if (
                        not isinstance(item, str)
                        or not 1 <= len(item) <= 128
                        or any(ord(c) < 32 or ord(c) == 127 for c in item)
                    ):
                        raise ValueError("Invalid inventory name")
                elif type(item) is not bool:
                    raise ValueError("Invalid plugin flag")
            names.append(row["name"])
        if names != sorted(set(names)):
            raise ValueError("Unordered inventory")
    return obj


class Budget:
    def __init__(self, deadline_ns: int) -> None:
        self.deadline = min(deadline_ns, time.monotonic_ns() + int(MAX_SECONDS * 1e9))
        self.entries = 0
        self.bytes = 0

    def check(self, size: int = 0) -> None:
        self.entries += 1
        self.bytes += size
        if (
            self.entries > MAX_ENTRIES
            or self.bytes > MAX_BYTES
            or time.monotonic_ns() >= self.deadline
        ):
            raise ValueError("Case transition budget")


def _info(info: os.stat_result, *, directory: bool = False) -> None:
    if (
        info.st_uid != os.getuid()
        or info.st_mode & 0o022
        or (
            not stat.S_ISDIR(info.st_mode)
            if directory
            else not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode))
        )
        or (stat.S_ISREG(info.st_mode) and info.st_nlink != 1)
    ):
        raise ValueError("Unsafe state path")


def _safe_name(name: str) -> bool:
    return (
        0 < len(os.fsencode(name)) <= 255
        and name not in {".", "..", ".env"}
        and "/" not in name
        and not any(ord(c) < 32 or ord(c) == 127 for c in name)
    )


def _names(fd: int) -> list[str]:
    names: list[str] = []
    with os.scandir(fd) as entries:
        for entry in entries:
            if len(names) >= MAX_ENTRIES or not _safe_name(entry.name):
                raise ValueError("Case directory budget or unsafe name")
            names.append(entry.name)
    return sorted(names)


def _dir(path: Path) -> int:
    # Resolve every ancestor through no-follow dirfds, not just the final leaf.
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.parts[1:]:
            if part == ".":
                continue
            if not _safe_name(part):
                raise ValueError("Unsafe directory component")
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        _info(os.fstat(fd), directory=True)
    except BaseException:
        os.close(fd)
        raise
    return fd


def _read(path: Path, limit: int = 1024 * 1024) -> bytes:
    parent = _dir(path.parent)
    try:
        fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
    finally:
        os.close(parent)
    try:
        info = os.fstat(fd)
        _info(info)
        if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
            raise ValueError("Invalid state file")
        with os.fdopen(fd, "rb", closefd=False) as source:
            return source.read(limit + 1)
    finally:
        os.close(fd)


def _write(path: Path, value: BaseModel) -> None:
    """Private atomic metadata replace + exact readback + directory fsync."""
    parent = _dir(path.parent)
    temp = ".prepared-" + uuid4().hex
    raw = value.model_dump_json().encode()
    try:
        if path.exists() or path.is_symlink():
            _read(path)
        fd = os.open(
            temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent
        )
        with os.fdopen(fd, "wb") as output:
            output.write(raw)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temp, path.name, src_dir_fd=parent, dst_dir_fd=parent)
        os.fsync(parent)
        if _read(path) != raw:
            raise ValueError("State metadata readback failed")
    finally:
        os.close(parent)


def _rename(source_fd: int, target_fd: int, name: str) -> None:
    # Linux RENAME_NOREPLACE: no check-then-clobber and no EXDEV copy fallback.
    libc = ctypes.CDLL(None, use_errno=True)
    call = libc.renameat2
    call.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    call.restype = ctypes.c_int
    encoded = os.fsencode(name)
    if call(source_fd, encoded, target_fd, encoded, 1) != 0:
        code = ctypes.get_errno()
        raise OSError(code, "Case rename refused")


def _file_identity(info: os.stat_result) -> tuple[int, ...]:
    # Reads may update atime; it is not writer mutation or an identity fence.
    return (
        info.st_dev,
        info.st_ino,
        info.st_mode,
        info.st_nlink,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
    )


def _tree(path: Path, budget: Budget, *, normalize: bool = False) -> dict[str, Node]:
    result: dict[str, Node] = {}

    def visit(current: Path, relative: str, depth: int) -> None:
        budget.check()
        if depth > 32:
            raise ValueError("Case tree depth")
        info = current.lstat()
        _info(info)
        directory = stat.S_ISDIR(info.st_mode)
        digest = None
        if directory:
            fd = _dir(current)
            try:
                if normalize:
                    os.fchmod(fd, 0o700)
                for name in _names(fd):
                    if name in {"auth.json", "auth.lock", ".anthropic_oauth.json", ".env"} or any(
                        ord(c) < 32 or ord(c) == 127 for c in name
                    ):
                        raise ValueError("Fallback auth or unsafe case path")
                    visit(current / name, relative + "/" + name, depth + 1)
                os.fsync(fd)
            finally:
                os.close(fd)
        else:
            if info.st_size > MAX_BYTES - budget.bytes:
                raise ValueError("Case transition budget")
            fd = os.open(current, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            try:
                if _file_identity(os.fstat(fd)) != _file_identity(info):
                    raise ValueError("Case file changed")
                if normalize:
                    os.fchmod(fd, 0o600)
                    info = os.fstat(fd)
                sha = hashlib.sha256()
                with os.fdopen(fd, "rb", closefd=False) as source:
                    while chunk := source.read(65536):
                        budget.check(len(chunk))
                        sha.update(chunk)
                os.fsync(fd)
                if _file_identity(os.fstat(fd)) != _file_identity(info):
                    raise ValueError("Case file changed")
                digest = sha.hexdigest()
            finally:
                os.close(fd)
        result[relative] = Node(
            dev=info.st_dev,
            ino=info.st_ino,
            size=0 if directory else info.st_size,
            directory=directory,
            digest=digest,
        )

    visit(path, ".", 0)
    return result


def _allowed(leaf: str, name: str) -> bool:
    if name in {"auth.json", "auth.lock", ".anthropic_oauth.json", ".env"}:
        return False
    if leaf in {"active-support/managed-empty", "active-support/os-home", "active-support/codex"}:
        return False
    if leaf != "active":
        return True
    return name in {
        "sessions",
        "logs",
        "cache",
        "state.db",
        "state.db-wal",
        "state.db-shm",
        "state.db-journal",
        "state.db.repair.lock",
        "state.db.auto-maintenance.lock",
        "state.db.repair-attempts.json",
        "state.db.repair-scratch",
        "state.db.repair-scratch-wal",
        "state.db.repair-scratch-shm",
        "state.db.repair-scratch-journal",
    } or bool(re.fullmatch(r"state\.db\.(?:malformed-backup|backup-staging)-[A-Za-z0-9_.-]+", name))


async def _worker(call: Callable[[], T]) -> T:
    # Cancellation must not release DB/file locks while a worker is still moving.
    task = asyncio.create_task(asyncio.to_thread(call))
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        try:
            await task
        finally:
            raise


class CaseSlot:
    def __init__(
        self,
        root: Path,
        case: UUID,
        instance: UUID,
        owner: UUID,
        epoch: int,
        generation: int,
        boot: str,
    ) -> None:
        if not root.is_absolute() or str(UUID(boot)) != boot:
            raise ValueError("Invalid case slot identity")
        self.root, self.case, self.instance, self.owner = root, case, instance, owner
        self.epoch, self.generation, self.boot = epoch, generation, boot
        self.lock_fd: int | None = None
        self.policy: Policy | None = None
        self.policy_digest = ""
        self.receipt: Receipt | None = None
        self.journal: Journal | None = None

    @property
    def archive_root(self) -> Path:
        return self.root / "archives" / str(self.case)

    def _validate_roots(self, budget: Budget | None = None) -> None:
        if self.policy is None or self.root.resolve(strict=True) != self.root:
            raise ValueError("Unbound state roots")
        device = self.policy.roots["."].dev
        for name, identity in self.policy.roots.items():
            info = (self.root / name).lstat()
            _info(info, directory=True)
            if (
                (info.st_dev, info.st_ino) != (identity.dev, identity.ino)
                or info.st_dev != device
                or stat.S_IMODE(info.st_mode) != 0o700
            ):
                raise ValueError("State root replaced or cross-device")
        config = _read(self.root / "active/config.yaml", 65536)
        if budget is not None:
            budget.check(len(config))
        if hashlib.sha256(config).hexdigest() != self.policy.config_sha256:
            raise ValueError("Unapproved shared config")
        for name in ("auth.json", "auth.lock"):
            info = (self.root / "active" / name).lstat()
            _info(info)
            if not stat.S_ISREG(info.st_mode):
                raise ValueError("Unsafe provider store")
        for leaf in (
            "active-support/managed-empty",
            "active-support/os-home",
            "active-support/codex",
        ):
            fd = _dir(self.root / leaf)
            try:
                with os.scandir(fd) as entries:
                    if next(entries, None) is not None:
                        raise ValueError("Unexpected fallback or managed state")
            finally:
                os.close(fd)

    def _initialize(self) -> None:
        budget = Budget(time.monotonic_ns() + int(MAX_SECONDS * 1e9))
        if self.root.resolve(strict=True) != self.root:
            raise ValueError("Noncanonical state root")
        # Check the fixed path hierarchy before opening any policy or lock.
        for name in ROOTS:
            budget.check()
            fd = _dir(self.root / name)
            os.close(fd)
        raw = _read(self.root / "control/policy.json", 65536)
        budget.check(len(raw))
        self.policy = Policy.model_validate(_object(raw))
        self.policy_digest = hashlib.sha256(raw).hexdigest()
        if self.policy.instance_id != str(self.instance):
            raise ValueError("Case instance mismatch")
        self._validate_roots(budget)
        fd = os.open(self.root / "control/slot.lock", os.O_RDWR | os.O_NOFOLLOW)
        try:
            info = os.fstat(fd)
            _info(info)
            if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600:
                raise ValueError("Unsafe case slot lock")
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BaseException:
            os.close(fd)
            raise
        self.lock_fd = fd
        journal_path = self.root / "control/journal.json"
        if journal_path.exists():
            journal = Journal.model_validate(_object(_read(journal_path)))
            self._bound(journal.receipt, same_case=False)
            if journal.state != "COMMITTED":
                raise ValueError("Incomplete case transition")
        active_path = self.root / "control/active.json"
        if active_path.exists():
            old = Receipt.model_validate(_object(_read(active_path)))
            self._bound(old, same_case=False)
            if old.state != "ARCHIVED":
                raise ValueError("Unclosed active case")

    def _bound(self, receipt: Receipt, *, same_case: bool = True) -> None:
        if (
            receipt.instance_id != str(self.instance)
            or receipt.policy_sha256 != self.policy_digest
            or (same_case and receipt.case_id != str(self.case))
        ):
            raise ValueError("Foreign case receipt")

    def _scan(self, base: Path, budget: Budget, *, shared: bool) -> list[Move]:
        moves: list[Move] = []
        for leaf in LEAVES:
            fd = _dir(base / leaf)
            try:
                for name in _names(fd):
                    budget.check()
                    if shared and leaf == "active" and name in SHARED:
                        continue
                    if not _allowed(leaf, name) or (
                        leaf != "active"
                        and (self.policy is None or name not in self.policy.support_children[leaf])
                    ):
                        raise ValueError("Unclassified case state")
                    tree = _tree(base / leaf / name, budget)
                    if (
                        any(n.dev != self.policy.roots["."].dev for n in tree.values())
                        if self.policy
                        else True
                    ):
                        raise ValueError("Cross-device case state")
                    moves.append(Move(leaf=leaf, name=name, tree=tree))
            finally:
                os.close(fd)
        return moves

    def _receipt(
        self, generation: int, state: Literal["ACTIVE", "ARCHIVED"], moves: list[Move]
    ) -> Receipt:
        return Receipt(
            schema_version=1,
            state=state,
            instance_id=str(self.instance),
            case_id=str(self.case),
            owner=str(self.owner),
            epoch=self.epoch,
            launch_generation=self.generation,
            current_generation=generation,
            boot=self.boot,
            policy_sha256=self.policy_digest,
            inventory=self.receipt.inventory if self.receipt else None,
            moves=moves,
        )

    def _preflight(self, restoring: bool, generation: int, budget: Budget) -> tuple[Path, Path]:
        self._validate_roots(budget)
        active = self._scan(self.root, budget, shared=True)
        archive = self.archive_root
        if restoring and active:
            raise ValueError("Fresh slot is not empty")
        if not archive.exists():
            archive.mkdir(mode=0o700)
            data = archive / "data"
            data.mkdir(mode=0o700)
            for leaf in ("active-support", "active-support/xdg", *LEAVES):
                (data / leaf).mkdir(mode=0o700, parents=True, exist_ok=True)
        fd = _dir(archive)
        try:
            if set(_names(fd)) - {"data", "receipt.json"}:
                raise ValueError("Unknown archive path")
        finally:
            os.close(fd)
        data = archive / "data"
        for name, allowed in (
            (".", {"active", "active-support"}),
            ("active-support", {"work", "os-home", "codex", "tmp", "managed-empty", "xdg"}),
            ("active-support/xdg", {"config", "cache", "state", "data"}),
        ):
            fd = _dir(data / name)
            try:
                if set(_names(fd)) != allowed:
                    raise ValueError("Unknown archive topology")
            finally:
                os.close(fd)
        archived = self._scan(data, budget, shared=False)
        if restoring:
            receipt_path = archive / "receipt.json"
            if receipt_path.exists():
                previous = Receipt.model_validate(_object(_read(receipt_path)))
                self._bound(previous)
                if previous.state != "ARCHIVED" or previous.moves != archived:
                    raise ValueError("Incomplete or changed archive")
            elif archived:
                raise ValueError("Unowned archive data")
            moves, source, target = archived, data, self.root
        else:
            if archived:
                raise ValueError("Archive destination occupied")
            moves, source, target = active, self.root, data
        for move in moves:
            if (target / move.leaf / move.name).exists() or (
                target / move.leaf / move.name
            ).is_symlink():
                raise ValueError("Case destination occupied")
        receipt = self._receipt(generation, "ACTIVE" if restoring else "ARCHIVED", moves)
        parents: dict[str, Identity] = {}
        for base in (source, target):
            for leaf in LEAVES:
                fd = _dir(base / leaf)
                try:
                    info = os.fstat(fd)
                    if self.policy is None or info.st_dev != self.policy.roots["."].dev:
                        raise ValueError("Cross-device case parent")
                    parents[str(base / leaf)] = Identity(dev=info.st_dev, ino=info.st_ino)
                finally:
                    os.close(fd)
        self.journal = Journal(
            schema_version=1,
            state="PREPARED",
            operation="RESTORE" if restoring else "ARCHIVE",
            receipt=receipt,
            parents=parents,
        )
        _write(self.root / "control/journal.json", self.journal)
        return source, target

    def _moves(self, source: Path, target: Path, budget: Budget) -> None:
        if self.journal is None:
            raise ValueError("Missing prepared journal")
        for move in self.journal.receipt.moves:
            budget.check()
            self._validate_roots(budget)
            if _tree(source / move.leaf / move.name, budget) != move.tree:
                raise ValueError("Case source changed")
            src, dst = _dir(source / move.leaf), _dir(target / move.leaf)
            try:
                for fd, path in ((src, source / move.leaf), (dst, target / move.leaf)):
                    info = os.fstat(fd)
                    identity = self.journal.parents[str(path)]
                    if (info.st_dev, info.st_ino) != (identity.dev, identity.ino):
                        raise ValueError("Case parent identity changed")
                _rename(src, dst, move.name)
                os.fsync(src)
                os.fsync(dst)
            finally:
                os.close(src)
                os.close(dst)
            if _tree(target / move.leaf / move.name, budget, normalize=True) != move.tree:
                raise ValueError("Case move readback failed")

    def _commit(self, budget: Budget) -> None:
        if self.journal is None:
            raise ValueError("Missing case journal")
        self._validate_roots(budget)
        self.receipt = self.journal.receipt
        _write(self.root / "control/active.json", self.receipt)
        if self.journal.operation == "ARCHIVE":
            _write(self.archive_root / "receipt.json", self.receipt)
        _write(
            self.root / "control/journal.json",
            self.journal.model_copy(update={"state": "COMMITTED"}),
        )

    async def _transition(self, service: InstanceService, generation: int, restoring: bool) -> None:
        self.journal = None
        try:
            async with service.case_transition(
                self.owner, self.epoch, generation, self.instance, restoring=restoring
            ) as guard:
                budget = Budget(guard.deadline_ns)
                source, target = await _worker(
                    lambda: self._preflight(restoring, generation, budget)
                )
                await guard.verify()
                await _worker(lambda: self._moves(source, target, budget))
                await guard.verify()
                budget.check()
                await _worker(lambda: self._commit(budget))
                await guard.verify()
        except BaseException:
            await _worker(self._invalidate)
            raise

    def _invalidate(self) -> None:
        if self.journal is not None:
            _write(self.root / "control/journal.json", self.journal)

    async def prepare(self, service: InstanceService) -> None:
        await _worker(self._initialize)
        await self._transition(service, self.generation, True)

    def _status(self, status: dict[str, object], expected: str) -> dict[str, object]:
        if (
            status.get("boot") != self.boot
            or type(status.get("generation")) is not int
            or status["generation"] != self.generation
            or type(status.get("epoch")) is not int
            or status["epoch"] != self.epoch
            or status.get("state") != expected
            or status.get("drained") is not (expected == "STOPPED")
        ):
            raise ValueError("Case runtime fence or drain mismatch")
        return inventory(status.get("bootstrap_inventory"))

    async def observe(self, status: dict[str, object]) -> None:
        observed = self._status(status, "READY")
        if self.receipt is None:
            raise ValueError("Case not prepared")
        receipt = self.receipt.model_copy(update={"inventory": observed})
        self.receipt = receipt
        await _worker(lambda: _write(self.root / "control/active.json", receipt))

    async def archive(
        self, service: InstanceService, generation: int, status: dict[str, object]
    ) -> None:
        observed = self._status(status, "STOPPED")
        if self.receipt is None or self.receipt.inventory != observed:
            raise ValueError("Case bootstrap receipt mismatch")
        await self._transition(service, generation, False)

    async def close(self) -> None:
        fd, self.lock_fd = self.lock_fd, None
        if fd is not None:
            await _worker(lambda: os.close(fd))
