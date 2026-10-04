"""Negative controls for the pre-effect installed Stop lock-wait readback."""

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from installed_stop import _lock_effect_snapshot, run_installed_stop


class FakeRuntime:
    def __init__(self):
        self.network_id = "network-a"
        self.network_state = {"Id": "network-a", "Containers": {"db": {}}}
        self.barrier = "instance|t||1||"

    def ids(self):
        return ["db"]

    def inspect(self, kind, ident):
        if kind == "network":
            return self.network_state.copy()
        assert (kind, ident) == ("container", "db")
        return {
            "Config": {"Labels": {"com.docker.compose.service": "db"}},
            "State": {"Running": True, "StartedAt": "start", "FinishedAt": ""},
            "RestartCount": 0,
        }

    def attest(self, *args):
        assert args[0:2] == ("db", "db")

    def network(self, allowed):
        assert allowed == {"db"}
        return self.network_id

    def psql(self, ident, query):
        assert ident == "db" and "instance_control WHERE id = 1" in query
        return self.barrier


class StopLockOracleTest(unittest.TestCase):
    def test_control_network_db_and_stop_receipt_changes_cannot_pass_as_no_effect(self):
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as base:
            root = Path(base)
            runtime = FakeRuntime()
            status = {
                "instance_id": "instance",
                "generation": 1,
                "admission_open": True,
                "shutdown_command_id": None,
                "quiesced_generation": None,
                "supervisor_epoch": 1,
                "supervisor_ready": True,
                "shutdown_finalized": False,
                "assessment_ready": False,
                "dashboard_ready": True,
            }
            record = {"containers": {"db": "db"}}
            with patch("installed_stop.request", side_effect=lambda *args: status.copy()):

                def observe():
                    return _lock_effect_snapshot(runtime, root, root / "control.sock", 8765, record)

                baseline = observe()
                self.assertEqual(observe(), baseline)
                runtime.network_id = "network-b"
                runtime.network_state["Id"] = "network-b"
                self.assertNotEqual(observe(), baseline)
                runtime.network_id = "network-a"
                runtime.network_state["Id"] = "network-a"
                runtime.network_state["Containers"] = {}
                self.assertNotEqual(observe(), baseline)
                runtime.network_state["Containers"] = {"db": {}}
                status["admission_open"] = False
                self.assertNotEqual(observe(), baseline)
                status["admission_open"] = True
                runtime.barrier = "instance|f|stop-command|2||"
                self.assertNotEqual(observe(), baseline)
                runtime.barrier = "instance|t||1||"
                (root / "stop-new.json").write_text("{}")
                self.assertNotEqual(observe(), baseline)
                (root / "stop-new.json").unlink()
                (root / "unreconciled.json").write_text("{}")
                self.assertNotEqual(observe(), baseline)

    def test_timeout_never_tears_down_ready_or_certifies_cleanup(self):
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as base:
            data = Path(base) / "data"
            (data / "omnis").mkdir(parents=True, mode=0o700)
            events = []

            class Runtime:
                receipt = SimpleNamespace(image_id="test-image")
                attempt = None
                deadline = None

                def psql(self, ident, query):
                    return "instance|t||1||"

                def network(self, allowed):
                    return "test-network"

                def inspect(self, kind, ident):
                    return {"Id": "test-network"}

            def run(argv, **kw):
                state = Path(kw["env"]["XDG_STATE_HOME"]) / "omnis"
                config = Path(kw["env"]["XDG_CONFIG_HOME"]) / "omnis/config.toml"
                port = int(config.read_text().splitlines()[0].split("=", 1)[1])
                if argv[1] == "start" and not (state / "startup.json").exists():
                    state.mkdir(parents=True, mode=0o700)
                    (state / "startup.json").write_text(
                        json.dumps(
                            {
                                "phase": "READY",
                                "attempt": "attempt",
                                "port": port,
                                "containers": {"db": "db"},
                            }
                        )
                    )
                    (state / "instance.json").write_text('{"instance":"test"}')
                    return subprocess.CompletedProcess(
                        argv,
                        0,
                        json.dumps(
                            {
                                "state": "READY",
                                "assessment_ready": False,
                                "origin": f"http://127.0.0.1:{port}",
                            }
                        ),
                        "",
                    )
                if argv[1] == "start":
                    return subprocess.CompletedProcess(
                        argv, 2, '{"reason":"CONFIG_PORT_CONFLICT"}', ""
                    )
                assert argv[1] == "stop"
                raise subprocess.TimeoutExpired(argv, kw["timeout"])

            with (
                patch.dict(os.environ, {"TMPDIR": base}),
                patch("installed_stop.ControlRuntime", return_value=Runtime()),
                patch("installed_stop.subprocess.run", side_effect=run),
                patch("installed_stop.resource_snapshot", return_value={"db": {}}),
                patch(
                    "installed_stop.request",
                    return_value={
                        "admission_open": True,
                        "generation": 1,
                        "shutdown_command_id": None,
                    },
                ),
                patch(
                    "installed_stop.teardown",
                    side_effect=lambda *args: events.append(("teardown",)),
                ),
                patch(
                    "installed_stop.assert_resources_absent",
                    side_effect=lambda *args: events.append(("absent",)),
                ),
                patch(
                    "installed_stop.save_probe",
                    side_effect=lambda *args, **kw: events.append(
                        ("probe", kw["probe"], kw["cleanup"])
                    ),
                ),
            ):
                with self.assertRaises(subprocess.TimeoutExpired):
                    run_installed_stop(
                        data, {"image_id": "test-image", "project": "test-project"}, "installed-cli"
                    )
            self.assertNotIn(("teardown",), events)
            self.assertNotIn(("absent",), events)
            self.assertIn(("probe", "FAIL", "UNCERTAIN"), events)


if __name__ == "__main__":
    unittest.main()
