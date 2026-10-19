"""Complete shipped synthetic bytes; publication/storage remain explicit SOURCE doubles."""

import base64
import shutil
import time
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from omnis.modules.instance.domain import ControlCode, ControlConflict
from omnis.modules.instance.service import RuntimeAuthority
from omnis.modules.runs.model_test_source import PACKAGE, verify_shipped
from omnis.modules.settings.catalog_models import CatalogError
from omnis.modules.tasks.managed_contract import mapping, sequence
from omnis.supervisor.runtime_client import RuntimeClient, RuntimeUnavailable
from test_contract_method_producer import batch2_source


@pytest.mark.asyncio
async def test_exact_shipped_source_and_foreign_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, bundle, _, _ = await batch2_source(tmp_path / "producer", monkeypatch)
    repository = Path(__file__).resolve().parents[2]
    shipped = tmp_path / "shipped"
    shipped.mkdir()
    (shipped / "skills").mkdir()
    shutil.copytree(repository / "skills" / PACKAGE, shipped / "skills" / PACKAGE)
    shutil.copyfile(repository / "profiles" / (PACKAGE + ".yaml"), shipped / "profile.yaml")
    candidate = str(mapping(mapping(bundle["payload"])["candidate_snapshot_ref"])["id"])
    catalog = tmp_path / "catalog"
    profile = catalog / "candidates" / candidate / "profile.yaml"
    profile.parent.mkdir(parents=True)
    shutil.copyfile(shipped / "profile.yaml", profile)
    verify_shipped(bundle, catalog, shipped)
    foreign = deepcopy(bundle)
    payload = mapping(foreign["payload"])
    package = mapping(sequence(payload["packages"])[0])
    files = sequence(package["files"])
    files[0] = {**mapping(files[0]), "content_b64": base64.b64encode(b"foreign").decode()}
    package["files"] = files
    foreign["payload"] = {**payload, "packages": [package]}
    with pytest.raises(CatalogError, match="PREPARATION_REJECTED"):
        verify_shipped(foreign, catalog, shipped)
    profile.write_text("foreign")
    with pytest.raises(CatalogError, match="PREPARATION_REJECTED"):
        verify_shipped(bundle, catalog, shipped)


@pytest.mark.asyncio
async def test_normal_inert_launch_initial_open_bind_and_stop_fence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = RuntimeClient(tmp_path, generation=0, epoch=1)
    owner = uuid4()
    service = Mock()

    async def authority(
        who: object, epoch: int, generation: int, *, inert_probe: bool
    ) -> RuntimeAuthority:
        if generation != 1:
            raise ControlConflict(ControlCode.GENERATION_CONFLICT)
        assert inert_probe and epoch == 1 and who == owner
        return RuntimeAuthority(1, 1, time.monotonic_ns() + 4_000_000_000)

    service.runtime_authority = AsyncMock(side_effect=authority)
    service.owned_status = AsyncMock(
        return_value=SimpleNamespace(
            generation=1,
            admission_open=True,
            shutdown_command_id=None,
        )
    )
    exchange = AsyncMock(side_effect=[{"state": "IDLE"}, {"state": "READY"}])
    monkeypatch.setattr(client, "_exchange_locked", exchange)
    assert (await client.launch_inert(service, owner))["state"] == "READY"
    assert client.generation == 1 and exchange.await_count == 2
    client = RuntimeClient(tmp_path, generation=0, epoch=1)
    service.owned_status.return_value.shutdown_command_id = uuid4()
    denied = AsyncMock()
    monkeypatch.setattr(client, "_exchange_locked", denied)
    with pytest.raises(RuntimeUnavailable, match="Initial OPEN generation required"):
        await client.launch_inert(service, owner)
    denied.assert_not_awaited()
