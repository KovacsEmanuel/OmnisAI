"""Cold CLI filesystem journey; OCI/PG are explicit doubles, not restore QA."""

import contextlib
import importlib
import io
import json
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

    def test_queued_cold_callers_recheck_upgrade_intent_under_data_lock(self):
        from omnis_cli.lifecycle import StartError, write_record
        from omnis_cli.start_runtime import refuse_upgrade

        module = self.module()
        for command in ("backup", "restore"):
            with self.subTest(command=command), self.source() as (base, _root, _old, runtime):

                def admitted_then_queued(*_args):
                    refuse_upgrade(base / "d/omnis")
                    write_record(base / "d/omnis/upgrade.json", {"state": "IMAGE_PENDING"})
                    return runtime

                with (
                    patch.object(module, "ControlRuntime", side_effect=admitted_then_queued),
                    patch.object(module, "cold_identity", side_effect=AssertionError("No helper")),
                    patch.object(module, "archive", side_effect=AssertionError("No archive")),
                    contextlib.redirect_stdout(io.StringIO()) as output,
                ):
                    self.assertEqual(module.cold_command(command, base / "snapshot"), 4)
                self.assertIn("UPGRADE_RECOVERY_REQUIRED", output.getvalue())
                self.assertFalse((base / "snapshot").exists())
                with self.assertRaisesRegex(StartError, "UPGRADE_RECOVERY_REQUIRED"):
                    refuse_upgrade(base / "d/omnis")

    def test_restore_status_is_read_only_and_refuses_invalid_admission(self):
        module = self.module()
        status = importlib.import_module("omnis_cli.status")
        with self.source() as (base, root, old, runtime):
            with (
                patch.object(module, "archive", side_effect=self.archive),
                patch.object(module, "cold_identity", return_value=old["system_id"]),
            ):
                module.backup(runtime, root, base / "snapshot")
                parent = base / "new"
                parent.mkdir(mode=0o700)
                target = parent / "omnis"
                with patch.dict(os.environ, {"XDG_STATE_HOME": str(parent)}):
                    module.restore(runtime, target, base / "snapshot", None)
                    original = (target / "restore.json").read_bytes()
                    before = {
                        p.relative_to(target): p.read_bytes()
                        for p in target.rglob("*")
                        if p.is_file()
                    }
                    for mutation in (None, "marker", "resource", "startup"):
                        with self.subTest(mutation=mutation), contextlib.ExitStack() as scope:
                            scope.enter_context(
                                patch.object(status, "ControlRuntime", return_value=runtime)
                            )
                            scope.enter_context(
                                patch.object(
                                    status, "request", side_effect=AssertionError("No control IO")
                                )
                            )
                            scope.enter_context(
                                patch.object(
                                    runtime,
                                    "run",
                                    side_effect=AssertionError("No effects"),
                                    create=True,
                                )
                            )
                            scope.enter_context(
                                patch.object(
                                    runtime,
                                    "ids",
                                    return_value=["f" * 64] if mutation == "resource" else [],
                                )
                            )
                            if mutation == "marker":
                                (target / "restore.json").write_bytes(
                                    original.replace(b"STOPPED", b"STARTING")
                                )
                            elif mutation == "startup":
                                (target / "startup.json").write_text("{}")
                                (target / "startup.json").chmod(0o600)
                            output = io.StringIO()
                            with contextlib.redirect_stdout(output):
                                code = main(["status", "--json"])
                            result = json.loads(output.getvalue())
                            if mutation is None:
                                self.assertEqual(
                                    (code, result["state"]), (0, "RESTORED_STOPPED"), result
                                )
                                self.assertEqual(result["provenance"], "RESTORE_ADMISSION")
                                self.assertEqual(result["instance_id"], old["instance_id"])
                                self.assertNotIn("generation", result)
                                self.assertNotIn("supervisor_epoch", result)
                                self.assertFalse(result["admission_open"])
                                self.assertEqual(
                                    before,
                                    {
                                        p.relative_to(target): p.read_bytes()
                                        for p in target.rglob("*")
                                        if p.is_file()
                                    },
                                )
                            else:
                                self.assertNotEqual(code, 0)
                                self.assertNotEqual(result["state"], "RESTORED_STOPPED")
                            (target / "restore.json").write_bytes(original)
                            if mutation == "startup":
                                (target / "startup.json").unlink()

    def test_restore_new_identity_stopped_separate_key_and_no_overwrite(self):
        module = self.module()
        with self.source() as (base, root, old, runtime):
            with (
                patch.object(module, "ControlRuntime", return_value=runtime),
                patch.object(module, "archive", side_effect=self.archive),
                patch.object(module, "cold_identity", return_value=old["system_id"]),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                self.assertEqual(main(["backup", "--output", str(base / "snapshot")]), 0)
                target_parent = base / "new"
                target_parent.mkdir(mode=0o700)
                with patch.dict(os.environ, {"XDG_STATE_HOME": str(target_parent)}):
                    self.assertEqual(main(["restore", "--backup", str(base / "snapshot")]), 0)
                    target = target_parent / "omnis"
                    self.assertFalse((target / "startup.json").exists())
                    self.assertFalse((target / "vault-key/master.key").exists())
                    marker = read_record(target / "restore.json")
                    self.assertEqual(marker["state"], "STOPPED")
                    self.assertNotEqual(marker["pgdata_identity"], old["pgdata_identity"])
                    self.assertEqual(
                        (target / "restore-source/startup.json").read_bytes(),
                        (root / "startup.json").read_bytes(),
                    )
                    self.assertEqual(
                        module.admit_restore(runtime, target)["instance_id"], old["instance_id"]
                    )
                    self.assertEqual(main(["restore", "--backup", str(base / "snapshot")]), 4)
                second = base / "keyed"
                second.mkdir(mode=0o700)
                key = base / "separate.key"
                key.write_bytes(b"K" * 32)
                key.chmod(0o600)
                with patch.dict(os.environ, {"XDG_STATE_HOME": str(second)}):
                    self.assertEqual(
                        main(
                            [
                                "restore",
                                "--backup",
                                str(base / "snapshot"),
                                "--master-key-file",
                                str(key),
                            ]
                        ),
                        0,
                    )
                    self.assertEqual(
                        (second / "omnis/vault-key/master.key").read_bytes(), b"K" * 32
                    )
                    marker = module.admit_restore(runtime, second / "omnis")
                    self.assertEqual(marker["instance_id"], old["instance_id"])
