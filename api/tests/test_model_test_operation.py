"""SOURCE owner lifetime, not PG/native/provider evidence."""

import asyncio
import time
from collections.abc import AsyncIterator
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from omnis.modules.instance.schemas import NativeTaskCommand
from omnis.modules.runs.managed_admission import ManagedAdmission
from omnis.modules.runs.model_test import REQUESTED
from omnis.modules.runs.model_test_models import ModelTestControl
from omnis.modules.settings import candidate_store as records
from omnis.modules.settings.catalog_models import CatalogError
from omnis.modules.tasks.managed_contract import mapping
from omnis.supervisor.native_tasks import NativeTaskOwner


@pytest.mark.asyncio
@pytest.mark.parametrize("finish", ["complete", "stop", "terminal-write-fails"])
async def test_operation_outlives_four_seconds_disconnect_and_no_refill(
    monkeypatch: pytest.MonkeyPatch,
    finish: str,
    ipc_directory: Path,
) -> None:
    from omnis.modules.runs import model_test_operation as operation
    from omnis.modules.runs.model_test_routes import control_exchange
    from omnis.transport import local_control
    from omnis.transport.local_control import LocalControl

    identity, command = map(str, (uuid4(), uuid4()))
    service = Mock()
    service.owned_status = AsyncMock(
        return_value=SimpleNamespace(
            instance_id=identity,
            generation=0,
            shutdown_command_id=None,
        )
    )
    engine = Mock()
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def transaction() -> AsyncIterator[Mock]:
        yield Mock()

    engine.begin = transaction
    service.native_preparation_commit = lambda *args: transaction()
    runtime = Mock()
    runtime.settings_status = AsyncMock(
        return_value={
            "operation_id": str(uuid4()),
            "status": "CONFIRMED",
            "selection": REQUESTED,
            "authenticated": "LOCAL_PRESENT",
        }
    )
    owner = NativeTaskOwner(ManagedAdmission(engine), service, uuid4(), 1, runtime)
    source: dict[str, object] = {
        "owner_id": identity,
        "command_id": str(uuid4()),
        "manifest_ref": {
            "kind": "launch-manifest",
            "id": str(uuid4()),
            "revision": 1,
            "digest": "a" * 64,
        },
    }
    saved = {"source": records.envelope("model-test-source", source)}
    monkeypatch.setattr(
        owner.domain,
        "readback",
        AsyncMock(
            return_value={
                "manifest_ref": source["manifest_ref"],
                "binding": None,
                "stage_started": False,
                "release_started": False,
                "results": [],
            }
        ),
    )

    async def load(conn: object, who: str, tag: str) -> dict[str, object] | None:
        return saved.get(tag)

    async def save(
        conn: object, who: str, tag: str, payload: dict[str, object]
    ) -> dict[str, object]:
        if tag in saved:
            raise CatalogError("COMMAND_CONFLICT")
        if tag == "terminal" and finish == "terminal-write-fails":
            raise OSError("SOURCE terminal persistence failure")
        saved[tag] = records.envelope("model-test-" + tag, payload)
        return saved[tag]

    monkeypatch.setattr(operation, "load", load)
    monkeypatch.setattr(operation, "save", save)
    monkeypatch.setattr(records, "lock", AsyncMock())

    begin = time.monotonic()
    monkeypatch.setattr(
        owner,
        "_model_test_prepare",
        AsyncMock(
            return_value={
                "composition_ref": {
                    "kind": "prompt-composition",
                    "id": str(uuid4()),
                    "revision": 1,
                    "digest": "b" * 64,
                }
            }
        ),
    )
    reads: list[dict[str, object]] = []

    async def send(checked: NativeTaskCommand) -> dict[str, object]:
        if finish == "terminal-write-fails" and reads:
            raise OSError("SOURCE receive persistence failure")
        reads.append(checked.model_dump(mode="json"))
        return {
            "state": "SETTLED" if time.monotonic() - begin > 4.1 else "SENT",
            "provider_receipt_ref": None,
        }

    monkeypatch.setattr(owner, "_model_test_send", send)
    monkeypatch.setattr(
        operation,
        "projection",
        AsyncMock(
            side_effect=lambda *args: (
                {
                    "response_text": "<actual controlled response>",
                    "observed_model": "gpt-6.1-sol",
                    "observed_effort": None,
                    "input_tokens": None,
                    "output_tokens": 3,
                    "reasoning_tokens": None,
                }
                if "terminal" in saved
                and mapping(saved["terminal"]["payload"])["status"] == "COMPLETE"
                else {}
            )
        ),
    )
    request = ModelTestControl(op="model_test", action="start", operation_id=command)
    monkeypatch.setattr(local_control, "readiness_reason", AsyncMock(return_value=None))
    monkeypatch.setenv("OMNIS_CONTROL_DIR", str(ipc_directory))
    async with LocalControl(ipc_directory, service, owner.owner, owner.epoch) as control:
        control.model_test = owner.model_test
        result = await asyncio.wait_for(control_exchange(request), 0.5)
    assert result["status"] == "PENDING"
    assert owner.model_test_task is not None
    # Client lifetime ends here; the supervisor-owned finite task remains tracked.
    task = owner.model_test_task
    if finish == "terminal-write-fails":
        with pytest.raises(OSError, match="terminal persistence failure"):
            await task
        assert (await owner.model_test(ModelTestControl(op="model_test", action="read")))[
            "status"
        ] == "UNKNOWN"
        before = len(reads)
        assert (await owner.model_test(request))["status"] == "UNKNOWN"
        assert len(reads) == before
        return
    if finish == "stop":
        await asyncio.sleep(0.01)
        await owner.close_model_test()
        assert task.done()
        assert (await owner.model_test(ModelTestControl(op="model_test", action="read")))[
            "status"
        ] == "UNKNOWN"
        before = len(reads)
        with pytest.raises(CatalogError, match="TASK_UNAVAILABLE"):
            await owner.model_test(request)
        replacement = NativeTaskOwner(owner.domain, service, uuid4(), owner.epoch + 1, runtime)
        assert (await replacement.model_test(request))["status"] == "UNKNOWN"
        assert len(reads) == before
        return
    await asyncio.wait_for(task, 6)
    assert time.monotonic() - begin > 4
    result = await owner.model_test(ModelTestControl(op="model_test", action="read"))
    assert result["status"] == "COMPLETE"
    assert result["response_text"] == "<actual controlled response>"
    assert result["observed_effort"] is None
    before = len(reads)
    assert (await owner.model_test(request))["status"] == "COMPLETE"
    with pytest.raises(CatalogError, match="COMMAND_CONFLICT"):
        await owner.model_test(request.model_copy(update={"operation_id": str(uuid4())}))

    assert len(reads) == before
    assert all(row == reads[0] for row in reads)
    owner.model_test_task = None
    assert (await owner.model_test(request))["status"] == "COMPLETE"


def test_public_request_and_private_fields_are_strict() -> None:
    from pydantic import ValidationError

    from omnis.modules.runs.model_test_models import ModelTestRequest

    with pytest.raises(ValidationError):
        ModelTestRequest.model_validate(
            {"operation_id": str(uuid4()), "consent": True, "prompt": "secret"}
        )
    with pytest.raises(ValidationError):
        ModelTestControl(
            op="model_test",
            action="start",
            operation_id=str(uuid4()),
            selection_ref={},
        )


def test_provision_uses_catalog_validator(monkeypatch: pytest.MonkeyPatch) -> None:
    from pydantic import ValidationError

    from omnis.modules.settings import candidate_catalog

    validate = Mock(wraps=candidate_catalog.valid_ref)
    monkeypatch.setattr(candidate_catalog, "valid_ref", validate)
    ref: dict[str, object] = {
        "kind": "execution-selection",
        "id": str(uuid4()),
        "revision": 1,
        "digest": "a" * 64,
    }
    control = ModelTestControl(op="model_test", action="provision", selection_ref=ref)
    assert control.selection_ref == ref
    validate.assert_called_once_with(ref)
    malformed = {**ref, "revision": True}
    with pytest.raises(ValidationError, match="INVALID_REQUEST"):
        ModelTestControl(op="model_test", action="provision", selection_ref=malformed)
    validate.assert_called_with(malformed)
    with pytest.raises(ValidationError, match="Published selection required"):
        ModelTestControl(
            op="model_test", action="provision", selection_ref={**ref, "kind": "run-snapshot"}
        )
