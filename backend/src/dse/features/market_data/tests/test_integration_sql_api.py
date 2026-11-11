"""Repositories and HTTP API against real Postgres (docker compose up -d db redis)."""

from collections.abc import AsyncIterator
from dataclasses import replace
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from dse.core.config import get_settings
from dse.core.db import Database
from dse.features.market_data.domain.entities import BarSource, CompanyPage
from dse.features.market_data.infrastructure.uow import SqlMarketDataUnitOfWork
from dse.features.market_data.presentation.dependencies import MarketDataContainer
from dse.features.market_data.tests.fakes import FakeClock, FakeSource
from dse.main import create_app
from dse.shared_kernel.symbol import Symbol

pytestmark = pytest.mark.integration
ORION = Symbol("ORIONINFU")
TABLES = "announcements, daily_bars, fundamentals, instruments"


@pytest.fixture
async def db() -> AsyncIterator[Database]:
    d = Database(get_settings().database)
    async with d.engine.begin() as c:
        await c.execute(text(f"TRUNCATE {TABLES}"))
    yield d
    await d.dispose()


async def test_sql_round_trip_and_bar_precedence(db: Database, page: CompanyPage) -> None:
    async with SqlMarketDataUnitOfWork(db.sessions) as uow:
        await uow.instruments.upsert(page.instrument, page.fetched_at)
        await uow.fundamentals.save(ORION, page.fundamentals, page.fetched_at)
        assert await uow.bars.upsert(page.bars) == 260
        await uow.announcements.upsert(page.announcements)
        await uow.commit()

    last = page.bars[-1]
    snap_bar = replace(last, close=Decimal("999"), source=BarSource.SNAPSHOT)
    new_day = replace(last, day=last.day.replace(day=last.day.day + 1), source=BarSource.SNAPSHOT)
    async with SqlMarketDataUnitOfWork(db.sessions) as uow:
        assert await uow.bars.upsert([snap_bar, new_day]) == 1  # page bar protected, new day inserted
        await uow.commit()

    async with SqlMarketDataUnitOfWork(db.sessions) as uow:
        bars = await uow.bars.latest(ORION, 3)
        assert [b.day for b in bars][-1] == new_day.day
        assert bars[-2].close == last.close
        assert bars[-2].source == BarSource.PAGE
        assert await uow.fundamentals.get(ORION) == page.fundamentals  # JSONB round-trip is lossless
        assert (await uow.instruments.get(ORION)) == page.instrument
        assert len(await uow.announcements.latest(ORION, 100)) == len(page.announcements)


async def test_uow_rolls_back_without_commit(db: Database, page: CompanyPage) -> None:
    async with SqlMarketDataUnitOfWork(db.sessions) as uow:
        await uow.bars.upsert(page.bars)
    async with SqlMarketDataUnitOfWork(db.sessions) as uow:
        assert await uow.bars.count() == 0


@pytest.mark.usefixtures("db")
def test_api_contract(page: CompanyPage) -> None:
    app = create_app()
    with TestClient(app) as client:
        src = FakeSource({"ORIONINFU": page})
        app.state.market_data = MarketDataContainer(app.state.db, src, FakeClock())

        r = client.get("/api/v1/stocks/orioninfu")
        assert r.status_code == 200
        body = r.json()
        assert body["data"]["symbol"] == "ORIONINFU"
        assert body["data"]["fundamentals"]["eps_ttm"] == pytest.approx(1.43)
        assert body["meta"]["requestId"]

        c = client.get("/api/v1/stocks/ORIONINFU/candles?limit=5").json()
        assert c["meta"]["count"] == 5
        assert c["data"][-1]["day"] == page.bars[-1].day.isoformat()
        assert src.calls == 1  # read-through happened once

        assert client.get("/api/v1/stocks/ORIONINFU/announcements?limit=2").json()["meta"]["count"] == 2

        missing = client.get("/api/v1/stocks/NOPE")
        assert missing.status_code == 404
        assert missing.headers["content-type"] == "application/problem+json"
        assert client.get("/api/v1/stocks/bad%20sym").status_code == 400
        assert client.get("/api/v1/stocks/ORIONINFU/candles?limit=0").status_code == 422

        paths = client.get("/api/v1/openapi.json").json()["paths"]
        assert {"/api/v1/stocks/{symbol}", "/api/v1/stocks/{symbol}/candles"} <= set(paths)
