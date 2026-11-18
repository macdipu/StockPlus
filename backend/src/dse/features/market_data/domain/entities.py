"""Market-data domain model. Pure Python: no framework, no ORM, no I/O."""

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from dse.shared_kernel.errors import ValidationFailedError
from dse.shared_kernel.symbol import Symbol


class BarSource(StrEnum):
    """Where a daily bar came from. PAGE (DSE's official series) always wins over SNAPSHOT (our EOD copy)."""

    PAGE = "page"
    SNAPSHOT = "snapshot"


@dataclass(frozen=True, slots=True)
class DailyBar:
    symbol: Symbol
    day: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    trades: int | None
    source: BarSource

    def __post_init__(self) -> None:
        if self.low > self.high:
            raise ValidationFailedError(f"{self.symbol} {self.day}: low {self.low} > high {self.high}")
        if self.volume < 0:
            raise ValidationFailedError(f"{self.symbol} {self.day}: negative volume")


@dataclass(frozen=True, slots=True)
class ShareholdingPattern:
    as_of: str | None
    sponsor_pct: float | None
    government_pct: float | None
    institution_pct: float | None
    foreign_pct: float | None
    public_pct: float | None


FUNDAMENTALS_SCHEMA = 2  # bump when the company page yields more; stored rows older than this are re-synced


@dataclass(frozen=True, slots=True)
class CompanyInfo:
    """Contacts, capital and status from the exchange's company page. Money is BDT million."""

    head_office: str | None = None
    registered_office: str | None = None
    factory_address: str | None = None
    phone: str | None = None
    fax: str | None = None
    email: str | None = None
    website: str | None = None
    secretary_name: str | None = None
    secretary_email: str | None = None
    secretary_phone: str | None = None
    authorized_capital_mn: float | None = None
    reserve_mn: float | None = None
    short_term_loan_mn: float | None = None
    long_term_loan_mn: float | None = None
    operational_status: str | None = None
    agm_date: str | None = None
    market_lot: int | None = None


@dataclass(frozen=True, slots=True)
class YearFinancial:
    """One financial year as the exchange reports it. `profit_mn` is BDT million; EPS, NAV per share."""

    year: int
    eps: float | None = None
    nav: float | None = None
    profit_mn: float | None = None
    pe: float | None = None
    cash_dividend_pct: float | None = None
    dividend_yield_pct: float | None = None


@dataclass(frozen=True, slots=True)
class Dividend:
    year: int
    cash_pct: float
    stock_pct: float


@dataclass(frozen=True, slots=True)
class EpsReport:
    """Interim EPS row, keyed by DSE's period labels; `period_ends` holds YYYYMM per label."""

    annual: float | None = None
    q1: float | None = None
    q2: float | None = None
    q3: float | None = None
    half_year: float | None = None
    nine_months: float | None = None
    period_ends: dict[str, str] = field(default_factory=dict)
    last_audited_year: float | None = None


@dataclass(frozen=True, slots=True)
class TtmEps:
    value: float | None
    basis: str


# YTD figure -> (period label, annualisation factor, description)
_YTD = (
    ("nine_months", "nine", 4 / 3, "9M EPS x 4/3"),
    ("half_year", "half", 2.0, "H1 EPS x 2"),
    ("q1", "q1", 4.0, "Q1 EPS x 4"),
)


@dataclass(frozen=True, slots=True)
class Fundamentals:
    eps: EpsReport
    nav: float | None
    face_value: float
    paid_up_capital: float | None
    market_cap: float | None
    free_float_pct: float | None
    shareholding: ShareholdingPattern
    dividends: tuple[Dividend, ...]
    pe_dse: float | None
    pe_dse_trailing: float | None
    dividend_yield_pct: float | None
    week_high_52: float | None
    week_low_52: float | None
    year_end: str | None = None
    listing_year: int | None = None
    info: CompanyInfo | None = None
    year_history: tuple[YearFinancial, ...] = ()
    holding_history: tuple[ShareholdingPattern, ...] = ()
    schema: int = 0  # 0 = stored before these fields existed

    def ttm_eps(self) -> TtmEps:
        """Annual EPS if it is the newest report; otherwise the newest year-to-date figure, annualised."""
        e = self.eps
        annual_end = e.period_ends.get("annual") or ""
        newer = [
            (e.period_ends.get(label) or "", getattr(e, attr), mult, desc)
            for attr, label, mult, desc in _YTD
            if getattr(e, attr) is not None and (e.period_ends.get(label) or "") > annual_end
        ]
        if newer:
            end, value, mult, desc = max(newer, key=lambda t: t[0])
            return TtmEps(value * mult, f"annualised {desc} (period {end})")
        if e.annual is not None:
            return TtmEps(e.annual, f"annual EPS (period {annual_end or '?'})")
        return TtmEps(e.last_audited_year, "last audited year EPS")

    @property
    def total_shares(self) -> int | None:
        return (
            int(self.paid_up_capital / self.face_value) if self.paid_up_capital and self.face_value else None
        )

    @property
    def last_dividend(self) -> Dividend | None:
        return max(self.dividends, key=lambda d: d.year) if self.dividends else None

    def dividend_per_share(self) -> float | None:
        """DSE declares cash dividends as a % of face value."""
        d = self.last_dividend
        return d.cash_pct / 100 * self.face_value if d else None

    def pe_at(self, price: float | None) -> float | None:
        eps = self.ttm_eps().value
        return price / eps if price and eps and eps > 0 else None


@dataclass(frozen=True, slots=True)
class Instrument:
    symbol: Symbol
    name: str
    sector: str | None
    category: str | None
    board: str | None
    asset_type: str | None
    isin: str | None


@dataclass(frozen=True, slots=True)
class Announcement:
    id: str
    symbol: Symbol
    published_on: date | None
    kind: str | None
    title: str | None
    body: str


@dataclass(frozen=True, slots=True)
class CompanyPage:
    """Everything one DSE company page yields; the unit a sync persists atomically."""

    instrument: Instrument
    fundamentals: Fundamentals
    bars: tuple[DailyBar, ...]
    announcements: tuple[Announcement, ...]
    last_price: float | None
    fetched_at: datetime


@dataclass(frozen=True, slots=True)
class Quote:
    symbol: Symbol
    ltp: float | None
    ycp: float | None
    open: float | None
    high: float | None
    low: float | None
    close: float | None
    volume: int
    value_mn: float | None
    trades: int | None
    category: str | None
    sector: str | None
    asset_type: str | None


@dataclass(frozen=True, slots=True)
class MarketSnapshot:
    session_date: date | None
    is_open: bool
    trading_day: bool
    trade_time: str | None
    quotes: dict[str, Quote]

    def end_of_day_bars(self) -> list[DailyBar]:
        """Today's bar per traded instrument, valid once the session is closed."""
        if self.session_date is None or not self.trading_day or self.is_open:
            return []
        bars = []
        for q in self.quotes.values():
            last = q.close or q.ltp
            if not last or q.volume <= 0:
                continue
            o, h, lo = (Decimal(str(v or last)) for v in (q.open, q.high, q.low))
            bars.append(
                DailyBar(
                    q.symbol,
                    self.session_date,
                    o,
                    h,
                    lo,
                    Decimal(str(last)),
                    q.volume,
                    q.trades,
                    BarSource.SNAPSHOT,
                )
            )
        return bars
