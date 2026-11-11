"""Application-boundary DTOs (what use cases return).

Presentation serialises these; it never sees entities.
"""

from datetime import date, datetime

from pydantic import BaseModel


class BarDto(BaseModel):
    day: date
    open: float
    high: float
    low: float
    close: float
    volume: int
    trades: int | None


class ShareholdingDto(BaseModel):
    as_of: str | None
    sponsor_pct: float | None
    government_pct: float | None
    institution_pct: float | None
    foreign_pct: float | None
    public_pct: float | None


class DividendDto(BaseModel):
    year: int
    cash_pct: float
    stock_pct: float


class FundamentalsDto(BaseModel):
    eps_ttm: float | None
    eps_ttm_basis: str
    eps_annual: float | None
    eps_q1: float | None
    eps_q2: float | None
    eps_q3: float | None
    eps_half_year: float | None
    eps_nine_months: float | None
    eps_period_ends: dict[str, str]
    pe: float | None
    pe_dse_trailing: float | None
    nav: float | None
    pb: float | None
    face_value: float
    total_shares: int | None
    market_cap: float | None
    free_float_pct: float | None
    dividend_per_share: float | None
    dividend_yield_pct: float | None
    last_dividend: DividendDto | None
    dividends: list[DividendDto]
    shareholding: ShareholdingDto
    week_high_52: float | None
    week_low_52: float | None


class ProfileDto(BaseModel):
    symbol: str
    name: str
    sector: str | None
    category: str | None
    board: str | None
    asset_type: str | None
    isin: str | None
    last_close: float | None
    last_bar_day: date | None
    synced_at: datetime | None
    fundamentals: FundamentalsDto


class AnnouncementDto(BaseModel):
    id: str
    published_on: date | None
    kind: str | None
    title: str | None
    body: str


class SyncReport(BaseModel):
    symbol: str
    bars: int
    announcements: int


class BackfillReport(BaseModel):
    requested: int
    skipped_fresh: int
    synced: int
    failed: dict[str, str]


class EndOfDayReport(BaseModel):
    session_date: date | None
    bars_written: int
    skipped_reason: str | None = None
