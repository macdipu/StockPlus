"""The ONLY entry point other features may use (import-linter enforces this)."""

from collections.abc import Sequence
from datetime import date
from typing import Any

from dse.features.live_feed.application.dto import MarketDto, QuoteDto
from dse.features.live_feed.application.use_cases import BroadcastEvent, GetMarket, GetMinuteBars, GetQuotes
from dse.features.live_feed.domain.entities import MinuteBar
from dse.shared_kernel.symbol import Symbol


class LiveFeedFacade:
    def __init__(
        self,
        quotes: GetQuotes,
        market: GetMarket,
        broadcast: BroadcastEvent | None = None,
        minutes: GetMinuteBars | None = None,
    ) -> None:
        self._quotes, self._market, self._broadcast, self._minutes = quotes, market, broadcast, minutes

    async def quotes(self, symbols: Sequence[str] | None = None) -> list[QuoteDto]:
        return await self._quotes(symbols)

    async def market(self) -> MarketDto:
        return await self._market()

    async def broadcast(self, event: str, data: dict[str, Any]) -> None:
        """Publish a custom SSE event to every replica. Needs a publisher, which only the worker wires."""
        if self._broadcast is None:
            raise RuntimeError("this process has no event publisher")
        await self._broadcast(event, data)

    async def minute_bars(self, symbol: Symbol, day: date | None = None) -> list[MinuteBar]:
        """1-minute bars for `day` (default: today) from recorded ticks. Only the API container wires this."""
        if self._minutes is None:
            raise RuntimeError("this process has no tick reader")
        return await self._minutes(symbol, day)
