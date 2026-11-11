"""AnalysisInputs adapter: assembles one instrument from the market_data and live_feed public facades.

Cross-feature rule (ARCHITECTURE §4.3): only `<feature>.application.facade` may be imported.
"""

import logging
from datetime import date

from dse.features.analysis.application.inputs import AnalysisInput, MinuteInput
from dse.features.analysis.domain.frames import Bar, LiveBar
from dse.features.live_feed.application.facade import LiveFeedFacade
from dse.features.market_data.application.facade import MarketDataFacade
from dse.shared_kernel.errors import ServiceNotReadyError
from dse.shared_kernel.symbol import Symbol

log = logging.getLogger("dse.analysis")
HISTORY_BARS = 600


class FacadeAnalysisInputs:
    def __init__(self, market_data: MarketDataFacade, live: LiveFeedFacade) -> None:
        self._md, self._live = market_data, live

    async def load(self, symbol: str) -> AnalysisInput:
        sym = Symbol(symbol)
        profile = await self._md.profile(sym)  # read-through: syncs from DSE when stale; 404 if unknown
        bars = await self._md.daily_bars(sym, HISTORY_BARS)
        announcements = await self._md.announcements(sym, 20)

        quote = market = None
        try:
            quotes = await self._live.quotes([sym.value])
            quote = quotes[0] if quotes else None
            market = await self._live.market()
        except ServiceNotReadyError:
            log.info("live feed not ready; analysing stored bars only", extra={"symbol": sym.value})

        live = None
        if quote and market and market.session.day:
            live = LiveBar(
                session_day=market.session.day,
                ltp=quote.ltp,
                open=quote.open,
                high=quote.high,
                low=quote.low,
                close=quote.close,
                volume=float(quote.volume),
                trades=float(quote.trades) if quote.trades is not None else None,
            )
        f = profile.fundamentals
        fund = {
            **f.model_dump(mode="json"),
            "name": profile.name,
            "sector": profile.sector,
            "category": profile.category,
            "board": profile.board,
            "isin": profile.isin,
            "ltp": quote.ltp if quote and quote.ltp else profile.last_close,
            "prev_close": quote.ycp if quote else None,
            "dps": f.dividend_per_share,
        }
        return AnalysisInput(
            symbol=sym.value,
            name=profile.name,
            category=profile.category,
            fundamentals=fund,
            bars=tuple(Bar(b.day, b.open, b.high, b.low, b.close, float(b.volume), b.trades) for b in bars),
            live=live,
            market_open=bool(market and market.session.is_open),
            as_of=(quote.trade_time if quote and quote.trade_time else None)
            or (profile.synced_at.isoformat() if profile.synced_at else ""),
            value_mn=quote.value_mn if quote else None,
            news=tuple(
                {
                    "id": a.id,
                    "date": a.published_on.isoformat() if a.published_on else None,
                    "type": a.kind,
                    "title": a.title,
                    "text": a.body,
                }
                for a in announcements
            ),
        )


class FacadeHistorySource:
    """HistorySource: daily bars from market_data, live bar and recorded minutes from live_feed."""

    def __init__(self, market_data: MarketDataFacade, live: LiveFeedFacade) -> None:
        self._md, self._live = market_data, live

    async def bars(self, symbol: str, limit: int) -> tuple[Bar, ...]:
        rows = await self._md.daily_bars(Symbol(symbol), limit)
        return tuple(Bar(b.day, b.open, b.high, b.low, b.close, float(b.volume), b.trades) for b in rows)

    async def live_bar(self, symbol: str) -> LiveBar | None:
        try:
            quotes = await self._live.quotes([symbol])
            market = await self._live.market()
        except ServiceNotReadyError:
            return None
        if not quotes or market.session.day is None:
            return None
        q = quotes[0]
        return LiveBar(
            market.session.day,
            q.ltp,
            q.open,
            q.high,
            q.low,
            q.close,
            float(q.volume),
            float(q.trades) if q.trades is not None else None,
        )

    async def minute_bars(self, symbol: str, day: date | None) -> tuple[MinuteInput, ...]:
        rows = await self._live.minute_bars(Symbol(symbol), day)
        return tuple(MinuteInput(m.minute, m.open, m.high, m.low, m.close, float(m.volume)) for m in rows)
