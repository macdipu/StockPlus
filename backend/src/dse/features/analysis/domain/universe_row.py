"""One scannable row per instrument: indicators, previous-bar values (for crosses), 52-week stats, returns,
candle patterns, VPA label, setup score and valuation ratios. Ported from legacy `scanner._row`.

Column names follow the project convention (snake_case): `asset_type` replaces legacy `assetType`.
"""

import math
from collections.abc import Mapping
from typing import Any

import pandas as pd

from dse.features.analysis.domain import indicators, patterns, setup_score, vpa

CROSS_FIELDS = ("close", "sma20", "sma50", "sma200", "ema9", "ema21", "macd", "macd_signal", "rsi14")
INDICATOR_FIELDS = (
    "sma20",
    "sma50",
    "sma200",
    "ema9",
    "ema21",
    "rsi14",
    "macd",
    "macd_signal",
    "macd_hist",
    "bb_upper",
    "bb_mid",
    "bb_lower",
    "atr14",
    "vol_avg20",
    "vol_ratio",
)
MIN_BARS = 30


def _opt(v: Any) -> float | None:
    return None if v is None or pd.isna(v) else float(v)


def build_row(
    sym: str, df: pd.DataFrame, fund: Mapping[str, Any], quote: Mapping[str, Any] | None
) -> dict[str, Any]:
    """`quote` keys: ltp, ycp, percent, sector, category, asset_type, value_mn, trades (all optional).
    `fund` may also carry `asset_type` (from the instrument record)."""
    q: Mapping[str, Any] = quote or {}
    ind = indicators.add_indicators(df)
    last, prev = ind.iloc[-1], ind.iloc[-2]
    c = float(last["close"])
    yr = ind[ind.index > ind.index[-1] - pd.Timedelta(days=365)]
    hi52 = max(float(fund.get("week_high_52") or yr["high"].max()), float(last["high"]))
    lo52 = min(float(fund.get("week_low_52") or yr["low"].min()), float(last["low"]))
    prev_hi52 = float(yr["high"].iloc[:-1].max()) if len(yr) > 1 else hi52
    bbw = (ind["bb_upper"] - ind["bb_lower"]) / ind["bb_mid"]
    bbw_tail = bbw.iloc[-120:].dropna()
    found = patterns.detect_at(ind, len(ind) - 1)
    pats = [n for n, _ in found]
    dirs = {d for _, d in found}
    v = vpa.classify(ind).iloc[-1]
    rng7 = (ind["high"] - ind["low"]).iloc[-7:]
    crit = setup_score.criteria_frame(ind.iloc[-3:], fund.get("category")).iloc[-1]

    def ret(days: int) -> float | None:
        past = ind["close"][ind.index <= ind.index[-1] - pd.Timedelta(days=days)]
        return (c / float(past.iloc[-1]) - 1) * 100 if len(past) else None

    eps, nav, ltp = fund.get("eps_ttm"), fund.get("nav"), q.get("ltp") or c
    graham = math.sqrt(22.5 * eps * nav) if eps and nav and eps > 0 and nav > 0 else None
    row: dict[str, Any] = {
        "symbol": sym,
        "name": fund.get("name"),
        "sector": q.get("sector") or fund.get("sector"),
        "category": q.get("category") or fund.get("category"),
        # the instrument record is the fallback: without it a quote-less row (not traded today, or the
        # last-close view, which ignores quotes) would silently drop out of every asset-type-filtered scan
        "asset_type": q.get("asset_type") or fund.get("asset_type"),
        "ltp": ltp,
        "ycp": q.get("ycp") or float(prev["close"]),
        "change_pct": q.get("percent") if quote else (c / float(prev["close"]) - 1) * 100,
        "open": float(last["open"]),
        "high": float(last["high"]),
        "low": float(last["low"]),
        "close": c,
        "volume": float(last["volume"]),
        "value_mn": q.get("value_mn"),
        "trades": q.get("trades"),
        "bar_date": ind.index[-1].strftime("%Y-%m-%d"),
        "bars": len(ind),
        "high_52w": hi52,
        "low_52w": lo52,
        "pct_from_52w_high": (c / hi52 - 1) * 100,
        "pct_from_52w_low": (c / lo52 - 1) * 100,
        "new_52w_high": float(last["high"]) >= prev_hi52,
        "breakout_20d": c > float(ind["high"].iloc[-21:-1].max()),
        "breakdown_20d": c < float(ind["low"].iloc[-21:-1].min()),
        "gap_up_pct": (float(last["open"]) / float(prev["high"]) - 1) * 100,
        "gap_down_pct": (float(last["open"]) / float(prev["low"]) - 1) * 100,
        "nr7": float(rng7.iloc[-1]) <= float(rng7.min()) and len(rng7) == 7,
        "inside_bar": float(last["high"]) <= float(prev["high"]) and float(last["low"]) >= float(prev["low"]),
        "bb_width": float(bbw.iloc[-1]) if pd.notna(bbw.iloc[-1]) else None,
        "bb_width_pctile": float((bbw_tail <= bbw_tail.iloc[-1]).mean() * 100)
        if len(bbw_tail) > 20
        else None,
        "atr_pct": float(last["atr14"]) / c * 100 if pd.notna(last["atr14"]) else None,
        "ret_1w": ret(7),
        "ret_1m": ret(30),
        "ret_3m": ret(91),
        "ret_6m": ret(182),
        "ret_1y": ret(365),
        "patterns": pats,
        "bullish_pattern": "bullish" in dirs,
        "bearish_pattern": "bearish" in dirs,
        "vpa": v["vpa"],
        "vpa_bias": v["vpa_bias"],
        "vol_rel": _opt(v["vol_rel"]),
        "setup_score": int(sum(bool(crit[k]) for k in setup_score.CRITERIA)),
        "eps_ttm": eps,
        "nav": nav,
        "pe": ltp / eps if eps and eps > 0 else None,
        "pb": ltp / nav if nav and nav > 0 else None,
        "dividend_yield_pct": fund.get("dividend_yield_pct"),
        "sponsor_pct": fund.get("sponsor_pct"),
        "free_float_pct": fund.get("free_float_pct"),
        "market_cap": fund.get("market_cap"),
        "graham": graham,
        "graham_gap_pct": (graham / ltp - 1) * 100 if graham else None,
    }
    for col in INDICATOR_FIELDS:
        row[col] = _opt(last[col])
    for col in CROSS_FIELDS:
        row[f"{col}_prev"] = _opt(prev[col])
    return row
