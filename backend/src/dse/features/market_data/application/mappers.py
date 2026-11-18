"""Entity -> DTO mapping (one direction: the application never accepts DTOs back as entities)."""

import dataclasses

from dse.features.market_data.application.dto import (
    AnnouncementDto,
    BarDto,
    CompanyInfoDto,
    DividendDto,
    FundamentalsDto,
    ShareholdingDto,
    YearFinancialDto,
)
from dse.features.market_data.domain.entities import (
    Announcement,
    DailyBar,
    Dividend,
    Fundamentals,
    ShareholdingPattern,
)


def bar_dto(b: DailyBar) -> BarDto:
    return BarDto(
        day=b.day,
        open=float(b.open),
        high=float(b.high),
        low=float(b.low),
        close=float(b.close),
        volume=b.volume,
        trades=b.trades,
    )


def _div(d: Dividend) -> DividendDto:
    return DividendDto(year=d.year, cash_pct=d.cash_pct, stock_pct=d.stock_pct)


def _holding(s: ShareholdingPattern) -> ShareholdingDto:
    return ShareholdingDto(
        as_of=s.as_of,
        sponsor_pct=s.sponsor_pct,
        government_pct=s.government_pct,
        institution_pct=s.institution_pct,
        foreign_pct=s.foreign_pct,
        public_pct=s.public_pct,
    )


def fundamentals_dto(f: Fundamentals, price: float | None) -> FundamentalsDto:
    ttm = f.ttm_eps()
    s = f.shareholding
    last = f.last_dividend
    return FundamentalsDto(
        eps_ttm=ttm.value,
        eps_ttm_basis=ttm.basis,
        eps_annual=f.eps.annual,
        eps_q1=f.eps.q1,
        eps_q2=f.eps.q2,
        eps_q3=f.eps.q3,
        eps_half_year=f.eps.half_year,
        eps_nine_months=f.eps.nine_months,
        eps_period_ends=f.eps.period_ends,
        pe=f.pe_at(price),
        pe_dse_trailing=f.pe_dse_trailing,
        nav=f.nav,
        pb=price / f.nav if price and f.nav and f.nav > 0 else None,
        face_value=f.face_value,
        total_shares=f.total_shares,
        market_cap=f.market_cap,
        free_float_pct=f.free_float_pct,
        dividend_per_share=f.dividend_per_share(),
        dividend_yield_pct=f.dividend_yield_pct,
        last_dividend=_div(last) if last else None,
        dividends=[_div(d) for d in sorted(f.dividends, key=lambda d: d.year, reverse=True)],
        shareholding=ShareholdingDto(
            as_of=s.as_of,
            sponsor_pct=s.sponsor_pct,
            government_pct=s.government_pct,
            institution_pct=s.institution_pct,
            foreign_pct=s.foreign_pct,
            public_pct=s.public_pct,
        ),
        week_high_52=f.week_high_52,
        week_low_52=f.week_low_52,
        paid_up_capital=f.paid_up_capital,
        year_end=f.year_end,
        listing_year=f.listing_year,
        info=CompanyInfoDto(**dataclasses.asdict(f.info)) if f.info else None,
        year_history=[YearFinancialDto(**dataclasses.asdict(y)) for y in f.year_history],
        holding_history=[_holding(h) for h in f.holding_history],
    )


def announcement_dto(a: Announcement) -> AnnouncementDto:
    return AnnouncementDto(id=a.id, published_on=a.published_on, kind=a.kind, title=a.title, body=a.body)
