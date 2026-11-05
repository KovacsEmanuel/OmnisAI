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
    def test_finite_pairs_preserve_source_before_backup(self):
        for s1 in (False, True):
            with self.subTest(s1=s1):
                self.finite_pair_before_backup(s1)

    def finite_pair_before_backup(self, s1):
        from omnis_cli import upgrade as module

        with self.source_upgrade(s1=s1) as (base, root, _stopped, runtime, _target, bundle):
            before = (root / "startup.json").read_bytes()

            def backup_admitted(*args):
                self.assertEqual(args, (runtime, root, base / "snapshot"))
                self.assertEqual((root / "startup.json").read_bytes(), before)
                self.assertFalse((root / "catalog").exists())
                self.assertEqual(
                    json.loads((base / "d/omnis/upgrade.json").read_bytes())["state"],
                    "BACKUP_PENDING",
                )
                raise RuntimeError("SOURCE_BACKUP_REACHED")

            with (
                patch.object(module, "ControlRuntime", return_value=runtime),
                patch.object(module, "backup", side_effect=backup_admitted) as backup,
            ):
                with self.assertRaisesRegex(RuntimeError, "SOURCE_BACKUP_REACHED"):
                    module.upgrade(bundle, base / "snapshot")
            backup.assert_called_once()

    @contextlib.contextmanager
    def source_upgrade(self, *, s1=True):
        import copy

        from omnis_cli.start_runtime import ControlRuntime
        from test_provider_settings_profile import ProviderSettingsBundleTest

        fixture = ProviderSettingsBundleTest()
        self.addCleanup(fixture.doCleanups)
        version, schema = ("0.1.2", "0019_agent_runs") if s1 else ("0.1.1", "0017_model_removal")
        bundle = fixture.bundle(version=version, schema=schema, dependencies=fixture.S0)
        with cold_fixture.ColdBackupTest().source() as (base, root, stopped, runtime):
            data = base / "d/omnis"
            old_version, old_schema = (
                ("0.1.1", "0017_model_removal") if s1 else ("0.1.0", "0016_provider_models")
            )
            runtime.schema = old_schema
            runtime.receipt.release = old_version
            runtime.release = data / "releases" / old_version
            write_record(data / "installed.json", {"format": 1, "release": old_version})
            write_record(data / "image.json", {"synthetic": "source binding"})
            raw = json.loads((root / "instance.json").read_bytes())
            raw.update(release=old_version, schema=old_schema)
            write_record(root / "instance.json", raw, replace=True)
            (root / "vault-key/master.key").write_bytes(b"K" * 32)
            target = ControlRuntime.__new__(ControlRuntime)
            target.__dict__.update(vars(runtime))
            target.receipt = copy.copy(runtime.receipt)
            target.receipt.release = version
            target.schema = schema
            target.release = data / "releases" / version
            import hashlib

            from omnis_cli.release import _manifest

            target.digest = hashlib.sha256(_manifest(bundle.bundle)[0]).hexdigest()
            yield base, root, stopped, runtime, target, bundle.bundle

    def test_upgrade_reaches_normal_restart_after_verified_backup(self):
        for s1 in (False, True):
            with self.subTest(s1=s1):
                self.upgrade_reaches_normal_restart_after_verified_backup(s1)

    def upgrade_reaches_normal_restart_after_verified_backup(self, s1):
        from uuid import uuid4

        from omnis_cli import upgrade as module
        from omnis_cli.start_runtime import private_identity, provider_settings_overlay

        with self.source_upgrade(s1=s1) as (base, root, stopped, old, target, bundle):
            data = base / "d/omnis"
            before = (root / "startup.json").read_bytes()
            events = []
            fixture = cold_fixture.ColdBackupTest()
            original_backup, original_restore = module.backup, module.restore

            def backup(*args):
                events.append("backup")
                self.assertFalse((root / "catalog").exists())
                original_backup(*args)

            def restore(*args):
                events.append("restore")
                original_restore(*args)

            def image(binding, *_args, **kwargs):
                events.append("image")
                self.assertEqual(events, ["backup", "restore", "image"])
                self.assertEqual(kwargs["version"], target.release.name)
                write_record(binding / "image.json", {"synthetic": "target binding"})
                target.receipt.docker_host = old.host
                return target.receipt

            def migration(runtime, _root, _control, record, intent, _data):
                events.append("migration")
                self.assertEqual((root / "startup.json").read_bytes(), before)
                runtime.upgrading = True
                if s1:
                    self.assertEqual(private_identity(root / "catalog"), intent["catalog_identity"])
                provider_settings_overlay(runtime, {"OMNIS_STATE_ROOT": str(root)})
                module.persist(data, intent, "MIGRATED")

            def restart(*, _upgrade):
                events.append("start")
                self.assertEqual(load_instance(root).schema, target.schema)
                prepared = module.prepare_restart(target, root, stopped, str(uuid4()), _upgrade)
                self.assertEqual(
                    prepared["request"]["grant"]["instance_id"], stopped["instance_id"]
                )
                return {"state": "RUNNING", "instance_id": stopped["instance_id"]}

            with (
                patch.object(module, "ControlRuntime", side_effect=[old, target]),
                patch.object(module, "backup", side_effect=backup),
                patch.object(module, "restore", side_effect=restore),
                patch("omnis_cli.backup.archive", side_effect=fixture.archive),
                patch("omnis_cli.backup.cold_identity", return_value=stopped["system_id"]),
                patch.object(module, "install_image", side_effect=image),
                patch.object(module, "migration", side_effect=migration),
                patch("omnis_cli.start.start_instance", side_effect=restart),
            ):
                result = module.upgrade(bundle, base / "snapshot")
            self.assertEqual(result["upgrade"], "COMPLETED")
            self.assertEqual(events, ["backup", "restore", "image", "migration", "start"])
            self.assertEqual((root / "startup.json").read_bytes(), before)
            self.assertEqual((root / "vault-key/master.key").read_bytes(), b"K" * 32)
            self.assertEqual((root / "vault/vault.json").read_bytes(), b'{"encrypted":"SOURCE"}')

    def test_migration_producer_uses_finite_attested_job_and_original_request(self):
        for s1 in (False, True):
            for fault in ("none", "source", "argv", "reply", "drain"):
                with self.subTest(s1=s1, fault=fault):
                    self.migration_job(s1, fault)

    def migration_job(self, s1, fault):
        import hashlib
        import subprocess
        from pathlib import Path
        from unittest.mock import Mock
        from uuid import uuid4

        from omnis_cli import upgrade as module
        from omnis_cli.start_runtime import private_identity
        from omnis_cli.stop_receipt import receipt_path
        from runtime_inspect_fixture import container_item, image_item

        with self.source_upgrade(s1=s1) as (base, root, stopped, old, target, _bundle):
            data = base / "d/omnis"
            saved = data / "source"
            saved.mkdir(mode=0o700)
            write_record(saved / "instance.json", json.loads((root / "instance.json").read_bytes()))
            intent = {"state": "IMAGE_READY", "upgrade_id": str(uuid4()), "saved": "source"}
            write_record(data / "upgrade.json", intent)
            if s1:
                (root / "catalog").mkdir(mode=0o700)
                target.upgrade_catalog_identity = private_identity(root / "catalog")
            before = (root / "startup.json").read_bytes()
            completion = receipt_path(root, stopped).read_bytes()
            expected = {
                "version": 1,
                "reconciliation_id": intent["upgrade_id"],
                "system_identifier": stopped["system_id"],
                "grant": json.loads(completion)["grant"],
                "completion_sha256": hashlib.sha256(completion).hexdigest(),
            }
            db, job = "1" * 64, "2" * 64
            resources = {db}
            item = {}
            replies = iter(
                [
                    stopped["system_id"],
                    stopped["instance_id"],
                    target.schema if fault == "source" else old.schema,
                    target.schema,
                ]
            )
            target.psql = Mock(side_effect=lambda *_args: next(replies))
            target.check_daemon = Mock()
            target.wait_container = Mock()
            target.compose = Mock()
            target.ids = lambda: list(resources)
            target.network = lambda _allowed: "1" * 64 if resources else None

            def inspect(kind, ident):
                if kind == "image":
                    return image_item(target, "migrate")
                if ident == job and job in resources:
                    return item
                return {"State": {"Running": False}} if ident == db and db in resources else None

            target.inspect = inspect

            def run(*args, **kwargs):
                if args[0] == "create":
                    self.assertEqual(args[-1], "--upgrade-s1" if s1 else "--upgrade-t1")
                    resources.add(job)
                    item.update(
                        container_item(
                            target,
                            "migrate",
                            job,
                            root,
                            Path(stopped["control_dir"]),
                            stopped["port"],
                            "created",
                        )
                    )
                    item["Config"].update(
                        Cmd=list(args[-5:]),
                        **dict.fromkeys(
                            (
                                "OpenStdin",
                                "StdinOnce",
                                "AttachStdin",
                                "AttachStdout",
                                "AttachStderr",
                            ),
                            True,
                        ),
                    )
                    if fault == "argv":
                        item["Config"]["Cmd"][-1] = "--initialize"
                    return subprocess.CompletedProcess(args, 0, job, "")
                if args[0:2] == ("start", "--attach"):
                    self.assertLessEqual(len(kwargs["stdin"]), 16384)
                    self.assertEqual(json.loads(kwargs["stdin"]), expected)
                    item["State"] = {"Running": False, "Status": "exited", "ExitCode": 0}
                    if fault == "drain":
                        target.family_drained = False
                    return subprocess.CompletedProcess(
                        args,
                        0,
                        json.dumps(
                            {
                                "ok": True,
                                "schema": old.schema if fault == "reply" else target.schema,
                                "request": expected,
                            }
                        ),
                        "",
                    )
                if args[0:2] == ("container", "rm"):
                    resources.remove(args[2])
                return subprocess.CompletedProcess(args, 0, "", "")

            target.run = Mock(side_effect=run)
            with (
                patch("omnis_cli.start.validate_config"),
                patch("omnis_cli.start.service_ids", return_value={"db": db}),
                patch.object(module, "cold_identity", return_value=stopped["system_id"]),
            ):
                if fault == "none":
                    module.migration(
                        target, root, Path(stopped["control_dir"]), stopped, intent, data
                    )
                    self.assertEqual(intent["state"], "MIGRATED")
                    self.assertFalse(resources)
                else:
                    reason = {
                        "source": "UPGRADE_DATABASE_MISMATCH",
                        "argv": "CONTAINER_IDENTITY_MISMATCH",
                        "reply": "UPGRADE_MIGRATION_UNCERTAIN",
                        "drain": "UPGRADE_MIGRATION_UNCERTAIN",
                    }[fault]
                    with self.assertRaisesRegex(StartError, reason):
                        module.migration(
                            target, root, Path(stopped["control_dir"]), stopped, intent, data
                        )
                    self.assertNotEqual(intent["state"], "MIGRATED")
                    if fault == "source":
                        self.assertFalse(
                            any(call.args[0] == "create" for call in target.run.call_args_list)
                        )
            self.assertEqual((root / "startup.json").read_bytes(), before)
            self.assertEqual(receipt_path(root, stopped).read_bytes(), completion)

    def test_foreign_catalog_and_source_pairs_refuse_before_backup(self):
        from omnis_cli import upgrade as module

        for fault in ("catalog", "alias", "schema", "replay"):
            with (
                self.subTest(fault=fault),
                self.source_upgrade() as (base, root, _stopped, old, _target, bundle),
            ):
                if fault == "catalog":
                    (root / "catalog").mkdir(mode=0o700)
                elif fault == "alias":
                    (root / "catalog").symlink_to(root / "vault", target_is_directory=True)
                elif fault == "schema":
                    old.schema = "0016_provider_models"
                else:
                    old.schema = "0019_agent_runs"
                    write_record(
                        base / "d/omnis/installed.json",
                        {"format": 1, "release": "0.1.2"},
                        replace=True,
                    )
                before = (root / "startup.json").read_bytes()
                with (
                    patch.object(module, "ControlRuntime", return_value=old),
                    patch.object(
                        module, "backup", side_effect=AssertionError("No backup")
                    ) as effect,
                ):
                    with self.assertRaisesRegex(
                        StartError,
                        "UPGRADE_CATALOG_EXISTS"
                        if fault in ("catalog", "alias")
                        else "UPGRADE_SOURCE_INCOMPATIBLE",
                    ):
                        module.upgrade(bundle, base / "snapshot")
                effect.assert_not_called()
                self.assertFalse((base / "d/omnis/upgrade.json").exists())
                self.assertEqual((root / "startup.json").read_bytes(), before)

    def test_upgrade_catalog_identity_cannot_be_replaced_or_adopted(self):
        from uuid import uuid4

        from omnis_cli import upgrade as module
        from omnis_cli.start_runtime import private_identity, provider_settings_overlay
        from omnis_cli.stop_receipt import receipt_path

        with self.source_upgrade() as (base, root, stopped, _old, target, _bundle):
            data = base / "d/omnis"
            saved = data / "source"
            saved.mkdir(mode=0o700)
            for name, path in (
                ("startup.json", root / "startup.json"),
                ("completion.json", receipt_path(root, stopped)),
            ):
                write_record(saved / name, json.loads(path.read_bytes()))
            (root / "catalog").mkdir(mode=0o700)
            target.upgrading = True
            target.upgrade_catalog_identity = private_identity(root / "catalog")
            intent = {
                "state": "STARTING",
                "saved": "source",
                "target_digest": target.digest,
                "catalog_identity": target.upgrade_catalog_identity,
            }
            write_record(data / "upgrade.json", intent)
            provider_settings_overlay(target, {"OMNIS_STATE_ROOT": str(root)})
            (root / "catalog").rename(root / "retained-catalog")
            (root / "catalog").mkdir(mode=0o700)
            with self.assertRaisesRegex(StartError, "VAULT_PATH_IDENTITY_MISMATCH"):
                provider_settings_overlay(target, {"OMNIS_STATE_ROOT": str(root)})
            with self.assertRaisesRegex(StartError, "UPGRADE_INTENT_CHANGED"):
                module.prepare_restart(target, root, stopped, str(uuid4()), intent)
            self.assertEqual(
                (root / "startup.json").read_bytes(), (saved / "startup.json").read_bytes()
            )

    def previous_upgrade(self, base, root, stopped, runtime):
        from uuid import uuid4

        from omnis_cli.compose import ImageReceipt, _put_record
        from omnis_cli.stop_receipt import receipt_path

        data = base / "d/omnis"
        saved = data / ("upgrade-source-" + str(uuid4()))
        saved.mkdir(mode=0o700)
        for name, source in (
            ("startup.json", root / "startup.json"),
            ("completion.json", receipt_path(root, stopped)),
            ("instance.json", root / "instance.json"),
        ):
            value = json.loads(source.read_bytes())
            if name == "startup.json":
                value["release_digest"] = "e" * 64
            elif name == "completion.json":
                value["grant"]["inventory"]["release"] = "e" * 64
            else:
                value.update(release="0.1.0", schema="0016_provider_models")
            write_record(saved / name, value)
        write_record(saved / "installed.json", {"format": 1, "release": "0.1.0"})
        _put_record(
            saved / "image.json",
            ImageReceipt(
                runtime.receipt.project,
                "omnis-control-" + runtime.receipt.project.removeprefix("omnis-local-") + ":0.1.0",
                stopped["image_id"],
                "e" * 64,
                runtime.host,
                runtime.receipt.docker_id,
                "t1-provider-settings",
                release="0.1.0",
            ),
            complete=True,
        )
        intent = {
            "version": 1,
            "state": "COMPLETE",
            "upgrade_id": str(uuid4()),
            "saved": saved.name,
            "backup": str(base / "previous-backup"),
            "target_digest": runtime.digest,
            "source_digest": "e" * 64,
            "old_attempt": stopped["attempt"],
            "instance_id": stopped["instance_id"],
            "restore_probe": str(base / "previous-restore"),
            "job": "a" * 64,
        }
        write_record(data / "upgrade.json", intent)
        return intent

    def test_completed_t1_history_is_preserved_before_next_backup(self):
        for fault in ("none", "active", "uncertain", "unknown", "foreign", "source", "extra"):
            with self.subTest(fault=fault):
                self.completed_t1_history_is_preserved_before_next_backup(fault)

    def completed_t1_history_is_preserved_before_next_backup(self, fault):
        from omnis_cli import upgrade as module

        with self.source_upgrade() as (base, root, stopped, old, _target, bundle):
            data = base / "d/omnis"
            previous = self.previous_upgrade(base, root, stopped, old)
            if fault in ("active", "uncertain", "unknown"):
                previous["state"] = {
                    "active": "STARTING",
                    "uncertain": "UNCERTAIN",
                    "unknown": "FUTURE",
                }[fault]
            elif fault == "foreign":
                previous["target_digest"] = "f" * 64
            elif fault == "source":
                write_record(
                    data / previous["saved"] / "installed.json",
                    {"format": 1, "release": "0.1.1"},
                    replace=True,
                )
            elif fault == "extra":
                previous["unknown"] = True
            write_record(data / "upgrade.json", previous, replace=True)
            before = (data / "upgrade.json").read_bytes()

            def backup(*_args):
                current = json.loads((data / "upgrade.json").read_bytes())
                self.assertEqual((data / current["saved"] / "upgrade.json").read_bytes(), before)
                self.assertEqual(current["state"], "BACKUP_PENDING")
                raise RuntimeError("SOURCE_BACKUP_REACHED")

            with (
                patch.object(module, "ControlRuntime", return_value=old),
                patch.object(module, "backup", side_effect=backup) as effect,
            ):
                if fault == "none":
                    with self.assertRaisesRegex(RuntimeError, "SOURCE_BACKUP_REACHED"):
                        module.upgrade(bundle, base / "snapshot")
                    effect.assert_called_once()
                else:
                    with self.assertRaisesRegex(StartError, "UPGRADE_RECOVERY_REQUIRED"):
                        module.upgrade(bundle, base / "snapshot")
                    effect.assert_not_called()
                    self.assertEqual((data / "upgrade.json").read_bytes(), before)
            self.assertFalse((root / "catalog").exists())

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
        for version in ("0.1.0", "0.1.1"):
            with self.subTest(version=version):
                self.known_preopen_rollback(version)

    def known_preopen_rollback(self, version):
        from omnis_cli import upgrade as module
        from omnis_cli.start_runtime import private_identity

        fixture = cold_fixture.ColdBackupTest()
        with fixture.source() as (base, root, stopped, runtime):
            runtime.check_daemon = lambda: None
            data = base / "d/omnis"
            runtime.release = data / "releases" / version
            runtime.receipt.release = version
            instance = json.loads((root / "instance.json").read_bytes())
            instance["release"] = version
            write_record(root / "instance.json", instance, replace=True)
            saved = data / "source"
            saved.mkdir(mode=0o700)
            for name, record in (
                ("installed.json", {"format": 1, "release": version}),
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
                with patch.object(module, "ControlRuntime", return_value=runtime) as constructor:
                    module.rollback(runtime, data, root, intent)
                self.assertEqual(constructor.call_args.kwargs["version"], version)
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
