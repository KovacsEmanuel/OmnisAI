"""Persistence-boundary regressions exposed by strict typing."""

import secrets
from collections import UserDict
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.engine import URL
from sqlalchemy.exc import SQLAlchemyError

from omnis.core.db import database_engine
from omnis.security.sessions import PairingDenied, SessionStore, code_digest


@pytest.mark.asyncio
async def test_incomplete_pairing_challenge_is_denied(migrated_database_url: URL) -> None:
    engine = database_engine(migrated_database_url.render_as_string(hide_password=False))
    store = SessionStore(engine)
    code = secrets.token_urlsafe(24)
    try:
        await store.register(code_digest(code), issuance_id=uuid4())
        async with engine.begin() as connection:
            await connection.execute(text("UPDATE pairing_challenge SET expires_at = NULL"))
        with pytest.raises(PairingDenied):
            await store.exchange(code)
        async with engine.connect() as connection:
            assert (
                await connection.execute(text("SELECT count(*) FROM ui_session"))
            ).scalar_one() == 0
            assert (
                await connection.execute(text("SELECT attempts FROM pairing_challenge"))
            ).scalar_one() == 1
    finally:
        await engine.dispose()


def test_database_scalar_types_reject_coercion() -> None:
    from omnis.core.persistence import DatabaseContractError, read_datetime, read_integer

    instant = datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert read_integer(3) == 3
    assert read_datetime(instant) == instant
    for invalid in ("3", True, None, 3.5):
        with pytest.raises(DatabaseContractError):
            read_integer(invalid)
    with pytest.raises(DatabaseContractError) as caught:
        read_datetime("synthetic-sensitive-database-value")
    assert isinstance(caught.value, SQLAlchemyError)
    assert "synthetic-sensitive" not in str(caught.value)


def test_database_records_are_strict_and_sanitized() -> None:
    from omnis.core.persistence import DatabaseContractError, DatabaseRecord, read_record

    class CounterRow(DatabaseRecord):
        count: int

    assert read_record(CounterRow, {"count": 3}).count == 3
    assert read_record(CounterRow, UserDict({"count": 3})).count == 3
    with pytest.raises(DatabaseContractError):
        read_record(CounterRow, UserDict({"count": "3"}))
    for invalid in ({"count": "3"}, {"count": True}, {"count": 3, "extra": "secret"}, {}):
        with pytest.raises(DatabaseContractError) as caught:
            read_record(CounterRow, invalid)
        assert "secret" not in str(caught.value)
