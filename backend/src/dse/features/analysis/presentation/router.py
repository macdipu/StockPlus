"""HTTP adapter for single-instrument analysis. Thin: validate, call one use case, wrap the result."""

from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, Query
from fastapi.responses import PlainTextResponse

from dse.core.http import envelope
from dse.features.analysis.presentation.dependencies import AnalysisContainer, container
from dse.shared_kernel.errors import ValidationFailedError
from dse.shared_kernel.symbol import Symbol

router = APIRouter(tags=["analysis"])
Container = Annotated[AnalysisContainer, Depends(container)]
SymbolPath = Annotated[str, Path(description="DSE trading code", examples=["ORIONINFU"], max_length=24)]
SCREENER_MAX_SYMBOLS = 15


@router.get(
    "/stocks/{symbol}/analysis",
    summary="Full analysis — the single call an AI agent needs",
    description=(
        "Price, fundamentals, every indicator, candle patterns, support/resistance, trend, valuation (with "
        "inputs), setup score, trade plan, signal with reasons, and the historical short-term profit "
        "probability. Uses the live quote when the feed has one."
    ),
)
async def get_analysis(symbol: SymbolPath, c: Container) -> dict[str, Any]:
    a = await c.analyze(Symbol(symbol).value)
    return envelope(a.model_dump(mode="json"), asOf=a.as_of)


@router.get("/stocks/{symbol}/brief", summary="Markdown brief sized for an LLM context window")
async def get_brief(symbol: SymbolPath, c: Container) -> PlainTextResponse:
    return PlainTextResponse(await c.brief(Symbol(symbol).value), media_type="text/markdown; charset=utf-8")


@router.get("/stocks/{symbol}/technicals", summary="Daily bars with moving averages and Bollinger bands")
async def get_technicals(
    symbol: SymbolPath, c: Container, limit: Annotated[int, Query(ge=1, le=1000)] = 260
) -> dict[str, Any]:
    rows = await c.technicals(Symbol(symbol).value, limit)
    return envelope([r.model_dump(mode="json") for r in rows], count=len(rows))


@router.get("/stocks/{symbol}/vpa", summary="Daily volume-price analysis labels")
async def get_vpa(
    symbol: SymbolPath, c: Container, days: Annotated[int, Query(ge=5, le=400)] = 60
) -> dict[str, Any]:
    v = await c.vpa(Symbol(symbol).value, days)
    return envelope(
        [r.model_dump(mode="json") for r in v.rows],
        legend=v.legend,
        thresholds=v.thresholds,
        count=len(v.rows),
    )


@router.get("/screener", summary="Rank symbols by setup score, then risk/reward")
async def screener(
    c: Container, symbols: Annotated[str, Query(description="Comma-separated codes", examples=["GP,BATBC"])]
) -> dict[str, Any]:
    codes = list(dict.fromkeys(Symbol(s).value for s in symbols.split(",") if s.strip()))
    if not codes:
        raise ValidationFailedError("Give at least one symbol.")
    if len(codes) > SCREENER_MAX_SYMBOLS:
        raise ValidationFailedError(f"At most {SCREENER_MAX_SYMBOLS} symbols (got {len(codes)}).")
    rows = await c.rank(codes)
    return envelope([r.model_dump(mode="json") for r in rows], count=len(rows))


@router.get("/stocks/{symbol}/intraday", summary="1-minute bars recorded from the live feed, with VPA labels")
async def get_intraday(
    symbol: SymbolPath, c: Container, day: Annotated[date | None, Query(description="default: today")] = None
) -> dict[str, Any]:
    rows = await c.intraday(Symbol(symbol).value, day)
    note = (
        None if rows else "No ticks recorded for this day yet; the worker records them while the market runs."
    )
    return envelope([r.model_dump(mode="json") for r in rows], count=len(rows), note=note)


@router.get("/tools/return", tags=["tools"], summary="Price return between two dates, after round-trip fees")
async def tool_return(
    symbol: Annotated[str, Query(max_length=24)],
    buy_date: date,
    c: Container,
    sell_date: date | None = None,
    quantity: Annotated[float, Query(gt=0, le=1e9)] = 100,
    fee_pct: Annotated[float, Query(ge=0, le=5)] = 0.4,
) -> dict[str, Any]:
    out = await c.calculate_return(Symbol(symbol).value, buy_date, sell_date, quantity, fee_pct)
    return envelope(out.model_dump(mode="json"))


@router.get("/tools/correlation", tags=["tools"], summary="Correlation of daily returns")
async def tool_correlation(
    symbols: Annotated[str, Query(description="Comma-separated codes, 2 to 20", examples=["GP,BATBC,ROBI"])],
    c: Container,
    days: Annotated[int, Query(ge=20, le=400)] = 120,
) -> dict[str, Any]:
    codes = [Symbol(s).value for s in symbols.split(",") if s.strip()]
    out = await c.correlation(codes, days)
    return envelope(out.model_dump(mode="json"))
