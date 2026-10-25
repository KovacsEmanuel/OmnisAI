"""Explicit T1 recovery; synthetic daemon is never physical recovery evidence."""

import contextlib
import fcntl
import io
import json
import os
import socket
import unittest
from unittest.mock import patch

from omnis_cli.main import main
from stop_owner_fixture import Fixture
from test_stop import private_stop_fixture


class RecoveryFixture(Fixture):
    """Existing Stop fixture; SQL/control/start doubles, real validators and owner."""

    def prepare(self, *, live_control=False):
        import hashlib
        import time
        from dataclasses import replace
        from pathlib import Path
        from unittest.mock import Mock
        from zipfile import ZipFile

        from omnis_cli.compose import _put_record
        from omnis_cli.lifecycle import read_record, write_record
        from omnis_cli.start import READY_FIELDS
        from omnis_cli.start_runtime import private_identity
        from omnis_cli.stop_owner import _load_runtime, _view

        release = self.runtime.release
        wheel = release / "api/omnis_api-0.1.0-py3-none-any.whl"
        with ZipFile(wheel, "w") as archive:
            for name in (
                "modules/settings/provider_key_models.py",
                "modules/settings/provider_key_routes.py",
                "modules/settings/provider_key_service.py",
                "modules/settings/provider_vault.py",
                "migrations/versions/0014_provider_settings.py",
                "migrations/versions/0015_model_test_v2.py",
                "modules/runs/model_test_runtime.py",
                "modules/runs/model_test_contract.py",
                "modules/runs/model_test_store.py",
                "supervisor/model_sender.py",
            ):
                archive.write(
                    Path(__file__).resolve().parents[2] / "api/src/omnis" / name, "omnis/" + name
                )
            archive.writestr(
                "omnis_api-0.1.0.dist-info/METADATA",
                "Requires-Dist: cryptography==50.0.1\nRequires-Dist: openai==2.24.0\nRequires-Dist: httpx==0.28.1\nRequires-Dist: httpcore==1.0.9\n",
            )
        manifest = json.loads((release / "release.json").read_bytes())
        manifest.update(format=3, profile="t1-provider-settings")
        manifest["files"]["api/" + wheel.name] = hashlib.sha256(wheel.read_bytes()).hexdigest()
        (release / "release.json").write_text(json.dumps(manifest))
        self.digest = hashlib.sha256((release / "release.json").read_bytes()).hexdigest()
        receipt = replace(
            self.runtime.receipt, profile="t1-provider-settings", manifest_sha256=self.digest
        )
        (self.data / "omnis/image.json").unlink()
        _put_record(self.data / "omnis/image.json", receipt, complete=True)
        self.record = {k: v for k, v in self.record.items() if k in READY_FIELDS}
        self.record.update(format=5, phase="READY", release_digest=self.digest)
        for name, field in (("vault", "vault_identity"), ("vault-key", "vault_key_identity")):
            (self.root / name).mkdir(mode=0o700)
            self.record[field] = private_identity(self.root / name)
        (self.root / "vault/sentinel").write_bytes(b"retained")
        item = self.items[self.ids["supervisor"]]
        item["Config"]["Env"] += [
            "OMNIS_VAULT_DIR=/vault",
            "OMNIS_VAULT_KEY_DIR=/vault-key",
            "OMNIS_MODEL_EGRESS_DIR=/vault",
        ]
        for name in ("vault", "vault-key"):
            item["Mounts"].append(
                dict(
                    Type="bind",
                    Source=str(self.root / name),
                    Destination="/" + name,
                    RW=True,
                    Propagation="rprivate",
                )
            )
        item["State"].update(Running=False, Status="exited", Pid=0, Dead=False, Error="")
        if not live_control:
            self.sockets["control"].close()  # Keep the original inode, not a live listener.
        # The fixture's held process is not a container. State is an explicit daemon double.
        write_record(self.root / "startup.json", self.record, replace=True)
        self.runtime = _load_runtime(self.data, self.record, time.monotonic() + 30)
        view = _view(self.runtime)
        for name in ("inspect", "ids", "network", "check_daemon"):
            setattr(self.runtime, name, getattr(view, name))
        self.runtime.run = Mock(side_effect=self.start)
        self.runtime.psql = Mock(side_effect=self.psql)
        self.environment = dict(
            XDG_CONFIG_HOME=str(self.base / "config"),
            XDG_DATA_HOME=str(self.data),
            XDG_STATE_HOME=str(self.base / "unused-state"),
        )
        self.old_owner = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
        self.new_owner = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
        self.implicit = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
        self.starts, self.ops = 0, []
        self.current = dict(
            instance_id=self.record["instance_id"],
            generation=2,
            admission_open=False,
            shutdown_command_id=self.implicit,
            quiesced_generation=2,
            supervisor_epoch=2,
            supervisor_ready=True,
            shutdown_finalized=False,
            assessment_ready=False,
            dashboard_ready=False,
        )
        self.journal = lambda: read_record(self.root / "startup.json")

    def start(self, *args, **kwargs):
        import socket
        import subprocess

        from omnis_cli.lifecycle import read_record

        assert args == ("start", self.ids["supervisor"]) and kwargs["effect"] is True
        with (self.control / "control.lock").open("r+") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert self.journal()["phase"] == "RECOVERING"
        assert (
            read_record(self.root / ("recovery-" + self.attempt + ".json"))["original"]
            == self.record
        )
        self.starts += 1
        assert self.starts == 1
        self.items[self.ids["supervisor"]]["State"].update(
            Running=True, Status="running", Pid=self.processes["supervisor"].pid
        )
        old = self.sockets["control"]
        (self.control / "control.sock").unlink()
        fresh = socket.socket(socket.AF_UNIX)
        fresh.bind(str(self.control / "control.sock"))
        (self.control / "control.sock").chmod(0o600)
        fresh.listen()
        self.sockets["control"] = fresh
        old.close()
        (self.control / "control.cap").write_text("c" * 64)
        return subprocess.CompletedProcess(args, 0, self.ids["supervisor"] + "\n", "")

    def psql(self, ident, query):
        assert ident == self.ids["db"] and query.startswith("SELECT ")
        if query == "SELECT system_identifier FROM pg_control_system()":
            return "12345"
        if query == "SELECT instance_id FROM instance_control WHERE id = 1":
            return self.record["instance_id"]
        if query == "SELECT version_num FROM alembic_version":
            return "0015_model_test_v2"
        if "json_build_object" in query:
            return json.dumps(
                dict(owner=self.old_owner if not self.starts else self.new_owner, eligible=True)
            )
        if "SELECT generation::text" in query:
            record = self.journal()
            return f"3|f|{record['stop_command']}|3|1|2"
        raise AssertionError(query)

    def control_request(self, directory, command, **kwargs):
        assert directory == self.control
        op = command["op"]
        self.ops.append(op)
        if op == "shutdown":
            assert command["expected_generation"] == 2
            self.current.update(
                generation=3, shutdown_command_id=command["command_id"], quiesced_generation=3
            )
        elif op == "finalize":
            assert command["expected_generation"] == 3
            self.current["shutdown_finalized"] = True
        elif op == "arm_stop":
            return {k: v for k, v in command.items() if k != "op"} | dict(
                version=1, state="STOP_PENDING", owner_uuid=self.new_owner
            )
        else:
            assert op == "status", "No OPEN/Pair/provider operations permitted"
        return dict(self.current)


class RecoverTests(unittest.TestCase):
    def invoke(self, fixture):
        import importlib
        import subprocess

        import omnis_cli.recover as recovery
        from stop_owner_fixture import owner_test_argv

        stop = importlib.import_module("omnis_cli.stop")
        popen = subprocess.Popen

        def spawn(argv, **kwargs):
            if "omnis_cli.stop_owner" in argv:
                argv = owner_test_argv(argv)
            return popen(argv, **kwargs)

        with (
            patch.dict(os.environ, fixture.environment),
            patch.object(stop, "ControlRuntime", return_value=fixture.runtime),
            patch.object(stop, "state_dir", return_value=fixture.root),
            patch.object(stop, "control_dir", return_value=fixture.control),
            patch.object(recovery, "request", side_effect=fixture.control_request),
            patch.object(stop, "request", side_effect=fixture.control_request),
            patch.object(
                recovery, "http_probe", return_value=b"SYNTHETIC_RELEASE_FIXTURE_NOT_AN_ARTIFACT"
            ),
            patch("subprocess.Popen", side_effect=spawn),
        ):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = main(["recover", "--json"])
        return code, json.loads(output.getvalue())

    def test_busy_control_ipc_refuses_before_intent(self):
        import omnis_cli.recover as recovery
        from omnis_cli.lifecycle import StartError, socket_identity

        for fault, reason in (
            ("lock", "IPC_OWNERSHIP_UNCERTAIN"),
            ("socket", "IPC_PEER_STILL_LIVE"),
        ):
            with self.subTest(fault=fault):
                fixture = RecoveryFixture()
                try:
                    fixture.prepare(live_control=fault == "socket")
                    with (fixture.control / "control.lock").open("r+") as lock:
                        if fault == "lock":
                            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                            with (fixture.control / "control.lock").open("r+") as challenger:
                                with self.assertRaises(BlockingIOError):
                                    fcntl.flock(challenger, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        else:
                            with socket.socket(socket.AF_UNIX) as peer:
                                peer.settimeout(0.2)
                                peer.connect(str(fixture.control / "control.sock"))
                        path = fixture.root / "startup.json"
                        before = path.read_bytes()
                        ipc = {
                            name: (fixture.control / name).stat().st_ino
                            for name in ("control.lock", "control.sock", "control.cap")
                        }
                        fixture.runtime.run.side_effect = StartError("TEST_START_INTERCEPTED", 4)
                        with patch.object(
                            recovery, "write_record", wraps=recovery.write_record
                        ) as writes:
                            code, result = self.invoke(fixture)
                        fixture.runtime.run.assert_not_called()
                        writes.assert_not_called()
                        self.assertEqual((code, result["reason"]), (4, reason))
                        self.assertEqual(result["state"], "UNCERTAIN")
                        self.assertEqual(path.read_bytes(), before)
                        self.assertFalse(list(fixture.root.glob("recovery-*.json")))
                        self.assertEqual(fixture.starts, 0)
                        self.assertEqual(fixture.ops, [])
                        self.assertFalse(
                            any(row.startswith(("POST", "DELETE")) for row in fixture.requests)
                        )
                        self.assertEqual(
                            socket_identity(fixture.control / "control.sock"),
                            fixture.record["control_socket"],
                        )
                        self.assertEqual(
                            {name: (fixture.control / name).stat().st_ino for name in ipc}, ipc
                        )
                        self.assertEqual((fixture.control / "control.cap").read_text(), "b" * 64)
                finally:
                    fixture.close()

    def test_control_ipc_becoming_busy_after_intent_prevents_start(self):
        import omnis_cli.recover as recovery
        from omnis_cli.lifecycle import StartError, read_record, socket_identity, write_record

        for fault, reason in (
            ("lock", "IPC_OWNERSHIP_UNCERTAIN"),
            ("socket", "IPC_PEER_STILL_LIVE"),
        ):
            with self.subTest(fault=fault):
                fixture = RecoveryFixture()
                try:
                    if fault == "socket":
                        fixture.sockets["control"].close()
                        (fixture.control / "control.sock").unlink()
                        bound = socket.socket(socket.AF_UNIX)
                        fixture.sockets["control"] = bound
                        bound.bind(str(fixture.control / "control.sock"))
                        (fixture.control / "control.sock").chmod(0o600)
                        fixture.record["control_socket"] = socket_identity(
                            fixture.control / "control.sock"
                        )
                    fixture.prepare(live_control=fault == "socket")
                    with (fixture.control / "control.lock").open("r+") as lock:

                        def persist(path, value, *, fault=fault, fixture=fixture, **kwargs):
                            write_record(path, value, **kwargs)
                            if value.get("phase") == "RECOVERING":
                                self.assertEqual(read_record(path), value)
                                if fault == "lock":
                                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                                else:
                                    fixture.sockets["control"].listen()

                        fixture.runtime.run.side_effect = StartError("TEST_START_INTERCEPTED", 4)
                        with patch.object(recovery, "write_record", side_effect=persist):
                            code, result = self.invoke(fixture)
                        fixture.runtime.run.assert_not_called()
                        self.assertEqual((code, result["reason"]), (4, reason))
                        self.assertEqual(result["state"], "UNCERTAIN")
                        self.assertEqual(
                            fixture.journal(), {**fixture.record, "phase": "RECOVERING"}
                        )
                        intent = read_record(fixture.root / f"recovery-{fixture.attempt}.json")
                        self.assertEqual(intent["original"], fixture.record)
                        self.assertEqual(fixture.starts, 0)
                        self.assertEqual(fixture.ops, [])
                        self.assertFalse(
                            any(row.startswith(("POST", "DELETE")) for row in fixture.requests)
                        )
                        self.assertFalse((fixture.root / "unreconciled.json").exists())
                    self.assertEqual(self.invoke(fixture)[1]["reason"], "RECOVERY_REQUIRED")
                    fixture.runtime.run.assert_not_called()
                finally:
                    fixture.close()

    def test_uncertain_control_probe_releases_lock_without_effects(self):
        import errno

        import omnis_cli.recover as recovery
        from omnis_cli.lifecycle import StartError

        for fault in (TimeoutError(), OSError(errno.EACCES, "denied"), "lock", "socket"):
            with self.subTest(fault=fault):
                fixture = RecoveryFixture()
                try:
                    fixture.prepare()
                    connect = socket.socket.connect

                    def probe(peer, address, *, fault=fault, fixture=fixture, connect=connect):
                        if address == str(fixture.control / "control.sock"):
                            self.assertGreater(peer.gettimeout(), 0)
                            self.assertLessEqual(peer.gettimeout(), 0.2)
                            if isinstance(fault, OSError):
                                raise fault
                            path = fixture.control / (
                                "control.lock" if fault == "lock" else "control.sock"
                            )
                            path.rename(path.with_suffix(".retained"))
                            if fault == "lock":
                                path.touch(mode=0o600)
                            else:
                                with socket.socket(socket.AF_UNIX) as replacement:
                                    replacement.bind(str(path))
                                    path.chmod(0o600)
                        return connect(peer, address)

                    fixture.runtime.run.side_effect = StartError("TEST_START_INTERCEPTED", 4)
                    with (
                        patch.object(socket.socket, "connect", probe),
                        patch.object(
                            recovery, "write_record", wraps=recovery.write_record
                        ) as writes,
                    ):
                        code, result = self.invoke(fixture)
                    fixture.runtime.run.assert_not_called()
                    writes.assert_not_called()
                    self.assertEqual(code, 4)
                    self.assertEqual(
                        result["reason"],
                        "IPC_OWNERSHIP_UNCERTAIN"
                        if isinstance(fault, OSError)
                        else "IPC_IDENTITY_MISMATCH",
                    )
                    path = fixture.control / (
                        "control.retained" if fault == "lock" else "control.lock"
                    )
                    with path.open("r+") as lock:
                        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                finally:
                    fixture.close()

    def test_denials_before_intent_preserve_resources_and_journal(self):
        from dataclasses import replace

        from omnis_cli.lifecycle import StartError, read_record, write_record

        for fault, reason in (
            ("healthy", "SUPERVISOR_NOT_DEAD"),
            ("live_lease", "RECOVERY_AUTHORITY_UNVERIFIED"),
            ("foreign_cid", "RESOURCE_IDENTITY_MISMATCH"),
            ("daemon", "DOCKER_IDENTITY_MISMATCH"),
            ("storage", "RECOVERY_REQUIRED"),
            ("profile", "IMAGE_PROFILE_MISMATCH"),
            ("socket", "IPC_IDENTITY_MISMATCH"),
            ("cap", "RECOVERY_METADATA_INVALID"),
            ("unreconciled", "RECOVERY_REQUIRED"),
            ("malformed", "RECOVERY_REQUIRED"),
        ):
            with self.subTest(fault=fault):
                fixture = RecoveryFixture()
                try:
                    fixture.prepare()
                    path = fixture.root / "startup.json"
                    if fault == "healthy":
                        fixture.items[fixture.ids["supervisor"]]["State"]["Running"] = True
                    elif fault == "live_lease":
                        fixture.runtime.psql.side_effect = lambda cid, q, fixture=fixture: (
                            json.dumps(dict(owner=fixture.old_owner, eligible=False))
                            if "json_build_object" in q
                            else fixture.psql(cid, q)
                        )
                    elif fault == "foreign_cid":
                        changed = read_record(path)
                        changed["containers"]["supervisor"] = "9" * 64
                        write_record(path, changed, replace=True)
                    elif fault == "daemon":
                        fixture.runtime.ids = lambda: (_ for _ in ()).throw(
                            StartError("DOCKER_IDENTITY_MISMATCH", 4)
                        )
                    elif fault == "storage":
                        (fixture.root / "postgres").rename(fixture.root / "retained-postgres")
                        (fixture.root / "postgres").mkdir(mode=0o711)
                        (fixture.root / "postgres").chmod(0o711)
                    elif fault == "profile":
                        fixture.runtime.receipt = replace(fixture.runtime.receipt, profile=None)
                    elif fault == "socket":
                        changed = read_record(path)
                        changed["control_socket"] = [1, 2]
                        write_record(path, changed, replace=True)
                    elif fault == "cap":
                        (fixture.control / "control.cap").write_text("not-a-capability")
                    elif fault == "unreconciled":
                        write_record(fixture.root / "unreconciled.json", {"state": "UNCERTAIN"})
                    elif fault == "malformed":
                        changed = read_record(path)
                        changed["generation"] = True
                        write_record(path, changed, replace=True)
                    before = path.read_bytes()
                    code, result = self.invoke(fixture)
                    self.assertEqual((code, result["reason"]), (4, reason))
                    self.assertEqual(path.read_bytes(), before)
                    self.assertEqual(fixture.starts, 0)
                    self.assertEqual(fixture.ops, [])
                    self.assertFalse(list(fixture.root.glob("recovery-*.json")))
                    self.assertFalse(
                        any(row.startswith(("POST", "DELETE")) for row in fixture.requests)
                    )
                finally:
                    fixture.close()

    def test_uncertain_start_and_barrier_are_never_retried_or_emergency_stopped(self):
        from omnis_cli.lifecycle import StartError

        for fault in (
            "ack",
            "exception",
            "generation",
            "epoch",
            "owner",
            "admission",
            "drain",
            "shutdown_ack",
        ):
            with self.subTest(fault=fault):
                fixture = RecoveryFixture()
                try:
                    fixture.prepare()
                    if fault in {"ack", "exception"}:

                        def start(*args, fixture=fixture, fault=fault, **kwargs):
                            result = fixture.start(*args, **kwargs)
                            if fault == "exception":
                                raise StartError("READBACK_LOST", 4)
                            fixture.runtime.uncertain = True
                            return result

                        fixture.runtime.run.side_effect = start
                    elif fault in {"generation", "epoch"}:
                        fixture.current[
                            "generation" if fault == "generation" else "supervisor_epoch"
                        ] += 1
                    elif fault == "owner":
                        fixture.new_owner = fixture.old_owner
                    elif fault == "admission":
                        fixture.current["admission_open"] = True
                    elif fault == "drain":
                        fixture.current["quiesced_generation"] = None
                    else:
                        from omnis_cli.control import ControlUnavailable

                        original = fixture.control_request

                        def control(directory, command, original=original, **kwargs):
                            result = original(directory, command, **kwargs)
                            if command["op"] == "shutdown":
                                raise ControlUnavailable()
                            return result

                        fixture.control_request = control
                    code, result = self.invoke(fixture)
                    self.assertNotEqual(code, 0)
                    self.assertEqual(result["state"], "UNCERTAIN")
                    self.assertEqual(fixture.starts, 1)
                    self.assertIn(fixture.journal()["phase"], ("RECOVERING", "STOPPING"))
                    self.assertEqual(len(list(fixture.root.glob("recovery-*.json"))), 1)
                    self.assertFalse((fixture.root / "unreconciled.json").exists())
                    self.assertFalse(
                        any(row.startswith(("POST", "DELETE")) for row in fixture.requests)
                    )
                    self.assertNotEqual(self.invoke(fixture)[0], 0)
                    self.assertEqual(fixture.starts, 1)
                finally:
                    fixture.close()

    def test_queued_start_stop_recover_refuse_interrupted_intent(self):
        import importlib
        import signal
        import threading
        from concurrent.futures import ThreadPoolExecutor

        from omnis_cli.lifecycle import StartError, write_record

        for sig in (signal.SIGINT, signal.SIGTERM):
            previous = signal.signal(sig, signal.SIG_DFL)
            self.addCleanup(signal.signal, sig, previous)

        fixture = RecoveryFixture()
        self.addCleanup(fixture.close)
        fixture.prepare()
        relocated = fixture.base / "control"
        fixture.control.rename(relocated)
        fixture.control = relocated
        fixture.record["control_dir"] = str(relocated)
        for item in fixture.items.values():
            for mount in item["Mounts"]:
                if mount["Destination"] == "/run/omnis-control":
                    mount["Source"] = str(relocated)
        write_record(fixture.root / "startup.json", fixture.record, replace=True)
        start = importlib.import_module("omnis_cli.start")
        stop = importlib.import_module("omnis_cli.stop")
        entered = [threading.Event() for _ in range(3)]
        local = threading.local()

        def runtime(*args):
            entered[local.index].set()
            return fixture.runtime

        def contender(index):
            local.index = index
            try:
                if index == 0:
                    start.start_instance()
                else:
                    stop.stop_instance(recover=index == 2)
            except StartError as error:
                return error.reason
            return "UNEXPECTED_SUCCESS"

        with (
            patch.dict(os.environ, fixture.environment),
            patch.object(start, "state_dir", return_value=fixture.root),
            patch.object(start, "control_dir", return_value=fixture.control),
            patch.object(stop, "state_dir", return_value=fixture.root),
            patch.object(stop, "control_dir", return_value=fixture.control),
            patch.object(start, "ControlRuntime", side_effect=runtime),
            patch.object(stop, "ControlRuntime", side_effect=runtime),
            ThreadPoolExecutor(max_workers=3) as pool,
        ):
            with fixture.original_locks():
                futures = [pool.submit(contender, index) for index in range(3)]
                self.assertTrue(all(event.wait(3) for event in entered))
                write_record(
                    fixture.root / f"recovery-{fixture.attempt}.json", {"original": fixture.record}
                )
            self.assertEqual(
                [future.result(timeout=5) for future in futures], ["RECOVERY_INTERRUPTED"] * 3
            )
        self.assertEqual(fixture.starts, 0)
        self.assertEqual(fixture.journal(), fixture.record)

    def test_existing_stop_serializers_fit_at_maximal_generations(self):
        from omnis_cli.control import _stop_binding
        from omnis_cli.lifecycle import write_record
        from omnis_cli.stop_owner import prepare_stop_inventory
        from omnis_cli.stop_receipt import encoded, validate_grant

        fixture = RecoveryFixture()
        self.addCleanup(fixture.close)
        fixture.prepare()
        record = dict(
            fixture.record,
            phase="STOPPING",
            generation=9223372036854775805,
            supervisor_epoch=9223372036854775807,
            stop_expected=9223372036854775805,
            stop_command=fixture.implicit,
            finalize_command=fixture.new_owner,
            stop_generation=9223372036854775806,
            finalized_generation=9223372036854775806,
            teardown_completed=[],
        )
        fixture.items[fixture.ids["supervisor"]]["State"].update(
            Running=True, Status="running", Pid=fixture.processes["supervisor"].pid
        )
        write_record(fixture.root / "startup.json", record, replace=True)
        inventory = prepare_stop_inventory(fixture.runtime, fixture.root, fixture.control, record)
        command = dict(
            op="arm_stop",
            instance_id=record["instance_id"],
            command_id=record["stop_command"],
            finalize_command_id=record["finalize_command"],
            generation=record["stop_generation"],
            owner_epoch=record["supervisor_epoch"],
            daemon_id=fixture.runtime.receipt.docker_id,
            inventory=inventory,
        )
        grant = dict(
            _stop_binding(command), version=1, state="STOP_PENDING", owner_uuid=fixture.new_owner
        )
        validate_grant(grant, record, inventory)
        self.assertLessEqual(len(encoded(inventory)), 2900)
        self.assertLessEqual(len(encoded(grant)), 3600)
        self.assertLessEqual(
            len(json.dumps(dict(version=1, capability="a" * 64, command=command)).encode()) + 1,
            4096,
        )
        handoff = dict(
            root=str(fixture.root),
            control=str(fixture.control),
            data_home=str(fixture.data),
            record=record,
            grant=grant,
            deadline_ns=9223372036854775807,
            guard_fds=[2147483647, 2147483647],
        )
        self.assertLessEqual(len(encoded(handoff)), 16384)
        oversized = dict(command, inventory={"oversized": "x" * 4096})
        from omnis_cli.control import ControlUnavailable

        with self.assertRaises(ControlUnavailable):
            _stop_binding(oversized)

    def test_journal_drift_before_start_has_no_daemon_effect(self):
        import omnis_cli.recover as recovery
        from omnis_cli.lifecycle import write_record

        fixture = RecoveryFixture()
        self.addCleanup(fixture.close)
        fixture.prepare()
        original = recovery._owner
        calls = 0

        def read_owner(*args, **kwargs):
            nonlocal calls
            result = original(*args, **kwargs)
            calls += 1
            if calls == 2:
                changed = fixture.journal()
                changed["phase"] = "UNCERTAIN"
                write_record(fixture.root / "startup.json", changed, replace=True)
            return result

        with patch.object(recovery, "_owner", side_effect=read_owner):
            code, result = self.invoke(fixture)
        self.assertEqual((code, result["reason"]), (4, "RECOVERY_AUTHORITY_CHANGED"))
        self.assertEqual(fixture.starts, 0)

    def test_explicit_recovery_reaches_real_stop_owner_completion(self):
        from omnis_cli.lifecycle import read_record, socket_identity

        fixture = RecoveryFixture()
        self.addCleanup(fixture.close)
        fixture.prepare()
        self.assertEqual(
            socket_identity(fixture.control / "control.sock"), fixture.record["control_socket"]
        )
        with socket.socket(socket.AF_UNIX) as peer:
            peer.settimeout(0.2)
            with self.assertRaises(ConnectionRefusedError):
                peer.connect(str(fixture.control / "control.sock"))
        code, result = self.invoke(fixture)
        self.assertEqual((code, result["state"]), (0, "STOPPED"))
        stopped = read_record(fixture.root / "startup.json")
        self.assertEqual(stopped["phase"], "STOPPED")
        self.assertEqual(stopped["supervisor_epoch"], 2)
        self.assertEqual(stopped["stop_generation"], 3)
        self.assertEqual(fixture.starts, 1)
        self.assertEqual(
            fixture.ops, ["status", "status", "shutdown", "status", "finalize", "arm_stop"]
        )
        self.assertFalse(fixture.items)
        self.assertIsNone(fixture.network_item)
        self.assertTrue((fixture.root / "postgres").is_dir())
        self.assertEqual((fixture.root / "vault/sentinel").read_bytes(), b"retained")

    def test_recover_is_explicit_and_refuses_non_t1_before_daemon(self):
        from omnis_cli.lifecycle import write_record

        with private_stop_fixture() as (base, root, _foreign, _control, record, _runtime):
            write_record(root / "startup.json", record)
            before = (root / "startup.json").read_bytes()
            with patch.dict(
                os.environ,
                {
                    "XDG_STATE_HOME": str(base / "s"),
                    "XDG_DATA_HOME": str(base / "d"),
                    "XDG_RUNTIME_DIR": "",
                    "XDG_CONFIG_HOME": str(base / "config"),
                },
            ):
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    code = main(["recover", "--json"])
                self.assertEqual(code, 4)
                self.assertEqual(json.loads(output.getvalue())["reason"], "RECOVERY_REQUIRED")
            self.assertEqual((root / "startup.json").read_bytes(), before)
            self.assertFalse((root / "lifecycle.lock").exists())
