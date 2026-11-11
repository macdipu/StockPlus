"""Short-term long setup: 6-point score, entry / stop / target and risk-reward.
Ported unchanged from legacy `setup_score.py`.
"""

from typing import Any

import pandas as pd

from dse.features.analysis.domain import patterns

MIN_RR = 1.5
STOP_ATR = 1.5  # fallback stop distance
STOP_BUFFER_ATR = 0.25  # stop placed this far below the support level
MAX_SUPPORT_ATR = 3.0  # supports further than this are ignored for the stop
ENTRY_ZONE_ATR = 0.5  # entry zone = [close - 0.5 ATR, close]
FALLBACK_TARGET_R = 2.0  # no resistance overhead -> project 2R

CRITERIA = {
    "above_ema21": "Close above EMA 21",
    "above_sma50": "Close above SMA 50",
    "rsi_50_70": "RSI(14) between 50 and 70",
    "volume_surge": "Volume ≥ 1.5× 20-day average",
    "bullish_candle": "Bullish candle pattern in the last 2 sessions",
    "not_z": "Not Z category",
}


def bullish_flags(df: pd.DataFrame) -> pd.Series:
    """True on bars where a bullish pattern completed."""
    return pd.Series(
        [any(d == "bullish" for _, d in patterns.detect_at(df, i)) for i in range(len(df))], index=df.index
    )


def criteria_frame(ind: pd.DataFrame, category: str | None, bull: pd.Series | None = None) -> pd.DataFrame:
    """One boolean column per criterion, for every bar (used by the score and the backtest)."""
    bull = bullish_flags(ind) if bull is None else bull
    c = ind["close"]
    return pd.DataFrame(
        {
            "above_ema21": c > ind["ema21"],
            "above_sma50": c > ind["sma50"],
            "rsi_50_70": ind["rsi14"].between(50, 70),
            "volume_surge": ind["vol_ratio"] >= 1.5,
            "bullish_candle": bull | bull.shift(1, fill_value=False),
            "not_z": pd.Series((category or "").upper() != "Z", index=ind.index),
        },
        index=ind.index,
    )


def trade_plan(ind: pd.DataFrame, sr: dict[str, Any]) -> dict[str, Any]:
    last = ind.iloc[-1]
    entry, a = float(last["close"]), float(last["atr14"])
    zone = (round(entry - ENTRY_ZONE_ATR * a, 2), round(entry, 2))

    supports = [s for s in sr["below"] if s < zone[0] and entry - s <= MAX_SUPPORT_ATR * a]
    if supports:
        stop, stop_basis = (
            supports[0] - STOP_BUFFER_ATR * a,
            f"support {supports[0]:.2f} − {STOP_BUFFER_ATR} ATR",
        )
    else:
        stop, stop_basis = entry - STOP_ATR * a, f"entry − {STOP_ATR} × ATR ({a:.2f})"

    entry, stop = round(entry, 2), round(stop, 2)
    risk = entry - stop
    above = [r for r in sr["above"] if r > entry]
    if above:
        target, target_basis = above[0], "next resistance"
    else:
        target = entry + FALLBACK_TARGET_R * risk
        target_basis = f"no resistance overhead — {FALLBACK_TARGET_R}R projection"
    target = round(target, 2)
    rr = (target - entry) / risk if risk > 0 else None
    return {
        "entry": round(entry, 2),
        "entry_zone": zone,
        "stop": round(stop, 2),
        "stop_basis": stop_basis,
        "target": round(target, 2),
        "target_basis": target_basis,
        "atr": round(a, 2),
        "risk_pct": risk / entry * 100,
        "reward_pct": (target - entry) / entry * 100,
        "rr": rr,
        "rr_ok": rr is not None and rr >= MIN_RR,
    }


def score(
    ind: pd.DataFrame, category: str | None, sr: dict[str, Any], crit: pd.DataFrame | None = None
) -> dict[str, Any]:
    crit = criteria_frame(ind, category) if crit is None else crit
    row = crit.iloc[-1]
    checks = [{"key": k, "label": CRITERIA[k], "pass": bool(row[k])} for k in CRITERIA]
    plan = trade_plan(ind, sr)
    flags = []
    if not plan["rr_ok"]:
        flags.append(
            f"Risk/reward {plan['rr']:.2f} is below {MIN_RR}" if plan["rr"] else "Risk/reward undefined"
        )
    if (category or "").upper() == "Z":
        flags.append("Z category: settlement is slower and liquidity is poor")
    return {
        "score": sum(c["pass"] for c in checks),
        "max": len(checks),
        "checks": checks,
        "plan": plan,
        "flags": flags,
    }
