"""Versioned S1 proposals and commands; model output carries no execution authority."""

from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Annotated, Literal, Self

from pydantic import BeforeValidator, Field, field_validator, model_validator

from omnis.modules.engagements.schemas import EngagementDraft
from omnis.modules.runs.model_test_contract import Ref
from omnis.modules.settings.catalog_models import ExactRef
from omnis.modules.settings.provider_key_models import (
    Identity,
    KeyDTO,
    ModelSelection,
    PositiveRevision,
    Revision,
    SelectionView,
    SelectionViewV2,
)
from omnis.modules.settings.provider_key_service import ConnectionRevision


def exact_ref_revision(value: object) -> object:
    fields = value.model_dump() if isinstance(value, Ref) else value
    if (
        not isinstance(fields, dict)
        or type(fields.get("revision")) is not int
        or fields["revision"] != 1
    ):
        raise ValueError("EXACT_REF_REQUIRED")
    return value


type RunRef = Annotated[Ref, BeforeValidator(exact_ref_revision)]


def completion_status(exit_kind: str, read_receipt: bool) -> str:
    if exit_kind == "cancel":
        return "CANCELLED"
    if exit_kind == "error":
        return "FAILED"
    if exit_kind not in {"direct", "finish"}:
        raise ValueError("FINALIZATION_DENIED")
    return "SUCCEEDED" if read_receipt else "INCONCLUSIVE"


class BrainDecision(KeyDTO):
    action: Literal["delegate", "ask", "finish"]
    summary: str = Field(min_length=1, max_length=256)
    consumed_refs: list[RunRef] = Field(max_length=32)
    detail: str = Field(min_length=1, max_length=1024)


class WorkerFinal(KeyDTO):
    summary: str = Field(min_length=1, max_length=256)
    consumed_refs: list[RunRef] = Field(max_length=32)
    gaps: list[str] = Field(max_length=16)

    @model_validator(mode="after")
    def distinct_refs(self) -> Self:
        if len({ref.model_dump_json() for ref in self.consumed_refs}) != len(self.consumed_refs):
            raise ValueError("DUPLICATE_CONSUMED_REF")
        return self


class Preflight(KeyDTO):
    command_id: Identity
    expected_generation: Revision
    engagement_id: Identity
    draft_ref: ExactRef
    selection_revision: PositiveRevision
    publication_ref: ExactRef
    synthetic_context: str = Field(min_length=1, max_length=1024)
    data_consent: Literal[True]

    @field_validator("data_consent", mode="before")
    @classmethod
    def exact_consent(cls, value: object) -> Literal[True]:
        if value is not True:
            raise ValueError("CONSENT_REQUIRED")
        return True

    @model_validator(mode="after")
    def bounded(self) -> Self:
        if self.draft_ref.kind != "engagement-revision" or "\x00" in self.synthetic_context:
            raise ValueError("PREFLIGHT_DENIED")
        if len(self.model_dump_json().encode()) > 3600:
            raise ValueError("COMMAND_LIMIT")
        return self


class StartRun(KeyDTO):
    command_id: Identity
    expected_generation: Revision
    expected_revision: Literal[1]
    setup_ref: RunRef

    @field_validator("expected_revision", mode="before")
    @classmethod
    def exact_revision(cls, value: object) -> int:
        if type(value) is not int or value != 1:
            raise ValueError("SETUP_REVISION_REQUIRED")
        return value


class RunControl(KeyDTO):
    op: Literal["agent_run"]
    request: Preflight | StartRun | RunCommand

    @model_validator(mode="after")
    def bounded(self) -> Self:
        if len(self.model_dump_json().encode()) > 3600:
            raise ValueError("COMMAND_LIMIT")
        return self


class RoleConfig(KeyDTO):
    choice: ModelSelection
    connection: ConnectionRevision
    capabilities_ref: RunRef


class Setup(KeyDTO):
    schema_version: Literal[1] = 1
    engagement_id: Identity
    draft_ref: ExactRef
    draft: EngagementDraft
    expected_generation: Revision
    selection_revision: PositiveRevision
    selection_snapshot: SelectionView | SelectionViewV2
    catalog_owner_id: Identity
    publication_ref: ExactRef
    context_ref: RunRef
    brain: RoleConfig
    recon: RoleConfig
    brain_instructions: str
    recon_instructions: str
    composition_refs: list[RunRef] = Field(min_length=2, max_length=2)
    data_policy: Literal["SELECTED_SYNTHETIC_ONLY"] = "SELECTED_SYNTHETIC_ONLY"

    @model_validator(mode="after")
    def selection_matches(self) -> Self:
        if self.selection_snapshot.revision != self.selection_revision:
            raise ValueError("SELECTION_REVISION_MISMATCH")
        return self


class RunView(KeyDTO):
    schema_version: Literal[1] = 1
    instance_id: Identity
    engagement_id: Identity
    run_id: Identity
    setup_ref: RunRef
    revision: PositiveRevision
    generation: Revision
    owner_id: Identity
    owner_epoch: PositiveRevision
    fence: PositiveRevision
    state: Literal[
        "RUNNING",
        "PAUSING",
        "PAUSED",
        "HOLD",
        "STOPPING",
        "STOPPED",
        "COMPLETED",
        "LIMITED",
        "NEEDS_RECONCILIATION",
    ]
    reason: str | None = Field(default=None, max_length=256)
    active_attempt_id: Identity | None = None
    question_id: Identity | None = None
    stagnation: int = Field(default=0, ge=0, le=3)
    through_cursor: Revision = 0


class Attempt(KeyDTO):
    instance_id: Identity
    run_id: Identity
    task_id: Identity
    attempt_id: Identity
    role: Literal["BRAIN", "RECON"]
    parent_task_id: Identity | None
    state: Literal[
        "RUNNING", "SUCCEEDED", "INCONCLUSIVE", "FAILED", "CANCELLED", "NEEDS_RECONCILIATION"
    ]
    brief: str = Field(min_length=1, max_length=1024)
    input_refs: list[RunRef] = Field(max_length=32)
    input_text: str
    instructions: str
    configured_model: str = Field(min_length=1, max_length=256)
    observed_model: str | None = Field(default=None, max_length=256)
    skill_refs: list[ExactRef] = Field(max_length=32)
    result_summary: str | None = Field(default=None, max_length=256)
    result_ref: RunRef | None = None
    read_receipt_ref: RunRef | None = None
    call_id: str | None = Field(default=None, max_length=128)
    tool_arguments: str | None = Field(default=None, max_length=128)
    tool_output: str | None = None
    correction_count: int = Field(default=0, ge=0, le=1)


class ResultRecord(KeyDTO):
    run_id: Identity
    task_id: Identity
    attempt_id: Identity
    state: Literal["SUCCEEDED", "INCONCLUSIVE", "FAILED", "CANCELLED"]
    completion_kind: Literal["direct", "finish", "error", "cancel"] | None = None
    summary: str | None = Field(max_length=256)
    consumed_refs: list[RunRef] = Field(max_length=32)
    gaps: list[str] = Field(max_length=17)


class DecisionRecord(KeyDTO):
    run_id: Identity
    task_id: Identity
    attempt_id: Identity
    completion_kind: Literal["direct"]
    decision: BrainDecision


class InboxConsumption(KeyDTO):
    held: bool
    decision_ref: RunRef | None
    consumer_attempt_id: Identity | None


type TokenCount = Annotated[int, Field(strict=True, ge=0, le=9007199254740991)]


def usage_cost(value: object) -> str | None:
    # Same Decimal/nonnegative evidence rule as T1; bound numeric expansion, not spending.
    if type(value) not in (int, float, str):
        return None
    source = str(value)
    if len(source) > 128 or not re.fullmatch(r"[0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?", source):
        return None
    try:
        amount = Decimal(source)
    except InvalidOperation:
        return None
    if not amount.is_finite() or amount < 0 or abs(amount.adjusted()) > 100:
        return None
    normalized = format(amount, "f")
    return normalized if len(normalized) <= 128 else None


class InputTokenDetails(KeyDTO):
    cached_tokens: TokenCount | None = None


class OutputTokenDetails(KeyDTO):
    reasoning_tokens: TokenCount | None = None


class ReportedUsage(KeyDTO):
    prompt_tokens: TokenCount | None = None
    completion_tokens: TokenCount | None = None
    total_tokens: TokenCount | None = None
    input_tokens: TokenCount | None = None
    output_tokens: TokenCount | None = None
    cached_tokens: TokenCount | None = None
    reasoning_tokens: TokenCount | None = None
    cache_read_input_tokens: TokenCount | None = None
    cache_creation_input_tokens: TokenCount | None = None
    prompt_tokens_details: InputTokenDetails | None = None
    completion_tokens_details: OutputTokenDetails | None = None
    cost: int | float | str | None = None

    @field_validator("cost")
    @classmethod
    def finite_cost(cls, value: int | float | str | None) -> int | float | str | None:
        if value is not None and usage_cost(value) is None:
            raise ValueError("USAGE_INVALID")
        return value


class UsageMeasures(KeyDTO):
    input_tokens: TokenCount | None = None
    output_tokens: TokenCount | None = None
    total_tokens: TokenCount | None = None
    cached_tokens: TokenCount | None = None
    reasoning_tokens: TokenCount | None = None
    cache_creation_tokens: TokenCount | None = None
    cost_observed: str | None = Field(default=None, max_length=128)

    @field_validator("cost_observed")
    @classmethod
    def finite_cost(cls, value: str | None) -> str | None:
        if value is not None and usage_cost(value) is None:
            raise ValueError("USAGE_INVALID")
        return value


class UsageObservation(KeyDTO):
    reported: ReportedUsage
    measures: UsageMeasures
    observed_model: str | None = Field(default=None, max_length=256, pattern=r"^[!-~]+$")


def usage_observation(response: object) -> UsageObservation:
    response = response if isinstance(response, dict) else {}
    raw = response.get("usage")
    source = raw if isinstance(raw, dict) else {}
    fields: dict[str, object] = {}
    for name in ReportedUsage.model_fields:
        value = source.get(name)
        if name in {"prompt_tokens_details", "completion_tokens_details"}:
            key = "cached_tokens" if name == "prompt_tokens_details" else "reasoning_tokens"
            count = value.get(key) if isinstance(value, dict) else None
            fields[name] = {
                key: count if type(count) is int and 0 <= count <= 9007199254740991 else None
            }
        elif name == "cost":
            fields[name] = value if usage_cost(value) is not None else None
        else:
            fields[name] = value if type(value) is int and 0 <= value <= 9007199254740991 else None
    reported = ReportedUsage.model_validate(fields)

    def agreed(*values: int | None) -> int | None:
        known = {v for v in values if v is not None}
        return known.pop() if len(known) == 1 else None

    incoming = agreed(reported.prompt_tokens, reported.input_tokens)
    outgoing = agreed(reported.completion_tokens, reported.output_tokens)
    total = (
        incoming + outgoing
        if incoming is not None and outgoing is not None
        else reported.total_tokens
    )
    if total is not None and (
        total > 9007199254740991 or reported.total_tokens not in (None, total)
    ):
        total = None
    model = response.get("model")
    return UsageObservation(
        reported=reported,
        measures=UsageMeasures(
            input_tokens=incoming,
            output_tokens=outgoing,
            total_tokens=total,
            cached_tokens=agreed(
                reported.cached_tokens,
                reported.cache_read_input_tokens,
                reported.prompt_tokens_details.cached_tokens
                if reported.prompt_tokens_details
                else None,
            ),
            reasoning_tokens=agreed(
                reported.reasoning_tokens,
                reported.completion_tokens_details.reasoning_tokens
                if reported.completion_tokens_details
                else None,
            ),
            cache_creation_tokens=reported.cache_creation_input_tokens,
            cost_observed=usage_cost(reported.cost),
        ),
        observed_model=model
        if isinstance(model, str) and 1 <= len(model) <= 256 and re.fullmatch(r"[!-~]+", model)
        else None,
    )


class UsageRecord(UsageObservation):
    instance_id: Identity
    run_id: Identity
    task_id: Identity
    attempt_id: Identity
    dispatch_id: Identity
    role: Literal["BRAIN", "RECON"]
    configured_model: str = Field(min_length=1, max_length=256)
    connection_id: Identity
    connection_revision: PositiveRevision
    observed_at: datetime


class UsageSubtotal(KeyDTO):
    value: str | None = Field(max_length=256, pattern=r"^[0-9]+(?:\.[0-9]+)?$")
    observed_dispatches: Revision
    state: Literal["OBSERVED", "PARTIAL", "UNKNOWN"]


class UsageTotals(KeyDTO):
    dispatches: Revision
    unobserved_dispatches: Revision
    input_tokens: UsageSubtotal
    output_tokens: UsageSubtotal
    total_tokens: UsageSubtotal
    cached_tokens: UsageSubtotal
    reasoning_tokens: UsageSubtotal
    cache_creation_tokens: UsageSubtotal
    cost_observed: UsageSubtotal


class RoleUsage(KeyDTO):
    role: Literal["BRAIN", "RECON"]
    configured_model: str = Field(min_length=1, max_length=256)
    connection_id: Identity
    connection_revision: PositiveRevision
    totals: UsageTotals


class UsageSummary(KeyDTO):
    scope: Literal["RUN", "ATTEMPT"]
    accounting_policy: Literal["MONITOR"] = "MONITOR"
    totals: UsageTotals
    roles: list[RoleUsage] = Field(max_length=2)


class DispatchUsage(KeyDTO):
    dispatch_id: Identity
    state: Literal["RESERVED", "SENT", "SETTLED", "RELEASED", "UNKNOWN"]
    usage_ref: RunRef | None
    usage: UsageRecord | None
    reserved_at: datetime | None
    sent_at: datetime | None
    settled_at: datetime | None


class AttemptInspection(Attempt):
    result: ResultRecord | None = None
    decision: BrainDecision | None = None
    decision_completion_kind: Literal["direct"] | None = None
    consumption: InboxConsumption | None = None
    usage: UsageSummary | None = None
    dispatches: list[DispatchUsage] = Field(default_factory=list, max_length=20)
    dispatches_has_more: bool = False
    as_of: datetime


class Question(KeyDTO):
    question_id: Identity
    run_id: Identity
    task_id: Identity
    revision: PositiveRevision
    kind: Literal["CLARIFICATION"] = "CLARIFICATION"
    cause: str = Field(min_length=1, max_length=256)
    text: str = Field(min_length=1, max_length=1024)
    refs: list[RunRef] = Field(max_length=32)
    state: Literal["PENDING", "ANSWER_ADMITTED", "CONSUMED"]
    answer_ref: RunRef | None = None
    command_id: Identity | None = None


class CommandReceipt(KeyDTO):
    command_id: Identity
    setup_ref: RunRef | None = None
    run_id: Identity | None = None
    revision: PositiveRevision
    state: Literal["READY", "ADMITTED"]


class RunMetrics(KeyDTO):
    started_at: datetime | None
    finished_at: datetime | None
    agents: Revision
    attempts: Revision
    failed_attempts: Revision
    sent: Revision
    reserved: Revision
    released: Revision
    inflight: Revision
    settled: Revision
    unknown: Revision


type AgentIdentity = Annotated[
    str,
    Field(
        strict=True,
        max_length=36,
        pattern=r"^(brain|[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12})$",
    ),
]


class AgentRow(KeyDTO):
    agent_id: AgentIdentity
    role: Literal["BRAIN", "RECON"]
    parent_agent_id: AgentIdentity | None
    attempt_id: Identity
    state: Literal[
        "RUNNING", "SUCCEEDED", "INCONCLUSIVE", "FAILED", "CANCELLED", "NEEDS_RECONCILIATION"
    ]
    brief: str = Field(min_length=1, max_length=1024)
    attempts: PositiveRevision


class AgentPage(KeyDTO):
    run_id: Identity
    revision: PositiveRevision
    agents: list[AgentRow] = Field(max_length=50)
    has_more: bool
    next_after: str | None = Field(max_length=128)
    as_of: datetime


class RunSummary(KeyDTO):
    metrics: RunMetrics
    usage: UsageSummary
    run: RunView
    owner_live: bool
    phase_active: bool
    question: Question | None
    attempts: list[Attempt] = Field(max_length=50)
    has_more: bool
    as_of: datetime


class RunEvent(KeyDTO):
    event_id: Identity
    run_id: Identity
    task_id: Identity | None
    attempt_id: Identity | None
    sequence: PositiveRevision
    kind: Literal[
        "started",
        "decision",
        "tool_called",
        "tool_result",
        "result",
        "control",
        "question",
        "answer",
    ]
    summary: str = Field(min_length=1, max_length=256)
    refs: list[RunRef] = Field(max_length=32)
    call_id: str | None
    created_at: datetime


class EventPage(KeyDTO):
    run_id: Identity
    through_cursor: Revision
    events: list[RunEvent] = Field(max_length=50)
    has_more: bool
    as_of: datetime


class AgentEvent(RunEvent):
    pairing: Literal["MATCHED", "PENDING", "UNMATCHED", "NOT_APPLICABLE"]
    paired_sequence: PositiveRevision | None


class AgentHistory(KeyDTO):
    run_id: Identity
    agent_id: AgentIdentity
    through_cursor: Revision
    events: list[AgentEvent] = Field(max_length=50)
    has_more: bool
    as_of: datetime


class RunCommand(KeyDTO):
    action: Literal["pause", "stop", "resume", "answer"]
    command_id: Identity
    expected_generation: Revision
    expected_revision: PositiveRevision
    run_id: Identity
    question_id: Identity | None = None
    answer: str | None = Field(default=None, min_length=1, max_length=2048, repr=False)

    @model_validator(mode="after")
    def bounded(self) -> Self:
        if (self.action == "answer") != (self.question_id is not None and self.answer is not None):
            raise ValueError("ANSWER_CONTEXT_REQUIRED")
        if self.action != "answer" and (self.question_id is not None or self.answer is not None):
            raise ValueError("ANSWER_CONTEXT_DENIED")
        if len(self.model_dump_json().encode()) > 3600 or (self.answer and "\x00" in self.answer):
            raise ValueError("COMMAND_LIMIT")
        return self
