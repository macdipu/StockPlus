"""Public response shapes for the company endpoints (documented in OpenAPI, validated on the way out)."""

from typing import Literal

from pydantic import BaseModel


class Contact(BaseModel):
    address: str | None
    phone: str | None
    fax: str | None
    email: str | None
    website: str | None


class CreditRating(BaseModel):
    agency: str | None
    long_term: str | None
    short_term: str | None
    outlook: str | None
    rated_on: str | None


class Profile(BaseModel):
    contact: Contact
    listing_year: int | None
    year_end: str | None
    operational_status: str | None
    credit_rating: CreditRating | None


class Capital(BaseModel):
    """BDT million, except total_shares."""

    authorized_mn: float | None
    paid_up_mn: float | None
    reserve_mn: float | None
    long_term_loan_mn: float | None
    short_term_loan_mn: float | None
    total_loan_mn: float | None
    total_shares: int | None
    loans_as_of: str | None


class PerShareYear(BaseModel):
    period_end: str
    eps: float | None = None
    nav: float | None = None
    nocfps: float | None = None
    cash_dividend_pct: float | None = None
    stock_dividend_pct: float | None = None


class PeriodValue(BaseModel):
    period_end: str
    value: float


class QuarterlyEps(BaseModel):
    period_end: str
    period: str
    label: str
    eps: float


class Dividend(BaseModel):
    period_end: str
    year: int
    cash_pct: float
    stock_pct: float
    cash_per_share: float


class Shareholding(BaseModel):
    as_of: str
    director: float | None
    government: float | None
    institute: float | None
    foreign: float | None
    public: float | None


class FinancialYear(BaseModel):
    """BDT; eps, nav_per_share and nocfps are Tk per share."""

    year: int
    revenue: float | None
    gross_profit: float | None
    net_profit: float | None
    operating_cf: float | None
    investing_cf: float | None
    total_assets: float | None
    total_equity: float | None
    total_debt: float | None
    cash: float | None
    interest_expense: float | None
    eps: float | None
    nav_per_share: float | None
    nocfps: float | None
    dividend_cash_pct: float | None


class StatementRow(BaseModel):
    label: str
    values: list[float | None]
    total: bool


class Statement(BaseModel):
    kind: Literal["income", "balance_sheet", "cash_flow"]
    years: list[str]
    rows: list[StatementRow]


class DirectorTrade(BaseModel):
    day: str | None
    holder: str
    side: str
    quantity: int | None
    price: float | None


class Events(BaseModel):
    record_date: str | None
    last_agm: str | None
    declaration_date: str | None
    declared_dividend_pct: float | None
    declared_dividend_type: str | None


class News(BaseModel):
    day: str | None
    title: str
    body: str


class Source(BaseModel):
    name: str
    ok: bool
    url: str
    error: str | None


class Ratio(BaseModel):
    key: str
    label: str
    value: float | None
    unit: str
    basis: str


class Flag(BaseModel):
    tone: Literal["good", "warn", "bad"]
    text: str


class Company(BaseModel):
    symbol: str
    fetched_at: str
    price: float | None
    profile: Profile
    capital: Capital
    per_share_history: list[PerShareYear]
    nav_history: list[PeriodValue]
    quarterly_eps: list[QuarterlyEps]
    dividends: list[Dividend]
    shareholding: list[Shareholding]
    financial_years: list[FinancialYear]
    statements: list[Statement]
    director_trades: list[DirectorTrade]
    events: Events
    news: list[News]
    sources: list[Source]
    units: dict[str, str]
    ratios: list[Ratio]
    flags: list[Flag]


class Bar(BaseModel):
    time: int
    open: float
    high: float
    low: float
    close: float
    volume: int


class Alert(BaseModel):
    symbol: str
    kind: Literal["buy_zone", "stop", "target", "breakout", "bearish_candle"]
    severity: Literal["info", "action", "warning"]
    key: str
    price: float
    message: str
