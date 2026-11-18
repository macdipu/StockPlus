"""HTTP adapter for charts. Thin: validate, call one use case, wrap the result."""

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Header, Path, Query, Response

from dse.core.http import Envelope, envelope
from dse.features.charts.application.dto import CatalogDto, ChartDto
from dse.features.charts.domain.candles import RESOLUTIONS
from dse.features.charts.domain.spec import MAX_INDICATORS
from dse.features.charts.presentation.dependencies import ChartsContainer, container
from dse.shared_kernel.symbol import Symbol

router = APIRouter(prefix="/charts", tags=["charts"])
Container = Annotated[ChartsContainer, Depends(container)]
SymbolPath = Annotated[
    str,
    Path(
        description="A DSE trading code or index (DSEX, DS30, DSES)", examples=["GP", "DSEX"], max_length=24
    ),
]
CACHE_SECONDS = {"1": 15, "5": 30, "30": 60, "60": 60, "D": 60}


@router.get(
    "/indicators",
    response_model=Envelope[CatalogDto],
    summary="Every indicator a chart can draw: parameters, outputs, how it is drawn, a plain description",
)
def list_indicators(c: Container, response: Response) -> dict[str, Any]:
    catalog = c.indicators()
    response.headers["Cache-Control"] = "public, max-age=3600"
    response.headers["ETag"] = f'W/"{catalog.version}"'
    return envelope(catalog.model_dump(), count=len(catalog.indicators))


@router.get(
    "/{symbol}",
    response_model=Envelope[ChartDto],
    responses={304: {"description": "The candles and indicators have not changed since the ETag you sent"}},
    summary="Candles and indicator series for one symbol, aligned by index, computed once and cached",
    description=(
        "`indicators` is a comma-separated list such as `rsi(14),macd(12,26,9),bbands`: positional "
        "parameters in the order the catalog lists them, defaults when omitted. Each series is an array "
        "with one value per candle (`null` while an indicator warms up). "
        f"At most {MAX_INDICATORS} indicators. Times are unix seconds UTC (Dhaka is UTC+6). "
        "Send the `ETag` back as `If-None-Match` to receive `304` when nothing changed."
    ),
)
async def get_chart(
    symbol: SymbolPath,
    c: Container,
    response: Response,
    resolution: Annotated[
        Literal["1", "5", "30", "60", "D"],
        Query(description=", ".join(f"{k} = {v}" for k, v in RESOLUTIONS.items())),
    ] = "D",
    indicators: Annotated[str | None, Query(max_length=400, examples=["rsi(14),macd"])] = None,
    pages: Annotated[
        int, Query(ge=1, le=4, description="Pages of 300 intraday candles (daily is one page)")
    ] = 1,
    if_none_match: Annotated[str | None, Header()] = None,
) -> Any:
    sym = Symbol(symbol).value
    result = await c.chart(sym, resolution, indicators, pages, if_none_match)
    headers = {
        "ETag": result.etag,
        "Cache-Control": f"public, max-age={CACHE_SECONDS[resolution]}, stale-while-revalidate=120",
    }
    if result.chart is None:
        return Response(status_code=304, headers=headers)
    response.headers.update(headers)
    return envelope(
        result.chart.model_dump(),
        count=len(result.chart.candles.time),
        timezone="UTC (Dhaka = UTC+6)",
    )
