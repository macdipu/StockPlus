"""The ONLY entry point other features may use (import-linter enforces this)."""

from dse.features.market_data.application.dto import (
    AnnouncementDto,
    BarDto,
    HistorySignature,
    InstrumentHistoryDto,
    ProfileDto,
)
from dse.features.market_data.application.use_cases import (
    GetAnnouncements,
    GetCandles,
    GetHistorySignature,
    GetInstrumentProfile,
    GetMarketHistory,
)
from dse.shared_kernel.symbol import Symbol


class MarketDataFacade:
    def __init__(
        self,
        candles: GetCandles,
        profile: GetInstrumentProfile,
        announcements: GetAnnouncements,
        history: GetMarketHistory,
        signature: GetHistorySignature,
    ) -> None:
        self._candles, self._profile, self._announcements = candles, profile, announcements
        self._history, self._signature = history, signature

    async def daily_bars(self, symbol: Symbol, limit: int = 400) -> list[BarDto]:
        return await self._candles(symbol, limit)

    async def profile(self, symbol: Symbol) -> ProfileDto:
        return await self._profile(symbol)

    async def announcements(self, symbol: Symbol, limit: int = 20) -> list[AnnouncementDto]:
        return await self._announcements(symbol, limit)

    async def market_history(self, bars: int = 400) -> list[InstrumentHistoryDto]:
        return await self._history(bars)

    async def history_signature(self) -> HistorySignature:
        return await self._signature()
