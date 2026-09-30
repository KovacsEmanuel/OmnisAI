"""Narrow regressions for startup subprocess and cleanup error boundaries."""

import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from omnis_cli.lifecycle import StartError
from omnis_cli.start_runtime import ControlRuntime


class StartupProcessTest(unittest.TestCase):
    def runtime(self, deadline):
        runtime = ControlRuntime.__new__(ControlRuntime)
        runtime.deadline = deadline
        runtime.uncertain = False
        runtime.family_drained = True
        runtime.docker = Path("/usr/bin/docker")
        runtime.release = Path(os.environ["TMPDIR"])
        runtime.host = "unix:///run/docker.sock"
        return runtime

    def test_matching_migration_shape_without_attempt_identity_is_not_owned(self):
        from types import SimpleNamespace

        runtime = self.runtime(time.monotonic() + 5)
        runtime.receipt = SimpleNamespace(
            project="omnis-local-" + "a" * 32, image_id="sha256:" + "b" * 64
        )
        runtime.attempt = "11111111-1111-4111-8111-111111111111"
        cid = "d" * 64
        item = {
            "Id": cid,
            "Image": runtime.receipt.image_id,
            "Mounts": [],
            "Config": {
                "Labels": {
                    "com.docker.compose.project": runtime.receipt.project,
                    "com.docker.compose.service": "migrate",
                    "org.omnis.start-attempt": "foreign",
                },
                "User": f"{os.getuid()}:{os.getgid()}",
                "Cmd": ["python", "-I", "-m", "omnis.migrate", "--initialize"],
                "Env": [],
            },
            "HostConfig": {
                "Privileged": False,
                "NetworkMode": runtime.receipt.project + "_control",
                "ReadonlyRootfs": True,
                "CapDrop": ["ALL"],
                "SecurityOpt": ["no-new-privileges:true"],
            },
            "NetworkSettings": {"Ports": {}, "Networks": {}},
            "State": {"Running": False},
        }
        with (
            patch.object(runtime, "check_daemon"),
            patch.object(runtime, "inspect", return_value=item),
        ):
            with self.assertRaisesRegex(StartError, "ATTEMPT_IDENTITY_MISMATCH"):
                runtime.attest(
                    cid, "migrate", Path(os.environ["TMPDIR"]), Path(os.environ["TMPDIR"]), 8765
                )
        network = {
            "Id": "e" * 64,
            "Driver": "bridge",
            "Internal": True,
            "Containers": {},
            "Labels": {"com.docker.compose.project": runtime.receipt.project},
        }
        with (
            patch.object(runtime, "check_daemon"),
            patch.object(runtime, "inspect", return_value=network),
        ):
            with self.assertRaisesRegex(StartError, "ATTEMPT_IDENTITY_MISMATCH"):
                runtime.network(set())

    def test_partial_cleanup_reclaims_dead_owned_ipc_but_not_live_peer(self):
        import socket
        from types import SimpleNamespace

        from omnis_cli.start import cleanup_attempt

        for live in (False, True):
            with (
                self.subTest(live=live),
                tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name,
            ):
                root = Path(name)
                control = root / "control"
                control.mkdir(mode=0o700)
                (root / "http").mkdir(mode=0o700)
                lock = control / "control.lock"
                lock.write_text("stale PID is not authority")
                lock.chmod(0o600)
                cap = control / "control.cap"
                cap.write_text("")  # Partial capability write is still our private file.
                cap.chmod(0o600)
                with socket.socket(socket.AF_UNIX) as peer:
                    path = control / "control.sock"
                    peer.bind(str(path))
                    path.chmod(0o600)
                    if live:
                        peer.listen(1)
                    else:
                        peer.close()
                    runtime = SimpleNamespace(
                        ids=lambda: [],
                        network=lambda allowed: None,
                        uncertain=False,
                        family_drained=True,
                    )
                    problems = cleanup_attempt(runtime, root, control, 8765, None, -1)
                    if live:
                        self.assertTrue(problems)
                        self.assertTrue(path.exists())
                        self.assertTrue(cap.exists())
                    else:
                        self.assertEqual(problems, [])
                        self.assertFalse(os.path.lexists(path))
                        self.assertFalse(cap.exists())
                    self.assertEqual(lock.read_text(), "stale PID is not authority")

    def test_expired_startup_deadline_does_not_spawn_forwarder(self):
        from omnis_cli.start import launch_forwarder

        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
            with patch(
                "subprocess.Popen", side_effect=AssertionError("forwarder spawned after deadline")
            ) as spawn:
                with self.assertRaisesRegex(StartError, "STARTUP_TIMEOUT"):
                    launch_forwarder(Path(name), 8765, time.monotonic() - 1)
                spawn.assert_not_called()
            self.assertFalse((Path(name) / "forwarder.log").exists())

    def test_expired_deadline_does_not_spawn_a_command(self):
        runtime = self.runtime(time.monotonic() - 1)
        with patch("subprocess.Popen", side_effect=AssertionError("spawn after deadline")) as spawn:
            with self.assertRaisesRegex(StartError, "STARTUP_TIMEOUT"):
                runtime.run("start", "synthetic", effect=True)
        spawn.assert_not_called()
        self.assertFalse(runtime.uncertain)

    def test_output_limit_interrupts_real_child_before_waiting_for_exit(self):
        runtime = self.runtime(time.monotonic() + 5)
        original = subprocess.Popen
        children = []

        def launch(argv, **kwargs):
            child = original(
                [
                    sys.executable,
                    "-I",
                    "-c",
                    "import os,time; os.write(1,b'x'*(5*1024*1024)); time.sleep(10)",
                ],
                **kwargs,
            )
            children.append(child)
            return child

        begin = time.monotonic()
        with patch("subprocess.Popen", side_effect=launch):
            with self.assertRaisesRegex(StartError, "DOCKER_OUTPUT_LIMIT"):
                runtime.run("inspect", "synthetic", cap=0.7, effect=True)
        self.assertLess(time.monotonic() - begin, 2)
        self.assertTrue(runtime.uncertain)
        self.assertIsNotNone(children[0].returncode)
        self.assertLess(children[0].returncode, 0, "Writer must be killed, not expire naturally")

    def test_failed_forwarder_handshake_preserves_owned_handles_for_outer_cleanup(self):
        import importlib

        start = importlib.import_module("omnis_cli.start")
        original_spawn, original_pin = subprocess.Popen, os.pidfd_open
        children, pins = [], []

        def spawn(argv, **kwargs):
            child = original_spawn(
                [sys.executable, "-I", "-c", "import time; time.sleep(30)"], **kwargs
            )
            children.append(child)
            return child

        def pin(pid):
            fd = original_pin(pid)
            pins.append(fd)
            return fd

        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
            try:
                with (
                    patch("subprocess.Popen", side_effect=spawn),
                    patch("os.pidfd_open", side_effect=pin),
                    patch.object(start.select, "select", return_value=([], [], [])),
                    patch.object(
                        start, "stop_forwarder", side_effect=OSError("synthetic stop failure")
                    ),
                ):
                    try:
                        start.launch_forwarder(Path(name), 8765, time.monotonic() + 1)
                    except (OSError, StartError) as exc:
                        self.assertIs(
                            getattr(exc, "process", None),
                            children[0],
                            "Forwarder ownership was lost on failure",
                        )
                        self.assertEqual(getattr(exc, "pidfd", None), pins[0])
                    else:
                        self.fail("Missing forwarder readiness was accepted")
            finally:
                for child in children:
                    child.kill()
                    child.wait(timeout=3)
                for fd in pins:
                    try:
                        os.close(fd)
                    except OSError:
                        pass

    def test_cleanup_rechecks_uncertainty_raised_during_non_db_removal(self):
        from omnis_cli.start import cleanup_attempt

        for flag in ("uncertain", "family_drained"):
            with (
                self.subTest(flag=flag),
                tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as directory,
            ):
                calls = []

                class Runtime:
                    deadline = 0
                    uncertain = False
                    family_drained = True

                    def ids(self):
                        return ["api-id", "db-id"]

                    def inspect(self, kind, ident):
                        return {
                            "Config": {
                                "Labels": {"com.docker.compose.service": ident.removesuffix("-id")}
                            },
                            "State": {"Running": False},
                        }

                    def attest(self, *args):
                        return {}

                    def run(self, *args, chosen=flag, history=calls, **kwargs):
                        history.append(args)
                        if args == ("container", "rm", "api-id"):
                            setattr(self, chosen, chosen == "uncertain")
                            raise OSError("synthetic removal interruption")

                root = Path(directory)
                problems = cleanup_attempt(Runtime(), root, root, 8765, None, -1)
                self.assertTrue(problems)
                self.assertIn(("container", "rm", "api-id"), calls)
                self.assertFalse(
                    any("db-id" in command for command in calls),
                    "New cleanup uncertainty must close the DB gate",
                )

    def test_uncertain_daemon_effect_keeps_database_running(self):
        from types import SimpleNamespace

        from omnis_cli.start import cleanup_attempt

        calls = []

        class Runtime:
            deadline = 0
            uncertain = True
            family_drained = True

            def ids(self):
                return ["db-id"]

            def inspect(self, kind, ident):
                return {
                    "Config": {"Labels": {"com.docker.compose.service": "db"}},
                    "State": {"Running": False},
                }

            def attest(self, *args):
                return {}

            def run(self, *args, **kwargs):
                calls.append(args)
                return SimpleNamespace(returncode=0)

        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as directory:
            root = Path(directory)
            problems = cleanup_attempt(Runtime(), root, root, 8765, None, -1)
        self.assertTrue(problems)
        self.assertFalse(
            any("db-id" in command for command in calls),
            "Unsettled create/start forbids DB teardown",
        )
