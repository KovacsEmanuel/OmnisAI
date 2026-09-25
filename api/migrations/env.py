"""Online-only migrations, run explicitly before the API starts."""

import asyncio
import os

from alembic import context
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from omnis.modules.instance.models import Base


target_metadata = Base.metadata


def run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def migrate() -> None:
    database_url = os.environ.get("OMNIS_DATABASE_URL")
    if not database_url or make_url(database_url).drivername != "postgresql+psycopg":
        raise RuntimeError("OMNIS_DATABASE_URL must use postgresql+psycopg")

    engine = create_async_engine(database_url, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            await connection.run_sync(run_migrations)
    finally:
        await engine.dispose()


if context.is_offline_mode():
    raise RuntimeError("Offline migrations are not supported")
asyncio.run(migrate())
