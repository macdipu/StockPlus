"""HTTP adapter for market data. Thin: validate input, call one use case, wrap the result."""

import csv
import io
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, Query, Response

from dse.core.auth import AdminOnly
from dse.core.http import envelope
from dse.features.market_data.presentation.dependencies import MarketDataContainer, container
from dse.shared_kernel.symbol import Symbol

MAX_CSV_BARS = 5000
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


# ---------------------------------------------------------------------------------------- admin
admin_router = APIRouter(prefix="/admin", tags=["admin"])


@admin_router.post("/stocks/{symbol}/sync", summary="Re-sync one instrument from DSE now (admin only)")
async def admin_sync(symbol: SymbolPath, c: Container, _: AdminOnly) -> dict[str, Any]:
    report = await c.sync(Symbol(symbol))
    return envelope(report.model_dump(mode="json"))


# ---------------------------------------------------------------------------------------- bulk data
data_router = APIRouter(prefix="/data", tags=["data"])


@data_router.get("/{symbol}.csv", summary="Download daily OHLCV as CSV (oldest first)")
async def download_csv(symbol: SymbolPath, c: Container) -> Response:
    sym = Symbol(symbol)
    bars = await c.get_candles(sym, MAX_CSV_BARS)
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(["date", "open", "high", "low", "close", "volume", "trades"])
    for b in bars:
        writer.writerow([b.day.isoformat(), b.open, b.high, b.low, b.close, b.volume, b.trades or 0])
    return Response(
        out.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{sym}.csv"'},
    )
