"""Stop-owner probes use only new private files/processes and synthetic Engine UDS."""

import fcntl
import importlib.util
import os
import select
import signal
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from omnis_cli.lifecycle import StartError, lifecycle_lock, read_record
from omnis_cli.stop_owner import prepare_stop_inventory, run_stop_owner, verify_stop_completion
from omnis_cli.stop_receipt import receipt_path
from stop_owner_fixture import Fixture, owner_test_argv


class StopProductTests(unittest.TestCase):
    def test_eof_after_ready_with_live_launcher_has_zero_effect(self):
        from omnis_cli.lifecycle import process_identity
        from omnis_cli.stop_owner import _process_stamp
        from omnis_cli.stop_receipt import encoded, persist

        fixture = Fixture()
        try:
            with (
                lifecycle_lock(fixture.data / "omnis", fixture.runtime.deadline) as data_fd,
                lifecycle_lock(fixture.root, fixture.runtime.deadline) as state_fd,
            ):
                inventory = prepare_stop_inventory(
                    fixture.runtime, fixture.root, fixture.control, fixture.record
                )
                grant = fixture.grant(inventory)
                persist(
                    receipt_path(fixture.root, fixture.record),
                    {
                        "version": 1,
                        "grant": grant,
                        "owner": None,
                        "launcher": _process_stamp(process_identity(os.getpid())),
                        "state": "PREPARED",
                        "pending": None,
                        "completed": [],
                    },
                )
                parent, child = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
                process = subprocess.Popen(
                    [
                        sys.executable,
                        "-I",
                        "-m",
                        "omnis_cli.stop_owner",
                        str(child.fileno()),
                        str(data_fd),
                        str(state_fd),
                    ],
                    pass_fds=(child.fileno(), data_fd, state_fd),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                try:
                    child.close()
                    parent.send(
                        encoded(
                            {
                                "root": str(fixture.root),
                                "control": str(fixture.control),
                                "data_home": str(fixture.data),
                                "record": fixture.record,
                                "grant": grant,
                                "deadline_ns": int(fixture.runtime.deadline * 1e9),
                            }
                        )
                    )
                    parent.settimeout(4)
                    self.assertEqual(parent.recv(128), b"READY")
                    parent.close()
                    self.assertEqual(process.wait(timeout=3), 4)
                    self.assertIsNone(fixture.forwarder.poll())
                    self.assertFalse(
                        any(x.startswith(("POST", "DELETE")) for x in fixture.requests)
                    )
                    with self.assertRaisesRegex(StartError, "STOP_OWNER_REPLAY_REFUSED"):
                        run_stop_owner(
                            fixture.runtime,
                            fixture.root,
                            fixture.control,
                            fixture.record,
                            grant,
                            lock_fds=(data_fd, state_fd),
                        )
                finally:
                    parent.close()
                    child.close()
                    process.wait(timeout=3)
        finally:
            fixture.close()

    def test_unverifiable_container_family_refuses_before_host_effect(self):
        fixture = Fixture()
        try:
            with (
                lifecycle_lock(fixture.data / "omnis", fixture.runtime.deadline) as data_fd,
                lifecycle_lock(fixture.root, fixture.runtime.deadline) as state_fd,
            ):
                inventory = prepare_stop_inventory(
                    fixture.runtime, fixture.root, fixture.control, fixture.record
                )
                with self.assertRaises((StartError, OSError)):
                    run_stop_owner(
                        fixture.runtime,
                        fixture.root,
                        fixture.control,
                        fixture.record,
                        fixture.grant(inventory),
                        lock_fds=(data_fd, state_fd),
                    )
                self.assertIsNone(
                    fixture.forwarder.poll(), "unproved family must not close admission transport"
                )
                self.assertFalse(any(x.startswith(("POST", "DELETE")) for x in fixture.requests))
        finally:
            fixture.close()

    def test_inventory_pins_container_incarnation_not_only_cid(self):
        fixture = Fixture()
        try:
            before = prepare_stop_inventory(
                fixture.runtime, fixture.root, fixture.control, fixture.record
            )
            fixture.items[fixture.ids["api"]]["State"]["Pid"] = fixture.processes["db"].pid
            after = prepare_stop_inventory(
                fixture.runtime, fixture.root, fixture.control, fixture.record
            )
            self.assertNotEqual(
                before, after, "same CID with another process cannot reuse the grant"
            )
            self.assertFalse(any(x.startswith(("POST", "DELETE")) for x in fixture.requests))
        finally:
            fixture.close()

    def test_pin_failure_and_second_lock_failure_leave_no_effect_or_fd_leak(self):
        fixture = Fixture()
        real_popen = subprocess.Popen
        created = []

        def popen(argv, **kwargs):
            process = real_popen(argv, **kwargs)
            created.append(process)
            return process

        try:
            with (
                lifecycle_lock(fixture.data / "omnis", fixture.runtime.deadline) as data_fd,
                lifecycle_lock(fixture.root, fixture.runtime.deadline) as state_fd,
            ):
                inventory = prepare_stop_inventory(
                    fixture.runtime, fixture.root, fixture.control, fixture.record
                )
                baseline = len(list(Path("/proc/self/fd").iterdir()))
                independent = os.open(fixture.root / "lifecycle.lock", os.O_RDWR)
                try:
                    with self.assertRaises(StartError):
                        run_stop_owner(
                            fixture.runtime,
                            fixture.root,
                            fixture.control,
                            fixture.record,
                            fixture.grant(inventory),
                            lock_fds=(data_fd, independent),
                        )
                finally:
                    os.close(independent)
                self.assertEqual(len(list(Path("/proc/self/fd").iterdir())), baseline)
                with (
                    patch("omnis_cli.stop_owner.subprocess.Popen", side_effect=popen),
                    patch(
                        "omnis_cli.stop_owner.os.pidfd_open",
                        side_effect=OSError("synthetic pin failure"),
                    ),
                    self.assertRaises(OSError),
                ):
                    run_stop_owner(
                        fixture.runtime,
                        fixture.root,
                        fixture.control,
                        fixture.record,
                        fixture.grant(inventory),
                        lock_fds=(data_fd, state_fd),
                    )
                self.assertIsNotNone(created[0].returncode)
                self.assertEqual(len(list(Path("/proc/self/fd").iterdir())), baseline)
                self.assertFalse(any(x.startswith(("POST", "DELETE")) for x in fixture.requests))
                self.assertIsNone(fixture.forwarder.poll())
        finally:
            fixture.close()

    def test_ack_does_not_allow_blocking_waitid(self):
        from omnis_cli.stop_owner import _wait_owner

        reader, writer = os.pipe()
        process = subprocess.Popen(
            [
                sys.executable,
                "-I",
                "-c",
                "import os,sys; print('DONE',flush=True); os.read(int(sys.argv[1]),1)",
                str(reader),
            ],
            pass_fds=(reader,),
            stdout=subprocess.PIPE,
        )
        os.close(reader)
        fd = os.pidfd_open(process.pid)
        try:
            assert process.stdout is not None
            self.assertTrue(select.select([process.stdout], [], [], 2)[0])
            self.assertEqual(os.read(process.stdout.fileno(), 128), b"DONE\n")
            start = time.monotonic()
            with self.assertRaises(StartError):
                _wait_owner(process, start + 0.15)
            self.assertLess(time.monotonic() - start, 0.7)
            self.assertFalse(select.select([fd], [], [], 0)[0], "child must still be held alive")
        finally:
            signal.pidfd_send_signal(fd, signal.SIGKILL)
            self.assertTrue(select.select([fd], [], [], 2)[0])
            exited = os.waitid(os.P_PID, process.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)
            self.assertIsNotNone(exited)
            self.assertEqual(exited.si_status, signal.SIGKILL)
            self.assertEqual(process.wait(timeout=2), -signal.SIGKILL)
            os.close(fd)
            os.close(writer)
            process.stdout.close()

    def test_parent_death_and_owner_death_are_distinct(self):
        import array
        import json

        for mode in ("pre-admit", "parent-death", "owner-death"):
            with self.subTest(mode=mode):
                fixture = Fixture()
                fixture.pause_mutation = mode != "pre-admit"
                observer, observer_child = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
                parent = subprocess.Popen(
                    [
                        sys.executable,
                        "-I",
                        str(Path(__file__).with_name("stop_owner_launcher_probe.py")),
                    ],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    pass_fds=(observer_child.fileno(),),
                    start_new_session=True,
                )
                parent_fd, owner_fd = os.pidfd_open(parent.pid), -1
                retained = None
                try:
                    assert parent.stdin is not None and parent.stdout is not None
                    payload = {
                        "root": str(fixture.root),
                        "data": str(fixture.data),
                        "control": str(fixture.control),
                        "record": fixture.record,
                        "fixture_module": str(Path(__file__).with_name("stop_owner_fixture.py")),
                        "mode": mode,
                        "observer_fd": observer_child.fileno(),
                    }
                    parent.stdin.write(json.dumps(payload).encode() + b"\n")
                    parent.stdin.flush()
                    observer_child.close()
                    self.assertTrue(select.select([parent.stdout], [], [], 5)[0])
                    marker = os.read(parent.stdout.fileno(), 128)
                    self.assertTrue(marker.strip().isdigit(), marker)
                    owner_pid = int(marker)
                    owner_fd = os.pidfd_open(owner_pid)
                    self.assertEqual(
                        Path(f"/proc/{owner_pid}/stat").read_text().rsplit(")", 1)[1].split()[1],
                        str(parent.pid),
                    )
                    if mode == "pre-admit":
                        observer.settimeout(3)
                        _body, ancillary, _flags, _addr = observer.recvmsg(
                            128, socket.CMSG_SPACE(4)
                        )
                        inherited = array.array("i")
                        inherited.frombytes(ancillary[0][2])
                        retained = socket.socket(fileno=inherited[0])
                        signal.pidfd_send_signal(parent_fd, signal.SIGKILL)
                        parent.wait(timeout=3)
                        self.assertTrue(
                            select.select([owner_fd], [], [], 3)[0],
                            "live observer writer must not hide parent death",
                        )
                        self.assertFalse(
                            any(x.startswith(("POST", "DELETE")) for x in fixture.requests)
                        )
                        self.assertIsNone(fixture.forwarder.poll())
                    else:
                        self.assertTrue(fixture.mutation_seen.wait(4))
                        self.assertEqual(
                            Path(f"/proc/{owner_pid}/task/{owner_pid}/children")
                            .read_text()
                            .strip(),
                            "",
                        )
                        signal.pidfd_send_signal(
                            parent_fd if mode == "parent-death" else owner_fd, signal.SIGKILL
                        )
                        if mode == "parent-death":
                            parent.wait(timeout=3)
                            for directory in (fixture.data / "omnis", fixture.root):
                                challenger = os.open(directory / "lifecycle.lock", os.O_RDWR)
                                try:
                                    with self.assertRaises(BlockingIOError):
                                        fcntl.flock(challenger, fcntl.LOCK_EX | fcntl.LOCK_NB)
                                finally:
                                    os.close(challenger)
                        fixture.release_mutation.set()
                        self.assertTrue(select.select([owner_fd], [], [], 8)[0])
                        if mode == "owner-death":
                            self.assertEqual(parent.wait(timeout=3), 4)
                            with self.assertRaises((StartError, OSError)):
                                verify_stop_completion(
                                    fixture.runtime, fixture.root, fixture.control, fixture.record
                                )
                        else:
                            verify_stop_completion(
                                fixture.runtime, fixture.root, fixture.control, fixture.record
                            )
                            self.assertEqual(
                                read_record(receipt_path(fixture.root, fixture.record))["state"],
                                "COMPLETED",
                            )
                finally:
                    fixture.release_mutation.set()
                    if owner_fd >= 0:
                        if not select.select([owner_fd], [], [], 1)[0]:
                            signal.pidfd_send_signal(owner_fd, signal.SIGKILL)
                            self.assertTrue(select.select([owner_fd], [], [], 3)[0])
                        os.close(owner_fd)
                    if parent.poll() is None:
                        signal.pidfd_send_signal(parent_fd, signal.SIGKILL)
                    parent.wait(timeout=3)
                    os.close(parent_fd)
                    for stream in (parent.stdin, parent.stdout, parent.stderr):
                        if stream:
                            stream.close()
                    if retained:
                        retained.close()
                    observer.close()
                    observer_child.close()
                    fixture.close()

    def test_correct_arity_independent_lock_fds_are_refused(self):
        import json

        fixture = Fixture()
        try:
            with (
                lifecycle_lock(fixture.data / "omnis", fixture.runtime.deadline),
                lifecycle_lock(fixture.root, fixture.runtime.deadline),
            ):
                fds = []
                parent, child = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
                process = None
                try:
                    for directory in (fixture.data / "omnis", fixture.root):
                        fds.append(os.open(directory / "lifecycle.lock", os.O_RDWR))
                    process = subprocess.Popen(
                        [
                            sys.executable,
                            "-I",
                            "-m",
                            "omnis_cli.stop_owner",
                            str(child.fileno()),
                            *(str(fd) for fd in fds),
                        ],
                        pass_fds=(child.fileno(), *fds),
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    child.close()
                    parent.send(
                        json.dumps(
                            {
                                "root": str(fixture.root),
                                "control": str(fixture.control),
                                "data_home": str(fixture.data),
                                "record": fixture.record,
                                "grant": {},
                                "deadline_ns": int(fixture.runtime.deadline * 1e9),
                            }
                        ).encode()
                    )
                    self.assertEqual(process.wait(timeout=3), 4)
                    self.assertFalse(
                        any(x.startswith(("POST", "DELETE")) for x in fixture.requests)
                    )
                    self.assertFalse(os.path.lexists(receipt_path(fixture.root, fixture.record)))
                finally:
                    parent.close()
                    child.close()
                    for fd in fds:
                        os.close(fd)
                    if process:
                        process.wait(timeout=3)
        finally:
            fixture.close()

    def test_real_handoff_and_receipts_with_synthetic_engine(self):
        fixture = Fixture()
        original_popen = subprocess.Popen

        def popen(argv, **kwargs):
            return original_popen(owner_test_argv(argv), **kwargs)

        try:
            with (
                lifecycle_lock(fixture.data / "omnis", fixture.runtime.deadline) as data_fd,
                lifecycle_lock(fixture.root, fixture.runtime.deadline) as state_fd,
            ):
                inventory = prepare_stop_inventory(
                    fixture.runtime, fixture.root, fixture.control, fixture.record
                )
                self.assertFalse(
                    any(line.startswith(("POST", "DELETE")) for line in fixture.requests)
                )
                self.assertNotIn("OMNIS_DATABASE_URL", str(inventory))
                grant = fixture.grant(inventory)
                before = (fixture.root / "startup.json").read_bytes()
                with patch("omnis_cli.stop_owner.subprocess.Popen", side_effect=popen):
                    run_stop_owner(
                        fixture.runtime,
                        fixture.root,
                        fixture.control,
                        fixture.record,
                        grant,
                        lock_fds=(data_fd, state_fd),
                    )
                self.assertEqual((fixture.root / "startup.json").read_bytes(), before)
                self.assertEqual(
                    read_record(receipt_path(fixture.root, fixture.record))["state"], "COMPLETED"
                )
                effects = [x for x in fixture.requests if x.startswith(("POST", "DELETE"))]
                self.assertEqual(len(effects), 7)
                verify_stop_completion(
                    fixture.runtime, fixture.root, fixture.control, fixture.record, grant
                )
                from copy import deepcopy

                from omnis_cli.lifecycle import write_record

                path = receipt_path(fixture.root, fixture.record)
                clean = read_record(path)
                for where in ("inventory", "launcher", "db_image"):
                    changed = deepcopy(clean)
                    if where == "inventory":
                        changed["grant"]["inventory"]["unknown"] = 1
                    elif where == "db_image":
                        changed["grant"]["inventory"]["containers"][2]["image"] = (
                            "sha256:" + "0" * 64
                        )
                    else:
                        changed["launcher"] = {"pid": True}
                    write_record(path, changed, replace=True)
                    with self.assertRaises(StartError, msg=f"strict {where} schema"):
                        verify_stop_completion(
                            fixture.runtime, fixture.root, fixture.control, fixture.record
                        )
                    write_record(path, clean, replace=True)
                self.assertEqual(
                    effects, [x for x in fixture.requests if x.startswith(("POST", "DELETE"))]
                )
        finally:
            fixture.close()

    def test_lost_ack_and_noop_keep_prepared_never_replay(self):
        original_popen = subprocess.Popen
        for fault in ("lost_ack", "noop", "retain_ipc"):
            with self.subTest(fault=fault):
                fixture = Fixture()
                setattr(fixture, fault, True)
                created = []

                def popen(argv, *, created=created, **kwargs):
                    process = original_popen(owner_test_argv(argv), **kwargs)
                    created.append(process)
                    return process

                try:
                    with (
                        lifecycle_lock(fixture.data / "omnis", fixture.runtime.deadline) as data_fd,
                        lifecycle_lock(fixture.root, fixture.runtime.deadline) as state_fd,
                    ):
                        inventory = prepare_stop_inventory(
                            fixture.runtime, fixture.root, fixture.control, fixture.record
                        )
                        with (
                            patch("omnis_cli.stop_owner.subprocess.Popen", side_effect=popen),
                            self.assertRaises((StartError, OSError)),
                        ):
                            run_stop_owner(
                                fixture.runtime,
                                fixture.root,
                                fixture.control,
                                fixture.record,
                                fixture.grant(inventory),
                                lock_fds=(data_fd, state_fd),
                            )
                        self.assertIsNotNone(
                            created[0].returncode, "failed owner must be boundedly reaped"
                        )
                        receipt = read_record(receipt_path(fixture.root, fixture.record))
                        self.assertNotEqual(receipt["state"], "COMPLETED")
                        if fault == "retain_ipc":
                            self.assertIn(
                                fixture.ids["db"],
                                fixture.items,
                                "IPC drift must stop subsequent DB removal",
                            )
                            self.assertTrue(
                                fixture.items[fixture.ids["db"]]["State"]["Running"],
                                "IPC drift must stop subsequent DB effects",
                            )
                        count = len(
                            [x for x in fixture.requests if x.startswith(("POST", "DELETE"))]
                        )
                        with self.assertRaises((StartError, OSError)):
                            run_stop_owner(
                                fixture.runtime,
                                fixture.root,
                                fixture.control,
                                fixture.record,
                                fixture.grant(inventory),
                                lock_fds=(data_fd, state_fd),
                            )
                        self.assertEqual(
                            count,
                            len([x for x in fixture.requests if x.startswith(("POST", "DELETE"))]),
                        )
                        with self.assertRaises((StartError, OSError)):
                            verify_stop_completion(
                                fixture.runtime, fixture.root, fixture.control, fixture.record
                            )
                finally:
                    fixture.close()


class StopLockTests(unittest.TestCase):
    def test_stop_owner_requires_both_original_descriptions(self) -> None:
        self.assertIsNotNone(
            importlib.util.find_spec("omnis_cli.stop_owner"), "missing product owner"
        )
        from omnis_cli.lifecycle import StartError
        from omnis_cli.stop_owner import _validate_lock

        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
            root = Path(name)
            with lifecycle_lock(root, time.monotonic() + 2) as original:
                _validate_lock(original, root, os.getpid())
                foreign = os.open(root / "lifecycle.lock", os.O_RDWR)
                try:
                    with self.assertRaises((StartError, BlockingIOError)):
                        _validate_lock(foreign, root, os.getpid())
                finally:
                    os.close(foreign)

    def test_original_description_retains_lock_after_launcher_close(self) -> None:
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
            root = Path(name)
            held = -1
            try:
                with lifecycle_lock(root, time.monotonic() + 2) as original:
                    self.assertIsInstance(original, int, "handoff requires original lock FD")
                    held = os.dup(original)
                challenger = os.open(root / "lifecycle.lock", os.O_RDWR)
                try:
                    with self.assertRaises(BlockingIOError):
                        fcntl.flock(challenger, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    os.close(held)
                    held = -1
                    fcntl.flock(challenger, fcntl.LOCK_EX | fcntl.LOCK_NB)
                finally:
                    os.close(challenger)
            finally:
                if held >= 0:
                    os.close(held)
