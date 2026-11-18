"""Application-boundary DTOs. The presentation layer serialises these; it never sees domain objects."""

from pydantic import BaseModel


class ParamDto(BaseModel):
    key: str
    label: str
    default: float
    min: float
    max: float
    integer: bool


class OutputDto(BaseModel):
    key: str
    label: str
    kind: str  # line | histogram | area | dots


class CatalogEntryDto(BaseModel):
    id: str
    name: str
    group: str
    placement: str  # overlay | pane
    description: str
    params: list[ParamDto]
    outputs: list[OutputDto]
    scale: tuple[float, float] | None
    levels: list[float]
    repaints: bool
    requires: list[str]  # price columns beyond the close it reads: open, high, low, volume


class CatalogDto(BaseModel):
    version: str  # changes whenever the catalog does; clients cache the catalog under it
    groups: list[str]
    indicators: list[CatalogEntryDto]


class CandlesDto(BaseModel):
    """Columnar: index i of every array is one candle. Times are unix seconds UTC."""

    time: list[int]
    open: list[float]
    high: list[float]
    low: list[float]
    close: list[float]
    volume: list[float]


class IndicatorDto(BaseModel):
    key: str  # "rsi(14)": unique in the response and what the client asked for
    id: str
    name: str
    group: str
    placement: str
    params: dict[str, float]
    outputs: list[OutputDto]
    scale: tuple[float, float] | None
    levels: list[float]
    repaints: bool
    series: dict[str, list[float | None]]  # output key -> one value per candle, null while warming up


class ChartDto(BaseModel):
    symbol: str
    resolution: str
    source: str  # dse-daily | dse-index | recorded-ticks
    ohlc: (
        bool  # false: closing values only (an index); indicators that need open/high/low/volume are left out
    )
    candles: CandlesDto
    indicators: list[IndicatorDto]
    warnings: list[str]
    catalog_version: str
