"""HTTP adapter for market data. Thin: validate input, call one use case, wrap the result."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, Query

from dse.core.http import envelope
from dse.features.market_data.presentation.dependencies import MarketDataContainer, container
from dse.shared_kernel.symbol import Symbol

router = APIRouter(prefix="/stocks", tags=["stocks"])
Container = Annotated[MarketDataContainer, Depends(container)]
SymbolPath = Annotated[str, Path(description="DSE trading code", examples=["ORIONINFU"], max_length=24)]


@router.get("/{symbol}", summary="Instrument profile and fundamentals")
async def get_profile(symbol: SymbolPath, c: Container) -> dict[str, Any]:
    profile = await c.get_profile(Symbol(symbol))
    return envelope(profile.model_dump(mode="json"), syncedAt=profile.synced_at)


@router.get("/{symbol}/candles", summary="Daily OHLCV, oldest first")
async def get_candles(
    symbol: SymbolPath, c: Container, limit: Annotated[int, Query(ge=1, le=2000)] = 260
) -> dict[str, Any]:
    bars = await c.get_candles(Symbol(symbol), limit)
    return envelope([b.model_dump(mode="json") for b in bars], count=len(bars))


@router.get("/{symbol}/announcements", summary="Recent DSE announcements")
async def get_announcements(
    symbol: SymbolPath, c: Container, limit: Annotated[int, Query(ge=1, le=100)] = 20
) -> dict[str, Any]:
    items = await c.get_announcements(Symbol(symbol), limit)
    return envelope([a.model_dump(mode="json") for a in items], count=len(items))
