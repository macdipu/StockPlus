"""Assemble one instrument's analysis (legacy `service.build`). Pure, synchronous: CPU only, no I/O."""

from typing import Any

import numpy as np
import pandas as pd

from dse.features.analysis.application.inputs import AnalysisInput
from dse.features.analysis.domain import (
    candle_story,
    indicators,
    patterns,
    setup_score,
    signals,
    summary,
    valuation,
)
from dse.features.analysis.domain.frames import merge_live, to_frame
from dse.shared_kernel.errors import ValidationFailedError

DISCLAIMER = "For research only, not investment advice."
MIN_BARS = 60
INDICATOR_COLS = (
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
CHART_COLS = (
    "open",
    "high",
    "low",
    "close",
    "volume",
    "sma20",
    "sma50",
    "sma200",
    "ema9",
    "ema21",
    "bb_upper",
    "bb_lower",
    "vol_avg20",
)


def day(ts: Any) -> str:
    return str(pd.Timestamp(ts).strftime("%Y-%m-%d"))


def num(v: Any) -> float | None:
    return None if v is None or pd.isna(v) else float(v)


def clean(o: Any) -> Any:
    """JSON-safe: NaN/inf → None, numpy scalars → Python, floats rounded to 4 dp, timestamps → dates."""
    if isinstance(o, dict):
        return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, list | tuple):
        return [clean(v) for v in o]
    if isinstance(o, np.bool_):
        return bool(o)
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, float | np.floating):
        return None if np.isnan(o) or np.isinf(o) else round(float(o), 4)
    if isinstance(o, pd.Timestamp):
        return o.strftime("%Y-%m-%d")
    return o


def build(inp: AnalysisInput) -> tuple[dict[str, Any], pd.DataFrame]:
    """Return (knowledge dict, indicator DataFrame)."""
    df = merge_live(to_frame(inp.bars), inp.live) if inp.bars else pd.DataFrame()
    if len(df) < MIN_BARS:
        raise ValidationFailedError(f"{inp.symbol}: only {len(df)} daily bars — too few to analyse.")
    fund = inp.fundamentals
    cat = inp.category
    ind = indicators.add_indicators(df)
    pats = patterns.scan(ind)
    # DSE's own 52-week figures win over the ones computed from bars
    sr = indicators.support_resistance(ind, hi52=fund.get("week_high_52"), lo52=fund.get("week_low_52"))
    crit = setup_score.criteria_frame(ind, cat)
    setup = setup_score.score(ind, cat, sr, crit)
    sig = signals.signal(ind, setup, pats, cat)
    prob = signals.profit_probability(ind, crit, setup)

    last = ind.iloc[-1]
    ltp = fund.get("ltp") or float(last["close"])
    prev_close = fund.get("prev_close") or float(ind["close"].iloc[-2])
    live = bool(inp.live and inp.live.session_day.isoformat() == day(ind.index[-1]))
    k: dict[str, Any] = {
        "symbol": inp.symbol,
        "name": inp.name,
        "as_of": inp.as_of,
        "disclaimer": DISCLAIMER,
        "price": {
            "ltp": ltp,
            "prev_close": prev_close,
            "change": ltp - prev_close if prev_close else None,
            "change_pct": (ltp / prev_close - 1) * 100 if prev_close else None,
            "open": float(last["open"]),
            "high": float(last["high"]),
            "low": float(last["low"]),
            "volume": float(last["volume"]),
            "trades": num(last.get("trades")),
            "value_mn": inp.value_mn,
            "live_bar": live,
            "market_open": inp.market_open,
            "last_bar_date": day(ind.index[-1]),
            "first_bar_date": day(ind.index[0]),
            "bars_available": len(ind),
        },
        "fundamentals": fund,
        "indicators": {c: num(last[c]) for c in INDICATOR_COLS},
        "candles": {
            "last_candle": patterns.describe_last_candle(ind),
            "patterns": pats,
            "thresholds": patterns.T,
            "last_sessions": [
                {
                    "date": day(d),
                    **{c: float(r[c]) for c in ("open", "high", "low", "close", "volume")},
                }
                for d, r in ind.iloc[-10:].iterrows()
            ],
        },
        "levels": sr,
        "trend": indicators.trend(ind),
        "valuation": valuation.value(fund),
        "setup": setup,
        "signal": sig,
        "probability": prob,
        "news": list(inp.news),
    }
    k["candle_story"] = candle_story.story(ind, pats, sr, setup["plan"], live=live)
    k["summary"] = summary.summarize(k)
    return k, ind


def technical_bars(ind: pd.DataFrame, limit: int | None = None) -> list[dict[str, Any]]:
    d = ind if not limit else ind.iloc[-limit:]
    return [{"date": day(idx), **{c: num(r[c]) for c in CHART_COLS}} for idx, r in d.iterrows()]
