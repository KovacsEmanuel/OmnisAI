"""Four-role SOURCE topology; synthetic inspect, no Docker/native execution."""

import json
import subprocess
from copy import deepcopy
from unittest.mock import Mock

from omnis_cli.lifecycle import StartError, write_record
from omnis_cli.start import validate_config
from omnis_cli.start_runtime import ControlRuntime
from test_start_attestation import ProductAttestationTest


def test_emergency_auth_identity_before_any_signal():
    import importlib
    import os
    import socket
    from contextlib import ExitStack
    from unittest.mock import patch

    from omnis_cli.lifecycle import process_identity
    from omnis_cli.start import _ready_record, auth_listener, runtime_ipc
    from omnis_cli.start_runtime import private_identity
    from test_stop import private_stop_fixture

    stop = importlib.import_module("omnis_cli.stop")

    class SignalBoundary(Exception):
        pass

    with (
        private_stop_fixture() as (_, root, _, control, record, runtime),
        ExitStack() as stack,
    ):
        for field in (
            "stop_command",
            "stop_expected",
            "stop_generation",
            "finalize_command",
            "finalized_generation",
            "teardown_completed",
        ):
            del record[field]
        for leaf in ("provider", "native-ipc"):
            (root / leaf).mkdir(mode=0o700)
        native = root / "native-ipc"
        (native / "runtime.lock").touch(mode=0o600)
        write_record(
            native / "runtime.boot",
            {
                "version": 1,
                "boot": "11111111-1111-4111-8111-111111111111",
                "capability": "a" * 64,
            },
        )
        for leaf in ("runtime.sock", "auth-egress.sock"):
            sock = stack.enter_context(
                socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            )
            sock.bind(str(native / leaf))
            (native / leaf).chmod(0o600)
            sock.listen()
        tcp = stack.enter_context(socket.socket())
        tcp.bind(("127.0.0.1", record["port"]))
        tcp.listen()
        record.update(
            format=4,
            phase="READY",
            runtime_image_id="sha256:" + "5" * 64,
            provider_identity=private_identity(root / "provider"),
            runtime_dir_identity=private_identity(native),
            runtime_ipc=runtime_ipc(root),
            forwarder=process_identity(os.getpid()),
            listener_inode=os.fstat(tcp.fileno()).st_ino,
        )
        record["containers"]["runtime"] = "4" * 64
        exact = auth_listener(root, record["forwarder"])
        runtime.native = True
        runtime.receipt.profile = "p4a-codex-auth"
        runtime.receipt.runtime_image_id = record["runtime_image_id"]
        runtime.ids = lambda: list(record["containers"].values())
        runtime.attest = lambda *a: {}
        runtime.network = lambda *a: {"Id": "d" * 64}
        for case in ("matching", "filesystem", "kernel"):
            record["auth"] = deepcopy(exact)
            if case == "filesystem":
                record["auth"]["socket"][1] += 1
            if case == "kernel":
                record["auth"]["listener"] += 1
            _ready_record(record)
            signals = []

            def sink(fd, sig):
                signals.append(int(sig))
                raise SignalBoundary()

            with patch.object(stop.signal, "pidfd_send_signal", side_effect=sink):
                try:
                    stop._emergency_inventory(runtime, root, control, record)
                    stop._emergency_drain(runtime, root, control, record)
                except SignalBoundary:
                    pass
                except StartError as error:
                    assert case != "matching"
                    assert str(error) == "AUTH_IDENTITY_MISMATCH"
            assert signals == ([15] if case == "matching" else [])


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
                "provider_identity": [
                    info.st_dev,
                    info.st_ino,
                    info.st_uid,
                    info.st_gid,
                    0o700,
                ],
                "runtime_dir_identity": [
                    ipc.st_dev,
                    ipc.st_ino,
                    ipc.st_uid,
                    ipc.st_gid,
                    0o700,
                ],
            },
        )

    def test_four_role_start_receipt_and_stop_inventory(self):
        from omnis_cli.start import runtime_ipc
        from omnis_cli.stop_owner import prepare_stop_inventory
        from omnis_cli.stop_receipt import validate_inventory
        from stop_owner_fixture import Fixture

        self.assertTrue(callable(runtime_ipc))
        fixture = Fixture(native=True, auth=True)
        try:
            inventory = prepare_stop_inventory(
                fixture.runtime, fixture.root, fixture.control, fixture.record
            )
            self.assertEqual(inventory["version"], 3)
            self.assertEqual(
                [x["role"] for x in inventory["containers"]],
                ["api", "supervisor", "runtime", "db"],
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
            verify_stop_completion(
                fixture.runtime, fixture.root, fixture.control, fixture.record
            )
            completed = completed_receipt(
                receipt_path(fixture.root, fixture.record), grant
            )
            self.assertEqual(completed["version"], 3)
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
            from uuid import uuid4

            from omnis_cli.restart import prepare_restart
            from omnis_cli.stop import _publish_stopped
            from omnis_cli.stop_owner import _view

            # Continue on the same synthetic Engine transport, never Docker CLI.
            fixture.runtime = _view(fixture.runtime)
            original_provider = fixture.record["provider_identity"]
            _publish_stopped(
                fixture.runtime,
                fixture.root,
                fixture.control,
                fixture.root / "startup.json",
                fixture.record,
            )
            restart = prepare_restart(
                fixture.runtime,
                fixture.root,
                fixture.control,
                fixture.record,
                str(uuid4()),
            )
            self.assertEqual(restart["request"]["grant"]["inventory"]["version"], 3)
            self.assertFalse((fixture.root / "native-ipc/auth-egress.sock").exists())
            self.assertEqual(fixture.record["provider_identity"], original_provider)
        finally:
            fixture.close()

    def test_native_inventory_and_control_exact_frame_budgets(self):
        from omnis_cli.control import _stop_binding, _stop_grant
        from omnis_cli.stop_owner import prepare_stop_inventory
        from omnis_cli.stop_receipt import (
            encoded,
            fingerprint,
            validate_grant,
            validate_inventory,
        )
        from stop_owner_fixture import Fixture

        fixture = Fixture(native=True, auth=True)
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
            record["format"] = 4
            record["auth"] = {"socket": [u64, u64], "listener": u64}
            maximum["version"] = 3
            maximum["forwarder"]["auth"] = deepcopy(record["auth"])
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
                k: v
                for k, v in grant.items()
                if k not in {"version", "state", "owner_uuid"}
            }
            command["op"] = "arm_stop"
            _stop_binding(command)
            frame = (
                json.dumps(
                    {"version": 1, "capability": "0" * 64, "command": command}
                ).encode()
                + b"\n"
            )
            self.assertLessEqual(len(frame), 4096)
            self.assertLessEqual(len(encoded(maximum)), 2900)
            print(
                "AUTH_PRODUCER_SIZES",
                len(encoded(maximum)),
                len(encoded(grant)),
                len(frame),
            )
            reply_frame = (
                json.dumps(
                    {
                        "ok": True,
                        "correlation_id": record["stop_command"],
                        "grant": grant,
                    }
                ).encode()
                + b"\n"
            )
            self.assertLessEqual(len(reply_frame), 4096)
            print("AUTH_REPLY_FRAME_BYTES", len(reply_frame))
            _stop_grant(
                {"ok": True, "correlation_id": record["stop_command"], "grant": grant},
                command,
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

    def test_runtime_boot_digest_binds_raw_bytes(self):
        from omnis_cli.start import runtime_ipc
        from stop_owner_fixture import Fixture

        fixture = Fixture(native=True)
        try:
            before = runtime_ipc(fixture.root)
            path = fixture.root / "native-ipc/runtime.boot"
            path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
            self.assertNotEqual(runtime_ipc(fixture.root)["digest"], before["digest"])
        finally:
            fixture.close()

    def test_runtime_wait_uses_published_socket_before_boot_metadata(self):
        from omnis_cli.start import runtime_ipc

        self.native()
        directory = self.root / "native-ipc"
        (directory / "runtime.lock").touch(mode=0o600)
        (directory / "runtime.boot").touch(mode=0o600)  # Host still publishing.
        with self.assertRaises(FileNotFoundError):
            runtime_ipc(self.root)

    def test_cleanup_refuses_changed_native_boot_before_unlink(self):
        import socket

        from omnis_cli.lifecycle import cleanup_startup_ipc
        from omnis_cli.start import runtime_ipc

        self.native()
        directory = self.root / "native-ipc"
        (directory / "runtime.lock").touch(mode=0o600)
        write_record(
            directory / "runtime.boot",
            {
                "version": 1,
                "boot": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
                "capability": "a" * 64,
            },
        )
        sock = socket.socket(socket.AF_UNIX)
        sock.bind(str(directory / "runtime.sock"))
        (directory / "runtime.sock").chmod(0o600)
        sock.close()
        expected = runtime_ipc(self.root)
        record = json.loads((self.root / "startup.json").read_text())
        record["runtime_ipc"] = expected
        write_record(self.root / "startup.json", record, replace=True)
        (directory / "runtime.boot").unlink()
        write_record(
            directory / "runtime.boot",
            {
                "version": 1,
                "boot": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
                "capability": "b" * 64,
            },
        )
        self.assertTrue(cleanup_startup_ipc(self.root, self.control, native=True))
        self.assertTrue((directory / "runtime.sock").exists())
        self.assertTrue((directory / "runtime.boot").exists())

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
                        (fixture.root / "provider").rename(
                            fixture.root / "retained-provider"
                        )
                        (fixture.root / "provider").mkdir(mode=0o700)
                        with self.assertRaises(StartError):
                            prepare_stop_inventory(
                                fixture.runtime,
                                fixture.root,
                                fixture.control,
                                fixture.record,
                            )
                        self.assertFalse(
                            any(
                                r.startswith(("POST", "DELETE"))
                                for r in fixture.requests
                            )
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
                            fixture.runtime,
                            fixture.root,
                            fixture.control,
                            fixture.record,
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
        # Compose 2.32.4 renders this explicit null even when omitted by the
        # producer. SOURCE regression; real installed renderer is checked separately.
        config["services"]["runtime"]["entrypoint"] = None
        self.runtime.compose = Mock(
            return_value=subprocess.CompletedProcess([], 0, json.dumps(config), "")
        )
        validate_config(self.runtime, self.env)
        for entrypoint in ("/bin/sh", ["/bin/sh"], False, []):
            with self.subTest(entrypoint=entrypoint):
                bad = deepcopy(config)
                bad["services"]["runtime"]["entrypoint"] = entrypoint
                self.runtime.compose.return_value.stdout = json.dumps(bad)
                with self.assertRaisesRegex(StartError, "^COMPOSE_RUNTIME_INVALID$"):
                    validate_config(self.runtime, self.env)
        for mutation in (
            "network_mode",
            "init",
            "image",
            "volumes",
            "environment",
            "command",
        ):
            bad = deepcopy(config)
            bad["services"]["runtime"][mutation] = {
                "network_mode": "host",
                "init": True,
                "image": self.runtime.receipt.image_id,
                "volumes": [],
                "environment": {"OMNIS_DATABASE_URL": "forbidden"},
                "command": ["sleep", "99"],
            }[mutation]
            self.runtime.compose.return_value.stdout = json.dumps(bad)
            with self.assertRaisesRegex(StartError, "^COMPOSE_RUNTIME_INVALID$"):
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
        native["Config"]["Env"] = [
            "PATH=/synthetic/image/bin",
            "OMNIS_RUNTIME_DIR=/runtime",
        ]
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
            self.runtime.attest(
                self.cid, "runtime", self.root, self.control, self.port
            ),
            native,
        )
        valid = deepcopy(native)
        for section, key, value in (
            ("HostConfig", "Init", True),
            ("HostConfig", "NetworkMode", "host"),
            ("HostConfig", "ReadonlyRootfs", False),
            ("Config", "User", "0:0"),
            ("Config", "Cmd", ["sleep", "99"]),
            ("Config", "Env", ["OMNIS_DATABASE_URL=forbidden"]),
            (
                "NetworkSettings",
                "Networks",
                {self.runtime.receipt.project + "_control": {}},
            ),
        ):
            native[section][key] = value
            with self.assertRaises(StartError):
                self.runtime.attest(
                    self.cid, "runtime", self.root, self.control, self.port
                )
            native = deepcopy(valid)
        native["Image"] = self.runtime.receipt.image_id
        with self.assertRaises(StartError):
            self.runtime.attest(self.cid, "runtime", self.root, self.control, self.port)
        native = deepcopy(valid)
        native["Mounts"].append(
            {
                "Type": "bind",
                "Source": str(self.control),
                "Destination": "/control",
                "RW": True,
                "Propagation": "rprivate",
            }
        )
        with self.assertRaises(StartError):
            self.runtime.attest(self.cid, "runtime", self.root, self.control, self.port)
        native = deepcopy(valid)
        (self.root / "provider").rename(self.root / "old-provider")
        (self.root / "provider").mkdir(mode=0o700)
        with self.assertRaises(StartError):
            self.runtime.attest(self.cid, "runtime", self.root, self.control, self.port)
