"""Shared building blocks for indicators. All vectorised (pandas/numpy), all causal."""

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view


def sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n, min_periods=n).mean()


def _seeded_ewm(s: pd.Series, n: int, alpha: float) -> pd.Series:
    """Exponential smoothing whose first value is the simple average of the first n valid values."""
    v = s.to_numpy(dtype="float64")
    valid = np.flatnonzero(~np.isnan(v))
    x = np.full(len(v), np.nan)
    if len(valid) and valid[0] + n - 1 < len(v):
        seed = int(valid[0]) + n - 1
        x[seed] = v[valid[0] : seed + 1].mean()
        x[seed + 1 :] = v[seed + 1 :]
    return pd.Series(x, index=s.index).ewm(alpha=alpha, adjust=False).mean()


def ema(s: pd.Series, n: int) -> pd.Series:
    """Exponential MA, alpha = 2/(n+1), seeded with the simple average of the first n values."""
    return _seeded_ewm(s, n, 2.0 / (n + 1))


def rma(s: pd.Series, n: int) -> pd.Series:
    """Wilder's smoothing (RMA/SMMA), alpha = 1/n, seeded with the first n values' simple average."""
    return _seeded_ewm(s, n, 1.0 / n)


def window_dot(s: pd.Series, w: np.ndarray) -> pd.Series:
    """Rolling weighted sum: out[t] = sum_i w[i] * s[t-n+1+i]; w[-1] is the current bar. NaN until n bars."""
    n = len(w)
    v = s.to_numpy(dtype="float64")
    out = np.full(len(v), np.nan)
    if len(v) >= n:
        out[n - 1 :] = sliding_window_view(v, n) @ w
    return pd.Series(out, index=s.index)


def wma(s: pd.Series, n: int) -> pd.Series:
    w = np.arange(1, n + 1, dtype="float64")
    return window_dot(s, w / w.sum())


def linreg(s: pd.Series, n: int, offset: int = 0) -> pd.Series:
    """Least-squares line through the last n values, evaluated at the current bar (or `offset` bars back)."""
    t = np.arange(n, dtype="float64")
    tm = (n - 1) / 2.0
    sxx = float(((t - tm) ** 2).sum())
    w = 1.0 / n + (t - tm) * ((n - 1 - offset) - tm) / sxx
    return window_dot(s, w)


def stdev(s: pd.Series, n: int) -> pd.Series:
    """Population standard deviation (ddof=0), the charting-platform convention for Bollinger Bands."""
    return s.rolling(n, min_periods=n).std(ddof=0)


def mean_abs_dev(s: pd.Series, n: int) -> pd.Series:
    """Rolling mean absolute deviation from the window mean."""
    v = s.to_numpy(dtype="float64")
    out = np.full(len(v), np.nan)
    if len(v) >= n:
        win = sliding_window_view(v, n)
        out[n - 1 :] = np.abs(win - win.mean(axis=1, keepdims=True)).mean(axis=1)
    return pd.Series(out, index=s.index)


def bars_since_extreme(s: pd.Series, window: int, *, highest_: bool) -> pd.Series:
    """Bars since the highest (or lowest) value in the last `window` bars (0 = this bar). Ties: latest."""
    v = s.to_numpy(dtype="float64")
    out = np.full(len(v), np.nan)
    if len(v) >= window:
        win = sliding_window_view(v, window)[:, ::-1]  # column 0 is the current bar
        idx = win.argmax(axis=1) if highest_ else win.argmin(axis=1)
        res = idx.astype("float64")
        res[np.isnan(win).any(axis=1)] = np.nan
        out[window - 1 :] = res
    return pd.Series(out, index=s.index)


def percent_rank(s: pd.Series, n: int) -> pd.Series:
    """Percent of the previous n values that are <= the current one (0..100)."""
    v = s.to_numpy(dtype="float64")
    out = np.full(len(v), np.nan)
    if len(v) >= n + 1:
        win = sliding_window_view(v, n + 1)
        out[n:] = (win[:, :-1] <= win[:, -1:]).sum(axis=1) * 100.0 / n
        out[n:][np.isnan(win).any(axis=1)] = np.nan
    return pd.Series(out, index=s.index)


def safe_div(a: pd.Series, b: pd.Series) -> pd.Series:
    """a / b with NaN (never inf) where b is zero."""
    return a / b.where(b != 0)


def true_range(df: pd.DataFrame) -> pd.Series:
    prev = df["close"].shift(1)
    tr = pd.concat([df["high"] - df["low"], (df["high"] - prev).abs(), (df["low"] - prev).abs()], axis=1).max(
        axis=1
    )
    tr.iloc[0] = df["high"].iloc[0] - df["low"].iloc[0]  # no previous close on the first bar
    return tr


def atr(df: pd.DataFrame, n: int) -> pd.Series:
    return rma(true_range(df), n)


def highest(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n, min_periods=n).max()


def lowest(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n, min_periods=n).min()


def rsi(s: pd.Series, n: int) -> pd.Series:
    """Wilder's RSI: 100 * avg gain / (avg gain + avg loss), both smoothed with Wilder's RMA."""
    d = s.diff()
    up = rma(d.clip(lower=0.0), n)
    dn = rma((-d).clip(lower=0.0), n)
    total = up + dn
    return (100.0 * up / total.where(total != 0)).where(total != 0, 100.0).where(up.notna() & dn.notna())


def median_price(df: pd.DataFrame) -> pd.Series:
    return (df["high"] + df["low"]) / 2.0


def typical_price(df: pd.DataFrame) -> pd.Series:
    return (df["high"] + df["low"] + df["close"]) / 3.0


def frame(index: pd.Index, **cols: pd.Series | np.ndarray) -> pd.DataFrame:
    """A result frame with the given column order, aligned to `index`. Infinities become NaN."""
    out = pd.DataFrame(
        {k: pd.Series(v, index=index) if isinstance(v, np.ndarray) else v for k, v in cols.items()},
        index=index,
    )
    return out.replace([np.inf, -np.inf], np.nan)
