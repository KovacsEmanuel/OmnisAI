"""Strict validation before replay/I/O; valid requests do not imply admission."""

from uuid import uuid4

import pytest

from omnis.modules.runs.managed_admission import validate_request
from omnis.modules.settings.catalog_models import CatalogError
from test_managed_contract import ref


def request() -> dict[str, object]:
    return {
        "schema_version": 1,
        "owner_id": str(uuid4()),
        "command_id": str(uuid4()),
        "selection_ref": ref("execution-selection"),
        "preparation_command_id": str(uuid4()),
        "task_count": 2,
    }


@pytest.mark.parametrize(
    "field,bad",
    [
        ("schema_version", True),
        ("schema_version", 2),
        ("task_count", True),
        ("task_count", 0),
        ("task_count", 3),
        ("task_count", "2"),
        ("owner_id", "foreign"),
        ("command_id", ""),
        ("preparation_command_id", False),
        (
            "selection_ref",
            {
                "kind": "execution-selection",
                "id": str(uuid4()),
                "revision": True,
                "digest": "a" * 64,
            },
        ),
        ("effective", None),
        ("goal", "override"),
        ("context", {}),
        ("role", "REVIEWER"),
        ("mission_ref", ref("mission")),
        ("model", "none"),
    ],
)
def test_reject_invalid_prepare_before_replay(field: str, bad: object) -> None:
    value = request()
    assert validate_request("prepare", value) == value
    with pytest.raises(CatalogError):
        validate_request("prepare", {**value, field: bad})


def test_reject_unknown_operation_and_missing_fields() -> None:
    value = request()
    with pytest.raises(CatalogError):
        validate_request("execute", value)
    for key in value:
        with pytest.raises(CatalogError):
            validate_request("prepare", {k: v for k, v in value.items() if k != key})
