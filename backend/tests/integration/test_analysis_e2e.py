"""Analysis through the real stack: HTTP → analysis → market_data + live_feed facades → Postgres + Redis.

DSE is faked (recorded page bytes); everything else is real. Redis db 15, like the live_feed tests.
"""

import asyncio
import gzip
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from dse.core.cache import create_redis
from dse.core.clock import SystemClock
from dse.core.config import RedisSettings, Settings, get_settings
from dse.features.analysis.infrastructure.gateways import FacadeAnalysisInputs
from dse.features.analysis.presentation.dependencies import AnalysisContainer
from dse.features.live_feed.domain.entities import LiveSnapshot
from dse.features.live_feed.infrastructure.dse_snapshot import parse_live_snapshot
from dse.features.live_feed.infrastructure.redis_adapters import RedisLiveStateStore
from dse.features.market_data.infrastructure.dse_parser import parse_company_page
from dse.features.market_data.presentation.dependencies import MarketDataContainer
from dse.features.market_data.tests.fakes import NOW, FakeSource
from dse.main import create_app
from dse.shared_kernel.symbol import Symbol

pytestmark = pytest.mark.integration
MD = Path(__file__).parents[2] / "src/dse/features/market_data/tests/fixtures"
TABLES = "announcements, daily_bars, fundamentals, instruments"


def settings() -> Settings:
    base = get_settings()
    return base.model_copy(update={"redis": RedisSettings(url=base.redis.url.rsplit("/", 1)[0] + "/15")})


async def seed_redis(s: Settings, snapshot: LiveSnapshot) -> None:
    r = create_redis(s.redis)
    await r.flushdb()
    await RedisLiveStateStore(r).save_snapshot(snapshot, list(snapshot.quotes.values()), full=True)
    await r.aclose()


async def reset(s: Settings) -> None:
    from dse.core.db import Database

    db = Database(s.database)
    async with db.engine.begin() as c:
        await c.execute(text(f"TRUNCATE {TABLES}"))
    await db.dispose()
    r = create_redis(s.redis)
    await r.flushdb()
    await r.aclose()


@pytest.fixture
def client() -> Iterator[TestClient]:
    s = settings()
    with gzip.open(MD / "company_ORIONINFU.html.gz", "rt") as f:
        page = parse_company_page(f.read(), Symbol("ORIONINFU"), NOW)
    with gzip.open(
        Path(__file__).parents[2] / "src/dse/features/live_feed/tests/fixtures/snapshot.json.gz", "rt"
    ) as f:
        snapshot = parse_live_snapshot(json.load(f))
    asyncio.run(reset(s))
    asyncio.run(seed_redis(s, snapshot))
    app = create_app(s)
    with TestClient(app) as c:
        # DSE is replaced by the recorded page; DB, Redis and all wiring stay real
        md = MarketDataContainer(app.state.db, FakeSource({"ORIONINFU": page}), SystemClock())
        app.state.market_data = md
        app.state.analysis = AnalysisContainer(FacadeAnalysisInputs(md.facade, app.state.live_feed.facade))
        yield c
    asyncio.run(reset(s))


def test_analysis_end_to_end(client: TestClient) -> None:
    r = client.get("/api/v1/stocks/ORIONINFU/analysis")
    assert r.status_code == 200, r.text
    body: dict[str, Any] = r.json()
    a = body["data"]
    assert a["symbol"] == "ORIONINFU"
    assert a["name"] == "Orion Infusion Ltd."
    assert a["fundamentals"]["category"] == "A"
    assert a["price"]["bars_available"] > 250
    assert a["price"]["ltp"] == 217.3  # the live quote wins over the stored close
    assert a["price"]["market_open"] is True
    assert a["signal"]["action"]
    assert a["setup"]["max"] == 6
    assert len(a["valuation"]["rows"]) >= 6
    assert a["news"]
    assert body["meta"]["disclaimer"]
    assert r.headers["x-request-id"]


def test_brief_technicals_vpa_screener(client: TestClient) -> None:
    brief = client.get("/api/v1/stocks/ORIONINFU/brief")
    assert brief.status_code == 200
    assert brief.headers["content-type"].startswith("text/markdown")
    assert "## Signal" in brief.text

    tech = client.get("/api/v1/stocks/ORIONINFU/technicals?limit=20").json()
    assert tech["meta"]["count"] == 20
    assert tech["data"][-1]["sma50"] is not None

    vpa = client.get("/api/v1/stocks/ORIONINFU/vpa?days=30").json()
    assert vpa["meta"]["count"] == 30
    assert "Strong buying" in vpa["meta"]["legend"]

    rows = client.get("/api/v1/screener?symbols=ORIONINFU,NOPE").json()["data"]
    assert [(r["symbol"], r["rank"]) for r in rows] == [("ORIONINFU", 1), ("NOPE", 2)]
    assert rows[1]["action"] == "ERROR"


def test_errors_are_problem_json(client: TestClient) -> None:
    r = client.get("/api/v1/stocks/NOPE/analysis")
    assert r.status_code == 404
    assert r.headers["content-type"] == "application/problem+json"
    assert client.get("/api/v1/stocks/bad!sym/analysis").status_code == 400
    assert client.get("/api/v1/stocks/ORIONINFU/vpa?days=1").status_code == 422
    too_many = ",".join(f"S{i}" for i in range(16))
    assert client.get(f"/api/v1/screener?symbols={too_many}").status_code == 400
    assert client.get("/api/v1/screener?symbols=,").status_code == 400
    paths = client.get("/api/v1/openapi.json").json()["paths"]
    assert {"/api/v1/stocks/{symbol}/analysis", "/api/v1/screener", "/api/v1/stocks/{symbol}/vpa"} <= set(
        paths
    )
