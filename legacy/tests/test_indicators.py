import numpy as np
import pandas as pd
import pytest

import indicators as I


def frame(close, spread=1.0, volume=1000):
    c = pd.Series(close, dtype=float, index=pd.date_range("2025-01-01", periods=len(close)))
    return pd.DataFrame({"open": c, "high": c + spread, "low": c - spread, "close": c, "volume": float(volume)})


def test_sma_and_ema_on_constant_series():
    s = pd.Series([10.0] * 30)
    assert I.sma(s, 20).iloc[-1] == 10
    assert I.sma(s, 20).iloc[18] != I.sma(s, 20).iloc[18]  # NaN before the window fills
    assert I.ema(s, 9).iloc[-1] == pytest.approx(10)


def test_ema_recursion():
    s = pd.Series([1.0, 2.0, 3.0, 4.0])
    a = 2 / (3 + 1)
    e = [1.0]
    for x in s[1:]:
        e.append(a * x + (1 - a) * e[-1])
    assert I.ema(s, 3).iloc[-1] == pytest.approx(e[-1])


def test_rsi_extremes():
    up, down = pd.Series(np.arange(1, 40, dtype=float)), pd.Series(np.arange(40, 1, -1, dtype=float))
    assert I.rsi(up).iloc[-1] == pytest.approx(100)
    assert I.rsi(down).iloc[-1] == pytest.approx(0)
    assert I.rsi(pd.Series([5.0] * 30)).iloc[-1] == 50


def test_rsi_symmetric_moves_is_50():
    s = pd.Series([10.0, 11.0] * 50)
    assert I.rsi(s).iloc[-1] == pytest.approx(50, abs=5)


def test_macd_flat_is_zero():
    m = I.macd(pd.Series([7.0] * 60))
    assert m.iloc[-1].abs().max() == pytest.approx(0)


def test_bollinger():
    s = pd.Series([1.0, 3.0] * 10)  # mean 2, population std 1
    b = I.bollinger(s, 20, 2).iloc[-1]
    assert (b.bb_mid, b.bb_upper, b.bb_lower) == pytest.approx((2, 4, 0))


def test_atr_constant_range():
    assert I.atr(frame([100.0] * 30, spread=2.0)).iloc[-1] == pytest.approx(4.0)


def test_atr_uses_gaps():
    df = frame([100.0, 110.0], spread=1.0)
    tr2 = max(111 - 109, abs(111 - 100), abs(109 - 100))
    assert tr2 == 11
    assert I.atr(pd.concat([df] * 1), 1).iloc[-1] == pytest.approx(11)


def test_add_indicators_columns_and_volume_ratio():
    df = frame(np.linspace(100, 150, 220))
    df.iloc[-1, df.columns.get_loc("volume")] = 3000
    out = I.add_indicators(df)
    for col in ("sma200", "ema21", "rsi14", "macd_hist", "bb_upper", "atr14", "vol_ratio"):
        assert col in out and out[col].notna().iloc[-1]
    assert out["vol_ratio"].iloc[-1] == pytest.approx(3000 / ((19 * 1000 + 3000) / 20))


def test_merge_levels_and_support_resistance():
    assert I.merge_levels([100, 100.5, 120]) == [100.25, 120]
    zig = [100, 105, 110, 105, 100, 95, 90, 95, 100, 105, 110, 105, 100, 95, 90, 95, 100] * 2
    sr = I.support_resistance(frame(zig, spread=0.5))
    assert sr["high_52w"] == 110.5 and sr["low_52w"] == 89.5
    assert all(x > sr["price"] for x in sr["above"]) and all(x < sr["price"] for x in sr["below"])


def test_trend_changes():
    df = I.add_indicators(frame(np.linspace(100, 200, 400)))
    t = I.trend(df)
    assert t["changes"]["1Y"] > 0 and t["vs_ma"]["SMA200"]["pct"] > 0
