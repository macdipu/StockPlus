import asyncio
from datetime import date, datetime
from typing import Any

import pytest

from dse.features.company.application.use_cases import GetBars, GetCompanyDossier
from dse.features.company.domain.entities import AmarStockPart, StockNowPart, TopStockPart
from dse.shared_kernel.errors import UpstreamUnavailableError, ValidationFailedError


class FixedClock:
    def now(self) -> datetime:
        return datetime(2026, 11, 18, 11, 0)

    def today(self) -> date:
        return date(2026, 11, 18)


class Sources:
    def __init__(self) -> None:
        self.calls = 0

    def url(self, source: str, symbol: str) -> str:
        return f"https://{source}/{symbol}"

    async def stocknow(self, symbol: str, refresh: bool = False) -> StockNowPart:
        self.calls += 1
        await asyncio.sleep(0.01)
        return StockNowPart(listing_year=2012)

    async def amarstock(self, symbol: str, refresh: bool = False) -> AmarStockPart:
        raise UpstreamUnavailableError("amarstock down")

    async def topstock(self, symbol: str, refresh: bool = False) -> TopStockPart:
        return TopStockPart()


class Prices:
    async def last_price(self, symbol: str) -> float | None:
        return 85.8


async def test_one_source_down_still_returns_a_dossier_and_says_so() -> None:
    uc = GetCompanyDossier(Sources(), Prices(), FixedClock())
    d = await uc("ENVOYTEX")
    assert d["profile"]["listing_year"] == 2012
    status = {s["name"]: s for s in d["sources"]}
    assert status["stocknow"]["ok"]
    assert not status["amarstock"]["ok"]
    assert status["amarstock"]["error"] == "amarstock down"
    assert d["price"] == 85.8
    assert d["statements"] == []


async def test_concurrent_requests_share_one_fetch() -> None:
    src = Sources()
    uc = GetCompanyDossier(src, Prices(), FixedClock())
    await asyncio.gather(*(uc("ENVOYTEX") for _ in range(5)))
    assert src.calls == 1


async def test_bars_reject_unknown_resolution() -> None:
    class Bars:
        async def bars(self, symbol: str, resolution: str, pages: int) -> list[dict[str, Any]]:
            return [{"pages": pages}]

    with pytest.raises(ValidationFailedError):
        await GetBars(Bars())("GP", "15")
    assert await GetBars(Bars())("GP", "5", 99) == [{"pages": 4}]  # capped
