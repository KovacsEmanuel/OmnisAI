"""Guardrails for the opt-in installed-control topology probe."""

import io
import json
import os
import socket
import stat
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from contextlib import redirect_stdout
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from control_topology import (
    _POSTGRES,
    _cleanup,
    _docker,
    _finish_probe,
    _http,
    _owned_container,
    _uds_http,
    assert_no_host_listener,
    conclude_cleanup,
    preflight_port,
    prepare_disposable_postgres,
    strict_probe_environment,
    validate_docker_engine,
)


class InstalledControlPreflightTest(unittest.TestCase):
    def test_forwarder_exit_race_still_attempts_owned_compose_cleanup(self):
        class ExitedForwarder:
            pid = 12345
            returncode = 0

            def poll(self):
                return None  # Exit between this check and killpg.

            def communicate(self, *, timeout):
                assert timeout == 5
                return "FORWARDER_READY", ""

        project = "omnis-local-" + "a" * 32
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
            scratch = Path(name)
            state = scratch / "state"
            (state / "postgres").mkdir(parents=True)
            empty_env = scratch / "empty.env"
            empty_env.touch()
            output = io.StringIO()
            with (
                patch("control_topology.os.killpg", side_effect=ProcessLookupError),
                patch("control_topology.assert_no_host_listener") as no_listener,
                patch("control_topology._cleanup") as cleanup,
                redirect_stdout(output),
            ):
                _finish_probe(
                    ExitedForwarder(),
                    port=8765,
                    launched=True,
                    host="unix:///owned/docker.sock",
                    release=scratch,
                    project=project,
                    empty_env=empty_env,
                    env={},
                    state_root=state,
                    image_id="owned-image",
                    uncertain=False,
                )
            cleanup.assert_called_once_with(
                "unix:///owned/docker.sock",
                scratch,
                project,
                empty_env,
                {},
                state,
                "owned-image",
                8765,
            )
            no_listener.assert_called_once_with(8765)
            self.assertIn("INSTALLED_CONTROL_STOPPED", output.getvalue())

    def test_poststop_readback_rejects_listener_not_own_tcp_time_wait(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen(1)
            port = listener.getsockname()[1]
            with self.assertRaisesRegex(ValueError, "listener"):
                assert_no_host_listener(port)
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client:
                client.connect(("127.0.0.1", port))
                accepted, _peer = listener.accept()
                with accepted:
                    accepted.shutdown(socket.SHUT_WR)
                    self.assertEqual(client.recv(1), b"")
        # A server-first FIN leaves TIME_WAIT on this port after every FD closes.
        with self.assertRaisesRegex(ValueError, "occupied"):
            preflight_port(port)
        assert_no_host_listener(port)

    def test_poststop_readback_rejects_ipv6_listener_on_the_same_port(self):
        if not socket.has_ipv6:
            self.skipTest("IPv6 socket support unavailable")
        try:
            listener = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        except OSError:
            self.skipTest("IPv6 socket unavailable")
        with listener:
            listener.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
            listener.bind(("::1", 0))
            listener.listen(1)
            with self.assertRaisesRegex(ValueError, "listener"):
                assert_no_host_listener(listener.getsockname()[1])

    def test_runtime_api_has_only_private_uds_and_no_docker_port(self):
        project = "omnis-local-" + "a" * 32
        image_id = "sha256:" + "b" * 64
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
            state = Path(name)
            item = {
                "Id": "owned-api",
                "Config": {
                    "Image": image_id,
                    "User": f"{os.getuid()}:{os.getgid()}",
                    "Labels": {
                        "com.docker.compose.project": project,
                        "com.docker.compose.service": "api",
                    },
                },
                "Image": image_id,
                "HostConfig": {
                    "Privileged": False,
                    "ReadonlyRootfs": True,
                    "CapDrop": ["ALL"],
                    "SecurityOpt": ["no-new-privileges:true"],
                },
                "Mounts": [
                    {
                        "Type": "bind",
                        "Destination": "/run/omnis-control",
                        "Source": str(state / "control"),
                        "RW": False,
                    },
                    {
                        "Type": "bind",
                        "Destination": "/run/omnis-http",
                        "Source": str(state / "http"),
                        "RW": True,
                    },
                ],
                "NetworkSettings": {"Ports": {}, "Networks": {f"{project}_control": {}}},
                "State": {"Running": True},
            }
            with (
                patch("control_topology._inspect", return_value=item),
                patch("control_topology._expected_image_id", return_value=image_id),
            ):
                self.assertEqual(
                    _owned_container(
                        "unix:///owned/docker.sock",
                        "owned-api",
                        state,
                        project,
                        image_id,
                        state,
                        8765,
                    ),
                    item,
                )
            for variant in ("extra-bind", "writable-rootfs", "retained-caps", "no-privileges-off"):
                with self.subTest(variant=variant):
                    unsafe = deepcopy(item)
                    if variant == "extra-bind":
                        unsafe["Mounts"].append(
                            {
                                "Type": "bind",
                                "Destination": "/etc",
                                "Source": str(state / "foreign"),
                                "RW": True,
                            }
                        )
                    elif variant == "writable-rootfs":
                        unsafe["HostConfig"]["ReadonlyRootfs"] = False
                    elif variant == "retained-caps":
                        unsafe["HostConfig"]["CapDrop"] = []
                    else:
                        unsafe["HostConfig"]["SecurityOpt"] = []
                    with (
                        patch("control_topology._inspect", return_value=unsafe),
                        patch("control_topology._expected_image_id", return_value=image_id),
                        self.assertRaises(AssertionError),
                    ):
                        _owned_container(
                            "unix:///owned/docker.sock",
                            "owned-api",
                            state,
                            project,
                            image_id,
                            state,
                            8765,
                        )

    def test_runtime_db_has_only_owned_data_and_readonly_secret_mounts(self):
        project = "omnis-local-" + "a" * 32
        image_id = "sha256:" + "b" * 64
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
            state = Path(name)
            item = {
                "Id": "owned-db",
                "Config": {
                    "Image": _POSTGRES,
                    "Labels": {
                        "com.docker.compose.project": project,
                        "com.docker.compose.service": "db",
                    },
                },
                "Image": image_id,
                "HostConfig": {"Privileged": False},
                "Mounts": [
                    {
                        "Type": "bind",
                        "Source": str(state / "postgres"),
                        "Destination": "/var/lib/postgresql",
                        "RW": True,
                    },
                    {
                        "Type": "bind",
                        "Source": str(state / "db-password"),
                        "Destination": "/run/secrets/db_password",
                        "RW": False,
                    },
                ],
                "NetworkSettings": {"Ports": {}, "Networks": {f"{project}_control": {}}},
                "State": {"Running": True},
            }
            with (
                patch("control_topology._inspect", return_value=item),
                patch("control_topology._expected_image_id", return_value=image_id),
            ):
                self.assertEqual(
                    _owned_container(
                        "unix:///owned/docker.sock",
                        "owned-db",
                        state,
                        project,
                        image_id,
                        state,
                        8765,
                    ),
                    item,
                )
            for variant in ("extra-bind", "writable-secret", "foreign-secret"):
                with self.subTest(variant=variant):
                    unsafe = deepcopy(item)
                    if variant == "extra-bind":
                        unsafe["Mounts"].append(
                            {
                                "Type": "bind",
                                "Source": str(state / "foreign"),
                                "Destination": "/etc",
                                "RW": True,
                            }
                        )
                    elif variant == "writable-secret":
                        unsafe["Mounts"][1]["RW"] = True
                    else:
                        unsafe["Mounts"][1]["Source"] = str(state / "foreign")
                    with (
                        patch("control_topology._inspect", return_value=unsafe),
                        patch("control_topology._expected_image_id", return_value=image_id),
                        self.assertRaises(AssertionError),
                    ):
                        _owned_container(
                            "unix:///owned/docker.sock",
                            "owned-db",
                            state,
                            project,
                            image_id,
                            state,
                            8765,
                        )

    def test_timeout_cleanup_cannot_claim_a_settled_daemon(self):
        output = io.StringIO()
        with redirect_stdout(output):
            with self.assertRaisesRegex(AssertionError, "uncertain"):
                conclude_cleanup("omnis-local-" + "a" * 32, Path("/private/data"), uncertain=True)
        self.assertIn("OUTCOME_UNCERTAIN", output.getvalue())
        self.assertNotIn("STOPPED", output.getvalue())

    def test_docker_timeout_reaps_a_term_resistant_owned_descendant(self):
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
            scratch = Path(name)
            ready = scratch / "child-ready"
            late = scratch / "late-side-effect"
            child = (
                "import signal,time; from pathlib import Path; "
                "signal.signal(signal.SIGTERM,signal.SIG_IGN); "
                f"Path({str(ready)!r}).write_text('ready'); "
                "time.sleep(2); "
                f"Path({str(late)!r}).write_text('late')"
            )
            wrapper = scratch / "docker"
            wrapper.write_text(
                f"#!{sys.executable}\nimport subprocess,sys,time\n"
                f"subprocess.Popen([sys.executable,'-c',{child!r}],"
                "stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)\n"
                "time.sleep(10)\n"
            )
            wrapper.chmod(0o700)
            with self.assertRaises(subprocess.TimeoutExpired):
                _docker(
                    "unix:///owned/docker.sock",
                    "info",
                    cwd=scratch,
                    env={"PATH": f"{scratch}:{os.environ.get('PATH', '')}"},
                    timeout=1,
                )
            self.assertTrue(ready.exists(), "A descendant must actually start before timeout")
            time.sleep(2.3)
            self.assertFalse(late.exists(), "A killed CLI must not leave a late Docker child")

    def test_foreign_network_member_does_not_keep_owned_containers_running(self):
        project = "omnis-local-" + "a" * 32
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
            scratch = Path(name)
            state = scratch / "state"
            (state / "postgres").mkdir(parents=True)
            empty_env = scratch / "empty.env"
            empty_env.touch()
            live = {"api-id", "db-id"}
            stopped: set[str] = set()

            def docker(_host, *args, **_kwargs):
                if args[:2] == ("network", "inspect"):
                    members = {"foreign-id": {}, **{ident: {} for ident in live}}
                    return subprocess.CompletedProcess(
                        args,
                        0,
                        stdout=json.dumps(
                            [
                                {
                                    "Labels": {"com.docker.compose.project": project},
                                    "Internal": args[2].endswith("_control"),
                                    "Containers": members,
                                }
                            ]
                        ),
                    )
                if args[:2] == ("container", "stop"):
                    stopped.add(args[-1])
                    return subprocess.CompletedProcess(args, 0)
                if args[:2] == ("container", "rm"):
                    self.assertIn(args[-1], stopped)
                    live.remove(args[-1])
                    return subprocess.CompletedProcess(args, 0)
                self.fail("Foreign resources must never be removed")

            def attest(_host, ident, _scratch, _project, _image, _state):
                self.assertIn(ident, live)
                return {"Config": {"Labels": {"com.docker.compose.oneoff": "False"}}}

            with (
                patch("control_topology._owner_set", side_effect=lambda *_args: sorted(live)),
                patch("control_topology._attest_container_identity", side_effect=attest),
                patch("control_topology._docker", side_effect=docker),
                patch("control_topology._compose") as compose,
            ):
                with self.assertRaisesRegex(AssertionError, "incomplete"):
                    _cleanup(
                        "unix:///owned/docker.sock",
                        scratch,
                        project,
                        empty_env,
                        {},
                        state,
                        "",
                        8765,
                    )
                compose.assert_not_called()
            self.assertEqual(stopped, {"api-id", "db-id"})
            self.assertEqual(live, set())
            self.assertTrue((state / "postgres").is_dir())

    def test_owned_private_uds_api_does_not_block_disposable_teardown(self):
        project = "omnis-local-" + "a" * 32
        image_id = "sha256:" + "b" * 64
        db_id = "sha256:" + "c" * 64
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
            scratch = Path(name)
            state = scratch / "state"
            (state / "postgres").mkdir(parents=True)
            control = state / "control"
            control.mkdir()
            http = state / "http"
            http.mkdir()
            empty_env = scratch / "empty.env"
            empty_env.touch()
            api = {
                "Id": "api-id",
                "Config": {
                    "Image": image_id,
                    "User": f"{os.getuid()}:{os.getgid()}",
                    "Labels": {
                        "com.docker.compose.project": project,
                        "com.docker.compose.service": "api",
                    },
                },
                "Image": image_id,
                "HostConfig": {
                    "Privileged": False,
                    "ReadonlyRootfs": True,
                    "CapDrop": ["ALL"],
                    "SecurityOpt": ["no-new-privileges:true"],
                },
                "Mounts": [
                    {
                        "Type": "bind",
                        "Destination": "/run/omnis-control",
                        "Source": str(control),
                        "RW": False,
                    },
                    {
                        "Type": "bind",
                        "Destination": "/run/omnis-http",
                        "Source": str(http),
                        "RW": True,
                    },
                ],
                "NetworkSettings": {
                    "Ports": {},
                    "Networks": {f"{project}_control": {}},
                },
                "State": {"Running": True},
            }
            db = {
                "Id": "db-id",
                "Config": {
                    "Image": _POSTGRES,
                    "Labels": {
                        "com.docker.compose.project": project,
                        "com.docker.compose.service": "db",
                    },
                },
                "Image": db_id,
                "HostConfig": {"Privileged": False},
                "Mounts": [
                    {
                        "Type": "bind",
                        "Destination": "/var/lib/postgresql",
                        "Source": str(state / "postgres"),
                        "RW": True,
                    },
                    {
                        "Type": "bind",
                        "Destination": "/run/secrets/db_password",
                        "Source": str(state / "db-password"),
                        "RW": False,
                    },
                ],
                "NetworkSettings": {
                    "Ports": {"5432/tcp": None},
                    "Networks": {f"{project}_control": {}},
                },
                "State": {"Running": True},
            }
            resources = {"api-id": api, "db-id": db}
            removed = False

            def docker(_host, *args, **_kwargs):
                if args[:2] == ("network", "inspect"):
                    if removed:
                        return subprocess.CompletedProcess(args, 1, stderr="network not found")
                    name = args[2]
                    self.assertTrue(name.endswith("_control"))
                    return subprocess.CompletedProcess(
                        args,
                        0,
                        stdout=json.dumps(
                            [
                                {
                                    "Labels": {"com.docker.compose.project": project},
                                    "Internal": True,
                                    "Containers": {"api-id": {}, "db-id": {}},
                                }
                            ]
                        ),
                    )
                self.fail("Unexpected Docker request")

            def compose(_host, _release, _project, _empty, _env, *args, **_kwargs):
                nonlocal removed
                self.assertEqual(args, ("down",))
                removed = True
                return subprocess.CompletedProcess(args, 0)

            def owners(_host, _project, _scratch):
                return [] if removed else ["api-id", "db-id"]

            with (
                patch("control_topology._owner_set", side_effect=owners),
                patch(
                    "control_topology._inspect", side_effect=lambda _h, ident, _s: resources[ident]
                ),
                patch(
                    "control_topology._expected_image_id",
                    side_effect=lambda _h, image, _s: db_id if image == _POSTGRES else image_id,
                ),
                patch("control_topology._docker", side_effect=docker),
                patch("control_topology._compose", side_effect=compose),
            ):
                _cleanup(
                    "unix:///owned/docker.sock",
                    scratch,
                    project,
                    empty_env,
                    {},
                    state,
                    image_id,
                    8765,
                )
            self.assertTrue(removed)
            self.assertTrue((state / "postgres").is_dir())

    def test_failed_oneoff_removal_still_attempts_owned_compose_teardown(self):
        project = "omnis-local-" + "a" * 32
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
            scratch = Path(name)
            state = scratch / "state"
            (state / "postgres").mkdir(parents=True)
            empty_env = scratch / "empty.env"
            empty_env.touch()
            down = False
            ids = ["owned-job", "owned-api", "owned-db"]

            def owners(_host, _project, _scratch):
                return [] if down else ids

            def attest(_host, ident, _scratch, _project, _image, _state):
                return {
                    "Config": {"Labels": {"com.docker.compose.oneoff": str(ident == "owned-job")}}
                }

            def docker(_host, *args, **_kwargs):
                if args[:2] == ("network", "inspect"):
                    if down:
                        return subprocess.CompletedProcess(args, 1, stderr="network not found")
                    return subprocess.CompletedProcess(
                        args,
                        0,
                        stdout=json.dumps(
                            [
                                {
                                    "Labels": {"com.docker.compose.project": project},
                                    "Internal": True,
                                    "Containers": {ident: {} for ident in ids},
                                }
                            ]
                        ),
                    )
                if args[:3] == ("container", "rm", "-f"):
                    raise AssertionError("synthetic owned one-off removal failure")
                self.fail("Unexpected Docker command")

            def compose(_host, _release, _project, _empty, _env, *args, **_kwargs):
                nonlocal down
                self.assertEqual(args, ("down",))
                down = True
                return subprocess.CompletedProcess(args, 0)

            with (
                patch("control_topology._owner_set", side_effect=owners),
                patch("control_topology._attest_container_identity", side_effect=attest),
                patch("control_topology._docker", side_effect=docker),
                patch("control_topology._compose", side_effect=compose),
            ):
                with self.assertRaisesRegex(AssertionError, "incomplete"):
                    _cleanup(
                        "unix:///owned/docker.sock",
                        scratch,
                        project,
                        empty_env,
                        {},
                        state,
                        "owned-image",
                        8765,
                    )
            self.assertTrue(down, "A failed one-off rm must not strand the owned services")
            self.assertTrue((state / "postgres").is_dir())

    def test_postgres_must_not_join_the_front_network_at_runtime(self):
        project = "omnis-local-" + "a" * 32
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
            state = Path(name)
            db_image_id = "sha256:" + "b" * 64
            container = {
                "Id": "owned-db",
                "Config": {
                    "Labels": {
                        "com.docker.compose.project": project,
                        "com.docker.compose.service": "db",
                    },
                    "Image": _POSTGRES,
                },
                "Image": db_image_id,
                "HostConfig": {"Privileged": False},
                "Mounts": [
                    {
                        "Type": "bind",
                        "Source": str(state / "postgres"),
                        "Destination": "/var/lib/postgresql",
                        "RW": True,
                    },
                    {
                        "Type": "bind",
                        "Source": str(state / "db-password"),
                        "Destination": "/run/secrets/db_password",
                        "RW": False,
                    },
                ],
                "NetworkSettings": {
                    "Ports": {"5432/tcp": None},
                    "Networks": {f"{project}_control": {}, f"{project}_front": {}},
                },
            }
            with (
                patch("control_topology._inspect", return_value=container),
                patch("control_topology._expected_image_id", return_value=db_image_id),
            ):
                with self.assertRaisesRegex(AssertionError, "network"):
                    _owned_container(
                        "unix:///owned/docker.sock", "owned-db", state, project, "", state, 8765
                    )

    def test_docker_27_is_not_a_private_loopback_proof(self):
        with self.assertRaises(ValueError):
            validate_docker_engine("27.5.1+dfsg4")

    def test_docker_28_is_eligible_for_a_later_lan_probe(self):
        validate_docker_engine("28.0.0")

    def test_redirect_does_not_contact_a_second_loopback_sink(self):
        hit = threading.Event()

        class Sink(BaseHTTPRequestHandler):
            def do_GET(self):
                hit.set()
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"{}")

            def log_message(self, format: str, *args: object) -> None:
                pass

        with ThreadingHTTPServer(("127.0.0.1", 0), Sink) as sink:

            class Redirect(BaseHTTPRequestHandler):
                def do_GET(self):
                    self.send_response(302)
                    self.send_header("Location", f"http://127.0.0.1:{sink.server_port}/sink")
                    self.end_headers()

                def log_message(self, format: str, *args: object) -> None:
                    pass

            with ThreadingHTTPServer(("127.0.0.1", 0), Redirect) as source:
                sink_thread = threading.Thread(target=sink.serve_forever, daemon=True)
                source_thread = threading.Thread(target=source.serve_forever, daemon=True)
                sink_thread.start()
                source_thread.start()
                try:
                    status, _body = _http(source.server_port, "/health/ready")
                    self.assertEqual(status, 302)
                    self.assertFalse(hit.is_set(), "A redirect is not authorized target traffic")
                finally:
                    source.shutdown()
                    sink.shutdown()
                    source_thread.join(timeout=2)
                    sink_thread.join(timeout=2)

    def test_private_uds_trickle_has_one_total_reply_deadline(self):
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
            directory = Path(name)
            path = directory / "api.sock"
            stop = threading.Event()
            done = threading.Event()
            outcome: list[str] = []
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
                listener.bind(str(path))
                path.chmod(0o600)
                listener.listen(1)

                def server():
                    connection, _peer = listener.accept()
                    with connection:
                        connection.settimeout(2)
                        request = bytearray()
                        while not request.endswith(b"\r\n\r\n"):
                            request.extend(connection.recv(4096))
                        connection.sendall(
                            b"HTTP/1.1 200 OK\r\nContent-Length: 100000\r\nConnection: close\r\n\r\n"
                        )
                        while not stop.wait(0.2):
                            try:
                                connection.sendall(b"x")
                            except OSError:
                                break

                def client():
                    try:
                        _uds_http(directory, 8765, "/health/ready")
                        outcome.append("unexpected success")
                    except TimeoutError:
                        outcome.append("total deadline")
                    except Exception as exc:
                        outcome.append(type(exc).__name__)
                    finally:
                        done.set()

                serving = threading.Thread(target=server, daemon=True)
                probing = threading.Thread(target=client, daemon=True)
                serving.start()
                probing.start()
                try:
                    self.assertTrue(done.wait(6), "UDS trickle bypassed the reply budget")
                    self.assertEqual(outcome, ["total deadline"])
                finally:
                    stop.set()
                    probing.join(timeout=2)
                    serving.join(timeout=2)
                self.assertFalse(probing.is_alive())
                self.assertFalse(serving.is_alive())

    def test_host_forwarded_http_trickle_has_one_total_reply_deadline(self):
        stop = threading.Event()
        done = threading.Event()
        outcome: list[str] = []

        class Drip(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-Length", "100000")
                self.send_header("Connection", "close")
                self.end_headers()
                while not stop.wait(0.2):
                    try:
                        self.wfile.write(b"x")
                        self.wfile.flush()
                    except OSError:
                        break

            def log_message(self, format: str, *args: object) -> None:
                pass

        with ThreadingHTTPServer(("127.0.0.1", 0), Drip) as server:
            server.daemon_threads = True

            def client():
                try:
                    _http(server.server_port, "/health/ready")
                    outcome.append("unexpected success")
                except TimeoutError:
                    outcome.append("total deadline")
                except Exception as exc:
                    outcome.append(type(exc).__name__)
                finally:
                    done.set()

            serving = threading.Thread(target=server.serve_forever, daemon=True)
            probing = threading.Thread(target=client, daemon=True)
            serving.start()
            probing.start()
            try:
                self.assertTrue(done.wait(6), "Loopback trickle bypassed the reply budget")
                self.assertEqual(outcome, ["total deadline"])
            finally:
                stop.set()
                server.shutdown()
                probing.join(timeout=2)
                serving.join(timeout=2)
            self.assertFalse(probing.is_alive())
            self.assertFalse(serving.is_alive())

    def test_pg18_bind_root_is_traversable_only_under_private_state(self):
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
            state = Path(name) / "state"
            state.mkdir(mode=0o700)
            postgres = prepare_disposable_postgres(state)
            self.assertEqual(stat.S_IMODE(state.stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE(postgres.stat().st_mode), 0o711)
            self.assertEqual(postgres.parent, state)

    def test_foreign_loopback_listener_is_refused_without_docker(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as foreign:
            foreign.bind(("127.0.0.1", 0))
            foreign.listen(1)
            port = foreign.getsockname()[1]
            with self.assertRaises(ValueError):
                preflight_port(port)
            self.assertEqual(foreign.getsockname()[1], port)

    def test_ambient_docker_compose_and_libpq_overrides_are_refused(self):
        for key in ("DOCKER_CONTEXT", "COMPOSE_FILE", "PGSERVICE"):
            with self.subTest(key=key), patch.dict(os.environ, {key: "foreign"}):
                with self.assertRaises(ValueError):
                    strict_probe_environment()

    def test_clean_environment_is_allowed(self):
        with patch.dict(
            os.environ,
            {
                key: value
                for key, value in os.environ.items()
                if not key.startswith(("DOCKER_", "COMPOSE_", "PG"))
            },
            clear=True,
        ):
            strict_probe_environment()
