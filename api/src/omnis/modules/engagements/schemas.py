"""Strict declarative P1 draft DTOs; saving never grants target or model effects."""

import builtins
import json
from datetime import datetime
from typing import Annotated, Literal
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic_core import PydanticCustomError

from omnis.core.persistence import DatabaseRecord

FULL_OBJECTIVE = "Evaluează suprafața Web/API autorizată în limitele profilului selectat."
MAX_DRAFT_PAYLOAD_BYTES = 1_000_000


def no_nul(value: str) -> str:
    # PostgreSQL JSONB cannot persist U+0000, regardless of its position.
    if "\x00" in value:
        raise ValueError("NUL is not valid draft text")
    return value


DraftText = Annotated[str, AfterValidator(no_nul)]


class DraftRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Authorization(DraftRecord):
    owner: DraftText = Field(min_length=1, max_length=128)
    statement: DraftText = Field(min_length=1, max_length=4096)
    valid_from: DraftText = Field(pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
    valid_until: DraftText = Field(pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

    @model_validator(mode="after")
    def ordered_window(self) -> "Authorization":
        try:
            start = datetime.fromisoformat(self.valid_from.replace("Z", "+00:00"))
            end = datetime.fromisoformat(self.valid_until.replace("Z", "+00:00"))
        except ValueError:
            raise PydanticCustomError(
                "authorization_window", "Invalid authorization window"
            ) from None
        if end <= start:
            raise PydanticCustomError("authorization_window", "Invalid authorization window")
        return self


type ScopeAccess = Literal["ATTACKABLE", "VISIT_ONLY", "BLOCKED"]


class ScopeEntry(DraftRecord):
    origin: DraftText = Field(min_length=1, max_length=255)
    port: int = Field(ge=1, le=65535)
    path_prefix: DraftText = Field(min_length=1, max_length=2048, pattern=r"^/[^?#]*$")
    exclusions: list[DraftText] = Field(max_length=32)
    access: ScopeAccess

    @field_validator("origin")
    @classmethod
    def exact_origin(cls, value: str) -> str:
        try:
            parsed = urlsplit(value)
            valid = (
                parsed.scheme in {"http", "https"}
                and parsed.hostname is not None
                and parsed.port is None
                and not parsed.netloc.endswith(":")
                and parsed.username is None
                and parsed.password is None
                and parsed.netloc.isascii()
                and parsed.netloc == parsed.netloc.lower()
                and value == f"{parsed.scheme}://{parsed.netloc}"
            )
        except ValueError:
            valid = False
        if not valid:
            raise ValueError("Expected an exact HTTP origin without port or path")
        return value

    @field_validator("exclusions")
    @classmethod
    def bounded_exclusions(cls, value: list[str]) -> list[str]:
        if any(
            not 1 <= len(item) <= 2048 or not item.startswith("/") or "?" in item or "#" in item
            for item in value
        ):
            raise ValueError("Invalid declarative path exclusion")
        return value


type AssessmentMode = Literal["FULL_ASSESSMENT", "FOCUSED_TEST"]


type ConstraintKind = Literal["READ_ONLY", "EXCLUDE_FEATURE", "REQUIRE_CRITERION"]


class ObjectiveConstraint(DraftRecord):
    id: UUID
    kind: ConstraintKind
    text: DraftText = Field(min_length=1, max_length=1024)
    # No operation catalog exists in B02a. References are not accepted on trust.
    operation_refs: list[object] = Field(max_length=0)

    @field_validator("id", mode="before")
    @classmethod
    def exact_id(cls, value: object) -> UUID:
        if type(value) is not str:
            raise ValueError("Invalid constraint ID")
        try:
            identity = UUID(value)
        except ValueError:
            raise ValueError("Invalid constraint ID") from None
        if str(identity) != value:
            raise ValueError("Invalid constraint ID")
        return identity


class LegacyEngagementDraft(DraftRecord):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        json_schema_extra={"x-max-canonical-payload-bytes": MAX_DRAFT_PAYLOAD_BYTES},
    )

    name: DraftText = Field(min_length=1, max_length=128)
    authorization: Authorization
    scope: list[ScopeEntry] = Field(min_length=1, max_length=64)
    assessment_mode: AssessmentMode
    objective_text: DraftText = Field(max_length=8192)
    objective_constraints: list[ObjectiveConstraint] = Field(max_length=64)
    workflow_profile_ref: Literal[None]

    @field_validator("objective_text")
    @classmethod
    def objective_bytes(cls, value: str) -> str:
        try:
            length = len(value.encode("utf-8"))
        except UnicodeEncodeError:
            raise ValueError("Invalid objective") from None
        if length > 32768:
            raise ValueError("Invalid objective")
        return value

    @model_validator(mode="after")
    def objective_for_mode(self) -> "LegacyEngagementDraft":
        if self.assessment_mode == "FULL_ASSESSMENT" and not self.objective_text:
            self.objective_text = FULL_OBJECTIVE
        if not self.objective_text or (
            self.assessment_mode == "FOCUSED_TEST" and not self.objective_text.strip()
        ):
            raise PydanticCustomError("focused_objective", "Invalid objective")
        return self

    @field_validator("objective_constraints")
    @classmethod
    def unique_constraints(cls, value: list[ObjectiveConstraint]) -> list[ObjectiveConstraint]:
        if len({item.id for item in value}) != len(value):
            raise ValueError("Duplicate objective constraint")
        return value

    @model_validator(mode="after")
    def bounded_total(self) -> "LegacyEngagementDraft":
        canonical = json.dumps(
            self.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
        if len(canonical) > MAX_DRAFT_PAYLOAD_BYTES:
            raise PydanticCustomError("draft_too_large", "Draft exceeds aggregate size limit")
        return self


class ApplicationContext(DraftRecord):
    seed_urls: list[DraftText] = Field(max_length=32)
    priority_workflows: list[DraftText] = Field(max_length=32)
    test_objects: list[DraftText] = Field(max_length=64)
    # No import identity/revision exists in B02b; never accept a guessed ref.
    import_ref: Literal[None]

    @field_validator("seed_urls")
    @classmethod
    def valid_seeds(cls, value: list[str]) -> list[str]:
        for seed in value:
            if len(seed) > 2048:
                raise ValueError("Invalid seed URL")
            try:
                parsed = urlsplit(seed)
                valid = (
                    parsed.scheme in {"http", "https"}
                    and parsed.hostname is not None
                    and parsed.username is None
                    and parsed.password is None
                    and parsed.fragment == ""
                    and parsed.netloc.isascii()
                    and not parsed.netloc.endswith(":")
                    and (parsed.port is None or 1 <= parsed.port <= 65535)
                )
            except ValueError:
                valid = False
            if not valid:
                raise ValueError("Invalid seed URL")
        return value

    @field_validator("priority_workflows", "test_objects")
    @classmethod
    def bounded_labels(cls, value: list[str]) -> list[str]:
        if any(not 1 <= len(item) <= 1024 for item in value):
            raise ValueError("Invalid application context label")
        return value


type EffectClass = Literal[
    "READ_ONLY_KNOWN", "SESSION_CHANGE", "LIMITED_WRITE", "DESTRUCTIVE", "UNKNOWN"
]
type DeclaredDecision = Literal["ALLOW", "DENY", "UNKNOWN"]


class EffectRule(DraftRecord):
    effect_class: EffectClass
    decision: DeclaredDecision
    note: DraftText = Field(max_length=1024)


class DraftBudgets(DraftRecord):
    max_requests: int = Field(ge=0, le=100000)
    max_duration_seconds: int = Field(ge=0, le=86400)
    max_storage_bytes: int = Field(ge=0, le=1073741824)
    validation_reserved_requests: int = Field(ge=0, le=100000)
    max_model_calls: int = Field(ge=0, le=10000)

    @model_validator(mode="after")
    def valid_reserve(self) -> "DraftBudgets":
        if self.validation_reserved_requests > self.max_requests:
            raise PydanticCustomError("invalid_budget_reserve", "Invalid draft budget reserve")
        return self


class DraftDataPolicy(DraftRecord):
    model_projection: Literal["NONE", "REDACTED"]
    research_egress: Literal["NONE", "PUBLIC_FACTS"]
    retention_days: int = Field(ge=0, le=365)


class BusinessMatrixEntry(DraftRecord):
    id: UUID
    principal: DraftText = Field(min_length=1, max_length=128)
    role: DraftText = Field(min_length=1, max_length=128)
    tenant: DraftText = Field(min_length=1, max_length=128)
    object: DraftText = Field(min_length=1, max_length=256)
    operation: DraftText = Field(min_length=1, max_length=128)
    expected: DeclaredDecision
    source: DraftText = Field(min_length=1, max_length=1024)
    source_revision: int = Field(ge=1, le=2147483647)

    @field_validator("id", mode="before")
    @classmethod
    def exact_id(cls, value: builtins.object) -> UUID:
        if type(value) is not str:
            raise ValueError("Invalid matrix entry ID")
        try:
            identity = UUID(value)
        except ValueError:
            raise ValueError("Invalid matrix entry ID") from None
        if str(identity) != value:
            raise ValueError("Invalid matrix entry ID")
        return identity


class EngagementDraft(LegacyEngagementDraft):
    """B02b authored payload. Legacy rows remain exactly readable, not backfilled."""

    application_context: ApplicationContext
    effect_rules: list[EffectRule] = Field(max_length=16)
    budgets: DraftBudgets
    data_policy: DraftDataPolicy
    business_matrix: list[BusinessMatrixEntry] = Field(max_length=64)
    # Inline matrix is draft data; no published BusinessRuleRevision exists yet.
    business_rules_ref: Literal[None]

    @field_validator("effect_rules")
    @classmethod
    def unique_effects(cls, value: list[EffectRule]) -> list[EffectRule]:
        if len({item.effect_class for item in value}) != len(value):
            raise ValueError("Duplicate effect class")
        return value

    @field_validator("business_matrix")
    @classmethod
    def unique_matrix_ids(cls, value: list[BusinessMatrixEntry]) -> list[BusinessMatrixEntry]:
        if len({item.id for item in value}) != len(value):
            raise ValueError("Duplicate business matrix entry")
        return value


class EngagementView(DatabaseRecord):
    engagement_id: UUID
    schema_version: Literal[1]
    kind: Literal["engagement-revision"]
    id: UUID
    revision: int = Field(ge=1)
    digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    payload: LegacyEngagementDraft | EngagementDraft
    created_at: datetime


class EngagementSummary(DatabaseRecord):
    engagement_id: UUID
    id: UUID
    revision: int = Field(ge=1)
    digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    name: str = Field(min_length=1, max_length=128)
    assessment_mode: AssessmentMode
    created_at: datetime


class EngagementPage(DraftRecord):
    items: list[EngagementSummary]
    has_more: bool
    next_page: UUID | None


class RevisionPage(DraftRecord):
    items: list[EngagementView]
    has_more: bool
    next_page: int | None
