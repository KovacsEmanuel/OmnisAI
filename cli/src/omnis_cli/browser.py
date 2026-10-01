"""Open only the exact origin of an attested, ready installed instance."""

import os
import re
import shutil
import subprocess
import sys

from .lifecycle import StartError
from .verified import verified_instance


def launch(origin: str) -> str:
    """Request OS browser dispatch; exit 0 cannot prove a window or UI session."""
    match = re.fullmatch(r"http://127\.0\.0\.1:([1-9][0-9]{3,4})", origin)
    if match is None or not 1024 <= int(match.group(1)) <= 65535:
        raise StartError("ORIGIN_INVALID")
    opener = shutil.which("xdg-open", path="/usr/bin:/bin")
    if opener is None:
        return "BROWSER_UNAVAILABLE"
    env = {"PATH": "/usr/bin:/bin"}
    for key in (
        "HOME",
        "DISPLAY",
        "WAYLAND_DISPLAY",
        "XDG_RUNTIME_DIR",
        "XDG_CURRENT_DESKTOP",
        "DBUS_SESSION_BUS_ADDRESS",
        "XAUTHORITY",
        "LANG",
    ):
        if key in os.environ:
            env[key] = os.environ[key]
    try:
        result = subprocess.run(
            [opener, origin + "/"],
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=8,
            check=False,
        )
    except FileNotFoundError:
        return "BROWSER_UNAVAILABLE"
    except (OSError, subprocess.SubprocessError):
        return "BROWSER_LAUNCH_FAILED"
    return "BROWSER_LAUNCH_ACCEPTED" if result.returncode == 0 else "BROWSER_LAUNCH_FAILED"


def open_verified(*, expected: dict[str, object] | None = None) -> int:
    try:
        with verified_instance() as (ready, _):
            if expected is not None and any(
                ready.get(key) != expected.get(key)
                for key in ("instance_id", "origin", "generation", "supervisor_epoch")
            ):
                raise StartError("INSTANCE_CHANGED", 4)
            origin = ready["origin"]
            if not isinstance(origin, str):
                raise StartError("ORIGIN_INVALID")
            outcome = launch(origin)
    except StartError as exc:
        print(f"{exc.reason}: fără deschidere de browser.", file=sys.stderr)
        return exc.code
    except (OSError, ValueError):
        print("READINESS_UNAVAILABLE: fără deschidere de browser.", file=sys.stderr)
        return 3
    print(f"Omnis READY: {origin}/ — {outcome}; fereastra/sesiunea nu sunt verificate.")
    if outcome == "BROWSER_UNAVAILABLE":
        print("Deschideți manual originul afișat; serviciile rămân pornite.", file=sys.stderr)
        return 2
    if outcome != "BROWSER_LAUNCH_ACCEPTED":
        print("Deschiderea a eșuat; serviciile rămân pornite.", file=sys.stderr)
        return 3
    return 0
