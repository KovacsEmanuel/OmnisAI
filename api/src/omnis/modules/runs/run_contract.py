"""Versioned S1 proposals and commands; model output carries no execution authority."""

from __future__ import annotations

from datetime import datetime
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


class RunSummary(KeyDTO):
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
