import numpy as np
import pandas as pd
import pytest

from dse.features.scanner.tests import legacy_adapter as scanner

def bars(closes, vol=1000.0, spread=1.0):
    c = pd.Series(closes, dtype=float, index=pd.date_range("2025-01-01", periods=len(closes), freq="B"))
    return pd.DataFrame({"open": c - 0.2, "high": c + spread, "low": c - spread, "close": c, "volume": vol,
                         "trades": 10.0})

@pytest.fixture(scope="module")
def universe():
    rng = np.random.default_rng(1)
    up = bars(100 * np.cumprod(1 + 0.004 + rng.normal(0, 0.008, 260)))
    down = bars(100 * np.cumprod(1 - 0.004 + rng.normal(0, 0.008, 260)))
    cross = bars(np.r_[np.linspace(120, 90, 220), np.linspace(90, 130, 40)])
    fund = {"UP": {"eps_ttm": 10, "nav": 50, "category": "A", "sector": "Bank"},
            "DOWN": {"eps_ttm": -1, "nav": 20, "category": "Z", "sector": "Textile"},
            "CROSS": {"category": "B", "sector": "Bank"}}
    quotes = {s: {"assetType": "EQ", "value": 5.0} for s in fund}
    return scanner.build_universe({"UP": up, "DOWN": down, "CROSS": cross}, fund, quotes, {}, live=True)


def test_universe_rows_and_fields(universe):
    assert set(universe["symbol"]) == {"UP", "DOWN", "CROSS"} and not universe.attrs["errors"]
    row = universe.loc["UP"]
    assert row["pe"] == pytest.approx(row["ltp"] / 10) and row["graham"] == pytest.approx((22.5 * 10 * 50) ** 0.5)
    assert universe.loc["DOWN"]["pe"] is None or np.isnan(universe.loc["DOWN"]["pe"])


def test_rules(universe):
    run = lambda rules, **kw: set(scanner.run(universe, rules, **kw)["symbol"])
    assert run([{"field": "close", "op": ">", "field2": "sma200"}]) >= {"UP"}
    assert "DOWN" in run([{"field": "close", "op": "<", "field2": "sma50"}])
    assert run([{"field": "category", "op": "in", "value": ["A", "B"]}]) == {"UP", "CROSS"}
    assert run([{"field": "rsi14", "op": "between", "value": [0, 100]}]) == {"UP", "DOWN", "CROSS"}
    assert run([{"field": "category", "op": "==", "value": "Z"}, {"field": "category", "op": "==", "value": "A"}],
               match="any") == {"UP", "DOWN"}
    assert run([], universe={"sectors": ["Bank"]}) == {"UP", "CROSS"}
    with pytest.raises(scanner.ScanError):
        scanner.run(universe, [{"field": "nope", "op": ">", "value": 1}])


def test_crosses_uses_prev_columns():
    u = pd.DataFrame({"a": [2.0, 2.0, 0.5], "a_prev": [1.0, 3.0, 1.0], "b": [1.5, 2.5, 1.0],
                      "b_prev": [1.5, 2.5, 1.0]}, index=["X", "Y", "Z"])
    up = scanner.evaluate(u, {"field": "a", "op": "crosses_above", "field2": "b"})
    dn = scanner.evaluate(u, {"field": "a", "op": "crosses_below", "field2": "b"})
    assert list(up) == [True, False, False] and list(dn) == [False, True, True]


def test_every_preset_runs(universe):
    for key, p in scanner.PRESETS.items():
        scanner.run(universe, p["rules"], p["match"], sort=p["sort"])   # no exception = fields exist


def test_sectors_and_pe(universe):
    names = {r["sector"] for r in scanner.sectors(universe)}
    assert names == {"Bank", "Textile"}
    assert scanner.pe_summary(universe)["market"]["instruments"] >= 0
