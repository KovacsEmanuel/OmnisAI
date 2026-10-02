"""Instance Stop is distinct from run Stop and never guesses an installation."""

import contextlib
import importlib
import io
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Iterator
from unittest.mock import patch
from uuid import uuid4

from omnis_cli.control import ControlUnavailable
from omnis_cli.lifecycle import (
    StartError,
    cleanup_startup_ipc,
    process_identity,
    read_record,
    socket_identity,
    write_record,
)
from omnis_cli.main import main
from omnis_cli.stop import readback_stopped


@contextlib.contextmanager
def private_stop_fixture() -> Iterator[
    tuple[Path, Path, Path, Path, dict[str, object], SimpleNamespace]
]:
    with tempfile.TemporaryDirectory(prefix="sl04-data-", dir=os.environ["TMPDIR"]) as name:
        base = Path(name)
        state, data = base / "s", base / "d"
        state.mkdir(mode=0o700)
        data.mkdir(mode=0o700)
        (data / "omnis").mkdir(mode=0o700)
        root, foreign = state / "omnis", base / "foreign"
        root.mkdir(mode=0o700)
        foreign.mkdir(mode=0o700)
        with socket.socket() as reservation:
            reservation.bind(("127.0.0.1", 0))
            port = reservation.getsockname()[1]
        project = "omnis-local-" + "a" * 32
        instance_id, attempt = str(uuid4()), str(uuid4())
        control = root / "runtime-ipc"
        write_record(
            root / "instance.json",
            {
                "version": 1,
                "instance_id": instance_id,
                "release": "0.1.0",
                "schema": "0004_pairing_receipts",
                "project": project,
                "origin": f"http://127.0.0.1:{port}",
            },
        )
        record: dict[str, object] = {
            "format": 1,
            "phase": "STOPPED",
            "attempt": attempt,
            "project": project,
            "release_digest": "b" * 64,
            "image_id": "sha256:" + "c" * 64,
            "docker_host": "unix:///run/docker.sock",
            "docker_id": "synthetic-daemon",
            "control_dir": str(control),
            "port": port,
            "containers": {
                key: char * 64 for key, char in zip(("db", "api", "supervisor"), "def", strict=True)
            },
            "system_id": "12345",
            "instance_id": instance_id,
            "forwarder": {},
            "listener_inode": 123,
            "api_socket": [1, 2],
            "control_socket": [3, 4],
            "open_command": str(uuid4()),
            "generation": 1,
            "supervisor_epoch": 1,
            "stop_command": str(uuid4()),
            "stop_expected": 1,
            "stop_generation": 2,
            "finalize_command": str(uuid4()),
            "finalized_generation": 2,
            "teardown_completed": ["forwarder", "api", "supervisor", "db", "network", "ipc"],
        }
        runtime = SimpleNamespace(
            receipt=SimpleNamespace(
                project=project, image_id=record["image_id"], docker_id=record["docker_id"]
            ),
            digest=record["release_digest"],
            host=record["docker_host"],
            attempt=None,
            deadline=time.monotonic() + 180,
            uncertain=False,
            family_drained=True,
            ids=lambda: [],
            network=lambda _allowed: None,
            inspect=lambda _kind, _cid: None,
        )
        password = root / "db-password"
        password.write_text("synthetic\n")
        password.chmod(0o600)
        (root / "postgres").mkdir(mode=0o711)
        (root / "postgres").chmod(0o711)  # mkdir mode is narrowed by an inherited umask.
        yield base, root, foreign, control, record, runtime


class StopTest(unittest.TestCase):
    def test_complete_forwarding_intent_after_start_crash_gets_emergency_marker(self) -> None:
        """A possible OPEN ACK cannot be abandoned with admission potentially open."""
        with private_stop_fixture() as (base, root, _foreign, control, record, runtime):
            stop_module = importlib.import_module("omnis_cli.stop")
            start_module = importlib.import_module("omnis_cli.start")
            for key in stop_module.STOP_FIELDS - start_module.READY_FIELDS:
                record.pop(key)
            record.pop("generation")
            record.pop("supervisor_epoch")
            record["phase"] = "FORWARDING"
            journal = root / "startup.json"
            write_record(journal, record)
            ids = record["containers"]
            assert isinstance(ids, dict)
            runtime.ids = lambda: list(ids.values())
            runtime.attest = lambda *_args: {"State": {"Running": True}}
            runtime.network = lambda _allowed: "n" * 64
            seen: list[str] = []

            def drain(*_args: object) -> None:
                assert read_record(root / "unreconciled.json")["attempt"] == record["attempt"]
                seen.append(str(read_record(journal)["phase"]))
                raise StartError("DRAIN_UNCERTAIN", 4)

            with (
                patch.dict(
                    os.environ,
                    {
                        "XDG_STATE_HOME": str(base / "s"),
                        "XDG_DATA_HOME": str(base / "d"),
                        "XDG_RUNTIME_DIR": "",
                    },
                ),
                patch.object(stop_module, "ControlRuntime", return_value=runtime),
                patch.object(stop_module, "_emergency_drain", side_effect=drain),
            ):
                with self.assertRaisesRegex(StartError, "DRAIN_UNCERTAIN"):
                    stop_module.stop_instance()
            self.assertEqual(seen, ["UNCERTAIN"])
            self.assertEqual(read_record(journal)["phase"], "UNCERTAIN")

    def test_control_loss_after_stopping_journal_uses_emergency_intent(self) -> None:
        """A lost shutdown ACK must not leave a live unmarked STOPPING fixture."""
        with private_stop_fixture() as (base, root, _foreign, control, record, runtime):
            record.update(
                phase="STOPPING",
                stop_generation=None,
                finalized_generation=None,
                teardown_completed=[],
            )
            journal = root / "startup.json"
            write_record(journal, record)
            ids = record["containers"]
            assert isinstance(ids, dict)
            runtime.ids = lambda: list(ids.values())
            runtime.attest = lambda *_args: {"State": {"Running": True}}
            runtime.network = lambda _allowed: "n" * 64
            stop_module = importlib.import_module("omnis_cli.stop")
            seen: list[tuple[str, str]] = []

            def drain(*_args: object) -> None:
                seen.append(
                    (
                        str(read_record(journal)["phase"]),
                        str(read_record(root / "unreconciled.json")["instance_id"]),
                    )
                )
                raise StartError("DRAIN_UNCERTAIN", 4)

            with (
                patch.dict(
                    os.environ,
                    {
                        "XDG_STATE_HOME": str(base / "s"),
                        "XDG_DATA_HOME": str(base / "d"),
                        "XDG_RUNTIME_DIR": "",
                    },
                ),
                patch.object(stop_module, "ControlRuntime", return_value=runtime),
                patch.object(stop_module, "_running_for_stop", side_effect=ControlUnavailable),
                patch.object(stop_module, "_emergency_drain", side_effect=drain),
            ):
                with self.assertRaisesRegex(StartError, "DRAIN_UNCERTAIN"):
                    stop_module.stop_instance()
            self.assertEqual(seen, [("UNCERTAIN", str(record["instance_id"]))])
            self.assertEqual(read_record(journal)["phase"], "UNCERTAIN")

    def test_failed_emergency_marker_and_drain_cannot_leave_ready_journal(self) -> None:
        """A transiently recovered peer cannot reuse READY after failed emergency Stop."""
        with private_stop_fixture() as (base, root, _foreign, control, record, runtime):
            stop_module = importlib.import_module("omnis_cli.stop")
            start_module = importlib.import_module("omnis_cli.start")
            for key in stop_module.STOP_FIELDS - start_module.READY_FIELDS:
                record.pop(key)
            record["phase"] = "READY"
            journal = root / "startup.json"
            write_record(journal, record)
            ids = record["containers"]
            assert isinstance(ids, dict)
            runtime.ids = lambda: list(ids.values())
            runtime.attest = lambda *_args: {"State": {"Running": True}}
            runtime.network = lambda _allowed: "n" * 64
            observed: list[str] = []

            def failed_drain(*_args: object) -> None:
                observed.append(str(read_record(journal)["phase"]))
                raise StartError("DRAIN_FAILED", 4)

            with (
                patch.dict(
                    os.environ,
                    {
                        "XDG_STATE_HOME": str(base / "s"),
                        "XDG_DATA_HOME": str(base / "d"),
                        "XDG_RUNTIME_DIR": "",
                    },
                ),
                patch.object(stop_module, "_marker", side_effect=OSError("fixture marker ENOSPC")),
                patch.object(stop_module, "_emergency_drain", side_effect=failed_drain),
            ):
                with self.assertRaisesRegex(StartError, "DRAIN_FAILED"):
                    stop_module._emergency_stop(runtime, root, control, record)
                self.assertEqual(observed, ["UNCERTAIN"])
                self.assertEqual(read_record(journal)["phase"], "UNCERTAIN")
                self.assertFalse(os.path.lexists(root / "unreconciled.json"))
                with (
                    patch.object(start_module, "ControlRuntime", return_value=runtime),
                    patch.object(start_module, "service_ids") as services,
                ):
                    code, outcome = start_module.start_result(None)
                self.assertEqual((code, outcome["reason"]), (4, "RECOVERY_REQUIRED"))
                services.assert_not_called()

    def test_finalized_stop_resumes_only_remaining_owned_resources(self) -> None:
        """A partial host teardown after FINALIZE is not a new DB shutdown."""
        with private_stop_fixture() as (base, root, _foreign, control, record, runtime):
            record.update(phase="STOPPING", teardown_completed=["forwarder", "api"])
            child = subprocess.Popen(
                [sys.executable, "-I", "-c", "import time; time.sleep(60)"],
                cwd=base,
                env={"PATH": "/usr/bin:/bin"},
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            try:
                record["forwarder"] = process_identity(child.pid)
            finally:
                child.terminate()  # This is the exact test-owned and unreaped child.
                child.wait(timeout=5)
            write_record(root / "startup.json", record)
            cids = record["containers"]
            assert isinstance(cids, dict)
            states = {cids["supervisor"]: True, cids["db"]: True}
            effects: list[tuple[str, ...]] = []
            network_active = True

            def ids() -> list[str]:
                return list(states)

            def inspect(kind: str, cid: str) -> dict[str, object] | None:
                assert kind == "container"
                return {"State": {"Running": states[cid]}} if cid in states else None

            def attest(cid: str, role: str, *_args: object) -> dict[str, object]:
                assert cid == cids[role] and cid in states, "Foreign identity was adopted"
                return {"State": {"Running": states[cid]}}

            def network(allowed: set[str]) -> str | None:
                assert not set(states) - allowed, "Foreign network member was accepted"
                return "n" * 64 if network_active else None

            def psql(cid: str, query: str) -> str:
                assert cid == cids["db"]
                if "pg_control_system()" in query:
                    return str(record["system_id"])
                if "SELECT instance_id FROM instance_control" in query:
                    return str(record["instance_id"])
                if "SELECT version_num FROM alembic_version" in query:
                    return "0004_pairing_receipts"
                if "SELECT generation" in query:
                    return f"2|f|{record['stop_command']}|2|1"
                raise AssertionError("Unexpected DB readback")

            def run(*args: str, **_kwargs: object) -> subprocess.CompletedProcess[str]:
                nonlocal network_active
                effects.append(args)
                if args[0] == "stop":
                    assert args[-1] in states
                    states[args[-1]] = False
                elif args[:2] == ("container", "rm"):
                    assert states[args[-1]] is False
                    del states[args[-1]]
                elif args[:2] == ("network", "rm"):
                    assert not states
                    network_active = False
                else:
                    raise AssertionError("Unexpected lifecycle effect")
                return subprocess.CompletedProcess(args, 0, "", "")

            runtime.ids = ids
            runtime.inspect = inspect
            runtime.attest = attest
            runtime.network = network
            runtime.psql = psql
            runtime.run = run
            output = io.StringIO()
            stop_module = importlib.import_module("omnis_cli.stop")
            with (
                patch.dict(
                    os.environ,
                    {
                        "XDG_STATE_HOME": str(base / "s"),
                        "XDG_DATA_HOME": str(base / "d"),
                        "XDG_RUNTIME_DIR": "",
                    },
                ),
                patch.object(stop_module, "ControlRuntime", return_value=runtime),
                contextlib.redirect_stdout(output),
            ):
                code = main(["stop", "--json"])
            assert code == 0, "A finalized, attested partial stop must be resumable"
            assert json.loads(output.getvalue())["state"] == "STOPPED"
            assert json.loads((root / "startup.json").read_text())["phase"] == "STOPPED"
            assert not os.path.lexists(root / "unreconciled.json")
            assert [event[:2] for event in effects] == [
                ("stop", "--time"),
                ("container", "rm"),
                ("stop", "--time"),
                ("container", "rm"),
                ("network", "rm"),
            ]
            assert not states and not network_active
            assert (root / "postgres").is_dir()

    def test_stopped_receipt_refuses_symlinked_pgdata_or_database_secret(self) -> None:
        """Offline STOPPED readback must not follow a replacement data root."""
        with private_stop_fixture() as (_base, root, foreign, control, record, runtime):
            password = root / "db-password"
            (root / "postgres").rmdir()
            (root / "postgres").symlink_to(foreign, target_is_directory=True)
            with self.assertRaises(StartError):
                readback_stopped(runtime, root, control, record)
            (root / "postgres").unlink()
            (root / "postgres").mkdir(mode=0o711)
            (root / "postgres").chmod(0o711)
            other_secret = foreign / "password"
            other_secret.write_text("synthetic\n")
            other_secret.chmod(0o600)
            password.unlink()
            password.symlink_to(other_secret)
            with self.assertRaises(StartError):
                readback_stopped(runtime, root, control, record)
            password.unlink()
            password.write_text("synthetic\n")
            password.chmod(0o600)
            readback_stopped(runtime, root, control, record)

    def test_stale_owned_socket_receipt_never_unlinks_replaced_private_peer(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sl04-ipc-", dir=os.environ["TMPDIR"]) as name:
            root = Path(name) / "omnis"
            http, control = root / "http", root / "runtime-ipc"
            root.mkdir(mode=0o700)
            http.mkdir(mode=0o700)
            control.mkdir(mode=0o700)
            lock = http / "api.lock"
            lock.write_text("")
            lock.chmod(0o600)
            path = http / "api.sock"
            with socket.socket(socket.AF_UNIX) as old:
                old.bind(str(path))
                path.chmod(0o600)
                expected = socket_identity(path)
                substitute = http / "replacement.sock"
                with socket.socket(socket.AF_UNIX) as replacement:
                    replacement.bind(str(substitute))
                    substitute.chmod(0o600)
                    actual = socket_identity(substitute)
                    os.replace(substitute, path)
                assert actual != expected
                problems = cleanup_startup_ipc(root, control, expected={"api": expected})
                assert problems == ["IPC ownership uncertain"]
                assert socket_identity(path) == actual
            path.unlink()
            with socket.socket(socket.AF_UNIX) as owned:
                owned.bind(str(path))
                path.chmod(0o600)
                current = socket_identity(path)
            assert cleanup_startup_ipc(root, control, expected={"api": current}) == []
            assert not os.path.lexists(path)

    def test_stop_without_installed_release_refuses_without_state_effects(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sl04-", dir=os.environ["TMPDIR"]) as name:
            root = Path(name)
            env = {
                "XDG_DATA_HOME": str(root / "data"),
                "XDG_STATE_HOME": str(root / "state"),
                "XDG_RUNTIME_DIR": str(root / "runtime"),
            }
            stdout, stderr = io.StringIO(), io.StringIO()
            with (
                patch.dict(os.environ, env),
                contextlib.redirect_stdout(stdout),
                contextlib.redirect_stderr(stderr),
            ):
                code = main(["stop", "--json"])
            assert code == 2
            result = json.loads(stdout.getvalue())
            assert result["state"] == "REFUSED" and result["reason"] == "RELEASE_REQUIRED"
            assert result["dashboard_ready"] is False
            assert result["assessment_ready"] is False
            assert not (root / "state").exists()
            assert not (root / "runtime").exists()
            assert not stderr.getvalue() or "Traceback" not in stderr.getvalue()
