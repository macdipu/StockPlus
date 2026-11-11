import math

import pytest

from dse.features.analysis.domain import valuation as V


def test_graham_number():
    assert V.graham_number(4, 25) == pytest.approx(math.sqrt(22.5 * 100))
    assert V.graham_number(-1, 25) is None


def test_ddm():
    assert V.ddm(2, 0.12, 0.04) == pytest.approx(2 * 1.04 / 0.08)
    assert V.ddm(2, 0.04, 0.05) is None
    assert V.ddm(0, 0.12, 0.04) is None


def test_dcf_no_growth_is_perpetuity():
    # g1 = g2 = 0 -> EPS / r
    assert V.dcf_two_stage(10, 0, 0, 0.10) == pytest.approx(100)


def test_dcf_matches_manual_sum():
    eps, g1, g2, r, n = 2.0, 0.10, 0.03, 0.12, 5
    e, pv = eps, 0
    for t in range(1, n + 1):
        e *= 1 + g1
        pv += e / (1 + r) ** t
    pv += e * (1 + g2) / (r - g2) / (1 + r) ** n
    assert V.dcf_two_stage(eps, g1, g2, r, n) == pytest.approx(pv)


def test_reverse_dcf_recovers_growth():
    price = V.dcf_two_stage(3, 0.17, 0.03, 0.12)
    assert V.reverse_dcf(price, 3, 0.03, 0.12) == pytest.approx(0.17, abs=1e-6)


def test_gap_pct():
    assert V.gap_pct(150, 100) == pytest.approx(50)
    assert V.gap_pct(None, 100) is None


def test_value_table_and_negative_eps_skips():
    fund = {"ltp": 100.0, "eps_ttm": 5.0, "eps_ttm_basis": "annual", "nav": 40.0, "dps": 2.0}
    out = V.value(fund)
    methods = {r["method"]: r for r in out["rows"]}
    assert methods["P/E 20x"]["fair_value"] == 100 and methods["P/E 20x"]["gap_pct"] == pytest.approx(0)
    assert methods["P/B 2.0x"]["fair_value"] == 80
    assert out["implied_growth"] is not None

    neg = V.value({**fund, "eps_ttm": -1.0})
    assert not any(r["method"].startswith(("P/E", "Graham", "DCF")) for r in neg["rows"])
    assert any("skipped" in n for n in neg["notes"])
    assert any(r["method"].startswith("P/B") for r in neg["rows"])
