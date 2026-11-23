"""HTTP adapter for scans and market analytics. Thin: validate, call one use case, wrap the result."""

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from dse.core.http import Envelope, envelope
from dse.features.scanner.domain.picks import BUCKETS, PickFilter
from dse.features.scanner.domain.rules import ALL_OPS, Rule, ScanError, ScanSpec, Sort, UniverseFilter
from dse.features.scanner.presentation.dependencies import ScannerContainer, container

router = APIRouter(tags=["scanner"])
Container = Annotated[ScannerContainer, Depends(container)]
Op = Literal[*ALL_OPS]  # type: ignore[valid-type]


def csv(raw: str | None) -> tuple[str, ...]:
    return tuple(x.strip() for x in raw.split(",") if x.strip()) if raw else ()


class RuleBody(BaseModel):
    field: str
    op: Op
    value: Any = None
    field2: str | None = None


class UniverseFilterBody(BaseModel):
    sectors: list[str] = []
    categories: list[str] = []
    asset_types: list[str] = Field([], examples=[["EQ"]])
    min_value_mn: float | None = Field(None, description="Minimum turnover today, BDT mn (liquidity filter)")
    exclude_sectors: list[str] = Field(
        [], examples=[["Bank", "Insurance"]], description="Sectors to leave out"
    )


class SortBody(BaseModel):
    field: str = "value_mn"
    desc: bool = True


class ScanBody(BaseModel):
    rules: list[RuleBody] = Field(min_length=1, max_length=20)
    match: Literal["all", "any"] = "all"
    universe: UniverseFilterBody = UniverseFilterBody()
    sort: SortBody | None = None
    limit: int = Field(100, ge=1, le=500)
    columns: list[str] | None = None
    live: bool = Field(True, description="false = evaluate the last completed session (pre-market scan)")
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "rules": [
                        {"field": "rsi14", "op": "between", "value": [50, 70]},
                        {"field": "close", "op": ">", "field2": "ema21"},
                        {"field": "vol_ratio", "op": ">=", "value": 1.5},
                    ],
                    "match": "all",
                    "universe": {"asset_types": ["EQ"], "categories": ["A", "B"]},
                    "sort": {"field": "vol_ratio", "desc": True},
                    "limit": 50,
                }
            ]
        }
    }


@router.get("/scanner/presets", summary="All preset scanners")
async def list_presets(c: Container) -> dict[str, Any]:
    presets = c.list_presets()
    return envelope([p.model_dump(mode="json") for p in presets], count=len(presets))


@router.get("/scanner/fields", summary="Fields and operators a custom scan can use")
async def list_fields(c: Container) -> dict[str, Any]:
    return envelope(c.list_fields().model_dump(mode="json"))


@router.get("/scanner/universe", summary="Universe build status (version, rows, build time, errors)")
async def universe_status(c: Container) -> dict[str, Any]:
    return envelope((await c.status()).model_dump(mode="json"))


@router.post(
    "/scanner/rescan",
    status_code=202,
    summary="Ask the worker to rebuild the universe now (history reloaded); throttled to one per 10 s",
)
async def rescan(c: Container) -> dict[str, Any]:
    return envelope((await c.rescan()).model_dump(mode="json"))


@router.get("/scanner/presets/{key}", summary="Run a preset scanner")
async def run_preset(
    key: str,
    c: Container,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    sectors: str | None = None,
    categories: str | None = None,
    asset_types: Annotated[str | None, Query(description="Comma-separated; default EQ")] = "EQ",
    min_value_mn: float | None = None,
    live: Annotated[bool | None, Query(description="default: false for pre-market presets")] = None,
    columns: str | None = None,
    exclude_sectors: Annotated[str | None, Query(description="Comma-separated sectors to leave out")] = None,
) -> dict[str, Any]:
    flt = UniverseFilter(csv(sectors), csv(categories), csv(asset_types), min_value_mn, csv(exclude_sectors))
    result, preset = await c.run_preset(key, flt, limit, csv(columns) or None, live)
    return envelope(
        result.rows,
        matched=result.matched,
        scanned=result.scanned,
        live=result.live,
        universe_version=result.universe_version,
        trade_time=result.trade_time,
        preset={"key": preset.key, "name": preset.name, "description": preset.description},
    )


@router.post("/scanner/run", summary="Run a custom scan (rule builder)")
async def run_custom(body: ScanBody, c: Container) -> dict[str, Any]:
    u = body.universe
    spec = ScanSpec(
        rules=tuple(Rule(r.field, r.op, r.value, r.field2) for r in body.rules),
        match=body.match,
        universe=UniverseFilter(
            tuple(u.sectors),
            tuple(u.categories),
            tuple(u.asset_types),
            u.min_value_mn,
            tuple(u.exclude_sectors),
        ),
        sort=Sort(body.sort.field, body.sort.desc) if body.sort else None,
        limit=body.limit,
    )
    result = await c.run_scan(spec, body.columns, body.live)
    return envelope(
        result.rows,
        matched=result.matched,
        scanned=result.scanned,
        live=result.live,
        universe_version=result.universe_version,
        trade_time=result.trade_time,
    )


# ------------------------------------------------------------------------------ market analytics
@router.get(
    "/market/sectors", tags=["market"], summary="Sector performance, breadth, turnover share, median P/E"
)
async def market_sectors(c: Container) -> dict[str, Any]:
    return envelope(await c.sectors())


@router.get(
    "/market/directory",
    tags=["market"],
    summary="Code, company name, sector and category of every instrument (for search)",
)
async def market_directory(c: Container) -> dict[str, Any]:
    rows = await c.directory()
    return envelope(rows, count=len(rows))


@router.get(
    "/market/pe", tags=["market"], summary="Market, sector and category P/E (median and cap-weighted)"
)
async def market_pe(c: Container) -> dict[str, Any]:
    return envelope(await c.pe())


@router.get("/market/52-week", tags=["market"], summary="Where every equity sits in its 52-week range")
async def market_52w(
    c: Container,
    near: Annotated[Literal["high", "low"], Query()] = "high",
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> dict[str, Any]:
    rows = await c.range_52w(near, limit)
    return envelope(rows, count=len(rows))


TA_COLUMNS = (
    "symbol,sector,ltp,change_pct,rsi14,macd,macd_signal,macd_hist,sma20,sma50,sma200,ema9,ema21,"
    "atr_pct,bb_width_pctile,vol_ratio,setup_score,vpa"
)
MATRIX_COLUMNS = (
    "symbol,name,sector,category,ltp,change_pct,eps_ttm,pe,nav,pb,dividend_yield_pct,sponsor_pct,"
    "free_float_pct,market_cap,graham,graham_gap_pct,ret_1m,ret_3m,ret_1y"
)


@router.get("/market/ta-values", tags=["market"], summary="Technical indicator values for every instrument")
async def ta_values(c: Container, sector: str | None = None, columns: str = TA_COLUMNS) -> dict[str, Any]:
    rows = await c.table(csv(columns), sector)
    return envelope(rows, count=len(rows))


@router.get(
    "/market/data-matrix", tags=["market"], summary="Fundamentals + valuation table for every instrument"
)
async def data_matrix(c: Container, sector: str | None = None) -> dict[str, Any]:
    rows = await c.table(csv(MATRIX_COLUMNS), sector)
    return envelope(rows, count=len(rows))


class PickRow(BaseModel):
    symbol: str
    name: str | None
    sector: str | None
    category: str | None
    ltp: float | None
    change_pct: float | None
    pe: float | None
    pb: float | None
    dividend_yield_pct: float | None
    rsi14: float | None
    setup_score: float | None
    patterns: list[str] | None
    vpa: str | None
    low_52w: float | None
    high_52w: float | None
    value_mn: float | None
    pick_score: float
    value_score: int
    entry_score: int
    bucket: Literal["buy_zone", "wait_pullback", "watch", "avoid"]
    bucket_label: str
    reasons: list[str]
    warnings: list[str]


@router.get(
    "/market/picks/track-record",
    tags=["market"],
    summary="How each Picks bucket did in the latest back-test (research, with its limits)",
)
async def picks_track_record(c: Container) -> dict[str, Any]:
    return envelope(c.track_record())


@router.get(
    "/market/picks",
    tags=["market"],
    response_model=Envelope[list[PickRow]],
    summary="Watch list built from a market-wide analysis: every share scored for value and entry timing",
    description=(
        "Each row gets a value score and an entry score (0–100), a pick score, a bucket (buy_zone, "
        "wait_pullback, watch, avoid) and the reasons. Filter by sector (include or exclude), category, "
        "turnover and bucket. Example: all shares except banks and insurance: "
        "`?exclude_sectors=Bank,Insurance,Life Insurance`."
    ),
)
async def market_picks(
    c: Container,
    sectors: Annotated[str | None, Query(description="Comma-separated sectors to keep (default all)")] = None,
    exclude_sectors: Annotated[str | None, Query(description="Comma-separated sectors to leave out")] = None,
    categories: Annotated[str | None, Query(description="e.g. A,B")] = None,
    asset_types: Annotated[str | None, Query(description="Comma-separated; default EQ")] = "EQ",
    min_value_mn: Annotated[float | None, Query(description="Minimum turnover today, BDT mn")] = None,
    buckets: Annotated[
        str | None, Query(description=f"Comma-separated subset of {', '.join(BUCKETS)}")
    ] = None,
    min_value_score: Annotated[int, Query(ge=0, le=100)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    live: bool = True,
) -> dict[str, Any]:
    wanted = csv(buckets)
    unknown = [b for b in wanted if b not in BUCKETS]
    if unknown:
        raise ScanError(f"Unknown bucket(s): {', '.join(unknown)}. Use {', '.join(BUCKETS)}")
    flt = PickFilter(
        universe=UniverseFilter(
            csv(sectors), csv(categories), csv(asset_types), min_value_mn, csv(exclude_sectors)
        ),
        buckets=wanted,
        min_value_score=min_value_score,
        limit=limit,
    )
    data = await c.picks(flt, live)
    rows = data.pop("rows")
    return envelope(rows, count=len(rows), **data)
