"""Narrow regressions for startup subprocess and cleanup error boundaries."""

import json
import os
import signal
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

    def signal_policy_probe(self, mode):
        from omnis_cli import start_runtime

        helper = Path(__file__).with_name("start_signal_probe.py")
        argv = [sys.executable, "-I", str(helper), mode]
        if mode == "ignored":
            argv = [
                sys.executable,
                "-I",
                "-c",
                "import os,signal,sys; signal.signal(signal.SIGCHLD,signal.SIG_IGN); "
                "os.execv(sys.executable,[sys.executable,'-I',*sys.argv[1:]])",
                str(helper),
                mode,
            ]
        result = subprocess.run(argv, capture_output=True, text=True, timeout=8, check=True)
        report = json.loads(result.stdout)
        self.assertEqual(report["module"], start_runtime.__file__)
        self.assertTrue(report["policy_unchanged"], "Library must not normalize caller signals")
        self.assertEqual(report["attempts"], [], "No signal may target a freed numeric group")
        return report

    def test_default_sigchld_real_child_completes(self):
        report = self.signal_policy_probe("default")
        self.assertEqual(report["spawned"], 1)
        self.assertEqual(report["outcome"], "completed")
        self.assertEqual(report["returncode"], 0)
        self.assertFalse(report["uncertain"])
        self.assertTrue(report["drained"])

    def test_exec_inherited_ignored_sigchld_refused_before_spawn(self):
        report = self.signal_policy_probe("ignored")
        self.assertTrue(report["kernel_echild"], "Fresh exec must prove real auto-reap")
        self.assertEqual(report["outcome"], "StartError")
        self.assertEqual(report["reason"], "CHILD_SIGNAL_POLICY_UNSUPPORTED")
        self.assertEqual(report["spawned"], 0)
        self.assertFalse(report["uncertain"])
        self.assertTrue(report["drained"])

    def test_sigchld_reaper_handler_refused_before_spawn(self):
        report = self.signal_policy_probe("handler")
        self.assertTrue(report["kernel_echild"])
        self.assertTrue(report["handler_reaped"])
        self.assertEqual(report["outcome"], "StartError")
        self.assertEqual(report["reason"], "CHILD_SIGNAL_POLICY_UNSUPPORTED")
        self.assertEqual(report["spawned"], 0)
        self.assertFalse(report["uncertain"])
        self.assertTrue(report["drained"])

    def test_unexpected_reap_revokes_numeric_authority_on_each_error_boundary(self):
        import errno
        import selectors

        original_spawn, original_waitid, original_read = subprocess.Popen, os.waitid, os.read
        for boundary in ("waitid", "timeout", "flood"):
            with self.subTest(boundary=boundary):
                runtime = self.runtime(time.monotonic() + 3)
                children, pins, held_writers, observed = [], [], [], []
                script = (
                    "import os; os.write(1,b'x'*(4*1024*1024+1))"
                    if boundary == "flood"
                    else "import time; time.sleep(0.05)"
                )

                def launch(
                    argv,
                    program=script,
                    owned=children,
                    handles=pins,
                    waiting=held_writers,
                    mode=boundary,
                    **kwargs,
                ):
                    child = original_spawn([sys.executable, "-I", "-c", program], **kwargs)
                    owned.append(child)
                    handles.append(os.pidfd_open(child.pid))
                    if mode == "timeout":
                        # A held output pipe exercises the genuine selector timeout
                        # after the real leader is reaped, without another child.
                        for name in ("stdout", "stderr"):
                            getattr(child, name).close()
                            read_fd, write_fd = os.pipe()
                            setattr(child, name, os.fdopen(read_fd, "rb"))
                            waiting.append(write_fd)
                    return child

                def reap(owned=children, events=observed):
                    if events:
                        return
                    child = owned[0]
                    os.waitpid(child.pid, 0)  # Real kernel reap; do not publish returncode.
                    with self.assertRaises(ChildProcessError) as caught:
                        original_waitid(os.P_PID, child.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)
                    self.assertEqual(caught.exception.errno, errno.ECHILD)
                    events.append(child.returncode)

                def lost_wait(*args):
                    reap()
                    return original_waitid(*args)  # Product encounters the real ECHILD.

                class ReapingSelector(selectors.DefaultSelector):
                    def select(self, timeout=None):
                        reap()
                        return super().select(timeout)

                total = 0

                def flood_read(fd, size, owned=children):
                    nonlocal total
                    part = original_read(fd, size)
                    if owned and fd == owned[0].stdout.fileno():
                        total += len(part)
                        if total > 4 * 1024 * 1024:
                            reap()  # Exit can precede processing the buffered flood.
                    return part

                try:
                    with (
                        patch("subprocess.Popen", side_effect=launch),
                        patch("os.killpg") as numeric,
                        patch("os.kill") as pid_numeric,
                        patch(
                            "os.waitid",
                            side_effect=lost_wait if boundary == "waitid" else original_waitid,
                        ),
                        patch(
                            "selectors.DefaultSelector",
                            ReapingSelector if boundary == "timeout" else selectors.DefaultSelector,
                        ),
                        patch(
                            "os.read",
                            side_effect=flood_read if boundary == "flood" else original_read,
                        ),
                    ):
                        reason = {
                            "waitid": "CHILD_OWNERSHIP_LOST",
                            "timeout": "STARTUP_TIMEOUT",
                            "flood": "DOCKER_OUTPUT_LIMIT",
                        }[boundary]
                        with self.assertRaises((StartError, OSError)) as caught:
                            runtime.run("synthetic", effect=True, cap=0.25)
                    self.assertEqual(observed, [None], "returncode=None is not wait ownership")
                    numeric.assert_not_called()
                    pid_numeric.assert_not_called()
                    self.assertIsInstance(caught.exception, StartError)
                    self.assertEqual(str(caught.exception), reason)
                    self.assertTrue(runtime.uncertain)
                    self.assertFalse(runtime.family_drained)
                finally:
                    for fd in held_writers:
                        os.close(fd)
                    for child, fd in zip(children, pins, strict=True):
                        try:
                            signal.pidfd_send_signal(fd, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                        child.wait(timeout=2)
                        for pipe in (child.stdout, child.stderr):
                            if pipe is not None:
                                pipe.close()
                        os.close(fd)

    def test_reaper_between_wnowait_and_wait_cannot_forge_zero_exit(self):
        original = subprocess.Popen
        for script in ("import sys; sys.exit(1)", "import os; os.kill(os.getpid(),9)", "pass"):
            with self.subTest(script=script):
                runtime = self.runtime(time.monotonic() + 3)
                children, observed = [], []

                def launch(argv, program=script, owned=children, events=observed, **kwargs):
                    child = original([sys.executable, "-I", "-c", program], **kwargs)
                    owned.append(child)
                    wait = child.wait

                    def competing_wait(*args, **kwargs):
                        os.waitpid(child.pid, 0)
                        with self.assertRaises(ChildProcessError):
                            os.waitid(os.P_PID, child.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)
                        events.append(child.returncode)
                        return wait(*args, **kwargs)  # Popen hides ECHILD by returning zero.

                    child.wait = competing_wait
                    return child

                try:
                    with (
                        patch("subprocess.Popen", side_effect=launch),
                        patch("os.killpg") as group_signal,
                        patch("os.kill") as pid_signal,
                    ):
                        if script == "pass":
                            result = runtime.run("synthetic", effect=True, success=False)
                            self.assertEqual(result.returncode, 0, "Observed WNOWAIT exit0 is ACK")
                        else:
                            with self.assertRaisesRegex(StartError, "CHILD_OWNERSHIP_LOST"):
                                runtime.run("synthetic", effect=True, success=False)
                    self.assertEqual(observed, [None])
                    group_signal.assert_not_called()
                    pid_signal.assert_not_called()
                    self.assertEqual(runtime.uncertain, script != "pass")
                    self.assertEqual(runtime.family_drained, script == "pass")
                finally:
                    for child in children:
                        # Already reaped by the controlled competing wait, not a PID rescue.
                        with self.assertRaises(ChildProcessError):
                            os.waitpid(child.pid, os.WNOHANG)
                        for pipe in (child.stdout, child.stderr):
                            if pipe is not None:
                                pipe.close()

    def test_pidfd_unavailable_has_no_numeric_signal_fallback(self):
        original_spawn, original_pin = subprocess.Popen, os.pidfd_open
        runtime = self.runtime(time.monotonic() + 3)
        children, pins = [], []

        def launch(argv, **kwargs):
            child = original_spawn(
                [sys.executable, "-I", "-c", "import time; time.sleep(0.1)"], **kwargs
            )
            children.append(child)
            pins.append(original_pin(child.pid))
            return child

        try:
            with (
                patch("subprocess.Popen", side_effect=launch),
                patch("os.pidfd_open", side_effect=OSError("synthetic pin failure")),
                patch("os.killpg") as numeric,
                patch("os.kill") as pid_numeric,
            ):
                with self.assertRaisesRegex(StartError, "CHILD_OWNERSHIP_UNAVAILABLE"):
                    runtime.run("synthetic", effect=True)
            numeric.assert_not_called()
            pid_numeric.assert_not_called()
            self.assertTrue(runtime.uncertain)
            self.assertFalse(runtime.family_drained)
        finally:
            for child, fd in zip(children, pins, strict=True):
                try:
                    signal.pidfd_send_signal(fd, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                child.wait(timeout=2)
                for pipe in (child.stdout, child.stderr):
                    if pipe is not None:
                        pipe.close()
                os.close(fd)

    def test_later_completed_commands_preserve_both_sticky_flags(self):
        original = subprocess.Popen
        for uncertain in (False, True):
            for drained in (False, True):
                for effect, exit_code in ((True, 0), (False, 0), (False, 1)):
                    with self.subTest(
                        uncertain=uncertain, drained=drained, effect=effect, code=exit_code
                    ):
                        runtime = self.runtime(time.monotonic() + 3)
                        runtime.uncertain, runtime.family_drained = uncertain, drained

                        def launch(argv, code=exit_code, **kwargs):
                            return original(
                                [sys.executable, "-I", "-c", f"import sys; sys.exit({code})"],
                                **kwargs,
                            )

                        with patch("subprocess.Popen", side_effect=launch):
                            result = runtime.run("synthetic", effect=effect, success=False)
                        self.assertEqual(result.returncode, exit_code)
                        self.assertEqual(runtime.uncertain, uncertain)
                        self.assertEqual(runtime.family_drained, drained)

    def test_real_non_db_removal_failure_continues_safe_cleanup_and_retains_db(self):
        from omnis_cli.start import cleanup_attempt

        original = subprocess.Popen
        for exit_code in (1, -9):
            with (
                self.subTest(exit_code=exit_code),
                tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as directory,
            ):
                runtime = self.runtime(time.monotonic() + 3)
                calls, removed, children = [], set(), []
                identities = ["api-id", "supervisor-id", "db-id"]

                def launch(argv, code=exit_code, owned=children, **kwargs):
                    failed = argv[-3:] == ["container", "rm", "api-id"]
                    script = (
                        (
                            "import sys; sys.exit(1)"
                            if code == 1
                            else "import os; os.kill(os.getpid(),9)"
                        )
                        if failed
                        else "pass"
                    )
                    child = original([sys.executable, "-I", "-c", script], **kwargs)
                    owned.append(child)
                    return child

                def command(*args, owner=runtime, history=calls, removed_ids=removed, **kwargs):
                    history.append(args)
                    result = ControlRuntime.run(owner, *args, **kwargs)
                    if args[:2] == ("container", "rm"):
                        removed_ids.add(args[-1])
                    return result

                def inspect(kind, ident, removed_ids=removed):
                    if ident in removed_ids:
                        return None
                    return {
                        "Config": {
                            "Labels": {"com.docker.compose.service": ident.removesuffix("-id")}
                        },
                        "State": {"Running": False},
                    }

                with (
                    patch("subprocess.Popen", side_effect=launch),
                    patch.object(runtime, "run", side_effect=command),
                    patch.object(
                        runtime,
                        "ids",
                        side_effect=lambda inventory=identities, removed_ids=removed: [
                            i for i in inventory if i not in removed_ids
                        ],
                    ),
                    patch.object(runtime, "inspect", side_effect=inspect),
                    patch.object(runtime, "attest", return_value={}),
                    patch("os.killpg") as numeric,
                    patch("os.kill") as pid_numeric,
                ):
                    root = Path(directory)
                    problems = cleanup_attempt(runtime, root, root, 8765, None, -1)
                numeric.assert_not_called()
                pid_numeric.assert_not_called()
                self.assertEqual([c.returncode for c in children], [0, exit_code, 0, 0])
                self.assertIn("container removal", problems)
                self.assertIn("database retained under uncertain writers", problems)
                self.assertEqual(removed, {"supervisor-id"})
                self.assertEqual(
                    calls,
                    [
                        ("container", "stop", "--time", "15", "api-id"),
                        ("container", "rm", "api-id"),
                        ("container", "stop", "--time", "15", "supervisor-id"),
                        ("container", "rm", "supervisor-id"),
                    ],
                    "Safe independent supervisor cleanup must continue, with zero DB effects",
                )
                self.assertTrue(runtime.uncertain)
                self.assertEqual(runtime.family_drained, exit_code == 1)

    def test_signal_exit_marks_uncertainty_even_when_success_is_not_required(self):
        original = subprocess.Popen
        for success in (True, False):
            with self.subTest(success=success):
                runtime = self.runtime(time.monotonic() + 5)
                children = []

                def launch(argv, owned=children, **kwargs):
                    child = original(
                        [sys.executable, "-I", "-c", "import os,signal; os.kill(os.getpid(),9)"],
                        **kwargs,
                    )
                    owned.append(child)
                    return child

                with (
                    patch("subprocess.Popen", side_effect=launch),
                    patch("os.killpg") as group_signal,
                ):
                    if success:
                        with self.assertRaisesRegex(StartError, "LOCAL_SERVICE_COMMAND_FAILED"):
                            runtime.run("start", "synthetic", effect=True, success=success)
                    else:
                        result = runtime.run("start", "synthetic", effect=True, success=success)
                        self.assertEqual(result.returncode, -9)
                self.assertEqual(children[0].returncode, -9)
                group_signal.assert_not_called()  # The leader has already been reaped.
                self.assertTrue(runtime.uncertain, "Signal exit lost the daemon ACK")
                self.assertFalse(runtime.family_drained, "Leader reap is not family drainage")

    def test_signal_producer_reaches_uncertain_startup_without_database_teardown(self):
        self.check_signal_startup(interrupt_close=False)

    def test_interrupt_at_pipe_close_keeps_database_and_uncertain_journal(self):
        self.check_signal_startup(interrupt_close=True)

    def check_signal_startup(self, *, interrupt_close):
        import contextlib
        import importlib
        import io
        import json
        from types import SimpleNamespace

        from omnis_cli.main import main

        start = importlib.import_module("omnis_cli.start")
        original = subprocess.Popen
        with tempfile.TemporaryDirectory(prefix="sc-", dir=os.environ["TMPDIR"]) as name:
            root = Path(name)
            (root / "d/omnis").mkdir(parents=True, mode=0o700)
            runtime = self.runtime(time.monotonic() + 5)
            runtime.receipt = SimpleNamespace(
                project="omnis-local-" + "a" * 32,
                image_id="sha256:" + "b" * 64,
                docker_id="test-daemon",
            )
            runtime.digest = "c" * 64
            children, effects = [], []

            def launch(argv, **kwargs):
                child = original(
                    [sys.executable, "-I", "-c", "import os; os.kill(os.getpid(),9)"], **kwargs
                )
                children.append(child)
                close = child.stdout.close

                def interrupted_close():
                    close()
                    if interrupt_close:
                        self.assertEqual(child.returncode, -9)
                        os.kill(os.getpid(), signal.SIGTERM)

                child.stdout.close = interrupted_close
                return child

            def create(*args, **kwargs):
                return ControlRuntime.run(runtime, "create", "synthetic", effect=True)

            def effect(*args, **kwargs):
                effects.append(args)
                return subprocess.CompletedProcess(args, 0, "", "")

            def inspect(kind, ident):
                if kind == "network":
                    return None
                return {
                    "Config": {"Labels": {"com.docker.compose.service": "db"}},
                    "State": {"Running": False},
                }

            out = io.StringIO()
            with (
                patch.dict(
                    os.environ,
                    {
                        "XDG_DATA_HOME": str(root / "d"),
                        "XDG_STATE_HOME": str(root / "s"),
                        "XDG_RUNTIME_DIR": str(root / "r"),
                    },
                ),
                patch.object(start, "ControlRuntime", return_value=runtime),
                patch.object(start, "preflight_port"),
                patch.object(start, "validate_config"),
                patch.object(runtime, "compose", side_effect=create),
                patch.object(runtime, "ids", side_effect=lambda: ["db-owned"] if children else []),
                patch.object(runtime, "inspect", side_effect=inspect),
                patch.object(runtime, "attest", return_value={}),
                patch.object(runtime, "run", side_effect=effect),
                patch("subprocess.Popen", side_effect=launch),
                patch("os.killpg") as group_signal,
                contextlib.redirect_stdout(out),
            ):
                code = main(["start", "--no-open", "--json"])
            self.assertEqual(children[0].returncode, -9)
            group_signal.assert_not_called()
            self.assertEqual(effects, [], "Unreconciled effect must retain DB before exit 4")
            self.assertEqual(code, 4)
            result = json.loads(out.getvalue())
            self.assertEqual(result["state"], "UNCERTAIN")
            self.assertEqual(result["reason"], "STARTUP_CLEANUP_UNCERTAIN")
            journal = json.loads((root / "s/omnis/startup.json").read_text())
            self.assertEqual(journal["phase"], "UNCERTAIN")
            self.assertEqual(
                journal["failure"],
                "STARTUP_FAILED" if interrupt_close else "LOCAL_SERVICE_COMMAND_FAILED",
            )
            self.assertEqual(journal["failed_phase"], "STARTING")
            self.assertEqual(journal["project"], runtime.receipt.project)
            self.assertIn("database retained under uncertain writers", journal["cleanup"])
            self.assertTrue((root / "s/omnis/postgres").is_dir())

    def test_command_outcomes_do_not_confuse_refusal_with_lost_ack(self):
        original = subprocess.Popen
        cases = (
            ("success", "print('ack')", True, 0, False, True, None),
            ("known_read_refusal", "import sys; sys.exit(1)", False, 1, False, True, None),
            ("lost_ack", "import sys; sys.exit(1)", True, 1, True, True, None),
            ("decode", r"import os; os.write(1,b'\xff')", True, 0, True, False, UnicodeError),
            ("signal_read", "import os; os.kill(os.getpid(),9)", False, -9, False, False, None),
            ("timeout", "import time; time.sleep(30)", True, None, True, False, StartError),
            (
                "eof_before_exit",
                "import os,time; os.close(1); os.close(2); time.sleep(30)",
                True,
                None,
                True,
                False,
                StartError,
            ),
        )
        for label, script, effect, code, uncertain, drained, error in cases:
            with self.subTest(outcome=label):
                runtime = self.runtime(time.monotonic() + 5)
                children = []

                def launch(argv, program=script, owned=children, **kwargs):
                    child = original([sys.executable, "-I", "-c", program], **kwargs)
                    owned.append(child)
                    return child

                with patch("subprocess.Popen", side_effect=launch):
                    if error is not None:
                        with self.assertRaises(error):
                            runtime.run("synthetic", success=False, effect=effect, cap=0.3)
                    else:
                        result = runtime.run("synthetic", success=False, effect=effect, cap=1)
                        self.assertEqual(result.returncode, code)
                self.assertIsNotNone(children[0].returncode)
                self.assertEqual(runtime.uncertain, uncertain)
                self.assertEqual(runtime.family_drained, drained)

    def test_exception_after_reap_never_signals_recycled_group(self):
        original = subprocess.Popen
        runtime = self.runtime(time.monotonic() + 5)
        children = []

        def launch(argv, **kwargs):
            child = original([sys.executable, "-I", "-c", "pass"], **kwargs)
            children.append(child)
            wait = child.wait

            def interrupted_wait(*args, **kwargs):
                wait(*args, **kwargs)
                raise StartError("SYNTHETIC_AFTER_REAP", 3)

            child.wait = interrupted_wait
            return child

        with patch("subprocess.Popen", side_effect=launch), patch("os.killpg") as group_signal:
            with self.assertRaisesRegex(StartError, "SYNTHETIC_AFTER_REAP"):
                runtime.run("synthetic", effect=True)
        self.assertEqual(children[0].returncode, 0)
        group_signal.assert_not_called()
        self.assertTrue(runtime.uncertain)
        self.assertFalse(runtime.family_drained)

    def test_repeated_interrupt_between_kernel_reap_and_returncode_never_signals(self):
        import importlib

        interrupt = importlib.import_module("omnis_cli.start")._interrupt
        original = subprocess.Popen
        for interrupts in (1, 2):
            with self.subTest(interrupts=interrupts):
                runtime = self.runtime(time.monotonic() + 5)
                children, events = [], []

                def launch(argv, count=interrupts, owned=children, observed=events, **kwargs):
                    child = original([sys.executable, "-I", "-c", "pass"], **kwargs)
                    owned.append(child)
                    handle = child._handle_exitstatus

                    def interrupted_status(status):
                        if len(observed) < count:
                            with self.assertRaises(ChildProcessError):
                                os.waitpid(child.pid, os.WNOHANG)
                            observed.append(child.returncode)
                            os.kill(os.getpid(), signal.SIGTERM)
                        handle(status)

                    child._handle_exitstatus = interrupted_status
                    return child

                previous = signal.signal(signal.SIGTERM, interrupt)
                try:
                    with patch("subprocess.Popen", side_effect=launch), patch("os.killpg") as kill:
                        with self.assertRaises(KeyboardInterrupt):
                            runtime.run("synthetic", effect=True)
                    kill.assert_not_called()
                    self.assertEqual(events, [None] * interrupts)
                    self.assertTrue(runtime.uncertain)
                    self.assertFalse(runtime.family_drained)
                finally:
                    signal.signal(signal.SIGTERM, previous)
                    for child in children:
                        child.wait(timeout=2)
                        if child.stdout:
                            child.stdout.close()
                        if child.stderr:
                            child.stderr.close()

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
