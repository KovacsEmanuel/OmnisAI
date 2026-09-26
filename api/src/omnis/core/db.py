"""Inert PostgreSQL pool and schema readiness; never migrate in the API process."""

from enum import StrEnum

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine


SCHEMA_REVISION = "0001_instance_control"


class ReadinessReason(StrEnum):
    DATABASE_UNAVAILABLE = "DATABASE_UNAVAILABLE"
    SCHEMA_INCOMPATIBLE = "SCHEMA_INCOMPATIBLE"


def database_engine(database_url: str) -> AsyncEngine:
    try:
        url = make_url(database_url)
    except ArgumentError:
        raise ValueError("Invalid PostgreSQL configuration") from None
    if url.drivername != "postgresql+psycopg":
        raise ValueError("PostgreSQL must use the async psycopg driver")
    return create_async_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 2})


async def readiness_reason(engine: AsyncEngine | None) -> ReadinessReason | None:
    if engine is None:
        return ReadinessReason.DATABASE_UNAVAILABLE
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
            try:
                revisions = (
                    await connection.execute(text("SELECT version_num FROM alembic_version"))
                ).scalars().all()
                instance = (
                    await connection.execute(
                        text(
                            "SELECT id, instance_id, admission_open, shutdown_command_id, "
                            "generation, quiesced_generation, quiesced_at "
                            "FROM instance_control WHERE id = 1"
                        )
                    )
                ).first()
            except SQLAlchemyError:
                return ReadinessReason.SCHEMA_INCOMPATIBLE
    except SQLAlchemyError:
        return ReadinessReason.DATABASE_UNAVAILABLE
    if revisions != [SCHEMA_REVISION] or instance is None:
        return ReadinessReason.SCHEMA_INCOMPATIBLE
    return None
