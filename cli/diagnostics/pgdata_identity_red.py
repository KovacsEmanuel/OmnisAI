"""Opt-in offline PGDATA identity regression; no Docker or PostgreSQL."""

import os
import socket
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from uuid import uuid4

from omnis_cli.lifecycle import StartError, write_record
from omnis_cli.start_runtime import ControlRuntime
from omnis_cli.stop import readback_stopped


class PGDataReadback(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="sl04-identity-", dir=os.environ["TMPDIR"])
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.root = base / "state/omnis"
        self.root.mkdir(parents=True, mode=0o700)
        self.control = self.root / "runtime-ipc"
        self.pg = self.root / "postgres"
        self.pg.mkdir(mode=0o711)
        self.pg.chmod(0o711)
        (self.pg / "18/docker").mkdir(parents=True)
        (self.pg / "18/docker/PG_VERSION").write_text("18\n")
        secret = self.root / "db-password"
        secret.write_text("synthetic\n")
        secret.chmod(0o600)
        iid = str(uuid4())
        project = "omnis-local-" + "a" * 32
        with socket.socket() as reservation:
            reservation.bind(("127.0.0.1", 0))
            port = reservation.getsockname()[1]
        write_record(
            self.root / "instance.json",
            {
                "version": 1,
                "instance_id": iid,
                "release": "0.1.0",
                "schema": "0004_pairing_receipts",
                "project": project,
                "origin": f"http://127.0.0.1:{port}",
            },
        )
        self.record = {
            "format": 2,
            "phase": "STOPPED",
            "attempt": str(uuid4()),
            "project": project,
            "release_digest": "b" * 64,
            "image_id": "sha256:" + "c" * 64,
            "docker_host": "unix:///run/docker.sock",
            "docker_id": "synthetic-daemon",
            "control_dir": str(self.control),
            "port": port,
            "containers": {
                key: char * 64 for key, char in zip(("db", "api", "supervisor"), "def", strict=True)
            },
            "system_id": "12345",
            "pgdata_identity": [self.pg.lstat().st_dev, self.pg.lstat().st_ino],
            "instance_id": iid,
            "forwarder": {
                "pid": 321,
                "start_ticks": "123",
                "boot_id": str(uuid4()),
                "executable": "/usr/bin/python3",
                "argv": ["python3", "-I"],
            },
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
            "finalized_generation": 2,
            "teardown_completed": ["forwarder", "api", "supervisor", "db", "network", "ipc"],
        }
        self.runtime = cast(
            ControlRuntime,
            SimpleNamespace(
                receipt=SimpleNamespace(
                    project=project,
                    image_id=self.record["image_id"],
                    docker_id=self.record["docker_id"],
                ),
                digest=self.record["release_digest"],
                host=self.record["docker_host"],
                attempt=None,
                deadline=time.monotonic() + 180,
                uncertain=False,
                family_drained=True,
                ids=lambda: [],
                network=lambda _allowed: None,
                inspect=lambda _kind, _cid: None,
            ),
        )

    def readback(self) -> None:
        readback_stopped(self.runtime, self.root, self.control, self.record)

    def test_original_retained_dataset_is_accepted(self) -> None:
        self.readback()
        self.assertEqual((self.pg / "18/docker/PG_VERSION").read_text(), "18\n")

    def test_legacy_format_one_cannot_adopt_current_inode(self) -> None:
        self.record["format"] = 1
        self.record.pop("pgdata_identity")
        with self.assertRaisesRegex(StartError, "RECOVERY_REQUIRED"):
            self.readback()
        self.assertEqual((self.pg / "18/docker/PG_VERSION").read_text(), "18\n")

    def test_replacement_with_copied_marker_same_uid_mode_is_rejected(self) -> None:
        original = self.root / "saved-postgres"
        self.pg.rename(original)
        self.pg.mkdir(mode=0o711)
        self.pg.chmod(0o711)
        (self.pg / "18/docker").mkdir(parents=True)
        (self.pg / "18/docker/PG_VERSION").write_bytes(
            (original / "18/docker/PG_VERSION").read_bytes()
        )
        self.assertEqual(self.pg.lstat().st_uid, original.lstat().st_uid)
        self.assertEqual(self.pg.lstat().st_mode & 0o777, original.lstat().st_mode & 0o777)
        self.assertNotEqual(
            (self.pg.lstat().st_dev, self.pg.lstat().st_ino),
            (original.lstat().st_dev, original.lstat().st_ino),
        )
        self.assertEqual((self.pg / "18/docker/PG_VERSION").read_text(), "18\n")
        self.assertTrue((original / "18/docker/PG_VERSION").exists())
        with self.assertRaisesRegex(StartError, "RECOVERY_REQUIRED"):
            self.readback()

    def test_symlink_is_rejected(self) -> None:
        original = self.root / "saved-postgres"
        self.pg.rename(original)
        self.pg.symlink_to(original, target_is_directory=True)
        with self.assertRaisesRegex(StartError, "RECOVERY_REQUIRED"):
            self.readback()

    def test_secret_symlink_is_rejected(self) -> None:
        secret = self.root / "db-password"
        original = self.root / "saved-secret"
        secret.rename(original)
        secret.symlink_to(original)
        with self.assertRaisesRegex(StartError, "RECOVERY_REQUIRED"):
            self.readback()

    def test_instance_identity_mismatch_is_rejected(self) -> None:
        self.record["instance_id"] = str(uuid4())
        with self.assertRaisesRegex(StartError, "RECOVERY_REQUIRED"):
            self.readback()


if __name__ == "__main__":
    unittest.main(verbosity=2)
