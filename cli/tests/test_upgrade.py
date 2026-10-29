"""Finite upgrade host boundaries; synthetic OCI doubles are not installed QA."""

import contextlib
import importlib
import io
import json
import unittest
from dataclasses import asdict
from unittest.mock import patch

import test_cold_backup as cold_fixture
from omnis_cli.instance import load_instance
from omnis_cli.lifecycle import StartError, write_record


class UpgradeTest(unittest.TestCase):
    def test_stop_view_preserves_old_schema_and_refuses_wrong_schema(self):
        from pathlib import Path
        from types import SimpleNamespace

        from omnis_cli.start import _bound_instance
        from omnis_cli.start_runtime import POSTGRES
        from omnis_cli.stop_owner import _View

        with cold_fixture.ColdBackupTest().source() as (_base, root, stopped, runtime):
            runtime.schema = "0016_provider_models"
            runtime.pg_image = POSTGRES
            raw = json.loads((root / "instance.json").read_text())
            raw["schema"] = runtime.schema
            write_record(root / "instance.json", raw, replace=True)
            control = Path(stopped["control_dir"])
            _bound_instance(runtime, root, control, stopped)
            view = _View(runtime, SimpleNamespace(deadline=runtime.deadline))
            _bound_instance(view, root, control, stopped)
            view.schema = "0017_model_removal"
            with self.assertRaisesRegex(StartError, "RECOVERY_REQUIRED"):
                _bound_instance(view, root, control, stopped)

    def test_queued_lifecycle_callers_recheck_upgrade_intent_under_data_lock(self):
        from omnis_cli.start_runtime import refuse_upgrade

        for name in ("start", "stop", "verified"):
            with (
                self.subTest(caller=name),
                cold_fixture.ColdBackupTest().source() as (base, root, record, runtime),
            ):
                module = importlib.import_module("omnis_cli." + name)
                if name == "verified":
                    start = importlib.import_module("omnis_cli.start")
                    ready = {
                        k: v
                        for k, v in record.items()
                        if k in start.READY_FIELDS | start.vault_fields(record)
                    }
                    ready["phase"] = "READY"
                    start._ready_record(ready)
                    write_record(root / "startup.json", ready, replace=True)

                def admitted_then_queued(*_args):
                    refuse_upgrade(base / "d/omnis")
                    write_record(base / "d/omnis/upgrade.json", {"state": "IMAGE_PENDING"})
                    return runtime

                with patch.object(module, "ControlRuntime", side_effect=admitted_then_queued):
                    with self.assertRaisesRegex(StartError, "UPGRADE_RECOVERY_REQUIRED"):
                        if name == "verified":
                            with module.verified_instance():
                                self.fail("No verified effect admission")
                        else:
                            getattr(module, name + "_instance")()

    def test_restart_cross_binding_keeps_original_grant_and_completion_bytes(self):
        from uuid import uuid4

        from omnis_cli.backup import private_bytes
        from omnis_cli.stop_receipt import receipt_path
        from omnis_cli.upgrade import prepare_restart

        with cold_fixture.ColdBackupTest().source() as (base, root, stopped, runtime):
            data = base / "d/omnis"
            saved = data / "source"
            saved.mkdir(mode=0o700)
            raw = private_bytes(root / "startup.json", 16384)
            completion = private_bytes(receipt_path(root, stopped), 16384)
            for name, content in (("startup.json", raw), ("completion.json", completion)):
                (saved / name).write_bytes(content)
                (saved / name).chmod(0o600)
            runtime.release = data / "releases/0.1.1"
            runtime.digest = "f" * 64
            intent = {"state": "STARTING", "saved": "source", "target_digest": runtime.digest}
            write_record(data / "upgrade.json", intent)
            result = prepare_restart(runtime, root, stopped, str(uuid4()), intent)
            self.assertEqual(result["state"], "PREPARED")
            self.assertEqual((root / "startup.json").read_bytes(), raw)
            self.assertEqual(private_bytes(receipt_path(root, stopped), 16384), completion)
            self.assertEqual(result["request"]["grant"], json.loads(completion)["grant"])

    def test_known_preopen_failure_restores_only_old_digest_into_absent_root(self):
        from omnis_cli import upgrade as module
        from omnis_cli.start_runtime import private_identity

        fixture = cold_fixture.ColdBackupTest()
        with fixture.source() as (base, root, stopped, runtime):
            runtime.check_daemon = lambda: None
            data = base / "d/omnis"
            saved = data / "source"
            saved.mkdir(mode=0o700)
            for name, record in (
                ("installed.json", {"format": 1, "release": "0.1.0"}),
                ("image.json", {"synthetic": "old preserved binding"}),
            ):
                write_record(saved / name, record)
                write_record(data / name, record)
            (root / "vault-key/master.key").write_bytes(b"K" * 32)
            before = (root / "startup.json").read_bytes()
            with (
                patch("omnis_cli.backup.archive", side_effect=fixture.archive),
                patch("omnis_cli.backup.cold_identity", return_value=stopped["system_id"]),
            ):
                module.backup(runtime, root, base / "snapshot")
                intent = {
                    "state": "MIGRATED",
                    "upgrade_id": "fixture",
                    "saved": "source",
                    "backup": str(base / "snapshot"),
                    "old_attempt": stopped["attempt"],
                }
                write_record(data / "upgrade.json", intent)
                with patch.object(module, "ControlRuntime", return_value=runtime):
                    module.rollback(runtime, data, root, intent)
            self.assertEqual(intent["state"], "ROLLED_BACK")
            self.assertEqual((root / "restore-source/startup.json").read_bytes(), before)
            self.assertFalse((root / "startup.json").exists())
            self.assertEqual((root / "vault-key/master.key").read_bytes(), b"K" * 32)
            self.assertTrue((base / "s/omnis-upgrade-failed-fixture/startup.json").is_file())
            self.assertNotEqual(
                private_identity(root), private_identity(base / "s/omnis-upgrade-failed-fixture")
            )

    def test_duplicate_caller_never_rewrites_or_resends_active_intent(self):
        from omnis_cli import upgrade as module

        with cold_fixture.ColdBackupTest().source() as (base, _root, _record, _runtime):
            path = base / "d/omnis/upgrade.json"
            write_record(path, {"state": "MIGRATION_PENDING", "upgrade_id": "original"})
            before = path.read_bytes()
            with (
                patch.object(
                    module, "upgrade", side_effect=StartError("UPGRADE_RECOVERY_REQUIRED", 4)
                ),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                self.assertEqual(
                    module.upgrade_command(base / "missing", base / "snapshot", as_json=True), 4
                )
            self.assertEqual(path.read_bytes(), before)

    def test_old_locator_is_readable_but_unknown_pairs_are_refused(self):
        with cold_fixture.ColdBackupTest().source() as (_base, root, _record, _runtime):
            raw = json.loads((root / "instance.json").read_text())
            raw.update(release="0.1.0", schema="0016_provider_models")
            write_record(root / "instance.json", raw, replace=True)
            self.assertEqual(asdict(load_instance(root))["schema"], "0016_provider_models")
            raw.update(release="0.1.1", schema="0016_provider_models")
            write_record(root / "instance.json", raw, replace=True)
            with self.assertRaises(ValueError):
                load_instance(root)

    def test_cli_missing_bundle_refuses_without_effects(self):
        from omnis_cli.main import main

        with cold_fixture.ColdBackupTest().source() as (base, root, _record, _runtime):
            before = (root / "startup.json").read_bytes()
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = main(
                    [
                        "upgrade",
                        "--bundle",
                        str(base / "absent"),
                        "--backup",
                        str(base / "snapshot"),
                        "--json",
                    ]
                )
            self.assertEqual(code, 2)
            self.assertEqual(json.loads(output.getvalue())["state"], "REFUSED")
            self.assertEqual((root / "startup.json").read_bytes(), before)
            self.assertFalse((base / "snapshot").exists())

    def test_active_intent_fences_runtime_before_daemon_io(self):
        from omnis_cli.start_runtime import ControlRuntime

        with cold_fixture.ColdBackupTest().source() as (base, _root, _record, _runtime):
            data = base / "d/omnis"
            data.mkdir(parents=True, mode=0o700, exist_ok=True)
            write_record(data / "upgrade.json", {"state": "MIGRATION_PENDING"})
            with self.assertRaisesRegex(StartError, "UPGRADE_RECOVERY_REQUIRED"):
                ControlRuntime(base / "d", 0)

    def test_start_refuses_active_upgrade_before_decoding_mixed_journal(self):
        from omnis_cli.main import main

        with cold_fixture.ColdBackupTest().source() as (base, root, _record, _runtime):
            write_record(
                base / "d/omnis/upgrade.json", {"state": "STARTING", "upgrade_id": "other"}
            )
            write_record(root / "startup.json", {"phase": "VERIFYING"}, replace=True)
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(main(["start", "--no-open", "--json"]), 4)
            self.assertEqual(json.loads(output.getvalue())["reason"], "UPGRADE_RECOVERY_REQUIRED")

    def test_rollback_never_accepts_open_or_unknown_effect(self):
        module = importlib.import_module("omnis_cli.upgrade")
        with cold_fixture.ColdBackupTest().source() as (base, root, record, runtime):
            for state in ("OPEN_PENDING", "COMPLETE", "UNCERTAIN"):
                with self.subTest(state=state):
                    with self.assertRaisesRegex(StartError, "UPGRADE_ROLLBACK_REFUSED"):
                        module.rollback(runtime, base / "d/omnis", root, {"state": state})
            self.assertEqual(json.loads((root / "startup.json").read_text())["phase"], "STOPPED")
