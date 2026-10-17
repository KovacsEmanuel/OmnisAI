"""One SOURCE causal probe: extracted QA callback + real owner/control UDS.

No PostgreSQL/native/provider is started. Existing SOURCE fixtures supply storage;
only SQL UUID decoding is real psycopg, and only control.sock is a real channel.
"""
import ast
import asyncio
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

ROOT = Path('/home/kali/OmnisAI')
OUT = Path(__file__).resolve().parent
os.umask(0o077)
os.environ['TMPDIR'] = str(OUT)
sys.path[:0] = [str(ROOT / p) for p in ('api/src', 'api/tests', 'integrations/hermes/src')]

import pytest
import psycopg
from psycopg.pq import Format
from sqlalchemy import UUID as SA_UUID, text as sql
from sqlalchemy.dialects.postgresql.psycopg import PGDialect_psycopg
from sqlalchemy.engine.result import IteratorResult, SimpleResultMetaData
import sqlalchemy
from omnis.modules.instance.service import RuntimeAuthority
from omnis.modules.runs.model_test import ModelTest, REQUESTED
from omnis.modules.settings import candidate_store as stored
from omnis.modules.settings.catalog_models import CatalogError
from omnis.modules.settings.catalog_schema import canonical
from omnis.modules.tasks import managed_store
from omnis.modules.tasks.managed_contract import mapping
from omnis.supervisor.native_tasks import control_task
from omnis.supervisor.runtime_client import RuntimeClient
from omnis.transport import local_control
from omnis_hermes.managed_admission_contract import preparation_result
from test_model_test_prepare_source import prepared_source

# Guard effects at the seams actually used; this is not a universal sandbox.
def no_external(event, args):
    if event in ('subprocess.Popen', 'os.system', 'os.posix_spawn', 'os.exec'):
        raise RuntimeError('FORBIDDEN_PROCESS')
    if event == 'socket.connect':
        address = args[1]
        if not isinstance(address, (str, bytes)):
            raise RuntimeError('FORBIDDEN_NETWORK')
        if not os.fsdecode(address).startswith(str(OUT) + '/'):
            raise RuntimeError('FORBIDDEN_UNOWNED_UDS')
sys.addaudithook(no_external)

SOURCE = ROOT / 'api/tests/test_contract_method_pg.py'
source_bytes = SOURCE.read_bytes()
callback = [n for n in ast.walk(ast.parse(source_bytes))
            if isinstance(n, ast.AsyncFunctionDef) and n.name == 'committed_prepare']
assert len(callback) == 1
callback = callback[0]
assert callback.lineno == 9733 and callback.end_lineno == 9790


def compile_callback(namespace, normalize):
    node = copy.deepcopy(callback)
    if normalize:
        changed = 0
        for part in ast.walk(node):
            if isinstance(part, ast.Compare) and part.lineno in (9778, 9779):
                part.left = ast.Call(func=ast.Name(id='str', ctx=ast.Load()),
                                     args=[part.left], keywords=[])
                changed += 1
        assert changed == 2
    tree = ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[]))
    exec(compile(tree, str(SOURCE), 'exec'), namespace)
    return namespace['committed_prepare']


def frames(error):
    answer = []
    tb = BaseException.__dict__['__traceback__'].__get__(error)
    allowed = {
        str(SOURCE): 'QA_CALLBACK',
        str(ROOT / 'api/src/omnis/supervisor/native_tasks.py'): 'NATIVE_TASK_OWNER',
        str(ROOT / 'api/src/omnis/supervisor/runtime_client.py'): 'RUNTIME_CLIENT',
        str(ROOT / 'api/src/omnis/transport/local_control.py'): 'LOCAL_CONTROL',
        str(Path(__file__).resolve()): 'SOURCE_PROBE',
    }
    while tb is not None:
        if tb.tb_frame.f_code.co_filename in allowed:
            answer.append({'code': allowed[tb.tb_frame.f_code.co_filename], 'line': tb.tb_lineno})
        tb = tb.tb_next
    return answer


async def case(name, normalize=False, row_kind='uuid', wrong_run=False):
    root = OUT / ('r4-' + name)
    root.mkdir(mode=0o700)
    result = {'case': name, 'scope': 'SOURCE_STORAGE_REAL_CONTROL_UDS',
              'candidate_callback_normalization': normalize, 'row_kind': row_kind,
              'wrong_run': wrong_run, 'checkpoints': [], 'exchange_calls': 0,
              'server_errors': []}
    with pytest.MonkeyPatch.context() as patch:
        owner, consumer, conn, manifest, authority = await prepared_source(root, patch)
        domain, service, runtime = owner.handler.domain, owner.handler.service, owner.runtime
        service.engine = domain.engine
        owner.base.update(owner_id=owner.owner, manifest_ref=manifest)
        patch.setattr(domain, 'readback', AsyncMock(return_value={'manifest_ref': manifest}))
        command = {**owner.base, 'action': 'model_test_prepare',
                   'settings_operation_id': str(uuid4()), 'initialization_id': str(uuid4())}
        patch.setattr(runtime, 'settings_status', AsyncMock(return_value={
            'status': 'CONFIRMED', 'selection': REQUESTED,
            'authenticated': 'NOT_VERIFIED', 'inference_ready': False}))
        patch.setattr(service, 'runtime_authority', AsyncMock(return_value=RuntimeAuthority(
            generation=0, epoch=1, deadline_ns=time.monotonic_ns() + 3_000_000_000)))
        patch.setattr(runtime, 'managed', RuntimeClient.managed.__get__(runtime, RuntimeClient))
        patch.setattr(local_control, 'readiness_reason', AsyncMock(return_value=None))
        patch.setattr(psycopg, 'connect', lambda *a, **kw: (_ for _ in ()).throw(
            RuntimeError('FORBIDDEN_DATABASE')))

        @asynccontextmanager
        async def connection():
            yield conn
        patch.setattr(domain.engine, 'connect', connection)
        loader = psycopg.adapters.get_loader(2950, Format.TEXT)(2950)

        async def execute(statement, params=None):
            statement_text = str(statement)
            if statement_text.startswith('SELECT task_id,attempt_id,run_id,batch_index,state'):
                context = next(r for r in owner.graph if r['kind'] == 'model-test-context')
                c = mapping(context['payload'])
                raw = [c['task_id'], c['attempt_id'], c['run_id']]
                values = [loader.load(v.encode()) for v in raw]
                assert all(type(v) is UUID for v in values)
                assert all(str(v) == s for v, s in zip(values, raw, strict=True))
                if wrong_run:
                    values[2] = loader.load(str(uuid4()).encode())
                if row_kind == 'string':
                    values = [str(v) for v in values]
                result['row_types'] = [type(v).__name__ for v in values]
                result['context_types'] = [type(v).__name__ for v in raw]
                result['identifier_values_equal_after_str'] = [
                    str(v) == s for v, s in zip(values, raw, strict=True)]
                return IteratorResult(SimpleResultMetaData(
                    ['task_id', 'attempt_id', 'run_id', 'batch_index', 'state']),
                    iter([(*values, 0, 'QUEUED')]))
            return SimpleNamespace(scalar_one=lambda: owner.instance)
        conn.execute.side_effect = execute

        async def exchange(op, authority=None, payload=None):
            assert op == 'task_model_initialize' and payload['mode'] == 'CREATE'
            assert owner.events[-1] == 'commit'
            result['exchange_calls'] += 1
            c = mapping(mapping(payload['context'])['payload'])
            return {'managed': preparation_result(payload,
                native_root_id=str(uuid4()), native_child_id=str(uuid4()),
                native_session_id='SOURCE-NO-NATIVE',
                native_turn={'task_id': c['task_id'], 'turn_id': 'SOURCE-NO-TURN'})}

        def checkpoint(**values):
            assert values == {'model_prepare_commit': 'INDEPENDENT_PG_READ_BEFORE_ORIGINAL_EXCHANGE'}
            result['checkpoints'].append('SOURCE_CALLBACK_COMMIT_CHECK_REACHED')
        namespace = dict(globals(), runtime=runtime, domain=domain, engine=domain.engine,
                         seed=SimpleNamespace(owner=owner.owner), prepared={'run_id': owner.run},
                         status=SimpleNamespace(instance_id=UUID(owner.instance), generation=0),
                         supervisor=owner.lease, epoch=1, request_prepare=command,
                         actual_exchange=exchange, modes=[], checkpoint=checkpoint)
        patch.setattr(runtime, '_exchange', compile_callback(namespace, normalize))
        loop = asyncio.get_running_loop()
        old_handler = loop.get_exception_handler()
        def handler(_loop, context):
            error = context.get('exception')
            assert isinstance(error, BaseException)
            result['server_errors'].append({'exception': type(error).__name__, 'frames': frames(error)})
        loop.set_exception_handler(handler)
        control_dir = root / 'ctl'
        control_dir.mkdir(mode=0o700)
        try:
            async with local_control.LocalControl(control_dir, service, owner.lease, 1,
                                                  native_task=owner.handler.handle):
                try:
                    answer = await control_task(control_dir, command)
                    result['client'] = {'tag': 'REPLY', 'ok': answer['ok'],
                                        'preparation_status': answer['preparation_status']}
                except CatalogError as error:
                    context = BaseException.__dict__['__context__'].__get__(error)
                    result['client'] = {'tag': 'CATALOG_ERROR', 'reason': error.reason,
                        'context': type(context).__name__ if context is not None else None,
                        'frames': frames(error)}
                await asyncio.sleep(0)
            await asyncio.sleep(0)
        finally:
            loop.set_exception_handler(old_handler)
            await runtime.close()
        owner.reserve.assert_not_awaited()
        owner.native.assert_not_awaited()
        result['modes'] = namespace['modes']
        result['control_cleanup'] = not (control_dir/'control.sock').exists() and not (control_dir/'control.cap').exists()
        result['inference_reservations'] = 0
        result['real_native_calls'] = 0
        return result


async def main():
    dialect = PGDialect_psycopg()
    processor = dialect.type_descriptor(SA_UUID()).result_processor(dialect, 2950)
    assert processor is None
    binary = psycopg.adapters.get_loader(2950, Format.BINARY)(2950)
    text_loader = psycopg.adapters.get_loader(2950, Format.TEXT)(2950)
    sample = UUID('00000000-0000-4000-8000-000000000001')
    assert binary.load(sample.bytes) == text_loader.load(str(sample).encode()) == sample
    results = [await case('raw-uuid'), await case('raw-string', row_kind='string'),
               await case('normalized', normalize=True),
               await case('wrong-uuid', normalize=True, wrong_run=True)]
    (OUT/'probe4-cases.json').write_text(json.dumps(results, indent=2)+'\n')
    for entry in (results[0], results[3]):
        assert entry['client']['reason'] == 'TASK_REJECTED'
        assert entry['client']['context'] == 'IncompleteReadError'
        assert entry['exchange_calls'] == 0 and entry['checkpoints'] == []
        assert len(entry['server_errors']) == 1
        assert entry['server_errors'][0]['exception'] == 'AssertionError'
        assert {'code': 'QA_CALLBACK', 'line': 9778} in entry['server_errors'][0]['frames']
    for entry in (results[1], results[2]):
        assert entry['client'] == {'tag': 'REPLY', 'ok': True,
                                  'preparation_status': 'TURN_BOUND_PRE_CLIENT_HOLD'}
        assert entry['exchange_calls'] == 1 and not entry['server_errors']
        assert entry['checkpoints'] == ['SOURCE_CALLBACK_COMMIT_CHECK_REACHED']
    assert all(r['control_cleanup'] and r['modes'] == ['CREATE'] for r in results)
    record = {'verdict': 'CONFIRMED_SOURCE_CAUSAL_REPRO_NOT_LIVE_ATTRIBUTION',
              'callback_source_sha256': hashlib.sha256(source_bytes).hexdigest(),
              'callback_lines': [9733, 9790], 'python': sys.version.split()[0],
              'psycopg': psycopg.__version__, 'sqlalchemy': sqlalchemy.__version__,
              'psycopg_default_uuid_loaders': ['UUIDLoader', 'UUIDBinaryLoader'],
              'sqlalchemy_uuid_result_processor': None, 'cases': results}
    (OUT/'probe-results.json').write_text(json.dumps(record, indent=2)+'\n')
    print(json.dumps({'tag': 'CAUSAL_PROBE_PASS', 'cases': len(results),
                      'result': str(OUT/'probe-results.json')}))

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except BaseException as error:
        (OUT/'probe4-failure.json').write_text(json.dumps(
            {'tag': 'PROBE_FAILED', 'exception': type(error).__name__, 'frames': frames(error)},
            indent=2)+'\n')
        print(json.dumps({'tag': 'PROBE_FAILED', 'exception': type(error).__name__}))
        raise SystemExit(1) from None
