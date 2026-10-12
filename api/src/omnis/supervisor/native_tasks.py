"""Existing supervisor owns native stage/commit/release; no second RPC client."""

import argparse
import asyncio
import os
import socket
import struct
import sys
from contextlib import suppress
from pathlib import Path
from typing import NoReturn
from uuid import UUID

from sqlalchemy import text as sql
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncConnection

from omnis.modules.instance.domain import ControlConflict
from omnis.modules.instance.schemas import NativeTaskCommand
from omnis.modules.instance.service import InstanceService
from omnis.modules.runs.managed_admission import ManagedAdmission
from omnis.modules.settings import candidate_store as records
from omnis.modules.settings.candidate_catalog import uuid_string
from omnis.modules.settings.catalog_models import CatalogError
from omnis.modules.settings.catalog_schema import canonical, load_json
from omnis.modules.tasks.managed_contract import PROTOCOL, manifest_protocol, mapping, ref
from omnis.supervisor.runtime_client import RuntimeClient, RuntimeUnavailable

# Request/capability framing remains 4 KiB. Qualified model context can be
# 32 KiB internally; reserve bounded server-encoding/envelope overhead in reply.
NATIVE_TASK_REPLY_MAX_BYTES = 65536


class NativeTaskOwner:
    def __init__(
        self,
        domain: ManagedAdmission,
        service: InstanceService,
        owner: UUID,
        epoch: int,
        runtime: RuntimeClient,
    ) -> None:
        self.domain, self.service, self.owner = domain, service, owner
        self.epoch, self.runtime = epoch, runtime

    async def _instance(self, connection: AsyncConnection, command: NativeTaskCommand) -> None:
        actual = (
            await connection.execute(sql("SELECT instance_id FROM instance_control WHERE id=1"))
        ).scalar_one()
        if str(actual) != command.instance_id or command.expected_epoch != self.epoch:
            raise CatalogError("TASK_REJECTED")

    def _reply(
        self, command: NativeTaskCommand, binding: dict[str, object], status: str
    ) -> dict[str, object]:
        return {
            "ok": True,
            "manifest_ref": command.manifest_ref,
            "binding_ref": records.reference(binding),
            "task_status": status,
        }

    async def _model_preflight(
        self, command: NativeTaskCommand, binding: dict[str, object]
    ) -> dict[str, object]:
        from omnis.modules.runs.model_dispatch import ModelDispatch

        if mapping(binding["payload"])["runtime_boot"] != self.runtime.boot:
            raise CatalogError("TASK_INDETERMINATE")
        consumer = ModelDispatch(self.domain)
        async with self.service.native_preparation_commit(
            self.owner, self.epoch, command.expected_generation
        ) as conn:
            await self._instance(conn, command)
            prepared = await consumer.prepare(
                conn,
                command.owner_id,
                command.manifest_ref,
                records.reference(binding),
                command.data_approval,
            )
        # Persistent decision/projection commit precedes IPC. A cold identity
        # never becomes a native-turn or an allocation by completing this call.
        result = await self.runtime.managed(
            self.service, self.owner, "task_model_preflight", mapping(prepared["payload"])
        )
        async with self.service.native_preparation_commit(
            self.owner, self.epoch, command.expected_generation
        ) as conn:
            await self._instance(conn, command)
            admission = await consumer.persist_configuration(
                conn, command.owner_id, prepared, result
            )
        return {
            **self._reply(command, binding, "BLOCKED"),
            "model_admission": admission,
        }

    async def handle(self, command: NativeTaskCommand) -> dict[str, object]:
        command = NativeTaskCommand.model_validate(command.model_dump(mode="json"))
        async with asyncio.timeout(4):
            try:
                return await self._handle(command)
            except RuntimeUnavailable:
                raise CatalogError("TASK_INDETERMINATE") from None

    async def _model_configuration(self, command: NativeTaskCommand) -> dict[str, object]:
        from omnis.modules.runs.model_dispatch import ModelDispatch

        consumer = ModelDispatch(self.domain)
        authority: dict[str, object] = {
            "instance_id": command.instance_id,
            "owner": str(self.owner),
            "epoch": self.epoch,
            "generation": command.expected_generation,
        }
        async with self.service.native_preparation_commit(
            self.owner, self.epoch, command.expected_generation
        ) as conn:
            await self._instance(conn, command)
            item = await consumer.prepare_ready_configuration(
                conn, command.owner_id, command.manifest_ref, command.configuration, authority
            )
        # The first consumer reads committed owned source; all execution grants HOLD.
        async with self.service.native_preparation_commit(
            self.owner, self.epoch, command.expected_generation
        ) as conn:
            await self._instance(conn, command)
            data = await consumer.read_ready_initialization(
                conn, command.owner_id, command.manifest_ref, records.reference(item), authority
            )
        return {
            "ok": True,
            "manifest_ref": command.manifest_ref,
            "provider_config_ref": records.reference(item),
            "configuration_status": "READY",
            "initialization_status": "HOLD",
            "inference_status": "HOLD",
            "initialization_data": data.decode(),
        }

    async def _model_initialization(self, command: NativeTaskCommand) -> dict[str, object]:
        from omnis.modules.runs.model_dispatch import ModelDispatch

        consumer = ModelDispatch(self.domain)
        authority: dict[str, object] = {
            "instance_id": command.instance_id,
            "owner": str(self.owner),
            "epoch": self.epoch,
            "generation": command.expected_generation,
        }
        async with self.service.native_preparation_commit(
            self.owner, self.epoch, command.expected_generation
        ) as conn:
            await self._instance(conn, command)
            payload, observation = await consumer.prepare_initialization(
                conn,
                command.owner_id,
                command.manifest_ref,
                command.provider_config_ref,
                command.initialization_id,
                authority,
                self.runtime.boot,
            )
        if payload["runtime_boot"] != self.runtime.boot:
            raise CatalogError("TASK_INDETERMINATE")
        if observation is None:
            # Committed intent precedes IPC. Pending replay is STATUS, never CREATE.
            result = await self.runtime.managed(
                self.service, self.owner, "task_model_initialize", payload
            )
            async with self.service.native_preparation_commit(
                self.owner, self.epoch, command.expected_generation
            ) as conn:
                await self._instance(conn, command)
                if payload["runtime_boot"] != self.runtime.boot:
                    raise CatalogError("TASK_INDETERMINATE")
                observation = await consumer.persist_initialization(
                    conn, command.owner_id, payload, result
                )
                if payload["runtime_boot"] != self.runtime.boot:
                    raise CatalogError("TASK_INDETERMINATE")
        return {
            "ok": True,
            "manifest_ref": command.manifest_ref,
            "provider_config_ref": command.provider_config_ref,
            "initialization_ref": records.reference(observation),
            "initialization_status": "CONFIG_INITIALIZED_AT_PRE_CLIENT_SEAM",
            "inference_status": "HOLD",
            "initialization_observation": observation,
        }

    async def _handle(self, command: NativeTaskCommand) -> dict[str, object]:
        # Lifecycle command ID is the original prepare ID, never an unused nonce.
        back = await self.domain.readback(
            {"schema_version": 1, "owner_id": command.owner_id, "command_id": command.command_id}
        )
        if canonical(back["manifest_ref"]) != canonical(command.manifest_ref):
            raise CatalogError("COMMAND_CONFLICT")
        if command.action in {"model_configuration", "model_initialization"}:
            if (
                back["binding"] is not None
                or back["stage_started"]
                or back["release_started"]
                or back["results"]
            ):
                raise CatalogError("MODEL_CONFIGURATION_REJECTED")
            if command.action == "model_initialization":
                return await self._model_initialization(command)
            return await self._model_configuration(command)
        protocol = manifest_protocol(back["manifest"])
        binding = None if back["binding"] is None else mapping(back["binding"])
        if binding is not None:
            authority = mapping(mapping(binding["payload"])["authority"])
            if any(
                authority[key] != expected
                for key, expected in (
                    ("instance_id", command.instance_id),
                    ("epoch", command.expected_epoch),
                    ("generation", command.expected_generation),
                )
            ):
                raise CatalogError("COMMAND_CONFLICT")
            if command.action == "model_preflight":
                if back["results"] or back["release_started"]:
                    raise CatalogError("TASK_REJECTED")
                return await self._model_preflight(command, binding)
            if back["results"]:
                checked = await self.domain.check(command.owner_id, command.command_id)
                return self._reply(command, binding, str(checked["status"]))
        if command.action == "stage":
            if binding is not None:
                return self._reply(command, binding, "BOUND")
            if back["stage_started"]:
                raise CatalogError("TASK_INDETERMINATE")
            async with self.service.native_preparation_commit(
                self.owner, self.epoch, command.expected_generation
            ) as conn:
                await self._instance(conn, command)
                # Validate the complete immutable material before uncertain dispatch.
                composed_payload = (
                    await self.domain.stage_payload(conn, command.owner_id, command.manifest_ref)
                    if protocol != PROTOCOL
                    else None
                )
                manifest = await self.domain.reserve_dispatch(
                    conn, command.owner_id, command.manifest_ref, "stage"
                )
            staged = await self.runtime.managed(
                self.service,
                self.owner,
                "task_stage",
                composed_payload or {"protocol": protocol, "manifest": manifest},
            )
            async with self.service.native_preparation_commit(
                self.owner, self.epoch, command.expected_generation
            ) as conn:
                await self._instance(conn, command)
                binding = await self.domain.commit_binding(
                    conn,
                    command.owner_id,
                    command.manifest_ref,
                    staged,
                    self.runtime.boot,
                    {
                        "instance_id": command.instance_id,
                        "owner": str(self.owner),
                        "epoch": self.epoch,
                        "generation": command.expected_generation,
                    },
                )
            return self._reply(command, binding, "BOUND")
        if binding is None:
            raise CatalogError("TASK_REJECTED")
        body = mapping(binding["payload"])
        if body["runtime_boot"] != self.runtime.boot:
            raise CatalogError("TASK_INDETERMINATE")
        payload = {
            "protocol": protocol,
            "ticket": body["ticket"],
            "manifest_ref": command.manifest_ref,
        }
        if command.action == "release":
            if back["release_started"]:
                raise CatalogError("TASK_INDETERMINATE")
            async with self.service.native_preparation_commit(
                self.owner, self.epoch, command.expected_generation
            ) as conn:
                await self._instance(conn, command)
                await self.domain.reserve_dispatch(
                    conn, command.owner_id, command.manifest_ref, "release"
                )
            if protocol == "omnis-managed-admission-v4":
                # Entire finite PURE method is one dispatch under the existing
                # InstanceControl/lease barrier. Stop waits; no warm/target work.
                # Obtain the existing short grant before entering its row locks
                # to avoid a second connection deadlocking against this owner.
                grant = await self.service.runtime_authority(
                    self.owner, self.epoch, command.expected_generation, inert_probe=True
                )
                async with self.service.native_preparation_commit(
                    self.owner, self.epoch, command.expected_generation
                ) as conn:
                    await self._instance(conn, command)
                    try:
                        response = await self.runtime._exchange(
                            "task_release", grant, {**payload, "binding": binding}
                        )
                    except BaseException:
                        # Match managed()'s interrupted-channel retirement while
                        # retaining the preobtained grant and committed intent.
                        await self.runtime.close()
                        raise
                    final = mapping(response["managed"])
            else:
                final = await self.runtime.managed(
                    self.service, self.owner, "task_release", {**payload, "binding": binding}
                )
        else:
            if not back["release_started"]:
                raise CatalogError("TASK_INDETERMINATE")
            final = await self.runtime.managed(self.service, self.owner, "task_status", payload)
        # A genuine already-produced result is received without granting new work.
        await self.domain.ingest_result(
            command.owner_id,
            command.manifest_ref,
            final,
            self.runtime.boot,
            body["authority"],
            held=False,
        )
        checked = await self.domain.check(command.owner_id, command.command_id)
        return self._reply(command, binding, str(checked["status"]))


async def control_task(directory: Path, value: object) -> dict[str, object]:
    from omnis.modules.runs.native_preparation import existing_private_root
    from omnis.transport.control_probe import _read_capability

    command = NativeTaskCommand.model_validate(value)
    existing_private_root(directory)
    capability = _read_capability(directory)
    async with asyncio.timeout(4):
        reader, writer = await asyncio.open_unix_connection(
            directory / "control.sock", limit=NATIVE_TASK_REPLY_MAX_BYTES
        )
        try:
            peer = writer.get_extra_info("socket").getsockopt(
                socket.SOL_SOCKET, socket.SO_PEERCRED, 12
            )
            if struct.unpack("3i", peer)[1] != os.getuid():
                raise CatalogError("TASK_UNAVAILABLE")
            frame = (
                canonical(
                    {
                        "version": 1,
                        "capability": capability,
                        "command": command.model_dump(mode="json"),
                    }
                )
                + b"\n"
            )
            if len(frame) > 4096:
                raise CatalogError("INVALID_REQUEST")
            writer.write(frame)
            await writer.drain()
            try:
                raw_reply = await reader.readuntil(b"\n")
            except (asyncio.LimitOverrunError, asyncio.IncompleteReadError):
                raise CatalogError("TASK_REJECTED") from None
            if len(raw_reply) > NATIVE_TASK_REPLY_MAX_BYTES:
                raise CatalogError("TASK_REJECTED")
            reply = mapping(load_json(raw_reply))
            uuid_string(reply.get("correlation_id"))
            if reply.get("ok") is not True:
                reason = reply.get("error")
                allowed = {
                    "TASK_UNAVAILABLE",
                    "TASK_REJECTED",
                    "TASK_INDETERMINATE",
                    "COMMAND_CONFLICT",
                    "CONTROL_TIMEOUT",
                    "CONTROL_UNAVAILABLE",
                    "LEASE_LOST",
                }
                raise CatalogError(
                    reason if type(reason) is str and reason in allowed else "TASK_UNAVAILABLE"
                )
            if command.action == "model_initialization":
                from hashlib import sha256

                from omnis.modules.runs.native_preparation_models import sha
                from omnis.modules.tasks.managed_contract import exact, integer, record, text
                from omnis.policy.ready_model_configuration import FIELDS, validate_ready_source

                exact(
                    reply,
                    {
                        "ok",
                        "correlation_id",
                        "manifest_ref",
                        "provider_config_ref",
                        "initialization_ref",
                        "initialization_status",
                        "inference_status",
                        "initialization_observation",
                    },
                )
                observation = record(
                    reply["initialization_observation"], "native-initialization-observation"
                )
                body = exact(
                    observation["payload"],
                    {
                        "protocol",
                        "version",
                        "initialization_id",
                        "intent_ref",
                        "owner_id",
                        "run_id",
                        "manifest_ref",
                        "runtime_boot",
                        "authority",
                        "source_byte_digest",
                        "initialization_data_digest",
                        "provider_config_ref",
                        "producer_receipt_ref",
                        "client_status",
                        "native_turn",
                        "inference_status",
                        "model_calls",
                        "status",
                        "native_session_id",
                        "native_instance_id",
                        "observed_configuration",
                        "observed_configuration_digest",
                    },
                )
                authority = exact(
                    body["authority"], {"instance_id", "owner", "epoch", "generation"}
                )
                uuid_string(authority["owner"])
                integer(authority["epoch"], 1)
                integer(authority["generation"], 0)
                for key in (
                    "initialization_id",
                    "owner_id",
                    "run_id",
                    "runtime_boot",
                    "native_instance_id",
                ):
                    uuid_string(body[key])
                text(body["native_session_id"], 128)
                integer(body["version"], 1, 1)
                integer(body["model_calls"], 0, 0)
                for key, kind in (
                    ("intent_ref", "native-initialization-intent"),
                    ("manifest_ref", "launch-manifest"),
                    ("provider_config_ref", "provider-config"),
                    ("producer_receipt_ref", "contract-input-command"),
                ):
                    ref(body[key], kind)
                for key in (
                    "source_byte_digest",
                    "initialization_data_digest",
                    "observed_configuration_digest",
                ):
                    sha(body[key])
                config = exact(body["observed_configuration"], FIELDS - {"version", "decision_id"})
                validate_ready_source(
                    {**config, "version": 1, "decision_id": body["initialization_id"]}
                )
                if (
                    ref(reply["manifest_ref"], "launch-manifest") != command.manifest_ref
                    or ref(reply["provider_config_ref"], "provider-config")
                    != command.provider_config_ref
                    or ref(reply["initialization_ref"], "native-initialization-observation")
                    != records.reference(observation)
                    or body["manifest_ref"] != command.manifest_ref
                    or body["provider_config_ref"] != command.provider_config_ref
                    or body["initialization_id"] != command.initialization_id
                    or body["owner_id"] != command.owner_id
                    or authority["instance_id"] != command.instance_id
                    or authority["epoch"] != command.expected_epoch
                    or authority["generation"] != command.expected_generation
                    or body["protocol"] != "omnis-managed-admission-v3"
                    or reply["initialization_status"] != "CONFIG_INITIALIZED_AT_PRE_CLIENT_SEAM"
                    or body["status"] != reply["initialization_status"]
                    or reply["inference_status"] != "HOLD"
                    or body["inference_status"] != "HOLD"
                    or body["client_status"] != "DEFERRED_NO_CREDENTIAL"
                    or body["native_turn"] is not None
                    or sha256(canonical(config)).hexdigest()
                    != body["observed_configuration_digest"]
                    or body["initialization_data_digest"] != body["observed_configuration_digest"]
                ):
                    raise CatalogError("TASK_REJECTED")
                return reply
            if command.action == "model_configuration":
                from omnis.modules.tasks.managed_contract import exact
                from omnis.policy.ready_model_configuration import initialization_data

                exact(
                    reply,
                    {
                        "ok",
                        "correlation_id",
                        "manifest_ref",
                        "provider_config_ref",
                        "configuration_status",
                        "initialization_status",
                        "inference_status",
                        "initialization_data",
                    },
                )
                if (
                    ref(reply["manifest_ref"], "launch-manifest") != command.manifest_ref
                    or reply["configuration_status"] != "READY"
                    or reply["initialization_status"] != "HOLD"
                    or reply["inference_status"] != "HOLD"
                    or type(reply["initialization_data"]) is not str
                    or reply["initialization_data"].encode()
                    != initialization_data(command.configuration)
                ):
                    raise CatalogError("TASK_REJECTED")
                ref(reply["provider_config_ref"], "provider-config")
                return reply
            fields = {"ok", "correlation_id", "manifest_ref", "binding_ref", "task_status"}
            if command.action == "model_preflight":
                fields.add("model_admission")
            if set(reply) != fields:
                raise CatalogError("TASK_REJECTED")
            if ref(reply["manifest_ref"], "launch-manifest") != command.manifest_ref:
                raise CatalogError("TASK_REJECTED")
            ref(reply["binding_ref"], "runtime-binding")
            if reply["task_status"] not in {"BOUND", "BLOCKED"}:
                raise CatalogError("TASK_REJECTED")
            if command.action == "model_preflight":
                from omnis.modules.runs.native_preparation_models import sha
                from omnis.modules.tasks.managed_contract import exact

                admission = exact(
                    reply["model_admission"],
                    {
                        "protocol",
                        "status",
                        "reason",
                        "manifest_ref",
                        "binding_ref",
                        "projection_ref",
                        "projection_digest",
                        "native_turn",
                        "model_calls",
                        "data_approval_ref",
                        "model_context",
                        "model_context_digest",
                        "source_configuration",
                        "configuration_receipt_ref",
                    },
                )
                ref(admission["projection_ref"], "model-projection")
                ref(admission["data_approval_ref"], "model-data-approval")
                manifest_pin = ref(admission["manifest_ref"], "launch-manifest")
                binding_pin = ref(admission["binding_ref"], "runtime-binding")
                sha(admission["projection_digest"])
                from hashlib import sha256

                from omnis.policy.model_context import validate_context_readback

                context = validate_context_readback(admission["model_context"])

                # Identity/pins of the observation are checked against the exact
                # owner context; this receipt is never a provider-config grant.
                ref(admission["configuration_receipt_ref"], "model-configuration-receipt")
                source = mapping(admission["source_configuration"])
                from omnis.modules.tasks.managed_contract import integer, text
                from omnis.policy.model_configuration import SOURCE_FIELDS

                exact(source, SOURCE_FIELDS)
                integer(source["version"], 1, 1)
                if (
                    source["source"] != "NATIVE_COLD_INITIALIZER"
                    or source["mode"] != "NO_MODEL"
                    or source["provider"] is not None
                    or source["model_id"] is not None
                ):
                    raise CatalogError("TASK_REJECTED")
                for key in ("native_child_id", "native_session_id", "native_parent_session_id"):
                    text(source[key], 128)
                if (
                    context["owner_id"] != command.owner_id
                    or context["manifest_ref"] != manifest_pin
                    or context["binding_ref"] != binding_pin
                    or context["projection_ref"] != admission["projection_ref"]
                    or sha256(canonical(context)).hexdigest()
                    != sha(admission["model_context_digest"])
                ):
                    raise CatalogError("TASK_REJECTED")
                if (
                    reply["task_status"] != "BLOCKED"
                    or type(admission["protocol"]) is not str
                    or admission["protocol"]
                    not in ("omnis-managed-admission-v2", "omnis-managed-admission-v3")
                    or admission["status"] != "BLOCKED"
                    or admission["reason"] != "NO_MODEL"
                    or admission["native_turn"] is not None
                    or type(admission["model_calls"]) is not int
                    or admission["model_calls"] != 0
                    or canonical(manifest_pin) != canonical(reply["manifest_ref"])
                    or canonical(binding_pin) != canonical(reply["binding_ref"])
                ):
                    raise CatalogError("TASK_REJECTED")
            return reply
        finally:
            writer.close()
            with suppress(OSError, TimeoutError):
                await asyncio.wait_for(writer.wait_closed(), 0.2)


def main(argv: list[str] | None = None) -> int:
    class Parser(argparse.ArgumentParser):
        def error(self, message: str) -> NoReturn:
            raise CatalogError("INVALID_ARGUMENTS")

    parser = Parser()
    parser.add_argument("--request", required=True)
    parser.add_argument("--control-dir", required=True)
    try:
        args = parser.parse_args(argv)
        from omnis.modules.settings.skill_catalog import read_file

        result = asyncio.run(
            control_task(Path(args.control_dir), load_json(read_file(Path(args.request), 4096)))
        )
        print(canonical(result).decode())
        return 0
    except CatalogError as error:
        reason = error.reason
    except (SQLAlchemyError, ControlConflict, TimeoutError):
        reason = "TASK_UNAVAILABLE"
    except (
        OSError,
        ValueError,
        TypeError,
        KeyError,
        RecursionError,
        asyncio.IncompleteReadError,
        asyncio.LimitOverrunError,
    ):
        reason = "TASK_REJECTED"
    print(canonical({"status": "BLOCKED", "reason": reason}).decode(), file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
