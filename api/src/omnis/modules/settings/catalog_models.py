"""Strict source DTOs and non-authoritative immutable compiler records.

This bounded subset is not a persisted CandidateSnapshot/RecordEnvelope.
Unsupported normative capabilities are blocked, not silently dropped.
"""

from dataclasses import dataclass
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue

Key = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_.-]{0,127}$")]
Text = Annotated[str, Field(max_length=4096)]
Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Sha = Annotated[str, Field(pattern=r"^[0-9a-f]{40}$")]


class CatalogError(ValueError):
    """A safe stable reason; raw input/validator diagnostics never escape CLI."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


class StrictDTO(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)


class LocalRef(StrictDTO):
    kind: Literal["LOCAL"]
    entity_kind: Key
    key: Key


class ExactRef(StrictDTO):
    kind: Key
    id: Annotated[str, Field(pattern=r"^[0-9a-f-]{36}$")]
    revision: Annotated[int, Field(ge=1)]
    digest: Digest


class ReleaseRef(StrictDTO):
    kind: Literal["RELEASE"]
    ref: ExactRef


TemplateRef = Annotated[LocalRef | ReleaseRef, Field(discriminator="kind")]


class CandidateRef(StrictDTO):
    kind: Literal["CANDIDATE"]
    package_key: Key
    entity_kind: Key
    key: Key


ProfileRef = Annotated[CandidateRef | ReleaseRef, Field(discriminator="kind")]


class SlotRef(StrictDTO):
    kind: Literal["CASE_SLOT_REF"]
    name: Key


class StepOutputRef(StrictDTO):
    kind: Literal["STEP_OUTPUT"]
    step_id: Key
    output_name: Key


InputRef = Annotated[LocalRef | ReleaseRef | SlotRef, Field(discriminator="kind")]
BindingRef = Annotated[LocalRef | ReleaseRef | SlotRef | StepOutputRef, Field(discriminator="kind")]


class Preference(StrictDTO):
    model_key: Key | None
    effort: Text | None
    requirement: Literal["REQUIRED", "PREFERRED"]
    on_unavailable: Literal["BLOCK", "USE_RUN_DEFAULT"]


DEFAULT_PREFERENCE = Preference(
    model_key=None, effort=None, requirement="PREFERRED", on_unavailable="BLOCK"
)


class Limits(StrictDTO):
    max_attempts: Annotated[int, Field(ge=1, le=10)]
    max_actions: Annotated[int, Field(ge=1, le=300)]
    deadline_seconds: Annotated[int, Field(ge=1, le=1200)]
    max_output_bytes: Annotated[int, Field(ge=1, le=1048576)]
    max_fanout: Annotated[int, Field(ge=1, le=2)]


class Binding(StrictDTO):
    name: Key
    source_ref: BindingRef
    selector: Key | None


class Step(StrictDTO):
    id: Key
    action_definition_ref: TemplateRef
    tool_ref: TemplateRef | None
    parameter_schema_ref: TemplateRef
    parameters: dict[str, JsonValue]
    input_bindings: tuple[Binding, ...]
    output_schema_ref: TemplateRef


class CaseSlot(StrictDTO):
    name: Key
    expected_kind: Key
    min_items: Annotated[int, Field(ge=0, le=128)]
    max_items: Annotated[int, Field(ge=1, le=128)]


class Precondition(StrictDTO):
    predicate_id: Key
    input_refs: tuple[InputRef, ...]
    expected: bool
    on_missing: Literal["BLOCKED", "INCONCLUSIVE"]


class NonApplicable(StrictDTO):
    group: Literal["BASELINE", "CONTROL"]
    reason: Annotated[str, Field(min_length=1, max_length=4096)]


class MethodRequirement(StrictDTO):
    key: Key
    description: Text
    required: bool
    applies_if: tuple[Precondition, ...]
    step_ids: tuple[Key, ...]
    artifact_schema_refs: tuple[TemplateRef, ...]
    evidence_kinds: tuple[Key, ...]


class Procedure(StrictDTO):
    schema_version: Literal[1]
    key: Key
    technique_ref: TemplateRef
    verification_kind: Literal["CONTRACT", "SECURITY"]
    non_applicable_groups: tuple[NonApplicable, ...]
    objective: Text
    applicability_predicate_ids: tuple[Key, ...]
    technologies: tuple[JsonValue, ...]
    input_schema_ref: TemplateRef
    output_schema_ref: TemplateRef
    preconditions: tuple[Precondition, ...]
    method_requirements: tuple[MethodRequirement, ...]
    identity_requirements: tuple[Key, ...]
    business_rule_refs: tuple[InputRef, ...]
    requested_capabilities: tuple[Key, ...]
    requested_effect_ceiling: Literal["PURE"]
    predicted_signal: Text
    baseline: tuple[Step, ...]
    probe: tuple[Step, ...]
    control: tuple[Step, ...]
    evidence_requirements: tuple[JsonValue, ...]
    oracle_ref: TemplateRef | None
    slots: tuple[CaseSlot, ...]
    false_positives: tuple[Text, ...]
    invalidation_predicate_ids: tuple[Key, ...]
    limits: Limits
    stop_reason_ids: tuple[Key, ...]
    cleanup: tuple[Step, ...]
    cleanup_not_needed_reason: Text | None
    handoff_schema_ref: TemplateRef
    outcomes: tuple[
        Literal[
            "SUCCEEDED", "INCONCLUSIVE", "BLOCKED", "FAILED", "CANCELLED", "NEEDS_RECONCILIATION"
        ],
        ...,
    ]


class Technique(StrictDTO):
    schema_version: Literal[1]
    key: Key
    family: Key
    work_kind: Literal["RECON", "ANALYSIS", "INVESTIGATION", "VALIDATION", "SUPPORT", "REVIEW"]
    cwe_ids: tuple[Text, ...]
    standards: tuple[JsonValue, ...]
    objective: Text
    hypothesis: Text
    invariant: Text
    method_ref: Text
    applicability_predicate_ids: tuple[Key, ...]
    technologies: tuple[JsonValue, ...]
    limitations: tuple[Text, ...]
    procedure_refs: tuple[TemplateRef, ...]


class FileBinding(StrictDTO):
    entity_kind: Literal["schema", "overlay", "method", "asset", "prompt", "template"]
    key: Key
    path: Text


class Provenance(StrictDTO):
    repository: Text
    revision: Sha
    path: Text
    source_digest: Digest
    license_id: Text
    notice_paths: tuple[Text, ...]
    modification_note: Text


class Compatibility(StrictDTO):
    hermes_revision: Sha
    brief_schema: Literal[1]
    result_schema: Literal[1]
    adapter_refs: tuple[TemplateRef, ...]
    tool_refs: tuple[TemplateRef, ...]
    predicate_refs: tuple[TemplateRef, ...]
    oracle_refs: tuple[TemplateRef, ...]


class Manifest(StrictDTO):
    schema_version: Literal[1]
    package_key: Key
    version: Annotated[
        str,
        Field(
            pattern=(
                r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
                r"(?:-(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*)"
                r"(?:\.(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*))*)?"
                r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
            )
        ),
    ]
    native_name: Key
    execution_preference: Preference | None
    skill_path: Literal["SKILL.md"]
    techniques: tuple[Technique, ...]
    procedures: tuple[Text, ...]
    support_files: tuple[Text, ...]
    file_bindings: tuple[FileBinding, ...]
    input_schema_ref: TemplateRef
    output_schema_ref: TemplateRef
    compatibility: Compatibility
    provenance: tuple[Provenance, ...]


class Recipe(StrictDTO):
    key: Key
    role: Literal["BRAIN", "RECON", "INVESTIGATOR", "VALIDATOR", "RESEARCH", "REVIEWER"]
    package_refs: tuple[ProfileRef, ...]
    technique_refs: tuple[ProfileRef, ...]
    procedure_refs: tuple[ProfileRef, ...]
    overlay_refs: tuple[ProfileRef, ...]
    execution_preference: Preference | None
    requested_capabilities: tuple[Key, ...]
    limits: Limits


class Profile(StrictDTO):
    schema_version: Literal[1]
    key: Key
    execution_preference: Preference | None
    agent_recipes: tuple[Recipe, ...]


@dataclass(frozen=True, slots=True)
class QualifiedRef:
    package_key: str
    entity_kind: str
    key: str
    digest: str


@dataclass(frozen=True, slots=True)
class CompiledStep:
    id: str
    handler: str
    bindings: tuple[Binding, ...]
    input_schema: bytes
    output_schema: bytes


@dataclass(frozen=True, slots=True)
class CompiledCatalog:
    material_digest: str
    resolved_index_digest: str
    resolution: Literal["NO_MODEL"]
    requested: Preference
    refs: tuple[QualifiedRef, ...]
    steps: tuple[CompiledStep, ...]
    input_schema: bytes
    output_schema: bytes
    verification_kind: Literal["CONTRACT", "SECURITY"]
    slots: tuple[CaseSlot, ...]
    max_output_bytes: int


@dataclass(frozen=True, slots=True)
class PureEvaluation:
    material_digest: str
    resolved_index_digest: str
    resolution: Literal["NO_MODEL"]
    outputs_json: tuple[bytes, ...]

    @property
    def outputs(self) -> tuple[object, ...]:
        import json

        return tuple(json.loads(item) for item in self.outputs_json)
