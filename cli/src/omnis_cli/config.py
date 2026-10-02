"""Non-secret operator configuration, independent of the working directory."""

import os
import stat
import tomllib
from dataclasses import dataclass
from pathlib import Path

from .instance import load_instance, private_dir, private_file
from .lifecycle import StartError

_KEYS = {"port", "startup_timeout_seconds", "shutdown_timeout_seconds", "cleanup_timeout_seconds"}


@dataclass(frozen=True)
class Config:
    # None preserves the distinction between an explicit selection and defaults.
    port: int | None = None
    startup_timeout_seconds: int = 180
    shutdown_timeout_seconds: int = 180
    cleanup_timeout_seconds: int = 100

    def check_port(self, actual: object, explicit: int | None = None) -> None:
        if explicit is not None:
            _integer(explicit, 1024, 65535)
        if any(value is not None and value != actual for value in (self.port, explicit)):
            raise StartError("PORT_CHANGE_REQUIRES_STOP", 2)

    def check_instance(self, root: Path, explicit: int | None = None) -> None:
        if explicit is not None:
            _integer(explicit, 1024, 65535)
        if self.port is None and explicit is None:
            return
        if os.path.lexists(root / "instance.json"):
            try:
                instance = load_instance(root)
            except (OSError, ValueError):
                raise StartError("RECOVERY_REQUIRED", 4) from None
            self.check_port(int(instance.origin.rsplit(":", 1)[1]), explicit)


def _integer(value: object, lower: int, upper: int) -> int:
    if type(value) is not int or not lower <= value <= upper:
        raise StartError("CONFIG_INVALID", 2)
    return value


def load_config() -> Config:
    base = os.environ.get("XDG_CONFIG_HOME")
    root = (Path(base) if base else Path.home() / ".config") / "omnis"
    path = root / "config.toml"
    try:
        if (
            (base and ("\x00" in base or str(Path(base)) != base))
            or not root.is_absolute()
            or root.resolve() != root
        ):
            raise ValueError("Noncanonical configuration location")
        protected = False
        for ancestor in (*reversed(root.parents), root):
            try:
                info = ancestor.lstat()
            except FileNotFoundError:
                break
            if (
                not stat.S_ISDIR(info.st_mode)
                or info.st_uid not in {0, os.getuid()}
                or info.st_mode & 0o002
                or (info.st_mode & 0o020 and not protected)
            ):
                raise ValueError("Replaceable configuration location")
            if info.st_uid == os.getuid() and info.st_mode & 0o077 == 0:
                protected = True
        if os.path.lexists(root):
            private_dir(root)
        if not os.path.lexists(path):
            return Config()
        raw: dict[str, object] = tomllib.loads(private_file(path, limit=4096))
        if set(raw) - _KEYS:
            raise ValueError("Unknown configuration field")
        return Config(
            port=_integer(raw["port"], 1024, 65535) if "port" in raw else None,
            startup_timeout_seconds=_integer(raw.get("startup_timeout_seconds", 180), 30, 300),
            shutdown_timeout_seconds=_integer(raw.get("shutdown_timeout_seconds", 180), 15, 180),
            cleanup_timeout_seconds=_integer(raw.get("cleanup_timeout_seconds", 100), 30, 180),
        )
    except (OSError, ValueError, RecursionError):
        raise StartError("CONFIG_INVALID", 2) from None
