"""Opt-in S1 live QA; SOURCE controls are not provider or persistence evidence.

Live admission additionally requires a verified total provider cap for the exact QA
key. max_price subtotal arithmetic alone does not prove all fees/cache/reasoning.
"""

import asyncio
import importlib
import json
import os
from collections.abc import AsyncIterable, AsyncIterator, Awaitable, Callable
from contextlib import AbstractAsyncContextManager, AsyncExitStack, asynccontextmanager, suppress
from contextvars import ContextVar
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import httpcore
import httpx
import pytest
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncEngine

from omnis.core.db import database_engine
from omnis.modules.instance.service import InstanceService
from omnis.modules.runs import run_store
from omnis.modules.runs.model_test_runtime import ApiKeyModelTest
from omnis.modules.runs.model_test_store import ModelConflict
from omnis.modules.runs.run_contract import Preflight, RunControl, StartRun
from omnis.modules.runs.run_runtime import AgentRunOwner
from omnis.modules.settings.catalog_models import ExactRef
from omnis.modules.settings.catalog_publication import PublicationCatalog
from omnis.modules.settings.provider_key_models import KeySettingsControl
from omnis.modules.settings.provider_key_service import ProviderSettingsOwner
from omnis.modules.settings.provider_model_models import ModelRegistryControl
from omnis.modules.settings.provider_vault import ProviderVault
from omnis.modules.tasks.agent_composition import compose_publication
from omnis.supervisor import agent_runner
from omnis.supervisor.agent_runner import AgentStep, Exchange, StepInput, StepResult
from omnis.supervisor.model_relay_protocol import Authority
from omnis.supervisor.model_sender import CURRENT, ModelSender, Permit, SendDenied
from omnis.transport.local_control import LocalControl
from test_agent_core_publication import publish_core
from test_agent_core_publication import storage_seam as storage_seam

MODEL = "deepseek/deepseek-v4.1-flash"
CONTEXT = "Read this synthetic non-secret context with Recon; report its stored read reference to Brain. No targets."


def routing() -> dict[str, object]:
    return {
        "allow_fallbacks": False,
        "require_parameters": True,
        "max_price": {"prompt": "0.05", "completion": "2", "request": "0.01"},
    }


def source_metadata() -> dict[str, object]:
    return {
        "id": MODEL,
        "context_length": 1048576,
        "top_provider": {"max_completion_tokens": 1024},
        "supported_parameters": ["tools", "structured_outputs", "response_format", "max_tokens"],
    }


@pytest.mark.parametrize(
    "change",
    [
        {"model": "other"},
        {"max_tokens": 1025},
        {"max_tokens": True},
        {"provider": {}},
        {"provider": {**routing(), "allow_fallbacks": 0}},
        {"provider": {**routing(), "require_parameters": False}},
        {
            "provider": {
                **routing(),
                "max_price": {"prompt": "0.06", "completion": "2", "request": "0.01"},
            }
        },
        {"plugins": [{"id": "web"}]},
        {"messages": [{"role": "user", "content": [{"type": "image_url"}]}]},
    ],
)
def test_live_body_mutations_denied(change: dict[str, object]) -> None:
    limit = LiveLimit()
    body: dict[str, object] = {
        "model": MODEL,
        "max_tokens": 1024,
        "provider": routing(),
        "messages": [{"role": "user", "content": CONTEXT}],
    }
    limit.validate_body(body)
    with pytest.raises(SendDenied, match="QA_BODY_DENIED"):
        limit.validate_body(body | change)


@pytest.mark.parametrize(
    "change",
    [
        {"id": "other"},
        {"context_length": 2000001},
        {"context_length": True},
        {"context_length": None},
        {"supported_parameters": ["max_tokens"]},
        {"top_provider": {"max_completion_tokens": 1023}},
    ],
)
def test_live_metadata_denied(change: dict[str, object]) -> None:
    limit = LiveLimit()
    limit.metadata(source_metadata())
    with pytest.raises(SendDenied, match="QA_METADATA_REQUIRED"):
        limit.metadata(source_metadata() | change)


@pytest.mark.asyncio
async def test_live_invalid_metadata_cannot_retain_success() -> None:
    limit = LiveLimit()
    limit.metadata(source_metadata())
    with pytest.raises(SendDenied, match="QA_METADATA_REQUIRED"):
        limit.metadata(None)
    with pytest.raises(SendDenied, match="QA_METADATA_REQUIRED"):
        limit.start()


class LiveLimit:
    """One test invocation, never a product MONITOR policy."""

    def __init__(self) -> None:
        self.calls = 0
        self.metadata_count = 0
        self.reserved_subtotal = Decimal(0)
        # Provider max_price uses USD/M tokens and USD/request, not observed min pricing.
        self.per_call = 2 * Decimal("0.05") + Decimal(1024) / 1_000_000 * 2 + Decimal("0.01")
        self.deadline: float | None = None

    def install(self, patch: pytest.MonkeyPatch, sender: ModelSender, runner: AgentStep) -> None:
        original_run, original_validate = runner.run, sender.transport.validate_request
        original_metadata = sender.metadata_page
        active: ContextVar[StepInput | None] = ContextVar("s1-live-step", default=None)
        patch.setattr(agent_runner, "ROUTING", routing())

        async def validate(request: httpx.Request) -> bytes:
            raw = await original_validate(request)
            permit = CURRENT.get()
            if permit.body is None:
                if self.deadline is not None or not permit.url.startswith(
                    "https://openrouter.ai/api/v1/models"
                ):
                    raise SendDenied("QA_METADATA_DENIED")
            else:
                self.check_deadline()
                step = active.get()
                if step is None or step.provider != "openrouter" or permit.response_limit != 131072:
                    raise SendDenied("QA_UNCOUNTED_DISPATCH")
                self.validate_body(permit.body)
            return raw

        async def metadata_page(
            endpoint: str,
            secret: str,
            guard: Callable[[], AbstractAsyncContextManager[Authority]],
            offset: int | None = None,
            remaining_bytes: int = 2097152,
        ) -> tuple[object, int]:
            if offset == 0:
                self.metadata_count = 0
            try:
                raw, size = await original_metadata(
                    endpoint, secret, guard, offset, remaining_bytes
                )
            except (ValueError, OSError, TimeoutError, asyncio.CancelledError):
                self.metadata_count = 0
                raise
            entries = raw.get("data") if isinstance(raw, dict) else None
            if not isinstance(entries, list):
                self.metadata_count = 0
                raise SendDenied("QA_METADATA_REQUIRED")
            for entry in entries:
                if isinstance(entry, dict) and entry.get("id") == MODEL:
                    self.metadata(entry)
            return raw, size

        async def run(
            step: StepInput,
            secret: str,
            guard: Callable[[], AbstractAsyncContextManager[Authority]],
            tool: Callable[[str, str, str], Awaitable[str]],
            observe: Callable[[bytes], Awaitable[None]],
            sent: Callable[[], Awaitable[None]],
            *,
            check_data: Callable[[object], Awaitable[None]] | None = None,
        ) -> StepResult:
            self.check_deadline()
            if self.metadata_count != 1 or step.provider != "openrouter":
                raise SendDenied("QA_METADATA_REQUIRED")
            self.validate_body(runner.projection(step))

            @asynccontextmanager
            async def bounded_guard() -> AsyncIterator[Authority]:
                self.check_deadline()
                async with guard() as authority:
                    self.check_deadline()
                    yield authority

            async def bounded_sent() -> None:
                # No await before reservation; uncertain SENT/transport failures never refund.
                self.reserve()
                await sent()

            token = active.set(step)
            try:
                async with asyncio.timeout_at(self.deadline):
                    return await original_run(
                        step,
                        secret,
                        bounded_guard,
                        tool,
                        observe,
                        bounded_sent,
                        check_data=check_data,
                    )
            finally:
                active.reset(token)

        patch.setattr(sender.transport, "validate_request", validate)
        patch.setattr(sender, "metadata_page", metadata_page)
        patch.setattr(runner, "run", run)

    def start(self) -> None:
        if self.metadata_count != 1:
            raise SendDenied("QA_METADATA_REQUIRED")
        if self.deadline is None:
            self.deadline = asyncio.get_running_loop().time() + 900

    def validate_body(self, body: dict[str, object]) -> None:
        messages = body.get("messages")
        if (
            body.get("model") != MODEL
            or type(body.get("max_tokens")) is not int
            or body["max_tokens"] != 1024
            or json.dumps(body.get("provider"), sort_keys=True)
            != json.dumps(routing(), sort_keys=True)
            or set(body)
            - {
                "model",
                "max_tokens",
                "provider",
                "messages",
                "parallel_tool_calls",
                "store",
                "tools",
                "response_format",
            }
            or not isinstance(messages, list)
            or not messages
            or any(
                not isinstance(m, dict)
                or not (
                    isinstance(m.get("content"), str)
                    or (m.get("role") == "assistant" and m.get("content") is None)
                )
                for m in messages
            )
        ):
            raise SendDenied("QA_BODY_DENIED")

    def metadata(self, model: object) -> None:
        if not isinstance(model, dict):
            self.metadata_count = 0
            raise SendDenied("QA_METADATA_REQUIRED")
        context = model.get("context_length")
        top = model.get("top_provider")
        cap = top.get("max_completion_tokens") if isinstance(top, dict) else None
        params = model.get("supported_parameters")
        if (
            model.get("id") != MODEL
            or type(context) is not int
            or not 1 <= context <= 2_000_000
            or type(cap) is not int
            or cap < 1024
            or not isinstance(params, list)
            or not all(
                p in params
                for p in ("tools", "structured_outputs", "response_format", "max_tokens")
            )
        ):
            self.metadata_count = 0
            raise SendDenied("QA_METADATA_REQUIRED")
        self.metadata_count += 1

    def check_deadline(self) -> None:
        if self.deadline is None or asyncio.get_running_loop().time() >= self.deadline:
            raise SendDenied("QA_DEADLINE")

    def reserve(self) -> None:
        self.check_deadline()
        if self.calls >= 8:
            raise SendDenied("QA_CALL_LIMIT")
        if not self.reserved_subtotal.is_finite() or self.reserved_subtotal + self.per_call > 1:
            raise SendDenied("QA_COST_LIMIT")
        self.calls += 1
        self.reserved_subtotal += self.per_call


@pytest.mark.asyncio
async def test_live_sdk_sent_guard_no_io(
    monkeypatch: pytest.MonkeyPatch, storage_seam: AsyncEngine, tmp_path: Path
) -> None:
    sender = ModelSender(Path("/nonexistent-s1-live-source"))
    runner = AgentStep(sender.transport)
    limit = LiveLimit()
    limit.install(monkeypatch, sender, runner)
    limit.metadata(source_metadata())
    limit.start()
    wire: list[bytes] = []
    admitted: list[str] = []

    @asynccontextmanager
    async def guard() -> AsyncIterator[Authority]:
        admitted.append("guard")
        yield object.__new__(Authority)  # SOURCE guard invocation, not relay authority proof.

    async def sent() -> None:
        admitted.append("sent")

    async def observed(raw: bytes) -> None:
        raise AssertionError("No response in serialization-only SOURCE")

    async def tool(name: str, arguments: str, call: str) -> str:
        raise AssertionError("No scripted model/tool response")

    async def no_io(request: httpcore.Request) -> httpcore.Response:
        assert isinstance(request.stream, AsyncIterable)
        raw = b"".join([part async for part in request.stream])
        async with CURRENT.get().guard():
            wire.append(raw)
        raise SendDenied("SOURCE_NO_IO")

    monkeypatch.setattr(sender.transport.pool, "handle_async_request", no_io)
    catalog, owner, publication = await publish_core(storage_seam, tmp_path / "catalog")
    reference = {
        "instance_id": str(uuid4()),
        "id": str(uuid4()),
        "kind": "run-context-v1",
        "digest": "a" * 64,
    }
    content = json.dumps(
        {
            "brief": "Propose the first inert task; cite and consume every supplied inbox ref.",
            "context_ref": reference,
            "inbox": [],
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
    steps: list[StepInput] = []
    async with storage_seam.begin() as db:
        for role in ("BRAIN", "RECON"):
            composition = await compose_publication(
                catalog,
                db,
                owner,
                ExactRef.model_validate(publication),
                role=role,
                brief="S1 inert only. Read the operator-selected synthetic context. No target actions.",
            )
            steps.append(
                StepInput(
                    role=role,
                    model=MODEL,
                    output_tokens=1024,
                    provider="openrouter",
                    instructions=composition.text,
                    input_text=content,
                    history=[],
                )
            )
    steps.append(
        steps[1].model_copy(
            update={
                "history": [
                    Exchange(
                        call_id="source-read-1",
                        arguments="{}",
                        result=json.dumps(
                            {
                                "ref": {**reference, "kind": "run-tool-result-v1"},
                                "context": {
                                    "text": CONTEXT,
                                    "data_policy": "SELECTED_SYNTHETIC_ONLY",
                                },
                            },
                            ensure_ascii=False,
                            separators=(",", ":"),
                        ),
                    )
                ]
            }
        )
    )
    steps.append(
        steps[0].model_copy(
            update={
                "input_text": json.dumps(
                    {
                        "brief": "Consume every retained result ref and decide the next step.",
                        "context_ref": reference,
                        "inbox": [
                            {
                                "ref": {**reference, "kind": "run-result-v1"},
                                "result": {
                                    "run_id": str(uuid4()),
                                    "task_id": str(uuid4()),
                                    "attempt_id": str(uuid4()),
                                    "state": "SUCCEEDED",
                                    "completion_kind": "finish",
                                    "summary": "SOURCE sizing only",
                                    "consumed_refs": [{**reference, "kind": "run-tool-result-v1"}],
                                    "gaps": [],
                                },
                            }
                        ],
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
            }
        )
    )
    step = steps[0]
    try:
        for change in ({"model": "other"}, {"output_tokens": 1025}, {"provider": "orcarouter"}):
            with pytest.raises(SendDenied, match="QA_"):
                await runner.run(
                    step.model_copy(update=change),
                    "synthetic-not-a-key",
                    guard,
                    tool,
                    observed,
                    sent,
                )
        with monkeypatch.context() as mutation:
            mutation.setattr(agent_runner, "ROUTING", {**routing(), "allow_fallbacks": True})
            with pytest.raises(SendDenied, match="QA_BODY_DENIED"):
                await runner.run(step, "synthetic-not-a-key", guard, tool, observed, sent)
        assert not wire and not admitted and limit.calls == 0
        for index in range(8):
            step = steps[index % len(steps)]
            with pytest.raises(SendDenied, match="SOURCE_NO_IO"):
                await runner.run(step, "synthetic-not-a-key", guard, tool, observed, sent)
        with pytest.raises(SendDenied, match="QA_CALL_LIMIT"):
            await runner.run(step, "synthetic-not-a-key", guard, tool, observed, sent)
        assert limit.calls == len(wire) == admitted.count("sent") == admitted.count("guard") == 8
        assert all(json.loads(raw)["provider"] == routing() for raw in wire)
        assert max(map(len, wire)) <= 32768
        print(
            "S1_LIVE_SOURCE_SDK_SIZES",
            [len(raw) for raw in wire[:4]],
            "eight_call_routing_subtotal_usd",
            8 * limit.per_call,
        )
    finally:
        await sender.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "boundary", ["sent_failure", "guard_expired", "overall_timeout", "uncounted"]
)
async def test_live_boundaries_before_handoff(
    monkeypatch: pytest.MonkeyPatch, boundary: str
) -> None:
    sender = ModelSender(Path("/nonexistent-s1-live-source"))
    runner = AgentStep(sender.transport)
    limit = LiveLimit()
    limit.install(monkeypatch, sender, runner)
    limit.metadata(source_metadata())
    limit.start()
    entered: list[str] = []

    @asynccontextmanager
    async def guard() -> AsyncIterator[Authority]:
        entered.append("guard")
        if boundary == "guard_expired":
            limit.deadline = asyncio.get_running_loop().time() - 1
        yield object.__new__(Authority)

    async def sent() -> None:
        entered.append("sent")
        if boundary == "sent_failure":
            raise SendDenied("SOURCE_SENT_FAILURE")

    async def tool(name: str, arguments: str, call: str) -> str:
        raise AssertionError("No SOURCE model response")

    async def observe(raw: bytes) -> None:
        raise AssertionError("No SOURCE response")

    async def sink(request: httpcore.Request) -> httpcore.Response:
        async with CURRENT.get().guard():
            await asyncio.Event().wait()
        raise AssertionError("No SOURCE I/O")

    monkeypatch.setattr(sender.transport.pool, "handle_async_request", sink)
    step = StepInput(
        role="BRAIN",
        model=MODEL,
        output_tokens=1024,
        provider="openrouter",
        instructions="Synthetic",
        input_text=CONTEXT,
        history=[],
    )
    try:
        if boundary == "uncounted":
            body = runner.projection(step)
            token = CURRENT.set(
                Permit(
                    "https://openrouter.ai/api/v1/chat/completions",
                    body,
                    "synthetic",
                    guard,
                    131072,
                )
            )
            try:
                with pytest.raises(SendDenied, match="QA_UNCOUNTED_DISPATCH"):
                    await sender.transport.handle_async_request(
                        httpx.Request(
                            "POST",
                            CURRENT.get().url,
                            json=body,
                            headers={"Authorization": "Bearer synthetic"},
                        )
                    )
            finally:
                CURRENT.reset(token)
            assert not entered and limit.calls == 0
        else:
            if boundary == "overall_timeout":
                limit.deadline = asyncio.get_running_loop().time() + 0.1
            with pytest.raises(TimeoutError if boundary == "overall_timeout" else SendDenied):
                await runner.run(step, "synthetic-not-a-key", guard, tool, observe, sent)
            assert limit.calls == 1 and entered.count("sent") == 1
            assert entered.count("guard") == (0 if boundary == "sent_failure" else 1)
            deadline, spent = limit.deadline, limit.reserved_subtotal
            limit.start()
            assert (limit.deadline, limit.reserved_subtotal, limit.calls) == (deadline, spent, 1)
    finally:
        await sender.close()


@pytest.mark.asyncio
async def test_live_missing_metadata_and_overcost_denied() -> None:
    limit = LiveLimit()
    with pytest.raises(SendDenied, match="QA_METADATA_REQUIRED"):
        limit.start()
    limit.metadata(source_metadata())
    limit.start()
    limit.reserved_subtotal = Decimal("0.95")
    with pytest.raises(SendDenied, match="QA_COST_LIMIT"):
        limit.reserve()
    assert limit.calls == 0
    assert 8 * limit.per_call == Decimal("0.896384") < 1
    limit.metadata(source_metadata())
    with pytest.raises(SendDenied, match="QA_METADATA_REQUIRED"):
        limit.start()


@pytest.mark.asyncio
async def test_live_limit_eight_then_deny_without_refund() -> None:
    limit = LiveLimit()
    limit.metadata(source_metadata())
    limit.start()
    for _ in range(8):
        limit.reserve()
    with pytest.raises(SendDenied, match="QA_CALL_LIMIT"):
        limit.reserve()
    assert limit.calls == 8


@pytest.mark.asyncio
async def test_live_deadline_and_replay_never_reset() -> None:
    limit = LiveLimit()
    limit.metadata(source_metadata())
    limit.start()
    limit.reserve()
    first = limit.deadline
    limit.start()
    assert limit.deadline == first and limit.calls == 1
    limit.deadline = asyncio.get_running_loop().time() - 1
    with pytest.raises(SendDenied, match="QA_DEADLINE"):
        limit.reserve()
    assert limit.calls == 1
    assert Decimal(8) * (
        2 * Decimal("0.05") + Decimal(1024) / 1_000_000 * 2 + Decimal("0.01")
    ) == Decimal("0.896384")


@pytest.mark.skipif(
    os.environ.get("OMNIS_S1_LIVE_UI") != "1", reason="Explicit reviewed live S1 only"
)
@pytest.mark.asyncio
async def test_live_s1_ui_pg(migrated_database_url: URL, monkeypatch: pytest.MonkeyPatch) -> None:
    from test_web_e2e import settings_models_browser

    root = Path(os.environ["TMPDIR"]) / "s1-live"
    root.mkdir(mode=0o700)  # Exclusive: a new invocation never adopts a prior budget or vault.
    for name in ("vault", "key", "relay", "control", "catalog", "browser"):
        (root / name).mkdir(mode=0o700)
    assert len(bytes(root / "relay/model-egress.sock")) <= 107
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "cli/src"))
    start_relay = importlib.import_module("omnis_cli.forwarder").start_auth_forwarder
    engine = database_engine(migrated_database_url.render_as_string(hide_password=False))
    async with AsyncExitStack() as cleanup:
        cleanup.push_async_callback(engine.dispose)
        service = InstanceService(engine)
        owner = uuid4()
        epoch = await service.acquire(owner)
        cleanup.push_async_callback(service.release, owner, epoch)
        initial = await service.owned_status(owner, epoch)
        await service.open(uuid4(), initial.generation, owner, epoch)

        async def renew() -> None:
            while True:
                await asyncio.sleep(0.5)
                await service.heartbeat(owner, epoch)

        heartbeat = asyncio.create_task(renew())

        async def stop_heartbeat() -> None:
            heartbeat.cancel()
            with suppress(asyncio.CancelledError):
                await heartbeat

        cleanup.push_async_callback(stop_heartbeat)
        relay = await start_relay(root / "relay", model=True)

        async def close_relay() -> None:
            relay.close()
            await relay.wait_closed()

        cleanup.push_async_callback(close_relay)
        sender = ModelSender(root / "relay/model-egress.sock")
        cleanup.push_async_callback(sender.close)
        settings = ProviderSettingsOwner(
            service,
            owner,
            epoch,
            ProviderVault(root / "vault", root / "key", str(initial.instance_id)),
        )
        model = ApiKeyModelTest(settings, sender)
        runs = AgentRunOwner(model, PublicationCatalog(engine, root / "catalog"))
        limit = LiveLimit()
        limit.install(monkeypatch, sender, runs.runner)

        async def drain_models() -> bool:
            a = await runs.drain_models()
            b = await model.drain_models()
            return a and b

        async def drain_all() -> bool:
            try:
                a = await runs.drain()
            finally:
                try:
                    b = await model.drain_models()
                finally:
                    c = await settings.drain()
            return a and b and c

        async def cleanup_models() -> None:
            assert await drain_all(), "Live QA owner drain uncertain"

        settings.model_drain = drain_models
        service.runtime_drain = drain_all
        cleanup.push_async_callback(cleanup_models)
        control = await cleanup.enter_async_context(
            LocalControl(root / "control", service, owner, epoch)
        )

        async def provider_command(
            command: KeySettingsControl | ModelRegistryControl,
        ) -> dict[str, object]:
            return (await settings.handle(command)).model_dump(mode="json")

        control.provider_settings = provider_command
        control.provider_catalog = model.catalog_handle
        # No SETTINGS_TEST handler: manual Save/discovery/assignments only, never Save & connect.
        async with asyncio.timeout(600) as window:

            async def run_command(envelope: RunControl) -> dict[str, object]:
                try:
                    if isinstance(envelope.request, Preflight):
                        if envelope.request.synthetic_context != CONTEXT:
                            raise SendDenied("QA_SYNTHETIC_CONTEXT_REQUIRED")
                        limit.start()
                        limit.check_deadline()
                        window.reschedule(
                            limit.deadline
                        )  # Even preflight precedes Start; never reset.
                    if isinstance(envelope.request, StartRun):
                        limit.check_deadline()
                        async with engine.connect() as db:
                            snapshot = await run_store.setup(
                                db, runs.instance, envelope.request.setup_ref
                            )
                        for config in (snapshot.brain, snapshot.recon):
                            if (
                                config.connection.provider != "openrouter"
                                or config.choice.model != MODEL
                                or config.choice.output_tokens != 1024
                            ):
                                raise SendDenied("QA_BODY_DENIED")
                except SendDenied:
                    raise ModelConflict("DATA_DENIED") from None
                return await runs.handle(envelope)

            control.agent_run = run_command
            await settings_models_browser(
                migrated_database_url, root / "control", root / "browser", scenario="s1-live"
            )
        assert 0 < limit.calls <= 8 and limit.reserved_subtotal <= 1 and not runs.failed
        (root / "browser/qa-bounds.json").write_text(
            json.dumps(
                {
                    "calls_reserved": limit.calls,
                    "routing_subtotal_upper_usd": str(limit.reserved_subtotal),
                    "eight_call_routing_subtotal_usd": str(8 * limit.per_call),
                    "deadline_seconds": 900,
                    "total_usd_cap": "EXTERNAL_PROVIDER_KEY_PREREQUISITE_NOT_PROVED_BY_THIS_TEST",
                }
            )
        )
