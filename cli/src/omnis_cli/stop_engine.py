"""Childless Stop-only Engine client. No URL, exec, create, proxy or retry API."""

import json
import re
import socket
import struct
import time
from pathlib import Path
from urllib.parse import quote

from .compose import _checked_socket
from .instance import unique_pairs
from .lifecycle import StartError, mapping

MAX_RESPONSE = 1024 * 1024


def identifier(value: str) -> str:
    if type(value) is not str or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise StartError("STOP_ENGINE_IDENTIFIER_INVALID", 4)
    return value


class StopEngine:
    def __init__(self, host: str, daemon_id: str, deadline: float) -> None:
        self.host = _checked_socket(host)
        self.path = Path(self.host[7:])
        info = self.path.stat()
        self.identity = (info.st_dev, info.st_ino)
        self.peer: bytes | None = None
        self.daemon_id, self.deadline = daemon_id, deadline

    def _remaining(self) -> float:
        value = self.deadline - time.monotonic()
        if value <= 0:
            raise StartError("STOP_ENGINE_TIMEOUT", 4)
        return value

    def _request(self, method: str, path: str, *, absent: bool = False) -> tuple[int, bytes]:
        # Only the fixed typed methods below construct method/path; never payload input.
        if _checked_socket(self.host) != self.host:
            raise StartError("STOP_ENGINE_CHANGED", 4)
        info = self.path.stat()
        if (info.st_dev, info.st_ino) != self.identity:
            raise StartError("STOP_ENGINE_CHANGED", 4)
        with socket.socket(socket.AF_UNIX) as connection:
            connection.settimeout(self._remaining())
            connection.connect(str(self.path))
            peer = connection.getsockopt(
                socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i")
            )
            if self.peer is not None and self.peer != peer:
                raise StartError("STOP_ENGINE_CHANGED", 4)
            self.peer = peer
            connection.settimeout(self._remaining())
            connection.sendall(
                f"{method} {path} HTTP/1.1\r\nHost: docker\r\nConnection: close\r\nContent-Length: 0\r\n\r\n".encode(
                    "ascii"
                )
            )
            buffer = bytearray()
            total = 0

            def receive() -> None:
                nonlocal total
                connection.settimeout(self._remaining())
                part = connection.recv(min(65536, MAX_RESPONSE + 1 - total))
                total += len(part)
                if not part or total > MAX_RESPONSE:
                    raise StartError("STOP_ENGINE_RESPONSE_INVALID", 4)
                buffer.extend(part)

            def line(limit: int = 16384) -> bytes:
                while b"\r\n" not in buffer:
                    if len(buffer) >= limit:
                        raise StartError("STOP_ENGINE_RESPONSE_INVALID", 4)
                    receive()
                end = buffer.index(b"\r\n")
                if end + 2 > limit:
                    raise StartError("STOP_ENGINE_RESPONSE_INVALID", 4)
                result = bytes(buffer[:end])
                del buffer[: end + 2]
                return result

            status_line = line()
            if re.fullmatch(rb"HTTP/1\.[01] [0-9]{3} [^\r\n]*", status_line) is None:
                raise StartError("STOP_ENGINE_RESPONSE_INVALID", 4)
            status = int(status_line.split(b" ", 2)[1])
            headers: dict[bytes, bytes] = {}
            header_bytes = len(status_line) + 2
            while True:
                field = line(16384 - header_bytes)
                header_bytes += len(field) + 2
                if not field:
                    break
                if b":" not in field:
                    raise StartError("STOP_ENGINE_RESPONSE_INVALID", 4)
                key, value = field.split(b":", 1)
                key, value = key.lower(), value.strip()
                if key in headers or not re.fullmatch(rb"[a-z0-9-]+", key):
                    raise StartError("STOP_ENGINE_RESPONSE_INVALID", 4)
                headers[key] = value
            expected = 200 if method == "GET" else 204
            if status != expected and not (method == "GET" and absent and status == 404):
                raise StartError("STOP_ENGINE_ACK_UNCERTAIN", 4)
            if status == 204:
                if (
                    buffer
                    or headers.get(b"transfer-encoding")
                    or headers.get(b"content-length", b"0") != b"0"
                ):
                    raise StartError("STOP_ENGINE_ACK_UNCERTAIN", 4)
                return status, b""
            body = bytearray()
            transfer, length = headers.get(b"transfer-encoding"), headers.get(b"content-length")
            if transfer is not None:
                if transfer != b"chunked" or length is not None:
                    raise StartError("STOP_ENGINE_RESPONSE_INVALID", 4)
                while True:
                    chunk = line()
                    if not re.fullmatch(rb"[0-9a-fA-F]{1,8}", chunk):
                        raise StartError("STOP_ENGINE_RESPONSE_INVALID", 4)
                    size = int(chunk, 16)
                    if size > MAX_RESPONSE:
                        raise StartError("STOP_ENGINE_RESPONSE_INVALID", 4)
                    if size == 0:
                        if line() or buffer:
                            raise StartError("STOP_ENGINE_RESPONSE_INVALID", 4)
                        break
                    while len(buffer) < size + 2:
                        receive()
                    if buffer[size : size + 2] != b"\r\n":
                        raise StartError("STOP_ENGINE_RESPONSE_INVALID", 4)
                    body.extend(buffer[:size])
                    del buffer[: size + 2]
            elif length is not None and re.fullmatch(rb"[0-9]{1,8}", length):
                size = int(length)
                if size > MAX_RESPONSE:
                    raise StartError("STOP_ENGINE_RESPONSE_INVALID", 4)
                while len(buffer) < size:
                    receive()
                if len(buffer) != size:
                    raise StartError("STOP_ENGINE_RESPONSE_INVALID", 4)
                body.extend(buffer)
            else:
                raise StartError("STOP_ENGINE_RESPONSE_INVALID", 4)
            return status, bytes(body)

    def _json(self, path: str, *, absent: bool = False) -> object:
        status, raw = self._request("GET", path, absent=absent)
        if status == 404:
            return None
        try:
            value: object = json.loads(raw, object_pairs_hook=unique_pairs)
        except (ValueError, UnicodeError, RecursionError):
            raise StartError("STOP_ENGINE_RESPONSE_INVALID", 4) from None
        # Only inspect endpoints allow 404. For their 200 replies, require an
        # object before returning: decoded null must never become absence.
        if absent and not isinstance(value, dict):
            raise StartError("STOP_ENGINE_RESPONSE_INVALID", 4)
        pending = [(value, 0)]
        while pending:
            item, depth = pending.pop()
            self._remaining()
            if depth > 32:
                raise StartError("STOP_ENGINE_RESPONSE_INVALID", 4)
            if isinstance(item, dict):
                pending.extend((child, depth + 1) for child in item.values())
            elif isinstance(item, list):
                pending.extend((child, depth + 1) for child in item)
        return value

    def check_daemon(self) -> None:
        if mapping(self._json("/info")).get("ID") != self.daemon_id:
            raise StartError("STOP_ENGINE_CHANGED", 4)

    def container(self, cid: str) -> dict[str, object] | None:
        item = self._json(f"/containers/{identifier(cid)}/json", absent=True)
        return None if item is None else mapping(item)

    def network(self, ident: str) -> dict[str, object] | None:
        item = self._json(f"/networks/{identifier(ident)}", absent=True)
        return None if item is None else mapping(item)

    def image(self, ident: str) -> dict[str, object]:
        if re.fullmatch(r"sha256:[0-9a-f]{64}", ident) is None:
            raise StartError("STOP_ENGINE_IDENTIFIER_INVALID", 4)
        return mapping(self._json(f"/images/{ident}/json"))

    def containers(self, project: str) -> list[str]:
        query = quote(
            json.dumps({"label": [f"com.docker.compose.project={project}"]}, separators=(",", ":")),
            safe="",
        )
        items = self._json(f"/containers/json?all=true&filters={query}")
        if not isinstance(items, list):
            raise StartError("STOP_ENGINE_RESPONSE_INVALID", 4)
        ids = [identifier(str(mapping(item).get("Id"))) for item in items]
        if len(ids) != len(set(ids)):
            raise StartError("STOP_ENGINE_RESPONSE_INVALID", 4)
        return ids

    def networks(self, project: str) -> list[dict[str, object]]:
        query = quote(
            json.dumps({"label": [f"com.docker.compose.project={project}"]}, separators=(",", ":")),
            safe="",
        )
        items = self._json(f"/networks?filters={query}")
        if not isinstance(items, list):
            raise StartError("STOP_ENGINE_RESPONSE_INVALID", 4)
        return [mapping(item) for item in items]

    def stop_container(self, cid: str) -> int:
        self.check_daemon()
        return self._request("POST", f"/containers/{identifier(cid)}/stop?t=15")[0]

    def remove_container(self, cid: str) -> int:
        identifier(cid)
        self.check_daemon()
        return self._request("DELETE", f"/containers/{cid}?force=false&v=false")[0]

    def remove_network(self, ident: str) -> int:
        identifier(ident)
        self.check_daemon()
        return self._request("DELETE", f"/networks/{ident}")[0]
