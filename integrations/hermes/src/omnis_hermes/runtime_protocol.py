"""Bounded native newline-JSON; IDs keep their JSON type."""

import asyncio
import json
import math
from collections import deque
from contextlib import suppress
from typing import Literal, TypedDict

from . import managed_admission_contract as managed

MAX_FRAME = 64 * 1024
MAX_PENDING = 32
MAX_QUEUED = 1024 * 1024
SAFE_UNKNOWN = "omnis.inert.probe_unknown"
ALLOWED = frozenset(
    {"ping", "client.capabilities", "gateway.capabilities", SAFE_UNKNOWN}
) | frozenset(managed.RPC.values())


class ProtocolError(ValueError):
    """Sanitized framing or transport failure."""


MAX_INVENTORY = 24 * 1024


class RegistryEntry(TypedDict):
    name: str
    toolset: str


class PluginEntry(TypedDict):
    name: str
    loaded: bool
    enabled: bool
    deferred: bool
    error_present: bool


class RegistrySnapshot(TypedDict):
    status: str
    generation: int | None
    count: int | None
    entries: list[RegistryEntry] | None


class PluginSnapshot(TypedDict):
    status: str
    count: int | None
    entries: list[PluginEntry] | None


class BootstrapInventory(TypedDict):
    schema_version: Literal[1]
    observation: Literal["NATIVE_BOOTSTRAP"]
    scope: Literal["/state/active"]
    registry: RegistrySnapshot
    plugins: PluginSnapshot


def _inventory_name(value: object) -> str:
    if (
        type(value) is not str
        or not 0 < len(value) <= 128
        or any(
            ord(c) < 32 or 127 <= ord(c) <= 159 or 0xD800 <= ord(c) <= 0xDFFF or c in "/\\"
            for c in value
        )
    ):
        raise ProtocolError("Invalid bootstrap inventory")
    return value


def validate_bootstrap_inventory(value: object) -> BootstrapInventory:
    """Frozen bootstrap schema. Reject, never coerce or retain native metadata."""
    if (
        type(value) is not dict
        or set(value) != {"schema_version", "observation", "scope", "registry", "plugins"}
        or type(value["schema_version"]) is not int
        or value["schema_version"] != 1
        or value["observation"] != "NATIVE_BOOTSTRAP"
        or value["scope"] != "/state/active"
    ):
        raise ProtocolError("Invalid bootstrap inventory")
    registry, plugins = value["registry"], value["plugins"]
    if type(registry) is not dict or set(registry) != {"status", "generation", "count", "entries"}:
        raise ProtocolError("Invalid bootstrap inventory")
    if type(plugins) is not dict or set(plugins) != {"status", "count", "entries"}:
        raise ProtocolError("Invalid bootstrap inventory")
    status = registry["status"]
    missing = {"NOT_INITIALIZED", "NOT_OBSERVED_BUSY", "LIMIT_EXCEEDED", "NOT_OBSERVED_INVALID"}
    if type(status) is not str:
        raise ProtocolError("Invalid bootstrap inventory")
    rs: RegistrySnapshot = {"status": status, "generation": None, "count": None, "entries": None}
    if status == "REGISTERED_SNAPSHOT":
        generation, count, entries = registry["generation"], registry["count"], registry["entries"]
        if (
            type(generation) is not int
            or generation < 0
            or type(count) is not int
            or not 0 <= count <= 256
            or type(entries) is not list
            or len(entries) != count
        ):
            raise ProtocolError("Invalid bootstrap inventory")
        rows: list[RegistryEntry] = []
        last = ""
        for row in entries:
            if type(row) is not dict or set(row) != {"name", "toolset"}:
                raise ProtocolError("Invalid bootstrap inventory")
            name, toolset = _inventory_name(row["name"]), _inventory_name(row["toolset"])
            if name <= last:
                raise ProtocolError("Invalid bootstrap inventory")
            last = name
            rows.append({"name": name, "toolset": toolset})
        rs = {"status": status, "generation": generation, "count": count, "entries": rows}
    elif status not in missing or any(
        registry[k] is not None for k in ("generation", "count", "entries")
    ):
        raise ProtocolError("Invalid bootstrap inventory")
    status = plugins["status"]
    if type(status) is not str:
        raise ProtocolError("Invalid bootstrap inventory")
    ps: PluginSnapshot = {"status": status, "count": None, "entries": None}
    if status == "PLUGIN_SNAPSHOT":
        count, entries = plugins["count"], plugins["entries"]
        if (
            type(count) is not int
            or not 0 <= count <= 128
            or type(entries) is not list
            or len(entries) != count
        ):
            raise ProtocolError("Invalid bootstrap inventory")
        plugin_rows: list[PluginEntry] = []
        last = ""
        for row in entries:
            keys = {"name", "loaded", "enabled", "deferred", "error_present"}
            if (
                type(row) is not dict
                or set(row) != keys
                or any(type(row[k]) is not bool for k in keys - {"name"})
            ):
                raise ProtocolError("Invalid bootstrap inventory")
            name = _inventory_name(row["name"])
            if name <= last:
                raise ProtocolError("Invalid bootstrap inventory")
            last = name
            plugin_rows.append(
                {
                    "name": name,
                    "loaded": row["loaded"],
                    "enabled": row["enabled"],
                    "deferred": row["deferred"],
                    "error_present": row["error_present"],
                }
            )
        ps = {"status": status, "count": count, "entries": plugin_rows}
    elif status not in missing | {"NOT_OBSERVED_IN_PROGRESS"} or any(
        plugins[k] is not None for k in ("count", "entries")
    ):
        raise ProtocolError("Invalid bootstrap inventory")
    result: BootstrapInventory = {
        "schema_version": 1,
        "observation": "NATIVE_BOOTSTRAP",
        "scope": "/state/active",
        "registry": rs,
        "plugins": ps,
    }
    try:
        size = len(json.dumps(result, ensure_ascii=False, allow_nan=False).encode("utf-8"))
    except (ValueError, UnicodeError):
        raise ProtocolError("Invalid bootstrap inventory") from None
    if size > MAX_INVENTORY:
        raise ProtocolError("Bootstrap inventory limit")
    return result


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
        self.queue: asyncio.Queue[tuple[bytes, tuple[type, object] | None]] = asyncio.Queue(
            MAX_PENDING
        )
        self.queued_bytes = 0
        self.events: deque[dict[str, object]] = deque(maxlen=16)
        # None marks a consumed cancellation; its ID stays reserved until drain/eviction.
        self.reverse: dict[tuple[type, object], str | None] = {}
        self.reverse_done: dict[tuple[type, object], str | None] = {}
        self.cancelled: deque[tuple[object, str]] = deque(maxlen=32)
        self.late: deque[tuple[type, object]] = deque(maxlen=32)
        self.ready = asyncio.get_running_loop().create_future()
        self.bootstrap_inventory: BootstrapInventory | None = None
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

    def _enqueue(
        self, frame: dict[str, object], reverse_key: tuple[type, object] | None = None
    ) -> None:
        if self.failure is not None:
            raise self.failure
        raw = encode(frame)
        if self.queued_bytes + len(raw) > MAX_QUEUED or self.queue.full():
            raise ProtocolError("Native backpressure")
        self.queued_bytes += len(raw)
        self.queue.put_nowait((raw, reverse_key))

    async def _write(self) -> None:
        assert self.process.stdin is not None
        try:
            while True:
                raw, reverse_key = await self.queue.get()
                self.process.stdin.write(raw)
                await asyncio.wait_for(self.process.stdin.drain(), self.timeout)
                self.queued_bytes -= len(raw)
                if reverse_key is not None:
                    # Only a successful drain releases queued/in-flight reverse quota.
                    self.reverse_done[reverse_key] = self.reverse.pop(reverse_key)
                    if len(self.reverse_done) > MAX_PENDING:
                        del self.reverse_done[next(iter(self.reverse_done))]
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
                    if (
                        len(self.reverse) >= MAX_PENDING
                        or key in self.reverse
                        or key in self.reverse_done
                    ):
                        raise ProtocolError("Reverse request limit")
                    method = frame["method"]
                    assert isinstance(method, str)
                    self.reverse[key] = method
                    reply = {"jsonrpc": "2.0", "id": frame["id"]}
                    if frame["method"] == "approval":
                        reply["result"] = {"choice": "deny"}
                    else:
                        reply["error"] = {"code": -32601, "message": "Method not allowed"}
                    self._enqueue(reply, key)
                elif frame["method"] == "event":
                    event = frame.get("params", {})
                    assert isinstance(event, dict)
                    self.events.append(event)
                    if event.get("type") == "gateway.ready":
                        if self.ready.done():
                            raise ProtocolError("Repeated ready")
                        payload = event.get("payload")
                        if type(payload) is not dict:
                            raise ProtocolError("Invalid ready")
                        self.bootstrap_inventory = validate_bootstrap_inventory(
                            payload.get("bootstrap_inventory")
                        )
                        self.ready.set_result(True)
                    if event.get("type") == "request.cancel":
                        payload = event.get("payload", {})
                        if type(payload) is not dict or not valid_id(payload.get("id")):
                            raise ProtocolError("Invalid reverse cancellation")
                        key = (type(payload["id"]), payload["id"])
                        method = self.reverse.get(key, self.reverse_done.get(key))
                        if method is None or method != payload.get("method"):
                            raise ProtocolError("Uncorrelated reverse cancellation")
                        if key in self.reverse:
                            self.reverse[key] = None
                        else:
                            self.reverse_done[key] = None
                        self.cancelled.append((payload["id"], method))
        except (ValueError, OSError, asyncio.IncompleteReadError, asyncio.LimitOverrunError):
            self._fail()

    async def call(
        self, method: str, params: dict[str, object], *, timeout: float | None = None
    ) -> object:
        # Validate BEFORE allocating correlation or touching the writer.
        managed_method = method in managed.RPC.values()
        if managed_method:
            {
                managed.RPC["task_stage"]: managed.validate_stage,
                managed.RPC["task_release"]: managed.validate_release,
                managed.RPC["task_status"]: managed.validate_status,
                managed.RPC["task_model_preflight"]: managed.validate_model_preflight,
                managed.RPC["task_model_initialize"]: managed.validate_initialization,
            }[method](params)
        if timeout is not None and (
            not managed_method
            or type(timeout) not in (float, int)
            or not math.isfinite(timeout)
            or not 0 < timeout <= 3.2
        ):
            raise ProtocolError("Invalid managed deadline")
        if method not in ALLOWED or (
            not managed_method
            and (
                params != {}
                and not (
                    method == "client.capabilities"
                    and params == {"server_requests": True}
                    and type(params.get("server_requests")) is bool
                )
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
            return await asyncio.wait_for(
                asyncio.shield(future), self.timeout if timeout is None else timeout
            )
        except TimeoutError:
            raise ProtocolError("Native RPC deadline") from None
        finally:
            self.pending.pop(key, None)
            self.late.append(key)
            if not future.done():
                future.cancel()
            elif not future.cancelled():
                future.exception()  # Observe a racing transport failure.

    async def handshake(self, *, ready_timeout: float | None = None) -> dict[str, object]:
        startup_budget = self.timeout if ready_timeout is None else ready_timeout
        if (
            type(startup_budget) not in (int, float)
            or not math.isfinite(startup_budget)
            or not 0 < startup_budget <= 10
        ):
            raise ProtocolError("Invalid startup deadline")
        try:
            await asyncio.wait_for(asyncio.shield(self.ready), startup_budget)
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
