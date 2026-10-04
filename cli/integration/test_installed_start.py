"""Acceptance observer must not manufacture cleanup after uncertainty."""

import os
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path
from types import SimpleNamespace

import installed_pair_open as probe
from installed_pair_open import tty_run
from installed_start import teardown


class InstalledStartObserverTest(unittest.TestCase):
    def test_pair_open_default_tty_fixture_is_not_replaced_by_configured_origin(self):
        """The canonical implicit TTY/default path remains a separate installed fixture."""
        from unittest.mock import patch

        import installed_start as harness

        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
            state = Path(name)
            binds = []

            class Selection:
                def __enter__(self):
                    return self

                def __exit__(self, *_args):
                    return False

                def bind(self, address):
                    binds.append(address)

                def getsockname(self):
                    return ("127.0.0.1", 8765 if binds[-1][1] == 8765 else 9101)

            def inspect_fixture(_data, _deadline):
                self.assertEqual(binds, [("127.0.0.1", 8765)])
                self.assertFalse((state / "config").exists(), "Default TTY path was replaced")
                raise RuntimeError("default fixture inspected before OCI")

            with (
                patch.object(harness.tempfile, "mkdtemp", return_value=name),
                patch.object(harness.socket, "socket", return_value=Selection()),
                patch.object(harness, "ControlRuntime", side_effect=inspect_fixture),
                self.assertRaisesRegex(RuntimeError, "default fixture inspected before OCI"),
            ):
                harness.run_installed_start(
                    state / "data",
                    {"project": "synthetic-project", "image_id": "synthetic-image"},
                    state,
                    "/synthetic/omnis",
                    pair_open=True,
                )

    def test_pair_open_fixture_selects_private_configured_nondefault_port(self):
        """Fail before OCI; the opt-in installed gate exercises TTY/HTTP on this fixture."""
        from unittest.mock import patch

        import installed_start as harness

        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
            state = Path(name)
            config_home = state / "config"
            config = config_home / "omnis/config.toml"

            def inspect_fixture(_data, _deadline):
                self.assertTrue(config.is_file(), "Pair/open lacks a private config file")
                selected = tomllib.loads(config.read_text())
                self.assertEqual(set(selected), {"port"})
                self.assertIs(type(selected["port"]), int)
                self.assertTrue(1024 <= selected["port"] <= 65535)
                self.assertNotEqual(selected["port"], 8765, "Default origin masks config wiring")
                self.assertEqual(config_home.stat().st_mode & 0o777, 0o700)
                self.assertEqual(config.parent.stat().st_mode & 0o777, 0o700)
                self.assertEqual(config.stat().st_mode & 0o777, 0o600)
                raise RuntimeError("fixture inspected before OCI")

            with (
                patch.object(harness.tempfile, "mkdtemp", return_value=name),
                patch.object(harness, "ControlRuntime", side_effect=inspect_fixture),
                self.assertRaisesRegex(RuntimeError, "fixture inspected before OCI"),
            ):
                harness.run_installed_start(
                    state / "data",
                    {"project": "synthetic-project", "image_id": "synthetic-image"},
                    state,
                    "/synthetic/omnis",
                    pair_open=True,
                    configured_pair_open=True,
                )

    def test_unknown_pair_child_exit_keeps_family_uncertain(self):
        import subprocess
        from unittest.mock import patch

        for code in (-9, 99):
            with self.subTest(code=code):
                with patch.object(probe, "tty_run", return_value=(code, b"", b"")):
                    with self.assertRaises(probe.ObserverUncertain):
                        probe.tty_pair("/synthetic/omnis", Path("/synthetic"), {}, expected=3)
                with patch.object(
                    probe.subprocess,
                    "run",
                    return_value=subprocess.CompletedProcess(
                        ["/synthetic/omnis", "pair"], code, "", ""
                    ),
                ):
                    with self.assertRaises(probe.ObserverUncertain):
                        probe.command(
                            "/synthetic/omnis", ["pair"], Path("/synthetic"), {}, expected=3
                        )
        with patch.object(probe, "tty_run", return_value=(4, b"", b"")):
            with self.assertRaises(AssertionError):
                probe.tty_pair("/synthetic/omnis", Path("/synthetic"), {}, expected=3)
        with patch.object(
            probe.subprocess,
            "run",
            return_value=subprocess.CompletedProcess(["/synthetic/omnis", "pair"], 4, "", ""),
        ):
            with self.assertRaises(AssertionError):
                probe.command("/synthetic/omnis", ["pair"], Path("/synthetic"), {}, expected=3)

    def test_explicit_open_observer_keeps_signalled_family_uncertain(self):
        import subprocess
        from unittest.mock import patch

        observer = probe.observed_open
        cli = "/synthetic/omnis"
        origin = "http://127.0.0.1:8765"
        env = {"PATH": "/usr/bin:/bin"}
        for result, error in (
            (subprocess.CompletedProcess([cli, "open"], -9, "", ""), probe.ObserverUncertain),
            (
                subprocess.CompletedProcess(
                    [cli, "open"],
                    0,
                    f"Omnis READY: {origin}/ — BROWSER_LAUNCH_ACCEPTED; "
                    "fereastra/sesiunea nu sunt verificate.\n",
                    "Deschiderea a eșuat; serviciile rămân pornite.\n",
                ),
                AssertionError,
            ),
        ):
            with (
                self.subTest(returncode=result.returncode),
                patch.object(probe.subprocess, "run", return_value=result),
            ):
                with self.assertRaises(error):
                    observer(cli, Path("/synthetic"), env, origin)
        accepted = subprocess.CompletedProcess(
            [cli, "open"],
            3,
            f"Omnis READY: {origin}/ — BROWSER_LAUNCH_FAILED; "
            "fereastra/sesiunea nu sunt verificate.\n",
            "Deschiderea a eșuat; serviciile rămân pornite.\n",
        )
        with patch.object(probe.subprocess, "run", return_value=accepted):
            outcome, text = observer(cli, Path("/synthetic"), env, origin)
        self.assertEqual(outcome, "BROWSER_LAUNCH_FAILED")
        self.assertEqual(text, accepted.stdout + accepted.stderr)

    def test_joined_tty_report_rejection_marks_owned_cli_settled(self):
        from unittest.mock import patch

        events = []
        mismatched = (
            "Cod pairing Omnis (expiră în 5 minute): " + "A" * 32 + "\r\n"
            "Omnis READY: http://127.0.0.1:8765/ — BROWSER_LAUNCH_UNCONFIRMED; "
            "fereastra/sesiunea nu sunt verificate.\r\n"
        ).encode()
        with patch.object(probe, "tty_run", return_value=(0, mismatched, b"")):
            try:
                probe.tty_default(
                    "/synthetic/omnis",
                    Path("/synthetic"),
                    {},
                    8765,
                    on_joined=lambda: events.append("joined"),
                )
            except TypeError as error:
                self.fail(f"No joined-child boundary for TTY parser: {error}")
            except AssertionError:
                pass
            else:
                self.fail("Mismatched opener outcome was accepted")
        self.assertEqual(events, ["joined"])
        with patch.object(probe, "tty_run", side_effect=probe.ObserverUncertain("unjoined")):
            with self.assertRaises(probe.ObserverUncertain):
                probe.tty_default(
                    "/synthetic/omnis",
                    Path("/synthetic"),
                    {},
                    8765,
                    on_joined=lambda: events.append("not-joined"),
                )
        self.assertEqual(events, ["joined"])
        with patch.object(probe, "tty_run", return_value=(-9, mismatched, b"")):
            with self.assertRaises(AssertionError):
                probe.tty_default(
                    "/synthetic/omnis",
                    Path("/synthetic"),
                    {},
                    8765,
                    on_joined=lambda: events.append("signalled-child"),
                )
        self.assertEqual(events, ["joined"], "Signalled child family is not reconciled")

    def test_reused_implicit_console_consumer_checks_exact_opener_result(self):
        import subprocess
        from unittest.mock import patch

        import installed_start as harness

        observer = harness.run_reused_default
        origin = "http://127.0.0.1:8765"
        joins = []
        for result in (
            subprocess.CompletedProcess(
                ["/synthetic/omnis"],
                0,
                f"Omnis READY: {origin}/ — BROWSER_LAUNCH_UNCONFIRMED; "
                "fereastra/sesiunea nu sunt verificate.\n",
                "",
            ),
            subprocess.CompletedProcess(
                ["/synthetic/omnis"],
                0,
                f"Omnis READY: {origin}/ — BROWSER_LAUNCH_ACCEPTED; "
                "fereastra/sesiunea nu sunt verificate.\nEXTRA",
                "",
            ),
            subprocess.CompletedProcess(
                ["/synthetic/omnis"],
                0,
                f"Omnis READY: {origin}/ — BROWSER_LAUNCH_ACCEPTED; "
                "fereastra/sesiunea nu sunt verificate.\n",
                "Deschiderea a eșuat; serviciile rămân pornite.\n",
            ),
        ):
            with (
                self.subTest(stdout=result.stdout),
                patch.object(harness.subprocess, "run", return_value=result) as launched,
            ):
                with self.assertRaises(AssertionError):
                    observer(
                        "/synthetic/omnis",
                        Path("/synthetic"),
                        {},
                        8765,
                        on_joined=lambda: joins.append("joined"),
                    )
                launched.assert_called_once()
        self.assertEqual(joins, ["joined"] * 3)
        accepted = subprocess.CompletedProcess(
            ["/synthetic/omnis"],
            3,
            f"Omnis READY: {origin}/ — BROWSER_LAUNCH_UNCONFIRMED; "
            "fereastra/sesiunea nu sunt verificate.\n",
            "Openerul a depășit termenul; fereastra poate exista sau lipsi. "
            "Serviciile rămân pornite.\n",
        )
        with patch.object(harness.subprocess, "run", return_value=accepted):
            self.assertIs(observer("/synthetic/omnis", Path("/synthetic"), {}, 8765), accepted)
        with patch.object(
            harness.subprocess,
            "run",
            side_effect=subprocess.TimeoutExpired(["/synthetic/omnis"], 50),
        ):
            with self.assertRaises(subprocess.TimeoutExpired):
                observer(
                    "/synthetic/omnis",
                    Path("/synthetic"),
                    {},
                    8765,
                    on_joined=lambda: joins.append("not-joined"),
                )
        self.assertEqual(joins, ["joined"] * 3)
        with patch.object(
            harness.subprocess,
            "run",
            return_value=subprocess.CompletedProcess(["/synthetic/omnis"], -9, "", ""),
        ):
            with self.assertRaises(AssertionError):
                observer(
                    "/synthetic/omnis",
                    Path("/synthetic"),
                    {},
                    8765,
                    on_joined=lambda: joins.append("signalled-child"),
                )
        self.assertEqual(joins, ["joined"] * 3)

    def test_tty_default_rejects_exit_outcome_mismatch_and_extra_bytes(self):
        from unittest.mock import patch

        origin = "http://127.0.0.1:8765"
        prefix = "Cod pairing Omnis (expiră în 5 minute): " + "A" * 32 + "\r\n"
        for suffix in (
            f"Omnis READY: {origin}/ — BROWSER_LAUNCH_UNCONFIRMED; fereastra/sesiunea nu sunt verificate.\r\n",
            f"Omnis READY: {origin}/ — BROWSER_LAUNCH_ACCEPTED; fereastra/sesiunea nu sunt verificate.\r\nEXTRA",
        ):
            with (
                self.subTest(suffix=suffix),
                patch.object(probe, "tty_run", return_value=(0, (prefix + suffix).encode(), b"")),
            ):
                with self.assertRaises(AssertionError):
                    probe.tty_default("/synthetic/omnis", Path("/synthetic"), {}, 8765)
        contradictory = (
            prefix + f"Omnis READY: {origin}/ — BROWSER_LAUNCH_ACCEPTED; "
            "fereastra/sesiunea nu sunt verificate.\r\n"
        )
        with patch.object(
            probe,
            "tty_run",
            return_value=(
                0,
                contradictory.encode(),
                "Deschiderea a eșuat; serviciile rămân pornite.\n".encode(),
            ),
        ):
            with self.assertRaises(AssertionError):
                probe.tty_default("/synthetic/omnis", Path("/synthetic"), {}, 8765)
        accepted = (
            prefix + f"Omnis READY: {origin}/ — BROWSER_LAUNCH_UNCONFIRMED; "
            "fereastra/sesiunea nu sunt verificate.\r\n"
        )
        diagnostic = (
            "Openerul a depășit termenul; fereastra poate exista sau lipsi. "
            "Serviciile rămân pornite.\n"
        )
        with patch.object(
            probe, "tty_run", return_value=(3, accepted.encode(), diagnostic.encode())
        ):
            code, public, exit_code = probe.tty_default(
                "/synthetic/omnis", Path("/synthetic"), {}, 8765
            )
        self.assertEqual(exit_code, 3)
        self.assertEqual(len(code), 32)
        self.assertIn("BROWSER_LAUNCH_UNCONFIRMED", public)

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

            implicit_replies = [
                subprocess.CompletedProcess(
                    [cli],
                    3,
                    "Omnis READY: http://127.0.0.1:8765/ — BROWSER_LAUNCH_FAILED; "
                    "fereastra/sesiunea nu sunt verificate.\n",
                    "Deschiderea a eșuat; serviciile rămân pornite.\n",
                ),
                subprocess.CompletedProcess(
                    [cli],
                    0,
                    "Omnis READY: http://127.0.0.1:8765/ — BROWSER_LAUNCH_UNCONFIRMED; "
                    "fereastra/sesiunea nu sunt verificate.\n",
                    "",
                ),
                subprocess.CompletedProcess(
                    [cli],
                    0,
                    "Omnis READY: http://127.0.0.1:8765/ — BROWSER_LAUNCH_ACCEPTED; "
                    "fereastra/sesiunea nu sunt verificate.\n",
                    "Deschiderea a eșuat; serviciile rămân pornite.\n",
                ),
            ]

            def invoke(argv, **_kwargs):
                if argv == [cli]:
                    clock["now"] = 40.0  # A valid CLI may take > initial observer budget.
                    return implicit_replies.pop(0)
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
                patch.object(harness, "opener_outcome", wraps=probe.opener_outcome) as parsed,
                patch.object(harness, "save_probe") as receipt_writer,
                patch.object(harness, "teardown") as teardown,
                patch.object(harness, "assert_resources_absent") as absent,
                contextlib.redirect_stdout(io.StringIO()) as output,
            ):
                harness.run_installed_non_tty_default(data, receipt, cli)
                teardown.assert_called_once()
                absent.assert_called_once()
                parsed.assert_called_once_with(
                    3,
                    "Omnis READY: http://127.0.0.1:8765/ — BROWSER_LAUNCH_FAILED; "
                    "fereastra/sesiunea nu sunt verificate.\n",
                    "http://127.0.0.1:8765",
                    "Deschiderea a eșuat; serviciile rămân pornite.\n",
                )
                # Same subprocess/READY/attestation channel with a contradictory
                # opener result: rejection must still clean its joined family.
                (state / "cwd").rmdir()
                with self.assertRaises(AssertionError):
                    harness.run_installed_non_tty_default(data, receipt, cli)
                self.assertEqual(teardown.call_count, 2)
                self.assertEqual(absent.call_count, 2)
                self.assertEqual(parsed.call_count, 2)
                self.assertEqual(receipt_writer.call_args.kwargs["probe"], "FAIL")
                self.assertEqual(receipt_writer.call_args.kwargs["cleanup"], "VERIFIED")
                (state / "cwd").rmdir()
                with self.assertRaises(AssertionError):
                    harness.run_installed_non_tty_default(data, receipt, cli)
                self.assertEqual(teardown.call_count, 3)
                self.assertEqual(absent.call_count, 3)
                self.assertEqual(parsed.call_count, 3)
                self.assertEqual(receipt_writer.call_args.kwargs["probe"], "FAIL")
                self.assertEqual(receipt_writer.call_args.kwargs["cleanup"], "VERIFIED")
            self.assertIn("INSTALLED_DEFAULT_NON_TTY_VERIFIED", output.getvalue())

    def test_opener_observer_accepts_only_exact_outcome_for_exit_and_origin(self):
        origin = "http://127.0.0.1:8765"
        cases = (
            (0, "BROWSER_LAUNCH_ACCEPTED", ""),
            (
                2,
                "BROWSER_UNAVAILABLE",
                "Deschideți manual originul afișat; serviciile rămân pornite.\n",
            ),
            (3, "BROWSER_LAUNCH_FAILED", "Deschiderea a eșuat; serviciile rămân pornite.\n"),
            (
                3,
                "BROWSER_LAUNCH_UNCONFIRMED",
                "Openerul a depășit termenul; fereastra poate exista sau lipsi. Serviciile rămân pornite.\n",
            ),
        )
        for exit_code, outcome, stderr in cases:
            with self.subTest(outcome=outcome):
                line = (
                    f"Omnis READY: {origin}/ — {outcome}; fereastra/sesiunea nu sunt verificate.\n"
                )
                self.assertEqual(probe.opener_outcome(exit_code, line, origin, stderr), outcome)
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
                    probe.opener_outcome(exit_code, line, origin, "")

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
            initial = {
                "attempt": "11111111-1111-4111-8111-111111111111",
                "phase": "VERIFYING",
                "containers": {},
            }
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
                    patch.object(probe.subprocess, "run", side_effect=retry) as retry_call,
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
                retry_call.assert_called_once()
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
