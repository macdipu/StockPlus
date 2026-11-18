"""Adapters over other features' public facades (ARCHITECTURE §4.3)."""

from typing import Any

from dse.features.analysis.application.facade import AnalysisFacade
from dse.features.live_feed.application.facade import LiveFeedFacade


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
