"""Technical indicators in plain pandas (no TA-Lib)."""
from __future__ import annotations

import numpy as np
import pandas as pd

import config as C


def sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n, min_periods=n).mean()


def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False, min_periods=n).mean()


def _wilder(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()


def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    d = close.diff()
    gain, loss = _wilder(d.clip(lower=0), n), _wilder(-d.clip(upper=0), n)
    rs = gain / loss
    out = 100 - 100 / (1 + rs)
    out[(loss == 0) & (gain > 0)] = 100.0
    out[(loss == 0) & (gain == 0)] = 50.0
    return out


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    line = ema(close, fast) - ema(close, slow)
    sig = line.ewm(span=signal, adjust=False, min_periods=signal).mean()
    return pd.DataFrame({"macd": line, "macd_signal": sig, "macd_hist": line - sig})


def bollinger(close: pd.Series, n: int = 20, k: float = 2.0) -> pd.DataFrame:
    mid = sma(close, n)
    sd = close.rolling(n, min_periods=n).std(ddof=0)
    return pd.DataFrame({"bb_mid": mid, "bb_upper": mid + k * sd, "bb_lower": mid - k * sd})


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    prev = df["close"].shift()
    tr = pd.concat([df["high"] - df["low"], (df["high"] - prev).abs(), (df["low"] - prev).abs()], axis=1).max(axis=1)
    return _wilder(tr, n)


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    c = out["close"]
    for n in (20, 50, 200):
        out[f"sma{n}"] = sma(c, n)
    for n in (9, 21):
        out[f"ema{n}"] = ema(c, n)
    out["rsi14"] = rsi(c, 14)
    out = out.join(macd(c)).join(bollinger(c))
    out["atr14"] = atr(out, 14)
    out["vol_avg20"] = sma(out["volume"], 20)
    out["vol_ratio"] = out["volume"] / out["vol_avg20"]
    return out


# --------------------------------------------------------------------------- support / resistance
def swing_points(df: pd.DataFrame, k: int = C.SWING_WINDOW) -> tuple[list[float], list[float]]:
    """Swing high = bar whose high is the strict max of the k bars on each side (same for lows)."""
    highs, lows = df["high"].to_numpy(), df["low"].to_numpy()
    sh, sl = [], []
    for i in range(k, len(df) - k):
        win_h, win_l = highs[i - k:i + k + 1], lows[i - k:i + k + 1]
        if highs[i] == win_h.max() and (win_h == highs[i]).sum() == 1:
            sh.append(float(highs[i]))
        if lows[i] == win_l.min() and (win_l == lows[i]).sum() == 1:
            sl.append(float(lows[i]))
    return sh, sl


def merge_levels(levels: list[float], pct: float = C.LEVEL_MERGE_PCT) -> list[float]:
    """Cluster levels lying within `pct`% of the running cluster mean."""
    out: list[list[float]] = []
    for lv in sorted(levels):
        if out and abs(lv - np.mean(out[-1])) / np.mean(out[-1]) * 100 <= pct:
            out[-1].append(lv)
        else:
            out.append([lv])
    return [round(float(np.mean(c)), 2) for c in out]


def support_resistance(df: pd.DataFrame, n: int = 3, hi52: float | None = None, lo52: float | None = None) -> dict:
    last_year = df[df.index > df.index[-1] - pd.Timedelta(days=365)]
    hi52 = max(float(hi52 or last_year["high"].max()), float(df["high"].iloc[-1]))
    lo52 = min(float(lo52 or last_year["low"].min()), float(df["low"].iloc[-1]))
    sh, sl = swing_points(df)
    levels = merge_levels(sh + sl + [hi52, lo52])
    price = float(df["close"].iloc[-1])
    above = [lv for lv in levels if lv > price][:n]
    below = sorted([lv for lv in levels if lv < price], reverse=True)[:n]
    return {"price": price, "high_52w": hi52, "low_52w": lo52, "above": above, "below": below}


# --------------------------------------------------------------------------- trend
def trend(df: pd.DataFrame) -> dict:
    c = df["close"]
    last = float(c.iloc[-1])
    changes = {}
    for label, days in (("1W", 7), ("1M", 30), ("3M", 91), ("1Y", 365)):
        past = c[c.index <= c.index[-1] - pd.Timedelta(days=days)]
        changes[label] = (last / float(past.iloc[-1]) - 1) * 100 if len(past) else None
    vs_ma = {}
    for col in ("ema9", "ema21", "sma20", "sma50", "sma200"):
        v = df[col].iloc[-1] if col in df else np.nan
        vs_ma[col.upper()] = None if pd.isna(v) else {"value": float(v), "pct": (last / float(v) - 1) * 100}
    return {"changes": changes, "vs_ma": vs_ma}
