"""Adapters over other features' public facades (ARCHITECTURE §4.3)."""

from typing import Any

from dse.features.analysis.application.facade import AnalysisFacade
from dse.features.company.domain.entities import AmarStockPart, ExchangePart, TopStockPart
from dse.features.company.infrastructure.exchange import exchange_part
from dse.features.company.infrastructure.http_sources import HttpCompanySources
from dse.features.live_feed.application.facade import LiveFeedFacade
from dse.features.market_data.application.facade import MarketDataFacade
from dse.shared_kernel.symbol import Symbol


class LiveFeedPrices:
    def __init__(self, live: LiveFeedFacade) -> None:
        self._live = live

    async def last_price(self, symbol: str) -> float | None:
        try:
            quotes = await self._live.quotes([symbol])
        except Exception:
            return None
        for q in quotes:
            if q.symbol == symbol:
                return q.ltp or q.close or q.ycp
        return None


class FacadeAnalysis:
    def __init__(self, analysis: AnalysisFacade) -> None:
        self._analysis = analysis

    async def analysis(self, symbol: str) -> dict[str, Any]:
        return (await self._analysis.analyze(symbol)).model_dump(mode="json")


class CompanySourceSet:
    """The three company sources behind one port: the exchange's own page (through market_data, which keeps it
    fresh and stored) and two third-party pages fetched politely and cached."""

    NEWS_LIMIT = 15

    def __init__(self, market_data: MarketDataFacade, pages: HttpCompanySources) -> None:
        self._md, self._pages = market_data, pages

    def url(self, source: str, symbol: str) -> str:
        return (
            f"https://www.dse.com.bd/company/{symbol}" if source == "dse" else self._pages.url(source, symbol)
        )

    async def exchange(self, symbol: str, refresh: bool = False) -> ExchangePart:
        sym = Symbol(symbol)
        profile = await self._md.profile(sym)
        news = await self._md.announcements(sym, self.NEWS_LIMIT)
        return exchange_part(profile.model_dump(), [n.model_dump() for n in news])

    async def amarstock(self, symbol: str, refresh: bool = False) -> AmarStockPart:
        return await self._pages.amarstock(symbol, refresh)

    async def topstock(self, symbol: str, refresh: bool = False) -> TopStockPart:
        return await self._pages.topstock(symbol, refresh)
