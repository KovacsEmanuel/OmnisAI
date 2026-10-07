"""Synthetic wire tests; not native Hermes certification."""

import asyncio
import importlib.util
import json
import sys
from pathlib import Path

import pytest


def protocol():
    assert importlib.util.find_spec("omnis_hermes") is not None, "installable adapter missing"
    from omnis_hermes import runtime_protocol

    return runtime_protocol


@pytest.mark.asyncio
async def test_real_peer_handshake_reverse_denial_and_no_arbitrary_write():
    wire = protocol()
    assert hasattr(wire, "NativePeer"), "bounded native peer missing"
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        str(Path(__file__).with_name("peer_fixture.py")),
        "reverse",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        limit=wire.MAX_FRAME,
    )
    peer = wire.NativePeer(process)
    try:
        capabilities = await peer.handshake()
        assert capabilities["per_session_exclusive_submit"] is True
        with pytest.raises(wire.ProtocolError):
            await peer.call("session.create", {})
        assert await peer.call("ping", {}) == {"pong": True}
        await asyncio.sleep(0.05)
        events = list(peer.events)
        responses = [
            event["payload"] for event in events if event.get("type") == "fixture.response"
        ]
        assert {response["id"] for response in responses} == {"srq-approval", "srq-unknown"}
        approval = next(response for response in responses if response["id"] == "srq-approval")
        assert approval["result"] == {"choice": "deny"}
        unknown = next(response for response in responses if response["id"] == "srq-unknown")
        assert unknown["error"]["code"] == -32601
        assert list(peer.cancelled) == [("srq-approval", "approval")]
    finally:
        process.kill()
        await process.wait()
        await peer.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["ready_stall", "stall", "eof", "oversized", "stderr"])
async def test_real_peer_faults_are_bounded_and_stderr_is_not_retained(mode):
    wire = protocol()
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        str(Path(__file__).with_name("peer_fixture.py")),
        mode,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        limit=wire.MAX_FRAME,
    )
    peer = wire.NativePeer(process, timeout=0.2)
    try:
        async with asyncio.timeout(2):
            if mode == "ready_stall":
                with pytest.raises(wire.ProtocolError):
                    await peer.handshake()
            else:
                await peer.handshake()
                if mode == "stderr":
                    assert await peer.call("ping", {}) == {"pong": True}
                    assert "synthetic_sensitive_marker" not in repr(peer.__dict__)
                elif mode == "stall":
                    calls = [asyncio.create_task(peer.call("ping", {})) for _ in range(32)]
                    await asyncio.sleep(0.02)
                    assert len(peer.pending) == 32
                    with pytest.raises(wire.ProtocolError, match="Pending limit"):
                        await peer.call("ping", {})
                    results = await asyncio.gather(*calls, return_exceptions=True)
                    assert all(isinstance(result, wire.ProtocolError) for result in results)
                    assert not peer.pending
                else:
                    with pytest.raises(wire.ProtocolError):
                        await peer.call("ping", {})
    finally:
        if process.returncode is None:
            process.kill()
        await asyncio.wait_for(process.wait(), 2)
        await peer.close()


@pytest.mark.asyncio
async def test_startup_wait_has_separate_budget_from_per_rpc_deadline():
    wire = protocol()
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        str(Path(__file__).with_name("peer_fixture.py")),
        "ready_delay",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    peer = wire.NativePeer(process, timeout=0.1)
    try:
        try:
            capabilities = await peer.handshake(ready_timeout=0.5)
        except TypeError:
            pytest.fail("separate startup budget is missing")
        assert capabilities["per_session_exclusive_submit"] is True
    finally:
        if process.returncode is None:
            process.kill()
        await asyncio.wait_for(process.wait(), 2)
        await peer.close()


def test_native_frames_require_unique_jsonrpc_and_exact_ids():
    wire = protocol()
    valid = {"jsonrpc": "2.0", "id": 1, "result": {}}
    assert wire.decode(wire.encode(valid)) == valid
    for raw in (
        b'{"jsonrpc":"2.0","id":1,"id":2,"result":{}}\n',
        b'{"jsonrpc":"2.0","id":true,"result":{}}\n',
        b'{"jsonrpc":"1.0","id":1,"result":{}}\n',
        b'{"jsonrpc":"2.0","id":null,"result":{}}\n',
        b'{"jsonrpc":"2.0","id":1,"result":{},"error":{}}\n',
        b'{"jsonrpc":"2.0","method":"ping","params":{"a":1,"a":2}}\n',
        b'{"jsonrpc":"2.0","id":1,"result":NaN}\n',
        b'{"jsonrpc":"2.0","id":1,"result":1e400}\n',
    ):
        with pytest.raises(wire.ProtocolError):
            wire.decode(raw)
    with pytest.raises(wire.ProtocolError):
        wire.decode(json.dumps({**valid, "result": "x" * 65536}).encode() + b"\n")
