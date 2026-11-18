"""HTTP adapter for company details and multi-timeframe bars. Thin: validate, call one use case, wrap."""

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Path, Query

from dse.core.http import Envelope, envelope
from dse.features.company.application.use_cases import RESOLUTIONS
from dse.features.company.presentation import schemas
from dse.features.company.presentation.dependencies import CompanyContainer, container
from dse.shared_kernel.symbol import Symbol

router = APIRouter(prefix="/stocks", tags=["company"])
Container = Annotated[CompanyContainer, Depends(container)]
SymbolPath = Annotated[str, Path(description="DSE trading code", examples=["ENVOYTEX"], max_length=24)]


@router.get(
    "/{symbol}/company",
    response_model=Envelope[schemas.Company],
    summary="Company details: profile, capital and loans, EPS/NAV/NOCF history, dividends, shareholding, "
    "financial statements, director trades, credit rating, events, news, ratios and flags",
)
async def get_company(
    symbol: SymbolPath,
    c: Container,
    refresh: Annotated[bool, Query(description="Bypass the 6-hour source cache")] = False,
) -> dict[str, Any]:
    data = await c.dossier(Symbol(symbol).value, refresh)
    return envelope(data, fetchedAt=data["fetched_at"])


@router.get(
    "/{symbol}/bars",
    response_model=Envelope[list[schemas.Bar]],
    summary="OHLCV candles at 1/5/30/60-minute or daily resolution, oldest first",
)
async def get_bars(
    symbol: SymbolPath,
    c: Container,
    resolution: Annotated[
        Literal["1", "5", "30", "60", "D"],
        Query(description=", ".join(f"{k} = {v}" for k, v in RESOLUTIONS.items())),
    ] = "D",
    pages: Annotated[int, Query(ge=1, le=4, description="300 bars per page")] = 1,
) -> dict[str, Any]:
    bars = await c.bars(Symbol(symbol).value, resolution, pages)
    return envelope(bars, count=len(bars), resolution=resolution, timezone="UTC (Dhaka = UTC+6)")


alerts_router = APIRouter(tags=["company"])


@alerts_router.get(
    "/alerts",
    response_model=Envelope[list[schemas.Alert]],
    summary="Alerts for watched symbols: buy zone with a bullish candle, stop broken, target hit, breakout, "
    "bearish candle (each with a stable key so a client notifies once)",
)
async def get_alerts(
    c: Container,
    symbols: Annotated[
        str, Query(description="Comma-separated trading codes (max 30)", examples=["PADMAOIL,GP"])
    ],
) -> dict[str, Any]:
    wanted = [Symbol(s).value for s in symbols.split(",") if s.strip()]
    items = await c.alerts(wanted)
    return envelope(items, count=len(items))
