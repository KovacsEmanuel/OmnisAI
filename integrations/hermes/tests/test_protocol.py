"""Synthetic wire tests; not native Hermes certification."""

import asyncio
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import cast

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


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["approval", "unknown"])
async def test_sequential_reverse_replies_retire_pending_without_cancellation(method):
    wire = protocol()
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        str(Path(__file__).with_name("peer_fixture.py")),
        f"reverse_sequential_{method}",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        limit=wire.MAX_FRAME,
    )
    peer = wire.NativePeer(process)
    try:
        async with asyncio.timeout(5):
            await peer.handshake()
            for index in range(1, 66):
                result = await peer.call("ping", {})
                assert isinstance(result, dict)
                assert result["pong"] is True
                reply = result["reverse_reply"]
                assert reply["id"] == f"srq-{index}"
                if method == "approval":
                    assert reply["result"] == {"choice": "deny"}
                else:
                    assert reply["error"]["code"] == -32601
            assert peer.failure is None
            assert not peer.reverse
            assert set(peer.reverse_done) == {(str, f"srq-{index}") for index in range(34, 66)}
            assert not peer.cancelled
    finally:
        if process.returncode is None:
            process.kill()
        await asyncio.wait_for(process.wait(), 2)
        await peer.close()


class DrainControlledInput:
    """Flow-control seam: the real reader/writer run, drain is test-owned."""

    def __init__(self):
        self.release = asyncio.Event()
        self.entered = asyncio.Event()
        self.writes = []

    def write(self, raw):
        self.writes.append(raw)

    async def drain(self):
        self.entered.set()
        await self.release.wait()

    def close(self):
        pass

    async def wait_closed(self):
        pass


async def controlled_peer():
    wire = protocol()
    writer = DrainControlledInput()
    reader = asyncio.StreamReader()
    stderr = asyncio.StreamReader()
    stderr.feed_eof()
    process = cast(
        asyncio.subprocess.Process, SimpleNamespace(stdin=writer, stdout=reader, stderr=stderr)
    )
    peer = wire.NativePeer(process)
    reader.feed_data(
        wire.encode(
            {
                "jsonrpc": "2.0",
                "method": "event",
                "params": {
                    "type": "gateway.ready",
                    "payload": {
                        "bootstrap_inventory": {
                            "schema_version": 1,
                            "observation": "NATIVE_BOOTSTRAP",
                            "scope": "/state/active",
                            "registry": {
                                "status": "NOT_INITIALIZED",
                                "generation": None,
                                "count": None,
                                "entries": None,
                            },
                            "plugins": {
                                "status": "NOT_INITIALIZED",
                                "count": None,
                                "entries": None,
                            },
                        }
                    },
                },
            }
        )
    )
    await asyncio.wait_for(peer.ready, 1)
    return wire, peer, reader, writer


async def settled(predicate):
    async with asyncio.timeout(1):
        while not predicate():
            await asyncio.sleep(0)


def cancel_frame(request_id, method="approval"):
    return {
        "jsonrpc": "2.0",
        "method": "event",
        "params": {"type": "request.cancel", "payload": {"id": request_id, "method": method}},
    }


async def feed_through_barrier(wire, peer, reader, frames):
    for frame in frames:
        reader.feed_data(wire.encode(frame))
    reader.feed_data(
        wire.encode({"jsonrpc": "2.0", "method": "event", "params": {"type": "fixture.barrier"}})
    )
    await settled(
        lambda: (
            peer.failure is not None
            or (bool(peer.events) and peer.events[-1].get("type") == "fixture.barrier")
        )
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("cancel_pending", [False, True])
async def test_reverse_pending_saturation_includes_undrained_cancelled_reply(cancel_pending):
    wire, peer, reader, writer = await controlled_peer()
    try:
        assert wire.MAX_PENDING == 32
        requests = [
            {"jsonrpc": "2.0", "id": index, "method": "approval", "params": {}}
            for index in range(32)
        ]
        await feed_through_barrier(wire, peer, reader, requests)
        await asyncio.wait_for(writer.entered.wait(), 1)
        assert len(peer.reverse) == 32
        assert len(writer.writes) == 1  # One in-flight, 31 queued, none drained.
        assert peer.queued_bytes > 0
        if cancel_pending:
            peer.events.clear()
            await feed_through_barrier(wire, peer, reader, [cancel_frame(0)])
            assert list(peer.cancelled) == [(0, "approval")]
            assert len(peer.reverse) == 32
        peer.events.clear()
        await feed_through_barrier(
            wire, peer, reader, [{"jsonrpc": "2.0", "id": 32, "method": "approval"}]
        )
        assert peer.failure is not None
        assert len(peer.reverse) == 32
        assert len(writer.writes) == 1
    finally:
        await peer.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "action",
    [
        "matching",
        "mismatch",
        "duplicate",
        "unknown",
        "wrong_type",
        "invalid",
        "replay",
        "cancel_replay",
    ],
)
async def test_completed_reverse_ids_correlate_late_cancels_and_reject_replays(action):
    wire, peer, reader, writer = await controlled_peer()
    request = {"jsonrpc": "2.0", "id": 7, "method": "approval", "params": {}}
    try:
        reader.feed_data(wire.encode(request))
        await asyncio.wait_for(writer.entered.wait(), 1)
        assert peer.reverse == {(int, 7): "approval"}
        assert not peer.reverse_done
        writer.release.set()
        await settled(lambda: peer.queued_bytes == 0)
        assert not peer.reverse
        assert wire.decode(writer.writes[0])["result"] == {"choice": "deny"}
        if action in {"duplicate", "cancel_replay"}:
            await feed_through_barrier(wire, peer, reader, [cancel_frame(7)])
            assert list(peer.cancelled) == [(7, "approval")]
            assert peer.failure is None
            peer.events.clear()
        frame = {
            "matching": cancel_frame(7),
            "mismatch": cancel_frame(7, "untrusted.method"),
            "duplicate": cancel_frame(7),
            "unknown": cancel_frame(8),
            "wrong_type": cancel_frame("7"),
            "invalid": cancel_frame(True),
            "replay": request,
            "cancel_replay": request,
        }[action]
        await feed_through_barrier(wire, peer, reader, [frame])
        if action == "matching":
            assert peer.failure is None
            assert list(peer.cancelled) == [(7, "approval")]
            assert not peer.reverse
        else:
            assert peer.failure is not None
        assert len(writer.writes) == 1
    finally:
        await peer.close()


@pytest.mark.asyncio
async def test_pending_cancel_keeps_slot_until_drain_and_retains_consumed_tombstone():
    wire, peer, reader, writer = await controlled_peer()
    request = {"jsonrpc": "2.0", "id": 7, "method": "approval"}
    try:
        reader.feed_data(wire.encode(request))
        await asyncio.wait_for(writer.entered.wait(), 1)
        await feed_through_barrier(wire, peer, reader, [cancel_frame(7)])
        assert list(peer.cancelled) == [(7, "approval")]
        assert peer.reverse == {(int, 7): None}
        assert not peer.reverse_done
        writer.release.set()
        await settled(lambda: peer.queued_bytes == 0)
        assert not peer.reverse
        assert peer.reverse_done == {(int, 7): None}
        assert peer.failure is None
        peer.events.clear()
        await feed_through_barrier(wire, peer, reader, [request])
        assert peer.failure is not None
        assert len(writer.writes) == 1
    finally:
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
