"""Ports the charts application needs. Implemented in infrastructure; faked in tests."""

from typing import Any, Protocol

from dse.features.charts.domain.candles import Candles


class CandleSource(Protocol):
    async def candles(self, symbol: str, resolution: str, pages: int) -> Candles:
        """Oldest first. NotFoundError: unknown symbol. UpstreamUnavailableError: the source is down."""
        ...


class ChartCache(Protocol):
    async def get(self, key: str) -> dict[str, Any] | None: ...

    async def put(self, key: str, value: dict[str, Any], ttl_s: int) -> None: ...
