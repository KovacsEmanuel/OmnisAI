"""Instance Stop is distinct from run Stop and never guesses an installation."""

import contextlib
import io
import json
import os
import socket
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from omnis_cli.lifecycle import StartError, cleanup_startup_ipc, socket_identity, write_record
from omnis_cli.main import main
from omnis_cli.stop import readback_stopped


class StopTest(unittest.TestCase):
    def test_stopped_receipt_refuses_symlinked_pgdata_or_database_secret(self) -> None:
        """Offline STOPPED readback must not follow a replacement data root."""
        with tempfile.TemporaryDirectory(prefix="sl04-data-", dir=os.environ["TMPDIR"]) as name:
            base = Path(name)
            root, foreign = base / "omnis", base / "foreign"
            root.mkdir(mode=0o700)
            foreign.mkdir(mode=0o700)
            with socket.socket() as reservation:
                reservation.bind(("127.0.0.1", 0))
                port = reservation.getsockname()[1]
            project = "omnis-local-" + "a" * 32
            instance_id, attempt = str(uuid4()), str(uuid4())
            control = root / "runtime-ipc"
            write_record(
                root / "instance.json",
                {
                    "version": 1,
                    "instance_id": instance_id,
                    "release": "0.1.0",
                    "schema": "0004_pairing_receipts",
                    "project": project,
                    "origin": f"http://127.0.0.1:{port}",
                },
            )
            record = {
                "format": 1,
                "phase": "STOPPED",
                "attempt": attempt,
                "project": project,
                "release_digest": "b" * 64,
                "image_id": "sha256:" + "c" * 64,
                "docker_host": "unix:///run/docker.sock",
                "docker_id": "synthetic-daemon",
                "control_dir": str(control),
                "port": port,
                "containers": {
                    key: char * 64
                    for key, char in zip(("db", "api", "supervisor"), "def", strict=True)
                },
                "system_id": "12345",
                "instance_id": instance_id,
                "forwarder": {},
                "listener_inode": 123,
                "api_socket": [1, 2],
                "control_socket": [3, 4],
                "open_command": str(uuid4()),
                "generation": 1,
                "supervisor_epoch": 1,
                "stop_command": str(uuid4()),
                "stop_expected": 1,
                "stop_generation": 2,
                "finalize_command": str(uuid4()),
            }
            runtime = SimpleNamespace(
                receipt=SimpleNamespace(
                    project=project, image_id=record["image_id"], docker_id=record["docker_id"]
                ),
                digest=record["release_digest"],
                host=record["docker_host"],
                attempt=None,
                uncertain=False,
                family_drained=True,
                ids=lambda: [],
                network=lambda _allowed: None,
                inspect=lambda _kind, _cid: None,
            )
            password = root / "db-password"
            password.write_text("synthetic\n")
            password.chmod(0o600)
            (root / "postgres").symlink_to(foreign, target_is_directory=True)
            with self.assertRaises(StartError):
                readback_stopped(runtime, root, control, record)
            (root / "postgres").unlink()
            (root / "postgres").mkdir(mode=0o711)
            other_secret = foreign / "password"
            other_secret.write_text("synthetic\n")
            other_secret.chmod(0o600)
            password.unlink()
            password.symlink_to(other_secret)
            with self.assertRaises(StartError):
                readback_stopped(runtime, root, control, record)
            password.unlink()
            password.write_text("synthetic\n")
            password.chmod(0o600)
            readback_stopped(runtime, root, control, record)

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
