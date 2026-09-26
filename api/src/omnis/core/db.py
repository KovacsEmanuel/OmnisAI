"""Inert PostgreSQL pool and schema readiness; never migrate in the API process."""

import asyncio
import os
from enum import StrEnum

from sqlalchemy import text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError, DBAPIError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine


SCHEMA_REVISION = "0001_instance_control"


class ReadinessReason(StrEnum):
    DATABASE_UNAVAILABLE = "DATABASE_UNAVAILABLE"
    SCHEMA_INCOMPATIBLE = "SCHEMA_INCOMPATIBLE"


def reject_ambient_libpq_config() -> None:
    if any(name.startswith("PG") for name in os.environ):
        raise ValueError("Ambient libpq configuration is forbidden")


def validated_database_url(database_url: str) -> URL:
    reject_ambient_libpq_config()
    try:
        url = make_url(database_url)
    except ArgumentError:
        raise ValueError("Invalid PostgreSQL configuration") from None
    if url.drivername != "postgresql+psycopg":
        raise ValueError("PostgreSQL must use the async psycopg driver")
    if url.query:
        raise ValueError("Database URL query parameters are forbidden")
    return url


def database_engine(database_url: str) -> AsyncEngine:
    url = validated_database_url(database_url)
    return create_async_engine(
        url,
        pool_pre_ping=True,
        pool_timeout=2,
        connect_args={"connect_timeout": 2, "options": "-c statement_timeout=2000"},
    )


async def readiness_reason(engine: AsyncEngine | None) -> ReadinessReason | None:
    if engine is None:
        return ReadinessReason.DATABASE_UNAVAILABLE
    try:
        async with asyncio.timeout(3):
            return await _probe_schema(engine)
    except (TimeoutError, SQLAlchemyError):
        return ReadinessReason.DATABASE_UNAVAILABLE


async def _probe_schema(engine: AsyncEngine) -> ReadinessReason | None:
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
            if revisions != [SCHEMA_REVISION] or instance is None:
                return ReadinessReason.SCHEMA_INCOMPATIBLE
            columns = (
                await connection.execute(
                    text(
                        "SELECT a.attname, format_type(a.atttypid, a.atttypmod), "
                        "a.attnotnull, pg_get_expr(d.adbin, d.adrelid) "
                        "FROM pg_attribute a LEFT JOIN pg_attrdef d "
                        "ON d.adrelid = a.attrelid AND d.adnum = a.attnum "
                        "WHERE a.attrelid = 'instance_control'::regclass "
                        "AND a.attnum > 0 AND NOT a.attisdropped"
                    )
                )
            ).all()
            constraints = (
                await connection.execute(
                    text(
                        "SELECT conname, contype, pg_get_constraintdef(oid), "
                        "convalidated, conenforced "
                        "FROM pg_constraint "
                        "WHERE conrelid = 'instance_control'::regclass"
                    )
                )
            ).all()
        except SQLAlchemyError as exc:
            if isinstance(exc, DBAPIError) and getattr(exc.orig, "sqlstate", None) in {"42P01", "42703"}:
                return ReadinessReason.SCHEMA_INCOMPATIBLE
            return ReadinessReason.DATABASE_UNAVAILABLE
    expected_columns = {
        ("id", "smallint", True),
        ("instance_id", "uuid", True),
        ("admission_open", "boolean", True),
        ("shutdown_command_id", "uuid", False),
        ("generation", "bigint", True),
        ("quiesced_generation", "bigint", False),
        ("quiesced_at", "timestamp with time zone", False),
    }
    actual_columns = {(name, kind, required) for name, kind, required, _ in columns}
    defaults = {name: default for name, _, _, default in columns}
    expected_constraints = {
        ("instance_control_pkey", "p", "PRIMARY KEY (id)", True, True),
        ("instance_control_instance_id_key", "u", "UNIQUE (instance_id)", True, True),
        ("ck_instance_control_singleton", "c", "CHECK ((id = 1))", True, True),
        ("ck_instance_control_generation", "c", "CHECK ((generation >= 0))", True, True),
        ("instance_control_id_not_null", "n", "NOT NULL id", True, True),
        ("instance_control_instance_id_not_null", "n", "NOT NULL instance_id", True, True),
        ("instance_control_admission_open_not_null", "n", "NOT NULL admission_open", True, True),
        ("instance_control_generation_not_null", "n", "NOT NULL generation", True, True),
    }
    if (
        actual_columns != expected_columns
        or defaults.get("instance_id") != "gen_random_uuid()"
        or defaults.get("admission_open") != "false"
        or defaults.get("generation") != "0"
        or set(constraints) != expected_constraints
    ):
        return ReadinessReason.SCHEMA_INCOMPATIBLE
    return None
