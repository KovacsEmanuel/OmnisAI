"""SOURCE controls: execute the workflow shell, never Docker or the real gate."""

import os
import runpy
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/ci_gate_diagnostics.py"
SECRET = "SYNTHETIC_PRIVATE_VALUE_DO_NOT_PUBLISH"
METHOD = "test_prepares_only_a_new_private_root_and_refuses_reuse"
SELECTOR = f"test_test_db_gate.SafeTestDatabaseGateTests.{METHOD}"
# Layout from the retained local failed gate; values are deliberately synthetic.
FAILED_LOG = f'''ERROR: {METHOD} ({SELECTOR})
Traceback (most recent call last):
  File "{ROOT}/tests/development/test_test_db_gate.py", line 762, in {METHOD}
    private_value = "{SECRET}"
  File "{ROOT}/ops/run_test_db_gate.py", line 63, in prepare_paths
<run_path>.UnsafeFixture: {SECRET}
make: *** [Makefile:212: check-development] Error 1
'''


def executable(path, content):
    path.write_text("#!/bin/bash\nset -eu\n" + content)
    path.chmod(0o700)


class CiGateDiagnosticsTests(unittest.TestCase):
    def test_workflow_failure_annotations_preserve_actual_exit(self):
        result, called = self.workflow(7)
        self.assertEqual(result.returncode, 7)
        self.assertTrue(called)
        self.assertIn("::error::make target: check-development", result.stdout)
        self.assertIn(f"::error::unittest: {SELECTOR}", result.stdout)
        self.assertIn("::error::source: ops/run_test_db_gate.py:63", result.stdout)
        self.assertIn("::error::exception: UnsafeFixture", result.stdout)
        self.assertNotIn(SECRET, result.stdout + result.stderr)

    def test_workflow_success_does_not_run_diagnostics(self):
        result, called = self.workflow(0)
        self.assertEqual(result.returncode, 0)
        self.assertFalse(called)
        self.assertNotIn("::error", result.stdout + result.stderr)

    def test_workflow_diagnostic_failure_cannot_mask_gate_exit(self):
        result, called = self.workflow(7, broken=True)
        self.assertEqual(result.returncode, 7)
        self.assertTrue(called)
        self.assertIn("::error::Gate diagnostics unavailable", result.stdout)
        self.assertNotIn(SECRET, result.stdout + result.stderr)

    def test_untrusted_values_and_commands_are_not_published(self):
        module = runpy.run_path(str(SCRIPT))
        malicious = f'''::error::{SECRET}
AssertionError: {SECRET} https://example.invalid/?token={SECRET}
ERROR: test_{SECRET} (test_test_db_gate.SafeTestDatabaseGateTests.test_{SECRET})
ERROR: {METHOD} ({SELECTOR}) (password='{SECRET}')
make: *** [Makefile:212: check-{SECRET}] Error 1
  File "{ROOT}/ops/../{SECRET}.py", line 1, in {SECRET}
{SECRET}: request_payload={SECRET}
SafeTestDatabaseGateTests: {SECRET}
'''
        messages = module["summarize"](malicious)
        self.assertEqual(messages, ["exception: AssertionError"])
        self.assertEqual(
            module["annotation"]("synthetic%\r\n::error::ignored"),
            "::error::synthetic%25%0D%0A::error::ignored",
        )

    def test_read_bounds_keep_tail_without_publishing_head(self):
        module = runpy.run_path(str(SCRIPT))
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as raw:
            root = Path(raw)
            log = self.log(root, "make: *** [Makefile:212: check-docs] Error 1\n")
            with log.open("a") as output:
                output.write("x" * (module["MAX_LOG_BYTES"] + 1) + "\n" + FAILED_LOG)
            messages = module["diagnostics"](root)
            self.assertIn("make target: check-development", messages)
            self.assertNotIn("make target: check-docs", messages)
            self.assertNotIn(SECRET, "\n".join(messages))

    def test_file_and_output_counts_are_bounded(self):
        module = runpy.run_path(str(SCRIPT))
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as raw:
            root = Path(raw)
            for number in range(module["MAX_LOGS"] + 1):
                self.log(root, FAILED_LOG, f"db-{number:016x}")
            diagnostics = module["diagnostics"]
            calls = []
            original = diagnostics.__globals__["summarize"]
            diagnostics.__globals__["summarize"] = lambda text: calls.append(text) or original(text)
            self.assertTrue(diagnostics(root))
            self.assertEqual(len(calls), module["MAX_LOGS"])
            for child in root.iterdir():
                (child / "gate.log").write_text(
                    "".join(
                        f'  File "{ROOT}/ops/run_test_db_gate.py", line {line}, in prepare_paths\n'
                        for line in range(1, 100)
                    )
                    + FAILED_LOG
                )
            messages = diagnostics(root)
            self.assertIn("make target: check-development", messages)
            self.assertEqual(len(messages), module["MAX_ANNOTATIONS"])
            self.assertLessEqual(len("\n".join(map(module["annotation"], messages))), 7200)

    def test_unsafe_files_and_directories_are_refused(self):
        module = runpy.run_path(str(SCRIPT))
        for kind in (
            "symlink",
            "hardlink",
            "fifo",
            "directory",
            "public",
            "parent-link",
            "root-link",
        ):
            with (
                self.subTest(kind=kind),
                tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as raw,
            ):
                root = Path(raw)
                owned = root / "owned"
                owned.mkdir(mode=0o700)
                log = self.log(owned, FAILED_LOG)
                outside = root / "outside"
                if kind in ("symlink", "hardlink", "parent-link"):
                    log.rename(outside)
                if kind == "symlink":
                    log.symlink_to(outside)
                elif kind == "hardlink":
                    os.link(outside, log)
                elif kind == "fifo":
                    log.unlink()
                    os.mkfifo(log, 0o600)
                elif kind == "directory":
                    log.unlink()
                    log.mkdir()
                elif kind == "public":
                    log.chmod(0o644)
                elif kind == "parent-link":
                    log.parent.rmdir()
                    log.parent.symlink_to(root, target_is_directory=True)
                else:
                    (root / "alias").symlink_to(owned, target_is_directory=True)
                    owned = root / "alias"
                result = subprocess.run(
                    [sys.executable, "-I", "-B", str(SCRIPT), str(owned)],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                self.assertEqual(result.returncode, 0)
                self.assertEqual(result.stdout, module["annotation"](module["UNAVAILABLE"]) + "\n")
                self.assertEqual(result.stderr, "")

    def test_missing_or_unclassified_log_is_explicitly_unavailable(self):
        module = runpy.run_path(str(SCRIPT))
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as raw:
            root = Path(raw)
            self.assertEqual(module["diagnostics"](root), [module["UNAVAILABLE"]])
            self.log(root, SECRET)
            self.assertEqual(module["diagnostics"](root), [module["UNAVAILABLE"]])

    def log(self, root, content, name="db-0123456789abcdef"):
        directory = root / name
        directory.mkdir(mode=0o700)
        log = directory / "gate.log"
        log.write_text(content)
        log.chmod(0o600)
        return log

    def workflow(self, exit_code, broken=False):
        workflow = (ROOT / ".github/workflows/ci.yml").read_text()
        step = workflow.split(
            "      - name: Run the local gate against a dedicated PostgreSQL instance\n", 1
        )[1]
        shell = textwrap.dedent(step.split("        run: |\n", 1)[1])
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as raw:
            root = Path(raw)
            bin_dir = root / "runner/omnis-docs/bin"
            bin_dir.mkdir(parents=True)
            (root / "input.log").write_text(FAILED_LOG)
            executable(bin_dir / "docker", 'test "$1" = pull\n')
            executable(
                bin_dir / "make",
                'test "$*" = check\n'
                'install -d -m 0700 "$TMPDIR/db-0123456789abcdef"\n'
                'cp "$SOURCE_ROOT/input.log" "$TMPDIR/db-0123456789abcdef/gate.log"\n'
                'chmod 0600 "$TMPDIR/db-0123456789abcdef/gate.log"\n'
                f"exit {exit_code}\n",
            )
            executable(
                bin_dir / "python",
                'touch "$SOURCE_ROOT/called"\n'
                + (
                    f"printf '{SECRET}\\n' >&2\nexit 9\n"
                    if broken
                    else f'exec "{sys.executable}" "$@"\n'
                ),
            )
            env = {
                "PATH": f"{bin_dir}:/usr/bin:/bin",
                "HOME": str(root / "home"),
                "RUNNER_TEMP": str(root / "runner"),
                "GITHUB_RUN_ID": "source",
                "GITHUB_RUN_ATTEMPT": "1",
                "SOURCE_ROOT": str(root),
            }
            result = subprocess.run(
                ["bash", "--noprofile", "--norc", "-e", "-o", "pipefail", "-c", shell],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result, (root / "called").exists()


if __name__ == "__main__":
    unittest.main()
