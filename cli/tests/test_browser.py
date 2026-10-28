"""Installed open/default are verified operator actions, not assessment browsers."""

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from omnis_cli.main import main


class BrowserTest(unittest.TestCase):
    def test_source_launcher_keeps_app_private_and_captures_only_desktop_context(self):
        """SOURCE shell expansion on an owned sink, never the operator installation."""
        from omnis_cli import browser

        source = (Path(__file__).resolve().parents[1] / "operator-launcher.sh").read_text()
        operator_root = "/home/kali/.local/share/omnis-settings-c-9e51d10"
        canaries = {
            name: "secret-canary"
            for name in (
                "BROWSER",
                "OPENROUTER_API_KEY",
                "ORCAROUTER_API_KEY",
                "SSH_AUTH_SOCK",
                "PYTHONPATH",
                "LD_PRELOAD",
                "ARBITRARY",
                "OMNIS_DESKTOP_EXTRA",
                "OMNIS_DESKTOP_HOME",
            )
        }
        graphics = {
            "DISPLAY": ":73.1",
            "WAYLAND_DISPLAY": "wayland-7",
            "XDG_CURRENT_DESKTOP": "XFCE",
            "DBUS_SESSION_BUS_ADDRESS": "unix:path=/synthetic/session bus",
            "XAUTHORITY": "/synthetic/auth file",
            "LANG": "C.UTF-8",
        }
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
            root = Path(name) / "operator"
            sink = root / "cli/bin/omnis"
            sink.parent.mkdir(parents=True)
            sink.write_text(
                f"#!{sys.executable} -I\n"
                "import json, os, sys\n"
                "print(json.dumps({'env': dict(os.environ), 'argv': sys.argv[1:]}))\n"
            )
            sink.chmod(0o700)
            launcher = root / "omnis"
            synthetic = source.replace(operator_root, str(root))
            self.assertNotIn(operator_root, synthetic)
            self.assertIn(str(sink), synthetic)
            launcher.write_text(synthetic)
            app = {
                key: str(root / leaf)
                for key, leaf in (
                    ("HOME", "h"),
                    ("XDG_CONFIG_HOME", "c"),
                    ("XDG_DATA_HOME", "d"),
                    ("XDG_STATE_HOME", "s"),
                    ("XDG_RUNTIME_DIR", "r"),
                )
            }
            for xdg_values in ("present", "empty", "absent"):
                desktop = {"HOME": "/synthetic/desktop home/'\"$(false)"}
                for key in app.keys() - {"HOME"}:
                    if xdg_values != "absent":
                        desktop[key] = "/synthetic/" + key if xdg_values == "present" else ""
                invocation = {**canaries, **graphics, **desktop, "PATH": "/untrusted"}
                # Do not load a canary as a shared library into the test shell itself.
                invocation.pop("LD_PRELOAD")
                with self.subTest(xdg_values=xdg_values):
                    captured = subprocess.run(
                        ["/bin/sh", str(launcher), "start", "--json", "literal argument"],
                        env=invocation,
                        capture_output=True,
                        text=True,
                        timeout=5,
                        check=True,
                    )
                    self.assertEqual(captured.stderr, "")
                    result = json.loads(captured.stdout)
                    app_env = {
                        **app,
                        **graphics,
                        "PATH": str(sink.parent) + ":/usr/bin:/bin",
                        "TMPDIR": "/home/kali/.hermes/cache/scratch",
                        **{"OMNIS_DESKTOP_" + key: desktop.get(key, "") for key in app},
                    }
                    self.assertEqual(result["env"], app_env)
                    self.assertEqual(result["argv"], ["start", "--json", "literal argument"])
                    self.assertNotIn("secret-canary", captured.stdout)
                    with (
                        patch.dict(os.environ, result["env"], clear=True),
                        patch.object(browser.shutil, "which", return_value="/usr/bin/xdg-open"),
                        patch.object(browser.subprocess, "run") as opener,
                    ):
                        opener.return_value.returncode = 0
                        self.assertEqual(
                            browser.launch("http://127.0.0.1:8989"), "BROWSER_LAUNCH_ACCEPTED"
                        )
                        self.assertEqual(dict(os.environ), app_env)
                    self.assertEqual(
                        opener.call_args.kwargs["env"],
                        {
                            "PATH": "/usr/bin:/bin",
                            **graphics,
                            **{key: value for key, value in desktop.items() if value},
                        },
                    )

    def test_unwrapped_opener_uses_finite_normal_desktop_environment(self):
        from omnis_cli import browser

        desktop = {
            "HOME": "/synthetic/home",
            "XDG_CONFIG_HOME": "/synthetic/config",
            "XDG_DATA_HOME": "/synthetic/data",
            "XDG_STATE_HOME": "/synthetic/state",
            "XDG_RUNTIME_DIR": "/synthetic/runtime",
            "DISPLAY": ":72",
            "WAYLAND_DISPLAY": "wayland-4",
            "XDG_CURRENT_DESKTOP": "XFCE",
            "DBUS_SESSION_BUS_ADDRESS": "unix:path=/synthetic/bus",
            "XAUTHORITY": "/synthetic/auth",
            "LANG": "C.UTF-8",
        }
        for context in (desktop, {"HOME": desktop["HOME"]}):
            with (
                self.subTest(context=context),
                patch.dict(
                    os.environ,
                    {
                        **context,
                        "BROWSER": "secret-canary",
                        "PATH": "/untrusted",
                        "PYTHONPATH": "secret-canary",
                        "OPENROUTER_API_KEY": "secret-canary",
                        "SSH_AUTH_SOCK": "secret-canary",
                        "LD_PRELOAD": "secret-canary",
                    },
                    clear=True,
                ),
                patch.object(browser.shutil, "which", return_value="/usr/bin/xdg-open") as which,
                patch.object(browser.subprocess, "run") as process,
            ):
                process.return_value.returncode = 0
                self.assertEqual(browser.launch("http://127.0.0.1:8989"), "BROWSER_LAUNCH_ACCEPTED")
                which.assert_called_once_with("xdg-open", path="/usr/bin:/bin")
                process.assert_called_once_with(
                    ["/usr/bin/xdg-open", "http://127.0.0.1:8989/"],
                    env={"PATH": "/usr/bin:/bin", **context},
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=8,
                    check=False,
                )

    def test_plain_start_opens_and_forwards_explicit_startup_options(self):
        ready = {"origin": "http://127.0.0.1:8989", "reused": True}
        for options, port, startup, cleanup in (
            ([], None, None, None),
            (
                ["--port", "8989", "--startup-timeout", "40", "--cleanup-timeout", "31"],
                8989,
                40,
                31,
            ),
        ):
            with (
                self.subTest(options=options),
                patch("omnis_cli.main.start_result", return_value=(0, ready)) as start,
                patch("omnis_cli.main.open_verified", return_value=0) as opener,
                patch("omnis_cli.main.pair") as issuer,
                contextlib.redirect_stderr(io.StringIO()),
            ):
                try:
                    code = main(["start", *options])
                except SystemExit as exc:
                    code = exc.code
                self.assertEqual(code, 0)
            start.assert_called_once_with(port, startup_timeout=startup, cleanup_timeout=cleanup)
            opener.assert_called_once_with(expected=ready)
            issuer.assert_not_called()

    def test_explicit_start_preserves_tty_pairing_and_uncertain_disclosure_policy(self):
        for reused, tty, issuance, expected, events in (
            (False, True, 0, 0, ["pair", "open"]),
            (False, True, 4, 4, ["pair"]),
            (True, True, 0, 0, ["open"]),
            (False, False, 0, 0, ["open"]),
        ):
            seen = []
            with (
                self.subTest(reused=reused, tty=tty, issuance=issuance),
                patch("omnis_cli.main.start_result", return_value=(0, {"reused": reused})),
                patch("omnis_cli.main.interactive_tty", return_value=tty),
                patch(
                    "omnis_cli.main.pair",
                    side_effect=lambda seen=seen, issuance=issuance: (
                        seen.append("pair") or issuance
                    ),
                ),
                patch(
                    "omnis_cli.main.open_verified",
                    side_effect=lambda seen=seen, **kw: seen.append("open") or 0,
                ),
            ):
                self.assertEqual(main(["start"]), expected)
                self.assertEqual(seen, events)

    def test_headless_json_retains_exact_formatter_and_never_invokes_gui_or_pairing(self):
        for code, result in (
            (0, {"state": "READY", "reused": False, "browser_opened": False}),
            (3, {"state": "FAILED", "reason": "STARTUP_FAILED", "browser_opened": False}),
        ):
            with (
                self.subTest(code=code),
                patch("omnis_cli.start.start_result", return_value=(code, result)) as startup,
                patch("omnis_cli.main.pair") as issuer,
                patch("omnis_cli.main.open_verified") as opener,
                contextlib.redirect_stdout(io.StringIO()) as output,
                contextlib.redirect_stderr(io.StringIO()) as error,
            ):
                self.assertEqual(
                    main(
                        [
                            "start",
                            "--no-open",
                            "--json",
                            "--port",
                            "8989",
                            "--startup-timeout",
                            "40",
                            "--cleanup-timeout",
                            "31",
                        ]
                    ),
                    code,
                )
                self.assertEqual(output.getvalue(), json.dumps(result, sort_keys=True) + "\n")
                self.assertEqual(error.getvalue(), "")
                startup.assert_called_once_with(8989, startup_timeout=40, cleanup_timeout=31)
                issuer.assert_not_called()
                opener.assert_not_called()

    def test_start_json_reports_fresh_reuse_and_opener_without_pairing(self):
        from omnis_cli import browser

        class Tty(io.StringIO):
            def isatty(self):
                return True

        for reused in (False, True):
            ready = {
                "state": "READY",
                "origin": "http://127.0.0.1:8989",
                "instance_id": "a",
                "generation": 1,
                "supervisor_epoch": 1,
                "dashboard_ready": True,
                "api_ready": True,
                "control_ready": True,
                "admission_open": True,
                "assessment_ready": False,
                "browser_opened": False,
                "reused": reused,
                "reason": None,
            }

            @contextlib.contextmanager
            def verified(ready=ready):
                yield ({**ready, "reused": True}, Path("/private"))

            for outcome, exit_code in (
                ("BROWSER_LAUNCH_ACCEPTED", 0),
                ("BROWSER_UNAVAILABLE", 2),
                ("BROWSER_LAUNCH_FAILED", 3),
                ("BROWSER_LAUNCH_UNCONFIRMED", 3),
            ):
                with (
                    self.subTest(reused=reused, outcome=outcome),
                    patch("omnis_cli.main.start_result", return_value=(0, ready)),
                    patch("omnis_cli.main.pair") as issuer,
                    patch.object(browser, "verified_instance", side_effect=verified),
                    patch.object(
                        browser.shutil,
                        "which",
                        return_value=(
                            None if outcome == "BROWSER_UNAVAILABLE" else "/usr/bin/xdg-open"
                        ),
                    ),
                    patch.object(
                        browser.subprocess,
                        "run",
                        side_effect=(
                            subprocess.TimeoutExpired("secret-canary", 8)
                            if outcome == "BROWSER_LAUNCH_UNCONFIRMED"
                            else OSError("secret-canary")
                            if outcome == "BROWSER_LAUNCH_FAILED"
                            else None
                        ),
                    ) as opener,
                    patch.dict(os.environ, {"OPENROUTER_API_KEY": "secret-canary"}),
                    patch("sys.stdin", Tty()),
                    contextlib.redirect_stdout(Tty()) as output,
                    contextlib.redirect_stderr(io.StringIO()) as error,
                ):
                    opener.return_value.returncode = 0
                    self.assertEqual(main(["start", "--json"]), exit_code)
                    self.assertEqual(
                        output.getvalue(),
                        json.dumps({**ready, "browser_outcome": outcome}, sort_keys=True) + "\n",
                    )
                    self.assertEqual(error.getvalue(), "")
                    issuer.assert_not_called()
                    if outcome == "BROWSER_UNAVAILABLE":
                        opener.assert_not_called()
                    else:
                        self.assertEqual(
                            opener.call_args.args[0], ["/usr/bin/xdg-open", ready["origin"] + "/"]
                        )
                        self.assertEqual(opener.call_args.kwargs["timeout"], 8)
                        self.assertNotIn("secret-canary", repr(opener.call_args))

    def test_start_json_failure_is_one_sanitized_result_without_browser(self):
        from omnis_cli.lifecycle import StartError

        for failure, code, state, reason in (
            (OSError("secret-canary"), 3, "FAILED", "STARTUP_FAILED"),
            (StartError("PORT_INVALID", 2), 2, "REFUSED", "PORT_INVALID"),
            (StartError("RECOVERY_REQUIRED", 4), 4, "UNCERTAIN", "RECOVERY_REQUIRED"),
        ):
            with (
                self.subTest(reason=reason),
                patch("omnis_cli.start.start_instance", side_effect=failure),
                patch("omnis_cli.main.pair") as issuer,
                patch("omnis_cli.main.open_verified") as opener,
                contextlib.redirect_stdout(io.StringIO()) as output,
                contextlib.redirect_stderr(io.StringIO()) as error,
            ):
                self.assertEqual(main(["start", "--json"]), code)
                self.assertEqual(
                    json.loads(output.getvalue()),
                    {
                        "state": state,
                        "reason": reason,
                        "dashboard_ready": False,
                        "assessment_ready": False,
                        "browser_opened": False,
                        "browser_outcome": "BROWSER_NOT_INVOKED",
                    },
                )
                self.assertEqual(error.getvalue(), "")
                issuer.assert_not_called()
                opener.assert_not_called()

    def test_start_json_reverification_refuses_before_browser(self):
        from omnis_cli import browser
        from omnis_cli.lifecycle import StartError

        ready = {
            "state": "READY",
            "origin": "http://127.0.0.1:8989",
            "instance_id": "a",
            "generation": 1,
            "supervisor_epoch": 1,
            "reused": False,
            "dashboard_ready": True,
            "api_ready": True,
            "control_ready": True,
            "admission_open": True,
            "shutdown_finalized": False,
            "assessment_ready": False,
            "browser_opened": False,
        }
        for changed in (
            "instance_id",
            "origin",
            "generation",
            "supervisor_epoch",
            "readiness",
            "entry",
        ):

            @contextlib.contextmanager
            def verified(changed=changed):
                if changed == "readiness":
                    raise OSError("secret-canary")
                if changed == "entry":
                    raise StartError("INSTANCE_CHANGED", 4)
                yield ({**ready, changed: "different"}, Path("/private"))

            with (
                self.subTest(changed=changed),
                patch("omnis_cli.main.start_result", return_value=(0, ready)),
                patch("omnis_cli.main.pair") as issuer,
                patch.object(browser, "verified_instance", side_effect=verified),
                patch.object(browser, "launch") as opener,
                contextlib.redirect_stdout(io.StringIO()) as output,
                contextlib.redirect_stderr(io.StringIO()) as error,
            ):
                self.assertEqual(main(["start", "--json"]), 3 if changed == "readiness" else 4)
                self.assertNotEqual(output.getvalue(), "")
                result = json.loads(output.getvalue())
                self.assertEqual(
                    result["state"], "FAILED" if changed == "readiness" else "UNCERTAIN"
                )
                self.assertEqual(
                    result["reason"],
                    "READINESS_UNAVAILABLE" if changed == "readiness" else "INSTANCE_CHANGED",
                )
                self.assertFalse(result["dashboard_ready"])
                self.assertFalse(result["api_ready"])
                self.assertFalse(result["control_ready"])
                for key in (
                    "generation",
                    "supervisor_epoch",
                    "admission_open",
                    "shutdown_finalized",
                ):
                    self.assertNotIn(key, result)
                self.assertFalse(result["reused"])
                self.assertEqual(result["browser_outcome"], "BROWSER_NOT_INVOKED")
                self.assertNotIn("secret-canary", output.getvalue())
                self.assertEqual(error.getvalue(), "")
                opener.assert_not_called()
                issuer.assert_not_called()

        # Even a matching but invalid origin must fail before subprocess dispatch.
        for origin in (
            "https://127.0.0.1:8989",
            "http://localhost:8989",
            "http://127.0.0.1:8989/?code=secret-canary",
        ):
            with patch.object(browser.subprocess, "run") as process:
                with self.assertRaises(StartError):
                    browser.launch(origin)
                process.assert_not_called()

    def test_start_json_post_launch_readback_error_preserves_outcome(self):
        from omnis_cli import browser

        ready = {
            "state": "READY",
            "origin": "http://127.0.0.1:8989",
            "instance_id": "a",
            "generation": 1,
            "supervisor_epoch": 1,
            "dashboard_ready": True,
            "api_ready": True,
            "control_ready": True,
            "admission_open": True,
            "shutdown_finalized": False,
            "assessment_ready": False,
            "browser_opened": False,
            "reused": True,
        }

        @contextlib.contextmanager
        def verified():
            yield ready, Path("/private")
            raise OSError("secret-canary")

        with (
            patch("omnis_cli.main.start_result", return_value=(0, ready)),
            patch("omnis_cli.main.pair") as issuer,
            patch.object(browser, "verified_instance", side_effect=verified),
            patch.object(browser, "launch", return_value="BROWSER_LAUNCH_ACCEPTED") as opener,
            contextlib.redirect_stdout(io.StringIO()) as output,
            contextlib.redirect_stderr(io.StringIO()) as error,
        ):
            self.assertEqual(main(["start", "--json"]), 3)
            self.assertNotEqual(output.getvalue(), "")
            result = json.loads(output.getvalue())
            self.assertEqual(result["browser_outcome"], "BROWSER_LAUNCH_ACCEPTED")
            self.assertFalse(result["browser_opened"])
            self.assertFalse(result["dashboard_ready"])
            self.assertFalse(result["api_ready"])
            self.assertFalse(result["control_ready"])
            for key in ("generation", "supervisor_epoch", "admission_open", "shutdown_finalized"):
                self.assertNotIn(key, result)
            self.assertEqual(result["state"], "FAILED")
            self.assertEqual(result["reason"], "READINESS_UNAVAILABLE")
            self.assertEqual(result["origin"], ready["origin"])
            self.assertEqual(result["instance_id"], ready["instance_id"])
            self.assertTrue(result["reused"])
            self.assertNotIn("secret-canary", output.getvalue())
            self.assertEqual(error.getvalue(), "")
            opener.assert_called_once_with(ready["origin"])
            issuer.assert_not_called()

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
