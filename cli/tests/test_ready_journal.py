"""READY startup receipts must be strict before OCI/HTTP attestation."""

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from omnis_cli.instance import Instance
from omnis_cli.lifecycle import StartError

start = importlib.import_module("omnis_cli.start")


class ReadyJournalTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"])
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "omnis"
        self.root.mkdir(mode=0o700)
        pg = self.root / "postgres"
        pg.mkdir(mode=0o711)
        pg.chmod(0o711)
        info = pg.lstat()
        self.control = self.root / "runtime-ipc"
        self.port = 8765
        identity = str(uuid4())
        project = "omnis-local-" + "a" * 32
        self.instance = Instance(
            identity, "0.1.0", "0004_pairing_receipts", project, f"http://127.0.0.1:{self.port}"
        )
        self.runtime = SimpleNamespace(
            digest="b" * 64,
            host="unix:///run/docker.sock",
            receipt=SimpleNamespace(
                project=project, image_id="sha256:" + "c" * 64, docker_id="synthetic-daemon"
            ),
        )
        self.record = {
            "format": 2,
            "phase": "READY",
            "attempt": str(uuid4()),
            "project": project,
            "release_digest": self.runtime.digest,
            "image_id": self.runtime.receipt.image_id,
            "docker_host": self.runtime.host,
            "docker_id": self.runtime.receipt.docker_id,
            "control_dir": str(self.control),
            "port": self.port,
            "containers": {"db": "d" * 64, "api": "e" * 64, "supervisor": "f" * 64},
            "system_id": "123456789",
            "pgdata_identity": [info.st_dev, info.st_ino],
            "instance_id": identity,
            "forwarder": {"pid": 321},
            "listener_inode": 123,
            "api_socket": [2049, 123],
            "control_socket": [2049, 124],
            "open_command": str(uuid4()),
            "generation": 1,
            "supervisor_epoch": 1,
        }

    def reason(self, record):
        with (
            patch.object(start, "load_instance", return_value=self.instance),
            patch.object(
                start, "service_ids", side_effect=StartError("ATTESTATION_REACHED", 3)
            ) as services,
        ):
            with self.assertRaises(StartError) as error:
                start.verify_running(self.runtime, self.root, self.control, record, self.port)
        return error.exception.reason, services.call_count

    def test_valid_ready_receipt_reaches_resource_attestation(self):
        self.assertEqual(self.reason(self.record), ("ATTESTATION_REACHED", 1))

    def test_bool_coercions_unknown_fields_and_socket_shapes_fail_before_resources(self):
        cases = []
        for key in ("format", "generation", "supervisor_epoch"):
            cases.append((key, {**self.record, key: True}))
        pg = self.record["pgdata_identity"]
        assert isinstance(pg, list)
        cases.append(("pgdata-bool", {**self.record, "pgdata_identity": [True, pg[1]]}))
        cases.append(
            (
                "pgdata-missing",
                {key: value for key, value in self.record.items() if key != "pgdata_identity"},
            )
        )
        cases.extend(
            [
                ("unknown", {**self.record, "ignored_admin": "synthetic-marker"}),
                ("socket-bool", {**self.record, "api_socket": [True, 123]}),
                ("socket-missing", {**self.record, "control_socket": [2049]}),
            ]
        )
        for label, record in cases:
            with self.subTest(label=label):
                self.assertEqual(self.reason(record), ("RECOVERY_REQUIRED", 0))
