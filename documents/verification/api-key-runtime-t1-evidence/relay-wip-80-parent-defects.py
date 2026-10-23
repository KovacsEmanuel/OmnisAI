"""Three focused SOURCE diagnostics; no PG, provider/TCP or Cancel oracle."""
import asyncio
import importlib
import json
import socket
import ssl
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch
from uuid import uuid4

BASE = Path('/home/kali/.hermes/cache/scratch/ot1-0zxf62th')
SOURCE = BASE / 'model-review-80'
sys.path[:0] = [str(SOURCE / 'api/src'), str(SOURCE / 'cli/src')]
from anyio import EndOfStream
from anyio.abc import ByteStream
from omnis.supervisor.model_relay import Relay, RelayFailure
from omnis.supervisor.model_relay_protocol import Scope, decode, encode
from omnis.supervisor.model_sender import Stream, TLSStream

forwarder = importlib.import_module('omnis_cli.forwarder')
assert Path(importlib.import_module('omnis.supervisor.model_relay').__file__).is_relative_to(SOURCE)
assert Path(forwarder.__file__).is_relative_to(SOURCE)


def scope():
    return Scope(str(uuid4()), 'METADATA_COMMAND', str(uuid4()), str(uuid4()),
                 1, 1, 1, (datetime.now(UTC) + timedelta(seconds=30)).isoformat(), 'openrouter')


async def main():
    result = {'scope': 'SOURCE_80_DIAGNOSTIC_NOT_PG_TLS_CONSUMER_QA'}
    with tempfile.TemporaryDirectory(prefix='p80-', dir=BASE) as name:
        root = Path(name)
        root.chmod(0o700)
        channel = root / 'model-egress.sock'
        assert len(bytes(channel)) <= 107
        broker = await forwarder.start_auth_forwarder(root, model=True)
        try:
            first = Relay(channel)
            with patch.object(socket, 'getaddrinfo', side_effect=socket.gaierror(-2, 'synthetic DNS outage')) as dns:
                try:
                    await first.rpc('OPEN', scope(), str(uuid4()), timeout=2.5)
                except RelayFailure as error:
                    assert str(error) == 'RELAY_CONTROL_UNCERTAIN' and first.failed
                else:
                    raise AssertionError('Expected actual DNS/control defect')
                assert dns.call_count == 1
            second = Relay(channel)
            answer = [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, '', ('8.8.8.8', 443))]
            with patch.object(socket, 'getaddrinfo', return_value=answer) as dns:
                try:
                    await second.rpc('OPEN', scope(), str(uuid4()), timeout=2.5)
                except RelayFailure:
                    assert second.failed and dns.call_count == 0
                else:
                    raise AssertionError('Expected OPEN left live/busy')
            result['dns'] = {'first_control_latched': True, 'healthy_explicit_open_denied_before_lookup': True}
        finally:
            broker.close()
            await broker.wait_closed()
        assert not channel.exists()

    tls = []
    for error in (EndOfStream(), ssl.SSLCertVerificationError(1, 'synthetic TLS verify failure'), TimeoutError()):
        raw = AsyncMock(spec=ByteStream)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        with patch.object(TLSStream, 'wrap', new=AsyncMock(side_effect=error)):
            try:
                await Stream(raw).start_tls(context, 'openrouter.ai', timeout=1)
            except type(error):
                assert raw.aclose.await_count == 0
            else:
                raise AssertionError('Expected handshake failure')
        tls.append({'error': type(error).__name__, 'raw_close_count': raw.aclose.await_count})
    result['tls'] = tls

    with tempfile.TemporaryDirectory(prefix='a80-', dir=BASE) as name:
        root = Path(name)
        root.chmod(0o700)
        channel = root / 'model-egress.sock'
        assert len(bytes(channel)) <= 107
        (root / 'model-relay.cap').write_text('a' * 64)
        (root / 'model-relay.cap').chmod(0o600)
        mode = 'version'

        async def reply(reader, writer):
            try:
                request = decode(await reader.readline())
                value = {k: request[k] for k in ('version', 'request_id', 'connection_id', 'scope', 'sequence')}
                if mode == 'scope':
                    value['scope'] = {**value['scope'], 'owner_epoch': True}
                else:
                    value[mode] = True
                writer.write(encode({**value, 'status': 'OK', 'size': 0}))
                await writer.drain()
            finally:
                writer.close()
                await writer.wait_closed()

        server = await asyncio.start_unix_server(reply, channel, cleanup_socket=True)
        channel.chmod(0o600)
        accepted = []
        try:
            for mode in ('version', 'sequence', 'scope'):
                relay = Relay(channel)
                status, payload = await relay.rpc('FENCE', scope(), sequence=1)
                assert status == 'OK' and payload == b'' and not relay.failed
                accepted.append(mode)
        finally:
            server.close()
            await server.wait_closed()
        assert not channel.exists()
        result['malformed_bool_ack_accepted'] = accepted
    print(json.dumps(result, indent=2))


asyncio.run(main())
