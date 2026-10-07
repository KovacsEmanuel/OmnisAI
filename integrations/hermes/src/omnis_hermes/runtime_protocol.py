"""Bounded native newline-JSON; IDs keep their JSON type."""

import asyncio
import json
import math
from collections import deque
from contextlib import suppress

MAX_FRAME = 64 * 1024
MAX_PENDING = 32
MAX_QUEUED = 1024 * 1024
SAFE_UNKNOWN = "omnis.inert.probe_unknown"
ALLOWED = frozenset({"ping", "client.capabilities", "gateway.capabilities", SAFE_UNKNOWN})


class ProtocolError(ValueError):
    """Sanitized framing or transport failure."""


class RPCError(ProtocolError):
    def __init__(self, code: int):
        self.code = code
        super().__init__("Native RPC refused")


def unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ProtocolError("Duplicate member")
        result[key] = value
    return result


def valid_id(value: object) -> bool:
    return (type(value) is int and -(2**53) < value < 2**53) or (
        type(value) is str and 0 < len(value) <= 128
    )


def _constant(value: str) -> object:
    raise ProtocolError("Nonfinite JSON")


def _finite_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ProtocolError("Nonfinite JSON")
    return number


def encode(frame: dict[str, object]) -> bytes:
    try:
        raw = json.dumps(frame, separators=(",", ":"), allow_nan=False).encode() + b"\n"
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise ProtocolError("Invalid JSON") from None
    if len(raw) > MAX_FRAME:
        raise ProtocolError("Frame limit")
    return raw


def decode(raw: bytes) -> dict[str, object]:
    if len(raw) > MAX_FRAME or not raw.endswith(b"\n"):
        raise ProtocolError("Frame limit or framing")
    try:
        value = json.loads(
            raw,
            object_pairs_hook=unique_object,
            parse_constant=_constant,
            parse_float=_finite_float,
        )
    except (ValueError, UnicodeError, RecursionError):
        raise ProtocolError("Invalid JSON") from None
    if type(value) is not dict or value.get("jsonrpc") != "2.0":
        raise ProtocolError("Invalid JSON-RPC")
    if "id" in value and not valid_id(value["id"]):
        raise ProtocolError("Invalid ID")
    if "method" in value:
        if type(value["method"]) is not str or not value["method"]:
            raise ProtocolError("Invalid method")
        if "result" in value or "error" in value or type(value.get("params", {})) is not dict:
            raise ProtocolError("Invalid request")
    elif "id" not in value or ("result" in value) == ("error" in value):
        raise ProtocolError("Invalid response")
    if "error" in value:
        error = value["error"]
        if type(error) is not dict or type(error.get("code")) is not int:
            raise ProtocolError("Invalid error")
    return value


class NativePeer:
    """One owner, typed correlation, bounded buffers; stderr is discarded."""

    def __init__(self, process: asyncio.subprocess.Process, timeout: float = 1.0):
        self.process = process
        self.timeout = timeout
        self.pending: dict[tuple[type, object], asyncio.Future[object]] = {}
        self.next_id = 0
        self.queue: asyncio.Queue[bytes] = asyncio.Queue(MAX_PENDING)
        self.queued_bytes = 0
        self.events: deque[dict[str, object]] = deque(maxlen=16)
        self.reverse: dict[tuple[type, object], str] = {}
        self.cancelled: deque[tuple[object, str]] = deque(maxlen=32)
        self.late: deque[tuple[type, object]] = deque(maxlen=32)
        self.ready = asyncio.get_running_loop().create_future()
        self.failure: ProtocolError | None = None
        self.tasks = [
            asyncio.create_task(self._read()),
            asyncio.create_task(self._write()),
            asyncio.create_task(self._stderr()),
        ]

    def _fail(self) -> None:
        self.failure = ProtocolError("Native transport unavailable")
        for future in self.pending.values():
            if not future.done():
                future.set_exception(self.failure)
        if not self.ready.done():
            self.ready.set_exception(self.failure)

    def _enqueue(self, frame: dict[str, object]) -> None:
        if self.failure is not None:
            raise self.failure
        raw = encode(frame)
        if self.queued_bytes + len(raw) > MAX_QUEUED or self.queue.full():
            raise ProtocolError("Native backpressure")
        self.queued_bytes += len(raw)
        self.queue.put_nowait(raw)

    async def _write(self) -> None:
        assert self.process.stdin is not None
        try:
            while True:
                raw = await self.queue.get()
                self.process.stdin.write(raw)
                await asyncio.wait_for(self.process.stdin.drain(), self.timeout)
                self.queued_bytes -= len(raw)
        except (OSError, TimeoutError, ProtocolError):
            self._fail()

    async def _stderr(self) -> None:
        assert self.process.stderr is not None
        while await self.process.stderr.read(8192):
            pass  # Never retain or log raw diagnostics/credentials.

    async def _read(self) -> None:
        assert self.process.stdout is not None
        try:
            while True:
                frame = decode(await self.process.stdout.readuntil(b"\n"))
                if "method" not in frame:
                    key = (type(frame["id"]), frame["id"])
                    future = self.pending.get(key)
                    if future is None:
                        if key in self.late:
                            continue
                        raise ProtocolError("Uncorrelated response")
                    if future.done():
                        raise ProtocolError("Repeated response")
                    if "error" in frame:
                        error = frame["error"]
                        assert isinstance(error, dict)
                        code = error["code"]
                        assert isinstance(code, int)
                        future.set_exception(RPCError(code))
                    else:
                        future.set_result(frame["result"])
                elif "id" in frame:
                    key = (type(frame["id"]), frame["id"])
                    if len(self.reverse) >= MAX_PENDING or key in self.reverse:
                        raise ProtocolError("Reverse request limit")
                    method = frame["method"]
                    assert isinstance(method, str)
                    self.reverse[key] = method
                    reply = {"jsonrpc": "2.0", "id": frame["id"]}
                    if frame["method"] == "approval":
                        reply["result"] = {"choice": "deny"}
                    else:
                        reply["error"] = {"code": -32601, "message": "Method not allowed"}
                    self._enqueue(reply)
                elif frame["method"] == "event":
                    event = frame.get("params", {})
                    assert isinstance(event, dict)
                    self.events.append(event)
                    if event.get("type") == "gateway.ready" and not self.ready.done():
                        self.ready.set_result(True)
                    if event.get("type") == "request.cancel":
                        payload = event.get("payload", {})
                        if type(payload) is dict and valid_id(payload.get("id")):
                            key = (type(payload["id"]), payload["id"])
                            method = self.reverse.get(key)
                            if method is not None and method == payload.get("method"):
                                self.reverse.pop(key)
                                self.cancelled.append((payload["id"], method))
        except (ValueError, OSError, asyncio.IncompleteReadError, asyncio.LimitOverrunError):
            self._fail()

    async def call(self, method: str, params: dict[str, object]) -> object:
        # Validate BEFORE allocating correlation or touching the writer.
        if method not in ALLOWED or (
            params != {}
            and not (
                method == "client.capabilities"
                and params == {"server_requests": True}
                and type(params.get("server_requests")) is bool
            )
        ):
            raise ProtocolError("Method or parameters not allowed")
        if len(self.pending) >= MAX_PENDING:
            raise ProtocolError("Pending limit")
        self.next_id += 1
        key = (int, self.next_id)
        future = asyncio.get_running_loop().create_future()
        self.pending[key] = future
        try:
            self._enqueue(
                {"jsonrpc": "2.0", "id": self.next_id, "method": method, "params": params}
            )
            return await asyncio.wait_for(asyncio.shield(future), self.timeout)
        except TimeoutError:
            raise ProtocolError("Native RPC deadline") from None
        finally:
            self.pending.pop(key, None)
            self.late.append(key)
            if not future.done():
                future.cancel()
            elif not future.cancelled():
                future.exception()  # Observe a racing transport failure.

    async def handshake(self) -> dict[str, object]:
        try:
            await asyncio.wait_for(asyncio.shield(self.ready), self.timeout)
        except TimeoutError:
            raise ProtocolError("Native ready deadline") from None
        await self.call("client.capabilities", {"server_requests": True})
        capabilities = await self.call("gateway.capabilities", {})
        if (
            type(capabilities) is not dict
            or capabilities.get("per_session_exclusive_submit") is not True
        ):
            raise ProtocolError("Required capabilities missing")
        try:
            await self.call(SAFE_UNKNOWN, {})
        except RPCError as error:
            if error.code != -32601:
                raise ProtocolError("Unexpected unknown probe") from None
        else:
            raise ProtocolError("Unknown probe was accepted")
        return capabilities

    async def close(self) -> None:
        self._fail()
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        if self.ready.done() and not self.ready.cancelled():
            self.ready.exception()
        if self.process.stdin is not None:
            self.process.stdin.close()
            with suppress(OSError, TimeoutError):
                await asyncio.wait_for(self.process.stdin.wait_closed(), self.timeout)
