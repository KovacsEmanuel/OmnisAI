"""Receive-only transport denials with real private Host/client, no native child.

The authentic final/cache positive is the pinned native PostgreSQL journey.
These controls never populate retention with fabricated execution bytes.
"""

import importlib
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from omnis.modules.instance.schemas import NativeTaskCommand
from omnis.modules.instance.service import InstanceService
from omnis.modules.runs.managed_admission import ManagedAdmission
from omnis.modules.settings import candidate_store as records
from omnis.modules.settings.catalog_models import CatalogError
from omnis.supervisor.native_tasks import NativeTaskOwner
from omnis.supervisor.runtime_client import RuntimeClient, RuntimeUnavailable
from test_managed_contract import manifest as manifest_fixture


@pytest.mark.asyncio
async def test_receive_unknown_ticket_and_foreign_pin_never_grant_or_launch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.syspath_prepend(
        str(Path(__file__).resolve().parents[2] / "integrations/hermes/src")
    )
    host_type = importlib.import_module("omnis_hermes.runtime_host").RuntimeHost
    with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"], prefix="cr-") as name:
        root = Path(name)
        runtime = RuntimeClient(root, generation=0, epoch=1)
        async with host_type(root) as host:
            try:
                await runtime.connect()
                payload: dict[str, object] = {
                    "protocol": "omnis-managed-admission-v4",
                    "ticket": str(uuid4()),
                    "manifest_ref": {
                        "kind": "launch-manifest",
                        "id": str(uuid4()),
                        "revision": 1,
                        "digest": "0" * 64,
                    },
                }
                for wrong in (
                    payload,
                    {**payload, "protocol": "unsupported"},
                    {**payload, "extra": True},
                ):
                    with pytest.raises(RuntimeUnavailable):
                        await runtime.receive(wrong, expected_boot=host.boot)
                assert host.managed_finals == {}
                assert host.process is None and host.peer is None
                assert host.deadline_ns == 0 and host.state == "IDLE"
            finally:
                await runtime.close()
        assert not (root / "runtime.sock").exists()
        assert not (root / "runtime.boot").exists()


@pytest.mark.asyncio
async def test_receive_refuses_replaced_host_before_any_exchange(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.syspath_prepend(
        str(Path(__file__).resolve().parents[2] / "integrations/hermes/src")
    )
    host_type = importlib.import_module("omnis_hermes.runtime_host").RuntimeHost
    with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"], prefix="cr-") as name:
        root = Path(name)
        runtime = RuntimeClient(root, generation=0, epoch=1)
        async with host_type(root) as original:
            await runtime.connect()
            boot = runtime.boot
            assert boot == original.boot
            await runtime.close()
        attempts: list[str] = []

        async def forbidden(*args: object, **kwargs: object) -> dict[str, object]:
            attempts.append("EXCHANGE")
            raise AssertionError("REPLACEMENT_HOST_CONTACTED")

        monkeypatch.setattr(runtime, "_exchange", forbidden)
        async with host_type(root) as replacement:
            try:
                assert replacement.boot != boot
                with pytest.raises(RuntimeUnavailable, match="Replaced runtime host"):
                    await runtime.receive({}, expected_boot=boot)
                assert attempts == []
                assert runtime.reader is None and runtime.writer is None
                assert replacement.process is None and replacement.peer is None
                assert replacement.managed_finals == {} and replacement.deadline_ns == 0
            finally:
                await runtime.close()
        assert not (root / "runtime.sock").exists()
        assert not (root / "runtime.boot").exists()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["host-absent", "invalid-metadata"])
async def test_original_host_loss_returns_sanitized_owner_control_reply(
    monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    """Real SOURCE UDS/control/owner; explicit domain/readiness doubles, no DB/native final."""
    import asyncio
    import json

    from omnis.transport.local_control import LocalControl

    monkeypatch.syspath_prepend(
        str(Path(__file__).resolve().parents[2] / "integrations/hermes/src")
    )
    host_type = importlib.import_module("omnis_hermes.runtime_host").RuntimeHost
    with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"], prefix="cr-") as name:
        root = Path(name)
        runtime = RuntimeClient(root, generation=0, epoch=1)
        async with host_type(root) as host:
            await runtime.connect()
            boot = runtime.boot
            assert boot == host.boot
            await runtime.close()
        if failure == "invalid-metadata":
            metadata = root / "runtime.boot"
            metadata.write_bytes(b"{}")
            metadata.chmod(0o600)
        manifest = manifest_fixture()
        reference = records.reference(manifest)
        supervisor, instance = uuid4(), str(uuid4())
        binding = records.envelope(
            "runtime-binding",
            {
                "runtime_boot": boot,
                "ticket": str(uuid4()),
                "authority": {
                    "instance_id": instance,
                    "owner": str(supervisor),
                    "epoch": 1,
                    "generation": 0,
                },
            },
        )
        domain = Mock(spec=ManagedAdmission)
        before = {
            "manifest_ref": reference,
            "manifest": manifest,
            "binding": binding,
            "results": [],
            "release_started": True,
        }
        domain.readback = AsyncMock(return_value=before)
        service = Mock(spec=InstanceService)
        service.engine = Mock()
        handler = NativeTaskOwner(domain, service, supervisor, 1, runtime)
        command = NativeTaskCommand(
            op="native_task",
            schema_version=1,
            owner_id=str(uuid4()),
            command_id=str(uuid4()),
            instance_id=instance,
            expected_epoch=1,
            expected_generation=0,
            manifest_ref=reference,
            action="receive",
        )
        exchanges: list[str] = []

        async def forbidden(*args: object, **kwargs: object) -> dict[str, object]:
            exchanges.append("EXCHANGE")
            raise AssertionError("MISSING_HOST_REACHED_EXCHANGE")

        monkeypatch.setattr(runtime, "_exchange", forbidden)
        monkeypatch.setattr(
            "omnis.transport.local_control.readiness_reason", AsyncMock(return_value=None)
        )
        loop = asyncio.get_running_loop()
        original_exception_handler = loop.get_exception_handler()
        unhandled: list[str] = []
        loop.set_exception_handler(
            lambda _, context: unhandled.append(type(context.get("exception")).__name__)
        )
        try:
            async with LocalControl(
                root, service, supervisor, 1, native_task=handler.handle
            ) as control:
                reader, writer = await asyncio.open_unix_connection(root / "control.sock")
                try:
                    request = {
                        "version": 1,
                        "capability": control.capability,
                        "command": command.model_dump(mode="json"),
                    }
                    writer.write(json.dumps(request).encode() + b"\n")
                    await writer.drain()
                    reply = await asyncio.wait_for(reader.readline(), 1)
                    if not reply:
                        raise AssertionError("HOST_DEATH_MISSING_SANITIZED_REPLY")
                    response = json.loads(reply)
                    assert set(response) == {"ok", "error", "correlation_id"}
                    assert response["ok"] is False and response["error"] == "TASK_INDETERMINATE"
                finally:
                    writer.close()
                    await writer.wait_closed()
        finally:
            loop.set_exception_handler(original_exception_handler)
            await runtime.close()
        assert unhandled == [] and exchanges == []
        assert runtime.reader is None and runtime.writer is None
        assert before["release_started"] is True and before["results"] == []
        domain.ingest_result.assert_not_called()
        domain.check.assert_not_called()
        service.runtime_authority.assert_not_called()
        assert not (root / "runtime.sock").exists()
        assert not (root / "control.sock").exists() and not (root / "control.cap").exists()


@pytest.mark.asyncio
async def test_foreign_supervisor_cannot_receive_original_owners_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Owner authorization SOURCE unit: no injected positive result or DB proof."""
    manifest = manifest_fixture()
    reference = records.reference(manifest)
    native_owner, foreign = uuid4(), uuid4()
    instance, boot = str(uuid4()), str(uuid4())
    binding = records.envelope(
        "runtime-binding",
        {
            "runtime_boot": boot,
            "ticket": str(uuid4()),
            "authority": {
                "instance_id": instance,
                "owner": str(native_owner),
                "epoch": 1,
                "generation": 0,
            },
        },
    )
    domain = Mock(spec=ManagedAdmission)
    domain.readback = AsyncMock(
        return_value={
            "manifest_ref": reference,
            "manifest": manifest,
            "binding": binding,
            "results": [],
            "release_started": True,
        }
    )
    runtime = RuntimeClient(Path("/unused"), generation=0, epoch=1)
    runtime.boot = boot
    received = AsyncMock(side_effect=AssertionError("FOREIGN_OWNER_REACHED_RECEIVE"))
    monkeypatch.setattr(runtime, "receive", received)
    handler = NativeTaskOwner(domain, Mock(spec=InstanceService), foreign, 1, runtime)
    command = NativeTaskCommand(
        op="native_task",
        schema_version=1,
        owner_id=str(uuid4()),
        command_id=str(uuid4()),
        instance_id=instance,
        expected_epoch=1,
        expected_generation=0,
        manifest_ref=reference,
        action="receive",
    )
    with pytest.raises(CatalogError, match="^COMMAND_CONFLICT$"):
        await handler.handle(command)
    assert received.await_count == 0
    domain.ingest_result.assert_not_called()
    domain.check.assert_not_called()
