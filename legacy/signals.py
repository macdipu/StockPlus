"""BUY / SELL / HOLD signal and an empirical short-term profit probability.

The probability is a historical base rate for THIS stock: of past sessions whose setup score was at least
today's, how often did price reach today's target % before today's stop % within HORIZON sessions?
It is a frequency from overlapping samples, not a forecast.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

HORIZON = 10
MIN_SAMPLES = 15


def signal(ind: pd.DataFrame, setup: dict, pats: list[dict], category: str | None) -> dict:
    last = ind.iloc[-1]
    c = last["close"]
    recent = [p for p in pats if p["bars_ago"] <= 1]
    bull, bear = [], []

    def vote(cond, side, text):
        if bool(cond):
            side.append(text)

    for col in ("ema21", "sma50", "sma200"):
        if pd.notna(last[col]):
            vote(c > last[col], bull, f"close above {col.upper()}")
            vote(c < last[col], bear, f"close below {col.upper()}")
    vote(last["ema9"] > last["ema21"], bull, "EMA 9 above EMA 21")
    vote(last["ema9"] < last["ema21"], bear, "EMA 9 below EMA 21")
    vote(last["macd"] > last["macd_signal"], bull, "MACD above signal")
    vote(last["macd"] < last["macd_signal"], bear, "MACD below signal")
    vote(50 <= last["rsi14"] <= 70, bull, f"RSI {last['rsi14']:.0f} in bullish zone")
    vote(last["rsi14"] < 45, bear, f"RSI {last['rsi14']:.0f} weak")
    vote(last["rsi14"] > 75, bear, f"RSI {last['rsi14']:.0f} overbought")
    vote(last["vol_ratio"] >= 1.5 and c > last["open"], bull, f"up day on {last['vol_ratio']:.1f}× volume")
    vote(last["vol_ratio"] >= 1.5 and c < last["open"], bear, f"down day on {last['vol_ratio']:.1f}× volume")
    for p in recent:
        vote(p["direction"] == "bullish", bull, f"{p['pattern']} ({p['date']})")
        vote(p["direction"] == "bearish", bear, f"{p['pattern']} ({p['date']})")

    net = len(bull) - len(bear)
    plan = setup["plan"]
    if (category or "").upper() == "Z":
        action = "AVOID"
    elif setup["score"] >= 5 and plan["rr_ok"]:
        action = "STRONG BUY"
    elif net >= 3 and plan["rr_ok"]:
        action = "BUY"
    elif net <= -5:
        action = "STRONG SELL"
    elif net <= -3:
        action = "SELL"
    else:
        action = "HOLD"
    return {"action": action, "net_votes": net, "bullish_reasons": bull, "bearish_reasons": bear,
            "rule": "STRONG BUY: score≥5 & R/R≥1.5 · BUY: net≥3 & R/R≥1.5 · SELL: net≤−3 · "
                    "STRONG SELL: net≤−5 · Z category: AVOID · else HOLD"}


def _hit_target_first(df: pd.DataFrame, i: int, tgt_pct: float, stop_pct: float, horizon: int) -> bool | None:
    entry = df["close"].iloc[i]
    up, dn = entry * (1 + tgt_pct / 100), entry * (1 - stop_pct / 100)
    for j in range(i + 1, min(i + 1 + horizon, len(df))):
        hit_dn, hit_up = df["low"].iloc[j] <= dn, df["high"].iloc[j] >= up
        if hit_dn:            # both on the same bar counts as a loss (conservative)
            return False
        if hit_up:
            return True
    return None               # neither within horizon


def profit_probability(ind: pd.DataFrame, crit: pd.DataFrame, setup: dict, horizon: int = HORIZON) -> dict:
    plan = setup["plan"]
    tgt, stp = plan["reward_pct"], plan["risk_pct"]
    scores = crit.sum(axis=1)
    valid = ind[["ema21", "sma50", "rsi14", "atr14", "vol_ratio"]].notna().all(axis=1)
    idx = [i for i in range(len(ind) - horizon) if valid.iloc[i]]

    def stats(rows):
        res = [_hit_target_first(ind, i, tgt, stp, horizon) for i in rows]
        wins, losses, open_ = res.count(True), res.count(False), res.count(None)
        fwd = [(ind["close"].iloc[i + horizon] / ind["close"].iloc[i] - 1) * 100 for i in rows]
        n = len(rows)
        p = wins / n if n else None
        return {"n": n, "wins": wins, "losses": losses, "unresolved": open_, "p_target_first": p,
                "avg_fwd_return_pct": float(np.mean(fwd)) if fwd else None,
                "pct_positive_fwd": float(np.mean([f > 0 for f in fwd]) * 100) if fwd else None,
                "expectancy_pct": (p * tgt - (losses / n) * stp) if n else None}

    similar = [i for i in idx if scores.iloc[i] >= setup["score"]]
    out = {"horizon_sessions": horizon, "target_pct": tgt, "stop_pct": stp,
           "similar_setups": stats(similar), "all_days_baseline": stats(idx),
           "method": (f"Of past sessions with setup score ≥ {setup['score']}/{setup['max']}, share that touched "
                      f"+{tgt:.1f}% before −{stp:.1f}% within {horizon} sessions. Same-bar hits count as losses. "
                      "Samples overlap; small n is unreliable. Historical frequency, not a forecast.")}
    n = out["similar_setups"]["n"]
    out["reliable"] = n >= MIN_SAMPLES
    if not out["reliable"]:
        out["warning"] = f"Only {n} similar sessions (< {MIN_SAMPLES}); treat the probability as noise."
    return out
