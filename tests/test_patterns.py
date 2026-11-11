import pandas as pd

import patterns as P


def bars(rows, lead=None):
    """rows: list of (o,h,l,c). `lead` prepends a 6-bar trend: 'down' or 'up'."""
    pre = []
    if lead == "down":
        pre = [(c + 1, c + 1.5, c - 0.5, c) for c in range(130, 118, -2)]
    elif lead == "up":
        pre = [(c - 1, c + 0.5, c - 1.5, c) for c in range(70, 82, 2)]
    df = pd.DataFrame(pre + rows, columns=["open", "high", "low", "close"], dtype=float)
    df.index = pd.date_range("2025-01-01", periods=len(df))
    return df


def names(df):
    return {n for n, _ in P.detect_at(df, len(df) - 1)}


def test_doji():
    assert "Doji" in names(bars([(100, 105, 95, 100.5)]))


def test_marubozu():
    assert "Bullish Marubozu" in names(bars([(100, 110.2, 99.9, 110)]))
    assert "Bearish Marubozu" in names(bars([(110, 110.1, 99.8, 100)]))


def test_hammer_needs_downtrend():
    candle = (100, 101, 90, 101)  # body 1, lower 10, no upper wick
    assert "Hammer" in names(bars([candle], "down"))
    assert "Hammer" not in names(bars([candle], "up"))


def test_inverted_hammer_vs_shooting_star():
    candle = (100, 111, 100, 101)
    assert "Inverted Hammer" in names(bars([candle], "down"))
    assert "Shooting Star" in names(bars([candle], "up"))


def test_engulfing():
    assert "Bullish Engulfing" in names(bars([(105, 106, 99, 100), (99, 108, 98, 107)]))
    assert "Bearish Engulfing" in names(bars([(100, 106, 99, 105), (106, 107, 97, 98)]))
    assert "Bullish Engulfing" not in names(bars([(105, 106, 99, 100), (101, 104, 100, 103)]))


def test_morning_and_evening_star():
    assert "Morning Star" in names(bars([(110, 111, 99, 100), (99, 100, 97, 98.5), (99, 108, 98.5, 107)]))
    assert "Evening Star" in names(bars([(100, 111, 99, 110), (111, 113, 110, 111.5), (111, 111.5, 102, 103)]))


def test_three_white_soldiers_and_black_crows():
    assert "Three White Soldiers" in names(bars([(100, 105.5, 99.5, 105), (103, 108.5, 102.5, 108), (106, 111.5, 105.5, 111)]))
    assert "Three Black Crows" in names(bars([(111, 111.5, 105.5, 106), (108, 108.5, 102.5, 103), (105, 105.5, 99.5, 100)]))


def test_scan_reports_bars_ago_and_lookback():
    df = bars([(100, 101, 99, 100.05)] * 13)  # every bar is a doji
    found = P.scan(df, lookback=10)
    assert len(found) == 10 and all(f["bars_ago"] < 10 for f in found)
    assert found and found[-1]["bars_ago"] == 0
