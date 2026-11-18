"""Company dossier: everything a share-details page shows about a listed company, beyond price and the DSE
page's own fundamentals. Pure Python: no framework, no I/O.

Assembled from three public sources, each optional (a dossier is still useful when one is down):
  dse         the exchange's own company page: contacts, capital and loans, yearly EPS/NAV/profit, dividends,
              shareholding snapshots, this year's quarterly EPS, announcements
  amarstock   full financial statements (profit & loss, balance sheet, cash flow); director buy/sell
  topstock    yearly financial summary (revenue, profit, equity, debt, cash flow); credit rating

Money from the exchange (capital, reserve, loans) is in BDT million. Money in `FinancialYear` is in BDT.
Statement values keep the source's units (BDT); per-share rows stay per share.
"""

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True, slots=True)
class Contact:
    address: str | None = None  # head office
    registered_office: str | None = None
    factory_address: str | None = None
    secretary: str | None = None
    phone: str | None = None
    fax: str | None = None
    email: str | None = None
    website: str | None = None


@dataclass(frozen=True, slots=True)
class CreditRating:
    agency: str | None
    long_term: str | None
    short_term: str | None
    outlook: str | None
    rated_on: str | None


@dataclass(frozen=True, slots=True)
class Capital:
    """BDT million, except `total_shares`."""

    authorized_mn: float | None = None
    paid_up_mn: float | None = None
    reserve_mn: float | None = None
    long_term_loan_mn: float | None = None
    short_term_loan_mn: float | None = None
    total_shares: int | None = None
    loans_as_of: str | None = None

    @property
    def total_loan_mn(self) -> float | None:
        if self.long_term_loan_mn is None and self.short_term_loan_mn is None:
            return None
        return (self.long_term_loan_mn or 0.0) + (self.short_term_loan_mn or 0.0)


@dataclass(frozen=True, slots=True)
class PeriodValue:
    """One reported figure. `period_end` is the ISO date the figure belongs to."""

    period_end: str
    value: float


@dataclass(frozen=True, slots=True)
class QuarterlyEps:
    period_end: str
    period: str  # q1 | q2 | q3 | h1 | 9m  (q2/q3 are the standalone quarter, h1/9m cumulative)
    eps: float


@dataclass(frozen=True, slots=True)
class DividendRecord:
    period_end: str
    cash_pct: float
    stock_pct: float

    @property
    def year(self) -> int:
        return int(self.period_end[:4])


@dataclass(frozen=True, slots=True)
class Shareholding:
    as_of: str
    director: float | None
    government: float | None
    institute: float | None
    foreign: float | None
    public: float | None


@dataclass(frozen=True, slots=True)
class FinancialYear:
    """Yearly summary in BDT (not million)."""

    year: int
    revenue: float | None = None
    gross_profit: float | None = None
    net_profit: float | None = None
    operating_cf: float | None = None
    investing_cf: float | None = None
    total_assets: float | None = None
    total_equity: float | None = None
    total_debt: float | None = None
    cash: float | None = None
    interest_expense: float | None = None
    eps: float | None = None
    nav_per_share: float | None = None
    nocfps: float | None = None
    dividend_cash_pct: float | None = None


@dataclass(frozen=True, slots=True)
class StatementRow:
    label: str
    values: tuple[float | None, ...]
    total: bool = False


@dataclass(frozen=True, slots=True)
class Statement:
    kind: str  # income | balance_sheet | cash_flow
    years: tuple[str, ...]
    rows: tuple[StatementRow, ...]


@dataclass(frozen=True, slots=True)
class DirectorTrade:
    day: date | None
    holder: str
    side: str  # Buy | Sell | Transfer | …
    quantity: int | None
    price: float | None


@dataclass(frozen=True, slots=True)
class NewsItem:
    day: date | None
    title: str
    body: str


@dataclass(frozen=True, slots=True)
class Events:
    record_date: str | None = None
    last_agm: str | None = None
    declaration_date: str | None = None
    declared_dividend_pct: float | None = None
    declared_dividend_type: str | None = None


@dataclass(frozen=True, slots=True)
class SourceStatus:
    name: str
    ok: bool
    url: str
    error: str | None = None


@dataclass(frozen=True, slots=True)
class ExchangePart:
    contact: Contact = field(default_factory=Contact)
    listing_year: int | None = None
    year_end: str | None = None
    operational_status: str | None = None
    capital: Capital = field(default_factory=Capital)
    eps_annual: tuple[PeriodValue, ...] = ()
    eps_quarterly: tuple[QuarterlyEps, ...] = ()
    nav: tuple[PeriodValue, ...] = ()
    nocfps: tuple[PeriodValue, ...] = ()
    dividends: tuple[DividendRecord, ...] = ()
    shareholding: tuple[Shareholding, ...] = ()
    events: Events = field(default_factory=Events)
    news: tuple[NewsItem, ...] = ()


@dataclass(frozen=True, slots=True)
class AmarStockPart:
    statements: tuple[Statement, ...] = ()
    director_trades: tuple[DirectorTrade, ...] = ()


@dataclass(frozen=True, slots=True)
class TopStockPart:
    years: tuple[FinancialYear, ...] = ()
    rating: CreditRating | None = None
    events: Events = field(default_factory=Events)


@dataclass(frozen=True, slots=True)
class CompanyDossier:
    symbol: str
    fetched_at: str
    exchange: ExchangePart = field(default_factory=ExchangePart)
    amarstock: AmarStockPart = field(default_factory=AmarStockPart)
    topstock: TopStockPart = field(default_factory=TopStockPart)
    sources: tuple[SourceStatus, ...] = ()

    @property
    def events(self) -> Events:
        """The exchange's dates, filled in with TopStock's declaration where the exchange has none."""
        a, b = self.exchange.events, self.topstock.events
        return Events(
            record_date=a.record_date or b.record_date,
            last_agm=a.last_agm or b.last_agm,
            declaration_date=b.declaration_date,
            declared_dividend_pct=b.declared_dividend_pct,
            declared_dividend_type=b.declared_dividend_type,
        )
