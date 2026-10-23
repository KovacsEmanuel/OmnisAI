"""Cold CLI filesystem journey; OCI/PG are explicit doubles, not restore QA."""

import contextlib
import importlib
import io
import os
import tarfile
import unittest
from unittest.mock import patch

from omnis_cli.lifecycle import read_record
from omnis_cli.main import main
from omnis_cli.start_runtime import private_identity
from stopped_fixture import completed_fixture
from test_stop import private_stop_fixture


class ColdBackupTest(unittest.TestCase):
    @contextlib.contextmanager
    def source(self):
        with private_stop_fixture() as (base, root, foreign, control, record, runtime):
            runtime.provider_settings = True
            runtime.receipt.profile = "t1-provider-settings"
            record["format"] = 5
            for name in ("vault", "vault-key"):
                (root / name).mkdir(mode=0o700)
                record[name.replace("-", "_") + "_identity"] = private_identity(root / name)
            (root / "db-password").write_text("a" * 48 + "\n")
            (root / "vault/vault.json").write_bytes(b'{"encrypted":"SOURCE"}')
            (root / "vault/vault.json").chmod(0o600)
            (root / "vault-key/master.key").write_bytes(b"SOURCE separate key\n")
            (root / "vault-key/master.key").chmod(0o600)
            runtime.release = base / "d/omnis/releases/0.1.0"
            with completed_fixture(root, control, record, runtime):
                env = {
                    "XDG_STATE_HOME": str(base / "s"),
                    "XDG_DATA_HOME": str(base / "d"),
                    "XDG_CONFIG_HOME": str(base / "config"),
                    "XDG_RUNTIME_DIR": "",
                }
                with patch.dict(os.environ, env):
                    yield base, root, record, runtime

    def module(self):
        self.assertIsNotNone(importlib.util.find_spec("omnis_cli.backup"), "Cold CLI missing")
        return importlib.import_module("omnis_cli.backup")

    def archive(self, runtime, root, fd, *, restore=False):
        if restore:
            with os.fdopen(os.dup(fd), "rb") as source, tarfile.open(fileobj=source) as archive:
                archive.extractall(root / "postgres", filter="data")
        else:
            with (
                os.fdopen(os.dup(fd), "wb") as dest,
                tarfile.open(fileobj=dest, mode="w") as archive,
            ):
                for name, content in (
                    ("18/docker/PG_VERSION", b"18\n"),
                    ("18/docker/global/pg_control", b"\x00\xffSOURCE"),
                ):
                    entry = tarfile.TarInfo(name)
                    entry.size, entry.mode = len(content), 0o600
                    archive.addfile(entry, io.BytesIO(content))

    def test_cli_backup_publishes_verifiable_private_snapshot_without_master_key(self):
        module = self.module()
        with self.source() as (base, root, record, runtime):
            saved = (root / "startup.json").read_bytes()
            with (
                patch.object(module, "ControlRuntime", return_value=runtime),
                patch.object(module, "archive", side_effect=self.archive),
                patch.object(module, "cold_identity", return_value=record["system_id"]),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                self.assertEqual(main(["backup", "--output", str(base / "snapshot")]), 0)
            snapshot = base / "snapshot"
            self.assertEqual((root / "startup.json").read_bytes(), saved)
            self.assertEqual((snapshot / "startup.json").read_bytes(), saved)
            self.assertEqual(
                set(p.name for p in snapshot.iterdir()),
                {
                    "manifest.json",
                    "postgres.tar",
                    "db-password",
                    "vault.json",
                    "startup.json",
                    "completion.json",
                },
            )
            self.assertLessEqual((snapshot / "manifest.json").stat().st_size, 16384)
            self.assertEqual(snapshot.stat().st_mode & 0o777, 0o700)
            self.assertNotIn(
                b"SOURCE separate key", b"".join(p.read_bytes() for p in snapshot.iterdir())
            )
            self.assertEqual(
                read_record(snapshot / "manifest.json")["instance_id"], record["instance_id"]
            )
