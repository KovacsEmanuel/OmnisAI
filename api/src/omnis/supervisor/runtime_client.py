"""Supervisor-only bounded UDS client; no Hermes imports or arbitrary RPC API."""

import asyncio
import json
import os
import re
import socket
import stat
import struct
import time
from contextlib import suppress
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import TYPE_CHECKING, Literal, TypedDict
from uuid import UUID, uuid4

from omnis.core.paths import check_private_file, private_directory

if TYPE_CHECKING:
    from omnis.modules.instance.service import InstanceService, RuntimeAuthority

MAX_FRAME = 64 * 1024
MANAGED_OPERATIONS = frozenset(
    {"task_stage", "task_release", "task_status", "task_model_preflight", "task_model_initialize"}
)


class RuntimeUnavailable(ValueError):
    """Sanitized runtime failure; never expose raw IPC or credentials."""


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
        raise RuntimeUnavailable("Invalid bootstrap inventory")
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
        raise RuntimeUnavailable("Invalid bootstrap inventory")
    registry, plugins = value["registry"], value["plugins"]
    if type(registry) is not dict or set(registry) != {"status", "generation", "count", "entries"}:
        raise RuntimeUnavailable("Invalid bootstrap inventory")
    if type(plugins) is not dict or set(plugins) != {"status", "count", "entries"}:
        raise RuntimeUnavailable("Invalid bootstrap inventory")
    status = registry["status"]
    missing = {"NOT_INITIALIZED", "NOT_OBSERVED_BUSY", "LIMIT_EXCEEDED", "NOT_OBSERVED_INVALID"}
    if type(status) is not str:
        raise RuntimeUnavailable("Invalid bootstrap inventory")
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
            raise RuntimeUnavailable("Invalid bootstrap inventory")
        rows: list[RegistryEntry] = []
        last = ""
        for row in entries:
            if type(row) is not dict or set(row) != {"name", "toolset"}:
                raise RuntimeUnavailable("Invalid bootstrap inventory")
            name, toolset = _inventory_name(row["name"]), _inventory_name(row["toolset"])
            if name <= last:
                raise RuntimeUnavailable("Invalid bootstrap inventory")
            last = name
            rows.append({"name": name, "toolset": toolset})
        rs = {"status": status, "generation": generation, "count": count, "entries": rows}
    elif status not in missing or any(
        registry[k] is not None for k in ("generation", "count", "entries")
    ):
        raise RuntimeUnavailable("Invalid bootstrap inventory")
    status = plugins["status"]
    if type(status) is not str:
        raise RuntimeUnavailable("Invalid bootstrap inventory")
    ps: PluginSnapshot = {"status": status, "count": None, "entries": None}
    if status == "PLUGIN_SNAPSHOT":
        count, entries = plugins["count"], plugins["entries"]
        if (
            type(count) is not int
            or not 0 <= count <= 128
            or type(entries) is not list
            or len(entries) != count
        ):
            raise RuntimeUnavailable("Invalid bootstrap inventory")
        plugin_rows: list[PluginEntry] = []
        last = ""
        for row in entries:
            keys = {"name", "loaded", "enabled", "deferred", "error_present"}
            if (
                type(row) is not dict
                or set(row) != keys
                or any(type(row[k]) is not bool for k in keys - {"name"})
            ):
                raise RuntimeUnavailable("Invalid bootstrap inventory")
            name = _inventory_name(row["name"])
            if name <= last:
                raise RuntimeUnavailable("Invalid bootstrap inventory")
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
        raise RuntimeUnavailable("Invalid bootstrap inventory")
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
        raise RuntimeUnavailable("Invalid bootstrap inventory") from None
    if size > MAX_INVENTORY:
        raise RuntimeUnavailable("Bootstrap inventory limit")
    return result


def _unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise RuntimeUnavailable("Invalid runtime message")
        result[key] = value
    return result


def _object(raw: bytes) -> dict[str, object]:
    if len(raw) > MAX_FRAME:
        raise RuntimeUnavailable("Runtime message limit")
    try:
        value: object = json.loads(raw, object_pairs_hook=_unique)
    except (ValueError, RecursionError, UnicodeError):
        raise RuntimeUnavailable("Invalid runtime message") from None
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise RuntimeUnavailable("Invalid runtime message")
    return {key: item for key, item in value.items()}


@dataclass(frozen=True)
class FrozenPreflight:
    """Memory-only secret-bearing frame. Never persist or log this object."""

    request_id: str
    boot: str
    generation: int
    epoch: int
    deadline_ns: int
    wall_seconds: int
    frame: bytes = field(repr=False)
    body: bytes = field(repr=False)

    @property
    def body_digest(self) -> str:
        return sha256(self.body).hexdigest()

    @property
    def frame_digest(self) -> str:
        return sha256(self.frame).hexdigest()


class RuntimeClient:
    def __init__(
        self, directory: Path, *, generation: int, epoch: int, peer_uid: int | None = None
    ) -> None:
        if type(generation) is not int or generation < 0 or type(epoch) is not int or epoch < 1:
            raise RuntimeUnavailable("Invalid runtime fence")
        self.directory = directory
        self.generation = generation
        self.epoch = epoch
        self.peer_uid = os.getuid() if peer_uid is None else peer_uid
        self.boot = ""
        self.capability = ""
        self.reader: asyncio.StreamReader | None = None
        self.writer: asyncio.StreamWriter | None = None
        self.lock = asyncio.Lock()
        self.recovery_lock = asyncio.Lock()
        self.bootstrap_inventory: BootstrapInventory | None = None
        self._initial_management_bind = True
        self._stop_serial = 0

    async def connect(self) -> None:
        private_directory(self.directory)
        fd = os.open(self.directory / "runtime.boot", os.O_RDONLY | os.O_NOFOLLOW)
        try:
            check_private_file(os.fstat(fd))
            with os.fdopen(fd, "rb", closefd=False) as source:
                metadata = _object(source.read(4097))
            boot, capability = metadata.get("boot"), metadata.get("capability")
            if (
                set(metadata) != {"version", "boot", "capability"}
                or type(metadata["version"]) is not int
                or metadata["version"] != 1
                or not isinstance(boot, str)
                or str(UUID(boot)) != boot
                or not isinstance(capability, str)
                or re.fullmatch("[0-9a-f]{64}", capability) is None
            ):
                raise RuntimeUnavailable("Invalid runtime identity")
            self.boot, self.capability = boot, capability
        finally:
            os.close(fd)
        info = (self.directory / "runtime.sock").lstat()
        if (
            not stat.S_ISSOCK(info.st_mode)
            or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o600
        ):
            raise RuntimeUnavailable("Invalid runtime socket")
        try:
            async with asyncio.timeout(1):
                self.reader, self.writer = await asyncio.open_unix_connection(
                    str(self.directory / "runtime.sock"), limit=MAX_FRAME
                )
                peer = self.writer.get_extra_info("socket").getsockopt(
                    socket.SOL_SOCKET, socket.SO_PEERCRED, 12
                )
                if struct.unpack("3i", peer)[1] != self.peer_uid:
                    raise RuntimeUnavailable("Runtime peer denied")
        except BaseException:
            await self.close()
            raise

    def freeze_preflight(
        self, authority: "RuntimeAuthority", payload: dict[str, object], *, wall_seconds: int
    ) -> FrozenPreflight:
        if type(wall_seconds) is not int or not 1 <= wall_seconds <= 3:
            raise RuntimeUnavailable("Runtime protocol cap denied")
        if payload.get("protocol") not in (
            "omnis-managed-admission-v2",
            "omnis-managed-admission-v3",
        ):
            raise RuntimeUnavailable("Runtime protocol denied")
        body = json.dumps(payload, separators=(",", ":"), allow_nan=False).encode()
        if len(body) > 32768:
            raise RuntimeUnavailable("Runtime payload limit")
        correlation = str(uuid4())
        frame = (
            json.dumps(
                {
                    "version": 1,
                    "id": correlation,
                    "boot": self.boot,
                    "capability": self.capability,
                    "generation": self.generation,
                    "epoch": self.epoch,
                    "op": "task_model_preflight",
                    "deadline_ns": authority.deadline_ns,
                    "payload": _object(body),
                },
                separators=(",", ":"),
                allow_nan=False,
            ).encode()
            + b"\n"
        )
        frozen = FrozenPreflight(
            correlation,
            self.boot,
            authority.generation,
            authority.epoch,
            authority.deadline_ns,
            wall_seconds,
            frame,
            body,
        )
        self.validate_frozen(frozen)
        return frozen

    def validate_frozen(self, frozen: FrozenPreflight) -> None:
        if len(frozen.frame) > MAX_FRAME:
            raise RuntimeUnavailable("Runtime managed-task limit")
        if (frozen.boot, frozen.generation, frozen.epoch) != (
            self.boot,
            self.generation,
            self.epoch,
        ):
            raise RuntimeUnavailable("Runtime authority mismatch")
        if time.monotonic_ns() >= frozen.deadline_ns:
            raise RuntimeUnavailable("Expired runtime authority")
        if self.reader is None or self.writer is None:
            raise RuntimeUnavailable("Runtime disconnected")

    async def exchange_frozen(self, frozen: FrozenPreflight) -> dict[str, object]:
        from omnis.modules.instance.service import RuntimeAuthority

        try:
            return await self._exchange(
                "task_model_preflight",
                RuntimeAuthority(frozen.generation, frozen.epoch, frozen.deadline_ns),
                _object(frozen.body),
                _frozen=frozen,
            )
        except BaseException:
            self.retire_frozen()
            raise

    def retire_frozen(self) -> None:
        """Retire uncertain protocol bytes before the caller releases its fence.

        Abort discards buffered output synchronously; no fresh close timeout can
        extend an expired owner/grant. Ordinary graceful close stays unchanged.
        """
        writer, self.writer = self.writer, None
        self.reader = None
        if writer is not None:
            with suppress(OSError):
                writer.transport.abort()

    async def _exchange(
        self,
        op: str,
        authority: "RuntimeAuthority | None" = None,
        payload: dict[str, object] | None = None,
        *,
        _frozen: FrozenPreflight | None = None,
        _settings_stop_serial: int | None = None,
    ) -> dict[str, object]:
        if (
            op
            not in {
                "launch",
                "status",
                "renew",
                "stop",
                "prepare",
                "task_receive",
                "settings",
                "settings_status",
            }
            | MANAGED_OPERATIONS
        ):
            raise RuntimeUnavailable("Runtime operation denied")
        if (
            op in {"prepare", "task_receive", "settings", "settings_status"}
            or op in MANAGED_OPERATIONS
        ) != (payload is not None):
            raise RuntimeUnavailable("Runtime payload denied")
        if op == "task_receive" and authority is not None:
            raise RuntimeUnavailable("Receive-only authority denied")
        if (
            op in {"launch", "renew", "prepare", "settings"} | MANAGED_OPERATIONS
            and authority is None
        ):
            raise RuntimeUnavailable("Runtime authority missing")
        async with self.lock:
            if op == "stop":
                self._stop_serial += 1
            if op == "settings" and _settings_stop_serial != self._stop_serial:
                raise RuntimeUnavailable("Settings overtaken by Stop")
            if (
                op == "settings"
                and authority is not None
                and authority.generation != self.generation
            ):
                if (
                    not self._initial_management_bind
                    or authority.epoch != self.epoch
                    or authority.generation != self.generation + 1
                ):
                    raise RuntimeUnavailable("Runtime authority mismatch")
                # Keep the same boot/stream, and serialize observation + bind + send
                # against every other operation, including Stop. Never hold this
                # lock while obtaining DB authority (quiesce holds DB -> runtime).
                observed = await self._exchange_locked("status")
                if observed["state"] != "IDLE":
                    raise RuntimeUnavailable("Fresh idle runtime required")
                if time.monotonic_ns() >= authority.deadline_ns:
                    raise RuntimeUnavailable("Expired runtime authority")
                self.generation = authority.generation
            if op not in {"status", "settings_status", "task_receive", "stop"}:
                self._initial_management_bind = False
            response = await self._exchange_locked(op, authority, payload, _frozen=_frozen)
            if op == "stop" and response["state"] != "IDLE":
                self._initial_management_bind = False
            return response

    async def _exchange_locked(
        self,
        op: str,
        authority: "RuntimeAuthority | None" = None,
        payload: dict[str, object] | None = None,
        *,
        _frozen: FrozenPreflight | None = None,
    ) -> dict[str, object]:
        if self.reader is None or self.writer is None:
            raise RuntimeUnavailable("Runtime disconnected")
        if _frozen is not None:
            self.validate_frozen(_frozen)
            correlation = _frozen.request_id
            timeout = min(
                3.2,
                _frozen.wall_seconds,
                (_frozen.deadline_ns - time.monotonic_ns()) / 1_000_000_000,
            )
            frame = _frozen.frame
        else:
            correlation = str(uuid4())
            request: dict[str, object] = {
                "version": 1,
                "id": correlation,
                "boot": self.boot,
                "capability": self.capability,
                "generation": self.generation,
                "epoch": self.epoch,
                "op": op,
            }
            if authority is not None:
                if (authority.generation, authority.epoch) != (self.generation, self.epoch):
                    raise RuntimeUnavailable("Runtime authority mismatch")
                request["deadline_ns"] = authority.deadline_ns
            if op in {"task_receive", "settings", "settings_status"}:
                request["payload"] = payload
                if len(json.dumps(request, separators=(",", ":")).encode()) + 1 > MAX_FRAME:
                    raise RuntimeUnavailable("Runtime receive limit")
            timeout = 2.0
            if op in MANAGED_OPERATIONS and authority is not None:
                request["payload"] = payload
                remaining = (authority.deadline_ns - time.monotonic_ns()) / 1_000_000_000
                if remaining <= 0:
                    raise RuntimeUnavailable("Expired runtime authority")
                timeout = min(3.2, remaining)
                if len(json.dumps(request, separators=(",", ":")).encode()) + 1 > MAX_FRAME:
                    raise RuntimeUnavailable("Runtime managed-task limit")
            if op == "prepare" and authority is not None:
                from omnis.modules.runs.native_preparation_models import (
                    LIMITS,
                    validate_bundle,
                )

                if payload is None or set(payload) != {"bundle_ref", "bundle"}:
                    raise RuntimeUnavailable("Runtime payload denied")
                validate_bundle(payload["bundle_ref"], payload["bundle"])
                request["payload"] = payload
                remaining = (authority.deadline_ns - time.monotonic_ns()) / 1_000_000_000
                if remaining <= 0:
                    raise RuntimeUnavailable("Expired runtime authority")
                # Explicit preparation-only budget; ordinary exchanges and launch unchanged.
                timeout = min(3.2, remaining)
                if (
                    len(json.dumps(request, separators=(",", ":")).encode()) + 1
                    > LIMITS["max_runtime_request_bytes"]
                ):
                    raise RuntimeUnavailable("Runtime preparation limit")
            if op == "launch" and authority is not None:
                remaining = (authority.deadline_ns - time.monotonic_ns()) / 1_000_000_000
                if remaining <= 0:
                    raise RuntimeUnavailable("Expired runtime authority")
                timeout = min(6.0, remaining + 1.0)  # Bounded refusal/drain after grant expiry.
            frame = json.dumps(request, separators=(",", ":")).encode() + b"\n"
        try:
            async with asyncio.timeout(timeout):
                self.writer.write(frame)
                await self.writer.drain()
                response = _object(await self.reader.readuntil(b"\n"))
                if response.get("id") != correlation or response.get("boot") != self.boot:
                    raise RuntimeUnavailable("Runtime correlation mismatch")
                if response.get("ok") is not True:
                    raise RuntimeUnavailable("Runtime refused")
                state = response.get("state")
                if not isinstance(state, str) or state not in {
                    "IDLE",
                    "STARTING",
                    "MANAGEMENT",
                    "READY",
                    "STOPPING",
                    "STOPPED",
                    "UNCERTAIN",
                }:
                    raise RuntimeUnavailable("Invalid runtime state")
                if (
                    response.get("assessment_ready") is not False
                    or type(response.get("drained")) is not bool
                ):
                    raise RuntimeUnavailable("Invalid runtime readiness")
                for key in ("generation", "epoch"):
                    if type(response.get(key)) is not int:
                        raise RuntimeUnavailable("Invalid runtime fence")
                if state == "IDLE":
                    if (response["generation"], response["epoch"]) != (0, 0):
                        raise RuntimeUnavailable("Invalid idle runtime")
                elif (response["generation"], response["epoch"]) != (
                    self.generation,
                    self.epoch,
                ):
                    raise RuntimeUnavailable("Runtime stale fence")
                if response["drained"] != (state in {"IDLE", "STOPPED"}):
                    raise RuntimeUnavailable("Invalid runtime drain")
                if "bootstrap_inventory" not in response:
                    raise RuntimeUnavailable("Missing bootstrap inventory")
                inventory = response["bootstrap_inventory"]
                if inventory is None:
                    if state == "READY" or (
                        state == "STOPPED" and self.bootstrap_inventory is not None
                    ):
                        raise RuntimeUnavailable("Missing ready bootstrap inventory")
                else:
                    if state == "IDLE":
                        raise RuntimeUnavailable("Inventory before native ready")
                    validated = validate_bootstrap_inventory(inventory)
                    if (
                        self.bootstrap_inventory is not None
                        and validated != self.bootstrap_inventory
                    ):
                        raise RuntimeUnavailable("Changed bootstrap inventory")
                    self.bootstrap_inventory = validated
                    response["bootstrap_inventory"] = validated
                if op == "prepare":
                    from omnis.modules.runs.native_preparation_models import validate_worker

                    if (
                        state != "READY"
                        or payload is None
                        or authority is None
                        or time.monotonic_ns() >= authority.deadline_ns
                    ):
                        raise RuntimeUnavailable("Runtime preparation fence")
                    response["preparation"] = validate_worker(
                        response.get("preparation"), payload["bundle_ref"], payload["bundle"]
                    )
                if op in MANAGED_OPERATIONS:
                    if (
                        state != "READY"
                        or authority is None
                        or time.monotonic_ns() >= authority.deadline_ns
                        or not isinstance(response.get("managed"), dict)
                    ):
                        raise RuntimeUnavailable("Runtime managed-task fence")
                return response
        except (
            OSError,
            ValueError,
            TimeoutError,
            asyncio.IncompleteReadError,
            asyncio.LimitOverrunError,
        ):
            if _frozen is not None:
                self.retire_frozen()
            else:
                await self.close()
            raise RuntimeUnavailable("Runtime exchange unavailable") from None

    async def prepare(
        self,
        service: "InstanceService",
        supervisor_owner: UUID,
        bundle_ref: dict[str, object],
        bundle: dict[str, object],
    ) -> dict[str, object]:
        from omnis.modules.runs.native_preparation_models import validate_bundle

        checked = validate_bundle(bundle_ref, bundle)
        try:
            authority = await service.runtime_authority(
                supervisor_owner, self.epoch, self.generation, inert_probe=True
            )
            return await self._exchange(
                "prepare", authority, {"bundle_ref": bundle_ref, "bundle": checked}
            )
        except BaseException:
            await self.close()
            raise

    async def managed(
        self,
        service: "InstanceService",
        owner: UUID,
        operation: str,
        payload: dict[str, object],
    ) -> dict[str, object]:
        """Finite private operations; domain/native owners validate the inner contracts.

        No reconnect, retry or child creation on channel loss. The caller retains
        its durable intention and reconciles rather than resending a prompt.
        """
        if operation not in MANAGED_OPERATIONS:
            raise RuntimeUnavailable("Runtime operation denied")
        checked = _object(json.dumps(payload, allow_nan=False).encode())
        if checked.get("protocol") not in (
            "omnis-managed-admission-v1",
            "omnis-managed-admission-v2",
            "omnis-managed-admission-v3",
            "omnis-managed-admission-v4",
            "omnis-managed-admission-v5",
        ):
            raise RuntimeUnavailable("Runtime payload denied")
        try:
            authority = await service.runtime_authority(
                owner, self.epoch, self.generation, inert_probe=True
            )
            response = await self._exchange(operation, authority, checked)
            result = response["managed"]
            if not isinstance(result, dict):
                raise RuntimeUnavailable("Invalid managed response")
            return {key: value for key, value in result.items()}
        except BaseException:
            await self.close()
            raise

    async def receive(self, payload: dict[str, object], *, expected_boot: str) -> dict[str, object]:
        """Explicit recovery by this owner, never reconnect-and-resend work.

        Only the original Host boot/fence may return a retained terminal result.
        Missing retention/replaced Host is indeterminate, not permission to retry.
        """
        async with self.recovery_lock:
            try:
                if self.boot != expected_boot:
                    raise RuntimeUnavailable("Historical runtime identity mismatch")
                if self.writer is None:
                    try:
                        await self.connect()
                    except (OSError, ValueError):
                        raise RuntimeUnavailable("Runtime recovery unavailable") from None
                if self.boot != expected_boot:
                    raise RuntimeUnavailable("Replaced runtime host")
                response = await self._exchange("task_receive", payload=payload)
                result = response.get("managed")
                if not isinstance(result, dict):
                    raise RuntimeUnavailable("Missing retained managed result")
                return result
            except BaseException:
                await self.close()
                raise

    async def settings(
        self, service: "InstanceService", owner: UUID, payload: dict[str, object]
    ) -> dict[str, object]:
        from omnis.modules.settings.provider_models import ProviderCommand, ProviderView

        command = ProviderCommand.model_validate(payload)
        stop_serial = self._stop_serial
        from omnis.modules.instance.domain import ControlCode, ControlConflict

        try:
            authority = await service.runtime_authority(
                owner, self.epoch, self.generation, management=True
            )
        except ControlConflict as exc:
            if exc.code != ControlCode.GENERATION_CONFLICT or not self._initial_management_bind:
                raise
            current = await service.owned_status(owner, self.epoch)
            if (
                not current.admission_open
                or current.shutdown_command_id is not None
                or current.generation != self.generation + 1
            ):
                raise RuntimeUnavailable("Initial OPEN generation required") from None
            authority = await service.runtime_authority(
                owner, self.epoch, current.generation, management=True
            )
        try:
            response = await self._exchange(
                "settings",
                authority,
                command.model_dump(mode="json"),
                _settings_stop_serial=stop_serial,
            )
            result = ProviderView.model_validate(response.get("settings"))
            if result.operation_id != command.operation_id:
                raise RuntimeUnavailable("Settings correlation mismatch")
            return result.model_dump(mode="json")
        except BaseException:
            await self.close()
            raise

    async def settings_status(self, operation_id: str) -> dict[str, object]:
        from omnis.modules.settings.provider_models import ProviderView

        try:
            response = await self._exchange(
                "settings_status", payload={"operation_id": operation_id}
            )
            result = ProviderView.model_validate(response.get("settings"))
            if (
                result.operation_id != operation_id
                and operation_id != "00000000-0000-0000-0000-000000000000"
            ):
                raise RuntimeUnavailable("Settings correlation mismatch")
            return result.model_dump(mode="json")
        except BaseException:
            await self.close()
            raise

    async def status(self) -> dict[str, object]:
        return await self._exchange("status")

    async def launch_inert(self, service: "InstanceService", owner: UUID) -> dict[str, object]:
        authority = await service.runtime_authority(
            owner, self.epoch, self.generation, inert_probe=True
        )
        return await self._exchange("launch", authority)

    async def renew(
        self, service: "InstanceService", owner: UUID, *, management: bool = False
    ) -> dict[str, object]:
        try:
            if management:
                authority = await service.runtime_authority(
                    owner, self.epoch, self.generation, management=True
                )
            else:
                authority = await service.runtime_authority(
                    owner, self.epoch, self.generation, inert_probe=True
                )
            return await self._exchange("renew", authority)
        except BaseException:
            await self.close()
            raise

    async def drain(self) -> bool:
        try:
            status = await self._exchange("stop")
            observed = await self.status()  # Exact target readback, not just ACK.
            return status["drained"] is True and observed["drained"] is True
        except (OSError, ValueError, TimeoutError):
            return False

    async def close(self) -> None:
        self._initial_management_bind = False
        writer, self.writer = self.writer, None
        self.reader = None
        if writer is not None:
            writer.close()
            with suppress(OSError, TimeoutError):
                await asyncio.wait_for(writer.wait_closed(), 0.5)
