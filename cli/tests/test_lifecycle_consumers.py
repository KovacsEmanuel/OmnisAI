"""Actual consumer/owner processes and crash durability; synthetic Engine/DB only."""

import importlib
import json
import os
import select
import signal
import subprocess
import threading
import unittest
from unittest.mock import patch
from uuid import uuid4

from omnis_cli.lifecycle import read_record, write_record
from omnis_cli.stop_owner import _view
from omnis_cli.stop_receipt import receipt_path
from stop_owner_fixture import Fixture, owner_test_argv
from stopped_fixture import completed_fixture
from test_stop import private_stop_fixture

start = importlib.import_module("omnis_cli.start")
stop = importlib.import_module("omnis_cli.stop")


class LifecycleConsumerProcessTest(unittest.TestCase):
    def test_real_stop_client_owner_and_repeat_use_completed_receipt(self):
        fixture = Fixture()
        original = subprocess.Popen
        operations, failures = [], []
        try:
            ready = {
                key: value for key, value in fixture.record.items() if key in start.READY_FIELDS
            }
            ready["phase"] = "READY"
            write_record(fixture.root / "startup.json", ready, replace=True)
            view = _view(fixture.runtime)
            peer = fixture.sockets["control"]
            peer.settimeout(5)

            def status(record, generation=1):
                return dict(
                    instance_id=record["instance_id"],
                    generation=generation,
                    admission_open=generation == 1,
                    shutdown_command_id=None if generation == 1 else record["stop_command"],
                    quiesced_generation=None if generation == 1 else generation,
                    supervisor_epoch=1,
                    supervisor_ready=True,
                    shutdown_finalized=generation == 2,
                    assessment_ready=False,
                    dashboard_ready=False,
                )

            def serve():
                try:
                    for _ in range(5):
                        connection, _address = peer.accept()
                        with connection:
                            connection.settimeout(5)
                            raw = bytearray()
                            while not raw.endswith(b"\n") and len(raw) <= 4096:
                                chunk = connection.recv(4097 - len(raw))
                                if not chunk:
                                    raise AssertionError("missing control frame")
                                raw.extend(chunk)
                            request = json.loads(raw)
                            self.assertEqual(request["capability"], "b" * 64)
                            command = request["command"]
                            operations.append(command["op"])
                            saved = read_record(fixture.root / "startup.json")
                            response = {"ok": True, "correlation_id": str(uuid4())}
                            if command["op"] == "arm_stop":
                                fixture.record = saved
                                response["grant"] = fixture.grant(command["inventory"])
                            else:
                                generation = 1 if len(operations) == 1 else 2
                                response["status"] = status(saved, generation)
                                if command["op"] in {"shutdown", "finalize"}:
                                    response.update(
                                        result_generation=2,
                                        owner_epoch=1,
                                        command_id=command["command_id"],
                                        expected_generation=command["expected_generation"],
                                    )
                            connection.sendall(json.dumps(response).encode() + b"\n")
                except BaseException as exc:
                    failures.append(exc)

            server = threading.Thread(target=serve)
            server.start()
            try:
                with (
                    patch.dict(
                        os.environ,
                        {
                            "XDG_DATA_HOME": str(fixture.data),
                            "XDG_CONFIG_HOME": str(fixture.base / "config"),
                        },
                    ),
                    patch.object(stop, "state_dir", return_value=fixture.root),
                    patch.object(stop, "control_dir", return_value=fixture.control),
                    patch.object(stop, "ControlRuntime", return_value=fixture.runtime),
                    patch.object(stop, "verify_running"),
                    patch.object(stop, "_running_for_stop", return_value=status(ready)),
                    patch.object(stop, "_finalized_db_readback"),
                    patch.object(fixture.runtime, "ids", side_effect=view.ids),
                    patch.object(fixture.runtime, "inspect", side_effect=view.inspect),
                    patch.object(fixture.runtime, "network", side_effect=view.network),
                    patch(
                        "omnis_cli.stop_owner.subprocess.Popen",
                        side_effect=lambda argv, **kwargs: original(
                            owner_test_argv(argv), **kwargs
                        ),
                    ) as owner_spawn,
                    patch.object(stop, "_resume_owned", side_effect=AssertionError("legacy path")),
                    patch.object(
                        stop, "_emergency_stop", side_effect=AssertionError("unexpected emergency")
                    ),
                ):
                    self.assertEqual(stop.stop_instance()["state"], "STOPPED")
                    complete = read_record(receipt_path(fixture.root, fixture.record))
                    self.assertEqual(complete["state"], "COMPLETED")
                    effects = [
                        event for event in fixture.requests if event.startswith(("POST", "DELETE"))
                    ]
                    self.assertEqual(len(effects), 7)
                    self.assertEqual(stop.stop_instance()["state"], "STOPPED")
                    self.assertEqual(
                        [
                            event
                            for event in fixture.requests
                            if event.startswith(("POST", "DELETE"))
                        ],
                        effects,
                    )
                    owner_spawn.assert_called_once()
                self.assertEqual(
                    operations, ["status", "shutdown", "status", "finalize", "arm_stop"]
                )
            finally:
                server.join(6)
                self.assertFalse(server.is_alive())
            self.assertEqual(failures, [])
        finally:
            fixture.close()

    def test_abrupt_start_exit_preserves_old_bytes_and_new_intent(self):
        with private_stop_fixture() as (base, root, _foreign, control, old, runtime):
            raw = (json.dumps(old, indent=1) + "\r\n").encode()
            journal = root / "startup.json"
            journal.write_bytes(raw)
            journal.chmod(0o600)
            (root / "forwarder.log").write_text("previous\n")
            (root / "forwarder.log").chmod(0o600)
            with (
                completed_fixture(root, control, old, runtime),
                patch.dict(
                    os.environ,
                    {
                        "XDG_DATA_HOME": str(base / "d"),
                        "XDG_STATE_HOME": str(base / "s"),
                        "XDG_RUNTIME_DIR": "",
                        "XDG_CONFIG_HOME": str(base / "config"),
                    },
                ),
                patch.object(start, "ControlRuntime", return_value=runtime),
                patch.object(start, "preflight_port"),
                patch.object(start, "environment", return_value={}),
                patch.object(start, "validate_config"),
                patch.object(
                    runtime, "compose", side_effect=lambda *_a, **_k: os._exit(91), create=True
                ),
            ):
                self.assertEqual(threading.active_count(), 1)
                reader, writer = os.pipe()
                pid = os.fork()
                if pid == 0:
                    os.close(writer)
                    if os.read(reader, 1) != b"G":
                        os._exit(93)
                    os.close(reader)
                    start.start_result(None)
                    os._exit(92)
                os.close(reader)
                pin = -1
                reaped = False
                try:
                    pin = os.pidfd_open(pid)
                    os.write(writer, b"G")
                    self.assertTrue(
                        select.select([pin], [], [], 5)[0], "Start did not reach crash cut"
                    )
                    _, status = os.waitpid(pid, 0)
                    reaped = True
                    self.assertEqual(os.waitstatus_to_exitcode(status), 91)
                    self.assertEqual(
                        (root / f"stopped-{old['stop_command']}.json").read_bytes(), raw
                    )
                    intent = read_record(root / f"restart-{old['stop_command']}.json")
                    self.assertEqual(intent["state"], "PREPARED")
                    self.assertEqual(intent["new_attempt"], read_record(journal)["attempt"])
                    self.assertEqual(read_record(journal)["phase"], "STARTING")
                    self.assertEqual(start.start_result(None)[0], 4)
                finally:
                    os.close(writer)
                    if not reaped:
                        if pin >= 0:
                            signal.pidfd_send_signal(pin, signal.SIGKILL)
                            self.assertTrue(select.select([pin], [], [], 3)[0])
                        os.waitpid(pid, 0)
                    if pin >= 0:
                        os.close(pin)
