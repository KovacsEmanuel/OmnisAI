"""Acceptance observer must not manufacture cleanup after uncertainty."""

import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from installed_start import teardown


class InstalledStartObserverTest(unittest.TestCase):
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
