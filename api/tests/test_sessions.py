import asyncio
import hashlib
import secrets

import pytest
from sqlalchemy import text

from omnis.core.db import database_engine


@pytest.mark.asyncio
async def test_pairing_consumes_once_across_competing_connections(migrated_database_url):
    from omnis.security.sessions import PairingDenied, SessionStore, code_digest

    engine = database_engine(migrated_database_url.render_as_string(hide_password=False))
    store = SessionStore(engine)
    code = secrets.token_urlsafe(24)
    try:
        await store.register(code_digest(code))
        results = await asyncio.gather(store.exchange(code), store.exchange(code), return_exceptions=True)
        grants = [result for result in results if not isinstance(result, Exception)]
        assert len(grants) == 1
        assert sum(isinstance(result, PairingDenied) for result in results) == 1
        grant = grants[0]
        assert await store.authenticate(grant.token) is not None
        async with engine.connect() as connection:
            rows = (await connection.execute(text("SELECT token_digest FROM ui_session"))).scalars().all()
            assert rows == [hashlib.sha256(grant.token.encode()).hexdigest()]
        await engine.dispose()
        # A fresh pool reads persisted authority, not a process-local dictionary.
        engine = database_engine(migrated_database_url.render_as_string(hide_password=False))
        store = SessionStore(engine)
        assert await store.authenticate(grant.token) is not None
        await store.logout(grant.token)
        assert await store.authenticate(grant.token) is None
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_expiry_and_persistent_attempt_limit(migrated_database_url):
    from omnis.security.sessions import PairingDenied, PairingLimited, SessionStore, code_digest

    engine = database_engine(migrated_database_url.render_as_string(hide_password=False))
    store = SessionStore(engine)
    code = secrets.token_urlsafe(24)
    try:
        await store.register(code_digest(code))
        async with engine.begin() as connection:
            await connection.execute(text("UPDATE pairing_challenge SET expires_at = clock_timestamp() - interval '1 second'"))
        with pytest.raises(PairingDenied):
            await store.exchange(code)
        await store.register(code_digest(code))
        for _ in range(4):
            with pytest.raises(PairingDenied):
                await store.exchange("invalid-but-bounded-code")
        # Re-registering a code must not reset the global attempt window.
        await store.register(code_digest(code))
        with pytest.raises(PairingLimited):
            await SessionStore(engine).exchange(code)
        async with engine.begin() as connection:
            await connection.execute(text("UPDATE pairing_challenge SET window_started_at = clock_timestamp() - interval '61 seconds'"))
        grant = await store.exchange(code)
        async with engine.begin() as connection:
            await connection.execute(text("UPDATE ui_session SET expires_at = clock_timestamp() - interval '1 second'"))
        assert await store.authenticate(grant.token) is None
    finally:
        await engine.dispose()
