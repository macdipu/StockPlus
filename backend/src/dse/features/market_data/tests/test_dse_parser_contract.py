"""Contract: the new adapter must reproduce the legacy implementation's output for the same DSE bytes."""

from typing import Any

import pytest

from dse.features.market_data.application.mappers import fundamentals_dto
from dse.features.market_data.domain.entities import CompanyPage, MarketSnapshot
from dse.features.market_data.infrastructure.dse_parser import parse_company_page
from dse.features.market_data.tests.fakes import NOW
from dse.shared_kernel.errors import NotFoundError, UpstreamUnavailableError
from dse.shared_kernel.symbol import Symbol


def test_bars_match_legacy(page: CompanyPage, golden: dict[str, Any]) -> None:
    got = [
        {
            "day": b.day.isoformat(),
            "open": float(b.open),
            "high": float(b.high),
            "low": float(b.low),
            "close": float(b.close),
            "volume": b.volume,
        }
        for b in page.bars
    ]
    assert got == golden["bars"]


def test_fundamentals_match_legacy(page: CompanyPage, golden: dict[str, Any]) -> None:
    g = golden["fundamentals"]
    price = page.last_price
    f = fundamentals_dto(page.fundamentals, price)
    assert page.instrument.name == g["name"]
    assert page.instrument.sector == g["sector"]
    assert page.instrument.category == g["category"]
    assert page.instrument.isin == g["isin"]
    pairs = {
        "eps_ttm": f.eps_ttm,
        "eps_annual": f.eps_annual,
        "eps_q1": f.eps_q1,
        "eps_q2": f.eps_q2,
        "eps_q3": f.eps_q3,
        "eps_half_year": f.eps_half_year,
        "eps_nine_months": f.eps_nine_months,
        "nav": f.nav,
        "total_shares": f.total_shares,
        "free_float_pct": f.free_float_pct,
        "sponsor_pct": f.shareholding.sponsor_pct,
        "institute_pct": f.shareholding.institution_pct,
        "public_pct": f.shareholding.public_pct,
        "dps": f.dividend_per_share,
        "week_high_52": f.week_high_52,
        "week_low_52": f.week_low_52,
        "pe_dse_trailing": f.pe_dse_trailing,
        "dividend_yield_pct": f.dividend_yield_pct,
    }
    for key, value in pairs.items():
        assert value == pytest.approx(g[key]), key
    assert f.eps_ttm_basis == g["eps_ttm_basis"]
    assert f.pe == pytest.approx(g["pe"])


def test_announcements_parsed(page: CompanyPage, golden: dict[str, Any]) -> None:
    assert len(page.announcements) == golden["news_count"]
    assert all(a.published_on is not None for a in page.announcements)


def test_snapshot_matches_legacy(snapshot: MarketSnapshot, golden: dict[str, Any]) -> None:
    q, g = snapshot.quotes["ORIONINFU"], golden["snapshot_ORIONINFU"]
    assert (q.ltp, q.ycp, q.high, q.low, q.volume, q.category) == (
        g["ltp"],
        g["ycp"],
        g["high"],
        g["low"],
        g["volume"],
        g["category"],
    )
    assert snapshot.session_date is not None
    assert len(snapshot.quotes) > 300


def test_unknown_or_changed_pages_fail_clearly() -> None:
    with pytest.raises(UpstreamUnavailableError, match="flight payload"):
        parse_company_page("<html></html>", Symbol("X"), NOW)
    empty = '<script>self.__next_f.push([1,"{\\"company\\":{}}"])</script>'
    with pytest.raises(NotFoundError):
        parse_company_page(empty, Symbol("X"), NOW)
