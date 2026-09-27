"""Online-only migrations, run explicitly before the API starts."""

import asyncio
import os

from alembic import context
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
            async with engine.connect() as connection:
                await connection.run_sync(run_migrations)
    except (TimeoutError, SQLAlchemyError):
        raise RuntimeError("PostgreSQL migration failed or timed out") from None
    finally:
        await engine.dispose()


if context.is_offline_mode():
    raise RuntimeError("Offline migrations are not supported")
asyncio.run(migrate())
