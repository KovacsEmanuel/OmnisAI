"""R1-01: actual private-control reader with SOURCE stream doubles, no socket I/O."""

import asyncio
import copy
import os
import struct
from pathlib import Path
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from omnis.modules.runs import native_preparation
from omnis.modules.settings import candidate_store as records
from omnis.modules.settings.catalog_models import CatalogError
from omnis.modules.settings.catalog_schema import canonical
from omnis.modules.tasks.managed_contract import mapping
from omnis.supervisor import native_tasks
from omnis.transport import control_probe


def fixture_values() -> tuple[dict[str, object], dict[str, object]]:
    manifest = records.reference(records.envelope("launch-manifest", {}))
    binding = records.reference(records.envelope("runtime-binding", {}))
    request: dict[str, object] = {
        "op": "native_task",
        "schema_version": 1,
        "owner_id": str(uuid4()),
        "command_id": str(uuid4()),
        "instance_id": str(uuid4()),
        "expected_generation": 0,
        "expected_epoch": 1,
        "action": "model_preflight",
        "manifest_ref": manifest,
        "data_approval": {
            "decision_id": str(uuid4()),
            "composition_ref": records.reference(records.envelope("prompt-composition", {})),
            "approved_text_digests": ["a" * 64],
        },
    }
    response: dict[str, object] = {
        "ok": True,
        "correlation_id": str(uuid4()),
        "manifest_ref": manifest,
        "binding_ref": binding,
        "task_status": "BLOCKED",
        "model_admission": {
            "protocol": "omnis-managed-admission-v3",
            "status": "BLOCKED",
            "reason": "NO_MODEL",
            "manifest_ref": copy.deepcopy(manifest),
            "binding_ref": copy.deepcopy(binding),
            "projection_ref": records.reference(records.envelope("model-projection", {})),
            "projection_digest": "a" * 64,
            "native_turn": None,
            "model_calls": 0,
            "data_approval_ref": records.reference(records.envelope("model-data-approval", {})),
        },
    }
    return request, response


async def consume(
    monkeypatch: pytest.MonkeyPatch,
    request: dict[str, object],
    response: dict[str, object],
) -> dict[str, object]:
    reader, writer = Mock(), Mock()
    reader.readuntil = AsyncMock(return_value=canonical(response) + b"\n")
    writer.drain, writer.wait_closed = AsyncMock(), AsyncMock()
    writer.get_extra_info.return_value.getsockopt.return_value = struct.pack(
        "3i", 123, os.getuid(), os.getgid()
    )
    monkeypatch.setattr(asyncio, "open_unix_connection", AsyncMock(return_value=(reader, writer)))
    monkeypatch.setattr(native_preparation, "existing_private_root", lambda path: path)
    monkeypatch.setattr(control_probe, "_read_capability", lambda path: "0" * 64)
    try:
        return await native_tasks.control_task(Path("/unused-control-source-double"), request)
    finally:
        writer.close.assert_called_once()
        writer.wait_closed.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("protocol", ["omnis-managed-admission-v2", "omnis-managed-admission-v3"])
async def test_valid_receipt_is_accepted(monkeypatch: pytest.MonkeyPatch, protocol: str) -> None:
    request, response = fixture_values()
    response["model_admission"] = {**mapping(response["model_admission"]), "protocol": protocol}
    assert await consume(monkeypatch, request, response) == response


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mutation",
    [
        "false-model-count",
        "fake-turn",
        "extra-field",
        "unknown-protocol",
        "non-string-protocol",
        "malformed-digest",
        "non-string-digest",
        "inner-manifest-bool-revision",
        "inner-binding-bool-revision",
    ],
)
async def test_all_receipt_fields_must_be_strict(
    monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    request, response = fixture_values()
    admission = mapping(response["model_admission"])
    if mutation == "false-model-count":
        admission["model_calls"] = False
    elif mutation == "fake-turn":
        admission["native_turn"] = str(uuid4())
    elif mutation == "extra-field":
        admission["unexpected"] = "synthetic"
    elif mutation == "unknown-protocol":
        admission["protocol"] = "not-supported"
    elif mutation == "non-string-protocol":
        admission["protocol"] = {"synthetic": "untrusted"}
    elif mutation == "malformed-digest":
        admission["projection_digest"] = "not-a-digest"
    elif mutation == "non-string-digest":
        admission["projection_digest"] = ["synthetic"]
    elif mutation == "inner-manifest-bool-revision":
        admission["manifest_ref"] = {**mapping(admission["manifest_ref"]), "revision": True}
    else:
        admission["binding_ref"] = {**mapping(admission["binding_ref"]), "revision": True}
    response["model_admission"] = admission
    with pytest.raises(CatalogError):
        await consume(monkeypatch, request, response)
