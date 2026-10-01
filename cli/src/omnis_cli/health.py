"""Total-deadline, byte-bounded probes of an already attested local route.

Callers establish resource ownership before any HTTP connection. No redirects,
ambient proxies, DNS, remote URL input or pairing are used here.
"""

import http.client
import json
import os
import re
import socket
import struct
import time
from collections.abc import Buffer
from pathlib import Path

from .control import request
from .instance import unique_pairs
from .lifecycle import StartError, remaining, socket_identity


class DeadlineSocket(socket.socket):
    def __init__(self, family: int, deadline: float, limit: int) -> None:
        super().__init__(family, socket.SOCK_STREAM)
        self.deadline = deadline
        self.left = limit

    def budget(self) -> None:
        self.settimeout(remaining(self.deadline, 4))
        if self.left <= 0:
            raise StartError("HTTP_SIZE_LIMIT", 3)

    def recv_into(self, buffer: Buffer, nbytes: int = 0, flags: int = 0) -> int:
        self.budget()
        count = super().recv_into(
            memoryview(buffer), min(nbytes or len(memoryview(buffer)), self.left), flags
        )
        self.left -= count
        return count


def http_probe(
    port: int,
    path: str,
    deadline: float,
    *,
    directory: Path | None = None,
    api_pid: int | None = None,
    limit: int = 2 * 1024 * 1024,
) -> bytes:
    if (
        type(port) is not int
        or not 1 <= port <= 65535
        or (
            path not in {"/", "/health/ready"}
            and re.fullmatch(r"/assets/[A-Za-z0-9_-]+\.(?:js|css|woff2|txt)", path) is None
        )
    ):
        raise StartError("HTTP_DESTINATION_INVALID")
    end = min(deadline, time.monotonic() + 4)
    with DeadlineSocket(
        socket.AF_UNIX if directory else socket.AF_INET, end, limit + 32768
    ) as connection:
        connection.budget()
        if directory:
            socket_identity(directory / "api.sock")
            connection.connect(str(directory / "api.sock"))
            peer = connection.getsockopt(
                socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i")
            )
            peer_pid, peer_uid, _ = struct.unpack("3i", peer)
            if peer_uid != os.getuid():
                raise StartError("API_PEER_MISMATCH", 3)
            if api_pid is not None:
                try:
                    if (
                        peer_pid <= 1
                        or api_pid <= 1
                        or os.readlink(f"/proc/{peer_pid}/ns/pid")
                        != os.readlink(f"/proc/{api_pid}/ns/pid")
                        or Path(f"/proc/{peer_pid}/cgroup").read_bytes()
                        != Path(f"/proc/{api_pid}/cgroup").read_bytes()
                    ):
                        raise StartError("API_PEER_MISMATCH", 3)
                except OSError:
                    raise StartError("API_PEER_MISMATCH", 3) from None
        else:
            connection.connect(("127.0.0.1", port))
        connection.budget()
        connection.sendall(
            f"GET {path} HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nConnection: close\r\n\r\n".encode()
        )
        with http.client.HTTPResponse(connection) as response:
            response.begin()
            if response.status != 200:
                raise StartError("HTTP_NOT_READY", 3)
            body = response.read(limit + 1)
        if len(body) > limit:
            raise StartError("HTTP_SIZE_LIMIT", 3)
        remaining(end)
        return body


def dashboard(
    control: Path,
    http_dir: Path,
    port: int,
    identity: str,
    files: dict[str, bytes],
    deadline: float,
    *,
    forwarded: bool,
    api_pid: int,
) -> dict[str, object]:
    current = request(control, {"op": "status"}, deadline=deadline)
    if (
        current["instance_id"] != identity
        or current["assessment_ready"] is not False
        or current["shutdown_command_id"] is not None
    ):
        raise StartError("INSTANCE_CONTROL_MISMATCH", 3)
    directory = None if forwarded else http_dir
    private_body = http_probe(
        port, "/health/ready", deadline, directory=http_dir, api_pid=api_pid, limit=4096
    )
    body = (
        http_probe(
            port, "/health/ready", deadline, directory=directory, api_pid=api_pid, limit=4096
        )
        if forwarded
        else private_body
    )
    if body != private_body:
        raise StartError("HTTP_ROUTE_MISMATCH", 3)
    projection = json.loads(body, object_pairs_hook=unique_pairs)
    if (
        not isinstance(projection, dict)
        or set(projection)
        != {"api_ready", "dashboard_ready", "assessment_ready", "reason", "dashboard_reason"}
        or projection["api_ready"] is not True
        or projection["dashboard_ready"] is not True
        or projection["assessment_ready"] is not False
        or projection["reason"] is not None
        or projection["dashboard_reason"] is not None
    ):
        raise StartError("DASHBOARD_NOT_READY", 3)
    for name, content in files.items():
        if name == "web/index.html" or name.startswith("web/assets/"):
            route = "/" if name == "web/index.html" else "/" + name.removeprefix("web/")
            if (
                http_probe(
                    port, route, deadline, directory=directory, api_pid=api_pid, limit=len(content)
                )
                != content
            ):
                raise StartError("SERVED_ASSET_MISMATCH", 3)
    after = request(control, {"op": "status"}, deadline=deadline)
    if after != current:
        raise StartError("CONTROL_CHANGED_DURING_HEALTH", 3)
    return current
