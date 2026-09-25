"""Regression: inherited TERMINAL_CWD hid trusted Omnis project skills."""
from pathlib import Path
import os
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "hermes_dev.py"


class HermesLaunchTests(unittest.TestCase):
    def test_launcher_exposes_project_check_without_starting_a_model(self):
        env = {**os.environ, "TERMINAL_CWD": str(Path.home())}
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--check"],
            cwd=Path.home(), env=env, text=True, capture_output=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        import json
        report = json.loads(result.stdout)
        self.assertEqual(report["cwd"], str(ROOT))
        self.assertEqual(report["TERMINAL_CWD"], str(ROOT))
        self.assertEqual(report["command"], ["hermes"])
        self.assertNotIn("environment", report)

    def test_arguments_are_preserved_without_shell_interpretation(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--check", "chat", "-q", "a; $(literal)"],
            text=True, capture_output=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        import json
        self.assertEqual(json.loads(result.stdout)["command"], ["hermes", "chat", "-q", "a; $(literal)"])


    def test_execution_pins_workspace_and_preserves_profile(self):
        import runpy
        from unittest import mock
        main = runpy.run_path(str(SCRIPT))["main"]
        args = ["chat", "-q", "literal ; $(untouched)"]
        with mock.patch.object(sys, "argv", [str(SCRIPT), *args]), mock.patch.dict(
            os.environ, {"TERMINAL_CWD": str(Path.home()), "HERMES_HOME": "profile-sentinel"}
        ), mock.patch("os.chdir") as chdir, mock.patch("os.execvpe") as execute:
            self.assertEqual(main(), 0)
            chdir.assert_called_once_with(ROOT)
            binary, command, environment = execute.call_args.args
            self.assertEqual(binary, "hermes")
            self.assertEqual(command, ["hermes", *args])
            self.assertEqual(environment["TERMINAL_CWD"], str(ROOT))
            self.assertEqual(environment["HERMES_HOME"], "profile-sentinel")

    def test_check_never_executes_or_dumps_environment(self):
        import io
        import runpy
        from unittest import mock
        main = runpy.run_path(str(SCRIPT))["main"]
        output = io.StringIO()
        with mock.patch.object(sys, "argv", [str(SCRIPT), "--check"]), mock.patch.dict(
            os.environ, {"PRIVATE_SENTINEL": "must-not-appear-452"}
        ), mock.patch("os.execvpe") as execute, mock.patch("sys.stdout", output):
            self.assertEqual(main(), 0)
            execute.assert_not_called()
        self.assertNotIn("must-not-appear-452", output.getvalue())
        self.assertNotIn("PRIVATE_SENTINEL", output.getvalue())

    def test_missing_executable_is_a_reported_failure(self):
        import io
        import runpy
        from unittest import mock
        main = runpy.run_path(str(SCRIPT))["main"]
        error = io.StringIO()
        with mock.patch.object(sys, "argv", [str(SCRIPT)]), mock.patch("os.chdir"), mock.patch(
            "os.execvpe", side_effect=FileNotFoundError("test executable missing")
        ), mock.patch("sys.stderr", error):
            self.assertEqual(main(), 127)
        self.assertIn("Cannot start Hermes", error.getvalue())


if __name__ == "__main__":
    unittest.main()
