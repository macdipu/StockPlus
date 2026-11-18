"""Ports the company application needs. Implemented in infrastructure; faked in tests."""

from typing import Any, Protocol

from dse.features.company.domain.entities import AmarStockPart, ExchangePart, TopStockPart


class CompanySources(Protocol):
    """One method per public source. Each raises on failure; the use case keeps the others."""

    def url(self, source: str, symbol: str) -> str: ...

    async def exchange(self, symbol: str, refresh: bool = False) -> ExchangePart: ...

    async def amarstock(self, symbol: str, refresh: bool = False) -> AmarStockPart: ...

    async def topstock(self, symbol: str, refresh: bool = False) -> TopStockPart: ...


class PriceLookup(Protocol):
    async def last_price(self, symbol: str) -> float | None:
        """Live price, or None when the feed does not know the symbol yet."""
        ...


class AnalysisLookup(Protocol):
    async def analysis(self, symbol: str) -> dict[str, Any]:
        """The instrument's analysis as JSON (the /analysis shape)."""
        ...
