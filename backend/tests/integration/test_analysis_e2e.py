"""Analysis through the real stack: HTTP → analysis → market_data + live_feed facades → Postgres + Redis.

DSE is faked (recorded page bytes); everything else is real. Redis db 15, like the live_feed tests.
"""

import asyncio
import gzip
import json
import math
from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from dse.core.cache import create_redis
from dse.core.clock import SystemClock
from dse.core.config import RedisSettings, Settings, get_settings
from dse.features.analysis.infrastructure.gateways import FacadeAnalysisInputs, FacadeHistorySource
from dse.features.analysis.presentation.dependencies import AnalysisContainer
from dse.features.live_feed.domain.entities import LiveSnapshot
from dse.features.live_feed.infrastructure.dse_snapshot import parse_live_snapshot
from dse.features.live_feed.infrastructure.redis_adapters import RedisLiveStateStore
from dse.features.market_data.domain.entities import CompanyPage, DailyBar
from dse.features.market_data.infrastructure.dse_parser import parse_company_page
from dse.features.market_data.presentation.dependencies import MarketDataContainer
from dse.features.market_data.tests.fakes import NOW, FakeSource
from dse.main import create_app
from dse.shared_kernel.symbol import Symbol

pytestmark = pytest.mark.integration
MD = Path(__file__).parents[2] / "src/dse/features/market_data/tests/fixtures"
TABLES = "announcements, daily_bars, fundamentals, instruments, ticks"


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


def second_page(page: CompanyPage) -> CompanyPage:
    """A second instrument: the recorded one with every price scaled by a day-dependent factor."""
    sym = Symbol("ORIONTWO")

    def scaled(b: DailyBar, i: int) -> DailyBar:
        f = Decimal(str(round(1 + 0.03 * math.sin(i * 1.7), 6)))
        q = Decimal("0.01")
        return replace(
            b,
            symbol=sym,
            open=(b.open * f).quantize(q),
            high=(b.high * f).quantize(q),
            low=(b.low * f).quantize(q),
            close=(b.close * f).quantize(q),
        )

    return replace(
        page,
        instrument=replace(page.instrument, symbol=sym, name="Orion Two Ltd."),
        bars=tuple(scaled(b, i) for i, b in enumerate(page.bars)),
        announcements=(),
    )


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
        pages = {"ORIONINFU": page, "ORIONTWO": second_page(page)}
        md = MarketDataContainer(app.state.db, FakeSource(pages), SystemClock())
        app.state.market_data = md
        app.state.analysis = AnalysisContainer(
            FacadeAnalysisInputs(md.facade, app.state.live_feed.facade),
            FacadeHistorySource(md.facade, app.state.live_feed.facade),
        )
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


# ============================================================================== intraday, tools, CSV
def insert_ticks(symbol: str, count: int = 30) -> list[datetime]:
    """`count` minutes of ticks for today (exchange time), two per minute, cumulative volume rising."""
    from dse.core.clock import DHAKA
    from dse.core.db import Database

    start = datetime.now(DHAKA).replace(hour=10, minute=0, second=0, microsecond=0)
    stamps = [start + timedelta(minutes=m, seconds=s) for m in range(count) for s in (5, 35)]

    async def go() -> None:
        db = Database(settings().database)
        try:
            async with db.engine.begin() as c:
                for i, ts in enumerate(stamps):
                    await c.execute(
                        text(
                            "INSERT INTO ticks (symbol, ts, trade_time, ltp, high, low, volume) "
                            "VALUES (:s, :ts, 't', :p, :p, :p, :v)"
                        ),
                        {
                            "s": symbol,
                            "ts": ts.astimezone(UTC),
                            "p": 100 + (i % 7) * 0.1,
                            "v": 1000 + i * 100,
                        },
                    )
        finally:
            await db.dispose()

    asyncio.run(go())
    return stamps


def test_intraday_bars_come_from_recorded_ticks(client: TestClient) -> None:
    empty = client.get("/api/v1/stocks/ORIONINFU/intraday").json()
    assert empty["data"] == []
    assert "No ticks recorded" in empty["meta"]["note"]

    insert_ticks("ORIONINFU", 30)
    body = client.get("/api/v1/stocks/ORIONINFU/intraday").json()
    rows = body["data"]
    assert body["meta"]["count"] == len(rows) == 30
    assert [r["time"] for r in rows[:3]] == ["10:00", "10:01", "10:02"]
    assert rows[0]["volume"] == 1100  # the first tick carries the volume traded before recording began
    assert all(r["volume"] == 200 for r in rows[1:])  # then two +100 ticks per minute
    assert all(r["low"] <= r["open"] <= r["high"] for r in rows)
    assert {"vpa"} <= set(rows[0])

    yesterday = (datetime.now().date() - timedelta(days=1)).isoformat()
    assert client.get(f"/api/v1/stocks/ORIONINFU/intraday?day={yesterday}").json()["data"] == []
    assert client.get("/api/v1/stocks/ORIONINFU/intraday?day=not-a-date").status_code == 422
    assert client.get("/api/v1/stocks/BATBC/intraday").json()["data"] == []  # other instruments have no ticks


def stored_closes(client: TestClient, symbol: str) -> dict[str, float]:
    rows = client.get(f"/api/v1/stocks/{symbol}/candles?limit=400").json()["data"]
    return {r["day"]: r["close"] for r in rows}


def test_return_tool_matches_the_stored_prices(client: TestClient) -> None:
    closes = stored_closes(client, "ORIONINFU")
    days = sorted(closes)
    buy, sell = days[10], days[200]
    r = client.get(
        "/api/v1/tools/return",
        params={"symbol": "orioninfu", "buy_date": buy, "sell_date": sell, "quantity": 50, "fee_pct": 0.5},
    )
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert (d["symbol"], d["buy_date"], d["sell_date"]) == ("ORIONINFU", buy, sell)
    assert (d["buy_price"], d["sell_price"]) == (closes[buy], closes[sell])
    cost, proceeds = closes[buy] * 50 * 1.005, closes[sell] * 50 * 0.995
    assert d["cost"] == pytest.approx(cost)
    assert d["profit"] == pytest.approx(proceeds - cost)
    assert d["return_pct"] == pytest.approx((proceeds / cost - 1) * 100)
    assert d["days"] == (date.fromisoformat(sell) - date.fromisoformat(buy)).days
    assert "dividends" in d["note"]

    latest = client.get("/api/v1/tools/return", params={"symbol": "ORIONINFU", "buy_date": days[-30]}).json()[
        "data"
    ]
    assert latest["sell_price"] == 217.3  # no sell date: today's live quote is the exit price


def test_return_tool_validation(client: TestClient) -> None:
    base = {"symbol": "ORIONINFU", "buy_date": "2025-11-01"}
    bad_range = client.get("/api/v1/tools/return", params={**base, "buy_date": "2030-01-01"})
    assert bad_range.status_code == 400
    assert "No bars between" in bad_range.json()["detail"]
    assert client.get("/api/v1/tools/return", params={**base, "fee_pct": 9}).status_code == 422
    assert client.get("/api/v1/tools/return", params={**base, "quantity": 0}).status_code == 422
    assert client.get("/api/v1/tools/return", params={"symbol": "ORIONINFU"}).status_code == 422
    assert client.get("/api/v1/tools/return", params={**base, "buy_date": "yesterday"}).status_code == 422
    assert client.get("/api/v1/tools/return", params={**base, "symbol": "NOPE"}).status_code == 404


def test_correlation_tool(client: TestClient) -> None:
    r = client.get(
        "/api/v1/tools/correlation", params={"symbols": "orioninfu, ORIONTWO,ORIONINFU", "days": 120}
    )
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["symbols"] == ["ORIONINFU", "ORIONTWO"]
    m = d["matrix"]
    assert m[0][0] == pytest.approx(1.0)
    assert m[1][1] == pytest.approx(1.0)
    assert m[0][1] == m[1][0]
    assert -1 <= m[0][1] <= 1

    one = client.get("/api/v1/tools/correlation", params={"symbols": "ORIONINFU"})
    assert one.status_code == 400
    assert "at least two" in one.json()["detail"]
    assert (
        client.get(
            "/api/v1/tools/correlation", params={"symbols": "ORIONINFU,ORIONTWO", "days": 5}
        ).status_code
        == 422
    )
    assert client.get("/api/v1/tools/correlation", params={"symbols": "ORIONINFU,NOPE"}).status_code == 404


def test_csv_download(client: TestClient) -> None:
    r = client.get("/api/v1/data/orioninfu.csv")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert r.headers["content-disposition"] == 'attachment; filename="ORIONINFU.csv"'
    lines = r.text.strip().split("\n")
    assert lines[0] == "date,open,high,low,close,volume,trades"
    assert len(lines) == 261  # header + 260 recorded sessions
    days = [ln.split(",")[0] for ln in lines[1:]]
    assert days == sorted(days)
    first = lines[1].split(",")
    assert float(first[3]) <= float(first[2])  # low <= high
    assert client.get("/api/v1/data/NOPE.csv").status_code == 404
