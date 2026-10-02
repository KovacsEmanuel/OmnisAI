"""Instance Stop is distinct from run Stop and never guesses an installation."""

import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from omnis_cli.main import main


class StopTest(unittest.TestCase):
    def test_stop_without_installed_release_refuses_without_state_effects(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sl04-", dir=os.environ["TMPDIR"]) as name:
            root = Path(name)
            env = {
                "XDG_DATA_HOME": str(root / "data"),
                "XDG_STATE_HOME": str(root / "state"),
                "XDG_RUNTIME_DIR": str(root / "runtime"),
            }
            stdout, stderr = io.StringIO(), io.StringIO()
            with (
                patch.dict(os.environ, env),
                contextlib.redirect_stdout(stdout),
                contextlib.redirect_stderr(stderr),
            ):
                code = main(["stop", "--json"])
            assert code == 2
            result = json.loads(stdout.getvalue())
            assert result["state"] == "REFUSED" and result["reason"] == "RELEASE_REQUIRED"
            assert result["dashboard_ready"] is False
            assert result["assessment_ready"] is False
            assert not (root / "state").exists()
            assert not (root / "runtime").exists()
            assert not stderr.getvalue() or "Traceback" not in stderr.getvalue()
