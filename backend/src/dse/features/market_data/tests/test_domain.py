from dataclasses import replace
from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from dse.features.market_data.domain.entities import (
    BarSource,
    DailyBar,
    Dividend,
    EpsReport,
    Fundamentals,
    MarketSnapshot,
    Quote,
    ShareholdingPattern,
)
from dse.shared_kernel.errors import ValidationFailedError
from dse.shared_kernel.symbol import Symbol

S = Symbol("TEST")


def fundamentals(**eps: Any) -> Fundamentals:
    return Fundamentals(
        eps=EpsReport(**eps),
        nav=20.0,
        face_value=10.0,
        paid_up_capital=1_000_000.0,
        market_cap=None,
        free_float_pct=None,
        shareholding=ShareholdingPattern(None, 40, 0, 10, 1, 49),
        dividends=(Dividend(2024, 10, 0), Dividend(2025, 25, 5)),
        pe_dse=None,
        pe_dse_trailing=None,
        dividend_yield_pct=None,
        week_high_52=None,
        week_low_52=None,
    )


def test_symbol_normalises_and_validates() -> None:
    assert Symbol(" amcl(pran) ").value == "AMCL(PRAN)"
    with pytest.raises(ValidationFailedError):
        Symbol("bad sym!")


def test_ttm_uses_annual_when_it_is_the_newest_report() -> None:
    f = fundamentals(annual=2.0, q1=0.5, period_ends={"annual": "202606", "q1": "202509"})
    assert f.ttm_eps().value == 2.0
    assert "annual" in f.ttm_eps().basis


def test_ttm_annualises_newest_ytd_figure() -> None:
    f = fundamentals(annual=2.0, q1=0.6, half_year=1.1, period_ends={"annual": "202606", "q1": "202609"})
    assert f.ttm_eps().value == pytest.approx(2.4)
    assert "Q1" in f.ttm_eps().basis
    f2 = fundamentals(
        annual=2.0,
        nine_months=1.8,
        q1=0.5,
        period_ends={"annual": "202606", "nine": "202703", "q1": "202609"},
    )
    assert f2.ttm_eps().value == pytest.approx(2.4)


def test_ttm_falls_back_to_last_audited_year() -> None:
    assert fundamentals(last_audited_year=1.7).ttm_eps().value == 1.7


def test_derived_values() -> None:
    f = fundamentals(annual=2.0)
    assert f.total_shares == 100_000
    assert f.last_dividend == Dividend(2025, 25, 5)
    assert f.dividend_per_share() == 2.5
    assert f.pe_at(50.0) == 25
    assert replace(f, eps=EpsReport(annual=-1.0)).pe_at(50.0) is None


def test_bar_invariants() -> None:
    with pytest.raises(ValidationFailedError):
        DailyBar(
            S, date(2026, 1, 1), Decimal(1), Decimal(1), Decimal(2), Decimal(1), 10, None, BarSource.PAGE
        )


def _q(sym: str, volume: int, close: float | None = None) -> Quote:
    return Quote(Symbol(sym), 11.0, 10.0, 10.5, 11.5, 10.0, close, volume, 1.0, 5, "A", "Bank", "EQ")


def test_end_of_day_bars_only_after_close_and_only_traded() -> None:
    quotes = {"AAA": _q("AAA", 100, 11.2), "BBB": _q("BBB", 0)}
    open_ = MarketSnapshot(date(2026, 11, 11), True, True, "x", quotes)
    assert open_.end_of_day_bars() == []
    closed = replace(open_, is_open=False)
    bars = closed.end_of_day_bars()
    assert [b.symbol.value for b in bars] == ["AAA"]
    assert bars[0].close == Decimal("11.2")
    assert bars[0].source == BarSource.SNAPSHOT
