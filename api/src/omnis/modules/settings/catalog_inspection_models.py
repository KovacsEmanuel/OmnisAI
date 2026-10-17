"""Read-only metadata DTOs; these are not execution selections or readiness grants."""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, field_validator

from .catalog_models import Digest, Key, Preference, StrictDTO

UUIDText = Annotated[
    str, Field(pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
]
Revision = Annotated[int, Field(ge=1, lt=2147483647)]
Generation = Annotated[int, Field(ge=1, lt=2**63)]


class CatalogPin(StrictDTO):
    kind: Literal[
        "source-draft",
        "candidate-snapshot",
        "technical-review",
        "evaluation-receipt",
        "operator-confirmation",
        "catalog-publication",
        "evaluation-input",
        "contract-case-input",
        "contract-case-records",
        "qualified-release",
        "release-qualification",
        "package",
        "profile",
        "technique",
        "procedure",
        "schema",
        "method",
        "prompt",
        "template",
        "overlay",
        "asset",
    ]
    id: UUIDText
    revision: Revision
    digest: Digest

    @field_validator("id")
    @classmethod
    def canonical_uuid(cls, value: str) -> str:
        if str(UUID(value)) != value:
            raise ValueError("Noncanonical identity")
        return value


Pins = Annotated[list[CatalogPin], Field(max_length=128)]


class CatalogEntry(StrictDTO):
    publication_ref: CatalogPin
    profile_key: Key
    generation: Generation


class CatalogPage(StrictDTO):
    items: Annotated[list[CatalogEntry], Field(max_length=20)]
    has_more: bool
    next_after: UUIDText | None


class CatalogInspection(CatalogEntry):
    owner_id: UUIDText
    profile_ref: CatalogPin
    snapshot_ref: CatalogPin
    technical_review_ref: CatalogPin
    static_evaluation_ref: CatalogPin
    pure_evaluation_ref: CatalogPin
    confirmation_ref: CatalogPin
    source_draft_refs: Pins
    candidate_refs: Pins
    dependency_closure_refs: Pins
    dependency_artifact_refs: Pins
    material_digest: Digest
    resolved_index_digest: Digest
    dependency_closure_digest: Digest
    compiler_revision: Digest
    evaluator_revision: Digest
    requested: Preference
    review: Literal["RECORDED_STATIC_PASS"]
    static: Literal["RECORDED_STATIC_PASS"]
    pure: Literal["RECORDED_PURE_PASS"]
    dependency_metadata: Literal["NO_EXTERNAL_DEPENDENCIES", "NOT_VERIFIED"]
    material: Literal["NOT_VERIFIED"]
    runtime: Literal["NOT_AVAILABLE"]
    benchmark: Literal["NOT_VERIFIED"]
    fixture: Literal["NOT_VERIFIED"]
    security: Literal["NOT_VERIFIED"]
    assessment_selectable: Literal[False]
    resolution: Literal["NO_MODEL"]
