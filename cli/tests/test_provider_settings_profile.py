"""T1 SOURCE profile/attestor controls; no Docker, installed or browser effects."""

import importlib
import io
import json
import os
import tempfile
import time
import unittest
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from zipfile import ZipFile

from omnis_cli.compose import ImageReceipt, _put_record, _record
from omnis_cli.lifecycle import StartError, read_record, write_record
from omnis_cli.release import ReleaseError, _manifest
from omnis_cli.start import _check_pgdata, service_roles
from omnis_cli.start_runtime import ControlRuntime, private_identity
from runtime_inspect_fixture import container_item, image_item
from test_install import InstallTest

PROFILE = "t1-provider-settings"


class ProviderSettingsProfileTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="t1p-", dir=os.environ["TMPDIR"])
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in ("vault", "vault-key", "control"):
            (self.root / name).mkdir(mode=0o700)
        (self.root / "postgres").mkdir(mode=0o711)
        (self.root / "postgres").chmod(0o711)
        (self.root / "db-password").write_text("a" * 48 + "\n")
        (self.root / "db-password").chmod(0o600)
        self.record = {
            "format": 5,
            "phase": "STARTING",
            "attempt": "11111111-1111-4111-8111-111111111111",
            "project": "omnis-local-" + "c" * 32,
            "release_digest": "a" * 64,
            "image_id": "sha256:" + "d" * 64,
            "docker_host": "unix:///run/docker.sock",
            "docker_id": "fixture-daemon",
            "control_dir": str(self.root / "control"),
            "port": 48765,
            "containers": {},
            "pgdata_identity": [
                (self.root / "postgres").stat().st_dev,
                (self.root / "postgres").stat().st_ino,
            ],
            "vault_identity": private_identity(self.root / "vault"),
            "vault_key_identity": private_identity(self.root / "vault-key"),
        }
        write_record(self.root / "startup.json", self.record)
        self.runtime = ControlRuntime.__new__(ControlRuntime)
        self.runtime.receipt = SimpleNamespace(
            project=self.record["project"], profile=PROFILE, image_id=self.record["image_id"]
        )
        self.runtime.model_test = False
        self.runtime.pg_image = "sha256:" + "e" * 64
        self.runtime.attempt = self.record["attempt"]
        self.runtime.deadline = time.monotonic() + 5
        self.runtime.check_daemon = Mock()
        self.runtime.run = Mock(side_effect=AssertionError("No effects permitted"))

    def test_compose_uses_only_supervisor_private_vault_without_creating_key(self):
        import omnis_cli.start_runtime as source

        self.assertFalse(self.runtime.native)
        self.assertEqual(service_roles(self.record), ("api", "supervisor", "db"))
        overlay = source.provider_settings_overlay(
            self.runtime, {"OMNIS_STATE_ROOT": str(self.root)}
        )
        self.assertEqual(set(overlay["services"]), {"supervisor"})
        supervisor = overlay["services"]["supervisor"]
        self.assertEqual(
            supervisor["environment"],
            {
                "OMNIS_VAULT_DIR": "/vault",
                "OMNIS_VAULT_KEY_DIR": "/vault-key",
                "OMNIS_MODEL_EGRESS_DIR": "/vault",
            },
        )
        self.assertEqual(
            supervisor["volumes"],
            [
                {"type": "bind", "source": str(self.root / "vault"), "target": "/vault"},
                {"type": "bind", "source": str(self.root / "vault-key"), "target": "/vault-key"},
            ],
        )
        self.assertEqual(list((self.root / "vault-key").iterdir()), [])
        self.runtime.receipt.profile = "p4a-settings-offline"
        with self.assertRaises(StartError):
            source.provider_settings_overlay(self.runtime, {"OMNIS_STATE_ROOT": str(self.root)})

    def test_explicit_start_persists_private_paths_before_first_create_without_key(self):
        start = importlib.import_module("omnis_cli.start")
        (self.root / "d/omnis").mkdir(parents=True, mode=0o700)
        root = self.root / "s/omnis"
        self.runtime.receipt.docker_id = "fixture-daemon"
        self.runtime.digest = "c" * 64
        self.runtime.host = "unix:///run/docker.sock"
        self.runtime.ids = Mock(return_value=[])
        self.runtime.inspect = Mock(return_value=None)
        observed = []

        def cut(runtime, env):
            record = read_record(root / "startup.json")
            self.assertEqual(record["format"], 5)
            _check_pgdata(root, record)
            self.assertEqual(list((root / "vault").iterdir()), [])
            self.assertEqual(list((root / "vault-key").iterdir()), [])
            self.assertFalse((root / "native-ipc").exists())
            self.assertFalse((root / "provider").exists())
            observed.append(record)
            raise StartError("SOURCE_CUT_BEFORE_FIRST_CREATE", 3)

        with (
            patch.dict(
                os.environ,
                {
                    "XDG_STATE_HOME": str(self.root / "s"),
                    "XDG_DATA_HOME": str(self.root / "d"),
                    "XDG_RUNTIME_DIR": "",
                    "XDG_CONFIG_HOME": str(self.root / "c"),
                },
            ),
            patch.object(start, "ControlRuntime", return_value=self.runtime),
            patch.object(start, "preflight_port"),
            patch.object(start, "validate_config", side_effect=cut),
            patch.object(start, "cleanup_attempt", return_value=[]),
        ):
            code, result = start.start_result(48765)
        self.assertEqual((code, result["reason"]), (3, "SOURCE_CUT_BEFORE_FIRST_CREATE"))
        self.assertEqual(len(observed), 1)
        self.runtime.run.assert_not_called()

    def test_paths_are_bound_to_journal_and_pending_lock_survives_checks(self):
        (self.root / "vault/vault.pending").write_text("retained lock")
        _check_pgdata(self.root, self.record)
        self.assertEqual((self.root / "vault/vault.pending").read_text(), "retained lock")
        (self.root / "vault-key").rename(self.root / "original-key-dir")
        (self.root / "vault-key").mkdir(mode=0o700)
        with self.assertRaises(StartError):
            _check_pgdata(self.root, self.record)

    def test_rendered_compose_accepts_only_supervisor_mounts_and_closed_profile(self):
        import subprocess

        import test_start_attestation as attestation
        from omnis_cli.start import validate_config

        fixture = attestation.ProductAttestationTest()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        valid = fixture.config()
        fixture.runtime.receipt.profile = PROFILE
        supervisor = valid["services"]["supervisor"]
        supervisor["environment"].update(
            OMNIS_VAULT_DIR="/vault",
            OMNIS_VAULT_KEY_DIR="/vault-key",
            OMNIS_MODEL_EGRESS_DIR="/vault",
        )
        supervisor["volumes"].extend(
            {"type": "bind", "source": str(fixture.root / name), "target": "/" + name}
            for name in ("vault", "vault-key")
        )
        fixture.runtime.compose = Mock(
            return_value=subprocess.CompletedProcess([], 0, json.dumps(valid))
        )
        validate_config(fixture.runtime, fixture.env)
        valid["services"]["api"]["volumes"].append(supervisor["volumes"][-1])
        fixture.runtime.compose.return_value = subprocess.CompletedProcess([], 0, json.dumps(valid))
        with self.assertRaises(StartError):
            validate_config(fixture.runtime, fixture.env)
        valid["services"]["api"]["volumes"].pop()
        fixture.runtime.receipt.profile = None
        fixture.runtime.compose.return_value = subprocess.CompletedProcess([], 0, json.dumps(valid))
        with self.assertRaises(StartError):
            validate_config(fixture.runtime, fixture.env)
        fixture.runtime.run.assert_not_called()

    def test_runtime_attestor_accepts_owner_and_denies_key_on_api_or_missing_mount(self):
        cid = "f" * 64
        control = self.root / "control"
        candidate = container_item(self.runtime, "supervisor", cid, self.root, control, 48765)
        # Producer fixture predates T1; construct the explicit new wire shape.
        candidate["Config"]["Env"] = [
            value
            for value in candidate["Config"]["Env"]
            if not value.startswith("OMNIS_RUNTIME_DIR=")
        ]
        candidate["Mounts"] = [
            row for row in candidate["Mounts"] if row["Destination"] != "/runtime"
        ]
        candidate["Config"]["Env"] += [
            "OMNIS_VAULT_DIR=/vault",
            "OMNIS_VAULT_KEY_DIR=/vault-key",
            "OMNIS_MODEL_EGRESS_DIR=/vault",
        ]
        for name in ("vault", "vault-key"):
            candidate["Mounts"].append(
                {
                    "Type": "bind",
                    "Source": str(self.root / name),
                    "Destination": "/" + name,
                    "RW": True,
                    "Propagation": "rprivate",
                }
            )
        self.runtime.ids = Mock(return_value=[cid])
        self.runtime.network = Mock(return_value="1" * 64)

        def inspect(kind, ident):
            return image_item(self.runtime, "supervisor") if kind == "image" else candidate

        self.runtime.inspect = Mock(side_effect=inspect)
        original = deepcopy(candidate)
        self.assertEqual(
            self.runtime.attest(cid, "supervisor", self.root, control, 48765), candidate
        )
        candidate["Mounts"].pop()
        with self.assertRaises(StartError):
            self.runtime.attest(cid, "supervisor", self.root, control, 48765)
        candidate = container_item(self.runtime, "api", cid, self.root, control, 48765)
        candidate["Mounts"].append(original["Mounts"][-1])
        with self.assertRaises(StartError):
            self.runtime.attest(cid, "api", self.root, control, 48765)
        self.runtime.run.assert_not_called()

    def test_new_image_receipt_has_profile_but_never_runtime_owner(self):
        receipt = ImageReceipt(
            "omnis-local-" + "a" * 32,
            "omnis-control-" + "a" * 32 + ":0.1.0",
            "sha256:" + "b" * 64,
            "c" * 64,
            "unix:///run/docker.sock",
            "fixture-daemon",
            PROFILE,
        )
        path = self.root / "image.json"
        _put_record(path, receipt, complete=True)
        raw = read_record(path)
        self.assertEqual(raw["format"], 3)
        self.assertNotIn("runtime_tag", raw)
        self.assertEqual(_record(path, "c" * 64, complete=True), receipt)
        raw["runtime_tag"] = "not-permitted"
        path.write_text(json.dumps(raw))
        with self.assertRaises(ValueError):
            _record(path, "c" * 64, complete=True)

    def test_stopped_reader_keeps_vault_key_and_pending_lock_but_denies_path_drift(self):
        from omnis_cli.stop import readback_stopped
        from stopped_fixture import completed_fixture
        from test_stop import private_stop_fixture

        with private_stop_fixture() as (_base, root, _foreign, control, record, runtime):
            record["format"] = 5
            runtime.provider_settings = True
            runtime.receipt.profile = PROFILE
            for name, field in (("vault", "vault_identity"), ("vault-key", "vault_key_identity")):
                (root / name).mkdir(mode=0o700)
                record[field] = private_identity(root / name)
            pending = root / "vault/vault.pending"
            pending.write_bytes(b"retained synthetic lock")
            pending.chmod(0o600)
            before = (pending.stat().st_ino, pending.read_bytes())
            with completed_fixture(root, control, record, runtime):
                readback_stopped(runtime, root, control, record)
                self.assertEqual((pending.stat().st_ino, pending.read_bytes()), before)
                (root / "vault-key").rename(root / "old-key")
                (root / "vault-key").mkdir(mode=0o700)
                with self.assertRaises(StartError):
                    readback_stopped(runtime, root, control, record)


class ProviderSettingsBundleTest(unittest.TestCase):
    def test_format3_requires_api_key_modules_migration_and_crypto_closure(self):
        import hashlib

        fixture = InstallTest()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        content = io.BytesIO()
        with ZipFile(content, "w") as wheel:
            for name in (
                "omnis/modules/settings/provider_key_models.py",
                "omnis/modules/settings/provider_key_routes.py",
                "omnis/modules/settings/provider_key_service.py",
                "omnis/modules/settings/provider_vault.py",
                "omnis/migrations/versions/0014_provider_settings.py",
                "omnis/migrations/versions/0015_model_test_v2.py",
                "omnis/modules/runs/model_test_runtime.py",
                "omnis/modules/runs/model_test_contract.py",
                "omnis/modules/runs/model_test_store.py",
                "omnis/supervisor/model_sender.py",
            ):
                wheel.writestr(name, "# SOURCE synthetic closure\n")
            wheel.writestr(
                "omnis_api-0.1.0.dist-info/METADATA",
                "Requires-Dist: cryptography==50.0.1\nRequires-Dist: openai==2.24.0\nRequires-Dist: httpx==0.28.1\nRequires-Dist: httpcore==1.0.9\n",
            )
        fixture.manifest.update(format=3, profile=PROFILE)
        name = "api/omnis_api-0.1.0-py3-none-any.whl"
        (fixture.bundle / name).write_bytes(content.getvalue())
        fixture.manifest["files"][name] = hashlib.sha256(content.getvalue()).hexdigest()
        fixture.write_manifest()
        _manifest(fixture.bundle)
        fixture.manifest["profile"] = "p4a-codex-auth"
        fixture.write_manifest()
        with self.assertRaises(ReleaseError):
            _manifest(fixture.bundle)
        fixture.manifest["profile"] = PROFILE
        (fixture.bundle / name).write_bytes(b"not a wheel")
        fixture.manifest["files"][name] = hashlib.sha256(b"not a wheel").hexdigest()
        fixture.write_manifest()
        with self.assertRaises(ReleaseError):
            _manifest(fixture.bundle)
