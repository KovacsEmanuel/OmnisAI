"""Attest a running installed instance before any operator-side pair/open effect."""

import http.client
import os
import subprocess
import time
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from pathlib import Path

from .config import load_config
from .control import ControlUnavailable
from .instance import control_dir, private_dir, state_dir
from .lifecycle import StartError, lifecycle_lock, read_record
from .start import _check_pgdata, _ready_record, verify_running
from .start_runtime import ControlRuntime


@contextmanager
def verified_instance() -> Iterator[tuple[dict[str, object], Path]]:
    """Reuse SL02's full OCI/DB/IPC/HTTP/asset proof, not status's legacy ACK."""
    config = load_config()
    root = state_dir()
    config.check_instance(root)
    data = os.environ.get("XDG_DATA_HOME")
    data_home = Path(data) if data else Path.home() / ".local/share"
    deadline = time.monotonic() + 30
    try:
        # Unlike start, no directory or lifecycle journal may be created here.
        private_dir(data_home / "omnis")
        private_dir(root)
        if os.path.lexists(root / "unreconciled.json"):
            raise StartError("RECOVERY_REQUIRED", 4)
        preflight = read_record(root / "startup.json")
        _ready_record(preflight)
        config.check_port(preflight.get("port"))
        _check_pgdata(root, preflight)
        runtime = ControlRuntime(data_home, deadline)
        with ExitStack() as locks:
            locks.enter_context(lifecycle_lock(data_home / "omnis", deadline))
            locks.enter_context(lifecycle_lock(root, deadline))
            if os.path.lexists(root / "unreconciled.json"):
                raise StartError("RECOVERY_REQUIRED", 4)
            record = read_record(root / "startup.json")
            if record != preflight:
                raise StartError("LIFECYCLE_CHANGED", 4)
            port = record.get("port")
            if type(port) is not int:
                raise StartError("RECOVERY_REQUIRED", 4)
            control = control_dir(root)
            result = verify_running(runtime, root, control, record, port)
            if read_record(root / "startup.json") != record:
                raise StartError("LIFECYCLE_CHANGED", 4)
            yield result, control
    except FileNotFoundError:
        raise StartError("INSTANCE_UNAVAILABLE", 3) from None
    except (ControlUnavailable, http.client.HTTPException, subprocess.SubprocessError):
        raise StartError("READINESS_UNAVAILABLE", 3) from None
    except OSError:
        raise StartError("READINESS_UNAVAILABLE", 3) from None
