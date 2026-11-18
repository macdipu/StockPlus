"""Charts use cases with fake sources and a fake cache; the indicator maths is tested in dse.indicators."""

import asyncio
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest

from dse.features.charts.application.sources import RoutedCandles
from dse.features.charts.application.use_cases import GetChart, ListIndicators
from dse.features.charts.domain.candles import Candles, aggregate
from dse.features.charts.domain.spec import MAX_INDICATORS, parse_specs
from dse.features.charts.infrastructure.dse_index import DHAKA, parse_daily, parse_intraday, parse_week
from dse.features.charts.infrastructure.gateways import RecordedTickCandles
from dse.indicators.base import REGISTRY
from dse.indicators.requirements import required_columns
from dse.shared_kernel.errors import NotFoundError, ValidationFailedError


def make_candles(n: int = 120, seed: int = 3) -> Candles:
    rng = np.random.RandomState(seed)
    close = 100 + np.cumsum(rng.normal(0, 1, n))
    open_ = close + rng.normal(0, 0.3, n)
    high = np.maximum(open_, close) + rng.uniform(0, 0.5, n)
    low = np.minimum(open_, close) - rng.uniform(0, 0.5, n)
    rows = [(1_700_000_000 + i * 86400, open_[i], high[i], low[i], close[i], 1000.0 + i) for i in range(n)]
    return Candles.from_rows(rows)


class FakeSource:
    def __init__(self, candles: Candles | None) -> None:
        self.candles_ = candles
        self.calls = 0

    async def candles(self, symbol: str, resolution: str, pages: int) -> Candles:
        self.calls += 1
        await asyncio.sleep(0.005)
        if self.candles_ is None:
            raise NotFoundError("nope")
        return self.candles_


class MemoryCache:
    def __init__(self) -> None:
        self.data: dict[str, dict[str, Any]] = {}
        self.puts = 0

    async def get(self, key: str) -> dict[str, Any] | None:
        return self.data.get(key)

    async def put(self, key: str, value: dict[str, Any], ttl_s: int) -> None:
        self.puts += 1
        self.data[key] = value


FIX = Path(__file__).parent / "fixtures"


def make_use_case(candles: Candles | None = None) -> tuple[GetChart, FakeSource, MemoryCache]:
    daily = FakeSource(candles or make_candles())
    index = FakeSource(
        Candles.from_closes([(1_700_000_000 + i * 86400, 5000 + i * 3.0 + (i % 5)) for i in range(120)])
    )
    ticks = FakeSource(make_candles(60, seed=9))
    cache = MemoryCache()
    return GetChart(RoutedCandles(daily, index, ticks), cache, ListIndicators()), daily, cache


def test_candles_are_sorted_deduplicated_and_fingerprinted() -> None:
    c = Candles.from_rows([(2, 1, 2, 0.5, 1.5, 10), (1, 1, 2, 0.5, 1.0, 10), (2, 1, 2, 0.5, 1.8, 11)])
    assert c.time.tolist() == [1, 2]
    assert c.close.tolist() == [1.0, 1.8]
    same = Candles.from_rows([(1, 1, 2, 0.5, 1.0, 10), (2, 1, 2, 0.5, 1.8, 11)])
    revised = Candles.from_rows([(1, 1, 2, 0.5, 1.0, 10), (2, 1, 2, 0.5, 1.9, 11)])
    assert c.fingerprint() == same.fingerprint() != revised.fingerprint()
    assert list(c.frame().columns) == ["open", "high", "low", "close", "volume"]


def test_spec_parsing_positional_params_and_errors() -> None:
    reg = REGISTRY
    assert reg, "the indicator catalog is empty"
    some = next(i for i in reg.values() if i.params)
    first = some.params[0]
    spec = parse_specs(f"{some.id}({int(first.default)})")[0]
    assert spec.key.startswith(some.id)
    assert spec.params[first.key] == first.default
    assert [s.key for s in parse_specs(f"{some.id},{some.id}")] == [
        parse_specs(some.id)[0].key
    ]  # duplicates collapse
    for bad in (
        "nope",
        f"{some.id}(1",
        f"{some.id}(a)",
        f"{some.id}(" + ",".join("1" * 20) + ")",
        f"{some.id})",
    ):
        with pytest.raises(ValidationFailedError):
            parse_specs(bad)
    many = ",".join(f"{some.id}({i + 2})" for i in range(MAX_INDICATORS + 1))
    if some.params[0].max >= MAX_INDICATORS + 2:
        with pytest.raises(ValidationFailedError, match="at most"):
            parse_specs(many)


async def test_chart_is_computed_once_cached_and_conditional() -> None:
    uc, _daily, cache = make_use_case()
    ind = next(i for i in REGISTRY.values() if i.placement == "pane")
    a = await uc("GP", "D", ind.id)
    assert a.chart is not None
    assert len(a.chart.candles.time) == 120
    assert a.chart.indicators[0].key.startswith(ind.id)
    assert all(len(s) == 120 for s in a.chart.indicators[0].series.values())  # one value per candle
    assert a.chart.source == "dse-daily"
    b = await uc("GP", "D", ind.id)
    assert cache.puts == 1
    assert b.etag == a.etag
    c = await uc("GP", "D", ind.id, if_none_match=a.etag)
    assert c.chart is None
    assert c.etag == a.etag
    d = await uc("GP", "D", None)
    assert d.etag != a.etag
    assert d.chart is not None
    assert d.chart.indicators == []


async def test_concurrent_identical_requests_share_one_computation() -> None:
    uc, _, cache = make_use_case()
    ind = next(iter(REGISTRY.values()))
    results = await asyncio.gather(*(uc("GP", "D", ind.id) for _ in range(6)))
    assert cache.puts == 1
    assert len({r.etag for r in results}) == 1


async def test_source_routing_and_errors() -> None:
    uc, _daily, _ = make_use_case()
    for symbol, resolution, expected in (
        ("GP", "5", "recorded-ticks"),
        ("DSEX", "D", "dse-index"),
        ("DSEX", "5", "dse-index"),
        ("GP", "D", "dse-daily"),
    ):
        chart = (await uc(symbol, resolution, None)).chart
        assert chart is not None
        assert chart.source == expected
    with pytest.raises(ValidationFailedError):
        await uc("GP", "15", None)
    nothing = FakeSource(Candles.from_rows([]))
    empty = GetChart(RoutedCandles(nothing, nothing, nothing), MemoryCache(), ListIndicators())
    with pytest.raises(NotFoundError):
        await empty("GP", "D", None)
    with pytest.raises(NotFoundError, match="records during market hours"):
        await empty("GP", "5", None)  # intraday of a company comes from recorded prices


async def test_an_index_chart_leaves_out_indicators_that_need_volume_or_high_low() -> None:
    uc, _, _ = make_use_case()
    close_only = next(i.id for i in REGISTRY.values() if not required_columns(i.id) and i.params)
    needs_volume = next(i.id for i in REGISTRY.values() if "volume" in required_columns(i.id))
    chart = (await uc("DSEX", "D", f"{close_only},{needs_volume}")).chart
    assert chart is not None
    assert chart.ohlc is False
    assert [i.id for i in chart.indicators] == [close_only]
    assert len(chart.warnings) == 1
    assert "volume" in chart.warnings[0]
    stock = (await uc("GP", "D", f"{close_only},{needs_volume}")).chart
    assert stock is not None
    assert stock.ohlc is True
    assert len(stock.indicators) == 2
    assert stock.warnings == []


def test_required_columns_are_found_by_trying_the_indicator() -> None:
    assert required_columns("sma") == ()  # closes only
    assert required_columns("rsi") == ()
    assert set(required_columns("atr")) == {"high", "low"}
    assert required_columns("obv") == ("volume",)
    assert "volume" in required_columns("vwap")  # a ratio of volume-weighted sums: still volume-dependent
    assert "volume" in required_columns("mfi")


def test_catalog_is_grouped_versioned_and_stable() -> None:
    a, b = ListIndicators()(), ListIndicators()()
    assert a.version == b.version
    assert a.indicators == b.indicators
    assert {e.group for e in a.indicators} <= set(a.groups)
    assert all(e.outputs and e.description for e in a.indicators)


def test_index_history_labels_become_timestamps() -> None:
    daily = parse_daily(json.loads((FIX / "dse_index_history_1Y.json").read_text()))
    assert len(daily) > 200
    assert daily == sorted(daily)
    assert datetime.fromtimestamp(daily[0][0], UTC).date() == date(
        2025, 11, 18
    )  # "18 Nov '25": the year is in the label
    assert datetime.fromtimestamp(daily[-1][0], UTC).date() == date(2026, 11, 17)
    week = parse_week(json.loads((FIX / "dse_index_history_1W.json").read_text()))
    first = datetime.fromtimestamp(week[0][0], DHAKA)
    assert (first.date(), first.hour, first.minute) == (
        date(2026, 11, 11),
        10,
        0,
    )  # "11 Nov, 10:00" Dhaka time
    assert all(
        10 <= datetime.fromtimestamp(t, DHAKA).hour <= 14 for t, _ in week
    )  # inside the trading session
    today = parse_intraday(json.loads((FIX / "dse_index_intraday.json").read_text()))
    assert datetime.fromtimestamp(today[0][0], DHAKA).strftime("%Y-%m-%d %H:%M") == "2026-11-18 10:00"


def test_a_label_without_a_year_takes_the_latest_year_not_after_the_session_date() -> None:
    payload = {
        "session": {"date": "2026-01-10"},
        "points": [{"t": "20 Dec", "value": 5.0}, {"t": "05 Jan", "value": 6.0}],
    }
    got = [datetime.fromtimestamp(t, UTC).date() for t, _ in parse_daily(payload)]
    assert got == [date(2025, 12, 20), date(2026, 1, 5)]
    assert (
        parse_daily({"points": [{"t": "junk", "value": 1}, {"t": "18 Nov '25", "value": 0}]}) == []
    )  # bad rows dropped


def test_aggregating_minutes_into_larger_candles() -> None:
    base = 1_700_000_040  # not on a boundary
    rows = [(base + 60 * i, 10.0 + i, 11.0 + i, 9.0 + i, 10.5 + i, 100.0) for i in range(12)]
    out = aggregate(Candles.from_rows(rows), 5)
    assert out.time.tolist() == sorted({(base + 60 * i) // 300 * 300 for i in range(12)})
    first = out.open[0], out.high[0], out.low[0], out.close[0], out.volume[0]
    n = sum(1 for r in rows if r[0] // 300 * 300 == out.time[0])  # candles that fell in the first bucket
    assert first == (
        10,
        11 + n - 1,
        9,
        10.5 + n - 1,
        100.0 * n,
    )  # open of the first, extremes, close of the last, summed volume
    assert aggregate(Candles.from_rows(rows), 1) is not None
    assert len(aggregate(Candles.from_rows(rows), 1)) == 12
    assert out.volume.sum() == 1200.0


async def test_recorded_ticks_become_intraday_candles_and_a_late_start_drops_its_volume_spike() -> None:
    tz = DHAKA
    today = date(2026, 11, 18)

    def minute(d: date, h: int, m: int, price: float, vol: int) -> Any:
        return SimpleNamespace(
            minute=datetime(d.year, d.month, d.day, h, m, tzinfo=tz),
            open=price,
            high=price + 1,
            low=price - 1,
            close=price,
            volume=vol,
        )

    class FakeLive:
        async def minute_bars(self, symbol: Any, day: date) -> list[Any]:
            if day == today:  # recording began at 11:20: the first bar holds everything traded before it
                return [
                    minute(day, 11, 20, 100, 50_000),
                    minute(day, 11, 21, 101, 10),
                    minute(day, 11, 22, 102, 20),
                ]
            if day == today - timedelta(days=1):  # a full session starting at the open
                return [minute(day, 10, 0, 90, 700), minute(day, 10, 1, 91, 30)]
            return []

    src = RecordedTickCandles(FakeLive(), lambda: today)  # type: ignore[arg-type]
    one = await src.candles("GP", "1", 1)
    assert len(one) == 5
    assert one.ohlc
    volumes = dict(
        zip(
            ((datetime.fromtimestamp(t, tz).day, datetime.fromtimestamp(t, tz).minute) for t in one.time),
            one.volume,
            strict=True,
        )
    )
    assert volumes[(18, 20)] == 0.0
    assert volumes[(17, 0)] == 700.0
    five = await src.candles("GP", "5", 1)
    assert len(five) == 2
    assert five.volume.tolist() == [730.0, 30.0]
    assert datetime.fromtimestamp(int(five.time[0]), tz).strftime("%d %H:%M") == "17 10:00"  # oldest first
