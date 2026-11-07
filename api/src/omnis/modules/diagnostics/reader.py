"""Private bounded reader. No raw log/inspection/environment is returned."""

import http.client
import json
import os
import re
import signal
import socket
import stat
import time
from pathlib import Path
from types import FrameType
from typing import Never

from omnis.modules.diagnostics.schemas import MARKER, UiRecord
from omnis.security.host_origin import reject_json_constant, unique_json_object

MAX_BYTES = 256 * 1024
MAX_RECORDS = 256


def read_records(data: bytes) -> list[UiRecord]:
    if len(data) > MAX_BYTES:
        raise ValueError("Diagnostic read bound")
    records = []
    for line in data.splitlines(keepends=True):
        if MARKER.encode() not in line:
            continue
        if not line.endswith(b"\n") or len(line) > 1024:
            raise ValueError("Incomplete or oversized diagnostic record")
        value: object = json.loads(
            line, object_pairs_hook=unique_json_object, parse_constant=reject_json_constant
        )
        records.append(UiRecord.model_validate(value))
        if len(records) > MAX_RECORDS:
            raise ValueError("Diagnostic record bound")
    return records


def validate_owner(value: object, container: str, project: str, attempt: str) -> None:
    if not isinstance(value, dict) or value.get("Id") != container:
        raise ValueError("Foreign container")
    config = value.get("Config")
    host = value.get("HostConfig")
    if not isinstance(config, dict) or not isinstance(host, dict):
        raise ValueError("Missing owner")
    labels = config.get("Labels")
    log = host.get("LogConfig")
    if (
        not isinstance(labels, dict)
        or labels.get("com.docker.compose.project") != project
        or labels.get("com.docker.compose.service") != "api"
        or labels.get("org.omnis.start-attempt") != attempt
        or config.get("Tty") is not False
        or not isinstance(log, dict)
        or log.get("Type") not in {"json-file", "local"}
    ):
        raise ValueError("Foreign or uncaptured API container")


class UnixDocker(http.client.HTTPConnection):
    def __init__(self, path: str) -> None:
        super().__init__("localhost", timeout=2)
        self.path = path

    def connect(self) -> None:
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(2)
        self.sock.connect(self.path)


def _get(path: str, resource: str, deadline: float, limit: int) -> bytes:
    connection = UnixDocker(path)
    response: http.client.HTTPResponse | None = None
    try:
        connection.connect()
        transport = connection.sock
        connection.request("GET", resource)
        response = connection.getresponse()
        if response.status != 200:
            raise ValueError("Docker read unavailable")
        data = bytearray()
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or transport is None:
                raise TimeoutError("Diagnostic reader deadline")
            transport.settimeout(min(2, remaining))
            chunk = response.read1(min(4096, limit + 1 - len(data)))
            if not chunk:
                return bytes(data)
            data.extend(chunk)
            if len(data) > limit:
                raise ValueError("Docker read bound")
    finally:
        if response is not None:
            response.close()
        connection.close()


def _read_docker(endpoint: str, container: str, project: str, attempt: str) -> list[UiRecord]:
    if (
        not re.fullmatch(r"[0-9a-f]{64}", container)
        or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,127}", project)
        or not re.fullmatch(r"[0-9a-f]{32}|[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", attempt)
    ):
        raise ValueError("Invalid supplied owner")
    if not endpoint.startswith("unix://"):
        raise ValueError("Local Unix endpoint required")
    path = Path(endpoint.removeprefix("unix://"))
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("Unsafe endpoint")
    info = path.stat(follow_symlinks=False)
    if not stat.S_ISSOCK(info.st_mode) or info.st_uid not in {0, os.getuid()}:
        raise ValueError("Foreign socket")
    deadline = time.monotonic() + 6
    inspected: object = json.loads(
        _get(str(path), f"/containers/{container}/json", deadline, 65536)
    )
    validate_owner(inspected, container, project, attempt)
    # Only stderr; no follow, no provider calls. Docker's multiplex frames are bounded too.
    raw = _get(
        str(path),
        f"/containers/{container}/logs?stdout=0&stderr=1&tail=256&timestamps=0",
        deadline,
        MAX_BYTES,
    )
    data = bytearray()
    while raw:
        if len(raw) < 8 or raw[0] != 2 or raw[1:4] != b"\0\0\0":
            raise ValueError("Invalid stderr frame")
        length = int.from_bytes(raw[4:8], "big")
        if length > len(raw) - 8:
            raise ValueError("Truncated stderr frame")
        data.extend(raw[8 : 8 + length])
        raw = raw[8 + length :]
    return read_records(bytes(data))


def _timeout(signum: int, frame: FrameType | None) -> Never:
    raise TimeoutError("Private diagnostic reader deadline")


def read_docker(endpoint: str, container: str, project: str, attempt: str) -> list[UiRecord]:
    # Bound headers/connect as well as payload; never replace another owner's active timer.
    previous = signal.getsignal(signal.SIGALRM)
    if previous is None or signal.getitimer(signal.ITIMER_REAL) != (0.0, 0.0):
        raise ValueError("Reader requires an unowned main-thread deadline")
    signal.signal(signal.SIGALRM, _timeout)
    signal.setitimer(signal.ITIMER_REAL, 6)
    try:
        return _read_docker(endpoint, container, project, attempt)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)
