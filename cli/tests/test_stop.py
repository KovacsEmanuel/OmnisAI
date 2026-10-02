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
            "format": 2,
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
        pg = (root / "postgres").lstat()
        record["pgdata_identity"] = [pg.st_dev, pg.st_ino]
        yield base, root, foreign, control, record, runtime


class StopTest(unittest.TestCase):
    def test_explicit_restart_preserves_both_identities_before_new_mount(self) -> None:
        """Replacing STOPPED with STARTING must not erase the saved logical or physical ID."""
        start_module = importlib.import_module("omnis_cli.start")
        with private_stop_fixture() as (base, root, _foreign, _control, record, runtime):
            journal = root / "startup.json"
            write_record(journal, record)
            log = root / "forwarder.log"
            log.write_text("synthetic prior forwarder\n")
            log.chmod(0o600)
            observed: list[dict[str, object]] = []

            def before_mount(_env: object, *args: object, **kwargs: object) -> None:
                self.assertEqual(args[0], "create")
                self.assertIs(kwargs.get("effect"), True)
                observed.append(read_record(journal))
                raise StartError("SYNTHETIC_RESTART_CUT", 3)

            with (
                patch.dict(
                    os.environ,
                    {
                        "XDG_STATE_HOME": str(base / "s"),
                        "XDG_DATA_HOME": str(base / "d"),
                        "XDG_RUNTIME_DIR": "",
                    },
                ),
                patch.object(start_module, "ControlRuntime", return_value=runtime),
                patch.object(start_module, "preflight_port"),
                patch.object(start_module, "environment", return_value={}),
                patch.object(start_module, "validate_config"),
                patch.object(start_module, "cleanup_attempt", return_value=[]),
                patch.object(runtime, "compose", side_effect=before_mount, create=True),
            ):
                code, outcome = start_module.start_result(None)
            self.assertEqual((code, outcome["reason"]), (3, "SYNTHETIC_RESTART_CUT"))
            self.assertEqual(len(observed), 1)
            self.assertEqual(observed[0]["format"], 2)
            self.assertEqual(observed[0]["pgdata_identity"], record["pgdata_identity"])
            self.assertEqual(observed[0].get("system_id"), record["system_id"])
            self.assertEqual(read_record(journal)["pgdata_identity"], record["pgdata_identity"])
            self.assertEqual(read_record(journal).get("system_id"), record["system_id"])

    def test_replaced_bind_root_blocks_stop_status_and_explicit_start_without_effects(self) -> None:
        """A copied marker and the same logical ID cannot authorize a new mount."""
        start_module = importlib.import_module("omnis_cli.start")
        stop_module = importlib.import_module("omnis_cli.stop")
        status_module = importlib.import_module("omnis_cli.status")
        with private_stop_fixture() as (base, root, _foreign, _control, record, runtime):
            pg = root / "postgres"
            (pg / "18/docker").mkdir(parents=True)
            (pg / "18/docker/PG_VERSION").write_text("18\n")
            saved = root / "saved-postgres"
            pg.rename(saved)
            pg.mkdir(mode=0o711)
            pg.chmod(0o711)
            (pg / "18/docker").mkdir(parents=True)
            (pg / "18/docker/PG_VERSION").write_text("18\n")
            self.assertEqual(
                (pg.stat().st_uid, pg.stat().st_mode & 0o777),
                (saved.stat().st_uid, saved.stat().st_mode & 0o777),
            )
            self.assertNotEqual([pg.stat().st_dev, pg.stat().st_ino], record["pgdata_identity"])
            env = {
                "XDG_STATE_HOME": str(base / "s"),
                "XDG_DATA_HOME": str(base / "d"),
                "XDG_RUNTIME_DIR": "",
            }
            for phase in ("READY", "STOPPING", "STOPPED"):
                with self.subTest(phase=phase):
                    candidate = dict(record)
                    candidate["phase"] = phase
                    if phase == "READY":
                        for key in stop_module.STOP_FIELDS - start_module.READY_FIELDS:
                            candidate.pop(key)
                    journal = root / "startup.json"
                    write_record(journal, candidate, replace=journal.exists())
                    before = journal.read_bytes()
                    with (
                        patch.dict(os.environ, env),
                        patch.object(start_module, "ControlRuntime", return_value=runtime),
                        patch.object(stop_module, "ControlRuntime", return_value=runtime),
                        patch.object(status_module, "ControlRuntime", return_value=runtime),
                        patch.object(
                            runtime, "ids", side_effect=AssertionError("replaced root reached OCI")
                        ),
                    ):
                        with self.assertRaisesRegex(StartError, "RECOVERY_REQUIRED"):
                            stop_module.stop_instance()
                        code, result = start_module.start_result(None)
                        self.assertEqual((code, result["reason"]), (4, "RECOVERY_REQUIRED"))
                        output = io.StringIO()
                        with contextlib.redirect_stdout(output):
                            status_code = status_module.status(as_json=True)
                        status_result = json.loads(output.getvalue())
                        self.assertEqual(
                            (status_code, status_result["reason"]), (4, "RECOVERY_REQUIRED")
                        )
                        self.assertNotEqual(status_result["state"], "STOPPED")
                    self.assertEqual(journal.read_bytes(), before)
                    self.assertEqual((saved / "18/docker/PG_VERSION").read_text(), "18\n")
                    self.assertFalse((root / "unreconciled.json").exists())

    def test_bad_physical_receipt_schema_is_refused_before_offline_resources(self) -> None:
        with private_stop_fixture() as (_base, root, _foreign, control, record, runtime):
            original = record["pgdata_identity"]
            assert isinstance(original, list)
            bad = (
                None,
                [True, original[1]],
                [original[0], 1.0],
                [original[0]],
                [*original, 3],
                {"dev": original[0], "ino": original[1]},
                [original[0], 0],
                [original[0], -1],
            )
            for value in bad:
                with self.subTest(value=value):
                    with self.assertRaisesRegex(StartError, "RECOVERY_REQUIRED"):
                        readback_stopped(
                            runtime, root, control, {**record, "pgdata_identity": value}
                        )
            for value in (True, 1.0, "2", 1):
                with self.subTest(format=value):
                    with self.assertRaisesRegex(StartError, "RECOVERY_REQUIRED"):
                        readback_stopped(runtime, root, control, {**record, "format": value})
            with self.assertRaisesRegex(StartError, "RECOVERY_REQUIRED"):
                readback_stopped(runtime, root, control, {**record, "extra": "untrusted"})
            for phase in ([], {}, None, 2):
                with self.subTest(phase=phase):
                    with self.assertRaisesRegex(StartError, "RECOVERY_REQUIRED"):
                        readback_stopped(runtime, root, control, {**record, "phase": phase})

    def test_physical_pin_never_substitutes_a_missing_logical_system_id(self) -> None:
        with private_stop_fixture() as (_base, root, _foreign, control, record, runtime):
            for bad in (None, True, 12345, "not-decimal", "9" * 21):
                with self.subTest(system_id=bad):
                    with self.assertRaisesRegex(StartError, "RECOVERY_REQUIRED"):
                        readback_stopped(runtime, root, control, {**record, "system_id": bad})

    def test_copied_cluster_in_new_ordinary_directory_refuses_offline_readback(self) -> None:
        """Matching UID/mode/PG_VERSION and logical system_id do not bind the mount."""
        with private_stop_fixture() as (_base, root, _foreign, control, record, runtime):
            pg = root / "postgres"
            (pg / "18/docker").mkdir(parents=True)
            (pg / "18/docker/PG_VERSION").write_text("18\n")
            original = root / "original-postgres"
            pg.rename(original)
            pg.mkdir(mode=0o711)
            pg.chmod(0o711)
            (pg / "18/docker").mkdir(parents=True)
            (pg / "18/docker/PG_VERSION").write_bytes(
                (original / "18/docker/PG_VERSION").read_bytes()
            )
            self.assertEqual(
                (pg.lstat().st_uid, pg.lstat().st_mode & 0o777),
                (original.lstat().st_uid, original.lstat().st_mode & 0o777),
            )
            self.assertNotEqual([pg.lstat().st_dev, pg.lstat().st_ino], record["pgdata_identity"])
            self.assertEqual(
                (pg / "18/docker/PG_VERSION").read_bytes(),
                (original / "18/docker/PG_VERSION").read_bytes(),
            )
            with self.assertRaisesRegex(StartError, "RECOVERY_REQUIRED"):
                readback_stopped(runtime, root, control, record)
            self.assertEqual((original / "18/docker/PG_VERSION").read_text(), "18\n")

    def test_legacy_format_one_start_stop_refuse_without_mutating_receipt_or_data(self) -> None:
        """There is no provenance for adopting today's inode into an old receipt."""
        start_module = importlib.import_module("omnis_cli.start")
        stop_module = importlib.import_module("omnis_cli.stop")
        status_module = importlib.import_module("omnis_cli.status")
        for phase in ("READY", "STOPPING", "STOPPED"):
            with (
                self.subTest(phase=phase),
                private_stop_fixture() as (base, root, _foreign, control, record, runtime),
            ):
                pg = root / "postgres"
                (pg / "18/docker").mkdir(parents=True)
                (pg / "18/docker/PG_VERSION").write_text("18\n")
                record.pop("pgdata_identity")
                record["format"] = 1
                if phase == "READY":
                    for key in stop_module.STOP_FIELDS - start_module.READY_FIELDS:
                        record.pop(key)
                record["phase"] = phase
                path = root / "startup.json"
                write_record(path, record)
                before = path.read_bytes()
                data_before = (pg / "18/docker/PG_VERSION").read_bytes()
                with (
                    patch.dict(
                        os.environ,
                        {
                            "XDG_STATE_HOME": str(base / "s"),
                            "XDG_DATA_HOME": str(base / "d"),
                            "XDG_RUNTIME_DIR": "",
                        },
                    ),
                    patch.object(start_module, "ControlRuntime", return_value=runtime),
                    patch.object(stop_module, "ControlRuntime", return_value=runtime),
                    patch.object(status_module, "ControlRuntime", return_value=runtime),
                    patch.object(
                        runtime, "ids", side_effect=AssertionError("legacy reached resources")
                    ),
                ):
                    code, outcome = start_module.start_result(None)
                    self.assertEqual((code, outcome["reason"]), (4, "RECOVERY_REQUIRED"))
                    with self.assertRaisesRegex(StartError, "RECOVERY_REQUIRED"):
                        stop_module.stop_instance()
                    output = io.StringIO()
                    with contextlib.redirect_stdout(output):
                        status_code = status_module.status(as_json=True)
                    self.assertEqual(
                        (status_code, json.loads(output.getvalue())["reason"]),
                        (4, "RECOVERY_REQUIRED"),
                    )
                self.assertEqual(path.read_bytes(), before)
                self.assertEqual((pg / "18/docker/PG_VERSION").read_bytes(), data_before)
                self.assertFalse((root / "unreconciled.json").exists())
                self.assertFalse((root / "lifecycle.lock").exists())

    def test_db_unavailable_after_stopping_intent_is_emergency_not_stopped(self) -> None:
        """A failed DB readback must retain a blocker before owned paths are drained."""
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
            runtime.psql = lambda *_args: (_ for _ in ()).throw(
                StartError("LOCAL_SERVICE_COMMAND_FAILED", 3)
            )
            stop_module = importlib.import_module("omnis_cli.stop")
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
                patch.object(stop_module, "service_ids", return_value=ids),
                patch.object(stop_module, "_emergency_drain", side_effect=drain),
            ):
                with self.assertRaisesRegex(StartError, "DRAIN_UNCERTAIN"):
                    stop_module.stop_instance()
            self.assertEqual(seen, ["UNCERTAIN"])
            self.assertEqual(read_record(journal)["phase"], "UNCERTAIN")

    def test_emergency_inventory_failure_still_closes_local_ready_reuse(self) -> None:
        """A transient Docker inventory outage cannot leave READY reusable."""
        with private_stop_fixture() as (_base, root, _foreign, control, record, runtime):
            stop_module = importlib.import_module("omnis_cli.stop")
            start_module = importlib.import_module("omnis_cli.start")
            for key in stop_module.STOP_FIELDS - start_module.READY_FIELDS:
                record.pop(key)
            record["phase"] = "READY"
            journal = root / "startup.json"
            write_record(journal, record)
            runtime.ids = lambda: (_ for _ in ()).throw(ControlUnavailable())
            with self.assertRaises(ControlUnavailable):
                stop_module._emergency_stop(runtime, root, control, record)
            self.assertEqual(read_record(journal)["phase"], "UNCERTAIN")
            marker = read_record(root / "unreconciled.json")
            self.assertEqual(marker["attempt"], record["attempt"])

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
            pg = root / "postgres"
            saved = root / "saved-postgres"
            pg.rename(saved)
            pg.symlink_to(foreign, target_is_directory=True)
            with self.assertRaises(StartError):
                readback_stopped(runtime, root, control, record)
            pg.unlink()
            saved.rename(pg)
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
