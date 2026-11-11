"""HTTP adapter for single-instrument analysis. Thin: validate, call one use case, wrap the result."""

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
