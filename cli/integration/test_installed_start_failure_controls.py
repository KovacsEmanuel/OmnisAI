"""Permanent controls of interrupted rescue/no-effects oracles, not OCI proof."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import installed_start_failures as failures
from start_oracle_probe import NoDocker


class InstalledFailureOracleTest(unittest.TestCase):
    def test_live_unjournaled_forwarder_fails_before_observer_rescue(self):
        result = subprocess.run(
            [sys.executable, "-I", str(Path(__file__).with_name("start_oracle_probe.py"))],
            capture_output=True,
            text=True,
            timeout=35,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(
            "PRE_RESCUE_FAIL_PRESERVED; OBSERVER_RESCUE_EXITED_LISTENER_ABSENT; NO_DB_EFFECTS",
            result.stdout,
        )

    def lock_control(self, effect):
        with tempfile.TemporaryDirectory(prefix="lo-", dir=os.environ["TMPDIR"]) as name:
            data = Path(name) / "data"
            (data / "omnis").mkdir(parents=True, mode=0o700)
            (data / "omnis").chmod(0o700)
            (data / "omnis/image.json").write_text("test-only")
            states = []

            def run(argv, **kw):
                state = Path(kw["env"]["HOME"])
                states.append(state)
                if effect:
                    control = Path(kw["env"]["XDG_RUNTIME_DIR"]) / "omnis"
                    control.mkdir(parents=True)
                    (control / "unexpected-effect").write_text("test-only")
                return subprocess.CompletedProcess(
                    argv,
                    2,
                    json.dumps(
                        {
                            "reason": "LIFECYCLE_BUSY",
                            "dashboard_ready": False,
                            "assessment_ready": False,
                        }
                    ),
                    "",
                )

            try:
                with (
                    patch.object(failures, "ControlRuntime", NoDocker),
                    patch.object(failures.subprocess, "run", run),
                    patch.object(failures.time, "monotonic", side_effect=[10, 10, 190, 190]),
                ):
                    if effect:
                        with self.assertRaisesRegex(AssertionError, "runtime|root|effect"):
                            failures.run_lock_expiry(
                                data, {"project": "test-only"}, "/synthetic-cli"
                            )
                    else:
                        failures.run_lock_expiry(data, {"project": "test-only"}, "/synthetic-cli")
            finally:
                # Only roots allocated by this test, not product/operator data.
                import shutil

                for state in states:
                    shutil.rmtree(state)

    def test_lock_no_effect_positive_control(self):
        self.lock_control(False)

    def test_lock_runtime_effect_negative_control(self):
        self.lock_control(True)
