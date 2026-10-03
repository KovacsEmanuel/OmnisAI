"""Explicit restart consumer; persistence real, DB/OCI boundaries explicitly substituted."""

import contextlib
import hashlib
import importlib
import json
import os
import subprocess
import unittest
from unittest.mock import patch
from uuid import uuid4

from omnis_cli.lifecycle import StartError, read_record, write_record
from omnis_cli.stop_receipt import receipt_path
from test_stop import private_stop_fixture

start = importlib.import_module("omnis_cli.start")
stop = importlib.import_module("omnis_cli.stop")


class RestartWiringTest(unittest.TestCase):
    def test_db_only_then_correlated_reconciliation_ack_then_supervisor(self):
        self.restart()

    def test_lost_mixed_wrong_ack_nonzero_oom_and_cancel_retain_db_no_retry(self):
        for fault in ("lost", "mixed", "wrong", "exit", "oom", "cancel", "drain", "ack-write"):
            with self.subTest(fault=fault):
                self.restart(fault)

    def test_old_bytes_survive_crash_before_first_db_effect(self):
        self.restart("crash")

    def restart(self, fault=None):
        with private_stop_fixture() as (base, root, _foreign, control, old, runtime):
            # This fixture replaces ONLY owner proof for wiring; real owner tests are separate.
            journal = root / "startup.json"
            old_raw = (json.dumps(old, indent=2) + "\r\n").encode()
            journal.write_bytes(old_raw)
            journal.chmod(0o600)
            grant = {
                "version": 1,
                "state": "STOP_PENDING",
                "instance_id": old["instance_id"],
                "command_id": old["stop_command"],
                "finalize_command_id": old["finalize_command"],
                "generation": 2,
                "owner_epoch": 1,
                "owner_uuid": str(uuid4()),
                "daemon_id": old["docker_id"],
                "inventory": {"synthetic": True},
            }
            completion = {"state": "COMPLETED", "grant": grant}
            completion_raw = (json.dumps(completion, indent=3) + "\r\n").encode()
            receipt_path(root, old).write_bytes(completion_raw)
            receipt_path(root, old).chmod(0o600)
            (root / "forwarder.log").write_text("prior\n")
            (root / "forwarder.log").chmod(0o600)
            events, resources, requests = [], {}, []
            db, job = "1" * 64, "2" * 64
            intent_path = root / f"restart-{old['stop_command']}.json"
            copy_path = root / f"stopped-{old['stop_command']}.json"

            def compose(_env, *args, **kwargs):
                self.assertTrue(kwargs["effect"])
                if args[-1] == "db":
                    events.append("create-db")
                    self.assertEqual(copy_path.read_bytes(), old_raw)
                    intent = read_record(intent_path)
                    self.assertEqual(intent["old_stop_command"], old["stop_command"])
                    self.assertEqual(intent["new_attempt"], read_record(journal)["attempt"])
                    if fault == "crash":
                        raise KeyboardInterrupt()
                    resources[db] = "db"
                else:
                    events.append("create-services")
                    self.assertEqual(read_record(intent_path)["state"], "ACKED")
                    self.assertEqual(read_record(intent_path)["ack"]["receipt"], requests[0])
                    raise StartError("SYNTHETIC_AFTER_ACK_CUT", 3)
                return subprocess.CompletedProcess(args, 0, "", "")

            def run(*args, **kwargs):
                if args == ("start", db):
                    events.append("start-db")
                elif args[0] == "create":
                    events.append("create-reconcile")
                    self.assertEqual(
                        args[-5:],
                        (runtime.receipt.image_id, "python", "-I", "-m", "omnis.stop_reconcile"),
                    )
                    self.assertIn("--interactive", args)
                    self.assertNotIn("--tty", args)
                    self.assertEqual(
                        [args[i + 1] for i, a in enumerate(args) if a == "--attach"],
                        ["stdin", "stdout", "stderr"],
                    )
                    self.assertNotIn("synthetic-dsn", " ".join(args))
                    self.assertEqual(
                        kwargs["env"],
                        {
                            "OMNIS_DATABASE_URL": "synthetic-dsn",
                            "OMNIS_EXPECTED_SYSTEM_ID": old["system_id"],
                        },
                    )
                    resources[job] = "reconcile"
                    return subprocess.CompletedProcess(args, 0, job + "\n", "")
                elif args[0] == "start" and args[-1] == job:
                    events.append("reconcile")
                    payload = json.loads(kwargs["stdin"])
                    requests.append(payload)
                    self.assertEqual(
                        set(payload),
                        {
                            "version",
                            "reconciliation_id",
                            "system_identifier",
                            "grant",
                            "completion_sha256",
                        },
                    )
                    self.assertEqual(payload["grant"], grant)
                    self.assertEqual(
                        payload["completion_sha256"], hashlib.sha256(completion_raw).hexdigest()
                    )
                    self.assertEqual(payload, read_record(intent_path)["request"])
                    self.assertIn("--attach", args)
                    self.assertIn("--interactive", args)
                    if fault == "cancel":
                        raise KeyboardInterrupt()
                    if fault == "drain":
                        runtime.family_drained = False
                    reply = {
                        "ok": True,
                        "correlation_id": payload["reconciliation_id"],
                        "receipt": payload,
                    }
                    if fault == "wrong":
                        reply["correlation_id"] = str(uuid4())
                    raw = json.dumps(reply) + "\n"
                    if fault == "mixed":
                        raw = "untrusted log\n" + raw
                    if fault == "lost":
                        raw = ""
                    return subprocess.CompletedProcess(args, 7 if fault == "exit" else 0, raw, "")
                elif args[:2] == ("container", "rm"):
                    events.append("remove-reconcile")
                    del resources[job]
                else:
                    self.fail(f"Unexpected effect {args[0]}")
                return subprocess.CompletedProcess(args, 0, "", "")

            def attest(cid, role, *_args):
                self.assertEqual(resources[cid], role)
                return {
                    "State": {
                        "Status": "exited" if requests else "created",
                        "Running": False,
                        "Pid": 0,
                        "ExitCode": 0,
                        "OOMKilled": fault == "oom",
                        "Dead": False,
                        "Restarting": False,
                        "Paused": False,
                    }
                }

            def saved(path, value, **kwargs):
                if fault == "ack-write" and path == intent_path and value.get("state") == "ACKED":
                    raise OSError("synthetic ENOSPC at ACK")
                write_record(path, value, **kwargs)

            with contextlib.ExitStack() as scope:
                for seam in (
                    patch.dict(
                        os.environ,
                        {
                            "XDG_STATE_HOME": str(base / "s"),
                            "XDG_DATA_HOME": str(base / "d"),
                            "XDG_RUNTIME_DIR": "",
                            "XDG_CONFIG_HOME": str(base / "config"),
                        },
                    ),
                    patch.object(start, "ControlRuntime", return_value=runtime),
                    patch("omnis_cli.stop_owner.verify_stop_completion"),
                    patch.object(start, "preflight_port"),
                    patch.object(
                        start, "environment", return_value={"OMNIS_DATABASE_URL": "synthetic-dsn"}
                    ),
                    patch.object(start, "validate_config"),
                    patch.object(
                        start,
                        "service_ids",
                        side_effect=lambda *_args: {v: k for k, v in resources.items()},
                    ),
                    patch.object(
                        start,
                        "database_identity",
                        return_value=(old["system_id"], old["instance_id"]),
                    ),
                    patch.object(runtime, "ids", side_effect=lambda: list(resources)),
                    patch.object(
                        runtime,
                        "inspect",
                        side_effect=lambda _kind, cid: (
                            attest(cid, resources[cid]) if cid in resources else None
                        ),
                    ),
                    patch.object(
                        runtime,
                        "network",
                        side_effect=lambda _allowed: "3" * 64 if resources else None,
                    ),
                    patch.object(runtime, "compose", side_effect=compose, create=True),
                    patch.object(runtime, "run", side_effect=run, create=True),
                    patch.object(runtime, "attest", side_effect=attest, create=True),
                    patch.object(runtime, "psql", return_value=old["system_id"], create=True),
                    patch.object(runtime, "wait_container", return_value={}, create=True),
                    patch.object(
                        start,
                        "cleanup_attempt",
                        side_effect=AssertionError("restart cleanup must not destroy DB"),
                    ),
                ):
                    scope.enter_context(seam)
                # Import only if implemented: missing module must fail on the real consumer first.
                try:
                    restart = importlib.import_module("omnis_cli.restart")
                except ModuleNotFoundError:
                    restart = None
                if restart is not None:
                    scope.enter_context(patch.object(restart, "write_record", side_effect=saved))
                code, result = start.start_result(None)
                self.assertEqual(code, 4)
                self.assertEqual(copy_path.read_bytes(), old_raw)
                self.assertEqual(read_record(intent_path)["old_stop_command"], old["stop_command"])
                if fault:
                    self.assertNotIn("create-services", events)
                    if fault != "crash":
                        self.assertIn(db, resources)
                    before = list(events)
                    again, _ = start.start_result(None)
                    self.assertEqual(again, 4)
                    self.assertEqual(events, before, "No blind job/DB replay after uncertainty")
                else:
                    self.assertEqual(
                        events,
                        [
                            "create-db",
                            "start-db",
                            "create-reconcile",
                            "reconcile",
                            "remove-reconcile",
                            "create-services",
                        ],
                    )
                    self.assertEqual(result["state"], "UNCERTAIN")
