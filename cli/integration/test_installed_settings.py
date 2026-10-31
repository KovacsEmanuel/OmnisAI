"""No-effect controls for the opt-in Settings consumer; no browser/OCI."""

import inspect
import io
import json
import os
import subprocess
import tempfile
import time
import unittest
from contextlib import ExitStack, nullcontext, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import installed_pair_open as pair
import installed_stop as stop
from installed_start import assert_resources_absent


class InstalledSettingsTest(unittest.TestCase):
    def test_native_runtime_is_excluded_from_control_network(self):
        from test_installed_stop_lock_oracle import FakeRuntime

        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as base:
            root = Path(base)
            with patch.object(stop, "request", return_value={}):
                stop._lock_effect_snapshot(
                    FakeRuntime(),
                    root,
                    root / "control",
                    8765,
                    {"containers": {"db": "db", "runtime": "native"}},
                )

    def test_legacy_browser_keeps_raw_stdin_and_finite_session_mode(self):
        def run(argv, **kw):
            self.assertEqual(kw["input"], "synthetic-private-code")
            self.assertEqual(kw["timeout"], 75)
            self.assertEqual(kw["env"]["OMNIS_BROWSER_MODE"], "session")
            return subprocess.CompletedProcess(
                argv, 0, "INSTALLED_BROWSER_SESSION_OK\nINSTALLED_BROWSER_CLOSED\n", ""
            )

        with patch.object(pair.subprocess, "run", side_effect=run):
            pair.run_browser(
                "synthetic-private-code",
                Path("/owned"),
                {"PATH": "/usr/bin:/bin"},
                "http://127.0.0.1:8765",
                "instance",
                browser={
                    "node": "/pinned/node",
                    "cache": "/pinned/cache",
                    "playwright": "/pinned/index.mjs",
                },
            )

    def test_four_role_absence_keeps_native_ipc_in_census(self):
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as base:
            root = Path(base)
            ipc = root / "native-ipc"
            ipc.mkdir()
            runtime = SimpleNamespace(
                ids=lambda: [], network=lambda allowed: None, inspect=lambda *a: None
            )
            record = {"containers": {"runtime": "owned-native"}}
            assert_resources_absent(runtime, root, root / "control", record)
            for name in ("runtime.sock", "runtime.boot"):
                (ipc / name).touch()
                with self.assertRaisesRegex(AssertionError, "IPC"):
                    assert_resources_absent(runtime, root, root / "control", record)
                (ipc / name).unlink()

    def test_default_is_legacy_and_callbacks_surround_normal_stop_restart(self):
        self.assertIsNone(
            inspect.signature(stop.run_installed_stop).parameters["settings_browser"].default
        )
        source = inspect.getsource(stop.run_installed_stop)
        self.assertLess(
            source.index('settings_visit("settings-save")'),
            source.index("stopper = subprocess.Popen"),
        )
        self.assertGreater(
            source.index('settings_visit("settings-readback")'),
            source.index("restarted = command"),
        )
        self.assertLess(
            source.index('settings_visit("settings-readback")'),
            source.rindex("proof = cleanup = True"),
        )
        self.assertIn("driver_pending = True", source)
        self.assertIn("not driver_pending", source)
        self.assertIn('probe="PENDING"', source)

    def test_private_browser_payload_and_settlement(self):
        code = "synthetic-private-code-0001"
        manifest = json.dumps(
            {
                "version": 1,
                "files": {"index.html": "a" * 64, "assets/a.js": "b" * 64},
            }
        )
        for exit_code, output, settled in (
            (0, "INSTALLED_SETTINGS_OK\nINSTALLED_BROWSER_CLOSED\n", True),
            (1, "INSTALLED_BROWSER_FAILED\nINSTALLED_BROWSER_CLOSED\n", True),
            (99, "INSTALLED_BROWSER_CLOSED\n", False),
            (-15, "INSTALLED_BROWSER_CLOSED\n", False),
            (0, "INSTALLED_SETTINGS_OK\n", False),
        ):
            events = []

            def run(argv, exit_code=exit_code, output=output, **kw):
                self.assertNotIn(code, repr(argv) + repr(kw["env"]))
                self.assertEqual(json.loads(kw["input"])["code"], code)
                self.assertLessEqual(kw["timeout"], 180)
                return subprocess.CompletedProcess(argv, exit_code, output, "")

            with patch.object(pair.subprocess, "run", side_effect=run):
                try:
                    pair.run_browser(
                        code,
                        Path("/owned"),
                        {"PATH": "/usr/bin:/bin"},
                        "http://127.0.0.1:8765",
                        "00000000-0000-4000-8000-000000000001",
                        mode="settings-save",
                        manifest=manifest,
                        captures=Path("/owned/screens"),
                        browser={
                            "node": "/pinned/node",
                            "cache": "/pinned/cache",
                            "playwright": "/pinned/index.mjs",
                        },
                        on_joined=lambda events=events: events.append("joined"),
                    )
                except (AssertionError, pair.ObserverUncertain):
                    self.assertFalse(exit_code == 0 and settled)
            self.assertEqual(events, ["joined"] if settled else [])

    def test_real_stop_caller_order_and_pending_browser_refusal(self):
        for scenario in (
            "legacy",
            "settings",
            "browser-unknown",
            "cli-unknown",
            "browser-failure",
            "cleanup-failure",
            "engine-unknown",
        ):
            self._stop_scenario(scenario)

    def test_real_signalled_observer_refuses_first_and_last_absence(self):
        # Same producer as F01: real bounded run/inspect, inert shell, no Docker.
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as base:
            child = Path(base) / "observer"
            child.write_text('#!/bin/sh\nprintf "No such container\\n" >&2\nkill -TERM $$\n')
            child.chmod(0o700)
            runtime = object.__new__(stop.ControlRuntime)
            runtime.docker = child
            runtime.release = Path(base)
            runtime.host = "unix:///unused-owned-fixture"
            runtime.deadline = time.monotonic() + 5
            runtime.uncertain = False
            runtime.family_drained = True
            self.assertIsNone(runtime.inspect("container", "synthetic-owned-cid"))
            self.assertFalse(runtime.family_drained)
            with self.assertRaises(ChildProcessError):
                os.waitpid(-1, os.WNOHANG)
            for cut in ("first-absence", "last-absence"):
                self._stop_scenario(cut, flags=(runtime.uncertain, runtime.family_drained))

    def test_late_uncertain_flag_refuses_absence(self):
        self._stop_scenario("last-absence", flags=(True, True))

    def test_cleanup_absence_keeps_primary_failure_and_uncertainty(self):
        self._stop_scenario("cleanup-absence")
        self._stop_scenario("stopped-absence")

    def test_cleanup_readback_refuses_stop_and_keeps_primary_failure(self):
        self._stop_scenario("cleanup-readback")

    def test_final_publication_rechecks_settlement_after_cleanup_credit(self):
        self._stop_scenario("final-readback")

    def _stop_scenario(self, scenario, *, flags=(False, False)):
        with (
            self.subTest(scenario=scenario),
            tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as base,
        ):
            base = Path(base)
            (base / "web").mkdir()
            (base / "web/omnis-web.json").write_text('{"version":1,"files":{}}')
            events, probes, commands = [], [], []
            cut_commands = None
            output = io.StringIO()
            primary_failure = scenario in {
                "browser-failure",
                "cleanup-failure",
                "engine-unknown",
                "cleanup-absence",
                "cleanup-readback",
                "stopped-absence",
            }
            tick = iter(range(0, 10000, 15))
            runtime = SimpleNamespace(
                receipt=SimpleNamespace(image_id="image"),
                native=True,
                uncertain=False,
                family_drained=True,
                release=base,
                psql=lambda *args: "7",
            )
            state = None
            boots = 0

            def run(argv, **kw):
                nonlocal state, boots
                commands.append(argv[1])
                if (
                    scenario == "cleanup-failure"
                    and argv[1] == "stop"
                    and "browser-failure" in events
                ):
                    raise RuntimeError("secondary cleanup failure")
                state = Path(kw["env"]["XDG_STATE_HOME"]) / "omnis"
                state.mkdir(parents=True, exist_ok=True)
                journal = state / "startup.json"
                record = json.loads(journal.read_text()) if journal.exists() else {}
                phase = record.get("phase")
                code = 0
                if argv[1] == "start":
                    if phase == "READY":
                        return subprocess.CompletedProcess(
                            argv, 2, '{"reason":"CONFIG_PORT_CONFLICT"}', ""
                        )
                    if phase == "STOPPING":
                        return subprocess.CompletedProcess(
                            argv, 4, '{"reason":"INSTANCE_SHUTTING_DOWN"}', ""
                        )
                    boots += 1
                    events.append("start")
                    config = Path(kw["env"]["XDG_CONFIG_HOME"]) / "omnis/config.toml"
                    port = int(config.read_text().splitlines()[0].split("=")[1])
                    record = {
                        "phase": "READY",
                        "port": port,
                        "attempt": str(boots),
                        "instance_id": "instance",
                        "provider_identity": [1, 2, 3],
                        "containers": {"db": "db", "runtime": "native"},
                    }
                    journal.write_text(json.dumps(record))
                    (state / "instance.json").write_text("{}")
                    (state / "postgres").mkdir(exist_ok=True)
                    (state / "db-password").touch()
                    value = {
                        "state": "READY",
                        "assessment_ready": False,
                        "origin": f"http://127.0.0.1:{port}",
                        "generation": boots,
                        "supervisor_epoch": boots,
                        "instance_id": "instance",
                    }
                    if scenario == "cli-unknown":
                        code = 99
                elif (
                    argv[1] == "stop"
                    and phase == "READY"
                    and "shutdown_timeout_seconds"
                    in (Path(kw["env"]["XDG_CONFIG_HOME"]) / "omnis/config.toml").read_text()
                ):
                    return subprocess.CompletedProcess(
                        argv, 2, '{"reason":"LIFECYCLE_BUSY","dashboard_ready":false}', ""
                    )
                else:
                    if argv[1] == "stop" and phase != "STOPPED":
                        events.append("stop")
                        record["phase"] = "STOPPED"
                        journal.write_text(json.dumps(record))
                    value = {
                        "state": record["phase"],
                        "dashboard_ready": False,
                        "assessment_ready": False,
                    }
                    if phase == "STOPPING":
                        code = 4
                        value.update(reason="INSTANCE_SHUTTING_DOWN")
                return subprocess.CompletedProcess(argv, code, json.dumps(value), "")

            class Stopper:
                returncode = None

                def __init__(self, *a, **kw):
                    commands.append("stop")
                    events.append("stop")
                    record = json.loads((state / "startup.json").read_text())
                    record["phase"] = "STOPPING"
                    (state / "startup.json").write_text(json.dumps(record))

                def poll(self):
                    return self.returncode

                def communicate(self, **kw):
                    self.returncode = 0
                    record = json.loads((state / "startup.json").read_text())
                    record["phase"] = "STOPPED"
                    (state / "startup.json").write_text(json.dumps(record))
                    if scenario == "stopped-absence":
                        return ('{"state":"STOPPED","dashboard_ready":true}', "")
                    return (
                        '{"state":"STOPPED","dashboard_ready":false,"assessment_ready":false}',
                        "",
                    )

            def browser(*a, **kw):
                self.assertEqual(probes[-1], ("PENDING", "UNCERTAIN"))
                events.append(kw["mode"])
                if scenario == "browser-unknown":
                    raise pair.ObserverUncertain("synthetic unsettled browser")
                kw["on_joined"]()
                if primary_failure and scenario != "stopped-absence":
                    if scenario == "engine-unknown":
                        runtime.family_drained = False
                    events.append("browser-failure")
                    raise AssertionError("primary browser failure")

            def unsettled():
                nonlocal cut_commands
                runtime.uncertain, runtime.family_drained = flags
                cut_commands = len(commands)

            def absent(*args):
                events.append("absent")
                if (
                    scenario in {"cleanup-absence", "stopped-absence", "first-absence"}
                    or scenario == "last-absence"
                    and events.count("absent") == 2
                ):
                    unsettled()

            def snapshot(*args):
                if scenario == "cleanup-readback" and "browser-failure" in events:
                    unsettled()
                return {}

            real_is_dir = Path.is_dir

            def is_dir(path):
                result = real_is_dir(path)
                if scenario == "final-readback" and events.count("absent") == 2:
                    unsettled()
                return result

            with ExitStack() as stack:
                stack.enter_context(redirect_stdout(output))
                stack.enter_context(patch.object(Path, "is_dir", is_dir))
                replacements = {
                    "ControlRuntime": lambda *a: runtime,
                    "resource_snapshot": snapshot,
                    "_lock_effect_snapshot": lambda *a: {
                        "control": {"admission_open": True},
                        "stop_receipts": [],
                        "unreconciled": False,
                    },
                    "request": lambda *a: {
                        "admission_open": True,
                        "generation": 1,
                        "supervisor_epoch": 0,
                        "shutdown_command_id": None,
                    },
                    "lifecycle_lock": lambda *a: nullcontext(),
                    "tty_pair": lambda *a: "synthetic-private-code",
                    "run_browser": browser,
                    "assert_resources_absent": absent,
                    "teardown": lambda *a: events.append("teardown"),
                    "save_probe": lambda *a, **kw: probes.append((kw["probe"], kw["cleanup"])),
                }
                for name, value in replacements.items():
                    stack.enter_context(patch.object(stop, name, value))
                stack.enter_context(patch.object(stop.subprocess, "run", run))
                stack.enter_context(patch.object(stop.subprocess, "Popen", Stopper))
                stack.enter_context(patch.object(stop.time, "monotonic", lambda: next(tick)))
                opts = (
                    None
                    if scenario == "legacy"
                    else dict.fromkeys(("node", "cache", "playwright"), str(base))
                )
                if primary_failure:
                    with self.assertRaisesRegex(
                        AssertionError,
                        "" if scenario == "stopped-absence" else "primary browser failure",
                    ):
                        stop.run_installed_stop(
                            base,
                            {"image_id": "image", "project": "owned"},
                            "cli",
                            settings_browser=opts,
                        )
                    self.assertEqual(
                        probes[-1],
                        ("FAIL", "VERIFIED" if scenario == "browser-failure" else "UNCERTAIN"),
                    )
                    self.assertNotIn("teardown", events)
                elif scenario in {"first-absence", "last-absence"}:
                    with self.assertRaisesRegex(RuntimeError, "observer.*unsettled"):
                        stop.run_installed_stop(
                            base,
                            {"image_id": "image", "project": "owned"},
                            "cli",
                            settings_browser=opts,
                        )
                    self.assertEqual(probes[-1], ("FAIL", "UNCERTAIN"))
                elif scenario.endswith("unknown"):
                    with self.assertRaises(RuntimeError):
                        stop.run_installed_stop(
                            base,
                            {"image_id": "image", "project": "owned"},
                            "cli",
                            settings_browser=opts,
                        )
                    self.assertEqual(probes[-1], ("FAIL", "UNCERTAIN"))
                    self.assertNotIn("stop", events)
                    self.assertNotIn("teardown", events)
                elif scenario == "final-readback":
                    stop.run_installed_stop(
                        base,
                        {"image_id": "image", "project": "owned"},
                        "cli",
                        settings_browser=opts,
                    )
                    self.assertEqual(probes[-1], ("FAIL", "UNCERTAIN"))
                else:
                    stop.run_installed_stop(
                        base,
                        {"image_id": "image", "project": "owned"},
                        "cli",
                        settings_browser=opts,
                    )
                    self.assertEqual(probes[-1], ("PASS", "VERIFIED"))
                    actual = [e for e in events if e != "absent"]
                    self.assertEqual(
                        actual,
                        ["start", "stop", "start", "stop"]
                        if scenario == "legacy"
                        else [
                            "start",
                            "settings-save",
                            "stop",
                            "start",
                            "settings-readback",
                            "stop",
                        ],
                    )

            if scenario in {
                "first-absence",
                "last-absence",
                "cleanup-absence",
                "stopped-absence",
                "cleanup-readback",
                "final-readback",
            }:
                self.assertIsNotNone(cut_commands, "Late observation cut was not reached")
            if cut_commands is not None:
                self.assertEqual(
                    len(commands), cut_commands, "Lifecycle continued after uncertainty"
                )
                self.assertNotIn("teardown", events)
                self.assertNotIn("INSTALLED_STOP_VERIFIED", output.getvalue())
                self.assertEqual(probes[-1], ("FAIL", "UNCERTAIN"))
                self.assertIsNotNone(state)
                self.assertTrue((state / "postgres").is_dir())

    def test_timeout_remains_uncertain_and_is_not_retried(self):
        events = []
        with patch.object(
            pair.subprocess, "run", side_effect=subprocess.TimeoutExpired(["node"], 180)
        ) as run:
            with self.assertRaises(subprocess.TimeoutExpired):
                pair.run_browser(
                    "synthetic-private-code",
                    Path("/owned"),
                    {"PATH": "/usr/bin:/bin"},
                    "http://127.0.0.1:8765",
                    "00000000-0000-4000-8000-000000000001",
                    mode="settings-readback",
                    manifest={},
                    captures=Path("/owned/screens"),
                    browser={
                        "node": "/pinned/node",
                        "cache": "/pinned/cache",
                        "playwright": "/pinned/index.mjs",
                    },
                    on_joined=lambda: events.append("joined"),
                )
            self.assertEqual(run.call_count, 1)
        self.assertEqual(events, [])


if __name__ == "__main__":
    unittest.main()
