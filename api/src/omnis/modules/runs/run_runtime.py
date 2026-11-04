"""S1 owner on InstanceService: one SDK step, durable checkpoint, fresh admission."""

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from omnis.modules.engagements.schemas import EngagementDraft
from omnis.modules.engagements.service import checked_view
from omnis.modules.instance.domain import ControlConflict
from omnis.modules.runs import model_test_store as records
from omnis.modules.runs import run_store as store
from omnis.modules.runs.model_test_contract import Ref
from omnis.modules.runs.model_test_runtime import ApiKeyModelTest
from omnis.modules.runs.run_contract import (
    Attempt,
    BrainDecision,
    CommandReceipt,
    Preflight,
    Question,
    RoleConfig,
    RunControl,
    RunView,
    Setup,
    StartRun,
    WorkerFinal,
    completion_status,
)
from omnis.modules.settings.catalog_models import ExactRef
from omnis.modules.settings.catalog_publication import PublicationCatalog
from omnis.modules.settings.provider_catalog_runtime import CatalogResult
from omnis.modules.tasks.agent_composition import compose_publication
from omnis.supervisor.agent_runner import (
    AgentStep,
    Exchange,
    StepInput,
    StepResult,
    contains_secret,
    decode,
)
from omnis.supervisor.model_relay_protocol import Authority, Scope
from omnis.supervisor.model_sender import SendDenied


class AgentRunOwner:
    def __init__(self, model_owner: ApiKeyModelTest, catalog: PublicationCatalog) -> None:
        self.model_owner, self.catalog = model_owner, catalog
        self.settings, self.service = model_owner.settings, model_owner.service
        self.instance = model_owner.instance
        self.runner = AgentStep(model_owner.sender.transport)
        self.tasks: dict[str, asyncio.Task[None]] = {}
        self.continuations: set[str] = set()
        self.failed = False
        self.closing = False
        self.draining = False
        self.drain_lock = asyncio.Lock()

    def spawn(self, identity: str) -> None:
        if identity in self.tasks:
            self.continuations.add(identity)
            return
        task = asyncio.create_task(self.work(identity))
        self.tasks[identity] = task

        def settled(done: asyncio.Task[None]) -> None:
            self.tasks.pop(identity, None)
            if not done.cancelled() and done.exception() is not None:
                self.failed = True
            wake = identity in self.continuations
            self.continuations.discard(identity)
            if wake and not self.closing and not self.failed:
                self.spawn(identity)

        task.add_done_callback(settled)

    def require_owned(self, run: RunView, *, running: bool = True) -> None:
        if (
            self.closing
            or self.draining
            or run.owner_id != str(self.settings.owner)
            or run.owner_epoch != self.settings.epoch
            or (running and run.state != "RUNNING")
        ):
            raise records.ModelConflict("AUTHORITY_DENIED")

    async def role_config(self, db: AsyncConnection, role: str, revision: int) -> RoleConfig:
        selection = await self.settings.selection(db)
        if selection is None or selection.revision != revision:
            raise records.ModelConflict("REVISION_CONFLICT")
        choice = await self.settings.resolve_role(
            db, selection, "brain" if role == "BRAIN" else "recon"
        )
        connection = await self.settings.require_selection(db, choice)
        rows = (
            await db.execute(
                text(
                    "SELECT id::text,digest,payload FROM model_record_v2 WHERE instance_id=:instance AND kind='catalog-result' AND payload->'connection'->>'connection_id'=:connection ORDER BY created_at DESC LIMIT 1"
                ),
                {"instance": self.instance, "connection": choice.connection_id},
            )
        ).all()
        if not rows:
            raise records.ModelConflict("CAPABILITIES_REQUIRED")
        raw = rows[0]
        ref = Ref(instance_id=self.instance, kind="catalog-result", id=raw[0], digest=raw[1])
        result = CatalogResult.model_validate(
            await records.resolve(db, self.instance, ref, ref.kind)
        )
        metadata = next((entry for entry in result.entries if entry.model == choice.model), None)
        if (
            result.connection != connection
            or result.state not in {"READY", "PARTIAL"}
            or metadata is None
            or metadata.reason is not None
            or metadata.supports_max_tokens is not True
            or metadata.max_output_tokens is None
            or metadata.max_output_tokens < choice.output_tokens
        ):
            raise records.ModelConflict("CAPABILITIES_REQUIRED")
        return RoleConfig(choice=choice, connection=connection, capabilities_ref=ref)

    async def preflight(self, db: AsyncConnection, command: Preflight) -> CommandReceipt:
        selection = await self.settings.selection(db)
        if selection is None or selection.revision != command.selection_revision:
            raise records.ModelConflict("REVISION_CONFLICT")
        row = (
            (
                await db.execute(
                    text(
                        "SELECT e.id AS engagement_id,r.schema_version,r.kind,r.id,r.revision,r.digest,r.payload,r.created_at FROM engagement e JOIN engagement_revision r ON r.engagement_id=e.id AND r.revision=e.current_revision WHERE e.id=:id FOR UPDATE OF e"
                    ),
                    {"id": command.engagement_id},
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise records.ModelConflict("NOT_FOUND")
        view = checked_view(row)
        expected = ExactRef(
            kind="engagement-revision", id=str(view.id), revision=view.revision, digest=view.digest
        )
        if command.draft_ref != expected or not isinstance(view.payload, EngagementDraft):
            raise records.ModelConflict("REVISION_CONFLICT")
        catalog_owner = await db.scalar(
            text(
                "SELECT owner_id::text FROM catalog_record WHERE id=:id AND kind='catalog-publication'"
            ),
            {"id": command.publication_ref.id},
        )
        if not isinstance(catalog_owner, str):
            raise records.ModelConflict("REF_UNAVAILABLE")
        brief = "S1 inert only. Read the operator-selected synthetic context. No target actions."
        for connection in await self.settings.connections(db):
            secret = await asyncio.to_thread(
                self.settings.vault.get, connection.credential(self.instance)
            )
            if contains_secret(command.synthetic_context, secret):
                raise records.ModelConflict("DATA_DENIED")
        compositions = [
            await compose_publication(
                self.catalog, db, catalog_owner, command.publication_ref, role=role, brief=brief
            )
            for role in ("BRAIN", "RECON")
        ]
        composition_refs = [
            await records.put(
                db,
                self.instance,
                "run-composition-v1",
                json.loads(json.dumps(asdict(c), default=lambda obj: obj.model_dump(mode="json"))),
            )
            for c in compositions
        ]
        context_ref = await records.put(
            db,
            self.instance,
            "run-context-v1",
            {"text": command.synthetic_context, "data_policy": "SELECTED_SYNTHETIC_ONLY"},
        )
        snapshot = Setup(
            engagement_id=command.engagement_id,
            draft_ref=expected,
            draft=view.payload,
            expected_generation=command.expected_generation,
            selection_revision=command.selection_revision,
            selection_snapshot=selection,
            catalog_owner_id=catalog_owner,
            publication_ref=command.publication_ref,
            context_ref=context_ref,
            brain=await self.role_config(db, "BRAIN", command.selection_revision),
            recon=await self.role_config(db, "RECON", command.selection_revision),
            brain_instructions=compositions[0].text,
            recon_instructions=compositions[1].text,
            composition_refs=composition_refs,
        )
        reference = await records.put(
            db, self.instance, "run-setup-v1", snapshot.model_dump(mode="json")
        )
        await db.execute(
            text(
                "INSERT INTO run_setup(instance_id,setup_id,engagement_id,draft_id) VALUES (:instance,:setup,:engagement,:draft)"
            ),
            {
                "instance": self.instance,
                "setup": reference.id,
                "engagement": command.engagement_id,
                "draft": expected.id,
            },
        )
        return CommandReceipt(
            command_id=command.command_id, setup_ref=reference, revision=1, state="READY"
        )

    async def revalidate(self, db: AsyncConnection, snapshot: Setup) -> None:
        for config in (snapshot.brain, snapshot.recon):
            if await self.settings.require_selection(db, config.choice) != config.connection:
                raise records.ModelConflict("CONNECTION_UNAVAILABLE")
            await records.resolve(db, self.instance, config.capabilities_ref, "catalog-result")
        await self.catalog.load_core(
            db, snapshot.catalog_owner_id, snapshot.publication_ref.model_dump(mode="json")
        )
        await records.resolve(db, self.instance, snapshot.context_ref, "run-context-v1")

    async def new_attempt(
        self,
        db: AsyncConnection,
        run: RunView,
        snapshot: Setup,
        *,
        role: str,
        brief: str,
        parent: str | None,
    ) -> RunView:
        pending = await store.inbox(db, run) if role == "BRAIN" else []
        inputs = [ref for ref, _ in pending] if role == "BRAIN" else [snapshot.context_ref]
        input_text = json.dumps(
            {
                "brief": brief,
                "context_ref": snapshot.context_ref.model_dump(mode="json"),
                "inbox": [
                    {"ref": ref.model_dump(mode="json"), "result": payload}
                    for ref, payload in pending
                ],
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
        composition = await records.resolve(
            db,
            self.instance,
            snapshot.composition_refs[0 if role == "BRAIN" else 1],
            "run-composition-v1",
        )
        attempt = Attempt.model_validate(
            {
                "instance_id": self.instance,
                "run_id": run.run_id,
                "task_id": str(uuid4()),
                "attempt_id": str(uuid4()),
                "role": role,
                "parent_task_id": parent,
                "state": "RUNNING",
                "brief": brief,
                "input_refs": [r.model_dump() for r in inputs],
                "input_text": input_text,
                "configured_model": (
                    snapshot.brain if role == "BRAIN" else snapshot.recon
                ).choice.model,
                "skill_refs": composition["skill_refs"],
                "instructions": snapshot.brain_instructions
                if role == "BRAIN"
                else snapshot.recon_instructions,
            }
        )
        await store.save_attempt(db, attempt, initial=True)
        return run.model_copy(update={"active_attempt_id": attempt.attempt_id})

    async def handle(self, envelope: RunControl) -> dict[str, object]:
        command = envelope.request
        request = command.model_dump(mode="json")
        wake = None
        drain = None
        async with self.settings.lock:
            async with self.service.engine.connect() as db:
                prior = await store.replay(db, self.instance, command.command_id, request)
            if prior is not None:
                return prior.model_dump(mode="json")
            async with self.service.admission(
                command.expected_generation, self.settings.owner, self.settings.epoch
            ) as db:
                if self.closing or self.draining:
                    raise records.ModelConflict("AUTHORITY_DENIED")
                if isinstance(command, Preflight):
                    result = await self.preflight(db, command)
                elif isinstance(command, StartRun):
                    await self.model_owner.require_idle(db)
                    if await db.scalar(
                        text(
                            "SELECT 1 FROM agent_run WHERE instance_id=:instance AND state NOT IN ('STOPPED','COMPLETED','LIMITED')"
                        ),
                        {"instance": self.instance},
                    ):
                        raise records.ModelConflict("OPERATION_ACTIVE")
                    snapshot = await store.setup(db, self.instance, command.setup_ref)
                    if snapshot.expected_generation != command.expected_generation:
                        raise records.ModelConflict("REVISION_CONFLICT")
                    current_draft = await db.scalar(
                        text("SELECT current_revision FROM engagement WHERE id=:id FOR UPDATE"),
                        {"id": snapshot.engagement_id},
                    )
                    if current_draft != snapshot.draft_ref.revision:
                        raise records.ModelConflict("REVISION_CONFLICT")
                    await self.revalidate(db, snapshot)
                    run = RunView(
                        instance_id=self.instance,
                        engagement_id=snapshot.engagement_id,
                        run_id=str(uuid4()),
                        setup_ref=command.setup_ref,
                        revision=1,
                        generation=command.expected_generation,
                        owner_id=str(self.settings.owner),
                        owner_epoch=self.settings.epoch,
                        fence=1,
                        state="RUNNING",
                    )
                    await store.save_run(db, run, initial=True)
                    run = await self.new_attempt(
                        db,
                        run,
                        snapshot,
                        role="BRAIN",
                        brief="Propose the first inert task; cite and consume every supplied inbox ref.",
                        parent=None,
                    )
                    cursor = await store.event(db, run, "started", "Inert run admitted")
                    run = run.model_copy(update={"through_cursor": cursor})
                    await store.save_run(db, run)
                    wake = run.run_id
                    result = CommandReceipt(
                        command_id=command.command_id,
                        run_id=run.run_id,
                        revision=run.revision,
                        state="ADMITTED",
                    )
                else:
                    run = await store.run(db, self.instance, command.run_id)
                    self.require_owned(run, running=False)
                    if (
                        run.revision != command.expected_revision
                        or run.generation != command.expected_generation
                    ):
                        raise records.ModelConflict("REVISION_CONFLICT")
                    if run.state in store.TERMINAL:
                        raise records.ModelConflict("OPERATION_FINISHED")
                    if command.action in {"pause", "stop"}:
                        run = run.model_copy(
                            update={
                                "state": "PAUSING" if command.action == "pause" else "STOPPING",
                                "fence": run.fence + 1,
                            }
                        )
                        drain = run.run_id
                    elif command.action == "resume":
                        if run.state not in {"PAUSED", "HOLD"} or run.run_id in self.tasks:
                            raise records.ModelConflict("AUTHORITY_DENIED")
                        snapshot = await store.setup(db, self.instance, run.setup_ref)
                        await self.revalidate(db, snapshot)
                        run = run.model_copy(update={"state": "RUNNING", "reason": None})
                        await db.execute(
                            text(
                                "UPDATE run_inbox SET held=false WHERE instance_id=:instance AND run_id=:run AND consumed_decision_id IS NULL"
                            ),
                            {"instance": self.instance, "run": run.run_id},
                        )
                        question = await store.question(db, run)
                        if run.active_attempt_id is None and (
                            question is None or question.state != "PENDING"
                        ):
                            run = await self.new_attempt(
                                db,
                                run,
                                snapshot,
                                role="BRAIN",
                                brief="Consume retained results; do not retry an unknown dispatch.",
                                parent=None,
                            )
                        wake = run.run_id
                    else:
                        question = await store.question(db, run)
                        if (
                            run.state != "RUNNING"
                            or question is None
                            or question.question_id != command.question_id
                            or question.state != "PENDING"
                            or command.answer is None
                        ):
                            raise records.ModelConflict("ANSWER_DENIED")
                        for connection in await self.settings.connections(db):
                            secret = await asyncio.to_thread(
                                self.settings.vault.get, connection.credential(self.instance)
                            )
                            if contains_secret(command.answer, secret):
                                raise records.ModelConflict("DATA_DENIED")
                        answer = await records.put(
                            db,
                            self.instance,
                            "run-answer-v1",
                            {
                                "question_id": question.question_id,
                                "text": command.answer,
                                "scope_change": False,
                            },
                        )
                        await store.add_inbox(db, run, answer)
                        await store.save_question(
                            db,
                            run,
                            question.model_copy(
                                update={
                                    "state": "ANSWER_ADMITTED",
                                    "answer_ref": answer,
                                    "command_id": command.command_id,
                                }
                            ),
                        )
                        snapshot = await store.setup(db, self.instance, run.setup_ref)
                        run = await self.new_attempt(
                            db,
                            run,
                            snapshot,
                            role="BRAIN",
                            brief="Consume the clarification without changing scope or ROE.",
                            parent=question.task_id,
                        )
                        wake = run.run_id
                    cursor = await store.event(db, run, "control", command.action)
                    run = run.model_copy(
                        update={"revision": run.revision + 1, "through_cursor": cursor}
                    )
                    await store.save_run(db, run)
                    result = CommandReceipt(
                        command_id=command.command_id,
                        run_id=run.run_id,
                        revision=run.revision,
                        state="ADMITTED",
                    )
                await store.receipt(db, self.instance, request, result)
        # Admission closure/fence is committed before physical drain or task cancellation.
        if drain is not None:
            await self.drain_run(drain)
        elif wake is not None:
            self.spawn(wake)
        return result.model_dump(mode="json")

    async def dispatch_config(
        self, db: AsyncConnection, run: RunView, scope: Scope, state: str
    ) -> RoleConfig:
        row = (
            await db.execute(
                text(
                    "SELECT task_id::text,attempt_id::text,projection_id::text,state,payload FROM run_dispatch WHERE instance_id=:instance AND run_id=:run AND dispatch_id=:id"
                ),
                {"instance": self.instance, "run": run.run_id, "id": scope.id},
            )
        ).one_or_none()
        if row is None or row[3] != state or row[1] != run.active_attempt_id:
            raise SendDenied("DISPATCH_DENIED")
        binding: object = row[4]
        if (
            not isinstance(binding, dict)
            or set(binding)
            != {
                "schema_version",
                "scope_kind",
                "purpose",
                "accounting_policy",
                "technical_caps",
                "scope",
                "projection_ref",
                "setup_ref",
            }
            or type(binding["schema_version"]) is not int
            or binding["schema_version"] != 1
            or binding["scope_kind"] != "RUN"
            or binding["accounting_policy"] != "MONITOR"
            or records.digest(binding["scope"]) != records.digest(scope.wire())
            or binding["setup_ref"] != run.setup_ref.model_dump(mode="json")
        ):
            raise SendDenied("DISPATCH_BINDING_DENIED")
        reference = Ref.model_validate(binding["projection_ref"])
        if reference.id != row[2]:
            raise SendDenied("PROJECTION_DENIED")
        step = StepInput.model_validate(
            await records.resolve(db, self.instance, reference, "run-step-v1")
        )
        snapshot = await store.setup(db, self.instance, run.setup_ref)
        attempt = await store.attempt(db, run, row[1])
        config = snapshot.brain if attempt.role == "BRAIN" else snapshot.recon
        history = (
            [
                Exchange(
                    call_id=attempt.call_id,
                    arguments=attempt.tool_arguments or "",
                    result=attempt.tool_output,
                )
            ]
            if attempt.call_id is not None and attempt.tool_output is not None
            else []
        )
        expected = StepInput(
            role=attempt.role,
            model=config.choice.model,
            output_tokens=config.choice.output_tokens,
            provider=config.connection.provider,
            instructions=snapshot.brain_instructions
            if attempt.role == "BRAIN"
            else snapshot.recon_instructions,
            input_text=attempt.input_text,
            history=history,
        )
        if (
            step != expected
            or binding["purpose"] != ("DECISION" if attempt.role == "BRAIN" else "RECON")
            or records.digest(binding["technical_caps"])
            != records.digest(
                {
                    "calls": 1,
                    "input_bytes": 32768,
                    "output_tokens": config.choice.output_tokens,
                    "wall_seconds": 300,
                }
            )
            or attempt.task_id != row[0]
            or attempt.state != "RUNNING"
            or scope.provider != config.connection.provider
        ):
            raise SendDenied("PROJECTION_BINDING_DENIED")
        if await self.settings.require_selection(db, config.choice) != config.connection:
            raise SendDenied("CONNECTION_REVOKED")
        return config

    @asynccontextmanager
    async def write_guard(self, identity: str, scope: Scope) -> AsyncIterator[Authority]:
        async with self.settings.lock:
            async with self.service.admission(
                scope.generation, self.settings.owner, self.settings.epoch
            ) as db:
                run = await store.run(db, self.instance, identity)
                self.require_owned(run)
                if run.fence != scope.cancel_epoch or datetime.fromisoformat(
                    scope.deadline
                ) <= datetime.now(UTC):
                    raise SendDenied("FENCE_OR_DEADLINE")
                await self.dispatch_config(db, run, scope, "SENT")
                fields = {k: v for k, v in scope.wire().items() if k != "operation_serial"}
                retained = await records.relay_scope(db, fields)
                async with self.model_owner.physical_window(
                    db, datetime.fromisoformat(scope.deadline)
                ) as end:
                    yield Authority(retained, end)

    async def work(self, identity: str) -> None:
        while not self.closing:
            async with self.settings.lock:
                status = await self.service.owned_status(self.settings.owner, self.settings.epoch)
                async with self.service.admission(
                    status.generation, self.settings.owner, self.settings.epoch
                ) as db:
                    run = await store.run(db, self.instance, identity)
                    if run.state != "RUNNING":
                        return
                    self.require_owned(run)
                    snapshot = await store.setup(db, self.instance, run.setup_ref)
                    if run.generation != status.generation:
                        raise records.ModelConflict("GENERATION_CONFLICT")
                    if run.active_attempt_id is None:
                        if run.reason != "RESULT_READY":
                            return
                        run = await self.new_attempt(
                            db,
                            run,
                            snapshot,
                            role="BRAIN",
                            brief="Consume every retained result ref and decide the next step.",
                            parent=None,
                        )
                        run = run.model_copy(update={"reason": None})
                        await store.save_run(db, run)
                    assert run.active_attempt_id is not None
                    attempt = await store.attempt(db, run, run.active_attempt_id)
                    config = snapshot.brain if attempt.role == "BRAIN" else snapshot.recon
                    step = StepInput(
                        role=attempt.role,
                        model=config.choice.model,
                        output_tokens=config.choice.output_tokens,
                        provider=config.connection.provider,
                        instructions=attempt.instructions,
                        input_text=attempt.input_text,
                        history=[
                            Exchange(
                                call_id=attempt.call_id,
                                arguments=attempt.tool_arguments or "",
                                result=attempt.tool_output,
                            )
                        ]
                        if attempt.call_id is not None and attempt.tool_output is not None
                        else [],
                    )
                    projection = await records.put(
                        db, self.instance, "run-step-v1", step.model_dump(mode="json")
                    )
                    expires_at = asyncio.get_running_loop().time() + 300
                    deadline = datetime.now(UTC) + timedelta(seconds=300)
                    scope = await records.relay_scope(
                        db,
                        {
                            "instance_id": self.instance,
                            "kind": "MODEL_DISPATCH",
                            "id": str(uuid4()),
                            "execution_owner_id": str(self.settings.owner),
                            "generation": run.generation,
                            "owner_epoch": self.settings.epoch,
                            "cancel_epoch": run.fence,
                            "deadline": deadline.isoformat(),
                            "provider": config.connection.provider,
                        },
                        allocate=True,
                    )
                    await db.execute(
                        text(
                            "INSERT INTO run_dispatch(instance_id,run_id,task_id,attempt_id,dispatch_id,projection_id,state,deadline,payload) VALUES (:instance,:run,:task,:attempt,:id,:projection,'RESERVED',:deadline,CAST(:payload AS jsonb))"
                        ),
                        {
                            "instance": self.instance,
                            "run": identity,
                            "task": attempt.task_id,
                            "attempt": attempt.attempt_id,
                            "id": scope.id,
                            "projection": projection.id,
                            "deadline": deadline,
                            "payload": json.dumps(
                                {
                                    "schema_version": 1,
                                    "scope_kind": "RUN",
                                    "purpose": "DECISION" if attempt.role == "BRAIN" else "RECON",
                                    "accounting_policy": "MONITOR",
                                    "technical_caps": {
                                        "calls": 1,
                                        "input_bytes": 32768,
                                        "output_tokens": config.choice.output_tokens,
                                        "wall_seconds": 300,
                                    },
                                    "scope": scope.wire(),
                                    "projection_ref": projection.model_dump(mode="json"),
                                    "setup_ref": run.setup_ref.model_dump(mode="json"),
                                }
                            ),
                        },
                    )

                    await store.dispatch_event(db, self.instance, scope.id, "RESERVED")

            async def sent(*, scope: Scope = scope, attempt: Attempt = attempt) -> None:
                async with self.settings.lock:
                    async with self.service.admission(
                        scope.generation, self.settings.owner, self.settings.epoch
                    ) as db:
                        current = await store.run(db, self.instance, identity)
                        self.require_owned(current)
                        if (
                            current.fence != scope.cancel_epoch
                            or current.active_attempt_id != attempt.attempt_id
                        ):
                            raise SendDenied("FENCE_DENIED")
                        await self.dispatch_config(db, current, scope, "RESERVED")
                        changed = await db.execute(
                            text(
                                "UPDATE run_dispatch SET state='SENT' WHERE instance_id=:instance AND dispatch_id=:id AND state='RESERVED' AND deadline>clock_timestamp()"
                            ),
                            {"instance": self.instance, "id": scope.id},
                        )
                        if changed.rowcount != 1:
                            raise SendDenied("DISPATCH_DENIED")
                        await store.dispatch_event(db, self.instance, scope.id, "SENT")

            async def observe(
                raw: bytes, *, scope: Scope = scope, attempt: Attempt = attempt
            ) -> None:
                parsed = decode(raw)
                usage = parsed.get("usage") if isinstance(parsed, dict) else None
                fields: dict[str, object] = {
                    "dispatch_id": scope.id,
                    "state": "UNKNOWN",
                    "prompt_tokens": None,
                    "completion_tokens": None,
                }
                if isinstance(usage, dict):
                    for key in ("prompt_tokens", "completion_tokens"):
                        count = usage.get(key)
                        fields[key] = (
                            count if type(count) is int and 0 <= count <= 9007199254740991 else None
                        )
                    fields["state"] = (
                        "OBSERVED"
                        if all(
                            fields[k] is not None for k in ("prompt_tokens", "completion_tokens")
                        )
                        else "UNKNOWN"
                    )
                async with self.service.engine.begin() as db:
                    await records.put(db, self.instance, "run-usage-v1", fields)
                    retained_run = await store.run(db, self.instance, identity)
                    retained_attempt = await store.attempt(db, retained_run, attempt.attempt_id)
                    observed_model = parsed.get("model") if isinstance(parsed, dict) else None
                    if isinstance(observed_model, str) and len(observed_model) <= 256:
                        await store.save_attempt(
                            db,
                            retained_attempt.model_copy(update={"observed_model": observed_model}),
                        )

            async def tool(
                name: str,
                arguments: str,
                call_id: str,
                *,
                scope: Scope = scope,
                attempt: Attempt = attempt,
                snapshot: Setup = snapshot,
            ) -> str:
                async with self.settings.lock:
                    async with self.service.admission(
                        scope.generation, self.settings.owner, self.settings.epoch
                    ) as db:
                        current = await store.run(db, self.instance, identity)
                        self.require_owned(current)
                        owned = await store.attempt(db, current, attempt.attempt_id)
                        if (
                            current.fence != scope.cancel_epoch
                            or current.active_attempt_id != attempt.attempt_id
                            or owned.read_receipt_ref is not None
                            or name != "read_context"
                            or decode(arguments.encode()) != {}
                        ):
                            raise SendDenied("TOOL_AUTHORITY_DENIED")
                        context = await records.resolve(
                            db, self.instance, snapshot.context_ref, "run-context-v1"
                        )
                        await store.event(
                            db, current, "tool_called", "read_context", actor=owned, call_id=call_id
                        )
                        ref = await records.put(
                            db,
                            self.instance,
                            "run-tool-result-v1",
                            {
                                "run_id": identity,
                                "task_id": owned.task_id,
                                "attempt_id": owned.attempt_id,
                                "call_id": call_id,
                                "context_ref": snapshot.context_ref.model_dump(mode="json"),
                                "context": context,
                            },
                        )
                        output = json.dumps(
                            {"ref": ref.model_dump(mode="json"), "context": context},
                            ensure_ascii=False,
                            separators=(",", ":"),
                        )
                        await store.save_attempt(
                            db,
                            owned.model_copy(
                                update={
                                    "read_receipt_ref": ref,
                                    "call_id": call_id,
                                    "tool_arguments": arguments,
                                    "tool_output": output,
                                }
                            ),
                        )
                        cursor = await store.event(
                            db,
                            current,
                            "tool_result",
                            "Selected inert context read",
                            actor=owned,
                            refs=[ref],
                            call_id=call_id,
                        )
                        await store.save_run(
                            db,
                            current.model_copy(
                                update={"through_cursor": cursor, "revision": current.revision + 1}
                            ),
                        )
                return output

            reason = None
            result = None
            cancelled = False

            def guard(*, scope: Scope = scope) -> AbstractAsyncContextManager[Authority]:
                return self.write_guard(identity, scope)

            try:
                async with asyncio.timeout_at(expires_at):
                    secret = await asyncio.to_thread(
                        self.settings.vault.get, config.connection.credential(self.instance)
                    )
                    result = await self.runner.run(
                        step,
                        secret,
                        guard,
                        tool,
                        observe,
                        sent,
                    )
            except asyncio.CancelledError:
                reason, cancelled = "CANCELLED", True
            except SendDenied as error:
                reason = (
                    str(error) if str(error).startswith("PROVIDER_") else "MODEL_RESPONSE_UNKNOWN"
                )
            except (ValueError, OSError, TimeoutError):
                reason = "MODEL_RESPONSE_UNKNOWN"
            finally:
                await self.model_owner.retire_relay()
            async with self.settings.lock:
                try:
                    async with self.service.admission(
                        scope.generation, self.settings.owner, self.settings.epoch
                    ) as db:
                        again = await self.finish_step(
                            db, identity, attempt.attempt_id, scope, result, reason, admitted=True
                        )
                except ControlConflict:
                    async with self.service.engine.begin() as db:
                        again = await self.finish_step(
                            db, identity, attempt.attempt_id, scope, result, reason, admitted=False
                        )
            if cancelled or not again:
                return

    async def finish_step(
        self,
        db: AsyncConnection,
        identity: str,
        attempt_id: str,
        scope: Scope,
        result: StepResult | None,
        reason: str | None,
        *,
        admitted: bool,
    ) -> bool:
        current = await store.run(db, self.instance, identity)
        owned = await store.attempt(db, current, attempt_id)
        authorized = (
            admitted
            and not self.closing
            and not self.draining
            and current.state == "RUNNING"
            and current.fence == scope.cancel_epoch
            and current.owner_id == str(self.settings.owner)
            and current.owner_epoch == self.settings.epoch
            and current.active_attempt_id == attempt_id
        )
        settled = await db.scalar(
            text(
                "UPDATE run_dispatch SET state=CASE WHEN state='RESERVED' THEN 'RELEASED' ELSE :state END WHERE instance_id=:instance AND dispatch_id=:id AND state IN ('RESERVED','SENT') RETURNING state"
            ),
            {
                "instance": self.instance,
                "id": scope.id,
                "state": "UNKNOWN" if reason else "SETTLED",
            },
        )
        if isinstance(settled, str):
            await store.dispatch_event(db, self.instance, scope.id, settled)
        if not authorized:
            if result is not None:
                await records.put(
                    db,
                    self.instance,
                    "run-late-response-v1",
                    {
                        "dispatch_id": scope.id,
                        "attempt_id": attempt_id,
                        "result": result.model_dump(mode="json"),
                    },
                )
            reason = "OWNER_LOST" if not admitted else "CANCELLED"
            if current.state == "RUNNING":
                current = current.model_copy(
                    update={
                        "state": "NEEDS_RECONCILIATION",
                        "reason": reason,
                        "fence": current.fence + 1,
                    }
                )
        if reason is not None:
            await self.complete(db, current, owned, None, reason)
            return False
        assert result is not None
        if result.kind == "tool":
            return True
        try:
            async with db.begin_nested():
                await self.complete(db, current, owned, result.text, None)
        except ValueError:
            await self.complete(db, current, owned, None, "FINALIZATION_DENIED")
            return False
        return True

    async def complete(
        self,
        db: AsyncConnection,
        run: RunView,
        attempt: Attempt,
        output: str | None,
        reason: str | None,
    ) -> None:
        if attempt.state != "RUNNING":
            return
        snapshot = await store.setup(db, self.instance, run.setup_ref)
        if attempt.role == "BRAIN" and reason is None and output is not None:
            decision = BrainDecision.model_validate_json(output)
            if len(decision.consumed_refs) != len(attempt.input_refs) or {
                ref.model_dump_json() for ref in decision.consumed_refs
            } != {ref.model_dump_json() for ref in attempt.input_refs}:
                raise records.ModelConflict("CONSUMPTION_CONTEXT_DENIED")
            reference = await records.put(
                db, self.instance, "run-decision-v1", decision.model_dump(mode="json")
            )
            await store.consume(db, run, decision.consumed_refs, reference)
            question = await store.question(db, run)
            if question is not None and question.state == "ANSWER_ADMITTED":
                if question.answer_ref not in decision.consumed_refs:
                    raise records.ModelConflict("CONSUMPTION_DENIED")
                await store.save_question(
                    db, run, question.model_copy(update={"state": "CONSUMED"})
                )
            await store.save_attempt(
                db,
                attempt.model_copy(
                    update={
                        "state": "SUCCEEDED",
                        "result_ref": reference,
                        "result_summary": decision.summary,
                    }
                ),
            )
            run = run.model_copy(
                update={
                    "active_attempt_id": None,
                    "stagnation": 0 if decision.consumed_refs else min(3, run.stagnation + 1),
                }
            )
            if decision.action == "delegate":
                run = await self.new_attempt(
                    db, run, snapshot, role="RECON", brief=decision.detail, parent=attempt.task_id
                )
            elif decision.action == "ask":
                question = Question(
                    question_id=str(uuid4()),
                    run_id=run.run_id,
                    task_id=attempt.task_id,
                    revision=run.revision + 1,
                    cause=decision.summary,
                    text=decision.detail,
                    refs=decision.consumed_refs,
                    state="PENDING",
                )
                await store.save_question(db, run, question, initial=True)
                run = run.model_copy(update={"question_id": question.question_id})
            else:
                run = run.model_copy(
                    update={"state": "LIMITED", "reason": "S1_INERT_ONLY_NO_ASSESSMENT"}
                )
            if run.stagnation >= 3:
                run = run.model_copy(update={"state": "LIMITED", "reason": "STAGNATION"})
            cursor = await store.event(
                db, run, "decision", decision.summary, actor=attempt, refs=[reference]
            )
        else:
            kind = "cancel" if reason == "CANCELLED" else "error" if reason else "direct"
            final = (
                WorkerFinal.model_validate_json(output)
                if output is not None and reason is None
                else None
            )
            valid = (
                attempt.read_receipt_ref is not None
                and final is not None
                and attempt.read_receipt_ref in final.consumed_refs
            )
            if final is not None and (
                any(
                    ref not in [attempt.read_receipt_ref, snapshot.context_ref]
                    for ref in final.consumed_refs
                )
                or final.gaps
            ):
                valid = False
            state = completion_status(kind, valid)
            if not valid and kind == "direct" and attempt.correction_count == 0:
                await store.save_attempt(
                    db,
                    attempt.model_copy(
                        update={
                            "correction_count": 1,
                            "input_text": attempt.input_text
                            + "\nSelf-review once: return JSON summary, consumed_refs from the stored tool result, and gaps. Do not claim unexecuted work.",
                        }
                    ),
                )
                return
            payload: dict[str, object] = {
                "run_id": run.run_id,
                "task_id": attempt.task_id,
                "attempt_id": attempt.attempt_id,
                "state": state,
                "summary": final.summary if final else reason,
                "consumed_refs": [r.model_dump(mode="json") for r in final.consumed_refs]
                if final
                else [],
                "gaps": (final.gaps + ([] if valid else ["INERT_READ_PROOF_INCOMPLETE"]))
                if final
                else [reason],
            }
            reference = await records.put(db, self.instance, "run-result-v1", payload)
            await store.save_attempt(
                db,
                attempt.model_copy(
                    update={
                        "state": state,
                        "result_ref": reference,
                        "result_summary": final.summary if final else reason,
                    }
                ),
            )
            await store.add_inbox(db, run, reference)
            run = run.model_copy(update={"active_attempt_id": None})
            if run.state == "RUNNING":
                if reason is not None:
                    run = run.model_copy(
                        update={
                            "state": "NEEDS_RECONCILIATION"
                            if reason == "MODEL_RESPONSE_UNKNOWN"
                            else "HOLD",
                            "reason": reason,
                            "fence": run.fence + 1,
                        }
                    )
                else:
                    # TxA ends here; the next owned step creates Brain from the committed inbox.
                    run = run.model_copy(update={"reason": "RESULT_READY"})
            cursor = await store.event(
                db,
                run,
                "result",
                final.summary if final else reason or "Incomplete",
                actor=attempt,
                refs=[reference],
            )
        await store.save_run(
            db, run.model_copy(update={"revision": run.revision + 1, "through_cursor": cursor})
        )

    async def drain_run(self, identity: str) -> None:
        self.continuations.discard(identity)
        task = self.tasks.get(identity)
        if task is not None:
            task.cancel()
            done, pending = await asyncio.wait({task}, timeout=1.5)
            if pending:
                self.failed = True
                return
        await self.model_owner.retire_relay()
        async with self.service.engine.begin() as db:
            run = await store.run(db, self.instance, identity)
            if run.active_attempt_id is not None:
                active = await store.attempt(db, run, run.active_attempt_id)
                if active.state == "RUNNING":
                    await self.complete(db, run, active, None, "CANCELLED")
                    run = await store.run(db, self.instance, identity)
            if run.state in {"PAUSING", "STOPPING"}:
                await store.save_run(
                    db,
                    run.model_copy(
                        update={
                            "state": "NEEDS_RECONCILIATION"
                            if self.failed
                            else "PAUSED"
                            if run.state == "PAUSING"
                            else "STOPPED",
                            "revision": run.revision + 1,
                        }
                    ),
                )

    async def drain(self) -> bool:
        self.closing = True
        return await self.drain_models()

    async def drain_models(self) -> bool:
        async with self.drain_lock:
            async with self.settings.lock:
                self.draining = True
            try:
                return await self._drain_models()
            finally:
                async with self.settings.lock:
                    self.draining = False

    async def _drain_models(self) -> bool:
        async with self.service.engine.begin() as db:
            ids = (
                (
                    await db.execute(
                        text(
                            "SELECT run_id::text FROM agent_run WHERE instance_id=:instance AND state NOT IN ('STOPPED','COMPLETED','LIMITED') FOR UPDATE"
                        ),
                        {"instance": self.instance},
                    )
                )
                .scalars()
                .all()
            )
            for identity in ids:
                run = await store.run(db, self.instance, identity)
                await store.save_run(
                    db,
                    run.model_copy(
                        update={
                            "state": "STOPPING",
                            "fence": run.fence + 1,
                            "revision": run.revision + 1,
                        }
                    ),
                )
        for identity in ids:
            await self.drain_run(identity)
        return not self.failed

    async def recover(self) -> None:
        await self.model_owner.retire_relay(recovery=True)
        async with self.service.engine.begin() as db:
            dispatches = (
                await db.execute(
                    text(
                        "UPDATE run_dispatch SET state=CASE WHEN state='RESERVED' THEN 'RELEASED' ELSE 'UNKNOWN' END WHERE instance_id=:instance AND state IN ('SENT','RESERVED') RETURNING dispatch_id::text,state"
                    ),
                    {"instance": self.instance},
                )
            ).all()
            for dispatch_id, dispatch_state in dispatches:
                await store.dispatch_event(db, self.instance, dispatch_id, dispatch_state)
            ids = (
                (
                    await db.execute(
                        text(
                            "SELECT run_id::text FROM agent_run WHERE instance_id=:instance AND state NOT IN ('STOPPED','COMPLETED','LIMITED') FOR UPDATE"
                        ),
                        {"instance": self.instance},
                    )
                )
                .scalars()
                .all()
            )
            for identity in ids:
                run = await store.run(db, self.instance, identity)
                await store.save_run(
                    db,
                    run.model_copy(
                        update={
                            "state": "NEEDS_RECONCILIATION",
                            "reason": "OWNER_LOST",
                            "fence": run.fence + 1,
                            "revision": run.revision + 1,
                        }
                    ),
                )
                retained = await store.run(db, self.instance, identity)
                if retained.active_attempt_id is not None:
                    attempt = await store.attempt(db, retained, retained.active_attempt_id)
                    await self.complete(db, retained, attempt, None, "OWNER_LOST")
