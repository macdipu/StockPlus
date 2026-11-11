"""HTTP adapter for scans and market analytics. Thin: validate, call one use case, wrap the result."""

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from dse.core.http import envelope
from dse.features.scanner.domain.rules import ALL_OPS, Rule, ScanSpec, Sort, UniverseFilter
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


class SortBody(BaseModel):
    field: str = "value_mn"
    desc: bool = True


class ScanBody(BaseModel):
    rules: list[RuleBody] = Field(..., min_length=1, max_length=20)
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
) -> dict[str, Any]:
    flt = UniverseFilter(csv(sectors), csv(categories), csv(asset_types), min_value_mn)
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
        universe=UniverseFilter(tuple(u.sectors), tuple(u.categories), tuple(u.asset_types), u.min_value_mn),
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
