"""Instance Stop is distinct from run Stop and never guesses an installation."""

import contextlib
import io
import json
import os
import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from omnis_cli.lifecycle import cleanup_startup_ipc, socket_identity
from omnis_cli.main import main


class StopTest(unittest.TestCase):
    def test_stale_owned_socket_receipt_never_unlinks_replaced_private_peer(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sl04-ipc-", dir=os.environ["TMPDIR"]) as name:
            root = Path(name) / "omnis"
            http, control = root / "http", root / "runtime-ipc"
            root.mkdir(mode=0o700)
            http.mkdir(mode=0o700)
            control.mkdir(mode=0o700)
            lock = http / "api.lock"
            lock.write_text("")
            lock.chmod(0o600)
            path = http / "api.sock"
            with socket.socket(socket.AF_UNIX) as old:
                old.bind(str(path))
                path.chmod(0o600)
                expected = socket_identity(path)
                substitute = http / "replacement.sock"
                with socket.socket(socket.AF_UNIX) as replacement:
                    replacement.bind(str(substitute))
                    substitute.chmod(0o600)
                    actual = socket_identity(substitute)
                    os.replace(substitute, path)
                assert actual != expected
                problems = cleanup_startup_ipc(root, control, expected={"api": expected})
                assert problems == ["IPC ownership uncertain"]
                assert socket_identity(path) == actual
            path.unlink()
            with socket.socket(socket.AF_UNIX) as owned:
                owned.bind(str(path))
                path.chmod(0o600)
                current = socket_identity(path)
            assert cleanup_startup_ipc(root, control, expected={"api": current}) == []
            assert not os.path.lexists(path)

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
