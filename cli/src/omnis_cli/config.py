"""Non-secret operator configuration, independent of the working directory."""

import os
import tomllib
from pathlib import Path

from .instance import private_dir, private_file
from .lifecycle import StartError

_KEYS = {"port", "startup_timeout_seconds", "shutdown_timeout_seconds", "cleanup_timeout_seconds"}


def load_config() -> dict[str, object]:
    base = os.environ.get("XDG_CONFIG_HOME")
    root = (Path(base) if base else Path.home() / ".config") / "omnis"
    path = root / "config.toml"
    try:
        if not os.path.lexists(path):
            return {}
        private_dir(root)
        raw: dict[str, object] = tomllib.loads(private_file(path, limit=4096))
        if set(raw) - _KEYS:
            raise ValueError("Unknown configuration field")
        return raw
    except (OSError, ValueError):
        raise StartError("CONFIG_INVALID", 2) from None
