"""R1-01: actual private-control reader with SOURCE stream doubles, no socket I/O."""

import asyncio
import os
import struct
from pathlib import Path
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from omnis.modules.instance.schemas import NativeTaskCommand
from omnis.modules.runs import native_preparation
from omnis.modules.settings.catalog_models import CatalogError
from omnis.modules.settings.catalog_schema import canonical
from omnis.modules.tasks.managed_contract import mapping
from omnis.supervisor import native_tasks
from omnis.transport import control_probe
from test_model_admission import (
    test_qualified_projection_reaches_cold_admission_without_model_reservation as owner_journey,
)


async def fixture_values(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[dict[str, object], dict[str, object]]:
    # Capture the complete current producer echo rather than hand-authoring an
    # obsolete receipt. Storage/native identities remain explicit SOURCE doubles.
    observed: list[tuple[dict[str, object], dict[str, object]]] = []
    original = native_tasks.NativeTaskOwner.handle

    async def capture(
        self: native_tasks.NativeTaskOwner, command: NativeTaskCommand
    ) -> dict[str, object]:
        answer = await original(self, command)
        observed.append((command.model_dump(mode="json"), answer))
        return answer

    with monkeypatch.context() as producer_patch:
        producer_patch.setattr(native_tasks.NativeTaskOwner, "handle", capture)
        await owner_journey(tmp_path, producer_patch)
    assert len(observed) == 1
    request, response = observed[0]
    return request, {**response, "correlation_id": str(uuid4())}


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
async def test_valid_receipt_is_accepted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, protocol: str
) -> None:
    request, response = await fixture_values(tmp_path, monkeypatch)
    response["model_admission"] = {**mapping(response["model_admission"]), "protocol": protocol}
    assert await consume(monkeypatch, request, response) == response


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mutation",
    [
        "terminal-success",
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
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    request, response = await fixture_values(tmp_path, monkeypatch)
    admission = mapping(response["model_admission"])
    if mutation == "terminal-success":
        response["task_status"] = "SUCCEEDED"
    elif mutation == "false-model-count":
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
