"""Parsers run on recorded pages from each source (ENVOYTEX, Nov 2026); insights and alerts on plain data."""

import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from dse.features.company.domain import insights
from dse.features.company.domain.alerts import alerts_for
from dse.features.company.domain.entities import CompanyDossier
from dse.features.company.infrastructure.exchange import exchange_part, fiscal_period_end
from dse.features.company.infrastructure.http_sources import _as_flight_html
from dse.features.company.infrastructure.parsers import (
    flight_objects,
    html_tables,
    parse_amarstock,
    parse_topstock,
)

F = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def dossier() -> CompanyDossier:
    raw = json.loads((F / "exchange_ENVOYTEX.json").read_text())
    ex = exchange_part(raw["profile"], raw["announcements"])
    am = parse_amarstock((F / "amarstock_ENVOYTEX.html").read_text())
    ts = parse_topstock((F / "topstock_ENVOYTEX.html").read_text())
    return CompanyDossier("ENVOYTEX", "2026-11-18T11:00:00", ex, am, ts)


def test_exchange_part_from_the_exchange_page(dossier: CompanyDossier) -> None:
    ex = dossier.exchange
    assert ex.listing_year == 2012
    assert ex.year_end == "June"
    assert ex.contact.website
    assert ex.contact.address
    assert "Envoy Tower" in ex.contact.address
    assert ex.capital.authorized_mn == pytest.approx(4750.0)  # BDT million
    assert ex.capital.paid_up_mn == pytest.approx(
        1677.35, rel=1e-3
    )  # the page gives BDT; converted to million
    assert ex.capital.short_term_loan_mn is not None
    assert ex.capital.total_loan_mn is not None
    eps = {e.period_end: e.value for e in ex.eps_annual}
    assert eps["2025-06-30"] == 8.4  # a June year-end company: fiscal year 2025 ends 30 June 2025
    assert ex.dividends[-1].cash_pct == 30.0
    assert ex.dividends[-1].period_end == "2025-06-30"
    assert [h.as_of for h in ex.shareholding] == sorted(h.as_of for h in ex.shareholding)
    assert ex.shareholding[-1].director == pytest.approx(65.41)
    assert ex.events.last_agm is not None
    assert ex.events.last_agm.count("-") == 2


def test_quarterly_eps_and_fiscal_periods_from_the_exchange_fields() -> None:
    profile = {
        "fundamentals": {
            "year_end": "June",
            "eps_period_ends": {
                "q1": "202509",
                "q2": "202512",
                "half": "202512",
                "q3": "202603",
                "nine": "202603",
            },
            "eps_q1": 0.57,
            "eps_q2": 0.58,
            "eps_half_year": 1.15,
            "eps_q3": 0.27,
            "eps_nine_months": 1.42,
        }
    }
    q = exchange_part(profile, []).eps_quarterly
    assert [(x.period, x.period_end, x.eps) for x in q] == [
        ("q1", "2025-09-30", 0.57), ("q2", "2025-12-31", 0.58), ("q3", "2026-03-31", 0.27),
        ("h1", "2025-12-31", 1.15), ("9m", "2026-03-31", 1.42),
    ]  # fmt: skip
    assert fiscal_period_end(2024, "February") == "2024-02-29"
    assert fiscal_period_end(2025, None) == "2025-12-31"
    assert (
        exchange_part({}, []).eps_annual == ()
    )  # a page without the fields yields an empty part, not an error


def test_announcements_become_news() -> None:
    part = exchange_part(
        {},
        [
            {"published_on": "2026-11-10", "title": "Board meeting", "kind": "Notice", "body": "text"},
            {"published_on": None, "title": None, "kind": "Notice", "body": ""},
        ],
    )
    assert [(n.day.isoformat() if n.day else None, n.title) for n in part.news] == [
        ("2026-11-10", "Board meeting"),
        (None, "Notice"),
    ]


def test_amarstock_statements_and_trades(dossier: CompanyDossier) -> None:
    am = dossier.amarstock
    assert [s.kind for s in am.statements] == ["income", "balance_sheet", "cash_flow"]
    income = am.statements[0]
    assert income.years == ("2022", "2023", "2024", "2025")
    revenue = income.rows[0]
    assert revenue.label.startswith("Revenue")
    assert revenue.total
    assert revenue.values[-1] == pytest.approx(18_624_802_107)  # "1,86,24,80,21,07" South-Asian grouping
    assert income.rows[-1].values[-1] == pytest.approx(8.4)
    assert am.director_trades
    assert am.director_trades[0].side == "Buy"
    keys = [(t.day, t.holder, t.side, t.quantity, t.price) for t in am.director_trades]
    assert len(keys) == len(set(keys))  # the page repeats rows; we keep one


def test_topstock_years_and_rating(dossier: CompanyDossier) -> None:
    ts = dossier.topstock
    assert ts.rating is not None
    assert ts.rating.long_term == "AA1"
    assert ts.rating.agency == "CRAB"
    fy25 = next(y for y in ts.years if y.year == 2025)
    assert fy25.revenue
    assert fy25.total_equity
    assert fy25.net_profit
    assert ts.events.declared_dividend_pct == 32.5
    # the adapter caches only the extracted objects; re-wrapping them must parse identically
    again = parse_topstock(
        _as_flight_html(
            flight_objects(
                (F / "topstock_ENVOYTEX.html").read_text(),
                ("extFinancials", "financials", "rating", "declaration"),
            )
        )
    )
    assert again == ts


def test_html_tables_tolerates_unclosed_cells() -> None:
    tables, bold = html_tables("<table><tr><td class=font-weight-bold>A<td>1<tr><td>B<td>(2)</table>")
    assert tables == [[["A", "1"], ["B", "(2)"]]]
    assert bold == [[True, False]]


def test_ratios_state_their_basis_and_flags_are_cautious(dossier: CompanyDossier) -> None:
    r = {x.key: x for x in insights.ratios(dossier, 85.8)}
    nav = dossier.exchange.nav[-1].value  # the exchange reports the annual NAV
    assert r["pb"].value == pytest.approx(85.8 / nav)
    dps = dossier.exchange.dividends[-1].cash_pct / 100 * 10  # % of the Tk 10 face value
    assert r["dividend_yield"].value == pytest.approx(dps / 85.8 * 100)
    assert all(x.basis for x in r.values())
    texts = [f.text for f in insights.flags(dossier, 85.8)]
    # TopStock counts only part of the debt; the exchange's loans give more. The flag uses the larger.
    assert any("equity" in t and ("borrowing" in t) for t in texts)
    assert any("AA1" in t for t in texts)


def _analysis(where: str, price: float, patterns: list[dict[str, Any]], live: bool = True) -> dict[str, Any]:
    return {
        "symbol": "PADMAOIL",
        "price": {"ltp": price, "last_bar_date": "2026-11-18", "live_bar": live},
        "candles": {"patterns": patterns},
        "candle_story": {
            "where": where,
            "annotations": [
                {"kind": "entry", "price": 197.0, "price_to": 194.0, "label": "BUY ZONE"},
                {"kind": "stop", "price": 189.0, "label": "EXIT"},
                {"kind": "target", "price": 205.0, "label": "TAKE PROFIT"},
                {"kind": "watch", "price": 200.0, "label": "WATCH breakout 200.00"},
            ],
        },
    }


def test_buy_zone_alert_reads_like_a_notification() -> None:
    a = _analysis("inside_buy_zone", 196.8, [{"pattern": "Hammer", "bars_ago": 0}])
    events = {"record_date": "2026-11-29", "declared_dividend_pct": 170.0}
    out = alerts_for(a, events, [], date(2026, 11, 18))
    assert [x.kind for x in out] == ["buy_zone"]
    assert out[0].message == (
        "PADMAOIL 196.8 in buy zone (194–197) with a hammer forming. "  # noqa: RUF001
        "Tk 17 dividend still ahead (record 29 Nov). Stop 189, target 205."
    )
    assert out[0].key == "PADMAOIL:buy_zone:2026-11-18"


def test_stop_target_breakout_and_bearish_alerts() -> None:
    today = date(2026, 11, 18)
    assert alerts_for(_analysis("below_stop", 188.0, []), None, [], today)[0].kind == "stop"
    assert alerts_for(_analysis("above_buy_zone", 206.0, []), None, [], today)[0].kind == "target"
    kinds = [x.kind for x in alerts_for(_analysis("above_buy_zone", 201.0, []), None, [], today)]
    assert kinds == ["breakout"]
    bear = alerts_for(
        _analysis("above_buy_zone", 198.0, [{"pattern": "Shooting Star", "bars_ago": 0}]), None, [], today
    )
    assert [x.kind for x in bear] == ["bearish_candle"]
    # a past record date adds no dividend note
    old = alerts_for(
        _analysis("inside_buy_zone", 196.0, []),
        {"record_date": "2026-10-01", "declared_dividend_pct": 50},
        [],
        today,
    )
    assert "dividend" not in old[0].message
