"""Online-only migrations, run explicitly before the API starts."""

import asyncio
import os

from alembic import context
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from omnis.core.db import validated_database_url
from omnis.modules.instance.models import Base

target_metadata = Base.metadata


def run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def migrate() -> None:
    database_url = os.environ.get("OMNIS_DATABASE_URL")
    if not database_url:
        raise RuntimeError("OMNIS_DATABASE_URL must use postgresql+psycopg")
    url = validated_database_url(database_url)

    engine = create_async_engine(
        url,
        poolclass=NullPool,
        connect_args={
            "connect_timeout": 2,
            "options": "-c lock_timeout=1500 -c statement_timeout=15000",
        },
    )
    try:
        async with asyncio.timeout(20):
            async with engine.begin() as connection:
                initialize = context.config.attributes.get("initialize_system_id")
                expected = context.config.attributes.get("upgrade_system_id", initialize)
                if expected is not None:
                    actual = (
                        await connection.execute(
                            text(
                                "SELECT system_identifier::text, pg_catalog.current_database() FROM pg_catalog.pg_control_system()"
                            )
                        )
                    ).one()
                    if actual != (expected, url.database):
                        raise RuntimeError("PostgreSQL cluster identity mismatch")
                await connection.execute(text("SELECT pg_advisory_xact_lock(5714308421745685321)"))
                if initialize is not None:
                    occupied = (
                        await connection.execute(
                            text(
                                "SELECT EXISTS (SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                                "WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema') "
                                "OR EXISTS (SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
                                "WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema') "
                                "OR EXISTS (SELECT 1 FROM pg_type t JOIN pg_namespace n ON n.oid=t.typnamespace "
                                "WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema') "
                                "OR EXISTS (SELECT 1 FROM pg_namespace WHERE nspname !~ '^pg_' "
                                "AND nspname NOT IN ('public', 'information_schema')) "
                                "OR EXISTS (SELECT 1 FROM pg_largeobject_metadata) "
                                "OR EXISTS (SELECT 1 FROM pg_collation c JOIN pg_namespace n ON n.oid=c.collnamespace "
                                "WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema') "
                                "OR EXISTS (SELECT 1 FROM pg_publication) "
                                "OR EXISTS (SELECT 1 FROM pg_foreign_data_wrapper) "
                                "OR EXISTS (SELECT 1 FROM pg_event_trigger) "
                                "OR EXISTS (SELECT 1 FROM pg_extension WHERE extname <> 'plpgsql')"
                            )
                        )
                    ).scalar_one()
                    if occupied:
                        raise RuntimeError(
                            "Explicit update/backup required; startup never upgrades existing data"
                        )
                s1_request = context.config.attributes.get("s1_upgrade")
                request = context.config.attributes.get("t1_upgrade")
                if s1_request is not None and request is not None:
                    raise RuntimeError("One finite upgrade required")
                request = s1_request if s1_request is not None else request
                if request is not None:
                    from omnis.migrate import admit_t1_upgrade

                    await admit_t1_upgrade(connection, engine, request, s1=s1_request is not None)
                await connection.run_sync(run_migrations)
                if request is not None:
                    from omnis.core.db import schema0017_reason_on, schema_reason_on

                    check = schema_reason_on if s1_request is not None else schema0017_reason_on
                    if await check(connection) is not None:
                        raise RuntimeError(
                            "Physical0019 readback required"
                            if s1_request is not None
                            else "Physical0017 readback required"
                        )
    except (TimeoutError, SQLAlchemyError):
        raise RuntimeError("PostgreSQL migration failed or timed out") from None
    finally:
        await engine.dispose()


if context.is_offline_mode():
    raise RuntimeError("Offline migrations are not supported")
asyncio.run(migrate())
