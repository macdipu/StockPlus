"""Hand-checkable cases: small inputs whose answers can be derived on paper."""

import numpy as np
import pandas as pd

from dse.indicators import maths
from dse.indicators.base import REGISTRY
from dse.indicators.tests.conftest import tiny

NAN = np.nan


def s(*v: float) -> pd.Series:
    return pd.Series(v, dtype="float64")


def vals(df: pd.DataFrame, col: str = "value") -> np.ndarray:
    return df[col].to_numpy()


def check(actual: np.ndarray, expected: list[float], tol: float = 1e-9) -> None:
    np.testing.assert_allclose(actual, np.array(expected, dtype="float64"), rtol=0, atol=tol, equal_nan=True)


# a four-bar OHLC case reused below
BARS4 = tiny(high=[10, 12, 11, 13], low=[8, 9, 9, 10], close=[9, 11, 10, 12])


def test_sma() -> None:
    check(maths.sma(s(1, 2, 3, 4, 5), 3).to_numpy(), [NAN, NAN, 2, 3, 4])


def test_ema_is_seeded_with_the_simple_average() -> None:
    # n=3 -> alpha 0.5; seed at bar 2 = mean(1,2,3) = 2; then 0.5*2+0.5*2 = 2; 0.5*5+0.5*2 = 3.5
    check(maths.ema(s(1, 2, 3, 2, 5), 3).to_numpy(), [NAN, NAN, 2, 2, 3.5])


def test_wma() -> None:
    # weights 1,2,3 / 6: (1+4+9)/6 and (2+6+12)/6
    check(maths.wma(s(1, 2, 3, 4), 3).to_numpy(), [NAN, NAN, 14 / 6, 20 / 6])


def test_rma_wilder() -> None:
    # seed = mean(3,6,9) = 6; next = 6*(2/3) + 12*(1/3) = 8
    check(maths.rma(s(3, 6, 9, 12), 3).to_numpy(), [NAN, NAN, 6, 8])


def test_rsi_wilder_stockcharts_example() -> None:
    """The classic 14-period RSI worked example (StockCharts / Wilder); first 14 readings to 2 decimals."""
    close = [
        44.3389, 44.0902, 44.1497, 43.6124, 44.3278, 44.8264, 45.0955, 45.4245, 45.8433, 46.0826,
        45.8931, 46.0328, 45.6140, 46.2820, 46.2820, 46.0028, 46.0328, 46.4116, 46.2222, 45.6439,
        46.2122, 46.2521, 45.7137, 46.4515, 45.7835, 45.3548, 44.0288, 44.1783,
    ]  # fmt: skip
    got = REGISTRY["rsi"].run(tiny(close=close))["value"]
    assert got.iloc[:14].isna().all()
    expected = [
        70.53,
        66.32,
        66.55,
        69.41,
        66.36,
        57.97,
        62.93,
        63.26,
        56.06,
        62.38,
        54.71,
        50.42,
        39.99,
        41.46,
    ]
    assert got.iloc[14:].round(2).tolist() == expected


def test_rsi_extremes() -> None:
    up = REGISTRY["rsi"].run(tiny(close=list(range(1, 30))), {"length": 5})["value"]
    down = REGISTRY["rsi"].run(tiny(close=list(range(30, 1, -1))), {"length": 5})["value"]
    assert up.iloc[-1] == 100.0
    assert down.iloc[-1] == 0.0


def test_macd_is_ema_difference(daily: pd.DataFrame) -> None:
    res = REGISTRY["macd"].run(daily)
    line = maths.ema(daily["close"], 12) - maths.ema(daily["close"], 26)
    np.testing.assert_allclose(res["macd"].to_numpy(), line.to_numpy(), atol=1e-12, equal_nan=True)
    np.testing.assert_allclose(
        res["signal"].to_numpy(), maths.ema(line, 9).to_numpy(), atol=1e-12, equal_nan=True
    )
    np.testing.assert_allclose(
        (res["macd"] - res["signal"]).to_numpy(), res["hist"].to_numpy(), atol=1e-12, equal_nan=True
    )
    assert res["macd"].first_valid_index() == daily.index[25]
    assert res["signal"].first_valid_index() == daily.index[33]


def test_bbands_basis_and_population_stdev(daily: pd.DataFrame) -> None:
    res = REGISTRY["bbands"].run(daily)
    np.testing.assert_allclose(
        res["basis"].to_numpy(), daily["close"].rolling(20).mean().to_numpy(), equal_nan=True
    )
    last_window = daily["close"].to_numpy()[-20:]
    width = res["upper"].iloc[-1] - res["lower"].iloc[-1]
    assert abs(width - 4 * np.std(last_window)) < 1e-9  # ddof=0
    assert abs(width - 4 * np.std(last_window, ddof=1)) > 1e-6


def test_true_range() -> None:
    # bar1: max(3, |12-9|, |9-9|) = 3; bar2: max(2, |11-11|, |9-11|) = 2; bar3: max(3, |13-10|, |10-10|) = 3
    check(maths.true_range(BARS4).to_numpy(), [2, 3, 2, 3])


def test_atr_wilder() -> None:
    # n=2: seed = (2+3)/2 = 2.5; then 2.5*0.5 + 2*0.5 = 2.25; then 2.25*0.5 + 3*0.5 = 2.625
    check(vals(REGISTRY["atr"].run(BARS4, {"length": 2})), [NAN, 2.5, 2.25, 2.625])


def test_obv() -> None:
    df = tiny(close=[10, 11, 10, 10, 12], volume=[100, 200, 300, 400, 500])
    # first bar has no previous close; up +200, down -300, flat +0, up +500
    check(vals(REGISTRY["obv"].run(df)), [NAN, 200, -100, -100, 400])


def test_stoch_k_formula() -> None:
    res = REGISTRY["stoch"].run(BARS4, {"k_length": 3, "k_smoothing": 1, "d_smoothing": 2})
    # bar2: 100*(10-8)/(12-8) = 50; bar3: 100*(12-9)/(13-9) = 75; %D = mean of two %K
    check(vals(res, "k"), [NAN, NAN, 50, 75])
    check(vals(res, "d"), [NAN, NAN, NAN, 62.5])


def test_donchian() -> None:
    res = REGISTRY["donchian"].run(BARS4, {"length": 3})
    check(vals(res, "upper"), [NAN, NAN, 12, 13])
    check(vals(res, "lower"), [NAN, NAN, 8, 9])
    check(vals(res, "basis"), [NAN, NAN, 10, 11])


def test_vwap_daily_resets_each_month() -> None:
    idx = pd.DatetimeIndex(["2024-01-30", "2024-01-31", "2024-02-01", "2024-02-02"])
    df = pd.DataFrame(
        {
            "open": [9.0, 10.0, 20.0, 21.0],
            "high": [10.0, 12.0, 22.0, 24.0],
            "low": [8.0, 8.0, 18.0, 18.0],
            "close": [9.0, 10.0, 20.0, 21.0],
            "volume": [100.0, 300.0, 50.0, 50.0],
        },
        index=idx,
    )
    tp = [9.0, 10.0, 20.0, 21.0]  # (h+l+c)/3
    res = vals(REGISTRY["vwap"].run(df))
    # first bar of a month equals that bar's typical price; later bars are volume-weighted cumulative
    check(res, [tp[0], (tp[0] * 100 + tp[1] * 300) / 400, tp[2], (tp[2] * 50 + tp[3] * 50) / 100])


def test_vwap_intraday_resets_each_date() -> None:
    idx = pd.DatetimeIndex(["2024-01-02 10:00", "2024-01-02 10:01", "2024-01-03 10:00", "2024-01-03 10:01"])
    df = pd.DataFrame(
        {
            "open": 1.0,
            "high": [3.0, 3.0, 6.0, 6.0],
            "low": [3.0, 3.0, 6.0, 6.0],
            "close": [3.0, 3.0, 6.0, 6.0],
        },
        index=idx,
    )
    df["volume"] = [10.0, 10.0, 10.0, 30.0]
    check(vals(REGISTRY["vwap"].run(df)), [3, 3, 6, 6])
    df["close"] = df["high"] = df["low"] = [3.0, 6.0, 9.0, 3.0]
    # session 1: (3*10+6*10)/20 = 4.5 ; session 2 restarts at 9 then (9*10+3*30)/40 = 4.5
    check(vals(REGISTRY["vwap"].run(df)), [3, 4.5, 9, 4.5])


def test_supertrend_only_flips_when_close_crosses_the_band(daily: pd.DataFrame) -> None:
    res = REGISTRY["supertrend"].run(daily)
    up, down, close = res["up"].to_numpy(), res["down"].to_numpy(), daily["close"].to_numpy()
    both = ~np.isnan(up) & ~np.isnan(down)
    assert not both.any()
    state = np.where(~np.isnan(up), 1, np.where(~np.isnan(down), -1, 0))
    assert (state[10:] != 0).all()
    flips = np.flatnonzero(np.diff(state[10:]) != 0) + 10
    assert len(flips) >= 3
    # while bullish the close never sits below the support line; while bearish never above the resistance line
    bull = state == 1
    assert (close[bull] >= up[bull]).all()
    bear = state == -1
    assert (close[bear] <= down[bear]).all()
    # a flip to bearish needs a close below the previous support; to bullish above the previous resistance
    for t in flips + 1:
        if state[t] == -1:
            assert close[t] <= down[t]
            assert close[t - 1] >= up[t - 1] - 1e-9
        else:
            assert close[t] >= up[t]
            assert close[t - 1] <= down[t - 1] + 1e-9
    # the support line never falls while it stays bullish, the resistance never rises while bearish
    for i in range(11, len(close)):
        if state[i] == 1 and state[i - 1] == 1:
            assert up[i] >= up[i - 1] - 1e-9
        if state[i] == -1 and state[i - 1] == -1:
            assert down[i] <= down[i - 1] + 1e-9


def test_supertrend_hand_case() -> None:
    # flat then a collapse: atr 1 (length 1), factor 1 => bands are hl2 +- 1
    df = tiny(
        high=[10.5, 10.5, 10.5, 5.5, 5.5],
        low=[9.5, 9.5, 9.5, 4.5, 4.5],
        close=[10, 10, 10, 5, 5],
    )
    res = REGISTRY["supertrend"].run(df, {"atr_length": 1, "factor": 1.0})
    # TR on the gap bar is 5.0 (|4.5-10|), so the bands move; direction flips only on that bar
    assert res["up"].iloc[:3].notna().all()
    assert np.isnan(res["up"].iloc[3])
    assert res["down"].iloc[3:].notna().all()


def test_williams_r_bounds_and_extremes(daily: pd.DataFrame) -> None:
    w = REGISTRY["willr"].run(daily)["value"].dropna()
    assert (w >= -100 - 1e-9).all()
    assert (w <= 1e-9).all()
    df = tiny(high=[10, 12, 12], low=[8, 8, 8], close=[9, 8, 12])
    check(vals(REGISTRY["willr"].run(df, {"length": 3})), [NAN, NAN, 0.0])
    df2 = tiny(high=[10, 12, 12], low=[8, 8, 8], close=[9, 11, 8])
    check(vals(REGISTRY["willr"].run(df2, {"length": 3})), [NAN, NAN, -100.0])


def test_roc_and_momentum() -> None:
    df = tiny(close=[100, 110, 121, 100])
    check(
        vals(REGISTRY["roc"].run(df, {"length": 2})),
        [NAN, NAN, 21.0, (100 / 110 - 1) * 100],
    )
    check(vals(REGISTRY["momentum"].run(df, {"length": 2})), [NAN, NAN, 21, -10])


def test_cci_hand_case() -> None:
    df = tiny(close=[1, 2, 6])  # high = low = close, so the typical price is the close
    # sma 3, mean deviation (2+1+3)/3 = 2 -> (6-3) / (0.015 * 2) = 100
    check(vals(REGISTRY["cci"].run(df, {"length": 3})), [NAN, NAN, 100.0], tol=1e-9)


def test_pivot_points_use_the_previous_bar() -> None:
    df = tiny(high=[12, 20], low=[8, 15], close=[10, 18])
    res = REGISTRY["pivot_points"].run(df)
    assert res.iloc[0].isna().all()
    # P = (12+8+10)/3 = 10; R1 = 12, S1 = 8; R2 = P + 4 = 14; S2 = P - 4 = 6
    assert res.iloc[1].tolist() == [10.0, 12.0, 14.0, 8.0, 6.0]


def test_price_transforms() -> None:
    df = pd.DataFrame(
        {"open": [2.0], "high": [6.0], "low": [2.0], "close": [4.0], "volume": [1.0]},
        index=pd.bdate_range("2024-01-01", periods=1),
    )
    assert REGISTRY["typical_price"].run(df)["value"].iloc[0] == 4.0
    assert REGISTRY["median_price"].run(df)["value"].iloc[0] == 4.0
    assert REGISTRY["average_price"].run(df)["value"].iloc[0] == 3.5
    assert REGISTRY["weighted_close"].run(df)["value"].iloc[0] == 4.0


def test_lsma_follows_a_straight_line_exactly() -> None:
    df = tiny(close=[2.0 * i + 1 for i in range(10)])
    check(vals(REGISTRY["lsma"].run(df, {"length": 5})), [NAN] * 4 + [2.0 * i + 1 for i in range(4, 10)])
    # offset 1 evaluates the fitted line one bar back
    check(
        vals(REGISTRY["lsma"].run(df, {"length": 5, "offset": 1})),
        [NAN] * 4 + [2.0 * (i - 1) + 1 for i in range(4, 10)],
    )


def test_averages_of_a_constant_series_are_that_constant() -> None:
    df = tiny(close=[7.0] * 120)
    for ind_id in (
        "sma",
        "ema",
        "wma",
        "hma",
        "dema",
        "tema",
        "smma",
        "lsma",
        "alma",
        "mcginley",
        "kama",
        "vwma",
    ):
        got = REGISTRY[ind_id].run(df)["value"].dropna()
        assert len(got) > 0
        np.testing.assert_allclose(got.to_numpy(), 7.0, atol=1e-9, err_msg=ind_id)


def test_aroon_extremes() -> None:
    df = tiny(high=[1, 2, 3, 4, 5, 6], low=[0, 1, 2, 3, 4, 5], close=[1, 2, 3, 4, 5, 6])
    res = REGISTRY["aroon"].run(df, {"length": 3})
    assert res["up"].iloc[-1] == 100.0  # new high on the current bar
    assert res["down"].iloc[-1] == 0.0  # lowest low is 3 bars back


def test_parabolic_sar_flips_when_price_crosses() -> None:
    close = [10, 11, 12, 13, 14, 9, 8, 7]
    df = tiny(high=[c + 0.5 for c in close], low=[c - 0.5 for c in close], close=close)
    sar = vals(REGISTRY["psar"].run(df), "sar")
    assert np.isnan(sar[0])
    assert (sar[1:5] < df["low"].to_numpy()[1:5]).all()  # rising: dots under the bars
    assert sar[5] > df["high"].to_numpy()[5]  # after the collapse the dot jumps above price


def test_zigzag_finds_the_swings() -> None:
    close = [10, 12, 14, 12, 10, 12, 15, 11, 9]
    df = tiny(high=close, low=close, close=close)
    zz = vals(REGISTRY["zigzag"].run(df, {"deviation": 10.0}))
    # pivots: 10 (bar 0 low), 14 (bar 2 high), 10 (bar 4 low), 15 (bar 6 high), then the open leg ends at 9
    check(zz, [10, 12, 14, 12, 10, 12.5, 15, 12, 9], tol=1e-9)


def test_fibonacci_levels_span_the_range() -> None:
    df = tiny(high=[10, 20, 15], low=[5, 8, 12], close=[7, 15, 14])
    res = REGISTRY["fib_retracement"].run(df, {"length": 3})
    last = res.iloc[-1]
    assert last["l0"] == 20.0
    assert last["l1000"] == 5.0
    assert abs(last["l500"] - 12.5) < 1e-12
    assert abs(last["l618"] - (20 - 0.618 * 15)) < 1e-12


def test_ichimoku_spans_are_shifted_forward() -> None:
    df = tiny(high=list(range(10, 40)), low=list(range(0, 30)), close=list(range(5, 35)))
    res = REGISTRY["ichimoku"].run(df, {"conversion": 2, "base": 3, "span_b": 4, "displacement": 5})
    conv, base = res["conversion"], res["base"]
    lead_a = res["leading_a"]
    assert lead_a.iloc[:7].isna().all()  # first base value at bar 2, shifted by 5
    assert lead_a.iloc[7] == (conv.iloc[2] + base.iloc[2]) / 2
    assert "lagging" not in res.columns


def test_bop_range(daily: pd.DataFrame) -> None:
    b = REGISTRY["bop"].run(daily)["value"]
    assert b.between(-1, 1).all()


def test_connors_rsi_bounds(daily: pd.DataFrame) -> None:
    c = REGISTRY["connors_rsi"].run(daily)["value"].dropna()
    assert len(c) > 200
    assert c.between(0, 100).all()


def test_bounded_oscillators_stay_in_their_scale(daily: pd.DataFrame) -> None:
    for ind in REGISTRY.values():
        if ind.scale is None:
            continue
        lo, hi = ind.scale
        res = ind.run(daily)
        main = res.iloc[:, 0].dropna() if ind.id not in {"adx", "dmi"} else res["adx"].dropna()
        if ind.id in {"aroon", "stoch", "stochrsi"}:
            main = res.iloc[:, 0].dropna()
        assert main.between(lo - 1e-9, hi + 1e-9).all(), ind.id
