"""Adapters over other features' public facades (ARCHITECTURE §4.3)."""

import asyncio
import time as clock
from collections.abc import Callable
from datetime import UTC, date, datetime, time, timedelta
from typing import ClassVar

from dse.features.charts.domain.candles import Candles, aggregate
from dse.features.live_feed.application.facade import LiveFeedFacade
from dse.features.market_data.application.facade import MarketDataFacade
from dse.shared_kernel.symbol import Symbol

DAILY_LIMIT = 400


class DseDailyCandles:
    """Daily candles of a company from the exchange data stored by market_data (synced on first use)."""

    def __init__(self, market_data: MarketDataFacade) -> None:
        self._md = market_data

    async def candles(self, symbol: str, resolution: str, pages: int) -> Candles:
        bars = await self._md.daily_bars(Symbol(symbol), DAILY_LIMIT)
        rows = [
            (
                int(datetime.combine(b.day, time.min, tzinfo=UTC).timestamp()),
                b.open,
                b.high,
                b.low,
                b.close,
                float(b.volume),
            )
            for b in bars
        ]
        return Candles.from_rows(rows)


class RecordedTickCandles:
    """Intraday candles of a company from the prices this app recorded from the exchange's live feed.

    History starts when the app first ran, so a fresh install has only the sessions since then. When recording
    began part-way through a session, the first recorded minute carries everything traded before it; its
    volume is dropped rather than shown as a spike."""

    SESSIONS = 5  # newest trading days to show
    LOOKBACK_DAYS = 9  # calendar days searched to find them (weekends and holidays have no ticks)
    OPEN = time(10, 3)  # a first bar after this is a late start
    CACHE_S = 30.0
    MINUTES: ClassVar[dict[str, int]] = {"1": 1, "5": 5, "30": 30, "60": 60}

    def __init__(self, live: LiveFeedFacade, today: Callable[[], date]) -> None:
        self._live, self._today = live, today
        self._cache: dict[tuple[str, str], tuple[float, Candles]] = {}

    async def candles(self, symbol: str, resolution: str, pages: int) -> Candles:
        key = (symbol, resolution)
        hit = self._cache.get(key)
        if hit and clock.monotonic() - hit[0] < self.CACHE_S:
            return hit[1]
        sym = Symbol(symbol)
        today = self._today()
        days = [today - timedelta(days=i) for i in range(self.LOOKBACK_DAYS)]
        per_day = await asyncio.gather(*(self._live.minute_bars(sym, d) for d in days))
        rows: list[tuple[int, float, float, float, float, float]] = []
        for bars in [b for b in per_day if b][: self.SESSIONS]:
            late = bars[0].minute.time() > self.OPEN
            for i, b in enumerate(bars):
                volume = 0.0 if (i == 0 and late) else float(b.volume)
                rows.append((int(b.minute.timestamp()), b.open, b.high, b.low, b.close, volume))
        out = aggregate(Candles.from_rows(rows), self.MINUTES[resolution])
        self._cache[key] = (clock.monotonic(), out)
        return out
