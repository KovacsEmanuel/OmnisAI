"""A disposable PostgreSQL gate must never adopt an existing data root."""

import json
import os
import runpy
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[2] / "ops/run_test_db_gate.py"


def _render_config(paths):
    env = {
        "PATH": os.environ.get("PATH", ""),
        "OMNIS_TEST_PROJECT": "omnis-p01-static-contract",
        "OMNIS_TEST_UID": str(os.getuid()),
        "OMNIS_TEST_GID": str(os.getgid()),
        "OMNIS_TEST_DATA_DIR": str(paths.data),
        "OMNIS_TEST_SOCKET_DIR": str(paths.socket),
        "OMNIS_TEST_PASSWORD_FILE": str(paths.password),
    }
    completed = subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            str(SCRIPT.with_name("compose.test.yaml")),
            "config",
            "--format",
            "json",
        ],
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert completed.returncode == 0, "test Compose contract did not render"
    return json.loads(completed.stdout)


class SafeTestDatabaseGateTests(unittest.TestCase):
    def test_attestor_binds_private_manifest_socket_and_runtime_identity(self) -> None:
        import socket

        module = runpy.run_path(str(SCRIPT))
        self.assertTrue("attest_fixture" in module, "Shared attestor must exist before fixture DDL")
        attest = module["attest_fixture"]
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
            paths = module["prepare_paths"](Path(name) / "db")
            manifest = paths.root / "fixture.json"
            payload = {
                "schema_version": 1,
                "root": str(paths.root),
                "project": "omnis-p01-synthetic-uds",
                "container_id": "a" * 64,
                "image_id": "sha256:" + "b" * 64,
                "daemon_id": "synthetic-daemon",
                "docker_endpoint": f"unix://{paths.root / 'daemon.sock'}",
                "system_identifier": "123456789",
            }
            manifest.write_text(json.dumps(payload))
            manifest.chmod(0o600)
            uds = paths.socket / ".s.PGSQL.5432"
            with socket.socket(socket.AF_UNIX) as peer, socket.socket(socket.AF_UNIX) as daemon:
                daemon.bind(str(paths.root / "daemon.sock"))
                (paths.root / "daemon.sock").chmod(0o600)
                peer.bind(str(uds))
                uds.chmod(0o600)
                paths.socket.chmod(0o3775)

                def command(argv, _env, *, timeout=20):
                    self.assertIn("--host", argv)
                    return subprocess.CompletedProcess(argv, 0, "synthetic-daemon\n", "")

                with patch.dict(
                    attest.__globals__,
                    {
                        "_container": lambda *_args: {"State": {"Running": True}},
                        "_run": command,
                    },
                ):
                    result = attest(manifest)
                    self.assertEqual(result["socket_directory"], str(paths.socket))
                    self.assertEqual(result["system_identifier"], "123456789")
                    manifest.chmod(0o644)
                    with self.assertRaisesRegex(ValueError, "private|ownership"):
                        attest(manifest)

    def test_attestor_cli_refuses_foreign_path_without_startup(self) -> None:
        completed = subprocess.run(
            [sys.executable, "-I", str(SCRIPT), "--attest", "/not-an-owned-fixture.json"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        self.assertEqual(completed.returncode, 2)
        self.assertIn("PRIVATE_DB_ATTESTATION_BLOCKED", completed.stdout)
        self.assertNotIn("DISPOSABLE_CREATED", completed.stdout)

    def test_long_unix_path_is_refused_before_creating_a_directory(self) -> None:
        prepare = runpy.run_path(str(SCRIPT))["prepare_paths"]
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
            root = Path(name) / ("long" * 30)
            with self.assertRaises(ValueError):
                prepare(root)
            self.assertFalse(root.exists())

    def test_cleanup_checks_daemon_before_any_mutation(self) -> None:
        cleanup = runpy.run_path(str(SCRIPT))["cleanup_owned"]
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
            root = Path(name)
            paths = type("Paths", (), {"socket": root})()
            mutations = []

            def command(argv, _env, *, timeout=20):
                if "stop" in argv or "rm" in argv:
                    mutations.append(argv)
                if "info" in argv:
                    return subprocess.CompletedProcess(argv, 0, "different-daemon\n", "")
                return subprocess.CompletedProcess(argv, 0, "", "")

            with patch.dict(
                cleanup.__globals__,
                {
                    "_container": lambda *_args: {},
                    "_run": command,
                    "_find_owned": lambda *_args: [],
                    "_project_networks": lambda *_args: [],
                },
            ):
                self.assertFalse(
                    cleanup(
                        "a" * 64,
                        ["docker"],
                        {},
                        paths,
                        "omnis-p01-own",
                        "sha256:own",
                        "expected-daemon",
                    )
                )
            self.assertEqual(mutations, [])

    def test_full_check_cannot_become_a_dry_run_from_makeflags(self) -> None:
        env = {**os.environ, "MAKEFLAGS": "-n"}
        completed = subprocess.run(
            ["make", "check"],
            cwd=SCRIPT.parent.parent,
            env=env,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("verification", completed.stdout + completed.stderr)

    def test_gate_process_propagates_failure_without_a_database(self) -> None:
        module = runpy.run_path(str(SCRIPT))
        self.assertTrue("run_gate" in module, "The runner must execute the real gate")
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
            result = module["run_gate"](
                [sys.executable, "-I", "-c", "raise SystemExit(7)"],
                {"PATH": os.environ.get("PATH", "")},
                Path(name) / "gate.log",
                5,
            )
            self.assertEqual(result, 7)

    def test_gate_timeout_stops_its_process_group(self) -> None:
        module = runpy.run_path(str(SCRIPT))
        self.assertTrue("run_gate" in module, "The runner must bound the gate process group")
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
            root = Path(name)
            child_code = (
                "import signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);time.sleep(15)"
            )
            parent_code = (
                "import subprocess,sys,time,pathlib; "
                f"p=subprocess.Popen([sys.executable,'-I','-c',{child_code!r}]); "
                f"pathlib.Path({str(root / 'child.pid')!r}).write_text(str(p.pid)); "
                "time.sleep(20)"
            )
            result = module["run_gate"](
                [sys.executable, "-I", "-c", parent_code],
                {"PATH": os.environ.get("PATH", "")},
                root / "gate.log",
                1,
            )
            self.assertEqual(result, 124)
            pid = int((root / "child.pid").read_text())
            proc = Path(f"/proc/{pid}/stat")
            if proc.exists():
                self.assertEqual(proc.read_text().rsplit(")", 1)[1].split()[0], "Z")

    def test_gate_early_exit_does_not_leave_a_live_descendant(self) -> None:
        module = runpy.run_path(str(SCRIPT))
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
            root = Path(name)
            child_code = (
                "import signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);time.sleep(15)"
            )
            parent_code = (
                "import subprocess,sys,pathlib; "
                f"p=subprocess.Popen([sys.executable,'-I','-c',{child_code!r}]); "
                f"pathlib.Path({str(root / 'child.pid')!r}).write_text(str(p.pid))"
            )
            result = module["run_gate"](
                [sys.executable, "-I", "-c", parent_code],
                {"PATH": os.environ.get("PATH", "")},
                root / "gate.log",
                5,
            )
            self.assertEqual(result, 2)  # Cleanup of a leftover must not turn exit 0 into PASS.
            pid = int((root / "child.pid").read_text())
            try:
                state = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0]
            except FileNotFoundError:
                state = "absent"
            self.assertIn(state, ("Z", "absent"))

    def test_gate_stop_request_refuses_a_new_process(self) -> None:
        module = runpy.run_path(str(SCRIPT))
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
            stop = module["_request_stop"]
            stop(15, None)
            marker = Path(name) / "must-not-start"
            result = module["run_gate"](
                [sys.executable, "-c", f"open({str(marker)!r}, 'w').close()"],
                {},
                Path(name) / "gate.log",
                5,
            )
            self.assertEqual(result, 130)
            self.assertFalse(marker.exists())

    def test_sigterm_during_gate_is_handled_without_skipping_cleanup(self) -> None:
        import signal
        import threading

        module = runpy.run_path(str(SCRIPT))
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
            previous = signal.signal(signal.SIGTERM, module["_request_stop"])
            timer = threading.Timer(0.2, lambda: os.kill(os.getpid(), signal.SIGTERM))
            try:
                timer.start()
                result = module["run_gate"](
                    [sys.executable, "-I", "-c", "import time;time.sleep(15)"],
                    {"PATH": os.environ.get("PATH", "")},
                    Path(name) / "gate.log",
                    5,
                )
                self.assertEqual(result, 130)
            finally:
                timer.cancel()
                timer.join()
                signal.signal(signal.SIGTERM, previous)

    def test_targeted_runs_cannot_emit_a_canonical_gate_label(self) -> None:
        module = runpy.run_path(str(SCRIPT))
        self.assertTrue("gate_label" in module)
        self.assertEqual(module["gate_label"]("check-components"), "CANONICAL_GATE")
        self.assertEqual(module["gate_label"]("test-db-contract"), "TARGETED_GATE")
        self.assertEqual(module["gate_label"]("test-migrations"), "TARGETED_GATE")

    def _assert_detached_family_drained(self, case: str) -> None:
        import select
        import signal
        import time

        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
            root = Path(name)
            fifo = root / "rescue.fifo"
            os.mkfifo(fifo, 0o600)
            fuse = os.open(fifo, os.O_RDWR | os.O_NONBLOCK)
            release = root / "release"
            pidfiles = [root / "child.pid", root / "grandchild.pid"]
            grandchild_code = (
                "import os,signal,pathlib;signal.signal(signal.SIGTERM,signal.SIG_IGN);"
                f"f=os.open({str(fifo)!r},os.O_RDONLY);"
                f"pathlib.Path({str(pidfiles[1])!r}).write_text(str(os.getpid()));os.read(f,1)"
            )
            child_code = (
                "import os,signal,pathlib,subprocess,sys;signal.signal(signal.SIGTERM,signal.SIG_IGN);"
                f"subprocess.Popen([sys.executable,'-I','-c',{grandchild_code!r}],start_new_session=True);"
                f"f=os.open({str(fifo)!r},os.O_RDONLY);"
                f"pathlib.Path({str(pidfiles[0])!r}).write_text(str(os.getpid()));os.read(f,1)"
            )
            leader_code = (
                "import subprocess,sys,time,pathlib;"
                f"subprocess.Popen([sys.executable,'-I','-c',{child_code!r}],start_new_session=True);"
                f"p=pathlib.Path({str(release)!r});"
                "exec('while not p.exists(): time.sleep(0.01)')"
            )
            timeout = 3 if case == "timeout" else 15
            wrapper = (
                "import runpy,sys,os,pathlib,signal;"
                f"m=runpy.run_path({str(SCRIPT)!r});"
                "signal.signal(signal.SIGTERM,m['_request_stop']);"
                f"raise SystemExit(m['run_gate']([sys.executable,'-I','-c',{leader_code!r}],"
                f"dict(os.environ),pathlib.Path({str(root / 'gate.log')!r}),{timeout}))"
            )
            owner = subprocess.Popen([sys.executable, "-I", "-c", wrapper])
            handles = []
            foreign = None
            try:
                deadline = time.monotonic() + 2
                while (
                    not all(path.exists() and path.stat().st_size for path in pidfiles)
                    and time.monotonic() < deadline
                ):
                    self.assertIsNone(owner.poll(), "owned producer exited before its family")
                    time.sleep(0.01)
                for path in pidfiles:
                    pid = int(path.read_text())
                    fd = os.pidfd_open(pid)
                    handles.append(fd)
                    # Verify live kernel ancestry, not just the marker, before the trigger.
                    ancestor = pid
                    for _ in range(8):
                        fields = (
                            Path(f"/proc/{ancestor}/stat").read_text().rsplit(")", 1)[1].split()
                        )
                        ancestor = int(fields[1])
                        if ancestor == owner.pid:
                            break
                    self.assertEqual(ancestor, owner.pid)
                # This late sibling must never be adopted or killed by the gate owner.
                foreign = subprocess.Popen(
                    [sys.executable, "-I", "-c", "import time;time.sleep(30)"]
                )
                if case == "early":
                    release.touch()
                elif case == "term":
                    owner.send_signal(signal.SIGTERM)
                result = owner.wait(timeout=12)
                for fd in handles:
                    self.assertTrue(select.select([fd], [], [], 0.2)[0], "detached family survived")
                self.assertEqual(result, {"early": 2, "timeout": 124, "term": 130}[case])
                self.assertIsNone(foreign.poll(), "unrelated late child was touched")
            finally:
                # The observer-held writer is closed only AFTER testing the inner verdict.
                os.close(fuse)
                release.touch(exist_ok=True)
                if owner.poll() is None:
                    owner.terminate()
                    try:
                        owner.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        owner.kill()
                        owner.wait(timeout=5)
                try:
                    rescued = [bool(select.select([fd], [], [], 5)[0]) for fd in handles]
                    self.assertTrue(all(rescued), "independent rescue failed")
                finally:
                    for fd in handles:
                        os.close(fd)
                    if foreign is not None:
                        foreign.terminate()
                        foreign.wait(timeout=5)

    def test_detached_family_early_exit(self) -> None:
        self._assert_detached_family_drained("early")

    def test_detached_family_timeout(self) -> None:
        self._assert_detached_family_drained("timeout")

    def test_detached_family_sigterm(self) -> None:
        self._assert_detached_family_drained("term")

    def test_dead_adoptees_are_reaped_while_the_gate_is_still_running(self) -> None:
        module = runpy.run_path(str(SCRIPT))
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
            root = Path(name)
            pidfile = root / "dead.pid"
            intermediate = (
                "import subprocess,sys,pathlib;"
                "p=subprocess.Popen([sys.executable,'-I','-c','import time;time.sleep(0.1)'],start_new_session=True);"
                f"pathlib.Path({str(pidfile)!r}).write_text(str(p.pid))"
            )
            command = (
                "import subprocess,sys,pathlib,time;"
                f"subprocess.run([sys.executable,'-I','-c',{intermediate!r}],check=True);"
                f"pid=int(pathlib.Path({str(pidfile)!r}).read_text());p=pathlib.Path(f'/proc/{{pid}}');"
                "deadline=time.monotonic()+2;"
                "exec('while p.exists() and time.monotonic()<deadline: time.sleep(0.02)');"
                "raise SystemExit(1 if p.exists() else 0)"
            )
            self.assertEqual(
                module["run_gate"](
                    [sys.executable, "-I", "-c", command], dict(os.environ), root / "gate.log", 5
                ),
                0,
            )

    def test_gate_exception_never_authorizes_database_teardown(self) -> None:
        module = runpy.run_path(str(SCRIPT))
        prove = module["prove_private_fixture"]
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
            paths = module["prepare_paths"](Path(name) / "owned")
            started = [False]
            cleanup = []

            def command(argv, _env, *, timeout=20):
                if "info" in argv:
                    return subprocess.CompletedProcess(argv, 0, "daemon\n", "")
                if "image" in argv:
                    return subprocess.CompletedProcess(argv, 0, "sha256:owned amd64\n", "")
                if "config" in argv:
                    return subprocess.CompletedProcess(argv, 0, "{}", "")
                if "create" in argv:
                    return subprocess.CompletedProcess(argv, 1, "", "missing bind")
                if "up" in argv:
                    started[0] = True
                    return subprocess.CompletedProcess(argv, 0, "", "")
                raise AssertionError(f"Unexpected synthetic command: {argv}")

            def gate(*_args):
                raise PermissionError("synthetic signal failure before family readback")

            with patch.dict(
                prove.__globals__,
                {
                    "prepare_paths": lambda _root: paths,
                    "_preflight_gate": lambda uv: uv,
                    "_docker_endpoint": lambda _env: "unix:///run/synthetic.sock",
                    "_run": command,
                    "validate_compose_config": lambda *_args: None,
                    "_find_owned": lambda *_args: ["a" * 64] if started[0] else [],
                    "_project_networks": lambda *_args: [],
                    "_container": lambda *_args: {},
                    "_authenticated": lambda *_args: "123456789",
                    "attest_fixture": lambda *_args: {},
                    "_gate_environment": lambda *_args: {},
                    "run_gate": gate,
                    "cleanup_owned": lambda *_args: cleanup.append(True) or True,
                },
            ):
                self.assertEqual(prove("check-components", "uv", 10), 2)
            self.assertEqual(cleanup, [], "DB teardown preceded family drain")

    def test_rendered_private_compose_contract_is_accepted(self) -> None:
        module = runpy.run_path(str(SCRIPT))
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
            paths = module["prepare_paths"](Path(name) / "own-db")
            module["validate_compose_config"](_render_config(paths), paths)

    def test_prepares_only_a_new_private_root_and_refuses_reuse(self) -> None:
        prepare = runpy.run_path(str(SCRIPT))["prepare_paths"]
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
            root = Path(name) / "own-disposable-db"
            paths = prepare(root)
            self.assertEqual(paths.root, root)
            for path in (root, paths.data, paths.socket):
                info = path.lstat()
                self.assertTrue(stat.S_ISDIR(info.st_mode))
                self.assertEqual(info.st_uid, os.getuid())
                self.assertEqual(stat.S_IMODE(info.st_mode), 0o700)
            secret = paths.password.lstat()
            self.assertTrue(stat.S_ISREG(secret.st_mode))
            self.assertEqual(secret.st_uid, os.getuid())
            self.assertEqual(stat.S_IMODE(secret.st_mode), 0o600)
            sentinel = root / "keep"
            sentinel.write_text("unchanged")
            with self.assertRaises(ValueError):
                prepare(root)
            self.assertEqual(sentinel.read_text(), "unchanged")

    def test_rejects_compose_host_network_before_launch(self) -> None:
        validate = runpy.run_path(str(SCRIPT))["validate_compose_config"]
        with self.assertRaisesRegex(ValueError, "network"):
            validate({"services": {"db": {"network_mode": "host"}}})

    def test_trust_local_auth_is_rejected_before_launch(self) -> None:
        module = runpy.run_path(str(SCRIPT))
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
            paths = module["prepare_paths"](Path(name) / "own-db")
            config = _render_config(paths)
            config["services"]["db"]["environment"]["POSTGRES_INITDB_ARGS"] = (
                "--auth-local=trust --auth-host=scram-sha-256"
            )
            with self.assertRaisesRegex(ValueError, "authentication"):
                module["validate_compose_config"](config, paths)

    def test_capability_readdition_is_rejected_before_launch(self) -> None:
        module = runpy.run_path(str(SCRIPT))
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
            paths = module["prepare_paths"](Path(name) / "own-db")
            config = _render_config(paths)
            config["services"]["db"]["cap_add"] = ["SYS_ADMIN"]
            with self.assertRaisesRegex(ValueError, "confinement"):
                module["validate_compose_config"](config, paths)

    def test_cleanup_retries_attestation_and_attempts_owned_stop_and_rm(self) -> None:
        module = runpy.run_path(str(SCRIPT))
        cleanup = module["cleanup_owned"]
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
            paths = module["prepare_paths"](Path(name) / "own-db")
            cid = "a" * 64
            attempts: list[str] = []
            pins = [0]

            def attest(*_args):
                pins[0] += 1
                if pins[0] == 1:
                    raise ValueError("injected transient inspect error")
                return {}

            def command(argv, _env, *, timeout=20):
                if "stop" in argv:
                    attempts.append("stop")
                elif "rm" in argv:
                    attempts.append("rm")
                if "inspect" in argv:
                    return subprocess.CompletedProcess(argv, 1, "", f"No such object: {cid}")
                if "info" in argv:
                    return subprocess.CompletedProcess(argv, 0, "daemon\n", "")
                return subprocess.CompletedProcess(argv, 0, "", "")

            with patch.dict(
                cleanup.__globals__,
                {
                    "_container": attest,
                    "_run": command,
                    "_find_owned": lambda *_args: [],
                    "_project_networks": lambda *_args: [],
                },
            ):
                clean = cleanup(cid, ["docker"], {}, paths, "omnis-p01-own", "sha256:own", "daemon")
            self.assertFalse(clean)  # Lost one identity readback even though rescue succeeded.
            self.assertGreaterEqual(pins[0], 2)
            self.assertEqual(attempts, ["stop", "rm"])

    def test_generic_inspect_error_never_counts_as_absence(self) -> None:
        module = runpy.run_path(str(SCRIPT))
        cleanup = module["cleanup_owned"]
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
            paths = module["prepare_paths"](Path(name) / "own-db")

            def command(argv, _env, *, timeout=20):
                if "inspect" in argv:
                    return subprocess.CompletedProcess(argv, 1, "", "permission denied")
                if "info" in argv:
                    return subprocess.CompletedProcess(argv, 0, "daemon\n", "")
                return subprocess.CompletedProcess(argv, 0, "", "")

            with patch.dict(
                cleanup.__globals__,
                {
                    "_container": lambda *_args: {},
                    "_run": command,
                    "_find_owned": lambda *_args: [],
                    "_project_networks": lambda *_args: [],
                },
            ):
                clean = cleanup(
                    "a" * 64, ["docker"], {}, paths, "omnis-p01-own", "sha256:own", "daemon"
                )
            self.assertFalse(clean)

    def test_listing_failure_still_checks_the_exact_project(self) -> None:
        module = runpy.run_path(str(SCRIPT))
        cleanup = module["cleanup_owned"]
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
            paths = module["prepare_paths"](Path(name) / "own-db")
            project_reads: list[str] = []

            def command(argv, _env, *, timeout=20):
                if "inspect" in argv:
                    return subprocess.CompletedProcess(argv, 1, "", f"No such object: {'a' * 64}")
                if "ps" in argv:
                    return subprocess.CompletedProcess(argv, 1, "", "daemon unavailable")
                if "info" in argv:
                    return subprocess.CompletedProcess(argv, 0, "daemon\n", "")
                return subprocess.CompletedProcess(argv, 0, "", "")

            def project(_docker, _env, name):
                project_reads.append(name)
                return []

            with patch.dict(
                cleanup.__globals__,
                {
                    "_container": lambda *_args: {},
                    "_run": command,
                    "_find_owned": project,
                    "_project_networks": lambda *_args: [],
                },
            ):
                clean = cleanup(
                    "a" * 64, ["docker"], {}, paths, "omnis-p01-own", "sha256:own", "daemon"
                )
            self.assertFalse(clean)
            self.assertEqual(project_reads, ["omnis-p01-own"])


if __name__ == "__main__":
    unittest.main()
