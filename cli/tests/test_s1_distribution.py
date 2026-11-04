"""S1 SOURCE packaging/lifecycle guards; no DB, Docker or provider effects."""

import importlib
import io
import json
import os
import runpy
import subprocess
import tomllib
import unittest
from contextlib import redirect_stdout
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock, patch

import test_provider_settings_profile as profiles
from omnis_cli.compose import ImageReceipt, _put_record, _record
from omnis_cli.instance import InvalidInstance, load_instance
from omnis_cli.lifecycle import StartError, read_record, write_record
from omnis_cli.start_runtime import private_identity, provider_settings_overlay
from test_provider_settings_profile import PROFILE

start = importlib.import_module("omnis_cli.start")


class S1DistributionTest(unittest.TestCase):
    def test_normal_bundle_producer_seals_current_wheels_schema_and_dockerfile(self):
        repository = Path(__file__).resolve().parents[2]
        fixture = profiles.ProviderSettingsBundleTest()
        self.addCleanup(fixture.doCleanups)
        bundle = fixture.bundle(version="0.1.2", schema="0019_agent_runs", dependencies=fixture.S0)
        producer = runpy.run_path(str(repository / "ops/build_control_bundle.py"))
        requirements = bundle.bundle / "api/requirements.txt"
        locked = b"synthetic==1 --hash=sha256:" + b"a" * 64 + b"\n"
        requirements.write_bytes(locked)
        web = bundle.bundle / "web"
        import hashlib

        web_manifest = {
            name: hashlib.sha256((web / name).read_bytes()).hexdigest()
            for name in ("index.html", "assets/index-1.js")
        }
        (web / "omnis-web.json").write_text(json.dumps({"version": 1, "files": web_manifest}))
        output = bundle.root / "produced"
        with (
            patch.dict(os.environ, {"OMNIS_UV": "/usr/bin/false"}),
            patch(
                "subprocess.run",
                side_effect=[
                    subprocess.CompletedProcess([], 0, b"uv 0.12.19 (x86_64-unknown-linux-gnu)\n"),
                    subprocess.CompletedProcess([], 0, locked),
                ],
            ),
        ):
            producer["build_bundle"](
                bundle.bundle / "api/omnis_api-0.1.2-py3-none-any.whl",
                bundle.bundle / "cli/omnis_cli-0.1.2-py3-none-any.whl",
                requirements,
                web,
                output,
            )
        manifest = json.loads((output / "release.json").read_bytes())
        self.assertEqual(
            (manifest["release"], manifest["schema"], manifest["format"], manifest["profile"]),
            ("0.1.2", "0019_agent_runs", 3, PROFILE),
        )
        self.assertIn(
            "api/omnis_api-0.1.2-py3-none-any.whl", (output / "ops/Dockerfile").read_text()
        )
        for project in ("api", "cli"):
            for name in ("pyproject.toml", "uv.lock"):
                value = tomllib.loads((repository / project / name).read_text())
                version = (
                    value["project"]["version"]
                    if name == "pyproject.toml"
                    else next(
                        entry["version"]
                        for entry in value["package"]
                        if entry["name"] == "omnis-" + project
                    )
                )
                self.assertEqual(version, "0.1.2")

    def setUp(self):
        self.fixture = profiles.ProviderSettingsProfileTest()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root, self.runtime, self.record = (
            self.fixture.root,
            self.fixture.runtime,
            self.fixture.record,
        )
        self.runtime.receipt.release = "0.1.2"
        self.runtime.schema = "0019_agent_runs"
        (self.root / "catalog").mkdir(mode=0o700)
        self.record["catalog_identity"] = private_identity(self.root / "catalog")
        write_record(self.root / "startup.json", self.record, replace=True)

    def test_overlay_pins_only_supervisor_catalog_and_refuses_replaced_root(self):
        overlay = provider_settings_overlay(self.runtime, {"OMNIS_STATE_ROOT": str(self.root)})
        self.assertEqual(set(overlay["services"]), {"supervisor"})
        supervisor = overlay["services"]["supervisor"]
        self.assertEqual(
            supervisor["environment"],
            {
                "OMNIS_VAULT_DIR": "/vault",
                "OMNIS_VAULT_KEY_DIR": "/vault-key",
                "OMNIS_MODEL_EGRESS_DIR": "/vault",
                "OMNIS_RUN_CATALOG_ROOT": "/catalog",
            },
        )
        self.assertEqual(
            supervisor["volumes"],
            [
                {"type": "bind", "source": str(self.root / name), "target": "/" + name}
                for name in ("vault", "vault-key", "catalog")
            ],
        )
        (self.root / "catalog").rename(self.root / "original")
        (self.root / "catalog").mkdir(mode=0o700)
        with self.assertRaises(StartError):
            provider_settings_overlay(self.runtime, {"OMNIS_STATE_ROOT": str(self.root)})
        (self.root / "catalog").rmdir()
        (self.root / "catalog").symlink_to(self.root / "original", target_is_directory=True)
        with self.assertRaises(ValueError):
            provider_settings_overlay(self.runtime, {"OMNIS_STATE_ROOT": str(self.root)})

    def test_compose_validator_requires_exact_mounts_environment_and_roles(self):
        from test_start_attestation import ProductAttestationTest

        fixture = ProductAttestationTest()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        valid = fixture.config()
        fixture.runtime.receipt.profile = PROFILE
        fixture.runtime.receipt.release = "0.1.2"
        fixture.runtime.schema = "0019_agent_runs"
        supervisor = valid["services"]["supervisor"]
        supervisor["environment"].update(
            OMNIS_VAULT_DIR="/vault",
            OMNIS_VAULT_KEY_DIR="/vault-key",
            OMNIS_MODEL_EGRESS_DIR="/vault",
            OMNIS_RUN_CATALOG_ROOT="/catalog",
        )
        supervisor["volumes"].extend(
            {"type": "bind", "source": str(fixture.root / name), "target": "/" + name}
            for name in ("vault", "vault-key", "catalog")
        )

        def check(config):
            fixture.runtime.compose = Mock(
                return_value=subprocess.CompletedProcess([], 0, json.dumps(config))
            )
            start.validate_config(fixture.runtime, fixture.env)

        check(valid)
        for fault in (
            "missing",
            "readonly",
            "duplicate",
            "api-mount",
            "api-env",
            "native",
            "runtime",
        ):
            with self.subTest(fault=fault):
                invalid = deepcopy(valid)
                owner = invalid["services"]["supervisor"]
                api = invalid["services"]["api"]
                if fault == "missing":
                    owner["volumes"].pop()
                elif fault == "readonly":
                    owner["volumes"][-1]["read_only"] = True
                elif fault == "duplicate":
                    owner["volumes"].append(owner["volumes"][-1])
                elif fault == "api-mount":
                    api["volumes"].append(owner["volumes"][-1])
                elif fault == "api-env":
                    api["environment"]["OMNIS_RUN_CATALOG_ROOT"] = "/catalog"
                elif fault == "native":
                    owner["environment"]["OMNIS_RUNTIME_DIR"] = "/runtime"
                else:
                    invalid["services"]["runtime"] = {}
                with self.assertRaises(StartError):
                    check(invalid)
        fixture.runtime.run.assert_not_called()

    def test_instance_and_image_readers_admit_only_exact_s1_pair(self):
        value = {
            "version": 1,
            "instance_id": self.record["attempt"],
            "release": "0.1.2",
            "schema": "0019_agent_runs",
            "project": self.record["project"],
            "origin": "http://127.0.0.1:48765",
        }
        write_record(self.root / "instance.json", value)
        self.assertEqual(load_instance(self.root).schema, "0019_agent_runs")
        for version, schema in (
            ("0.1.2", "0017_model_removal"),
            ("0.1.1", "0019_agent_runs"),
            ("0.2.0", "0017_model_removal"),
        ):
            write_record(
                self.root / "instance.json",
                {**value, "release": version, "schema": schema},
                replace=True,
            )
            with self.assertRaises(InvalidInstance):
                load_instance(self.root)
        receipt = ImageReceipt(
            self.record["project"],
            "omnis-control-" + "c" * 32 + ":0.1.2",
            self.record["image_id"],
            "a" * 64,
            "unix:///run/docker.sock",
            "fixture-daemon",
            PROFILE,
            release="0.1.2",
        )
        path = self.root / "image.json"
        _put_record(path, receipt, complete=True)
        self.assertEqual(_record(path, "a" * 64, complete=True), receipt)
        path.unlink()
        _put_record(path, replace(receipt, profile=None), complete=True)
        with self.assertRaises(ValueError):
            _record(path, "a" * 64, complete=True)

    def test_s1_backup_refuses_before_cold_helpers_or_destination_writes(self):
        from omnis_cli import backup

        output = self.root / "snapshot"
        with (
            patch.object(
                backup, "readback_stopped", side_effect=AssertionError("No readback/effects")
            ),
            patch.object(backup, "cold_identity", side_effect=AssertionError("No Docker helper")),
            patch.object(backup, "archive", side_effect=AssertionError("No archive")),
        ):
            with self.assertRaisesRegex(StartError, "COLD_CATALOG_UNSUPPORTED"):
                backup.backup(self.runtime, self.root, output)
        self.assertFalse(output.exists())
        self.assertEqual(list(self.root.glob(".cold-*")), [])

    def test_normal_backup_command_refuses_s1_before_lock_writes(self):
        from omnis_cli import backup
        from omnis_cli.main import main

        output = io.StringIO()
        with (
            patch.dict(os.environ, {"XDG_CONFIG_HOME": str(self.root / "absent-config")}),
            patch.object(backup, "ControlRuntime", return_value=self.runtime),
            patch.object(backup, "load_config", return_value=Mock()),
            patch.object(backup, "lifecycle_lock", side_effect=AssertionError("No lock writes")),
            redirect_stdout(output),
        ):
            self.assertEqual(main(["backup", "--output", str(self.root / "snapshot")]), 4)
        self.assertIn("COLD_CATALOG_UNSUPPORTED", output.getvalue())
        self.assertFalse((self.root / "snapshot").exists())

    def test_catalog_identity_is_typed_and_preserved_by_journal_reader(self):
        self.assertIn("catalog_identity", start.vault_fields(self.record))
        start._check_pgdata(self.root, self.record)
        changed = deepcopy(self.record)
        changed["catalog_identity"][0] = True
        with self.assertRaises(StartError):
            start._pgdata_receipt(changed)
        self.assertEqual(read_record(self.root / "startup.json"), self.record)

    def test_stopped_catalog_roundtrip_identity_and_existing_private_frame_limits(self):
        from omnis_cli.control import _stop_binding, _stop_grant
        from omnis_cli.stop import _stopping_record, readback_stopped
        from omnis_cli.stop_receipt import (
            encoded,
            fingerprint,
            receipt_path,
            validate_grant,
            validate_inventory,
        )
        from stopped_fixture import completed_fixture
        from test_stop import private_stop_fixture

        with private_stop_fixture() as (_base, root, _foreign, control, record, runtime):
            runtime.provider_settings = runtime.run_catalog = True
            runtime.schema = "0019_agent_runs"
            runtime.receipt.release = "0.1.2"
            runtime.receipt.profile = PROFILE
            record["format"] = 5
            for name in ("vault", "vault-key", "catalog"):
                (root / name).mkdir(mode=0o700)
                record[name.replace("-", "_") + "_identity"] = private_identity(root / name)
            instance = read_record(root / "instance.json")
            instance.update(release="0.1.2", schema="0019_agent_runs")
            write_record(root / "instance.json", instance, replace=True)
            ready = {
                key: value
                for key, value in record.items()
                if key in start.READY_FIELDS | start.vault_fields(record)
            }
            ready["phase"] = "READY"
            start._ready_record(ready)
            start._bound_instance(runtime, root, control, ready)
            stopping = {**record, "phase": "STOPPING"}
            _stopping_record(stopping)
            with completed_fixture(root, control, record, runtime):
                readback_stopped(runtime, root, control, record)
                grant = read_record(receipt_path(root, record))["grant"]
                self.assertEqual(grant["inventory"]["catalog"], record["catalog_identity"])
                u64 = 18446744073709551615
                inventory = grant["inventory"]
                record["catalog_identity"] = inventory["catalog"] = [
                    u64,
                    u64,
                    4294967294,
                    4294967294,
                    448,
                ]
                record["pgdata_identity"] = inventory["pgdata"] = [u64, u64]
                record["system_id"] = inventory["system_id"] = str(u64)
                record["listener_inode"], record["port"] = u64, 65535
                record["forwarder"].update(pid=2147483647, start_ticks=str(u64))
                inventory["forwarder"].update(
                    pid=2147483647,
                    start_ticks=str(u64),
                    listener=u64,
                    port=65535,
                    identity=fingerprint(record["forwarder"]),
                )
                for key in ("api", "control", "api_lock", "control_lock", "cap"):
                    inventory["ipc"][key] = [u64, u64]
                record["api_socket"] = record["control_socket"] = [u64, u64]
                record.update(
                    stop_expected=9223372036854775806,
                    stop_generation=9223372036854775807,
                    finalized_generation=9223372036854775807,
                    supervisor_epoch=9223372036854775807,
                    docker_id="d" * 128,
                )
                grant.update(
                    generation=record["stop_generation"],
                    owner_epoch=record["supervisor_epoch"],
                    daemon_id=record["docker_id"],
                )
                validate_inventory(inventory, record)
                validate_grant(grant, record, inventory)
                command = {
                    key: value
                    for key, value in grant.items()
                    if key not in {"version", "state", "owner_uuid"}
                }
                command["op"] = "arm_stop"
                _stop_binding(command)
                reply = {"ok": True, "correlation_id": record["stop_command"], "grant": grant}
                _stop_grant(reply, command)
                frame = (
                    json.dumps({"version": 1, "capability": "0" * 64, "command": command}).encode()
                    + b"\n"
                )
                reply_frame = json.dumps(reply).encode() + b"\n"
                self.assertLessEqual(len(encoded(inventory)), 2900)
                self.assertLessEqual(len(encoded(grant)), 3600)
                self.assertLessEqual(len(frame), 4096)
                self.assertLessEqual(len(reply_frame), 4096)
                print(
                    "S1_MAX_IDENTITY_BYTES",
                    len(encoded(inventory)),
                    len(encoded(grant)),
                    len(frame),
                    len(reply_frame),
                )
            # Refusal precedes any Stop effect for a changed pinned private root.
            original = read_record(root / "startup.json")
            (root / "catalog").rename(root / "old-catalog")
            (root / "catalog").mkdir(mode=0o700)
            with self.assertRaises(StartError):
                start._check_pgdata(root, original)
