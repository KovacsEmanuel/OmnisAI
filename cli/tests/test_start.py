"""Installed-start boundaries, without substituting mocks for the live OCI proof."""

import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from omnis_cli.main import main


class StartTest(unittest.TestCase):
    def test_fresh_pgdata_identity_is_durable_before_first_mount(self):
        """The first Compose create must see the original, fsynced bind-root identity."""
        import importlib
        import time
        from types import SimpleNamespace
        from unittest.mock import Mock

        from omnis_cli.lifecycle import StartError, read_record

        start = importlib.import_module("omnis_cli.start")
        (self.root / "data/omnis").mkdir(parents=True, mode=0o700)
        root = self.root / "state/omnis"
        runtime = Mock(
            receipt=SimpleNamespace(
                project="omnis-local-" + "a" * 32,
                image_id="sha256:" + "b" * 64,
                docker_id="test-daemon",
            ),
            digest="c" * 64,
            host="unix:///run/docker.sock",
            deadline=time.monotonic() + 30,
        )
        runtime.ids.return_value = []
        runtime.inspect.return_value = None
        observed = []

        def first_create(_env, *args, **kwargs):
            self.assertEqual(
                args, ("create", "--no-recreate", "--no-build", "--pull", "never", "db")
            )
            self.assertIs(kwargs.get("effect"), True)
            receipt = read_record(root / "startup.json")
            pg = (root / "postgres").lstat()
            observed.append(
                (receipt.get("format"), receipt.get("pgdata_identity"), [pg.st_dev, pg.st_ino])
            )
            raise StartError("SYNTHETIC_CUT_BEFORE_FIRST_MOUNT", 3)

        with (
            patch.object(start, "ControlRuntime", return_value=runtime),
            patch.object(start, "preflight_port"),
            patch.object(start, "validate_config"),
            patch.object(start, "cleanup_attempt", return_value=[]),
        ):
            runtime.compose.side_effect = first_create
            code, result = start.start_result(None)
        self.assertEqual((code, result["reason"]), (3, "SYNTHETIC_CUT_BEFORE_FIRST_MOUNT"))
        self.assertEqual(len(observed), 1)
        self.assertEqual(observed[0][0], 2)
        self.assertEqual(observed[0][1], observed[0][2])
        self.assertEqual(read_record(root / "startup.json")["pgdata_identity"], observed[0][2])

    def test_fresh_instance_identity_is_durable_before_open_can_commit(self):
        """An OPEN ACK cut must leave an instance ID for a later fenced Stop."""
        import importlib
        import subprocess
        import time
        from types import SimpleNamespace
        from unittest.mock import Mock
        from uuid import uuid4

        from omnis_cli.lifecycle import StartError

        start = importlib.import_module("omnis_cli.start")
        (self.root / "data/omnis").mkdir(parents=True, mode=0o700)
        identity = str(uuid4())
        project = "omnis-local-" + "a" * 32
        runtime = Mock(
            receipt=SimpleNamespace(
                project=project,
                image_id="sha256:" + "b" * 64,
                docker_id="test-daemon",
            ),
            digest="c" * 64,
            host="unix:///run/docker.sock",
            deadline=time.monotonic() + 30,
        )
        runtime.ids.return_value = []
        runtime.inspect.return_value = None
        runtime.psql.return_value = "1234"
        runtime.run.return_value = subprocess.CompletedProcess([], 0, "migration-id", "")
        runtime.wait_container.return_value = {"ExitCode": 0}
        closed = {"admission_open": False, "generation": 0, "shutdown_command_id": None}
        root = self.root / "state/omnis"

        def before_open(_control, command, **_kwargs):
            self.assertEqual(command["op"], "open")
            try:
                installed = start.load_instance(root)
            except FileNotFoundError:
                raise StartError("INSTANCE_RECORD_MISSING_BEFORE_OPEN", 4) from None
            self.assertEqual((installed.instance_id, installed.project), (identity, project))
            raise StartError("CUT_AFTER_OPEN_WOULD_BE_SAFE", 4)

        with (
            patch.object(start, "ControlRuntime", return_value=runtime),
            patch.object(start, "preflight_port"),
            patch.object(start, "validate_config"),
            patch.object(
                start,
                "service_ids",
                side_effect=[
                    {"db": "db-id"},
                    {"db": "db-id", "api": "api-id", "supervisor": "supervisor-id"},
                ],
            ),
            patch.object(start, "database_identity", return_value=("1234", identity)),
            patch.object(start, "api_process", return_value=4242),
            patch.object(start, "wait_dashboard", return_value=closed),
            patch.object(start, "dashboard", return_value=closed),
            patch.object(start, "launch_forwarder", return_value=(None, -1, {"pid": 4242}, 101)),
            patch.object(start, "listener_owned"),
            patch.object(start, "socket_identity", return_value=[1, 2]),
            patch.object(start, "request", side_effect=before_open),
            patch.object(start, "cleanup_attempt", return_value=[]),
        ):
            code, result = start.start_result(None)
        self.assertEqual((code, result["reason"]), (4, "CUT_AFTER_OPEN_WOULD_BE_SAFE"))
        self.assertEqual(json.loads((root / "startup.json").read_text())["phase"], "FAILED_CLEANED")

    def test_headless_help_does_not_advertise_delivered_commands_as_missing(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaises(SystemExit) as result:
            main(["start", "--help"])
        self.assertEqual(result.exception.code, 0)
        self.assertIn("--no-open", output.getvalue())
        self.assertNotIn("not yet delivered", output.getvalue())

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="sl02-", dir=os.environ["TMPDIR"])
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.environment = patch.dict(
            os.environ,
            {
                "XDG_DATA_HOME": str(self.root / "data"),
                "XDG_STATE_HOME": str(self.root / "state"),
                "XDG_RUNTIME_DIR": str(self.root / "ipc"),
            },
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def test_verifying_journal_starts_after_subprocess_attestation_before_http(self):
        """Phase ordering only; Docker/readiness are substituted, not a live gate."""
        import importlib
        import subprocess
        import time
        from types import SimpleNamespace
        from unittest.mock import Mock

        start = importlib.import_module("omnis_cli.start")
        (self.root / "data/omnis").mkdir(parents=True, mode=0o700)
        runtime = Mock(
            receipt=SimpleNamespace(
                project="omnis-local-" + "a" * 32,
                image_id="sha256:" + "b" * 64,
                docker_id="test-daemon",
            ),
            digest="c" * 64,
            host="unix:///run/docker.sock",
            deadline=time.monotonic() + 5,
        )
        runtime.ids.return_value = []
        runtime.inspect.return_value = None
        runtime.psql.return_value = "1234"
        runtime.run.return_value = subprocess.CompletedProcess([], 0, "migration-id", "")
        runtime.wait_container.return_value = {"ExitCode": 0}
        phases = []
        journal = self.root / "state/omnis/startup.json"

        def api_attestation(*args):
            phases.append(("subprocess", json.loads(journal.read_text())["phase"]))
            return 4242

        def http_wait(*args, **kwargs):
            self.assertIs(kwargs.get("allow_closed"), False)
            phases.append(("http", json.loads(journal.read_text())["phase"]))
            raise start.StartError("SYNTHETIC_READINESS_FAILED", 3)

        out = io.StringIO()
        with (
            patch.object(start, "ControlRuntime", return_value=runtime),
            patch.object(start, "preflight_port"),
            patch.object(start, "validate_config"),
            patch.object(
                start,
                "service_ids",
                side_effect=[
                    {"db": "db-id"},
                    {"db": "db-id", "api": "api-id", "supervisor": "supervisor-id"},
                ],
            ),
            patch.object(start, "database_identity", return_value=("1234", "instance-id")),
            patch.object(start, "api_process", side_effect=api_attestation),
            patch.object(start, "wait_dashboard", side_effect=http_wait),
            patch.object(start, "cleanup_attempt", return_value=[]),
            contextlib.redirect_stdout(out),
        ):
            code = main(["start", "--no-open", "--json"])
        self.assertEqual(code, 3)
        self.assertEqual(phases, [("subprocess", "SERVICES"), ("http", "VERIFYING")])
        self.assertEqual(json.loads(journal.read_text())["failed_phase"], "VERIFYING")

    def test_cleanup_journal_error_does_not_downgrade_uncertainty(self):
        self.check_cleanup_journal_error(["forwarder"])

    def test_clean_resource_result_with_failed_journal_still_refuses_clean_verdict(self):
        self.check_cleanup_journal_error([])

    def check_cleanup_journal_error(self, problems):
        import importlib
        import types

        start = importlib.import_module("omnis_cli.start")
        (self.root / "data/omnis").mkdir(parents=True, mode=0o700)
        runtime = types.SimpleNamespace(
            receipt=types.SimpleNamespace(
                project="omnis-local-" + "a" * 32,
                image_id="sha256:" + "b" * 64,
                docker_id="test-daemon",
            ),
            digest="c" * 64,
            host="unix:///run/docker.sock",
            ids=lambda: [],
            inspect=lambda *args: None,
        )
        original = start.write_record

        def record(path, value, **kwargs):
            if value.get("phase") in {"UNCERTAIN", "FAILED_CLEANED"}:
                raise OSError("synthetic private disk failure")
            original(path, value, **kwargs)

        out = io.StringIO()
        with (
            patch.object(start, "ControlRuntime", return_value=runtime),
            patch.object(start, "preflight_port"),
            patch.object(
                start, "validate_config", side_effect=start.StartError("CONFIG_TEST_FAILURE")
            ),
            patch.object(start, "cleanup_attempt", return_value=problems),
            patch.object(start, "write_record", side_effect=record),
            contextlib.redirect_stdout(out),
        ):
            code = main(["start", "--no-open", "--json"])
        self.assertEqual(code, 4)
        self.assertEqual(json.loads(out.getvalue())["state"], "UNCERTAIN")
        self.assertNotIn("synthetic private disk failure", out.getvalue())

    def test_missing_release_is_actionable_and_does_not_create_state(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = main(["start", "--no-open", "--json"])
            except SystemExit as exc:
                code = exc.code
        self.assertEqual(code, 2)
        self.assertIn("RELEASE_REQUIRED", out.getvalue() + err.getvalue())
        result = json.loads(out.getvalue())
        self.assertFalse(result["dashboard_ready"])
        self.assertFalse(result["assessment_ready"])
        self.assertFalse(result["browser_opened"])
        self.assertFalse((self.root / "state").exists())
        self.assertFalse((self.root / "ipc").exists())
