import ast
import time
from pathlib import Path
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection
from omnis.modules.instance.schemas import NativeTaskCommand
from omnis.modules.runs.managed_admission import ManagedAdmission
from omnis.modules.runs.model_test import ModelTest, REQUESTED
from omnis.modules.settings.catalog_schema import canonical
from omnis.modules.settings.catalog_models import CatalogError
from omnis.modules.tasks import managed_store as store
from omnis.modules.tasks.managed_contract import mapping
from omnis.supervisor.native_tasks import control_task
from omnis.supervisor.runtime_client import RuntimeClient
from omnis.transport import local_control
from omnis_hermes import management_contract as settings
from omnis_hermes.managed_admission_contract import preparation_result
from omnis_hermes.runtime_host import RuntimeHost
from test_model_test_prepare_source import prepared_source, produce

@pytest.mark.asyncio
async def test_reason_probe(tmp_path: Path, ipc_directory: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    actual_state = store.state
    owner, consumer, conn, manifest, authority = await prepared_source(tmp_path, monkeypatch)
    original_graph = list(owner.graph)
    from omnis.modules.runs.pure_probe import PureProbe
    probe = PureProbe(owner.handler.domain.engine, tmp_path)
    _, snapshot, _, _ = await probe.publications.load_probe(conn, owner.owner, mapping(next(r for r in original_graph if r['kind'] == 'managed-run')['payload'])['snapshot_ref'])
    catalog_get = __import__('omnis.modules.settings.candidate_store', fromlist=['get'])
    original_get = catalog_get.get
    async def catalog(c: AsyncConnection, who: str, pin: object) -> tuple[str, dict[str, object]]:
        from omnis.modules.settings.candidate_store import reference
        if pin == reference(snapshot):
            return 'SOURCE-CATALOG-GROUP', snapshot
        return await original_get(c, who, pin)
    monkeypatch.setattr(catalog_get, 'get', catalog)
    payload = await produce(owner, consumer, conn, manifest, authority)
    context = mapping(mapping(payload['context'])['payload'])
    await consumer.persist(conn, owner.owner, payload, preparation_result(payload, native_root_id=str(uuid4()), native_child_id=str(uuid4()), native_session_id='SOURCE-session', native_turn={'task_id': context['task_id'], 'turn_id':'SOURCE-turn'}))
    command = NativeTaskCommand.model_validate({**owner.base, 'owner_id':owner.owner, 'manifest_ref':manifest, 'action':'model_test_prepare', 'initialization_id':context['preparation_id'], 'settings_operation_id':context['settings_operation_id']})
    expected = owner.handler._model_test_reply(command, mapping(payload['context']), owner.graph[-1])
    original_execute = conn.execute
    original_state = {**owner.state, 'owner_id':owner.owner, 'command_id':owner.command_id, 'manifest_id':manifest['id'], 'runtime_boot':None, 'ticket':None}
    async def execute(statement: object, params: dict[str, object] | None = None) -> object:
        query = str(statement)
        if query.startswith('SELECT * FROM managed_run WHERE owner_id=:owner AND '):
            assert params is not None
            row = original_state if params['owner'] == owner.owner and params['value'] in (owner.command_id, manifest['id']) else None
            return Mock(mappings=Mock(return_value=Mock(one_or_none=Mock(return_value=row))))
        if query.startswith('SELECT package_key,entity_key FROM catalog_identity'):
            return Mock(mappings=Mock(return_value=Mock(one_or_none=Mock(return_value={'package_key':'records-mapping-contract','entity_key':'records-mapping'}))))
        if query.startswith('SELECT * FROM managed_task') or query.startswith('SELECT i.* FROM managed_inbox'):
            return Mock(mappings=Mock(return_value=Mock(all=Mock(return_value=[]))))
        return await original_execute(statement, params)
    monkeypatch.setattr(conn, 'execute', AsyncMock(side_effect=execute))
    monkeypatch.setattr(store, 'state', actual_state)
    graph = store.graph
    async def graphs(c: AsyncConnection, who: str, run: str) -> list[dict[str, object]]:
        return original_graph if run == owner.run else await graph(c, who, run)
    monkeypatch.setattr(store, 'graph', graphs)
    monkeypatch.setattr(owner.handler.domain, 'readback', ManagedAdmission.readback.__get__(owner.handler.domain))
    monkeypatch.setattr(local_control, 'readiness_reason', AsyncMock(return_value=None))
    owner.handler.service.engine = owner.handler.domain.engine
    directory = ipc_directory / 'r'
    directory.mkdir(mode=0o700)
    host = RuntimeHost(directory)
    host.boot = str(owner.runtime.boot)
    host.state, host.generation, host.epoch = 'READY', 0, 1
    host.deadline_ns = time.monotonic_ns() + 4_000_000_000
    host.settings_result = settings.view(str(command.settings_operation_id), 'CONFIRMED', REQUESTED)
    host.peer = Mock(bootstrap_inventory={'schema_version':1, 'observation':'NATIVE_BOOTSTRAP', 'scope':'/state/active', 'registry':{'status':'NOT_INITIALIZED','generation':None,'count':None,'entries':None},'plugins':{'status':'NOT_INITIALIZED','count':None,'entries':None}})
    async def stop() -> None:
        host.state = 'STOPPED'
    monkeypatch.setattr(host, 'stop', stop)
    owner.runtime.directory = directory
    async with host:
        await owner.runtime.connect()
        assert (await owner.runtime.settings_status(str(command.settings_operation_id)))['status'] == 'CONFIRMED'
        assert (await owner.runtime.settings_status(str(uuid4())))['status'] == 'UNAVAILABLE'
        async with local_control.LocalControl(ipc_directory, owner.handler.service, owner.lease, 1, native_task=owner.handler.handle):
            answer = await control_task(ipc_directory, command.model_dump(mode='json'))
            assert canonical({k:v for k,v in answer.items() if k != 'correlation_id'}) == canonical(expected)
            import test_contract_method_pg as qa
            tree = ast.parse(Path(qa.__file__).read_bytes())
            loop = next(n for n in ast.walk(tree) if isinstance(n, ast.For) and any(isinstance(t, ast.Name) and t.id == 'mt_changed' for t in ast.walk(n.target)))
            before = canonical(owner.graph)
            async def census() -> bytes:
                return canonical(owner.graph)
            observation = Mock(read_bytes=lambda: canonical(owner.payloads))
            async def observed_control(directory: Path, value: object) -> dict[str, object]:
                try:
                    return await control_task(directory, value)
                except CatalogError as error:
                    assert error.reason in {'TASK_REJECTED', 'COMMAND_CONFLICT'}
                    print('PUBLIC_REASON', error.reason)
                    raise
            scope = {'pytest':pytest, 'CatalogError':CatalogError, 'control_task':observed_control, 'directory':ipc_directory, 'request_prepare':command.model_dump(mode='json'), 'lifecycle':command.model_dump(mode='json'), 'mapping':mapping, 'uuid4':uuid4, 'mission_census':census, 'after_tables':before, 'observation':observation, 'native_after':observation.read_bytes()}
            probe = ast.parse('async def probe(): pass').body[0]
            probe.body = [loop]
            exec(compile(ast.fix_missing_locations(ast.Module(body=[probe], type_ignores=[])), qa.__file__, 'exec'), scope)
            await scope['probe']()
            assert canonical(owner.graph) == before
        await owner.runtime.close()
    owner.native.assert_not_awaited()
    owner.reserve.assert_not_awaited()
