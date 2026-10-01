"""Acceptance observer must not manufacture cleanup after uncertainty."""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import installed_pair_open as probe
from installed_pair_open import tty_run
from installed_start import teardown


class InstalledStartObserverTest(unittest.TestCase):
    def test_slow_joined_implicit_start_gets_fresh_attestation_deadline(self):
        """Observer time is substituted; product startup and Docker are not proved here."""
        import contextlib
        import io
        import json
        import subprocess
        from unittest.mock import MagicMock, patch

        import installed_start as harness

        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
            state = Path(name)
            root = state / "s/omnis"
            root.mkdir(parents=True, mode=0o700)
            record = {
                "phase": "READY",
                "port": 8765,
                "attempt": "synthetic-attempt",
                "instance_id": "synthetic-instance",
                "containers": {"db": "db-id", "api": "api-id", "supervisor": "supervisor-id"},
            }
            (root / "startup.json").write_text(json.dumps(record))
            clock = {"now": 0.0}

            class Runtime:
                receipt = SimpleNamespace(image_id="sha256:" + "a" * 64)
                uncertain = False
                family_drained = True
                deadline = 0.0

                def ids(self):
                    assert self.deadline > clock["now"], "Stale observer deadline"
                    return list(record["containers"].values())

                def attest(self, *_args):
                    return {}

                def psql(self, *_args):
                    return "0"

            runtime = Runtime()
            data = state / "data"
            receipt = {"image_id": runtime.receipt.image_id, "project": "omnis-local-synthetic"}
            cli = "/synthetic/omnis"

            def make_runtime(_data, deadline):
                runtime.deadline = deadline
                return runtime

            def invoke(argv, **_kwargs):
                if argv == [cli]:
                    clock["now"] = 40.0  # A valid CLI may take > initial observer budget.
                    return subprocess.CompletedProcess(
                        argv,
                        3,
                        "Omnis READY: http://127.0.0.1:8765/ — BROWSER_LAUNCH_FAILED; "
                        "fereastra/sesiunea nu sunt verificate.\n",
                        "Deschiderea a eșuat; serviciile rămân pornite.\n",
                    )
                if argv == [cli, "status", "--json"]:
                    return subprocess.CompletedProcess(
                        argv,
                        0,
                        json.dumps(
                            {
                                "instance_id": record["instance_id"],
                                "dashboard_ready": True,
                                "assessment_ready": False,
                                "browser_opened": False,
                            }
                        ),
                        "",
                    )
                self.fail("Unexpected observer subprocess")

            with (
                patch.object(harness.time, "monotonic", side_effect=lambda: clock["now"]),
                patch.object(harness.socket, "socket", return_value=MagicMock()),
                patch.object(harness.tempfile, "mkdtemp", return_value=name),
                patch.object(harness, "ControlRuntime", side_effect=make_runtime),
                patch.object(harness.subprocess, "run", side_effect=invoke),
                patch.object(harness, "save_probe"),
                patch.object(harness, "teardown") as teardown,
                patch.object(harness, "assert_resources_absent") as absent,
                contextlib.redirect_stdout(io.StringIO()) as output,
            ):
                harness.run_installed_non_tty_default(data, receipt, cli)
            teardown.assert_called_once()
            absent.assert_called_once()
            self.assertIn("INSTALLED_DEFAULT_NON_TTY_VERIFIED", output.getvalue())

    def test_opener_observer_accepts_only_exact_outcome_for_exit_and_origin(self):
        origin = "http://127.0.0.1:8765"
        cases = (
            (0, "BROWSER_LAUNCH_ACCEPTED"),
            (2, "BROWSER_UNAVAILABLE"),
            (3, "BROWSER_LAUNCH_FAILED"),
            (3, "BROWSER_LAUNCH_UNCONFIRMED"),
        )
        for exit_code, outcome in cases:
            with self.subTest(outcome=outcome):
                line = (
                    f"Omnis READY: {origin}/ — {outcome}; fereastra/sesiunea nu sunt verificate.\n"
                )
                self.assertEqual(probe.opener_outcome(exit_code, line, origin), outcome)
        for exit_code, line in (
            (
                0,
                f"Omnis READY: {origin}/ — BROWSER_LAUNCH_UNCONFIRMED; fereastra/sesiunea nu sunt verificate.\n",
            ),
            (
                3,
                f"Omnis READY: {origin}/ — BROWSER_UNAVAILABLE; fereastra/sesiunea nu sunt verificate.\n",
            ),
            (
                3,
                "Omnis READY: http://127.0.0.1:9999/ — BROWSER_LAUNCH_FAILED; fereastra/sesiunea nu sunt verificate.\n",
            ),
            (
                3,
                f"Omnis READY: {origin}/ — BROWSER_LAUNCH_FAILED; fereastra/sesiunea nu sunt verificate.\nEXTRA",
            ),
        ):
            with self.subTest(exit_code=exit_code, line=line):
                with self.assertRaises(AssertionError):
                    probe.opener_outcome(exit_code, line, origin)

    def test_pty_overflow_before_join_is_uncertain_not_an_assertion_cleanup(self):
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
            root = Path(name)
            script = root / "noisy-owned-child"
            script.write_text(
                f"#!{sys.executable}\nimport os,time\nos.write(1,b'x'*128)\ntime.sleep(5)\n"
            )
            script.chmod(0o700)
            with self.assertRaises(RuntimeError):
                tty_run(str(script), [], root, {"PATH": "/usr/bin:/bin"}, limit=32)

    def test_retry_timeout_retains_uncertainty_before_any_rescue(self):
        import json
        import subprocess
        from unittest.mock import patch

        import installed_start as probe

        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
            state = Path(name)
            root = state / "s/omnis"
            root.mkdir(parents=True, mode=0o700)
            journal = root / "startup.json"
            initial = {"attempt": "synthetic", "phase": "VERIFYING", "containers": {}}
            journal.write_text(json.dumps(initial))
            journal.chmod(0o600)
            survivors = []
            runtime = SimpleNamespace(
                uncertain=False,
                family_drained=True,
                ids=lambda: list(survivors),
                network=lambda _: None,
            )
            process = SimpleNamespace(pid=12345, returncode=None, stdout=None, stderr=None)
            process.poll = lambda: process.returncode

            def completed(**kwargs):
                process.returncode = 3
                journal.write_text(
                    json.dumps(
                        {
                            **initial,
                            "phase": "FAILED_CLEANED",
                            "cleanup": [],
                            "failed_phase": "VERIFYING",
                        }
                    )
                )
                return '{"dashboard_ready":false}', ""

            process.communicate = completed

            def retry(*args, **kwargs):
                survivors.append("late-db")
                journal.write_text(json.dumps({**initial, "phase": "MIGRATING"}))
                raise subprocess.TimeoutExpired("synthetic retry", 40)

            def rescue(*args, **kwargs):
                survivors.clear()

            fd = os.open(os.devnull, os.O_RDONLY)
            try:
                with (
                    patch.object(probe.tempfile, "mkdtemp", return_value=str(state)),
                    patch.object(probe, "ControlRuntime", return_value=runtime),
                    patch.object(probe.subprocess, "Popen", return_value=process),
                    patch.object(probe.subprocess, "run", side_effect=retry),
                    patch.object(probe.os, "pidfd_open", return_value=fd),
                    patch.object(probe.signal, "pidfd_send_signal"),
                    patch.object(probe, "teardown", side_effect=rescue) as teardown_call,
                ):
                    with self.assertRaises((subprocess.TimeoutExpired, AssertionError)):
                        probe.run_interrupted_start(
                            state / "data", {"project": "synthetic"}, "/synthetic/omnis"
                        )
                self.assertFalse(
                    teardown_call.called, "Timed-out retry must not authorize DB rescue"
                )
                self.assertEqual(
                    json.loads((state / "probe-receipt.json").read_text())["cleanup"], "UNCERTAIN"
                )
            finally:
                try:
                    os.close(fd)
                except OSError:
                    pass

    def test_installed_gate_rejects_flags_that_could_fake_success(self):
        import subprocess

        for flag in ("-n", "-t", "-i", "-q"):
            with self.subTest(flag=flag):
                p = subprocess.run(
                    ["make", flag, "check-installed-start"],
                    cwd=Path(__file__).resolve().parents[2],
                    env={"PATH": "/usr/bin:/bin"},
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                self.assertEqual(p.returncode, 2)
                self.assertIn("Unsafe Make flags for verification", p.stderr)
                self.assertEqual(p.stdout, "")

    def test_resource_snapshot_observes_restart_with_same_cid(self):
        from installed_start import resource_snapshot

        item = {
            "Config": {"Labels": {"com.docker.compose.service": "api"}},
            "State": {"Running": True, "StartedAt": "first", "FinishedAt": "none"},
            "RestartCount": 0,
        }
        runtime = SimpleNamespace(
            ids=lambda: ["same-cid"], inspect=lambda *args: item, attest=lambda *args: item
        )
        before = resource_snapshot(runtime, Path("/"), Path("/"), 8765)
        item["State"]["StartedAt"] = "second"
        item["RestartCount"] = 1
        self.assertNotEqual(resource_snapshot(runtime, Path("/"), Path("/"), 8765), before)

    def test_false_failed_cleaned_is_rejected_before_rescue(self):
        from installed_start import assert_resources_absent

        runtime = SimpleNamespace(ids=lambda: ["survivor"])
        with self.assertRaisesRegex(AssertionError, "Claimed cleanup left containers"):
            assert_resources_absent(runtime, Path("/"), Path("/"), {})

    def test_private_locator_survives_teardown_failure(self):
        import json

        from installed_start import save_probe

        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
            state = Path(name)
            save_probe(
                state,
                state / "data",
                "synthetic-project",
                state / "state",
                {},
                probe="PREPARED",
                cleanup="NOT_RUN",
            )
            path = state / "probe-receipt.json"
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            try:
                raise OSError("synthetic teardown failure")
            except OSError:
                save_probe(
                    state,
                    state / "data",
                    "synthetic-project",
                    state / "state",
                    {},
                    probe="FAIL",
                    cleanup="UNCERTAIN",
                )
            value = json.loads(path.read_text())
            self.assertEqual(value["cleanup"], "UNCERTAIN")
            self.assertEqual(value["state_root"], str(state / "state"))

    def test_unreconciled_daemon_or_cli_family_cannot_be_rescued_as_clean(self):
        for reason in ("daemon outcome uncertain", "CLI descendants uncertain"):
            with (
                self.subTest(reason=reason),
                tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name,
            ):
                root = Path(name)
                (root / "postgres").mkdir()
                calls = []

                class Runtime:
                    deadline = 0
                    uncertain = True
                    family_drained = False
                    receipt = SimpleNamespace(project="synthetic-project")

                    def ids(self, history=calls):
                        return [] if history else ["owned-db"]

                    def inspect(self, *args):
                        return {
                            "Config": {"Labels": {"com.docker.compose.service": "db"}},
                            "State": {"Running": False},
                        }

                    def attest(self, *args):
                        return {}

                    def run(self, *args, history=calls, **kwargs):
                        history.append(args)

                    def network(self, *args):
                        return None

                record = {"attempt": "synthetic", "phase": "UNCERTAIN", "cleanup": [reason]}
                failure = ""
                try:
                    teardown(Runtime(), root, root, 8765, record)
                except AssertionError as exc:
                    failure = str(exc)
                self.assertFalse(calls, "Test rescue cannot erase unsettled writer evidence")
                self.assertIn("Unreconciled", failure)
