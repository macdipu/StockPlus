"""Live-feed domain model: the latest market state and the rules for what counts as a change.

Pure Python: no framework, no I/O. Timestamps are epoch milliseconds (what SSE clients measure latency in).
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime, time
from typing import Any

from dse.shared_kernel.symbol import Symbol

# A quote counts as changed only when one of these moves (percent/category changes alone are noise).
QUOTE_FIELDS = ("ltp", "open", "high", "low", "close", "volume", "trades", "value_mn")


@dataclass(frozen=True, slots=True)
class LiveQuote:
    symbol: Symbol
    ltp: float | None
    ycp: float | None
    open: float | None
    high: float | None
    low: float | None
    close: float | None  # official close; None while the session is open
    volume: int
    value_mn: float | None
    trades: int | None
    percent: float | None
    category: str | None
    board: str | None
    sector: str | None
    asset_type: str | None

    @property
    def change(self) -> float | None:
        if self.ltp and self.ycp:
            return round(self.ltp - self.ycp, 4)
        return None

    def differs_from(self, other: "LiveQuote") -> bool:
        return any(getattr(self, f) != getattr(other, f) for f in QUOTE_FIELDS)


@dataclass(frozen=True, slots=True)
class SessionState:
    day: date | None
    is_open: bool
    trading_day: bool
    phase: str | None = None
    opening: time | None = None
    closing: time | None = None

    def is_after_close(self, now: datetime) -> bool:
        """True once today's trading day is over: the moment end-of-day bars become final.

        `is_open` alone is not enough: it is also False before the opening bell, when the snapshot still
        carries the previous session's prices.
        """
        if not self.trading_day or self.is_open or self.day is None or self.closing is None:
            return False
        return now.date() == self.day and now.time() >= self.closing


@dataclass(frozen=True, slots=True)
class IndexLevel:
    key: str
    value: float | None
    change: float | None
    percent: float | None


@dataclass(frozen=True, slots=True)
class MarketSummary:
    indices: tuple[IndexLevel, ...] = ()
    totals: Mapping[str, Any] = field(default_factory=dict)  # trades, volume, turnover, marketCap
    breadth: Mapping[str, Any] = field(default_factory=dict)  # advanced, declined, unchanged, traded
    movers: Mapping[str, Any] = field(default_factory=dict)  # gainers/losers/active as DSE ships them


@dataclass(frozen=True, slots=True)
class MarketState:
    """Everything market-wide in one snapshot (no per-instrument quotes)."""

    session: SessionState
    trade_time: str | None
    summary: MarketSummary


@dataclass(frozen=True, slots=True)
class LiveSnapshot:
    state: MarketState
    quotes: Mapping[str, LiveQuote]

    @property
    def session(self) -> SessionState:
        return self.state.session

    @property
    def trade_time(self) -> str | None:
        return self.state.trade_time

    def changes_since(self, previous: "LiveSnapshot | None") -> "SnapshotChanges":
        """What a subscriber needs to hear about. The first snapshot ever seen announces nothing:
        clients get full state on connect, so replaying the whole market as 'changes' is pure noise."""
        if previous is None:
            return SnapshotChanges(quotes=(), market_changed=False, first=True)
        changed = tuple(
            q
            for sym, q in sorted(self.quotes.items())
            if sym not in previous.quotes or q.differs_from(previous.quotes[sym])
        )
        market_changed = self.trade_time != previous.trade_time or self.session != previous.session
        return SnapshotChanges(quotes=changed, market_changed=market_changed, first=False)


@dataclass(frozen=True, slots=True)
class SnapshotChanges:
    quotes: tuple[LiveQuote, ...]
    market_changed: bool
    first: bool

    @property
    def any(self) -> bool:
        return bool(self.quotes) or self.market_changed


@dataclass(frozen=True, slots=True)
class Tick:
    """One recorded quote change: the raw material for intraday (1-minute) bars."""

    symbol: Symbol
    ts_ms: int
    trade_time: str | None
    ltp: float | None
    high: float | None
    low: float | None
    volume: int
    value_mn: float | None
    trades: int | None

    @classmethod
    def of(cls, quote: LiveQuote, ts_ms: int, trade_time: str | None) -> "Tick":
        return cls(
            quote.symbol,
            ts_ms,
            trade_time,
            quote.ltp,
            quote.high,
            quote.low,
            quote.volume,
            quote.value_mn,
            quote.trades,
        )


@dataclass(frozen=True, slots=True)
class PollPolicy:
    """How often to ask upstream. DSE publishes ~once a minute behind a 10-15 s CDN cache, so polling faster
    than `open_s` only re-reads the cache. Failures back off exponentially (5 s → 120 s cap)."""

    open_s: float = 10.0
    closed_s: float = 60.0
    floor_s: float = 5.0
    backoff_start_s: float = 5.0
    backoff_cap_s: float = 120.0

    def interval(self, session: SessionState | None) -> float:
        base = self.open_s if session is None or session.is_open else self.closed_s
        return max(self.floor_s, base)

    def next_backoff(self, current: float) -> float:
        return min(max(current * 2, self.backoff_start_s), self.backoff_cap_s)
