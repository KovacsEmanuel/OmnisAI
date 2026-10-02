"""Read-only status; a private supervisor ACK is not proof of HTTP ownership."""

import http.client
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from .config import load_config
from .control import ControlUnavailable, request
from .instance import control_dir, load_instance, state_dir
from .lifecycle import StartError, read_record
from .start import _bound_instance, _check_pgdata, _ready_record, verify_running
from .start_runtime import ControlRuntime
from .stop import _stopping_record, readback_stopped


def status(*, as_json: bool) -> int:
    root = state_dir()
    try:
        config = load_config()
        config.check_instance(root)
    except StartError as exc:
        refused = {
            "state": "REFUSED",
            "reason": exc.reason,
            "dashboard_ready": False,
            "control_ready": False,
            "assessment_ready": False,
            "browser_opened": False,
        }
        print(json.dumps(refused, sort_keys=True) if as_json else f"Omnis: REFUSED ({exc.reason})")
        return exc.code
    unreconciled = os.path.lexists(root / "unreconciled.json")
    record: dict[str, object] | None = None
    preflight_error: OSError | ValueError | None = None
    if not unreconciled and os.path.lexists(root / "startup.json"):
        try:
            record = read_record(root / "startup.json")
            config.check_port(record.get("port"))
            if record.get("phase") == "READY":
                _ready_record(record)
            elif type(record.get("phase")) is str and record["phase"] in {"STOPPING", "STOPPED"}:
                _stopping_record(record)
            else:
                raise StartError("RECOVERY_REQUIRED", 4)
            _check_pgdata(root, record)
        except (OSError, ValueError) as exc:
            preflight_error = exc
    result: dict[str, object] = {
        "state": "NOT_INSTALLED",
        "control_ready": False,
        "dashboard_ready": False,
        "assessment_ready": False,
        "browser_opened": False,
    }
    exit_code = 3
    try:
        instance = load_instance(root)
    except FileNotFoundError:
        pass
    except (OSError, ValueError):
        result["state"] = "CONFIG_INVALID"
        exit_code = 2
    else:
        result.update(
            state="UNAVAILABLE",
            instance_id=instance.instance_id,
            release=instance.release,
            schema=instance.schema,
            origin=instance.origin,
            reason="CONTROL_UNAVAILABLE",
        )
        if not unreconciled and preflight_error is None:
            try:
                current = request(control_dir(root), {"op": "status"})
                if current["instance_id"] != instance.instance_id:
                    raise ControlUnavailable()
            except ControlUnavailable:
                pass
            else:
                result.update(
                    state="RUNNING",
                    control_ready=True,
                    generation=current["generation"],
                    supervisor_epoch=current["supervisor_epoch"],
                    admission_open=current["admission_open"],
                    shutdown_finalized=current["shutdown_finalized"],
                    reason="HTTP_UNVERIFIED",
                )
                exit_code = 0
    if unreconciled:
        result.update(
            state="RECOVERY_REQUIRED",
            control_ready=False,
            dashboard_ready=False,
            reason="UNRECONCILED_STOP",
        )
        exit_code = 4
    elif preflight_error is not None:
        result.update(
            state="UNAVAILABLE",
            control_ready=False,
            dashboard_ready=False,
            reason=(
                preflight_error.reason
                if isinstance(preflight_error, StartError)
                else "READINESS_UNAVAILABLE"
            ),
        )
        exit_code = preflight_error.code if isinstance(preflight_error, StartError) else 4
    elif record is not None:
        # Installed lifecycle receipts opt into HTTP only after exact ownership.
        # Legacy status-only locators remain conservative and never contact a port.
        try:
            port = record.get("port")
            data = os.environ.get("XDG_DATA_HOME")
            runtime = ControlRuntime(
                Path(data) if data else Path.home() / ".local/share", time.monotonic() + 30
            )
            if record.get("phase") == "STOPPED":
                instance = load_instance(root)
                readback_stopped(runtime, root, control_dir(root), record)
                verified = {
                    "state": "STOPPED",
                    "instance_id": instance.instance_id,
                    "release": instance.release,
                    "schema": instance.schema,
                    "origin": instance.origin,
                    "generation": record["stop_generation"],
                    "admission_open": False,
                    "control_ready": False,
                    "dashboard_ready": False,
                    "assessment_ready": False,
                    "browser_opened": False,
                    "reason": None,
                }
            elif record.get("phase") == "STOPPING":
                _stopping_record(record)
                _check_pgdata(root, record)
                instance = _bound_instance(runtime, root, control_dir(root), record)
                barrier_committed = record["stop_generation"] is not None
                verified = {
                    "state": "STOPPING" if barrier_committed else "STOP_REQUESTED",
                    "instance_id": instance.instance_id,
                    "release": instance.release,
                    "schema": instance.schema,
                    "origin": instance.origin,
                    "generation": record["stop_generation"],
                    "control_ready": False,
                    "dashboard_ready": False,
                    "assessment_ready": False,
                    "browser_opened": False,
                    "reason": (
                        "INSTANCE_SHUTTING_DOWN"
                        if barrier_committed
                        else "STOP_BARRIER_UNCONFIRMED"
                    ),
                }
            elif record.get("phase") == "READY" and type(port) is int:
                verified = verify_running(runtime, root, control_dir(root), record, port)
                verified.pop("reused")
            else:
                raise StartError("RECOVERY_REQUIRED", 4)
            if read_record(root / "startup.json") != record:
                raise StartError("LIFECYCLE_CHANGED", 4)
            result = verified
            exit_code = 4 if record["phase"] == "STOPPING" else 0
        except (
            OSError,
            ValueError,
            ControlUnavailable,
            http.client.HTTPException,
            subprocess.SubprocessError,
        ) as exc:
            result.update(
                state="UNAVAILABLE",
                control_ready=False,
                dashboard_ready=False,
                reason=exc.reason if isinstance(exc, StartError) else "READINESS_UNAVAILABLE",
            )
            for key in ("generation", "supervisor_epoch", "admission_open", "shutdown_finalized"):
                result.pop(key, None)
            exit_code = exc.code if isinstance(exc, StartError) else 3
    if as_json:
        print(json.dumps(result, sort_keys=True))
    else:
        print(
            f"Omnis: {result['state']} (dashboard_ready={str(result['dashboard_ready']).lower()}, {result.get('reason') or 'verified'})"
        )
        if result.get("origin"):
            print(f"Origin configurat: {result['origin']}")
        if exit_code:
            print(
                "Verificați instalarea, controlul privat și identitatea instanței.", file=sys.stderr
            )
    return exit_code
