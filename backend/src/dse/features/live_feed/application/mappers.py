"""Entity → DTO mapping (one direction only: presentation never builds entities)."""

from dse.features.live_feed.application.dto import (
    FeedCounters,
    FeedStatusDto,
    IndexDto,
    MarketDto,
    QuoteDto,
    SessionDto,
)
from dse.features.live_feed.domain.entities import LiveQuote, MarketState, SessionState


def quote_dto(q: LiveQuote, trade_time: str | None) -> QuoteDto:
    return QuoteDto(
        symbol=q.symbol.value,
        ltp=q.ltp,
        ycp=q.ycp,
        open=q.open,
        high=q.high,
        low=q.low,
        close=q.close,
        change=q.change,
        percent=q.percent,
        volume=q.volume,
        value_mn=q.value_mn,
        trades=q.trades,
        category=q.category,
        board=q.board,
        sector=q.sector,
        asset_type=q.asset_type,
        trade_time=trade_time,
    )


def session_dto(s: SessionState) -> SessionDto:
    return SessionDto(
        day=s.day,
        is_open=s.is_open,
        trading_day=s.trading_day,
        phase=s.phase,
        opening=s.opening.strftime("%H:%M") if s.opening else None,
        closing=s.closing.strftime("%H:%M") if s.closing else None,
    )


def market_dto(m: MarketState) -> MarketDto:
    return MarketDto(
        session=session_dto(m.session),
        trade_time=m.trade_time,
        indices=[
            IndexDto(key=i.key, value=i.value, change=i.change, percent=i.percent) for i in m.summary.indices
        ],
        totals=dict(m.summary.totals),
        breadth=dict(m.summary.breadth),
        movers=dict(m.summary.movers),
    )


def feed_status_dto(c: FeedCounters | None, now_ms: int, stale_after_ms: int) -> FeedStatusDto:
    c = c or FeedCounters()

    def age(ts: int | None) -> int | None:
        return now_ms - ts if ts is not None else None

    ok_age = age(c.last_ok_ms)
    return FeedStatusDto(
        ready=c.last_ok_ms is not None and c.symbols > 0,
        stale=ok_age is None or ok_age > stale_after_ms,
        market_open=c.market_open,
        trade_time=c.trade_time,
        symbols=c.symbols,
        poll_interval_s=c.poll_interval_s,
        last_poll_age_ms=age(c.last_poll_ms),
        last_success_age_ms=ok_age,
        last_change_age_ms=age(c.last_change_ms),
        polls=c.polls,
        not_modified=c.not_modified,
        changes=c.changes,
        last_error=c.last_error,
    )
