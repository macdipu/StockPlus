"""What the analysis needs to know about one instrument, independent of where it came from."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from dse.features.analysis.domain.frames import Bar, LiveBar


@dataclass(frozen=True, slots=True)
class AnalysisInput:
    symbol: str
    name: str | None
    category: str | None
    fundamentals: dict[str, Any]  # profile fields + ltp, prev_close, dps (valuation reads these)
    bars: tuple[Bar, ...]
    live: LiveBar | None
    market_open: bool
    as_of: str
    value_mn: float | None = None
    news: tuple[dict[str, Any], ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class QuoteInput:
    """A live quote, as the universe build needs it (all fields optional except volume)."""

    ltp: float | None = None
    ycp: float | None = None
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    volume: float = 0.0
    value_mn: float | None = None
    trades: float | None = None
    percent: float | None = None
    sector: str | None = None
    category: str | None = None
    asset_type: str | None = None


@dataclass(frozen=True, slots=True)
class UniverseInput:
    """One instrument's history + fundamentals + (optional) live quote."""

    symbol: str
    bars: tuple[Bar, ...]
    fundamentals: dict[str, Any]  # name, sector, category, eps_ttm, nav, dividend_yield_pct, sponsor_pct,
    quote: QuoteInput | None = None  # free_float_pct, market_cap, week_high_52, week_low_52


@dataclass(frozen=True, slots=True)
class UniverseRows:
    rows: list[dict[str, Any]]
    errors: dict[str, str]


@dataclass(frozen=True, slots=True)
class MinuteInput:
    """One recorded 1-minute bar (exchange time)."""

    minute: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
