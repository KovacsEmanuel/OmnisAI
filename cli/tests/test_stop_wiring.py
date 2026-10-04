"""Real Stop consumer, file/flock; explicit control/owner effect seams, NOT OCI/PG."""

import contextlib
import fcntl
import importlib
import io
import json
import os
import signal
import unittest
from unittest.mock import patch
from uuid import uuid4

from omnis_cli.control import ControlUnavailable
from omnis_cli.lifecycle import StartError, read_record, write_record
from omnis_cli.main import main
from omnis_cli.stop_receipt import receipt_path
from test_stop import private_stop_fixture

stop = importlib.import_module("omnis_cli.stop")
start = importlib.import_module("omnis_cli.start")
stop_owner = importlib.import_module("omnis_cli.stop_owner")


class StopWiringTest(unittest.TestCase):
    def test_owner_can_import_the_strict_stop_validator_without_cycle(self):
        import subprocess
        import sys

        # Explicit integration seam for the reviewed owner import dependency;
        # no owner commit is copied into this worktree.
        code = (
            "import builtins\n"
            "original = builtins.__import__\n"
            "def importing(name, globals=None, locals=None, fromlist=(), level=0):\n"
            "    if name == 'stop_owner' and level == 1:\n"
            "        from omnis_cli.stop import _stopping_record\n"
            "        assert callable(_stopping_record)\n"
            "    return original(name, globals, locals, fromlist, level)\n"
            "builtins.__import__ = importing\n"
            "import omnis_cli.stop\n"
        )
        result = subprocess.run(
            [sys.executable, "-I", "-c", code], capture_output=True, text=True, timeout=5
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_normal_stop_hands_original_locks_to_owner_after_authenticated_arm(self):
        self.normal_stop()

    def test_arm_loss_or_owner_failure_never_falls_back_to_emergency(self):
        for fault in ("arm", "owner", "wrong-grant"):
            with self.subTest(fault=fault):
                self.normal_stop(fault)

    def test_post_grant_sigint_is_uncertain_without_fallback_or_retry(self):
        previous = signal.signal(signal.SIGINT, signal.default_int_handler)
        try:
            for fault in ("oserror", "sigint"):
                with self.subTest(fault=fault):
                    self.normal_stop(fault)
        finally:
            signal.signal(signal.SIGINT, previous)

    def normal_stop(self, fault=None):
        with private_stop_fixture() as (base, root, _foreign, control, record, runtime):
            for key in stop.STOP_FIELDS - start.READY_FIELDS:
                record.pop(key)
            record["phase"] = "READY"
            write_record(root / "startup.json", record)
            events, originals, handed_guards, early_data_guards = [], [], [], []
            inventory = {"synthetic-public-inventory": True}
            real_lock = stop.lifecycle_lock

            @contextlib.contextmanager
            def locks(path, deadline):
                if len(originals) == 1:
                    original = os.fstat(originals[0])
                    with os.scandir("/proc/self/fd") as entries:
                        for entry in entries:
                            try:
                                candidate = int(entry.name)
                                info = os.fstat(candidate)
                                if candidate != originals[0] and (info.st_dev, info.st_ino) == (
                                    original.st_dev,
                                    original.st_ino,
                                ):
                                    with open(f"/proc/self/fdinfo/{candidate}") as details:
                                        if "lock:" in details.read():
                                            early_data_guards.append(candidate)
                            except OSError:  # /proc/self/fd's own enumeration FD closes.
                                continue
                    self.assertEqual(len(early_data_guards), 1)
                with real_lock(path, deadline) as fd:
                    originals.append(fd)
                    yield fd

            def current(generation=1, **changes):
                return dict(
                    instance_id=record["instance_id"],
                    generation=generation,
                    supervisor_epoch=1,
                    assessment_ready=False,
                    admission_open=generation == 1,
                    **changes,
                )

            def control_request(_directory, command, **_kwargs):
                events.append(command["op"])
                saved = read_record(root / "startup.json")
                if command["op"] == "status":
                    return (
                        current()
                        if saved["phase"] == "READY"
                        else current(
                            2, shutdown_command_id=saved["stop_command"], quiesced_generation=2
                        )
                    )
                if command["op"] == "shutdown":
                    return current(2, shutdown_command_id=saved["stop_command"])
                if command["op"] == "finalize":
                    return current(2, quiesced_generation=2, shutdown_finalized=True)
                self.assertEqual(command["op"], "arm_stop")
                self.assertEqual(saved["finalized_generation"], 2)
                self.assertEqual(command["inventory"], inventory)
                if fault == "arm":
                    raise ControlUnavailable()
                grant = {key: value for key, value in command.items() if key != "op"}
                grant.update(version=1, state="STOP_PENDING", owner_uuid=str(uuid4()))
                if fault == "wrong-grant":
                    grant["generation"] = 3
                return grant

            def prepare(_runtime, _root, _control, saved):
                self.assertEqual(read_record(root / "startup.json"), saved)
                self.assertEqual(saved["finalized_generation"], 2)
                events.append("inventory")
                return inventory

            def owner(_runtime, _root, _control, saved, grant, *, lock_fds, guard_fds, deadline):
                events.append("owner")
                self.assertEqual(lock_fds, tuple(originals))
                self.assertEqual(deadline, runtime.deadline)
                self.assertEqual(len(set((*lock_fds, *guard_fds))), 4)
                self.assertEqual(early_data_guards, [guard_fds[0]])
                handed_guards.extend(guard_fds)
                for fd, guard, directory in zip(
                    lock_fds, guard_fds, (base / "d/omnis", root), strict=True
                ):
                    self.assertEqual(
                        os.fstat(fd).st_ino, (directory / "lifecycle.lock").stat().st_ino
                    )
                    self.assertEqual(os.fstat(guard).st_ino, os.fstat(fd).st_ino)
                    with open(f"/proc/self/fdinfo/{guard}") as info:
                        self.assertIn("lock:", info.read())
                    with (directory / "lifecycle.lock").open("rb") as other:
                        with self.assertRaises(BlockingIOError):
                            fcntl.flock(other, fcntl.LOCK_EX | fcntl.LOCK_NB)
                if fault == "owner":
                    raise StartError("SYNTHETIC_OWNER_FAILURE", 4)
                if fault == "oserror":
                    raise OSError("synthetic owner error")
                if fault == "sigint":
                    signal.raise_signal(signal.SIGINT)
                write_record(receipt_path(root, saved), {"state": "COMPLETED", "grant": grant})

            def verify(_runtime, _root, _control, saved, grant=None):
                events.append("verify")
                self.assertEqual(read_record(receipt_path(root, saved))["state"], "COMPLETED")

            with (
                patch.dict(
                    os.environ,
                    {
                        "XDG_STATE_HOME": str(base / "s"),
                        "XDG_DATA_HOME": str(base / "d"),
                        "XDG_RUNTIME_DIR": "",
                        "XDG_CONFIG_HOME": str(base / "config"),
                    },
                ),
                patch.object(stop, "ControlRuntime", return_value=runtime),
                patch.object(stop, "lifecycle_lock", side_effect=locks),
                patch.object(stop, "verify_running"),
                patch.object(stop, "_running_for_stop", return_value=current()),
                patch.object(stop, "_finalized_db_readback"),
                patch.object(stop, "request", side_effect=control_request),
                patch.object(stop_owner, "prepare_stop_inventory", side_effect=prepare),
                patch.object(stop_owner, "run_stop_owner", side_effect=owner) as run_owner,
                patch.object(stop_owner, "verify_stop_completion", side_effect=verify),
                patch.object(stop, "_resume_owned", side_effect=AssertionError("legacy teardown")),
                patch.object(stop, "_emergency_stop", side_effect=AssertionError("emergency")),
            ):
                if fault in {"sigint", "oserror"}:
                    output, errors = io.StringIO(), io.StringIO()
                    with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
                        try:
                            code = main(["stop", "--json"])
                        except KeyboardInterrupt:
                            self.fail("post-grant cancellation escaped the CLI projection")
                    self.assertEqual(code, 4)
                    result = json.loads(output.getvalue())
                    self.assertEqual(
                        (result["state"], result["reason"]), ("UNCERTAIN", "STOP_UNCERTAIN")
                    )
                    self.assertFalse(result["dashboard_ready"] or result["assessment_ready"])
                    self.assertEqual(errors.getvalue(), "")
                    saved = read_record(root / "startup.json")
                    self.assertEqual(
                        (saved["phase"], saved["finalized_generation"]), ("STOPPING", 2)
                    )
                    self.assertEqual(events[-2:], ["arm_stop", "owner"])
                    before = list(events)
                    with contextlib.redirect_stdout(io.StringIO()):
                        self.assertEqual(main(["stop", "--json"]), 4)
                    self.assertEqual(events, before)
                    self.assertEqual(read_record(root / "startup.json"), saved)
                    run_owner.assert_called_once()
                elif fault:
                    with self.assertRaises(StartError) as caught:
                        stop.stop_instance()
                    self.assertEqual(caught.exception.code, 4)
                    if fault in {"arm", "wrong-grant"}:
                        run_owner.assert_not_called()
                    self.assertEqual(read_record(root / "startup.json")["phase"], "STOPPING")
                else:
                    self.assertEqual(stop.stop_instance()["state"], "STOPPED")
                    for guard in handed_guards:
                        with self.assertRaises(OSError):
                            os.fstat(guard)
                    self.assertEqual(
                        events[:8],
                        [
                            "status",
                            "shutdown",
                            "status",
                            "finalize",
                            "inventory",
                            "arm_stop",
                            "owner",
                            "verify",
                        ],
                    )
                    self.assertEqual(
                        read_record(root / "startup.json")["teardown_completed"],
                        list(stop.STOP_STAGES),
                    )
                    self.assertEqual(stop.stop_instance()["state"], "STOPPED")
                    run_owner.assert_called_once()

    def test_missing_owner_proof_is_exit_four_on_start_and_status(self):
        status = importlib.import_module("omnis_cli.status")
        with private_stop_fixture() as (base, root, _foreign, _control, record, runtime):
            write_record(root / "startup.json", record)
            before = (root / "startup.json").read_bytes()
            with (
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
                patch.object(status, "ControlRuntime", return_value=runtime),
                patch.object(runtime, "compose", side_effect=AssertionError("effect"), create=True),
            ):
                for command in (["start", "--no-open", "--json"], ["status", "--json"]):
                    with self.subTest(command=command):
                        output = io.StringIO()
                        with contextlib.redirect_stdout(output):
                            code = main(command)
                        self.assertEqual(code, 4)
                        self.assertNotEqual(json.loads(output.getvalue())["state"], "STOPPED")
            self.assertEqual((root / "startup.json").read_bytes(), before)

    def test_incomplete_or_foreign_owner_proof_blocks_real_consumers(self):
        from stopped_fixture import completed_fixture

        changes = (
            ("prepared", lambda r: r.update(state="PREPARED")),
            ("pending", lambda r: r.update(pending="db.stop")),
            ("partial", lambda r: r["completed"].pop()),
            ("foreign-grant", lambda r: r["grant"].update(generation=3)),
            ("uncertain-grant", lambda r: r["grant"].update(state="STOP_UNCERTAIN")),
            ("extra", lambda r: r.update(untrusted=True)),
        )
        for label, mutate in changes:
            with (
                self.subTest(proof=label),
                private_stop_fixture() as (base, root, _foreign, control, record, runtime),
                completed_fixture(root, control, record, runtime),
            ):
                path = receipt_path(root, record)
                owner_receipt = read_record(path)
                mutate(owner_receipt)
                write_record(path, owner_receipt, replace=True)
                before = (root / "startup.json").read_bytes()
                with (
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
                    patch.object(stop, "ControlRuntime", return_value=runtime),
                    patch.object(
                        runtime, "compose", side_effect=AssertionError("effect"), create=True
                    ),
                    patch.object(stop, "request", side_effect=AssertionError("control retry")),
                ):
                    with self.assertRaises(StartError):
                        stop.readback_stopped(runtime, root, control, record)
                    with self.assertRaises(StartError):
                        stop.stop_instance()
                    self.assertEqual(start.start_result(None)[0], 4)
                self.assertEqual((root / "startup.json").read_bytes(), before)
                self.assertEqual(read_record(path), owner_receipt)

    def test_stopped_without_owner_receipt_is_not_authority(self):
        with private_stop_fixture() as (_base, root, _foreign, control, record, runtime):
            with self.assertRaises((StartError, OSError)):
                stop.readback_stopped(runtime, root, control, record)

    def test_completed_owner_after_dead_cli_publishes_without_reemission(self):
        for completed in (True, False):
            with (
                self.subTest(completed=completed),
                private_stop_fixture() as (base, root, _foreign, _control, record, runtime),
            ):
                record.update(phase="STOPPING", teardown_completed=[])
                write_record(root / "startup.json", record)
                write_record(
                    receipt_path(root, record), {"state": "COMPLETED" if completed else "PREPARED"}
                )

                def verify(*_args, complete=completed):
                    if not complete:
                        raise StartError("STOP_RECEIPT_UNVERIFIED", 4)

                with (
                    patch.dict(
                        os.environ,
                        {
                            "XDG_STATE_HOME": str(base / "s"),
                            "XDG_DATA_HOME": str(base / "d"),
                            "XDG_RUNTIME_DIR": "",
                            "XDG_CONFIG_HOME": str(base / "config"),
                        },
                    ),
                    patch.object(stop, "ControlRuntime", return_value=runtime),
                    patch.object(stop_owner, "verify_stop_completion", side_effect=verify),
                    patch.object(stop, "request", side_effect=AssertionError("reissued control")),
                    patch.object(
                        stop_owner,
                        "run_stop_owner",
                        side_effect=AssertionError("reissued owner"),
                        create=True,
                    ),
                    patch.object(stop, "_resume_owned", side_effect=AssertionError("legacy retry")),
                ):
                    if completed:
                        self.assertEqual(stop.stop_instance()["state"], "STOPPED")
                    else:
                        with self.assertRaises(StartError):
                            stop.stop_instance()
                        self.assertEqual(read_record(root / "startup.json"), record)
