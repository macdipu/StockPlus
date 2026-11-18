"""Ports the company application needs. Implemented in infrastructure; faked in tests."""

from typing import Any, Protocol

from dse.features.company.domain.entities import AmarStockPart, StockNowPart, TopStockPart


class CompanySources(Protocol):
    """One method per public source. Each raises on failure; the use case keeps the others."""

    def url(self, source: str, symbol: str) -> str: ...

    async def stocknow(self, symbol: str, refresh: bool = False) -> StockNowPart: ...

    async def amarstock(self, symbol: str, refresh: bool = False) -> AmarStockPart: ...

    async def topstock(self, symbol: str, refresh: bool = False) -> TopStockPart: ...


class PriceLookup(Protocol):
    async def last_price(self, symbol: str) -> float | None:
        """Live price, or None when the feed does not know the symbol yet."""
        ...


class BarSource(Protocol):
    async def bars(self, symbol: str, resolution: str, pages: int) -> list[dict[str, Any]]:
        """Oldest first: {"time": unix seconds UTC, "open", "high", "low", "close", "volume"}."""
        ...


class AnalysisLookup(Protocol):
    async def analysis(self, symbol: str) -> dict[str, Any]:
        """The instrument's analysis as JSON (the /analysis shape)."""
        ...
