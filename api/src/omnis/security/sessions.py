"""PostgreSQL owns pairing consumption, throttling and session revocation."""

import hashlib
import hmac
import re
import secrets
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


class PairingDenied(Exception):
    pass


class PairingLimited(Exception):
    pass


class PairingConflict(Exception):
    pass


@dataclass(frozen=True)
class SessionGrant:
    token: str = field(repr=False)

    @property
    def csrf(self) -> str:
        return hmac.new(self.token.encode(), b"omnis-ui-csrf-v1", hashlib.sha256).hexdigest()


def code_digest(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


class SessionStore:
    def __init__(self, engine: AsyncEngine):
        self.engine = engine

    async def register(self, digest: str, *, issuance_id: UUID) -> datetime:
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError("Invalid pairing digest")
        async with self.engine.begin() as connection:
            await connection.execute(text("SELECT id FROM pairing_challenge WHERE id = 1 FOR UPDATE"))
            previous = (await connection.execute(text(
                "SELECT digest, expires_at FROM pairing_issuance WHERE issuance_id = :issuance"
            ), {"issuance": issuance_id})).mappings().one_or_none()
            if previous is not None:
                if previous["digest"] != digest:
                    raise PairingConflict()
                return previous["expires_at"]
            reused = (await connection.execute(text(
                "SELECT 1 FROM pairing_issuance WHERE digest = :digest"
            ), {"digest": digest})).scalar_one_or_none()
            if reused:
                raise PairingConflict()
            expires = (await connection.execute(text(
                "INSERT INTO pairing_issuance VALUES (:issuance, :digest, clock_timestamp() + interval '5 minutes') "
                "RETURNING expires_at"
            ), {"issuance": issuance_id, "digest": digest})).scalar_one()
            # New code invalidates the old one but never resets the rate limit.
            result = await connection.execute(text(
                "UPDATE pairing_challenge SET digest = :digest, "
                "expires_at = :expires WHERE id = 1"
            ), {"digest": digest, "expires": expires})
            if result.rowcount != 1:
                raise PairingDenied()
            return expires

    async def exchange(self, code: str) -> SessionGrant:
        grant = None
        limited = False
        async with self.engine.begin() as connection:
            row = (await connection.execute(text(
                "SELECT * FROM pairing_challenge WHERE id = 1 FOR UPDATE"
            ))).mappings().one()
            now = (await connection.execute(text("SELECT clock_timestamp()"))).scalar_one()
            attempts = row["attempts"] if (now - row["window_started_at"]).total_seconds() < 60 else 0
            limited = attempts >= 5
            if not limited:
                await connection.execute(text(
                    "UPDATE pairing_challenge SET attempts = :attempts, "
                    "window_started_at = :started WHERE id = 1"
                ), {"attempts": attempts + 1, "started": now if attempts == 0 else row["window_started_at"]})
                if (
                    row["digest"] is not None and row["expires_at"] > now
                    and hmac.compare_digest(row["digest"], code_digest(code))
                ):
                    grant = SessionGrant(secrets.token_urlsafe(32))
                    await connection.execute(text(
                        "UPDATE pairing_challenge SET digest = NULL, expires_at = NULL WHERE id = 1"
                    ))
                    await connection.execute(text("DELETE FROM ui_session WHERE expires_at <= clock_timestamp()"))
                    await connection.execute(text(
                        "INSERT INTO ui_session (token_digest, expires_at) "
                        "VALUES (:digest, clock_timestamp() + interval '12 hours')"
                    ), {"digest": code_digest(grant.token)})
        # Denials must commit their attempt counter, not roll it back by raising inside begin().
        if limited:
            raise PairingLimited()
        if grant is None:
            raise PairingDenied()
        return grant

    async def authenticate(self, token: str) -> SessionGrant | None:
        if not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
            return None
        async with self.engine.connect() as connection:
            valid = (await connection.execute(text(
                "SELECT 1 FROM ui_session WHERE token_digest = :digest AND expires_at > clock_timestamp()"
            ), {"digest": code_digest(token)})).scalar_one_or_none()
        return SessionGrant(token) if valid else None

    async def logout(self, token: str) -> None:
        async with self.engine.begin() as connection:
            await connection.execute(text("DELETE FROM ui_session WHERE token_digest = :digest"),
                                     {"digest": code_digest(token)})
