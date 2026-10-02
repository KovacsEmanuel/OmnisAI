"""RT-F01 caller regression: real child/listener/cleanup, substituted Docker."""

import contextlib
import importlib
import io
import json
import os
import select
import signal
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from omnis_cli.start_runtime import ControlRuntime

start = importlib.import_module("omnis_cli.start")


class ForwarderCallerTest(unittest.TestCase):
    def test_close_signal_cannot_publish_cleaned_with_live_forwarder(self):
        self.run_attempt("close")

    def test_cancelled_tuple_delivery_uses_caller_owned_holder(self):
        self.run_attempt("return")

    def test_missing_pidfd_retains_database_and_spawn_locator(self):
        self.run_attempt("missing-pin")

    def test_repeated_signal_at_cleanup_entry_cannot_abandon_owned_child(self):
        self.run_attempt("repeat-cleanup")

    def run_attempt(self, boundary):
        with tempfile.TemporaryDirectory(prefix="fc-", dir=os.environ["TMPDIR"]) as temp:
            base = Path(temp)
            data, state, ipc = base / "d", base / "s", base / "i"
            root = state / "omnis"
            (data / "omnis").mkdir(parents=True, mode=0o700)
            resources, effects, children, inodes = {}, [], [], []
            api = socket.socket(socket.AF_UNIX)
            runtime = ControlRuntime.__new__(ControlRuntime)
            runtime.deadline = time.monotonic() + 5
            runtime.uncertain, runtime.family_drained = False, True
            runtime.receipt = SimpleNamespace(
                project="omnis-local-" + "a" * 32,
                image_id="sha256:" + "b" * 64,
                docker_id="synthetic-daemon",
            )
            runtime.digest, runtime.host, runtime.files = "c" * 64, "unix:///synthetic", {}
            spawn, pin, launch = subprocess.Popen, os.pidfd_open, start.launch_forwarder
            getsignal = signal.getsignal
            secondary_signals = []

            def observed_getsignal(sig):
                handler = getsignal(sig)
                if (
                    boundary == "repeat-cleanup"
                    and sys.exception() is not None
                    and not secondary_signals
                ):
                    secondary_signals.append(sig)
                    os.kill(os.getpid(), signal.SIGTERM)
                return handler

            def compose(env, *args, **kwargs):
                for role in ("db",) if args[-1] == "db" else ("api", "supervisor"):
                    resources[role + "-id"] = {"role": role, "running": True}
                return subprocess.CompletedProcess(args, 0, "", "")

            def run(*args, **kwargs):
                effects.append(args)
                if args[0] == "create":
                    resources["migrate-id"] = {"role": "migrate", "running": False}
                    return subprocess.CompletedProcess(args, 0, "migrate-id", "")
                if args[:2] == ("container", "stop"):
                    resources[args[-1]]["running"] = False
                if args[:2] == ("container", "rm"):
                    resources.pop(args[-1], None)
                return subprocess.CompletedProcess(args, 0, "", "")

            def inspect(kind, ident):
                item = resources.get(ident)
                if kind == "network" or item is None:
                    return None
                return {
                    "Config": {"Labels": {"com.docker.compose.service": item["role"]}},
                    "State": {"Running": item["running"]},
                }

            def ready(*args, **kwargs):
                self.assertIs(kwargs.get("allow_closed"), False)
                api.bind(str(root / "http/api.sock"))
                (root / "http/api.sock").chmod(0o600)
                api.listen(1)
                return {"admission_open": False, "generation": 0, "shutdown_command_id": None}

            def observed_spawn(argv, **kwargs):
                child = spawn(argv, **kwargs)
                children.append((child, pin(child.pid)))
                close = child.stdout.close

                def observed_close():
                    # Observer identity is captured independently BEFORE fault.
                    child.stdout.close = close
                    if boundary != "missing-pin":
                        inodes.extend(start.process_sockets(child.pid))
                    close()
                    if boundary == "close":
                        os.kill(os.getpid(), signal.SIGTERM)

                child.stdout.close = observed_close
                return child

            def observed_launch(*args, **kwargs):
                result = launch(*args, **kwargs)
                if boundary in ("return", "repeat-cleanup"):
                    os.kill(os.getpid(), signal.SIGTERM)
                return result

            def own_pin(pid):
                if boundary == "missing-pin":
                    raise OSError("synthetic pin refusal")
                return pin(pid)

            def fixture_ipc_cleanup(*args):
                api.close()
                (root / "http/api.sock").unlink()
                return []

            with socket.socket() as reservation:
                reservation.bind(("127.0.0.1", 0))
                port = reservation.getsockname()[1]
            output = io.StringIO()
            try:
                managers = (
                    patch.dict(
                        os.environ,
                        {
                            "XDG_DATA_HOME": str(data),
                            "XDG_STATE_HOME": str(state),
                            "XDG_RUNTIME_DIR": str(ipc),
                        },
                    ),
                    patch.object(start, "ControlRuntime", return_value=runtime),
                    patch.object(start, "validate_config"),
                    patch.object(runtime, "compose", side_effect=compose),
                    patch.object(runtime, "run", side_effect=run),
                    patch.object(runtime, "ids", side_effect=lambda: list(resources)),
                    patch.object(runtime, "inspect", side_effect=inspect),
                    patch.object(runtime, "network", return_value=None),
                    patch.object(runtime, "attest", return_value={}),
                    patch.object(runtime, "psql", return_value="1234"),
                    patch.object(runtime, "wait_container", return_value={"ExitCode": 0}),
                    patch.object(
                        start,
                        "database_identity",
                        return_value=(
                            "1234",
                            "11111111-1111-4111-8111-111111111111",
                        ),
                    ),
                    patch.object(start, "api_process", return_value=os.getpid()),
                    patch.object(start, "wait_dashboard", side_effect=ready),
                    patch.object(start, "cleanup_startup_ipc", side_effect=fixture_ipc_cleanup),
                    patch.object(start, "launch_forwarder", side_effect=observed_launch),
                    patch.object(start.subprocess, "Popen", side_effect=observed_spawn),
                    patch.object(start.os, "pidfd_open", side_effect=own_pin),
                    patch.object(start.signal, "getsignal", side_effect=observed_getsignal),
                    contextlib.redirect_stdout(output),
                )
                with contextlib.ExitStack() as scope:
                    for manager in managers:
                        scope.enter_context(manager)
                    code = start.start(port=port, as_json=True)
                record = json.loads((root / "startup.json").read_text())
                result = json.loads(output.getvalue())
                if boundary == "repeat-cleanup":
                    self.assertEqual(len(secondary_signals), 1, "Secondary stop was not injected")
                self.assertFalse(result["dashboard_ready"])
                self.assertEqual(
                    record["phase"], "UNCERTAIN" if boundary == "missing-pin" else "FAILED_CLEANED"
                )
                self.assertEqual(record["failed_phase"], "FORWARDING")
                child, observer = children[0]
                if boundary == "missing-pin":
                    self.assertEqual(code, 4)
                    self.assertEqual(record["phase"], "UNCERTAIN")
                    self.assertEqual(record["forwarder_spawn_pid"], child.pid)
                    self.assertFalse(
                        any(
                            args[:2] in (("container", "stop"), ("container", "rm"))
                            and args[-1] == "db-id"
                            for args in effects
                        )
                    )
                    self.assertIn("db-id", resources)
                else:
                    self.assertEqual(code, 3)
                    self.assertEqual(record["phase"], "FAILED_CLEANED")
                    self.assertEqual(record["cleanup"], [])
                    self.assertTrue(inodes, "Independent observer never saw sockets")
                    self.assertTrue(select.select([observer], [], [], 0)[0])
                    self.assertIsNotNone(child.returncode)
                    self.assertEqual(resources, {})
                    for table in ("tcp", "tcp6"):
                        rows = Path(f"/proc/net/{table}").read_text().splitlines()[1:]
                        self.assertFalse(
                            any(
                                row.split()[3] == "0A" and int(row.split()[9]) in inodes
                                for row in rows
                            ),
                            "Product cleanup left observed listener before rescue",
                        )
                self.assertTrue((root / "postgres").is_dir())
            finally:
                api.close()
                for child, observer in children:
                    if not select.select([observer], [], [], 0)[0]:
                        signal.pidfd_send_signal(observer, signal.SIGKILL)
                    child.wait(timeout=3)
                    os.close(observer)
                    if child.stdout is not None:
                        child.stdout.close()
