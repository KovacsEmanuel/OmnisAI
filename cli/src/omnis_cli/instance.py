"""Strict, private, cwd-independent location of the installed instance."""

import json
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID


class InvalidInstance(ValueError):
    """Metadata cannot be trusted; never interpolate the source into an error."""


def private_dir(path: Path) -> None:
    if not path.is_absolute() or path.resolve() != path:
        raise InvalidInstance("Noncanonical private directory")
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise InvalidInstance("Unsafe private directory")
    protected = False
    for parent in reversed(path.parents):
        ancestor = parent.lstat()
        if (
            not stat.S_ISDIR(ancestor.st_mode)
            or ancestor.st_uid not in {0, os.getuid()}
            or ancestor.st_mode & 0o002
            or (ancestor.st_mode & 0o020 and not protected)
        ):
            raise InvalidInstance("Replaceable ancestor")
        if ancestor.st_uid == os.getuid() and ancestor.st_mode & 0o077 == 0:
            protected = True


def private_file(path: Path, *, limit: int) -> str:
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd) as source:
        info = os.fstat(source.fileno())
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o600
            or info.st_nlink != 1
        ):
            raise InvalidInstance("Unsafe private file")
        value = source.read(limit + 1)
        if len(value) > limit:
            raise InvalidInstance("Private file exceeds limit")
        return value


def state_dir() -> Path:
    base = os.environ.get("XDG_STATE_HOME")
    return (Path(base) if base else Path.home() / ".local/state") / "omnis"


def control_dir(root: Path) -> Path:
    runtime = os.environ.get("XDG_RUNTIME_DIR")
    return (Path(runtime) / "omnis") if runtime else (root / "runtime-ipc")


def unique_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise InvalidInstance("Duplicate JSON key")
        result[key] = value
    return result


@dataclass(frozen=True)
class Instance:
    instance_id: str
    release: str
    schema: str
    project: str
    origin: str


def load_instance(root: Path) -> Instance:
    private_dir(root)
    raw = json.loads(
        private_file(root / "instance.json", limit=4096), object_pairs_hook=unique_pairs
    )
    if not isinstance(raw, dict) or set(raw) != {
        "version",
        "instance_id",
        "release",
        "schema",
        "project",
        "origin",
    }:
        raise InvalidInstance("Invalid instance record")
    identity = raw["instance_id"]
    if (
        type(raw["version"]) is not int
        or raw["version"] != 1
        or not isinstance(identity, str)
        or str(UUID(identity)) != identity
        or not isinstance(raw["release"], str)
        or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", raw["release"])
        or raw["schema"] != "0004_pairing_receipts"
        or not isinstance(raw["project"], str)
        or not re.fullmatch(r"omnis-[a-z0-9-]{1,42}", raw["project"])
        or not isinstance(raw["origin"], str)
        or not re.fullmatch(r"http://127\.0\.0\.1:(?:[1-9][0-9]{0,4})", raw["origin"])
        or int(raw["origin"].rsplit(":", 1)[1]) > 65535
    ):
        raise InvalidInstance("Invalid instance identity")
    return Instance(identity, raw["release"], raw["schema"], raw["project"], raw["origin"])
