"""Synthetic Engine peer and held processes. NOT Docker or cgroup proof.

Only SyntheticFamily substitutes the Linux container-cgroup attestation. All
HTTP, daemon pinning, entry handoff, forwarder and durable receipt code is real.
"""

import hashlib
import json
import os
import runpy
import select
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import unquote
from uuid import uuid4

from omnis_cli.compose import ImageReceipt, _put_record
from omnis_cli.lifecycle import StartError, process_identity, socket_identity, write_record
from omnis_cli.release import _BASE_FILES
from omnis_cli.stop_owner import _load_runtime

# This fixture is also loaded by an isolated (-I) child via runpy.
_shapes = runpy.run_path(str(Path(__file__).with_name("runtime_inspect_fixture.py")))
container_item, image_item = _shapes["container_item"], _shapes["image_item"]


class SyntheticFamily:
    def __init__(self, cid, state):
        self.fd = os.pidfd_open(state["Pid"])

    def drained(self):
        if not select.select([self.fd], [], [], 0)[0]:
            raise StartError("STOP_CONTAINER_FAMILY_LIVE", 4)

    def close(self):
        os.close(self.fd)


def owner_test_argv(argv):
    source = str(Path(__file__).resolve())
    code = (
        "import runpy,sys; import omnis_cli.stop_owner as m; "
        f"m._ContainerFamily=runpy.run_path({source!r})['SyntheticFamily']; "
        "sys.argv=['stop-owner',*sys.argv[1:]]; sys.exit(m.main())"
    )
    return [argv[0], "-I", "-c", code, *argv[4:]]


class Fixture:
    def __init__(self):
        self.temp = tempfile.TemporaryDirectory(prefix="s4o-", dir=os.environ["TMPDIR"])
        self.base = Path(self.temp.name)
        self.root, self.data = self.base / "s", self.base / "d"
        self.control = self.root / "c"
        for path in (
            self.root,
            self.data,
            self.control,
            self.root / "http",
            self.root / "postgres",
            self.data / "omnis",
        ):
            path.mkdir(mode=0o700)
        (self.root / "postgres").chmod(0o711)
        (self.root / "db-password").write_text("a" * 48)
        (self.root / "db-password").chmod(0o600)
        self.sockets = {}
        for path, stem in ((self.root / "http", "api"), (self.control, "control")):
            (path / f"{stem}.lock").touch(mode=0o600)
            sock = socket.socket(socket.AF_UNIX)
            sock.bind(str(path / f"{stem}.sock"))
            (path / f"{stem}.sock").chmod(0o600)
            sock.listen()
            self.sockets[stem] = sock
        (self.control / "control.cap").write_text("b" * 64)
        (self.control / "control.cap").chmod(0o600)
        self.attempt = str(uuid4())
        self.project = "omnis-local-" + uuid4().hex
        self.ids = {
            role: char * 64 for role, char in zip(("api", "supervisor", "db"), "abc", strict=True)
        }
        self.network_id = "d" * 64
        self.image, self.pg_image = "sha256:" + "e" * 64, "sha256:" + "f" * 64
        self.port_sock = socket.socket()
        self.port_sock.bind(("127.0.0.1", 0))
        self.port = self.port_sock.getsockname()[1]
        self.port_sock.close()
        self.forwarder = subprocess.Popen(
            [
                sys.executable,
                "-I",
                "-m",
                "omnis_cli.forwarder",
                "--socket-dir",
                str(self.root / "http"),
                "--port",
                str(self.port),
                "--stop-attempt",
                self.attempt,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        self.forwarder_fd = os.pidfd_open(self.forwarder.pid)
        assert self.forwarder.stdout is not None
        assert select.select([self.forwarder.stdout], [], [], 3)[0]
        assert os.read(self.forwarder.stdout.fileno(), 128) == b"FORWARDER_READY\n"
        self.forwarder.stdout.close()
        self.processes, self.fuses, self.pidfds = {}, {}, {}
        self.items = {}
        for role, cid in self.ids.items():
            reader, writer = os.pipe()
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-I",
                    "-c",
                    "import os,sys; os.read(int(sys.argv[1]),1)",
                    str(reader),
                ],
                pass_fds=(reader,),
            )
            os.close(reader)
            self.processes[role], self.fuses[role] = process, writer
            self.pidfds[role] = os.pidfd_open(process.pid)
            self.items[cid] = self.item(role, cid, process.pid)
        self.network_item = {
            "Id": self.network_id,
            "Name": self.project + "_control",
            "Internal": True,
            "Driver": "bridge",
            "Labels": {
                "com.docker.compose.project": self.project,
                "org.omnis.start-attempt": self.attempt,
            },
            "Containers": {cid: {} for cid in self.ids.values()},
        }
        release = self.data / "omnis/releases/0.1.0"
        release.mkdir(parents=True, mode=0o700)
        files = {}
        for rel in sorted(_BASE_FILES | {"web/assets/synthetic.js"}):
            target = release / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            content = b"SYNTHETIC_RELEASE_FIXTURE_NOT_AN_ARTIFACT"
            target.write_bytes(content)
            files[rel] = hashlib.sha256(content).hexdigest()
        manifest = {
            "format": 1,
            "release": "0.1.0",
            "schema": "0006_stop_reconciliation",
            "platform": "linux/amd64",
            "files": files,
        }
        (release / "release.json").write_text(json.dumps(manifest))
        digest = hashlib.sha256((release / "release.json").read_bytes()).hexdigest()
        self.peer = socket.socket(socket.AF_UNIX)
        self.peer.bind(str(self.base / "e"))
        self.peer.listen()
        self.peer.settimeout(0.05)
        self.requests = []
        self.stop_status = 204
        self.noop = False
        self.lost_ack = False
        self.retain_ipc = False
        self.mutation_seen, self.release_mutation = threading.Event(), threading.Event()
        self.pause_mutation = False
        self.done = threading.Event()
        self.thread = threading.Thread(target=self.serve)
        self.thread.start()
        receipt = ImageReceipt(
            self.project,
            "omnis-control-" + self.project.removeprefix("omnis-local-") + ":0.1.0",
            self.image,
            digest,
            "unix://" + str(self.base / "e"),
            "synthetic-stop-daemon",
        )
        _put_record(self.data / "omnis/image.json", receipt, complete=True)
        write_record(self.data / "omnis/installed.json", {"format": 1, "release": "0.1.0"})
        instance = str(uuid4())
        write_record(
            self.root / "instance.json",
            {
                "version": 1,
                "instance_id": instance,
                "release": "0.1.0",
                "schema": "0006_stop_reconciliation",
                "project": self.project,
                "origin": f"http://127.0.0.1:{self.port}",
            },
        )
        inode = next(
            int(row.split()[9])
            for row in Path("/proc/net/tcp").read_text().splitlines()[1:]
            if row.split()[1] == f"0100007F:{self.port:04X}" and row.split()[3] == "0A"
        )
        pg = (self.root / "postgres").stat()
        self.record = {
            "format": 2,
            "phase": "STOPPING",
            "attempt": self.attempt,
            "project": self.project,
            "release_digest": digest,
            "image_id": self.image,
            "docker_host": receipt.docker_host,
            "docker_id": receipt.docker_id,
            "control_dir": str(self.control),
            "port": self.port,
            "containers": self.ids,
            "system_id": "12345",
            "pgdata_identity": [pg.st_dev, pg.st_ino],
            "instance_id": instance,
            "forwarder": process_identity(self.forwarder.pid),
            "listener_inode": inode,
            "api_socket": socket_identity(self.root / "http/api.sock"),
            "control_socket": socket_identity(self.control / "control.sock"),
            "open_command": str(uuid4()),
            "generation": 1,
            "supervisor_epoch": 1,
            "stop_command": str(uuid4()),
            "stop_expected": 1,
            "stop_generation": 2,
            "finalize_command": str(uuid4()),
            "finalized_generation": 2,
            "teardown_completed": [],
        }
        write_record(self.root / "startup.json", self.record)
        self.runtime = _load_runtime(self.data, self.record, time.monotonic() + 15)

    def item(self, role, cid, pid):
        runtime = SimpleNamespace(
            receipt=SimpleNamespace(project=self.project, image_id=self.image),
            pg_image=self.pg_image,
            attempt=self.attempt,
        )
        item = container_item(runtime, role, cid, self.root, self.control, self.port)
        item["State"].update(Paused=False, Restarting=False, Pid=pid)
        item["NetworkSettings"]["Networks"][self.project + "_control"]["NetworkID"] = (
            self.network_id
        )
        return item

    def response(self, method, target):
        path = target.split("?", 1)[0]
        if method == "GET":
            if path == "/info":
                return 200, {"ID": "synthetic-stop-daemon"}
            if path.startswith("/images/"):
                runtime = SimpleNamespace(
                    receipt=SimpleNamespace(image_id=self.image), pg_image=self.pg_image
                )
                ident = unquote(path.split("/")[2])
                assert ident in (self.pg_image, self.image)
                return 200, image_item(runtime, "db" if ident == self.pg_image else "api")
            if path == "/containers/json":
                return 200, [{"Id": cid} for cid in self.items]
            if path == "/networks":
                return 200, [] if self.network_item is None else [self.network_item]
            if path.startswith("/networks/"):
                return (404, {}) if self.network_item is None else (200, self.network_item)
            cid = path.split("/")[2]
            return (200, self.items[cid]) if cid in self.items else (404, {})
        self.mutation_seen.set()
        if self.pause_mutation:
            if not self.release_mutation.wait(5):
                return 500, {}
        if method == "POST":
            if self.stop_status != 204:
                return self.stop_status, {}
            cid = path.split("/")[2]
            if not self.noop:
                role = next(role for role, ident in self.ids.items() if ident == cid)
                os.close(self.fuses.pop(role))
                self.processes[role].wait(timeout=2)
                self.items[cid]["State"] = {
                    "Running": False,
                    "Paused": False,
                    "Restarting": False,
                    "Dead": False,
                    "OOMKilled": False,
                    "ExitCode": 0,
                    "Pid": 0,
                    "Status": "exited",
                    "Error": "",
                }
                self.network_item["Containers"].pop(cid)
                if not self.retain_ipc:
                    stem = {"api": "api", "supervisor": "control"}.get(role)
                    if stem:
                        self.sockets[stem].close()
                        directory = self.root / "http" if stem == "api" else self.control
                        (directory / f"{stem}.sock").unlink()
                        if stem == "control":
                            (directory / "control.cap").unlink()
            return (0, {}) if self.lost_ack else (204, {})
        if path.startswith("/containers/"):
            self.items.pop(path.split("/")[2])
        else:
            self.network_item = None
        return 204, {}

    def serve(self):
        while not self.done.is_set():
            try:
                channel, _ = self.peer.accept()
            except TimeoutError:
                continue
            with channel:
                channel.settimeout(2)
                data = bytearray()
                while b"\r\n\r\n" not in data:
                    part = channel.recv(16384)
                    if not part:
                        break
                    data.extend(part)
                line = data.decode().split("\r\n")[0]
                method, target, _ = line.split()
                self.requests.append(line)
                status, value = self.response(method, target)
                if status == 0:
                    continue
                body = b"" if status == 204 else json.dumps(value).encode()
                try:
                    channel.sendall(
                        f"HTTP/1.1 {status} Synthetic\r\nContent-Length: {len(body)}\r\n\r\n".encode()
                        + body
                    )
                except (BrokenPipeError, ConnectionResetError):
                    pass

    def grant(self, inventory):
        return {
            "version": 1,
            "state": "STOP_PENDING",
            "instance_id": self.record["instance_id"],
            "command_id": self.record["stop_command"],
            "finalize_command_id": self.record["finalize_command"],
            "generation": 2,
            "owner_epoch": 1,
            "owner_uuid": "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
            "daemon_id": "synthetic-stop-daemon",
            "inventory": inventory,
        }

    def close(self):
        self.release_mutation.set()
        self.done.set()
        self.thread.join(6)
        assert not self.thread.is_alive()
        self.peer.close()
        for sock in self.sockets.values():
            sock.close()
        for writer in self.fuses.values():
            os.close(writer)
        for role, process in self.processes.items():
            process.wait(timeout=3)
            assert select.select([self.pidfds[role]], [], [], 0)[0]
            os.close(self.pidfds[role])
        if self.forwarder.poll() is None:
            signal.pidfd_send_signal(self.forwarder_fd, signal.SIGTERM)
        self.forwarder.wait(timeout=3)
        assert select.select([self.forwarder_fd], [], [], 0)[0]
        os.close(self.forwarder_fd)
        self.temp.cleanup()
