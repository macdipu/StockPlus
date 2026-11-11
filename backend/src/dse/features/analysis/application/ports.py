"""The analysis use cases depend on this port; infrastructure fulfils it from other features' facades."""

from datetime import date
from typing import Protocol

from dse.features.analysis.application.inputs import AnalysisInput, MinuteInput
from dse.features.analysis.domain.frames import Bar, LiveBar


class AnalysisInputs(Protocol):
    async def load(self, symbol: str) -> AnalysisInput:
        """Raises NotFoundError for an unknown symbol."""
        ...


class HistorySource(Protocol):
    """Daily history and recorded intraday bars, without the rest of an instrument's profile."""

    async def bars(self, symbol: str, limit: int) -> tuple[Bar, ...]:
        """Most recent daily bars, oldest first; empty for an instrument with none."""
        ...

    async def live_bar(self, symbol: str) -> LiveBar | None:
        """Today's partial bar from the live feed, or None when there is no quote or the feed is down."""
        ...

    async def minute_bars(self, symbol: str, day: date | None) -> tuple[MinuteInput, ...]: ...
