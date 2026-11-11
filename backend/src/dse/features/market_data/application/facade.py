"""The ONLY entry point other features may use (import-linter enforces this)."""

from dse.features.market_data.application.dto import BarDto, ProfileDto
from dse.features.market_data.application.use_cases import GetCandles, GetInstrumentProfile
from dse.shared_kernel.symbol import Symbol


class MarketDataFacade:
    def __init__(self, candles: GetCandles, profile: GetInstrumentProfile) -> None:
        self._candles, self._profile = candles, profile

    async def daily_bars(self, symbol: Symbol, limit: int = 400) -> list[BarDto]:
        return await self._candles(symbol, limit)

    async def profile(self, symbol: Symbol) -> ProfileDto:
        return await self._profile(symbol)
