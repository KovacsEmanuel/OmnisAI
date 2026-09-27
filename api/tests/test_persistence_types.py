"""Persistence-boundary regressions exposed by strict typing."""

import secrets
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.engine import URL

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
