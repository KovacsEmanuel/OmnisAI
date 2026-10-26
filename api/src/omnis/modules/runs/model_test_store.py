"""V2 only. Ref resolution includes stable namespace, producer kind and exact retained bytes."""

import json
from hashlib import sha256
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from omnis.modules.runs.model_test_contract import (
    Capabilities,
    Dispatch,
    EntryCapabilities,
    EntrySnapshot,
    Operation,
    Ref,
    Snapshot,
)
from omnis.modules.settings.provider_vault import canonical


class ModelConflict(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def digest(value: object) -> str:
    return sha256(canonical(value)).hexdigest()


async def put(db: AsyncConnection, instance: str, kind: str, payload: dict[str, object]) -> Ref:
    reference = Ref(instance_id=instance, kind=kind, id=str(uuid4()), digest=digest(payload))
    await db.execute(
        text(
            "INSERT INTO model_record_v2(instance_id,id,kind,revision,digest,payload) "
            "VALUES (:instance_id,:id,:kind,1,:digest,CAST(:payload AS jsonb))"
        ),
        {**reference.model_dump(), "payload": json.dumps(payload, allow_nan=False)},
    )
    return reference


async def resolve(
    db: AsyncConnection, instance: str, reference: Ref, kind: str
) -> dict[str, object]:
    if reference.instance_id != instance or reference.kind != kind:
        raise ModelConflict("REF_UNAVAILABLE")
    payload: object = (
        await db.execute(
            text(
                "SELECT payload FROM model_record_v2 WHERE instance_id=:instance_id "
                "AND id=:id AND kind=:kind AND revision=:revision AND digest=:digest"
            ),
            reference.model_dump(),
        )
    ).scalar_one_or_none()
    if not isinstance(payload, dict) or digest(payload) != reference.digest:
        raise ModelConflict("REF_UNAVAILABLE")
    return {str(k): v for k, v in payload.items()}


async def snapshot(db: AsyncConnection, instance: str, reference: Ref) -> Snapshot | EntrySnapshot:
    if reference.kind == "model-entry-snapshot-v1":
        return EntrySnapshot.model_validate_json(
            json.dumps(await resolve(db, instance, reference, reference.kind))
        )
    return Snapshot.model_validate_json(
        json.dumps(await resolve(db, instance, reference, "model-selection-snapshot-v2"))
    )


async def capabilities(
    db: AsyncConnection, instance: str, reference: Ref
) -> Capabilities | EntryCapabilities:
    if reference.kind == "model-entry-capabilities-v1":
        return EntryCapabilities.model_validate_json(
            json.dumps(await resolve(db, instance, reference, reference.kind))
        )
    return Capabilities.model_validate_json(
        json.dumps(await resolve(db, instance, reference, "model-capabilities-v2"))
    )


async def operation(
    db: AsyncConnection, instance: str, identity: str | None, *, legacy_latest: bool = False
) -> Operation | None:
    row = (
        (
            await db.execute(
                text(
                    "SELECT * FROM system_operation WHERE instance_id=:instance "
                    + (
                        "AND operation_id=:id"
                        if identity
                        else (
                            "AND config_snapshot_ref->>'kind'='model-selection-snapshot-v2' "
                            if legacy_latest
                            else ""
                        )
                        + "ORDER BY deadline DESC LIMIT 1"
                    )
                ),
                {"instance": instance, "id": identity},
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        return None
    fields = dict(row)
    for key in ("instance_id", "operation_id", "command_id", "execution_owner_id"):
        fields[key] = str(fields[key])
    return Operation.model_validate(fields)


async def save_operation(db: AsyncConnection, value: Operation, *, initial: bool = False) -> None:
    parameters = value.model_dump()
    for key in ("config_snapshot_ref", "input_projection_ref", "outcome_ref"):
        parameters[key] = json.dumps(parameters[key]) if parameters[key] is not None else None
    if initial:
        await db.execute(
            text(
                "INSERT INTO system_operation ("
                + ",".join(parameters)
                + ") VALUES ("
                + ",".join(
                    "CAST(:" + key + " AS jsonb)" if key.endswith("_ref") else ":" + key
                    for key in parameters
                )
                + ")"
            ),
            parameters,
        )
    else:
        await db.execute(
            text(
                "UPDATE system_operation SET state=:state,state_revision=:state_revision, "
                "cancel_epoch=:cancel_epoch,finish_reason=:finish_reason,outcome_ref=CAST(:outcome_ref AS jsonb) "
                "WHERE instance_id=:instance_id AND operation_id=:operation_id AND state_revision=:previous"
            ),
            {**parameters, "previous": value.state_revision - 1},
        )
    await db.execute(
        text(
            "INSERT INTO system_operation_event(instance_id,operation_id,state_revision,payload) "
            "VALUES (:instance,:id,:revision,CAST(:payload AS jsonb))"
        ),
        {
            "instance": value.instance_id,
            "id": value.operation_id,
            "revision": value.state_revision,
            "payload": value.model_dump_json(),
        },
    )


async def replay(
    db: AsyncConnection, instance: str, command: str, request_digest: str
) -> tuple[bool, str | None]:
    row = (
        await db.execute(
            text(
                "SELECT request_digest,operation_id::text FROM model_command_v2 "
                "WHERE instance_id=:instance AND command_id=:command"
            ),
            {"instance": instance, "command": command},
        )
    ).one_or_none()
    if row is None:
        return False, None
    if row[0] != request_digest:
        raise ModelConflict("COMMAND_CONFLICT")
    return True, row[1]


async def command(
    db: AsyncConnection,
    instance: str,
    identity: str,
    request_digest: str,
    action: str,
    operation_id: str | None,
) -> None:
    await db.execute(
        text(
            "INSERT INTO model_command_v2(instance_id,command_id,request_digest,action,operation_id) "
            "VALUES (:instance,:command,:digest,:action,:operation)"
        ),
        {
            "instance": instance,
            "command": identity,
            "digest": request_digest,
            "action": action,
            "operation": operation_id,
        },
    )


async def dispatch(db: AsyncConnection, instance: str, identity: str) -> Dispatch:
    value: object = (
        await db.execute(
            text(
                "SELECT payload FROM model_dispatch_v2 WHERE instance_id=:instance "
                "AND operation_id=:id"
            ),
            {"instance": instance, "id": identity},
        )
    ).scalar_one()
    return Dispatch.model_validate_json(json.dumps(value))


async def event(
    db: AsyncConnection, instance: str, identity: str, state: str, receipt: Ref | None = None
) -> None:
    last: object = (
        await db.execute(
            text(
                "SELECT state FROM model_dispatch_event_v2 WHERE instance_id=:instance "
                "AND dispatch_attempt_id=:id ORDER BY sequence DESC LIMIT 1"
            ),
            {"instance": instance, "id": identity},
        )
    ).scalar_one_or_none()
    if last == state:
        return
    valid = {
        (None, "RESERVED"): 1,
        ("RESERVED", "SENT"): 2,
        ("RESERVED", "RELEASED"): 2,
        ("SENT", "SETTLED"): 3,
    }
    sequence = valid.get((last, state)) if isinstance(last, (str, type(None))) else None
    if sequence is None:
        raise ModelConflict("DISPATCH_CONFLICT")
    await db.execute(
        text(
            "INSERT INTO model_dispatch_event_v2(instance_id,dispatch_attempt_id,sequence,state,receipt_ref) "
            "VALUES (:instance,:id,:sequence,:state,CAST(:receipt AS jsonb))"
        ),
        {
            "instance": instance,
            "id": identity,
            "sequence": sequence,
            "state": state,
            "receipt": receipt.model_dump_json() if receipt else None,
        },
    )
