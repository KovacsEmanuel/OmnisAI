"""One durable synthetic test per instance; the existing supervisor owns its task."""

import asyncio
import time
from datetime import UTC, datetime
from hashlib import sha256
from typing import TYPE_CHECKING
from uuid import UUID, uuid4, uuid5

from sqlalchemy import text as sql
from sqlalchemy.ext.asyncio import AsyncConnection

from omnis.modules.instance.schemas import NativeTaskCommand
from omnis.modules.runs.model_test import REQUESTED, ModelTest
from omnis.modules.runs.model_test_models import ModelTestControl, ModelTestView
from omnis.modules.runs.model_test_runtime import ApiKeyModelTest as ApiKeyModelTest
from omnis.modules.settings import candidate_store as records
from omnis.modules.settings.catalog_models import CatalogError
from omnis.modules.tasks import managed_store
from omnis.modules.tasks.managed_contract import mapping

if TYPE_CHECKING:
    from omnis.supervisor.native_tasks import NativeTaskOwner

SYSTEM = "Respond briefly to this synthetic model test. Use no tools."
OBJECTIVE = "Map supplied structured synthetic records."


def key(owner: str, tag: str) -> str:
    return str(uuid5(UUID(owner), "omnis-fixed-model-test-v1:" + tag))


async def load(connection: AsyncConnection, owner: str, tag: str) -> dict[str, object] | None:
    value = (
        await connection.execute(
            sql("SELECT result FROM catalog_command WHERE owner_id=:owner AND command_id=:id"),
            {"owner": owner, "id": key(owner, tag)},
        )
    ).scalar_one_or_none()
    if value is None:
        return None
    _, item = await records.get(connection, owner, mapping(mapping(value)["ref"]))
    if item["kind"] != "model-test-" + tag:
        raise CatalogError("STORAGE_INCOMPATIBLE")
    return item


async def save(
    connection: AsyncConnection, owner: str, tag: str, payload: dict[str, object]
) -> dict[str, object]:
    item = records.envelope("model-test-" + tag, payload)
    await records.put(connection, owner, key(owner, tag), item)
    await records.complete(
        connection,
        owner,
        key(owner, tag),
        "fixed-model-test-" + tag,
        payload,
        {"ref": records.reference(item)},
    )
    return item


def native_commands(payload: dict[str, object]) -> NativeTaskCommand:
    return NativeTaskCommand.model_validate(payload["start_command"])


def send_command(payload: dict[str, object], composition: object) -> NativeTaskCommand:
    start = native_commands(payload)
    return NativeTaskCommand.model_validate(
        {
            **start.model_dump(mode="json", exclude={"settings_operation_id"}),
            "action": "model_test_send",
            "protocol_id": payload["protocol_id"],
            "data_approval": {
                "decision_id": payload["decision_id"],
                "composition_ref": composition,
                "approved_text_digests": payload["approved_text_digests"],
            },
        }
    )


async def projection(
    owner: "NativeTaskOwner", connection: AsyncConnection, payload: dict[str, object]
) -> dict[str, object]:
    start = native_commands(payload)
    try:
        receipt = await managed_store.command_receipt(
            connection, start.owner_id, str(payload["protocol_id"])
        )
    except CatalogError as error:
        if error.reason == "REF_UNAVAILABLE":
            return {}
        raise
    command = mapping(receipt["payload"])
    if command["operation"] != "model_test_send" or command["owner_id"] != start.owner_id:
        raise CatalogError("COMMAND_CONFLICT")
    _, attempt = await managed_store.owned(
        connection, start.owner_id, mapping(command["result_refs"])["attempt_ref"]
    )
    accounting = await ModelTest(owner.domain).execution_receipt(
        connection, start.owner_id, attempt
    )
    pin = accounting["provider_receipt_ref"]
    if pin is None:
        return {}
    _, retained = await managed_store.owned(connection, start.owner_id, pin)
    observed = mapping(mapping(retained["payload"])["observed"])
    return {
        "response_text": observed["output_text"],
        "observed_model": observed["model"],
        "observed_effort": observed["effort"],
        **{k: observed[k] for k in ("input_tokens", "output_tokens", "reasoning_tokens")},
    }


async def view(
    owner: "NativeTaskOwner",
    identity: str,
) -> dict[str, object]:
    async with owner.domain.engine.begin() as connection:
        item = await load(connection, identity, "operation")
        fields: dict[str, object] = {
            "operation_id": None,
            "system_message": SYSTEM,
            "user_message": OBJECTIVE,
            "status": "AVAILABLE" if await load(connection, identity, "source") else "UNAVAILABLE",
            "reason": None,
        }
        if item is not None:
            payload = mapping(item["payload"])
            terminal = await load(connection, identity, "terminal")
            active = owner.model_test_task is not None and not owner.model_test_task.done()
            fields.update(
                operation_id=payload["operation_id"],
                status="PENDING" if active else "UNKNOWN",
                reason=None,
            )
            if terminal is not None:
                end = mapping(terminal["payload"])
                fields.update(
                    status=end["status"], reason=end["reason"], duration_ms=end["duration_ms"]
                )
            observed = await projection(owner, connection, payload)
            if observed:
                fields.update(observed, status="COMPLETE", reason=None)
        return ModelTestView.model_validate(fields).model_dump(mode="json")


async def handle(owner: "NativeTaskOwner", command: ModelTestControl) -> dict[str, object]:
    command = ModelTestControl.model_validate(command.model_dump(mode="python"))
    status = await owner.service.owned_status(owner.owner, owner.epoch)
    identity = str(status.instance_id)
    if command.action == "provision":
        from omnis.modules.runs.model_test_source import provision

        return await provision(owner, command, status)
    if command.action == "read":
        return await view(owner, identity)
    if owner.model_test_closing:
        raise CatalogError("TASK_UNAVAILABLE")
    async with owner.service.native_preparation_commit(
        owner.owner, owner.epoch, status.generation
    ) as connection:
        await records.lock(connection, "fixed-model-test:" + identity)
        prior = await load(connection, identity, "operation")
        if prior is not None:
            previous = mapping(prior["payload"])
            if previous["operation_id"] != command.operation_id:
                raise CatalogError("COMMAND_CONFLICT")
        else:
            source = await load(connection, identity, "source")
            if source is None:
                raise CatalogError("CATALOG_REQUIRED")
            bound = mapping(source["payload"])
            back = await owner.domain.readback(
                {
                    "schema_version": 1,
                    "owner_id": bound["owner_id"],
                    "command_id": bound["command_id"],
                }
            )
            if (
                back["manifest_ref"] != bound["manifest_ref"]
                or back["binding"] is not None
                or back["stage_started"]
                or back["release_started"]
                or back["results"]
            ):
                raise CatalogError("MODEL_TEST_REJECTED")
            # Status-only read: never connect/authenticate or adopt a personal grant here.
            settings = await owner.runtime.settings_status("00000000-0000-0000-0000-000000000000")
            if (
                settings.get("status") != "CONFIRMED"
                or settings.get("selection") != REQUESTED
                or settings.get("authenticated") != "LOCAL_PRESENT"
            ):
                raise CatalogError("MODEL_TEST_SETTINGS_REQUIRED")
            start = NativeTaskCommand.model_validate(
                {
                    "op": "native_task",
                    "schema_version": 1,
                    "owner_id": bound["owner_id"],
                    "command_id": bound["command_id"],
                    "manifest_ref": bound["manifest_ref"],
                    "instance_id": identity,
                    "expected_generation": status.generation,
                    "expected_epoch": owner.epoch,
                    "action": "model_test_start",
                    "initialization_id": str(uuid4()),
                    "settings_operation_id": settings["operation_id"],
                }
            )
            payload: dict[str, object] = {
                "operation_id": command.operation_id,
                "start_command": start.model_dump(mode="json"),
                "protocol_id": str(uuid4()),
                "decision_id": str(uuid4()),
                "approved_text_digests": sorted(
                    sha256(t.encode()).hexdigest() for t in (SYSTEM, OBJECTIVE)
                ),
                "started_at": datetime.now(UTC).isoformat(),
            }
            # All browser-independent identities, authority and exact approved DATA are bound
            # before task creation; composition_ref is attached only to the real prepared turn.
            native_commands(payload)
            await save(connection, identity, "operation", payload)
    if prior is None and not owner.model_test_closing:
        owner.model_test_task = asyncio.create_task(run(owner, identity, payload))
    return await view(owner, identity)


async def run(owner: "NativeTaskOwner", identity: str, payload: dict[str, object]) -> None:
    began = time.monotonic()
    status, reason = "UNKNOWN", None
    try:
        async with asyncio.timeout(300):
            start = native_commands(payload)
            # Use the validated existing owner entry and its unchanged per-exchange limits.
            ready = await owner.handle(start)
            send = send_command(payload, ready["composition_ref"])
            while True:
                result = await owner.handle(send)
                if result["state"] == "SETTLED":
                    status = "COMPLETE"
                    break
                await asyncio.sleep(0.25)
    except asyncio.CancelledError:
        reason = "STOPPED_OR_OWNER_CLOSED"
        raise
    except Exception:
        # SENT may have reached the provider. Cancellation/timeout is not a refund or retry.
        reason = "RESULT_UNKNOWN"
    finally:
        async with asyncio.timeout(2), owner.domain.engine.begin() as connection:
            await records.lock(connection, "fixed-model-test:" + identity)
            if await load(connection, identity, "terminal") is None:
                await save(
                    connection,
                    identity,
                    "terminal",
                    {
                        "operation_id": payload["operation_id"],
                        "status": status,
                        "reason": reason,
                        "duration_ms": int((time.monotonic() - began) * 1000),
                    },
                )
