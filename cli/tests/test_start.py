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

    def test_cleanup_journal_error_does_not_downgrade_uncertainty(self):
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
            if value.get("phase") == "UNCERTAIN":
                raise OSError("synthetic private disk failure")
            original(path, value, **kwargs)

        out = io.StringIO()
        with (
            patch.object(start, "ControlRuntime", return_value=runtime),
            patch.object(start, "preflight_port"),
            patch.object(
                start, "validate_config", side_effect=start.StartError("CONFIG_TEST_FAILURE")
            ),
            patch.object(start, "cleanup_attempt", return_value=["forwarder"]),
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
