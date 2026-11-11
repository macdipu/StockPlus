"""Adapters over the other features' public facades (ARCHITECTURE §4.3: facades only)."""

import logging
from collections.abc import Hashable

from dse.features.analysis.application.facade import Bar, QuoteInput, UniverseInput
from dse.features.live_feed.application.facade import LiveFeedFacade
from dse.features.market_data.application.facade import MarketDataFacade
from dse.features.scanner.application.ports import LiveState
from dse.shared_kernel.errors import ServiceNotReadyError

log = logging.getLogger("dse.scanner")
HISTORY_BARS = 400


class FacadeUniverseSource:
    """UniverseSource: history from market_data, quotes + session from live_feed."""

    def __init__(self, market_data: MarketDataFacade, live: LiveFeedFacade) -> None:
        self._md, self._live = market_data, live

    async def history_signature(self) -> Hashable:
        s = await self._md.history_signature()
        return (s.bars, s.last_bar_day, s.fundamentals)

    async def load_history(self) -> list[UniverseInput]:
        out = []
        for h in await self._md.market_history(HISTORY_BARS):
            f = h.fundamentals
            fund = {
                "name": h.name,
                "sector": h.sector,
                "category": h.category,
                "asset_type": h.asset_type,
                "eps_ttm": f.eps_ttm if f else None,
                "nav": f.nav if f else None,
                "dividend_yield_pct": f.dividend_yield_pct if f else None,
                "sponsor_pct": f.shareholding.sponsor_pct if f else None,
                "free_float_pct": f.free_float_pct if f else None,
                "market_cap": f.market_cap if f else None,
                "week_high_52": f.week_high_52 if f else None,
                "week_low_52": f.week_low_52 if f else None,
            }
            bars = tuple(
                Bar(b.day, b.open, b.high, b.low, b.close, float(b.volume), b.trades) for b in h.bars
            )
            out.append(UniverseInput(h.symbol, bars, fund))
        return out

    async def live_state(self) -> LiveState:
        try:
            market = await self._live.market()
            quotes = await self._live.quotes(None)
        except ServiceNotReadyError:
            log.info("live feed not ready; building the universe without quotes")
            return LiveState(None, None, {})
        return LiveState(
            session_day=market.session.day,
            trade_time=market.trade_time,
            quotes={
                q.symbol: QuoteInput(
                    ltp=q.ltp,
                    ycp=q.ycp,
                    open=q.open,
                    high=q.high,
                    low=q.low,
                    close=q.close,
                    volume=float(q.volume),
                    value_mn=q.value_mn,
                    trades=float(q.trades) if q.trades is not None else None,
                    percent=q.percent,
                    sector=q.sector,
                    category=q.category,
                    asset_type=q.asset_type,
                )
                for q in quotes
            },
        )


class LiveFeedUniverseNotifier:
    """Tells SSE clients the universe changed, so they can re-run their scans."""

    def __init__(self, live: LiveFeedFacade) -> None:
        self._live = live

    async def built(self, version: int, rows: int, build_ms: int) -> None:
        await self._live.broadcast("universe", {"version": version, "rows": rows, "build_ms": build_ms})
