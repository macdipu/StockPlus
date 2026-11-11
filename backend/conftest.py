"""Test bootstrap shared by every suite (tests/ and src/dse/features/*/tests).

Integration tests run against their OWN database (`dse_test`) and Redis db 15, never the development ones:
several suites TRUNCATE tables, and a developer's hours of backfilled history must survive `pytest`.
The test database is created and migrated on demand, only when an integration test is selected.
"""

import asyncio
import fcntl
import os
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import IO

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


# One lock for the whole test database. Integration suites TRUNCATE shared tables, so two pytest sessions
# at once would block each other (and hang). A POSIX file lock makes the second session wait its turn; the
# OS releases it if the holder dies, and it holds no async object that could outlive its event loop.
LOCK_PATH = Path(tempfile.gettempdir()) / "dse-analyzer-test-db.lock"
_lock_file: IO[str] | None = None


def _acquire_lock() -> None:
    global _lock_file
    _lock_file = LOCK_PATH.open("w")
    fcntl.flock(_lock_file, fcntl.LOCK_EX)  # blocks while another session holds it


def _release_lock() -> None:
    global _lock_file
    if _lock_file is not None:
        fcntl.flock(_lock_file, fcntl.LOCK_UN)
        _lock_file.close()
        _lock_file = None


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
def _test_database(request: pytest.FixtureRequest) -> Iterator[None]:
    if not any(item.get_closest_marker("integration") for item in request.session.items):
        yield
        return
    _acquire_lock()  # blocks while another pytest session is using the test database
    try:
        asyncio.run(_ensure_database())
        _migrate()
        yield
    finally:
        _release_lock()
