"""SOURCE-only reason control for the newly reached real QA negative; no product edit."""
from pathlib import Path
from unittest.mock import AsyncMock
from uuid import uuid4
import json
import pytest

from omnis.modules.instance.schemas import NativeTaskCommand
from omnis.modules.settings.catalog_models import CatalogError
from omnis.modules.settings.catalog_schema import canonical
from omnis.supervisor.native_tasks import NativeTaskOwner, control_task
from omnis.transport import local_control
from test_owned_model_initialization import test_model_test_prepare_owns_fresh_qualified_context_and_holds as prepared


@pytest.mark.asyncio
async def test_existing_manifest_negative_has_conflict_not_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    original = NativeTaskOwner.handle
    captures = []

    async def capture(self, command):
        answer = await original(self, command)
        captures.append((self, command, answer))
        return answer

    monkeypatch.setattr(NativeTaskOwner, 'handle', capture)
    await prepared(tmp_path, monkeypatch, False)
    handler, command, answer = captures[0]
    monkeypatch.setattr(NativeTaskOwner, 'handle', original)
    monkeypatch.setattr(local_control, 'readiness_reason', AsyncMock(return_value=None))
    handler.service.engine = handler.domain.engine
    directory = Path('/home/kali/.hermes/cache/scratch/ms-xxfxw95l/reason-ipc2')
    directory.mkdir(mode=0o700)
    # Actual producer/retained SOURCE records; no fabricated successful wire DTO.
    before = canonical(answer)
    async with local_control.LocalControl(directory, handler.service, handler.owner, handler.epoch, native_task=handler.handle) as local:
        positive = await control_task(directory, command.model_dump(mode='json'))
        assert canonical({k: v for k, v in positive.items() if k != 'correlation_id'}) == before
        negative = {**command.model_dump(mode='json'), 'initialization_id': str(uuid4()), 'manifest_ref': {**command.manifest_ref, 'digest': '0' * 64}}
        NativeTaskCommand.model_validate(negative)
        with pytest.raises(CatalogError, match='^COMMAND_CONFLICT$') as caught:
            await control_task(directory, negative)
        # Exercise the original QA expectation on the observed exception, unchanged.
        with pytest.raises(AssertionError):
            with pytest.raises(CatalogError, match='^TASK_REJECTED$'):
                raise caught.value
        assert not local.clients
    assert local.lock_fd is None
    assert not (directory/'control.sock').exists() and not (directory/'control.cap').exists()
    print(json.dumps({'scope': 'SOURCE_STORAGE_MODEL_DOUBLES_REAL_OWNER_CONTROL_UDS', 'positive': 'ORIGINAL_COMPLETED_REPLY', 'negative': 'COMMAND_CONFLICT', 'original_QA_expectation': 'TASK_REJECTED', 'expectation_matches_observed': False, 'guard': 'NativeTaskOwner._handle_manifest_comparison_before_consumer', 'cleanup': 'CLIENTS_JOINED_ENDPOINTS_ABSENT_LOCK_CLOSED', 'native_PG_launches': 0, 'historical_negative_index_and_reason': 'UNKNOWN'}))
