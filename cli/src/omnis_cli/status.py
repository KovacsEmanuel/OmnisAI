"""Read-only status; a private supervisor ACK is not proof of HTTP ownership."""

import json
import sys

from .control import ControlUnavailable, request
from .instance import control_dir, load_instance, state_dir


def status(*, as_json: bool) -> int:
    root = state_dir()
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
    if as_json:
        print(json.dumps(result, sort_keys=True))
    else:
        print(
            f"Omnis: {result['state']} (dashboard_ready=false, {result.get('reason', 'no instance')})"
        )
        if result.get("origin"):
            print(f"Origin configurat: {result['origin']}")
        if exit_code:
            print(
                "Verificați instalarea, controlul privat și identitatea instanței.", file=sys.stderr
            )
    return exit_code
