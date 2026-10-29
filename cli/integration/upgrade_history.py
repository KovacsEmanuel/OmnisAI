"""Synthetic settled archive for existing installed upgrade QA; no sender/provider IO.

Reuse the typed migration fixture in test_provider_key_api, not an effect owner.
"""

import asyncio
import json
import os
import sys
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import text

from omnis.core.db import database_engine
from omnis.modules.runs import model_test_store as store
from omnis.modules.runs.model_test_contract import (
    Caps,
    Dispatch,
    EntryCapabilities,
    EntrySnapshot,
    Operation,
    Outcome,
    Projection,
)
from omnis.modules.settings.provider_catalog_models import CatalogModel, CatalogView
from omnis.modules.settings.provider_key_service import ConnectionRevision
from omnis.modules.settings.provider_model_models import ModelEntry


async def seed_history(db, instance, connection, entry_id, secret, operation_id, dispatch_id):
    entry = ModelEntry(
        entry_id=entry_id,
        connection_id=connection,
        connection_revision=1,
        model="synthetic/upgrade",
        revision=1,
        output_tokens=37,
    )
    seed_connection = ConnectionRevision(
        connection_id=connection,
        provider="openrouter",
        revision=1,
        enabled=True,
        secret_id=secret,
        credential_revision=1,
    )
    catalog = CatalogView(
        connection_id=connection,
        connection_revision=1,
        provider="openrouter",
        catalog_command_id=str(uuid4()),
        state="READY",
        query="",
        offset=0,
        total=1,
        entries=[
            CatalogModel(
                model=entry.model,
                max_output_tokens=128,
                supports_max_tokens=True,
            )
        ],
    )
    catalog_ref = await store.put(db, instance, "catalog-result", catalog.model_dump(mode="json"))
    capabilities = EntryCapabilities(
        entry=entry,
        connection=seed_connection,
        catalog_ref=catalog_ref,
        max_output_tokens=128,
    )
    capability = await store.put(
        db,
        instance,
        "model-entry-capabilities-v1",
        capabilities.model_dump(mode="json"),
    )
    snapshot = EntrySnapshot(
        entry=entry,
        connection=seed_connection,
        capabilities_ref=capability,
        endpoint="https://openrouter.ai/api/v1",
    )
    config = await store.put(
        db,
        instance,
        "model-entry-snapshot-v1",
        snapshot.model_dump(mode="json"),
    )
    projection = Projection(model=entry.model, output_tokens=entry.output_tokens)
    projected = await store.put(db, instance, "model-input-v2", projection.model_dump(mode="json"))
    identity = operation_id
    operation = Operation(
        instance_id=instance,
        operation_id=identity,
        command_id=identity,
        payload_digest="c" * 64,
        config_snapshot_ref=config,
        input_projection_ref=projected,
        execution_owner_id=str(uuid4()),
        generation=1,
        owner_epoch=1,
        cancel_epoch=1,
        deadline=datetime.now(UTC) + timedelta(seconds=300),
        state_revision=1,
        state="PENDING",
        finish_reason=None,
        outcome_ref=None,
    )
    await store.save_operation(db, operation, initial=True)
    scope = await store.put(db, instance, "system-operation", operation.model_dump(mode="json"))
    dispatch_owner = await store.put(
        db,
        instance,
        "dispatch-owner-v2",
        {
            "execution_owner_id": operation.execution_owner_id,
            "owner_epoch": 1,
            "generation": 1,
            "scope_ref": scope.model_dump(mode="json"),
        },
    )
    permit = await store.put(
        db,
        instance,
        "model-permit-v2",
        {
            "scope_ref": scope.model_dump(mode="json"),
            "owner_ref": dispatch_owner.model_dump(mode="json"),
            "config_ref": config.model_dump(mode="json"),
            "calls": 1,
        },
    )
    dispatch = Dispatch(
        scope_ref=scope,
        dispatch_attempt_id=dispatch_id,
        dispatch_owner_ref=dispatch_owner,
        config_snapshot_ref=config,
        projection_ref=projected,
        projection_digest=projected.digest,
        reservation_ref=permit,
        instance_generation=1,
        owner_epoch=1,
        cancel_epoch=1,
        deadline=operation.deadline,
        technical_caps=Caps(output_tokens=projection.output_tokens),
    )
    await db.execute(
        text(
            "INSERT INTO model_dispatch_v2(instance_id,dispatch_attempt_id,operation_id,payload) VALUES (:instance,:id,:operation,CAST(:payload AS jsonb))"
        ),
        {
            "instance": instance,
            "id": dispatch.dispatch_attempt_id,
            "operation": identity,
            "payload": dispatch.model_dump_json(),
        },
    )
    await store.event(db, instance, dispatch.dispatch_attempt_id, "RESERVED")
    await store.event(db, instance, dispatch.dispatch_attempt_id, "SENT")
    dispatch_ref = await store.put(
        db, instance, "model-dispatch-v2", dispatch.model_dump(mode="json")
    )
    outcome = Outcome(
        operation_or_run_ref=scope,
        dispatch_ref=dispatch_ref,
        requested=config,
        result_state="UNKNOWN",
        reason_code="SYNTHETIC_MIGRATION_INPUT",
        usage_state="KNOWN",
        input_tokens=9,
        output_tokens=7,
        cost_observed="0.000016",
        recorded_at=datetime.now(UTC),
    )
    outcome_ref = await store.put(db, instance, "model-outcome-v2", outcome.model_dump(mode="json"))
    await store.event(db, instance, dispatch.dispatch_attempt_id, "SETTLED", outcome_ref)
    finished = Operation.model_validate(
        {
            **operation.model_dump(),
            "state": "FINISHED",
            "state_revision": 2,
            "finish_reason": "OWNER_LOST",
            "outcome_ref": outcome_ref,
        }
    )
    await store.save_operation(db, finished)
    await store.command(db, instance, identity, "c" * 64, "start", identity)


async def main(context):
    engine = database_engine(os.environ["OMNIS_DATABASE_URL"])
    try:
        async with engine.begin() as db:
            await seed_history(db, **context)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main(json.loads(sys.argv[1])))
