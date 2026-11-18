"""Pick the candle source for a request. Replacing a provider means replacing one adapter, not this policy."""

from dse.features.charts.application.ports import CandleSource
from dse.features.charts.domain.candles import Candles, is_index


class RoutedCandles:
    """Indices come from the exchange's index endpoints; a company's daily candles from the exchange data we
    store; a company's intraday candles from the prices this app recorded."""

    def __init__(self, daily: CandleSource, index: CandleSource, ticks: CandleSource) -> None:
        self._daily, self._index, self._ticks = daily, index, ticks

    def source_name(self, symbol: str, resolution: str) -> str:
        if is_index(symbol):
            return "dse-index"
        return "dse-daily" if resolution == "D" else "recorded-ticks"

    async def candles(self, symbol: str, resolution: str, pages: int) -> Candles:
        src = {"dse-index": self._index, "dse-daily": self._daily, "recorded-ticks": self._ticks}[
            self.source_name(symbol, resolution)
        ]
        return await src.candles(symbol, resolution, pages)
