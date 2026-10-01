"""Installed open/default are verified operator actions, not assessment browsers."""

import contextlib
import io
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from omnis_cli.main import main


class BrowserTest(unittest.TestCase):
    def test_implicit_fresh_tty_issues_code_before_open(self):
        class Tty(io.StringIO):
            def isatty(self):
                return True

        events = []
        ready = {"origin": "http://127.0.0.1:8765", "reused": False}
        with (
            patch("omnis_cli.main.start_result", return_value=(0, ready)),
            patch("omnis_cli.main.pair", side_effect=lambda **_kw: events.append("pair") or 0),
            patch(
                "omnis_cli.main.open_verified", side_effect=lambda **_kw: events.append("open") or 3
            ),
            patch("sys.stdin", Tty()),
            contextlib.redirect_stdout(Tty()),
        ):
            self.assertEqual(main([]), 3)
        self.assertEqual(events, ["pair", "open"])

    def test_implicit_reuse_does_not_invalidate_existing_pairing(self):
        class Tty(io.StringIO):
            def isatty(self):
                return True

        ready = {"origin": "http://127.0.0.1:8765", "reused": True}
        with (
            patch("omnis_cli.main.start_result", return_value=(0, ready)),
            patch("omnis_cli.main.pair") as issuer,
            patch("omnis_cli.main.open_verified", return_value=0),
            patch("sys.stdin", Tty()),
            contextlib.redirect_stdout(Tty()),
        ):
            self.assertEqual(main([]), 0)
        issuer.assert_not_called()

    def test_implicit_fresh_non_tty_never_issues_code(self):
        ready = {"origin": "http://127.0.0.1:8765", "reused": False}
        with (
            patch("omnis_cli.main.start_result", return_value=(0, ready)),
            patch("omnis_cli.main.pair") as issuer,
            patch("omnis_cli.main.open_verified", return_value=3),
            patch("sys.stdin", io.StringIO()),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            self.assertEqual(main([]), 3)
        issuer.assert_not_called()

    def test_implicit_unreadable_tty_probe_never_issues_code(self):
        class BrokenInput(io.StringIO):
            def isatty(self):
                raise OSError("synthetic TTY error")

        ready = {"origin": "http://127.0.0.1:8765", "reused": False}
        with (
            patch("omnis_cli.main.start_result", return_value=(0, ready)),
            patch("omnis_cli.main.pair") as issuer,
            patch("omnis_cli.main.open_verified", return_value=3) as opener,
            patch("sys.stdin", BrokenInput()),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            self.assertEqual(main([]), 3)
        issuer.assert_not_called()
        opener.assert_called_once_with(expected=ready)

    def test_implicit_pair_failure_does_not_invoke_opener(self):
        class Tty(io.StringIO):
            def isatty(self):
                return True

        ready = {"origin": "http://127.0.0.1:8765", "reused": False}
        with (
            patch("omnis_cli.main.start_result", return_value=(0, ready)),
            patch("omnis_cli.main.pair", return_value=4),
            patch("omnis_cli.main.open_verified") as opener,
            patch("sys.stdin", Tty()),
            contextlib.redirect_stdout(Tty()),
        ):
            self.assertEqual(main([]), 4)
        opener.assert_not_called()

    def test_implicit_tty_context_close_after_code_never_invokes_opener(self):
        class Tty(io.StringIO):
            def isatty(self):
                return True

        @contextlib.contextmanager
        def verified():
            yield (
                {
                    "instance_id": "00000000-0000-0000-0000-000000000001",
                    "generation": 1,
                    "supervisor_epoch": 1,
                },
                Path("/private"),
            )
            raise OSError("synthetic close after display")

        ready = {"origin": "http://127.0.0.1:8765", "reused": False}
        reply = {
            "instance_id": "00000000-0000-0000-0000-000000000001",
            "generation": 1,
            "supervisor_epoch": 1,
            "admission_open": True,
            "shutdown_command_id": None,
        }
        output = Tty()
        with (
            patch("omnis_cli.main.start_result", return_value=(0, ready)),
            patch("omnis_cli.pairing.verified_instance", side_effect=verified),
            patch("omnis_cli.pairing.request", return_value=reply),
            patch("omnis_cli.main.open_verified") as opener,
            patch("sys.stdin", Tty()),
            contextlib.redirect_stdout(output),
            contextlib.redirect_stderr(io.StringIO()) as error,
        ):
            self.assertEqual(main([]), 4)
        self.assertIn("Cod pairing Omnis", output.getvalue())
        self.assertIn("PAIRING_DISPLAY_UNCERTAIN", error.getvalue())
        opener.assert_not_called()

    def test_open_without_installed_instance_refuses_without_invoking_opener(self):
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as state:
            with (
                patch.dict(os.environ, {"XDG_STATE_HOME": state, "XDG_DATA_HOME": state}),
                contextlib.redirect_stdout(io.StringIO()),
                contextlib.redirect_stderr(io.StringIO()) as error,
            ):
                self.assertEqual(main(["open"]), 3)
        self.assertIn("INSTANCE_UNAVAILABLE", error.getvalue())

    def test_missing_journal_does_not_create_lifecycle_locks(self):
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
            base = Path(name)
            data, state = base / "data/omnis", base / "state/omnis"
            data.mkdir(parents=True, mode=0o700)
            state.mkdir(parents=True, mode=0o700)
            with (
                patch.dict(
                    os.environ,
                    {
                        "XDG_DATA_HOME": str(base / "data"),
                        "XDG_STATE_HOME": str(base / "state"),
                    },
                ),
                patch("omnis_cli.verified.ControlRuntime"),
                contextlib.redirect_stdout(io.StringIO()),
                contextlib.redirect_stderr(io.StringIO()) as error,
            ):
                self.assertEqual(main(["open"]), 3)
            self.assertIn("INSTANCE_UNAVAILABLE", error.getvalue())
            self.assertFalse((data / "lifecycle.lock").exists())
            self.assertFalse((state / "lifecycle.lock").exists())

    def test_opener_acceptance_is_not_claimed_as_visible_window(self):
        from omnis_cli import browser

        with (
            patch.object(browser.shutil, "which", return_value="/usr/bin/xdg-open"),
            patch.object(browser.subprocess, "run") as process,
        ):
            process.return_value.returncode = 0
            result = browser.launch("http://127.0.0.1:8765")
        self.assertEqual(result, "BROWSER_LAUNCH_ACCEPTED")
        self.assertEqual(process.call_args.args[0], ["/usr/bin/xdg-open", "http://127.0.0.1:8765/"])
        self.assertNotIn("BROWSER", process.call_args.kwargs["env"])
        self.assertFalse(process.call_args.kwargs.get("shell", False))

    def test_absent_and_failed_opener_are_distinct_and_never_claim_window(self):
        from omnis_cli import browser

        with patch.object(browser.shutil, "which", return_value=None):
            self.assertEqual(browser.launch("http://127.0.0.1:8765"), "BROWSER_UNAVAILABLE")
        with (
            patch.object(browser.shutil, "which", return_value="/usr/bin/xdg-open"),
            patch.object(browser.subprocess, "run") as process,
        ):
            process.return_value.returncode = 1
            self.assertEqual(browser.launch("http://127.0.0.1:8765"), "BROWSER_LAUNCH_FAILED")

    def test_timed_out_opener_reports_uncertain_window_not_definite_failure(self):
        from omnis_cli import browser

        @contextlib.contextmanager
        def verified():
            yield ({"origin": "http://127.0.0.1:8765"}, Path("/private"))

        with (
            patch.object(browser, "verified_instance", side_effect=verified),
            patch.object(browser.shutil, "which", return_value="/usr/bin/xdg-open"),
            patch.object(
                browser.subprocess, "run", side_effect=subprocess.TimeoutExpired("xdg-open", 8)
            ),
            contextlib.redirect_stdout(io.StringIO()) as output,
            contextlib.redirect_stderr(io.StringIO()) as error,
        ):
            self.assertEqual(main(["open"]), 3)
        self.assertIn("BROWSER_LAUNCH_UNCONFIRMED", output.getvalue())
        self.assertIn("poate", error.getvalue())
        self.assertNotIn("Deschiderea a eșuat", error.getvalue())

    def test_open_uses_only_verified_origin_and_never_starts_services(self):
        from omnis_cli import browser

        @contextlib.contextmanager
        def verified():
            yield ({"origin": "http://127.0.0.1:8989", "instance_id": "a"}, Path("/private"))

        with (
            patch.object(browser, "verified_instance", side_effect=verified),
            patch.object(browser, "launch", return_value="BROWSER_LAUNCH_ACCEPTED") as opener,
            patch("omnis_cli.start.start_instance") as startup,
            contextlib.redirect_stdout(io.StringIO()) as output,
        ):
            self.assertEqual(main(["open"]), 0)
        opener.assert_called_once_with("http://127.0.0.1:8989")
        startup.assert_not_called()
        self.assertIn("BROWSER_LAUNCH_ACCEPTED", output.getvalue())

    def test_implicit_start_reuses_startup_and_rechecks_same_origin(self):
        from omnis_cli import browser

        @contextlib.contextmanager
        def verified():
            yield ({"origin": "http://127.0.0.1:8989", "instance_id": "a"}, Path("/private"))

        with (
            patch(
                "omnis_cli.main.start_result",
                return_value=(
                    0,
                    {
                        "origin": "http://127.0.0.1:8989",
                        "instance_id": "a",
                        "dashboard_ready": True,
                        "assessment_ready": False,
                    },
                ),
            ) as startup,
            patch.object(browser, "verified_instance", side_effect=verified),
            patch.object(browser, "launch", return_value="BROWSER_LAUNCH_ACCEPTED") as opener,
            contextlib.redirect_stdout(io.StringIO()) as output,
        ):
            self.assertEqual(main([]), 0)
        startup.assert_called_once_with(None)
        opener.assert_called_once_with("http://127.0.0.1:8989")
        self.assertIn("BROWSER_LAUNCH_ACCEPTED", output.getvalue())

    def test_implicit_failed_start_does_not_call_browser(self):
        with (
            patch("omnis_cli.main.start_result", return_value=(3, {"reason": "STARTUP_FAILED"})),
            patch("omnis_cli.browser.launch") as opener,
            contextlib.redirect_stderr(io.StringIO()) as error,
        ):
            self.assertEqual(main([]), 3)
        self.assertIn("STARTUP_FAILED", error.getvalue())
        opener.assert_not_called()
