import asyncio
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest

from omnis.supervisor.model_relay import Relay, RelayFailure
from omnis.supervisor.model_relay_protocol import MAX_INT, Scope, decode, encode, validate


def frame() -> dict[str, object]:
    return {
        "version": 1,
        "action": "WRITE",
        "request_id": str(uuid4()),
        "connection_id": str(uuid4()),
        "scope": Scope(
            str(uuid4()),
            "METADATA_COMMAND",
            str(uuid4()),
            str(uuid4()),
            MAX_INT,
            MAX_INT,
            MAX_INT,
            "9999-12-31T23:59:59.999999+00:00",
            "orcarouter",
        ).wire(),
        "sequence": MAX_INT,
        "size": 65536,
        "timeout_ms": 300000,
        "write_deadline": "9999-12-31T23:59:59.999999+00:00",
        "capability": "f" * 64,
    }


def test_final_wire_maxima_and_packaging_are_bounded() -> None:
    value = frame()
    raw = encode(value)
    validate(decode(raw))
    assert len(raw) <= 4096
    assert b"f" * 64 in raw
    root = Path(__file__).resolve().parents[2]
    assert (root / "api/src/omnis/supervisor/model_relay_protocol.py").read_bytes() == (
        root / "cli/src/omnis_cli/model_relay_protocol.py"
    ).read_bytes()


@pytest.mark.parametrize(
    "field,value",
    [
        ("version", True),
        ("version", 2),
        ("action", "CONNECT"),
        ("sequence", MAX_INT + 1),
        ("sequence", -1),
        ("sequence", True),
        ("size", 65537),
        ("size", True),
        ("timeout_ms", 0),
        ("timeout_ms", 300001),
        ("timeout_ms", float("inf")),
        ("request_id", "AAAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAA"),
        ("connection_id", None),
        ("capability", "F" * 64),
        ("write_deadline", "2026-10-23T12:00:00+01:00"),
    ],
)
def test_wire_denies_invalid_fields(field: str, value: object) -> None:
    candidate = frame()
    candidate[field] = value
    with pytest.raises(ValueError):
        validate(candidate)


@pytest.mark.parametrize(
    "raw", [b'{"x":1,"x":2}\n', b"[]\n", b"{}", b" " * 4096 + b"\n", b"\xff\n"]
)
def test_wire_denies_duplicate_nonobject_unterminated_oversize_utf8(raw: bytes) -> None:
    with pytest.raises(ValueError):
        decode(raw)


def test_scope_extra_and_cancel_epoch_overflow_are_denied() -> None:
    candidate = frame()
    scope = Scope.parse(candidate["scope"]).wire()
    scope["cancel_epoch"] = MAX_INT + 1
    candidate["scope"] = scope
    with pytest.raises(ValueError):
        validate(candidate)
    candidate["scope"] = {**Scope.parse(frame()["scope"]).wire(), "host": "127.0.0.1"}
    with pytest.raises(ValueError):
        validate(candidate)
    candidate = frame()
    candidate["url"] = "https://example.com"
    with pytest.raises(ValueError):
        validate(candidate)


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["missing", "drain_upstream"])
async def test_missing_scoped_ack_prevents_quiescence(mode: str) -> None:
    import os

    with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
        root = Path(name)
        root.chmod(0o700)
        path = root / "model-egress.sock"
        (root / "model-relay.cap").write_text("a" * 64)
        (root / "model-relay.cap").chmod(0o600)

        async def no_ack(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
            request = decode(await reader.readline())
            if mode == "drain_upstream":
                reply = {
                    k: request[k]
                    for k in ("version", "request_id", "connection_id", "scope", "sequence")
                }
                writer.write(
                    encode(
                        {
                            **reply,
                            "size": 0,
                            "status": "OK"
                            if request["action"] == "FENCE"
                            else "UPSTREAM_UNAVAILABLE",
                        }
                    )
                )
                await writer.drain()
            writer.close()
            await writer.wait_closed()

        server = await asyncio.start_unix_server(no_ack, path)
        path.chmod(0o600)
        relay = Relay(path)
        scope = Scope(
            str(uuid4()),
            "MODEL_DISPATCH",
            str(uuid4()),
            str(uuid4()),
            1,
            1,
            1,
            (datetime.now(UTC) + timedelta(seconds=30)).isoformat(),
            "openrouter",
        )
        relay.scopes.add(scope)
        try:
            with pytest.raises(RelayFailure, match="RELAY_.*UNCERTAIN"):
                await relay.drain()
            assert scope in relay.scopes
            if mode == "missing":
                assert relay.failed
        finally:
            server.close()
            await server.wait_closed()


@pytest.mark.asyncio
async def test_db_query_latency_is_subtracted_from_host_write_window() -> None:
    from unittest.mock import AsyncMock, Mock

    from sqlalchemy.ext.asyncio import AsyncConnection

    from omnis.modules.runs.model_test_runtime import ApiKeyModelTest
    from omnis.modules.settings.provider_key_service import ProviderSettingsOwner

    owner = ApiKeyModelTest.__new__(ApiKeyModelTest)
    owner.settings = ProviderSettingsOwner.__new__(ProviderSettingsOwner)
    owner.settings.owner, owner.settings.epoch = uuid4(), 1
    db = AsyncMock(spec=AsyncConnection)

    async def query(*args: object, **kwargs: object) -> object:
        await asyncio.sleep(0.06)
        now = datetime.now(UTC)
        result = Mock()
        result.one_or_none.return_value = (now, now + timedelta(seconds=10))
        return result

    db.execute.side_effect = query
    began = datetime.now(UTC)
    async with owner.physical_window(db, began + timedelta(seconds=10)) as deadline:
        assert (datetime.fromisoformat(deadline) - began).total_seconds() <= 0.5
