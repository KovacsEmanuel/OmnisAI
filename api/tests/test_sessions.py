import asyncio
import hashlib
import secrets
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.engine import URL

from omnis.core.db import database_engine


@pytest.mark.asyncio
async def test_pairing_consumes_once_across_competing_connections(
    migrated_database_url: URL,
) -> None:
    from omnis.security.sessions import PairingDenied, SessionGrant, SessionStore, code_digest

    engine = database_engine(migrated_database_url.render_as_string(hide_password=False))
    store = SessionStore(engine)
    code = secrets.token_urlsafe(24)
    try:
        await store.register(code_digest(code), issuance_id=uuid4())
        results = await asyncio.gather(
            store.exchange(code), store.exchange(code), return_exceptions=True
        )
        grants = [result for result in results if not isinstance(result, Exception)]
        assert len(grants) == 1
        assert sum(isinstance(result, PairingDenied) for result in results) == 1
        grant = grants[0]
        assert isinstance(grant, SessionGrant)
        assert await store.authenticate(grant.token) is not None
        async with engine.connect() as connection:
            rows = (
                (await connection.execute(text("SELECT token_digest FROM ui_session")))
                .scalars()
                .all()
            )
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
async def test_expiry_and_persistent_attempt_limit(migrated_database_url: URL) -> None:
    from omnis.security.sessions import PairingDenied, PairingLimited, SessionStore, code_digest

    engine = database_engine(migrated_database_url.render_as_string(hide_password=False))
    store = SessionStore(engine)
    code = secrets.token_urlsafe(24)
    try:
        await store.register(code_digest(code), issuance_id=uuid4())
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "UPDATE pairing_challenge SET expires_at = clock_timestamp() - interval '1 second'"
                )
            )
        with pytest.raises(PairingDenied):
            await store.exchange(code)
        code = secrets.token_urlsafe(24)
        issuance = uuid4()
        await store.register(code_digest(code), issuance_id=issuance)
        for _ in range(4):
            with pytest.raises(PairingDenied):
                await store.exchange("invalid-but-bounded-code")
        # Re-registering a code must not reset the global attempt window.
        await store.register(code_digest(code), issuance_id=issuance)
        with pytest.raises(PairingLimited):
            await SessionStore(engine).exchange(code)
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "UPDATE pairing_challenge SET window_started_at = clock_timestamp() - interval '61 seconds'"
                )
            )
        grant = await store.exchange(code)
        async with engine.begin() as connection:
            await connection.execute(
                text("UPDATE ui_session SET expires_at = clock_timestamp() - interval '1 second'")
            )
        assert await store.authenticate(grant.token) is None
    finally:
        await engine.dispose()


@pytest.mark.parametrize("state", ["consumed", "superseded", "expired"])
@pytest.mark.asyncio
async def test_pairing_registration_replay_never_reactivates_a_code(
    migrated_database_url: URL, state: str
) -> None:
    from omnis.security.sessions import PairingDenied, SessionStore, code_digest

    engine = database_engine(migrated_database_url.render_as_string(hide_password=False))
    store = SessionStore(engine)
    old_code = secrets.token_urlsafe(24)
    current_code = secrets.token_urlsafe(24)
    issuance = uuid4()
    try:
        expires = await store.register(code_digest(old_code), issuance_id=issuance)
        if state == "consumed":
            await store.exchange(old_code)
        elif state == "superseded":
            await store.register(code_digest(current_code), issuance_id=uuid4())
        else:
            async with engine.begin() as connection:
                await connection.execute(
                    text(
                        "UPDATE pairing_challenge SET expires_at = clock_timestamp() - interval '1 second'"
                    )
                )
        assert await store.register(code_digest(old_code), issuance_id=issuance) == expires
        with pytest.raises(PairingDenied):
            await store.exchange(old_code)
        if state == "superseded":
            assert await store.exchange(current_code)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_pairing_issuance_is_idempotent_and_rejects_id_or_code_reuse(
    migrated_database_url: URL,
) -> None:
    from omnis.security.sessions import PairingConflict, SessionStore, code_digest

    engine = database_engine(migrated_database_url.render_as_string(hide_password=False))
    store = SessionStore(engine)
    code = secrets.token_urlsafe(24)
    issuance = uuid4()
    try:
        deadlines = await asyncio.gather(
            *[store.register(code_digest(code), issuance_id=issuance) for _ in range(2)]
        )
        assert deadlines[0] == deadlines[1]
        with pytest.raises(PairingConflict):
            await store.register(code_digest("another-synthetic-code"), issuance_id=issuance)
        with pytest.raises(PairingConflict):
            await store.register(code_digest(code), issuance_id=uuid4())
        async with engine.connect() as connection:
            assert (
                await connection.execute(text("SELECT count(*) FROM pairing_issuance"))
            ).scalar_one() == 1
        assert await store.exchange(code)
    finally:
        await engine.dispose()
