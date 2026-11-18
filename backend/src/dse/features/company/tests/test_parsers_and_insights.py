"""Parsers run on recorded pages from each source (ENVOYTEX, Nov 2026); insights and alerts on plain data."""

import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from dse.features.company.domain import insights
from dse.features.company.domain.alerts import alerts_for
from dse.features.company.domain.entities import CompanyDossier
from dse.features.company.infrastructure.http_sources import _as_flight_html, parse_bars
from dse.features.company.infrastructure.parsers import (
    flight_objects,
    html_tables,
    parse_amarstock,
    parse_stocknow,
    parse_topstock,
)

F = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def dossier() -> CompanyDossier:
    sn = parse_stocknow(
        json.loads((F / "stocknow_ENVOYTEX_fundamentals.json").read_text()),
        json.loads((F / "stocknow_ENVOYTEX_news.json").read_text()),
    )
    am = parse_amarstock((F / "amarstock_ENVOYTEX.html").read_text())
    ts = parse_topstock((F / "topstock_ENVOYTEX.html").read_text())
    return CompanyDossier("ENVOYTEX", "2026-11-18T11:00:00", sn, am, ts)


def test_stocknow_history(dossier: CompanyDossier) -> None:
    sn = dossier.stocknow
    assert sn.listing_year == 2012
    assert sn.contact.website == "http://www.envoytextiles.com"
    assert sn.contact.address
    assert "Envoy Tower" in sn.contact.address
    assert sn.capital.paid_up_mn == pytest.approx(1677.35)
    assert sn.capital.total_loan_mn == pytest.approx(3014.14 + 7385.4)
    assert [(e.period_end, e.value) for e in sn.eps_annual[-2:]] == [
        ("2025-06-30", 8.4),
        ("2026-06-30", 8.24),
    ]
    assert sn.dividends[-1].cash_pct == 32.5
    assert sn.dividends[-1].year == 2026
    assert len(sn.shareholding) > 90
    assert sn.shareholding[-1].director == pytest.approx(65.41)
    assert {q.period for q in sn.eps_quarterly} == {"q1", "q2", "q3", "h1", "9m"}
    assert sn.events.last_agm == "2025-12-06"  # dd-mm-yyyy normalised to ISO
    assert sn.news
    assert sn.news[0].day == date(2026, 11, 9)


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
    assert r["pb"].value == pytest.approx(85.8 / 63.49)
    assert r["dividend_yield"].value == pytest.approx(3.25 / 85.8 * 100)
    assert all(x.basis for x in r.values())
    texts = [f.text for f in insights.flags(dossier, 85.8)]
    # TopStock counts only part of the debt (0.3x); StockNow's loans give 1.2x. The flag uses the larger.
    assert any("1.2x equity" in t for t in texts)
    assert any("AA1" in t for t in texts)


def test_parse_bars() -> None:
    bars = parse_bars([[1, 2], [1.5, 2.5], [0.5, 1.5], [1.2, 2.2], [10, None], [100, 200]])
    assert bars == [
        {"time": 100, "open": 1.0, "high": 1.5, "low": 0.5, "close": 1.2, "volume": 10},
        {"time": 200, "open": 2.0, "high": 2.5, "low": 1.5, "close": 2.2, "volume": 0},
    ]


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
