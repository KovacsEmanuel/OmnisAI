"""Four-role SOURCE topology; synthetic inspect, no Docker/native execution."""

import json
import subprocess
from copy import deepcopy
from unittest.mock import Mock

from omnis_cli.lifecycle import StartError, write_record
from omnis_cli.start import validate_config
from omnis_cli.start_runtime import ControlRuntime
from test_start_attestation import ProductAttestationTest


class SettingsTopologyTest(ProductAttestationTest):
    def native(self):
        self.runtime.receipt.profile = "p4a-settings-offline"
        self.runtime.receipt.runtime_image_id = "sha256:" + "2" * 64
        self.runtime.release = self.root / "release"
        for name in ("native-ipc", "provider"):
            (self.root / name).mkdir(mode=0o700)
        info = (self.root / "provider").stat()
        ipc = (self.root / "native-ipc").stat()
        write_record(
            self.root / "startup.json",
            {
                "format": 3,
                "provider_identity": [info.st_dev, info.st_ino, info.st_uid, info.st_gid, 0o700],
                "runtime_dir_identity": [ipc.st_dev, ipc.st_ino, ipc.st_uid, ipc.st_gid, 0o700],
            },
        )

    def test_four_role_start_receipt_and_stop_inventory(self):
        from omnis_cli.start import runtime_ipc
        from omnis_cli.stop_owner import prepare_stop_inventory
        from omnis_cli.stop_receipt import validate_inventory
        from stop_owner_fixture import Fixture

        self.assertTrue(callable(runtime_ipc))
        fixture = Fixture(native=True)
        try:
            inventory = prepare_stop_inventory(
                fixture.runtime, fixture.root, fixture.control, fixture.record
            )
            self.assertEqual(inventory["version"], 2)
            self.assertEqual(
                [x["role"] for x in inventory["containers"]], ["api", "supervisor", "runtime", "db"]
            )
            validate_inventory(inventory, fixture.record)
            from unittest.mock import patch

            from omnis_cli.stop_owner import run_stop_owner, verify_stop_completion
            from omnis_cli.stop_receipt import completed_receipt, encoded, receipt_path
            from stop_owner_fixture import owner_test_argv

            original = subprocess.Popen
            grant = fixture.grant(inventory)
            with (
                fixture.original_locks() as (locks, guards),
                patch(
                    "omnis_cli.stop_owner.subprocess.Popen",
                    side_effect=lambda argv, original=original, **kw: original(
                        owner_test_argv(argv), **kw
                    ),
                ),
            ):
                run_stop_owner(
                    fixture.runtime,
                    fixture.root,
                    fixture.control,
                    fixture.record,
                    grant,
                    lock_fds=locks,
                    guard_fds=guards,
                )
            verify_stop_completion(fixture.runtime, fixture.root, fixture.control, fixture.record)
            completed = completed_receipt(receipt_path(fixture.root, fixture.record), grant)
            self.assertEqual(completed["version"], 2)
            self.assertEqual(
                [x["stage"] for x in completed["completed"]],
                [
                    "forwarder",
                    "api.stop",
                    "api.rm",
                    "supervisor.stop",
                    "supervisor.rm",
                    "runtime.stop",
                    "runtime.rm",
                    "db.stop",
                    "db.rm",
                    "network.rm",
                    "ipc",
                ],
            )
            self.assertTrue((fixture.root / "provider").is_dir())
            self.assertLessEqual(len(encoded(inventory)), 2900)
            self.assertLessEqual(len(encoded(grant)), 3600)
        finally:
            fixture.close()

    def test_native_inventory_and_control_exact_frame_budgets(self):
        from omnis_cli.control import _stop_binding, _stop_grant
        from omnis_cli.stop_owner import prepare_stop_inventory
        from omnis_cli.stop_receipt import encoded, fingerprint, validate_grant, validate_inventory
        from stop_owner_fixture import Fixture

        fixture = Fixture(native=True)
        try:
            inventory = prepare_stop_inventory(
                fixture.runtime, fixture.root, fixture.control, fixture.record
            )
            record = deepcopy(fixture.record)
            maximum = deepcopy(inventory)
            u64 = 18446744073709551615
            record["pgdata_identity"] = maximum["pgdata"] = [u64, u64]
            record["system_id"] = maximum["system_id"] = str(u64)
            record["listener_inode"] = u64
            record["port"] = 65535
            record["forwarder"].update(pid=2147483647, start_ticks=str(u64))
            maximum["forwarder"].update(
                pid=2147483647,
                start_ticks=str(u64),
                listener=u64,
                port=65535,
                identity=fingerprint(record["forwarder"]),
            )
            for key in ("api", "control", "api_lock", "control_lock", "cap"):
                maximum["ipc"][key] = [u64, u64]
            record["api_socket"] = record["control_socket"] = [u64, u64]
            for key, field in (
                ("provider", "provider_identity"),
                ("runtime_dir", "runtime_dir_identity"),
            ):
                maximum[key] = record[field] = [u64, u64, 4294967294, 4294967294, 448]
            for key in ("socket", "lock", "file"):
                maximum["runtime_ipc"][key] = [u64, u64]
            record["runtime_ipc"] = deepcopy(maximum["runtime_ipc"])
            record.update(
                stop_generation=9223372036854775807,
                finalized_generation=9223372036854775807,
                stop_expected=9223372036854775806,
                supervisor_epoch=9223372036854775807,
                docker_id="d" * 128,
            )
            grant = fixture.grant(maximum)
            grant.update(
                generation=record["stop_generation"],
                owner_epoch=record["supervisor_epoch"],
                daemon_id=record["docker_id"],
            )
            validate_inventory(maximum, record)
            validate_grant(grant, record, maximum)
            command = {
                k: v for k, v in grant.items() if k not in {"version", "state", "owner_uuid"}
            }
            command["op"] = "arm_stop"
            _stop_binding(command)
            _stop_grant(
                {"ok": True, "correlation_id": record["stop_command"], "grant": grant}, command
            )
            # Exact inventory cap, using its existing variable-width ticks field;
            # no new extension field, codec or larger protocol limit.
            pad = 2900 - len(encoded(maximum))
            record["forwarder"]["start_ticks"] += "0" * pad
            maximum["forwarder"]["start_ticks"] = record["forwarder"]["start_ticks"]
            maximum["forwarder"]["identity"] = fingerprint(record["forwarder"])
            self.assertEqual(len(encoded(maximum)), 2900)
            validate_inventory(maximum, record)
            record["forwarder"]["start_ticks"] += "0"
            maximum["forwarder"]["start_ticks"] = record["forwarder"]["start_ticks"]
            maximum["forwarder"]["identity"] = fingerprint(record["forwarder"])
            self.assertEqual(len(encoded(maximum)), 2901)
            with self.assertRaises(StartError):
                validate_inventory(maximum, record)
        finally:
            fixture.close()

    def test_native_stop_denies_replacement_lost_ack_and_nondrain(self):
        from unittest.mock import patch

        from omnis_cli.stop_owner import (
            prepare_stop_inventory,
            run_stop_owner,
            verify_stop_completion,
        )
        from stop_owner_fixture import Fixture, owner_test_argv

        for fault in ("provider", "lost_ack", "nondrain"):
            with self.subTest(fault=fault):
                fixture = Fixture(native=True)
                try:
                    if fault == "provider":
                        (fixture.root / "provider").rename(fixture.root / "retained-provider")
                        (fixture.root / "provider").mkdir(mode=0o700)
                        with self.assertRaises(StartError):
                            prepare_stop_inventory(
                                fixture.runtime, fixture.root, fixture.control, fixture.record
                            )
                        self.assertFalse(
                            any(r.startswith(("POST", "DELETE")) for r in fixture.requests)
                        )
                        continue
                    inventory = prepare_stop_inventory(
                        fixture.runtime, fixture.root, fixture.control, fixture.record
                    )
                    fixture.lost_ack = fault == "lost_ack"
                    fixture.noop = fault == "nondrain"
                    original = subprocess.Popen
                    with (
                        fixture.original_locks() as (locks, guards),
                        patch(
                            "omnis_cli.stop_owner.subprocess.Popen",
                            side_effect=lambda argv, original=original, **kw: original(
                                owner_test_argv(argv), **kw
                            ),
                        ),
                    ):
                        with self.assertRaises(StartError):
                            run_stop_owner(
                                fixture.runtime,
                                fixture.root,
                                fixture.control,
                                fixture.record,
                                fixture.grant(inventory),
                                lock_fds=locks,
                                guard_fds=guards,
                            )
                    with self.assertRaises(StartError):
                        verify_stop_completion(
                            fixture.runtime, fixture.root, fixture.control, fixture.record
                        )
                    self.assertIn(fixture.ids["db"], fixture.items)
                    self.assertIn(fixture.ids["runtime"], fixture.items)
                finally:
                    fixture.close()

    def test_sealed_native_compose_and_full_attestation(self):
        self.native()
        from omnis_cli.start import environment

        self.env = environment(self.runtime, self.root, self.control, self.port)
        self.runtime.run = Mock(return_value=subprocess.CompletedProcess([], 0, "", ""))
        ControlRuntime.compose(self.runtime, self.env, "config", "--format", "json")
        call = self.runtime.run.call_args
        self.assertIn("-", call.args)
        overlay = json.loads(call.kwargs["stdin"])
        config = self.config()
        config["services"]["supervisor"]["environment"].update(
            overlay["services"]["supervisor"]["environment"]
        )
        # Synthetic inspect producer already includes the native supervisor bind.
        config["services"]["runtime"] = overlay["services"]["runtime"]
        self.runtime.compose = Mock(
            return_value=subprocess.CompletedProcess([], 0, json.dumps(config), "")
        )
        validate_config(self.runtime, self.env)
        for mutation in ("network_mode", "init", "image", "volumes", "environment"):
            bad = deepcopy(config)
            bad["services"]["runtime"][mutation] = {
                "network_mode": "host",
                "init": True,
                "image": self.runtime.receipt.image_id,
                "volumes": [],
                "environment": {"OMNIS_DATABASE_URL": "forbidden"},
            }[mutation]
            self.runtime.compose.return_value.stdout = json.dumps(bad)
            with self.assertRaises(StartError):
                validate_config(self.runtime, self.env)
        item = self.item("supervisor")

        native = deepcopy(item)
        native["Config"]["Labels"]["com.docker.compose.service"] = "runtime"
        native["Config"]["Cmd"] = [
            "/opt/hermes/venv/bin/python",
            "-I",
            "-m",
            "omnis_hermes.runtime_host",
        ]
        native["Config"]["Env"] = ["PATH=/synthetic/image/bin", "OMNIS_RUNTIME_DIR=/runtime"]
        native["Image"] = self.runtime.receipt.runtime_image_id
        native["HostConfig"]["NetworkMode"] = "none"
        native["NetworkSettings"]["Networks"] = {"none": {"NetworkID": "3" * 64}}
        native["Mounts"] = [
            item["Mounts"][-1],
            {
                "Type": "bind",
                "Source": str(self.root / "provider"),
                "Destination": "/state/provider",
                "RW": True,
                "Propagation": "rprivate",
            },
        ]
        self.runtime.inspect = Mock(
            side_effect=lambda kind, ident: (
                {
                    "Id": self.runtime.receipt.runtime_image_id,
                    "Config": {"Env": ["PATH=/synthetic/image/bin"]},
                }
                if kind == "image"
                else self.network
                if kind == "network"
                else native
            )
        )
        self.assertEqual(
            self.runtime.attest(self.cid, "runtime", self.root, self.control, self.port), native
        )
        (self.root / "provider").rename(self.root / "old-provider")
        (self.root / "provider").mkdir(mode=0o700)
        with self.assertRaises(StartError):
            self.runtime.attest(self.cid, "runtime", self.root, self.control, self.port)
