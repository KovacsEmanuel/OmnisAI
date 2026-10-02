"""Non-secret operator configuration, independent of the working directory."""

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

from .instance import private_dir, private_file
from .lifecycle import StartError

_KEYS = {"port", "startup_timeout_seconds", "shutdown_timeout_seconds", "cleanup_timeout_seconds"}


@dataclass(frozen=True)
class Config:
    # None preserves the distinction between an explicit selection and defaults.
    port: int | None = None
    startup_timeout_seconds: int = 180
    shutdown_timeout_seconds: int = 180
    cleanup_timeout_seconds: int = 100


def _integer(value: object, lower: int, upper: int) -> int:
    if type(value) is not int or not lower <= value <= upper:
        raise StartError("CONFIG_INVALID", 2)
    return value


def load_config() -> Config:
    base = os.environ.get("XDG_CONFIG_HOME")
    root = (Path(base) if base else Path.home() / ".config") / "omnis"
    path = root / "config.toml"
    try:
        if not os.path.lexists(path):
            return Config()
        private_dir(root)
        raw: dict[str, object] = tomllib.loads(private_file(path, limit=4096))
        if set(raw) - _KEYS:
            raise ValueError("Unknown configuration field")
        return Config(
            port=_integer(raw["port"], 1024, 65535) if "port" in raw else None,
            startup_timeout_seconds=_integer(raw.get("startup_timeout_seconds", 180), 30, 300),
            shutdown_timeout_seconds=_integer(raw.get("shutdown_timeout_seconds", 180), 15, 180),
            cleanup_timeout_seconds=_integer(raw.get("cleanup_timeout_seconds", 100), 30, 180),
        )
    except (OSError, ValueError):
        raise StartError("CONFIG_INVALID", 2) from None
