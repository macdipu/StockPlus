"""Application-boundary DTOs (what use cases return).

Presentation serialises these; it never sees entities.
"""

from dataclasses import dataclass
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


class CompanyInfoDto(BaseModel):
    """Contacts, capital and status. Money is BDT million."""

    head_office: str | None
    registered_office: str | None
    factory_address: str | None
    phone: str | None
    fax: str | None
    email: str | None
    website: str | None
    secretary_name: str | None
    secretary_email: str | None
    secretary_phone: str | None
    authorized_capital_mn: float | None
    reserve_mn: float | None
    short_term_loan_mn: float | None
    long_term_loan_mn: float | None
    operational_status: str | None
    agm_date: str | None
    market_lot: int | None


class YearFinancialDto(BaseModel):
    year: int
    eps: float | None
    nav: float | None
    profit_mn: float | None
    pe: float | None
    cash_dividend_pct: float | None
    dividend_yield_pct: float | None


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
    paid_up_capital: float | None  # BDT
    year_end: str | None  # month name, e.g. "June"
    listing_year: int | None
    info: CompanyInfoDto | None
    year_history: list[YearFinancialDto]  # oldest first
    holding_history: list[ShareholdingDto]  # oldest first


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
    asset_types_updated: int = 0


# Bulk (whole-market) shapes are plain dataclasses: ~100k bars are built per universe refresh and pydantic
# validation of each would dominate the cost.
@dataclass(frozen=True, slots=True)
class HistoryBarDto:
    day: date
    open: float
    high: float
    low: float
    close: float
    volume: int
    trades: int | None


@dataclass(frozen=True, slots=True)
class InstrumentHistoryDto:
    symbol: str
    name: str
    sector: str | None
    category: str | None
    board: str | None
    asset_type: str | None
    bars: tuple[HistoryBarDto, ...]
    fundamentals: FundamentalsDto | None


@dataclass(frozen=True, slots=True)
class HistorySignature:
    """Changes iff stored history or fundamentals changed (lets a caller cache the bulk load)."""

    bars: int
    last_bar_day: date | None
    fundamentals: int
