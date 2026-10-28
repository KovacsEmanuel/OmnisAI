"""Open only the exact origin of an attested, ready installed instance."""

import json
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
    desktop = "OMNIS_DESKTOP_" if "OMNIS_DESKTOP_HOME" in os.environ else ""
    for key in (
        "HOME",
        "XDG_CONFIG_HOME",
        "XDG_DATA_HOME",
        "XDG_STATE_HOME",
        "XDG_RUNTIME_DIR",
    ):
        # An empty captured XDG value means desktop defaults, never the private app root.
        if value := os.environ.get(desktop + key):
            env[key] = value
    for key in (
        "DISPLAY",
        "WAYLAND_DISPLAY",
        "XDG_CURRENT_DESKTOP",
        "DBUS_SESSION_BUS_ADDRESS",
        "XAUTHORITY",
        "LANG",
    ):
        if value := os.environ.get(key):
            env[key] = value
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
    except subprocess.TimeoutExpired:
        # The direct opener timed out; a detached browser may still have opened.
        return "BROWSER_LAUNCH_UNCONFIRMED"
    except (OSError, subprocess.SubprocessError):
        return "BROWSER_LAUNCH_FAILED"
    return "BROWSER_LAUNCH_ACCEPTED" if result.returncode == 0 else "BROWSER_LAUNCH_FAILED"


def open_verified(*, expected: dict[str, object] | None = None, as_json: bool = False) -> int:
    outcome = "BROWSER_NOT_INVOKED"
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
    except (StartError, OSError, ValueError) as exc:
        code = exc.code if isinstance(exc, StartError) else 3
        reason = exc.reason if isinstance(exc, StartError) else "READINESS_UNAVAILABLE"
        if as_json:
            result = dict(expected or {})
            for key in ("generation", "supervisor_epoch", "admission_open", "shutdown_finalized"):
                result.pop(key, None)
            print(
                json.dumps(
                    {
                        **result,
                        "state": "REFUSED" if code == 2 else "UNCERTAIN" if code == 4 else "FAILED",
                        "reason": reason,
                        "api_ready": False,
                        "control_ready": False,
                        "dashboard_ready": False,
                        "assessment_ready": False,
                        "browser_opened": False,
                        "browser_outcome": outcome,
                    },
                    sort_keys=True,
                )
            )
        elif outcome == "BROWSER_NOT_INVOKED":
            print(f"{reason}: fără deschidere de browser.", file=sys.stderr)
        else:
            print(
                f"{reason}: {outcome}; fereastra/sesiunea și starea instanței nu sunt verificate.",
                file=sys.stderr,
            )
        return code
    if as_json:
        print(json.dumps({**(expected or ready), "browser_outcome": outcome}, sort_keys=True))
        return {"BROWSER_LAUNCH_ACCEPTED": 0, "BROWSER_UNAVAILABLE": 2}.get(outcome, 3)
    print(f"Omnis READY: {origin}/ — {outcome}; fereastra/sesiunea nu sunt verificate.")
    if outcome == "BROWSER_UNAVAILABLE":
        print("Deschideți manual originul afișat; serviciile rămân pornite.", file=sys.stderr)
        return 2
    if outcome == "BROWSER_LAUNCH_UNCONFIRMED":
        print(
            "Openerul a depășit termenul; fereastra poate exista sau lipsi. Serviciile rămân pornite.",
            file=sys.stderr,
        )
        return 3
    if outcome != "BROWSER_LAUNCH_ACCEPTED":
        print("Deschiderea a eșuat; serviciile rămân pornite.", file=sys.stderr)
        return 3
    return 0
