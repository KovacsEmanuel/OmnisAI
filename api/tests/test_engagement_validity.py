"""Source-only validity contract; no database fixture is requested."""

import hashlib
from uuid import UUID

import pytest
from pydantic import ValidationError

from omnis.modules.engagements.schemas import Authorization, EngagementDraft, LegacyEngagementDraft
from omnis.modules.engagements.service import canonical_json, revision_digest
from test_engagements import declarative_fields, draft


def test_unbounded_validity_is_explicit_and_preserves_the_complete_payload() -> None:
    original = draft()
    authorization = original["authorization"]
    assert isinstance(authorization, dict)
    original["authorization"] = {**authorization, "valid_from": None, "valid_until": None}
    parsed = EngagementDraft.model_validate(original)
    assert parsed.model_dump(mode="json") == original
    assert len(canonical_json(original).encode()) == 1244
    assert set(parsed.model_dump()) == set(draft())
    legacy = {key: value for key, value in original.items() if key not in declarative_fields()}
    assert LegacyEngagementDraft.model_validate(legacy).model_dump(mode="json") == legacy


@pytest.mark.parametrize(
    "changes",
    [
        {"valid_from": None},
        {"valid_until": None},
        {"valid_from": True},
        {"valid_until": 2030},
        {"valid_from": "2030-02-29T00:00:00Z"},
        {"valid_from": "2030-04-31T00:00:00Z"},
        {"valid_from": "0000-01-01T00:00:00Z"},
        {"valid_from": "2030-01-01T24:00:00Z"},
        {"valid_from": "2030-01-01T00:00:60Z"},
        {"valid_until": "2030-01-01T00:00:00Z"},
        {"valid_until": "2029-12-31T23:59:59Z"},
        {"valid_from": "2030-01-01T00:00:00+00:00"},
        {"extra": None},
    ],
)
def test_invalid_validity_cannot_be_coerced(changes: dict[str, object]) -> None:
    original = draft()["authorization"]
    assert isinstance(original, dict)
    with pytest.raises(ValidationError):
        Authorization.model_validate({**original, **changes})


@pytest.mark.parametrize("missing", ["valid_from", "valid_until"])
def test_validity_fields_remain_required_even_when_unbounded(missing: str) -> None:
    fields: dict[str, object] = {
        "owner": "Synthetic owner",
        "statement": "Synthetic permission",
        "valid_from": None,
        "valid_until": None,
    }
    del fields[missing]
    with pytest.raises(ValidationError):
        Authorization.model_validate(fields)


def test_finite_payload_and_revision_digest_remain_exact() -> None:
    original = draft()
    parsed = EngagementDraft.model_validate(original)
    assert parsed.model_dump(mode="json") == original
    assert len(canonical_json(original).encode()) == 1280
    # Bind the old canonical envelope independently of the model's serializer.
    revision_id = UUID("11111111-1111-4111-8111-111111111111")

    expected = hashlib.sha256(
        canonical_json(
            {
                "schema_version": 1,
                "kind": "engagement-revision",
                "id": str(revision_id),
                "revision": 1,
                "payload": original,
            }
        ).encode()
    ).hexdigest()
    assert revision_digest(revision_id, 1, parsed) == expected
    assert (
        Authorization.model_validate(
            {**parsed.authorization.model_dump(), "valid_from": "2028-02-29T12:34:56Z"}
        ).valid_from
        == "2028-02-29T12:34:56Z"
    )


def test_validity_openapi_input_output_are_identical_and_required() -> None:
    schema = Authorization.model_json_schema(mode="validation")
    assert schema == Authorization.model_json_schema(mode="serialization")
    assert set(schema["required"]) == {"owner", "statement", "valid_from", "valid_until"}
    assert "default" not in schema["properties"]["valid_from"]
