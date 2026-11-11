"""Test bootstrap shared by every suite (tests/ and src/dse/features/*/tests).

Integration tests run against their OWN database (`dse_test`) and Redis db 15, never the development ones:
several suites TRUNCATE tables, and a developer's hours of backfilled history must survive `pytest`.
The test database is created and migrated on demand, only when an integration test is selected.
"""

import asyncio
import os
from pathlib import Path

import pytest
from sqlalchemy.engine import make_url

os.environ.setdefault("DSE_ENV", "test")

TEST_DB = "dse_test"
TEST_REDIS_DB = "15"

_dev = make_url(os.environ.get("DSE_DATABASE__URL", "postgresql+asyncpg://dse:dse@localhost:5433/dse"))
_test = _dev.set(database=TEST_DB)
os.environ["DSE_DATABASE__URL"] = _test.render_as_string(hide_password=False)
_redis = os.environ.get("DSE_REDIS__URL", "redis://localhost:6380/0")
os.environ["DSE_REDIS__URL"] = _redis.rsplit("/", 1)[0] + "/" + TEST_REDIS_DB


async def _ensure_database() -> None:
    import asyncpg

    admin = _test.set(database="postgres", drivername="postgresql")
    conn = await asyncpg.connect(admin.render_as_string(hide_password=False))
    try:
        exists = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", TEST_DB)
        if not exists:
            await conn.execute(f'CREATE DATABASE "{TEST_DB}"')
    finally:
        await conn.close()


def _migrate() -> None:
    from alembic import command
    from alembic.config import Config

    root = Path(__file__).parent
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "alembic"))
    command.upgrade(cfg, "head")


@pytest.fixture(scope="session", autouse=True)
def _test_database(request: pytest.FixtureRequest) -> None:
    if not any(item.get_closest_marker("integration") for item in request.session.items):
        return
    asyncio.run(_ensure_database())
    _migrate()
