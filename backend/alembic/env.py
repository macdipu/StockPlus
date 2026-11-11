"""Alembic environment: async engine; URL from Settings (never alembic.ini); metadata from all features."""

import asyncio

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

# Import every feature's ORM models here so autogenerate sees them (added per migrated feature).
import dse.features.identity.infrastructure.orm
import dse.features.live_feed.infrastructure.orm
import dse.features.market_data.infrastructure.orm
import dse.features.watchlists.infrastructure.orm  # noqa: F401
from dse.core.config import get_settings
from dse.core.db import Base

target_metadata = Base.metadata


def run_offline() -> None:
    context.configure(url=get_settings().database.url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def _run(connection) -> None:  # type: ignore[no-untyped-def]
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_online() -> None:
    engine = create_async_engine(get_settings().database.url)
    async with engine.connect() as conn:
        await conn.run_sync(_run)
    await engine.dispose()


if context.is_offline_mode():
    run_offline()
else:
    asyncio.run(run_online())
