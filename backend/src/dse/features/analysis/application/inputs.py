"""What the analysis needs to know about one instrument, independent of where it came from."""

from dataclasses import dataclass, field
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
