"""The ONLY entry point other features may use (import-linter enforces this)."""

from collections.abc import Sequence

from dse.features.live_feed.application.dto import MarketDto, QuoteDto
from dse.features.live_feed.application.use_cases import GetMarket, GetQuotes


class LiveFeedFacade:
    def __init__(self, quotes: GetQuotes, market: GetMarket) -> None:
        self._quotes, self._market = quotes, market

    async def quotes(self, symbols: Sequence[str] | None = None) -> list[QuoteDto]:
        return await self._quotes(symbols)

    async def market(self) -> MarketDto:
        return await self._market()
