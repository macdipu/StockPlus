"""Application-boundary DTOs. Shapes follow the legacy `/analysis` contract (snake_case already)."""

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel


class TradePlanDto(BaseModel):
    entry: float
    entry_zone: list[float]
    stop: float
    stop_basis: str
    target: float
    target_basis: str
    atr: float
    risk_pct: float
    reward_pct: float
    rr: float | None = None
    rr_ok: bool


class SetupDto(BaseModel):
    score: int
    max: int
    checks: list[dict[str, Any]]
    plan: TradePlanDto
    flags: list[str]


class SignalDto(BaseModel):
    action: str  # STRONG BUY | BUY | HOLD | SELL | STRONG SELL | AVOID
    net_votes: int
    bullish_reasons: list[str]
    bearish_reasons: list[str]
    rule: str


class ProbabilityStatsDto(BaseModel):
    n: int
    wins: int
    losses: int
    unresolved: int
    p_target_first: float | None = None
    avg_fwd_return_pct: float | None = None
    pct_positive_fwd: float | None = None
    expectancy_pct: float | None = None


class ProbabilityDto(BaseModel):
    horizon_sessions: int
    target_pct: float
    stop_pct: float
    similar_setups: ProbabilityStatsDto
    all_days_baseline: ProbabilityStatsDto
    reliable: bool
    warning: str | None = None
    method: str


class AnalysisDto(BaseModel):
    symbol: str
    name: str | None = None
    as_of: str | None = None
    price: dict[str, Any]
    signal: SignalDto
    setup: SetupDto
    probability: ProbabilityDto
    indicators: dict[str, float | None]
    candles: dict[str, Any]
    levels: dict[str, Any]
    trend: dict[str, Any]
    valuation: dict[str, Any]
    fundamentals: dict[str, Any]
    news: list[dict[str, Any]]
    summary: list[str]
    candle_story: dict[str, Any] | None = None
    disclaimer: str


class TechnicalBarDto(BaseModel):
    """A daily bar with the overlays a chart draws."""

    date: str
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    volume: float | None = None
    sma20: float | None = None
    sma50: float | None = None
    sma200: float | None = None
    ema9: float | None = None
    ema21: float | None = None
    bb_upper: float | None = None
    bb_lower: float | None = None
    vol_avg20: float | None = None


class VpaRowDto(BaseModel):
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    vpa: str | None
    vpa_bias: str | None
    spread_rel: float | None
    vol_rel: float | None
    close_pos: float | None


class VpaDto(BaseModel):
    rows: list[VpaRowDto]
    legend: dict[str, dict[str, str]]
    thresholds: dict[str, float]


class ScreenerRowDto(BaseModel):
    rank: int
    symbol: str
    ltp: float | None = None
    action: str
    score: int
    rr: float | None = None
    p_target_first: float | None = None
    error: str | None = None


class ReturnDto(BaseModel):
    symbol: str
    buy_date: str
    buy_price: float
    sell_date: str
    sell_price: float
    quantity: float
    fee_pct: float
    cost: float
    proceeds: float
    profit: float
    return_pct: float
    days: int
    annualised_pct: float | None
    note: str


class CorrelationDto(BaseModel):
    symbols: list[str]
    days: int
    matrix: list[list[float | None]]


class IntradayBarDto(BaseModel):
    time: str  # HH:MM, exchange time
    open: float
    high: float
    low: float
    close: float
    volume: float
    vpa: str | None = None


class ChartPointDto(BaseModel):
    day: date
    price: float
    label: str = ""


class ChartLineDto(BaseModel):
    role: str  # neckline, upper, lower
    a: ChartPointDto
    b: ChartPointDto


class ChartPatternDto(BaseModel):
    kind: str
    name: str
    direction: Literal["bullish", "bearish", "neutral"]
    status: Literal["forming", "confirmed"]
    confidence: int
    start: date
    end: date
    points: list[ChartPointDto]
    lines: list[ChartLineDto]
    summary: str


class ChangeDto(BaseModel):
    kind: str
    text: str
    tone: Literal["good", "bad", "info"]


class ChangesDto(BaseModel):
    symbol: str
    bar_date: date | None
    previous_bar_date: date | None
    changes: list[ChangeDto]
    enough_history: bool = True
