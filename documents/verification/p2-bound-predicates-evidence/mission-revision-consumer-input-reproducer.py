"""Independent SOURCE-only probes; no DB, IPC, native or provider calls."""
import asyncio
from contextlib import asynccontextmanager
from copy import deepcopy
from hashlib import sha256
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4
import sys
sys.path.insert(0, '/home/kali/OmnisAI/api/src')
sys.path.insert(0, '/home/kali/OmnisAI/api/tests')
import pytest
from test_c04_criteria import criteria_graph
from test_mission_revisions import SQLDouble
from omnis.modules.runs.contract_inputs import ContractInputs, main
from omnis.modules.tasks import managed_contract as contract
from omnis.modules.tasks import managed_store as store
from omnis.modules.settings import candidate_store as records
from omnis.modules.settings.catalog_schema import canonical
from omnis.modules.settings.catalog_models import CatalogError
from omnis.modules.instance.schemas import NativeTaskCommand
from omnis.supervisor.native_tasks import NativeTaskOwner


def fixture():
    graph = criteria_graph([str(uuid4())])
    context = next(r for r in graph if r['kind'] == 'contract-input-context')
    context['payload']['version'] = 2
    context['digest'] = sha256(canonical({k:v for k,v in context.items() if k!='digest'})).hexdigest()
    body = context['payload']
    conn = SQLDouble(body['owner_id'], body['basis_ref']['id'], graph)
    inputs = ContractInputs(conn)
    calls = []
    async def qualified(*args):
        calls.append('source')
        return SimpleNamespace(procedure=SimpleNamespace(key='map-records', verification_kind='CONTRACT'))
    inputs.current_source = qualified
    req = dict(schema_version=1, owner_id=conn.owner, command_id=str(uuid4()), context_ref=records.reference(context), mission_ref=body['mission_ref'], criterion_id=str(uuid4()))
    return conn, inputs, req, calls


@pytest.mark.asyncio
async def test_strict_first_write_existing_receipt_same_service():
    conn, inputs, req, calls = fixture()
    attacks = []
    for key in ('schema_version','owner_id','command_id','criterion_id','context_ref','mission_ref'):
        for value in (True, False, 1.0, None, [], {}, 2**64):
            attacks.append({**req, key:value})
    for key in ('context_ref','mission_ref'):
        for field in ('kind','id','revision','digest'):
            for value in (True, 1.0, None, [], {}, '\x00', '\ud800'):
                attacks.append({**req, key:{**req[key],field:value}})
    for key in ('owner_id','command_id','criterion_id'):
        for value in (req[key].upper(), req[key].replace('-',''), '{'+req[key]+'}'):
            if value != req[key]:
                attacks.append({**req,key:value})
    for existing in (False, True):
        if existing:
            assert (await inputs.append_mission(req))['created'] is True
            assert len(calls)==1
        before=canonical(conn.graph)
        write_count=len(conn.writes)
        for attack in attacks:
            with pytest.raises(CatalogError):
                await inputs.append_mission(attack)
            assert canonical(conn.graph)==before
            assert len(conn.writes)==write_count
        if existing:
            async def no_qualification(*args):
                raise AssertionError('historical replay reevaluated qualification')
            inputs.current_source=no_qualification
            assert (await inputs.append_mission(req))['created'] is False
            back=await inputs.read('read-mission',{k:req[k] for k in ('schema_version','owner_id','command_id')})
            assert back['mission']['revision']==2
            assert canonical(conn.graph)==before
            with pytest.raises(CatalogError,match='MISSION_REVISION_CONFLICT'):
                await inputs.append_mission({**req,'command_id':str(uuid4())})


@pytest.mark.parametrize('raw',[
    b'\xef\xbb\xbf{}', '{}'.encode('utf-16'), b'{"schema_version":1,"schema_version":1}',
    b'{"context_ref":{"id":"a","id":"a"}}', b'{"schema_version":1.0}',
    b'{"schema_version":NaN}', b'{"owner_id":"\\ud800"}', b'\xff',
])
def test_cli_malformed_bytes_sanitized_before_database(tmp_path, monkeypatch, capsys, raw):
    import omnis.modules.runs.contract_inputs as module
    def forbid_engine(*args):
        raise AssertionError('malformed request reached database_engine')
    monkeypatch.setattr(module,'database_engine',forbid_engine)
    monkeypatch.setenv('OMNIS_DATABASE_URL','synthetic-non-dsn-marker')
    path=tmp_path/'request.json'
    path.write_bytes(raw)
    assert main(['append-mission','--request',str(path)])==2
    output=capsys.readouterr()
    assert output.out==''
    assert 'Traceback' not in output.err and 'synthetic-non-dsn-marker' not in output.err
    assert '"status":"BLOCKED"' in output.err


@pytest.mark.asyncio
async def test_m2_append_must_fence_stage_after_dispatch_transaction_commit():
    """Product owner, real append + SOURCE SQL/domain/service/sink doubles.

    Inject M2 only after the reservation transaction exits and BEFORE task_stage.
    A matching M1 positive and M2 negative use the SAME product owner channel.
    """
    for interleave in (False, True):
        conn, inputs, req, calls=fixture()
        manifest=next(r for r in conn.graph if r['kind']=='launch-manifest')
        ref=records.reference(manifest)
        instance=str(uuid4())
        supervisor=uuid4()
        events=[]
        domain=Mock()
        domain.readback=AsyncMock(return_value={'manifest_ref':ref,'manifest':manifest,'binding':None,'results':[],'stage_started':False,'release_started':False})
        async def material(*args):
            from omnis.modules.tasks.mission_revisions import require_no_revision
            require_no_revision(await store.graph(conn,conn.owner,conn.run))
            events.append('validated-M1')
            return {'protocol':'omnis-managed-admission-v4','manifest':manifest}
        domain.stage_payload=material
        async def reserve(*args):
            await material()
            events.append('dispatch-reserved')
            return manifest
        domain.reserve_dispatch=reserve
        domain.commit_binding=AsyncMock(return_value=records.envelope('runtime-binding',{}))
        identity=SimpleNamespace(scalar_one=lambda:instance)
        owner_conn=SimpleNamespace(execute=AsyncMock(return_value=identity))
        @asynccontextmanager
        async def fence(*args):
            yield owner_conn
            if interleave and not events.count('M2-committed'):
                assert (await inputs.append_mission(req))['created'] is True
                events.append('M2-committed')
        service=SimpleNamespace(native_preparation_commit=fence)
        async def fake_sink(*args):
            events.append('task_stage-sink')
            return {'synthetic':True}
        runtime=SimpleNamespace(boot=str(uuid4()),managed=fake_sink)
        command=NativeTaskCommand(op='native_task',schema_version=1,owner_id=conn.owner,command_id=str(uuid4()),instance_id=instance,expected_generation=0,expected_epoch=1,action='stage',manifest_ref=ref)
        owner=NativeTaskOwner(domain,service,supervisor,1,runtime)
        await owner.handle(command)
        if not interleave:
            assert events.count('task_stage-sink')==1
        else:
            assert 'M2-committed' in events
            assert 'task_stage-sink' not in events, 'M2 committed before task_stage but owner still invoked native sink'
