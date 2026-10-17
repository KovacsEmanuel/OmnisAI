"""Bounded SOURCE experiment: real UDS/client/Host/peer, synthetic native/storage.

No PG, installed Hermes, credentials or provider. No product timeout changed.
"""
import asyncio
import json
import time
from pathlib import Path
from unittest.mock import Mock
from uuid import uuid4

import pytest
from omnis.modules.instance.service import RuntimeAuthority
from omnis.modules.tasks.managed_contract import mapping
from omnis.supervisor.runtime_client import RuntimeUnavailable
from omnis_hermes import managed_admission_contract as contract
from omnis_hermes.runtime_host import RuntimeHost, TestLaunch as Launch
from omnis_hermes.runtime_protocol import NativePeer
from test_model_test_prepare_source import REQUESTED, prepared_source, produce

ROOT = Path('/home/kali/.hermes/cache/scratch/mtp-cancel-8vl5xa60')
PEER = Path('/home/kali/OmnisAI/integrations/hermes/tests/peer_fixture.py')


@pytest.mark.asyncio
@pytest.mark.parametrize('route,mode', [('client', 'normal'), ('client', 'slow_ready'), ('host', 'slow_ready')])
async def test_cancellation_producer(tmp_path, monkeypatch, route, mode):
    owner, consumer, conn, manifest, authority = await prepared_source(tmp_path, monkeypatch)
    payload = await produce(owner, consumer, conn, manifest, authority)
    runtime = owner.runtime
    directory = ROOT / ('i-' + uuid4().hex[:8])
    directory.mkdir(mode=0o700)
    import sys
    host = RuntimeHost(directory, _test_launch=Launch((sys.executable, '-I', '-B', str(PEER), mode), directory))
    host.boot = runtime.boot
    host.generation, host.epoch, host.state = 0, 1, 'MANAGEMENT'
    host.settings_task = Mock(done=Mock(return_value=True))
    context = mapping(mapping(payload['context'])['payload'])
    host.settings_result = {'status': 'CONFIRMED', 'operation_id': context['settings_operation_id'], 'selection': REQUESTED}
    events = []
    observed = {}
    original_stop, original_handshake, original_call = host.stop, NativePeer.handshake, NativePeer.call
    original_managed, original_connected = host._managed, host._managed_connected

    async def saved_read(action, selected):
        assert action == 'read' and selected is None
        events.append('SAVED_READ_ENTER')
        await asyncio.sleep(1.2)
        events.append('SAVED_READ_COMPLETED')
        return dict(REQUESTED)

    async def stop():
        events.append('STOP')
        if host.process is None:
            # No management subprocess in SOURCE; native cleanup below stays real.
            host.state = 'STOPPED'
        else:
            await original_stop()

    async def handshake(peer, *, ready_timeout=None):
        events.append('HANDSHAKE_ENTER')
        observed['ready_budget_s'] = ready_timeout
        try:
            result = await original_handshake(peer, ready_timeout=ready_timeout)
            events.append('HANDSHAKE_COMPLETED')
            return result
        except asyncio.CancelledError:
            events.append('HANDSHAKE_CANCELLED')
            observed['cancel_grant_remaining_ns'] = host.deadline_ns - time.monotonic_ns()
            observed['cancel_peer_failure'] = peer.failure is not None
            raise

    async def call(peer, method, params, *, timeout=None):
        if method != contract.RPC['task_model_initialize']:
            return await original_call(peer, method, params, timeout=timeout)
        events.append('SYNTHETIC_MODEL_REPLY')
        if params['mode'] == 'CLOSE':
            return {**params, 'status': 'CLOSED_JOINED'}
        return contract.preparation_result(payload, native_root_id=str(uuid4()), native_child_id=str(uuid4()), native_session_id='SOURCE-peer', native_turn={'task_id': context['task_id'], 'turn_id': 'SOURCE-turn'})

    async def managed(body):
        try:
            return await original_managed(body)
        except asyncio.CancelledError:
            events.append('MANAGED_CANCELLED')
            raise

    async def connected(body, reader):
        try:
            return await original_connected(body, reader)
        except ValueError as error:
            assert error.args == ('Managed owner disconnected',)
            events.append('MANAGED_OWNER_DISCONNECTED')
            observed['owner_eof'] = reader.at_eof()
            raise

    monkeypatch.setattr(host, '_settings_native', saved_read)
    monkeypatch.setattr(host, 'stop', stop)
    monkeypatch.setattr(host, '_managed', managed)
    monkeypatch.setattr(host, '_managed_connected', connected)
    monkeypatch.setattr(NativePeer, 'handshake', handshake)
    monkeypatch.setattr(NativePeer, 'call', call)
    runtime.directory = directory
    started = time.monotonic_ns()
    host.deadline_ns = started + 4_500_000_000
    deadline = started + 4_500_000_000
    grant = RuntimeAuthority(0, 1, deadline)
    try:
        async with host:
            await runtime.connect()
            try:
                if route == 'host':
                    answer = await host._managed({'payload': payload, 'op': 'task_model_initialize', 'epoch': 1, 'generation': 0, 'deadline_ns': deadline})
                else:
                    answer = (await runtime._exchange('task_model_initialize', grant, payload))['managed']
                assert answer['status'] == 'TURN_BOUND_PRE_CLIENT_HOLD'
                events.append('COMPLETED_SYNTHETIC')
                assert mode == 'normal' or route == 'host'
            except RuntimeUnavailable as error:
                assert route == 'client' and mode == 'slow_ready'
                # The primary local context is the real exchange timeout, not a
                # manually injected CancelledError or a Host/peer timeout.
                assert type(error.__context__) is TimeoutError
                frames = []
                cursor = error.__context__.__traceback__
                while cursor is not None:
                    frames.append(cursor.tb_frame.f_code)
                    cursor = cursor.tb_next
                assert type(runtime)._exchange_locked.__code__ in frames
                observed['primary'] = 'RUNTIME_CLIENT_EXCHANGE_TIMEOUT'
                events.append('CLIENT_TIMEOUT')
            await runtime.close()
            async with asyncio.timeout(1):
                while host.owner_writer is not None:
                    await asyncio.sleep(0.005)
            await host.stop()
            if route == 'client' and mode == 'slow_ready':
                assert observed['owner_eof'] is True
                assert observed['cancel_grant_remaining_ns'] > 0
                assert observed['cancel_peer_failure'] is False
                assert events.index('CLIENT_TIMEOUT') < events.index('HANDSHAKE_CANCELLED')
                assert events.index('HANDSHAKE_CANCELLED') < events.index('MANAGED_OWNER_DISCONNECTED')
                assert 'SYNTHETIC_MODEL_REPLY' not in events
            else:
                assert 'HANDSHAKE_COMPLETED' in events
                assert 'HANDSHAKE_CANCELLED' not in events
            assert host.process is not None and host.process.returncode is not None
            assert not Path(f'/proc/{host.process.pid}').exists()
    finally:
        await runtime.close()
        await host.__aexit__(None, None, None)
    assert not host.clients and not (directory / 'runtime.sock').exists()
    assert not (directory / 'runtime.boot').exists()
    (ROOT / f'{route}-{mode}.json').write_text(json.dumps({'scope': 'SOURCE_SYNTHETIC_NOT_NATIVE_ACCEPTANCE', 'route': route, 'peer': mode, 'events': events, 'observation': observed, 'elapsed_ns': time.monotonic_ns()-started, 'owned_process_reaped': True, 'owned_endpoints_absent': True}, indent=2)+'\n')
