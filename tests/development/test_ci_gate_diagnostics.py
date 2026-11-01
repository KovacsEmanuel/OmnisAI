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
# SOURCE calibration: pytest 9.1.1 -q on one inert parametrized failure.
PYTEST_SELECTOR = "api/tests/test_health.py::test_live_rejects_a_foreign_host"
PYTEST_LOG = f"""E       AssertionError: {SECRET}
api/tests/test_health.py:5: AssertionError
FAILED {PYTEST_SELECTOR}[{SECRET}]
1 failed in 0.01s
"""


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

    def test_workflow_selects_exact_log_in_full_scratch_layout(self):
        result, called = self.workflow(7, large=True)
        self.assertEqual(result.returncode, 7)
        self.assertTrue(called)
        self.assertIn("CANONICAL_GATE_BEGIN target=check-components log=", result.stdout)
        self.assertIn("::error::make target: check-development", result.stdout)
        self.assertNotIn("::error::make target: check-docs", result.stdout)
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

    def test_workflow_pytest_failure_in_full_scratch_layout(self):
        limit = runpy.run_path(str(SCRIPT))["MAX_LOG_BYTES"]
        result, called = self.workflow(7, large=True, content="x" * (limit + 1) + "\n" + PYTEST_LOG)
        self.assertEqual(result.returncode, 7)
        self.assertTrue(called)
        self.assertIn(f"::error::pytest: {PYTEST_SELECTOR}", result.stdout)
        self.assertIn("::error::source: api/tests/test_health.py:5", result.stdout)
        self.assertNotIn(SECRET, result.stdout + result.stderr)

    def test_workflow_capture_failures_preserve_gate_or_fail_healthy_gate(self):
        for failure in ("tee", "mktemp"):
            for code in (0, 7):
                with self.subTest(failure=failure, code=code):
                    result, called = self.workflow(code, capture_failure=failure)
                    self.assertEqual(result.returncode, code or 9)
                    self.assertFalse(called)
                    self.assertIn("PUBLIC_BEFORE", result.stdout)
                    self.assertIn("PUBLIC_AFTER", result.stdout)
                    self.assertIn("(outer-capture-failed)", result.stdout)
                    self.assertNotIn(SECRET, result.stdout + result.stderr)

    def test_workflow_fallback_output_failures_preserve_gate_exit(self):
        for broken, code in ((False, 7), (True, 7), (False, 0)):
            with self.subTest(reporter_failure=broken, code=code), open("/dev/full", "w") as output:
                # Quiet make lets real tee succeed so the reporter fallback is reached.
                result, called = self.workflow(
                    code, broken=broken, quiet=broken, stdout=output.fileno()
                )
                self.assertEqual(called, broken)
                self.assertIn("printf: write error", result.stderr)
                self.assertNotIn(SECRET, result.stderr)
                self.assertEqual(result.returncode, code or 1)

    def test_pytest_selectors_require_tracked_source_and_exact_ast_names(self):
        module = runpy.run_path(str(SCRIPT))
        selector = f"tests/development/test_test_db_gate.py::SafeTestDatabaseGateTests::{METHOD}"
        messages = module["summarize"](
            f"FAILED {selector}[{SECRET}] - AssertionError: {SECRET}\n"
            f"ERROR {PYTEST_SELECTOR} - ValueError: {SECRET}\n"
            f"FAILED {selector.replace('SafeTestDatabaseGateTests', 'UnknownClass')}\n"
            f"FAILED {selector.replace(METHOD, 'test_unknown')}\n"
            f"FAILED untracked.py::test_unknown[{SECRET}]\n"
        )
        self.assertEqual(messages, [f"pytest: {selector}", f"pytest: {PYTEST_SELECTOR}"])

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
FAILED api/tests/test_health.py::test_{SECRET}[{SECRET}]
FAILED api/tests/../{SECRET}.py::test_live_rejects_a_foreign_host
api/tests/test_health.py:999999: {SECRET}
'''
        messages = module["summarize"](malicious)
        self.assertEqual(messages, ["exception: AssertionError"])
        result, called = self.workflow(7, content=FAILED_LOG + malicious)
        self.assertEqual(result.returncode, 7)
        self.assertTrue(called)
        self.assertNotIn(SECRET, result.stdout + result.stderr)
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
            messages = module["diagnostics"](root, self.outer(root))
            self.assertIn("make target: check-development", messages)
            self.assertNotIn("make target: check-docs", messages)
            self.assertNotIn(SECRET, "\n".join(messages))

    def test_file_and_output_counts_are_bounded(self):
        module = runpy.run_path(str(SCRIPT))
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as raw:
            root = Path(raw)
            for number in range(8):
                self.log(root, FAILED_LOG, f"db-{number:016x}")
            log = self.log(root, FAILED_LOG)
            outer = self.outer(root)
            diagnostics = module["diagnostics"]
            calls = []
            original = diagnostics.__globals__["summarize"]
            diagnostics.__globals__["summarize"] = lambda text: calls.append(text) or original(text)
            self.assertTrue(diagnostics(root, outer))
            self.assertEqual(len(calls), 1)
            log.write_text(
                "".join(
                    f'  File "{ROOT}/ops/run_test_db_gate.py", line {line}, in prepare_paths\n'
                    for line in range(1, 100)
                )
                + FAILED_LOG
            )
            messages = diagnostics(root, outer)
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
                    [sys.executable, "-I", "-B", str(SCRIPT), str(owned), str(self.outer(owned))],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                self.assertEqual(result.returncode, 0)
                reason = "root-unsafe" if kind == "root-link" else "log-unsafe"
                self.assertEqual(
                    result.stdout, module["annotation"](module["unavailable"](reason)[0]) + "\n"
                )
                self.assertEqual(result.stderr, "")

    def test_missing_or_unclassified_log_is_explicitly_unavailable(self):
        module = runpy.run_path(str(SCRIPT))
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as raw:
            root = Path(raw)
            outer = self.outer(root)
            self.assertEqual(
                module["diagnostics"](root, outer), module["unavailable"]("log-unsafe")
            )
            self.log(root, SECRET)
            self.assertEqual(
                module["diagnostics"](root, outer), module["unavailable"]("log-unclassified")
            )

    def test_exact_locator_refusals_and_outer_bounds(self):
        module = runpy.run_path(str(SCRIPT))
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as raw:
            root = Path(raw)
            self.log(root, FAILED_LOG)
            outer = self.outer(root)
            valid = outer.read_text()
            cases = {
                "locator-missing": "public output only\n",
                "locator-duplicate": valid + valid,
                "locator-truncated": valid.rstrip("\n"),
                "locator-foreign": valid.replace(str(root), str(root) + "-foreign"),
                "locator-invalid": valid.replace("db-0123456789abcdef", "db-wrong"),
                "outer-bounds": valid + "x" * (module["MAX_OUTER_BYTES"] - len(valid.encode()) + 1),
            }
            for reason, content in cases.items():
                with self.subTest(reason=reason):
                    outer.write_text(content)
                    self.assertEqual(
                        module["diagnostics"](root, outer), module["unavailable"](reason)
                    )
            for content in (
                valid.replace("check-components", "check-docs"),
                valid.replace("gate.log", "../gate.log"),
                valid.replace("gate.log", f"$(touch {root}/injected)"),
            ):
                outer.write_text(content)
                self.assertEqual(
                    module["diagnostics"](root, outer), module["unavailable"]("locator-invalid")
                )
            self.assertFalse((root / "injected").exists())
            outer.write_text(valid + "x" * (module["MAX_OUTER_BYTES"] - len(valid.encode())))
            self.assertIn("make target: check-development", module["diagnostics"](root, outer))

    def test_workflow_rejects_missing_duplicate_foreign_and_truncated_locator(self):
        for kind in ("missing", "duplicate", "foreign", "truncated", "invalid"):
            with self.subTest(kind=kind):
                result, called = self.workflow(7, marker=kind, large=True)
                self.assertEqual(result.returncode, 7)
                self.assertTrue(called)
                self.assertIn(f"(locator-{kind})", result.stdout)
                self.assertNotIn("::error::make target:", result.stdout)

    def test_private_root_child_and_outer_file_guards(self):
        module = runpy.run_path(str(SCRIPT))
        for kind in ("root", "child", "public", "symlink", "hardlink", "fifo", "directory"):
            with (
                self.subTest(kind=kind),
                tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as raw,
            ):
                root = Path(raw)
                log = self.log(root, FAILED_LOG)
                outer = self.outer(root)
                reason = "outer-unsafe"
                if kind == "root":
                    root.chmod(0o755)
                    reason = "root-unsafe"
                elif kind == "child":
                    log.parent.chmod(0o755)
                    reason = "log-unsafe"
                elif kind == "public":
                    outer.chmod(0o644)
                elif kind in ("symlink", "hardlink"):
                    saved = root / "saved"
                    outer.rename(saved)
                    if kind == "symlink":
                        outer.symlink_to(saved)
                    else:
                        os.link(saved, outer)
                else:
                    outer.unlink()
                    if kind == "fifo":
                        os.mkfifo(outer, 0o600)
                    else:
                        outer.mkdir(mode=0o700)
                self.assertEqual(module["diagnostics"](root, outer), module["unavailable"](reason))

    def outer(self, root):
        outer = root / "ci-outer.12345678"
        outer.write_text(
            f"CANONICAL_GATE_BEGIN target=check-components log={root}/db-0123456789abcdef/gate.log\n"
        )
        outer.chmod(0o600)
        return outer

    def log(self, root, content, name="db-0123456789abcdef"):
        directory = root / name
        directory.mkdir(mode=0o700)
        log = directory / "gate.log"
        log.write_text(content)
        log.chmod(0o600)
        return log

    def workflow(
        self,
        exit_code,
        broken=False,
        large=False,
        content=FAILED_LOG,
        capture_failure=None,
        marker="valid",
        quiet=False,
        stdout=subprocess.PIPE,
    ):
        workflow = (ROOT / ".github/workflows/ci.yml").read_text()
        step = workflow.split(
            "      - name: Run the local gate against a dedicated PostgreSQL instance\n", 1
        )[1]
        self.assertIn("        shell: bash\n", step)
        shell = textwrap.dedent(step.split("        run: |\n", 1)[1])
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as raw:
            root = Path(raw)
            bin_dir = root / "runner/omnis-docs/bin"
            bin_dir.mkdir(parents=True)
            if large:
                scratch = root / "home/.cache/omnis-ci-source-1"
                scratch.mkdir(parents=True, mode=0o700)
                for number in range(154):
                    (scratch / f"unrelated-{number}").mkdir()
                for number in range(8):
                    self.log(
                        scratch,
                        "make: *** [Makefile:208: check-docs] Error 1\n",
                        f"db-{number:016x}",
                    )
            (root / "input.log").write_text(content)
            executable(bin_dir / "docker", 'test "$1" = pull\n')
            begin = 'printf "CANONICAL_GATE_BEGIN target=check-components log=%s/db-0123456789abcdef/gate.log\\n" "$TMPDIR"\n'
            if marker == "missing":
                begin = ""
            elif marker == "duplicate":
                begin *= 2
            elif marker == "foreign":
                begin = begin.replace("%s/db-", "%s-foreign/db-")
            elif marker == "truncated":
                begin = begin.replace("gate.log\\n", "gate.log")
            elif marker == "invalid":
                begin = begin.replace("check-components", "check-docs")
            executable(
                bin_dir / "make",
                'test "$*" = check\n'
                'install -d -m 0700 "$TMPDIR/db-0123456789abcdef"\n'
                'cp "$SOURCE_ROOT/input.log" "$TMPDIR/db-0123456789abcdef/gate.log"\n'
                'chmod 0600 "$TMPDIR/db-0123456789abcdef/gate.log"\n'
                + ("" if quiet else 'printf "PUBLIC_BEFORE\\nPUBLIC_AFTER\\n"\n' + begin)
                + f"exit {exit_code}\n",
            )
            if capture_failure:
                executable(
                    bin_dir / capture_failure,
                    ("cat\n" if capture_failure == "tee" else "")
                    + f"printf '{SECRET}\\n' >&2\nexit 9\n",
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
                stdout=stdout,
                stderr=subprocess.PIPE,
                text=True,
                timeout=10,
            )
            scratch = root / "home/.cache/omnis-ci-source-1"
            for capture in scratch.glob("ci-outer.*"):
                self.assertEqual(capture.stat().st_mode & 0o777, 0o600)
            return result, (root / "called").exists()


if __name__ == "__main__":
    unittest.main()
