"""Supervisor's finite T1 consumer. No scheduler, native context, or resend path."""

import asyncio
import json
from collections.abc import AsyncIterator, Coroutine
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from omnis.core.persistence import read_datetime
from omnis.modules.runs import model_test_store as store
from omnis.modules.runs.model_test_contract import (
    ENDPOINTS,
    Capabilities,
    Caps,
    Dispatch,
    ModelTestView,
    Operation,
    Outcome,
    Projection,
    Ref,
    Snapshot,
)
from omnis.modules.runs.model_test_models import ModelTestControl
from omnis.modules.settings.provider_key_models import SelectionView
from omnis.modules.settings.provider_key_service import ConnectionRevision, ProviderSettingsOwner
from omnis.supervisor.model_sender import ModelSender, Reply, SendDenied


class ApiKeyModelTest:
    def __init__(self, settings: ProviderSettingsOwner, sender: ModelSender) -> None:
        self.settings, self.sender = settings, sender
        self.service = settings.service
        self.instance = settings.vault.instance_id
        self.tasks: set[asyncio.Task[None]] = set()
        self.closing = False
        self.settlement_failed = False
        settings.model_drain = self.drain_models

    def spawn(self, coroutine: Coroutine[None, None, None]) -> None:
        task = asyncio.create_task(coroutine)
        self.tasks.add(task)
        task.add_done_callback(self.finished)

    def finished(self, task: asyncio.Task[None]) -> None:
        self.tasks.discard(task)
        if not task.cancelled() and task.exception() is not None:
            self.settlement_failed = True

    async def drain(self) -> bool:
        self.closing = True
        return await self.drain_models() and await self.settings.drain()

    async def drain_models(self) -> bool:
        for task in self.tasks:
            task.cancel()
        if self.tasks:
            _, pending = await asyncio.wait(self.tasks, timeout=1.5)
            if pending:
                return False
        await self.sender.drain()
        if not self.settlement_failed:
            await self.reconcile(cancelled=True)
        return not self.settlement_failed

    async def reconcile(self, *, cancelled: bool = False) -> None:
        # New process never schedules inherited work, even a PENDING pre-send attempt.
        async with self.service.engine.begin() as db:
            rows = (
                (
                    await db.execute(
                        text(
                            "SELECT operation_id::text FROM system_operation "
                            "WHERE instance_id=:instance AND state <> 'FINISHED' "
                            + (
                                "AND execution_owner_id=:owner AND owner_epoch=:epoch "
                                if cancelled
                                else ""
                            )
                            + "FOR UPDATE"
                        ),
                        {
                            "instance": self.instance,
                            "owner": str(self.settings.owner),
                            "epoch": self.settings.epoch,
                        },
                    )
                )
                .scalars()
                .all()
            )
            for identity in rows:
                op = await store.operation(db, self.instance, identity)
                assert op is not None
                dispatch = await store.dispatch(db, self.instance, identity)
                reason = "CANCELLED" if cancelled else "OWNER_LOST"
                await self.settle(db, op, dispatch, Reply("UNKNOWN", reason), reason)

    async def latest(
        self, db: AsyncConnection, kind: str, command_id: str | None = None
    ) -> dict[str, object] | None:
        payload: object = (
            await db.execute(
                text(
                    "SELECT payload FROM model_record_v2 WHERE instance_id=:instance "
                    "AND kind=:kind "
                    + ("AND payload->>'command_id'=:command " if command_id else "")
                    + "ORDER BY created_at DESC LIMIT 1"
                ),
                {"instance": self.instance, "kind": kind, "command": command_id},
            )
        ).scalar_one_or_none()
        return {str(k): v for k, v in payload.items()} if isinstance(payload, dict) else None

    async def view(self, identity: str | None = None) -> dict[str, object]:
        async with self.service.engine.connect() as db:
            selection = await self.settings.selection(db)
            request = await self.latest(db, "metadata-request")
            metadata: dict[str, object] = {
                "selection_revision": selection.revision if selection else None
            }
            if request is not None:
                result = await self.latest(db, "metadata-result", str(request["command_id"]))
                metadata.update(
                    metadata_command_id=request["command_id"],
                    metadata_state="PENDING" if result is None else result["state"],
                )
                if result is not None:
                    metadata["reason"] = result.get("reason")
                if result is None and request["owner_epoch"] != self.settings.epoch:
                    metadata.update(metadata_state="FAILED", reason="OWNER_LOST")
                if request["selection_revision"] != metadata["selection_revision"]:
                    metadata["metadata_state"] = "NOT_REQUESTED"
            op = await store.operation(db, self.instance, identity)
            if identity is not None and op is None:
                raise store.ModelConflict("NOT_FOUND")
            if op is None:
                return ModelTestView.model_validate(metadata).model_dump(mode="json")
            snapshot = Snapshot.model_validate_json(
                json.dumps(
                    await store.resolve(
                        db, self.instance, op.config_snapshot_ref, "model-selection-snapshot-v2"
                    )
                )
            )
            fields: dict[str, object] = {
                **metadata,
                "operation_id": op.operation_id,
                "state": op.state,
                "state_revision": op.state_revision,
                "finish_reason": op.finish_reason,
                "requested_provider": snapshot.connection.provider,
                "requested_model": snapshot.selection.default.model,
                "requested_output_tokens": snapshot.selection.default.output_tokens,
            }
            if op.outcome_ref is not None:
                outcome = Outcome.model_validate_json(
                    json.dumps(
                        await store.resolve(db, self.instance, op.outcome_ref, "model-outcome-v2")
                    )
                )
                fields.update(
                    {
                        k: getattr(outcome, k)
                        for k in (
                            "result_state",
                            "output_state",
                            "observed_model",
                            "provider_status",
                            "usage_state",
                            "input_tokens",
                            "output_tokens",
                            "reasoning_tokens",
                            "cost_observed",
                        )
                    }
                )
                fields["reason"] = outcome.reason_code
                if outcome.output_ref is not None:
                    fields["response_text"] = (
                        await store.resolve(
                            db, self.instance, outcome.output_ref, "model-output-v2"
                        )
                    )["text"]
            return ModelTestView.model_validate(fields).model_dump(mode="json")

    async def handle(self, command: ModelTestControl) -> dict[str, object]:
        if command.action == "read":
            return await self.view(command.operation_id)
        if command.action == "provision":
            raise store.ModelConflict("ROOT_CONTEXT_UNAVAILABLE")
        identity = command.operation_id if command.action == "start" else command.command_id
        assert identity is not None
        request_digest = store.digest(command.model_dump(mode="json", exclude_none=True))
        async with self.settings.lock:
            async with self.service.engine.connect() as db:
                repeated, previous = await store.replay(db, self.instance, identity, request_digest)
            if repeated:
                return await self.view(previous)
            if self.closing or self.settlement_failed:
                raise store.ModelConflict("CONTROL_UNAVAILABLE")
            status = await self.service.owned_status(self.settings.owner, self.settings.epoch)
            async with self.service.admission(
                status.generation, self.settings.owner, self.settings.epoch
            ) as db:
                if command.action == "cancel":
                    op = await store.operation(db, self.instance, command.operation_id)
                    if op is None:
                        raise store.ModelConflict("NOT_FOUND")
                    if op.state_revision != command.expected_state_revision:
                        raise store.ModelConflict("REVISION_CONFLICT")
                    if op.state == "FINISHED":
                        raise store.ModelConflict("OPERATION_FINISHED")
                    stopping = op.model_copy(
                        update={
                            "state": "STOPPING",
                            "cancel_epoch": op.cancel_epoch + 1,
                            "state_revision": op.state_revision + 1,
                        }
                    )
                    await store.save_operation(db, stopping)
                    await store.command(
                        db, self.instance, identity, request_digest, "cancel", op.operation_id
                    )
                else:
                    if (
                        self.tasks
                        or (
                            await db.execute(
                                text(
                                    "SELECT 1 FROM system_operation WHERE instance_id=:instance "
                                    "AND state <> 'FINISHED'"
                                ),
                                {"instance": self.instance},
                            )
                        ).first()
                        is not None
                    ):
                        raise store.ModelConflict("OPERATION_ACTIVE")
                    selection = await self.settings.selection(db)
                    if (
                        selection is None
                        or selection.revision != command.expected_selection_revision
                    ):
                        raise store.ModelConflict("REVISION_CONFLICT")
                    connection = await self.settings.require_selection(db, selection.default)
                    if command.action == "refresh":
                        await store.put(
                            db,
                            self.instance,
                            "metadata-request",
                            {
                                "command_id": identity,
                                "selection_revision": selection.revision,
                                "generation": status.generation,
                                "owner_epoch": self.settings.epoch,
                            },
                        )
                        await store.command(
                            db, self.instance, identity, request_digest, "refresh", None
                        )
                    else:
                        metadata = await self.latest(db, "metadata-request")
                        result = (
                            await self.latest(db, "metadata-result", str(metadata["command_id"]))
                            if metadata
                            else None
                        )
                        if result is None or result["state"] != "READY":
                            raise store.ModelConflict("CAPABILITIES_REQUIRED")
                        cap_ref = Ref.model_validate(result["capabilities_ref"])
                        cap = Capabilities.model_validate_json(
                            json.dumps(
                                await store.resolve(
                                    db, self.instance, cap_ref, "model-capabilities-v2"
                                )
                            )
                        )
                        if (
                            cap.selection_revision != selection.revision
                            or cap.choice != selection.default
                            or cap.connection != connection
                            or selection.default.output_tokens > cap.max_output_tokens
                        ):
                            raise store.ModelConflict("CAPABILITIES_REQUIRED")
                        snapshot = Snapshot(
                            selection=selection,
                            connection=connection,
                            capabilities_ref=cap_ref,
                            endpoint=ENDPOINTS[connection.provider],
                        )
                        config = await store.put(
                            db,
                            self.instance,
                            "model-selection-snapshot-v2",
                            snapshot.model_dump(mode="json"),
                        )
                        projection = Projection(
                            model=selection.default.model,
                            output_tokens=selection.default.output_tokens,
                        )
                        input_ref = await store.put(
                            db, self.instance, "model-input-v2", projection.model_dump(mode="json")
                        )
                        op = Operation(
                            instance_id=self.instance,
                            operation_id=identity,
                            command_id=identity,
                            payload_digest=request_digest,
                            config_snapshot_ref=config,
                            input_projection_ref=input_ref,
                            execution_owner_id=str(self.settings.owner),
                            generation=status.generation,
                            owner_epoch=self.settings.epoch,
                            cancel_epoch=1,
                            deadline=datetime.now(UTC) + timedelta(seconds=300),
                            state_revision=1,
                            state="PENDING",
                            finish_reason=None,
                            outcome_ref=None,
                        )
                        await store.save_operation(db, op, initial=True)
                        scope = await store.put(
                            db, self.instance, "system-operation", op.model_dump(mode="json")
                        )
                        owner_ref = await store.put(
                            db,
                            self.instance,
                            "dispatch-owner-v2",
                            {
                                "execution_owner_id": op.execution_owner_id,
                                "owner_epoch": op.owner_epoch,
                                "generation": op.generation,
                                "scope_ref": scope.model_dump(mode="json"),
                            },
                        )
                        permit = await store.put(
                            db,
                            self.instance,
                            "model-permit-v2",
                            {
                                "scope_ref": scope.model_dump(mode="json"),
                                "owner_ref": owner_ref.model_dump(mode="json"),
                                "config_ref": config.model_dump(mode="json"),
                                "calls": 1,
                            },
                        )
                        dispatch = Dispatch(
                            scope_ref=scope,
                            dispatch_attempt_id=str(uuid4()),
                            dispatch_owner_ref=owner_ref,
                            config_snapshot_ref=config,
                            projection_ref=input_ref,
                            projection_digest=input_ref.digest,
                            reservation_ref=permit,
                            instance_generation=op.generation,
                            owner_epoch=op.owner_epoch,
                            cancel_epoch=op.cancel_epoch,
                            deadline=op.deadline,
                            technical_caps=Caps(output_tokens=projection.output_tokens),
                        )
                        await db.execute(
                            text(
                                "INSERT INTO model_dispatch_v2(instance_id,dispatch_attempt_id,operation_id,payload) "
                                "VALUES (:instance,:id,:op,CAST(:payload AS jsonb))"
                            ),
                            {
                                "instance": self.instance,
                                "id": dispatch.dispatch_attempt_id,
                                "op": identity,
                                "payload": dispatch.model_dump_json(),
                            },
                        )
                        await store.event(
                            db, self.instance, dispatch.dispatch_attempt_id, "RESERVED"
                        )
                        await store.command(
                            db, self.instance, identity, request_digest, "start", identity
                        )
            # Commit admission before making the one task visible; never a hidden queue.
            if command.action == "start":
                self.spawn(self.run(identity))
            elif command.action == "refresh":
                assert selection is not None
                self.spawn(self.refresh(identity, selection, connection, status.generation))
            else:
                for task in self.tasks:
                    task.cancel()
        if command.action == "cancel" and not await self.drain_models():
            raise store.ModelConflict("CONTROL_UNAVAILABLE")
        return await self.view(command.operation_id)

    @asynccontextmanager
    async def physical_window(self, db: AsyncConnection, deadline: datetime) -> AsyncIterator[None]:
        began = asyncio.get_running_loop().time()
        row = (
            await db.execute(
                text(
                    "SELECT clock_timestamp(), expires_at FROM supervisor_lease "
                    "WHERE id=1 AND owner=:owner AND epoch=:epoch AND expires_at>clock_timestamp()"
                ),
                {"owner": self.settings.owner, "epoch": self.settings.epoch},
            )
        ).one_or_none()
        if row is None:
            raise SendDenied("LEASE_LOST")
        now, expires = read_datetime(row[0]), read_datetime(row[1])
        end = began + min(0.5, (expires - now).total_seconds(), (deadline - now).total_seconds())
        if asyncio.get_running_loop().time() >= end:
            raise SendDenied("DEADLINE_OR_LEASE_LOST")
        async with asyncio.timeout_at(end):
            yield

    @asynccontextmanager
    async def metadata_guard(
        self, connection: ConnectionRevision, selection: SelectionView, generation: int
    ) -> AsyncIterator[None]:
        async with self.settings.lock:
            async with self.service.admission(
                generation, self.settings.owner, self.settings.epoch
            ) as db:
                if self.closing:
                    raise SendDenied("OWNER_CLOSED")
                if await self.settings.require_selection(db, selection.default) != connection:
                    raise SendDenied("CONNECTION_REVOKED")
                async with self.physical_window(db, datetime.now(UTC) + timedelta(seconds=15)):
                    yield

    async def refresh(
        self,
        command: str,
        selection: SelectionView,
        connection: ConnectionRevision,
        generation: int,
    ) -> None:
        result: dict[str, object] = {
            "command_id": command,
            "state": "FAILED",
            "reason": "METADATA_UNKNOWN",
        }
        try:
            async with asyncio.timeout(15):
                secret = await asyncio.to_thread(
                    self.settings.vault.get, connection.credential(self.instance)
                )
                raw = await self.sender.metadata(
                    ENDPOINTS[connection.provider],
                    secret,
                    lambda: self.metadata_guard(connection, selection, generation),
                )
                if not isinstance(raw, dict) or not isinstance(raw.get("data"), list):
                    raise SendDenied("METADATA_UNSUPPORTED")
                models: object = raw["data"]
                assert isinstance(models, list)
                found = [
                    m
                    for m in models
                    if isinstance(m, dict) and m.get("id") == selection.default.model
                ]
                if len(found) != 1:
                    raise SendDenied("MODEL_UNAVAILABLE")
                row = found[0]
                top: object = row.get("top_provider")
                maximum: object = (
                    top.get("max_completion_tokens") if isinstance(top, dict) else None
                )
                supported: object = row.get("supported_parameters")
                if (
                    type(maximum) is not int
                    or maximum < selection.default.output_tokens
                    or not isinstance(supported, list)
                    or "max_tokens" not in supported
                ):
                    raise SendDenied("CAPABILITY_UNSUPPORTED")
                capability = Capabilities(
                    selection_revision=selection.revision,
                    choice=selection.default,
                    connection=connection,
                    max_output_tokens=min(maximum, 65536),
                    fetched_at=datetime.now(UTC),
                )
                async with self.service.engine.begin() as db:
                    cap_ref = await store.put(
                        db,
                        self.instance,
                        "model-capabilities-v2",
                        capability.model_dump(mode="json"),
                    )
                result.update(
                    state="READY", reason=None, capabilities_ref=cap_ref.model_dump(mode="json")
                )
        except asyncio.CancelledError:
            result["reason"] = "CANCELLED_OR_STOPPED"
            raise
        except (ValueError, OSError, TimeoutError):
            result["reason"] = "METADATA_UNAVAILABLE"
        finally:
            async with self.service.engine.begin() as db:
                await store.put(db, self.instance, "metadata-result", result)

    @asynccontextmanager
    async def write_guard(self, identity: str) -> AsyncIterator[None]:
        async with self.settings.lock:
            async with self.service.engine.connect() as lookup:
                original = await store.operation(lookup, self.instance, identity)
            if original is None:
                raise SendDenied("OPERATION_UNAVAILABLE")
            async with self.service.admission(
                original.generation, self.settings.owner, self.settings.epoch
            ) as db:
                op = await store.operation(db, self.instance, identity)
                if (
                    op is None
                    or op.state != "RUNNING"
                    or self.closing
                    or op.execution_owner_id != str(self.settings.owner)
                    or op.owner_epoch != self.settings.epoch
                    or op.deadline <= datetime.now(UTC)
                ):
                    raise SendDenied("AUTHORITY_DENIED")
                dispatch = await store.dispatch(db, self.instance, identity)
                scope = await store.resolve(
                    db, self.instance, dispatch.scope_ref, "system-operation"
                )
                ownership = await store.resolve(
                    db, self.instance, dispatch.dispatch_owner_ref, "dispatch-owner-v2"
                )
                permit = await store.resolve(
                    db, self.instance, dispatch.reservation_ref, "model-permit-v2"
                )
                if (
                    scope["operation_id"] != identity
                    or ownership["scope_ref"] != dispatch.scope_ref.model_dump(mode="json")
                    or ownership["execution_owner_id"] != op.execution_owner_id
                    or ownership["owner_epoch"] != op.owner_epoch
                    or permit
                    != {
                        "scope_ref": dispatch.scope_ref.model_dump(mode="json"),
                        "owner_ref": dispatch.dispatch_owner_ref.model_dump(mode="json"),
                        "config_ref": op.config_snapshot_ref.model_dump(mode="json"),
                        "calls": 1,
                    }
                    or dispatch.cancel_epoch != op.cancel_epoch
                    or dispatch.config_snapshot_ref != op.config_snapshot_ref
                    or dispatch.projection_ref != op.input_projection_ref
                    or dispatch.deadline != op.deadline
                ):
                    raise SendDenied("DISPATCH_DENIED")
                snapshot = Snapshot.model_validate_json(
                    json.dumps(
                        await store.resolve(
                            db, self.instance, op.config_snapshot_ref, "model-selection-snapshot-v2"
                        )
                    )
                )
                capabilities = Capabilities.model_validate_json(
                    json.dumps(
                        await store.resolve(
                            db, self.instance, snapshot.capabilities_ref, "model-capabilities-v2"
                        )
                    )
                )
                projection = Projection.model_validate(
                    await store.resolve(
                        db, self.instance, op.input_projection_ref, "model-input-v2"
                    )
                )
                ledger = (
                    await db.execute(
                        text(
                            "SELECT state FROM model_dispatch_event_v2 WHERE instance_id=:instance AND dispatch_attempt_id=:id ORDER BY sequence DESC LIMIT 1"
                        ),
                        {"instance": self.instance, "id": dispatch.dispatch_attempt_id},
                    )
                ).scalar_one()
                if (
                    ledger != "SENT"
                    or dispatch.owner_epoch != op.owner_epoch
                    or dispatch.instance_generation != op.generation
                    or dispatch.technical_caps.output_tokens != projection.output_tokens
                    or dispatch.projection_digest != op.input_projection_ref.digest
                    or snapshot.endpoint != ENDPOINTS[snapshot.connection.provider]
                    or capabilities.choice != snapshot.selection.default
                    or capabilities.connection != snapshot.connection
                    or projection.output_tokens > capabilities.max_output_tokens
                ):
                    raise SendDenied("PERMIT_OR_CONFIG_DENIED")
                if (
                    await self.settings.require_selection(db, snapshot.selection.default)
                    != snapshot.connection
                ):
                    raise SendDenied("CONNECTION_REVOKED")
                await asyncio.to_thread(
                    self.settings.vault.get, snapshot.connection.credential(self.instance)
                )
                async with self.physical_window(db, op.deadline):
                    yield

    async def run(self, identity: str) -> None:
        reply = Reply("UNKNOWN", "RESULT_UNKNOWN")
        finish = "FAILED"
        try:
            async with self.settings.lock:
                status = await self.service.owned_status(self.settings.owner, self.settings.epoch)
                async with self.service.admission(
                    status.generation, self.settings.owner, self.settings.epoch
                ) as db:
                    op = await store.operation(db, self.instance, identity)
                    assert op is not None
                    dispatch = await store.dispatch(db, self.instance, identity)
                    snapshot = Snapshot.model_validate_json(
                        json.dumps(
                            await store.resolve(
                                db,
                                self.instance,
                                op.config_snapshot_ref,
                                "model-selection-snapshot-v2",
                            )
                        )
                    )
                    projection = Projection.model_validate(
                        await store.resolve(
                            db, self.instance, op.input_projection_ref, "model-input-v2"
                        )
                    )
                    if op.state != "PENDING" or op.deadline <= datetime.now(UTC):
                        raise SendDenied("OPERATION_CANCELLED")
                    await store.save_operation(
                        db, op.model_copy(update={"state": "RUNNING", "state_revision": 2})
                    )
                    await store.event(db, self.instance, dispatch.dispatch_attempt_id, "SENT")
            # SENT is committed before SDK/network; no SQL transaction waits for its response.
            secret = await asyncio.to_thread(
                self.settings.vault.get, snapshot.connection.credential(self.instance)
            )
            async with asyncio.timeout(max(0, (op.deadline - datetime.now(UTC)).total_seconds())):
                reply = await self.sender.send(
                    snapshot.endpoint, secret, projection, lambda: self.write_guard(identity)
                )
            finish = "COMPLETED" if reply.result_state == "COMPLETED" else "FAILED"
        except asyncio.CancelledError:
            finish = "CANCELLED"
            reply = Reply("UNKNOWN", "CANCELLED_OR_STOPPED")
            raise
        except TimeoutError:
            finish = "DEADLINE"
            reply = Reply("UNKNOWN", "DEADLINE")
        except (ValueError, OSError):
            reply = Reply("UNKNOWN", "AUTHORITY_OR_TRANSPORT_UNAVAILABLE")
        finally:
            async with self.service.engine.begin() as db:
                op = await store.operation(db, self.instance, identity)
                assert op is not None
                dispatch = await store.dispatch(db, self.instance, identity)
                await self.settle(db, op, dispatch, reply, finish)

    async def settle(
        self, db: AsyncConnection, op: Operation, dispatch: Dispatch, reply: Reply, finish: str
    ) -> None:
        if op.state == "FINISHED":
            return
        states = (
            (
                await db.execute(
                    text(
                        "SELECT state FROM model_dispatch_event_v2 WHERE instance_id=:instance "
                        "AND dispatch_attempt_id=:id ORDER BY sequence"
                    ),
                    {"instance": self.instance, "id": dispatch.dispatch_attempt_id},
                )
            )
            .scalars()
            .all()
        )
        sent = "SENT" in states
        output_ref = None
        content = reply.text.encode() if reply.text is not None else b""
        retained = content[:8192].decode(errors="ignore")
        if reply.text is not None:
            output_ref = await store.put(db, self.instance, "model-output-v2", {"text": retained})
        dispatch_ref = await store.put(
            db, self.instance, "model-dispatch-v2", dispatch.model_dump(mode="json")
        )
        outcome = Outcome.model_validate(
            {
                "operation_or_run_ref": dispatch.scope_ref,
                "dispatch_ref": dispatch_ref,
                "requested": op.config_snapshot_ref,
                "observed_model": reply.model,
                "provider_response_id": reply.response_id,
                "provider_status": reply.provider_status,
                "result_state": reply.result_state if sent else "NOT_SENT",
                "output_ref": output_ref,
                "output_state": "ABSENT"
                if reply.text is None
                else "TRUNCATED"
                if len(content) > 8192
                else "COMPLETE",
                "captured_bytes": len(retained.encode()),
                "reason_code": reply.reason,
                "usage_state": "KNOWN"
                if reply.input_tokens is not None and reply.output_tokens is not None
                else "PARTIAL"
                if reply.input_tokens is not None or reply.output_tokens is not None
                else "UNKNOWN",
                "input_tokens": reply.input_tokens,
                "output_tokens": reply.output_tokens,
                "reasoning_tokens": reply.reasoning_tokens,
                "cost_observed": reply.cost,
                "currency": None,
                "recorded_at": datetime.now(UTC),
            }
        )
        outcome_ref = await store.put(
            db, self.instance, "model-outcome-v2", outcome.model_dump(mode="json")
        )
        await store.event(
            db,
            self.instance,
            dispatch.dispatch_attempt_id,
            "SETTLED" if sent else "RELEASED",
            outcome_ref,
        )
        finished = Operation.model_validate(
            {
                **op.model_dump(),
                "state": "FINISHED",
                "state_revision": op.state_revision + 1,
                "finish_reason": finish,
                "outcome_ref": outcome_ref,
            }
        )
        await store.save_operation(db, finished)
