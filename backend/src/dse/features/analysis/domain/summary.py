"""Plain-language summary composer. Moved out of legacy `report.py` (problem P5: rendering owned domain text).

Input is the analysis "knowledge" dict built by `AnalyzeInstrument`; output is a list of sentences.
"""

import math
from typing import Any


def fmt(v: float | None, spec: str = "{:.2f}", none: str = "n/a") -> str:
    return none if v is None or (isinstance(v, float) and math.isnan(v)) else spec.format(v)


def summarize(k: dict[str, Any]) -> list[str]:
    t, ind, sr, sig = k["trend"], k["indicators"], k["levels"], k["signal"]
    ch = t["changes"]
    lines = [k["candles"]["last_candle"]]
    pats = [p for p in k["candles"]["patterns"] if p["bars_ago"] <= 2]
    lines.append(
        "Recent patterns: " + ", ".join(f"{p['pattern']} ({p['date']})" for p in pats) + "."
        if pats
        else "No textbook candle pattern in the last 3 sessions."
    )
    above = [n for n, v in t["vs_ma"].items() if v and v["pct"] > 0]
    below = [n for n, v in t["vs_ma"].items() if v and v["pct"] < 0]
    lines.append(
        f"Price is above {', '.join(above) or 'none'} and below {', '.join(below) or 'none'} "
        "of its moving averages."
    )
    lines.append("Change: " + ", ".join(f"{p} {fmt(v, '{:+.1f}%')}" for p, v in ch.items()) + ".")
    rsi = ind.get("rsi14")
    if rsi is not None:
        zone = "overbought" if rsi > 70 else "oversold" if rsi < 30 else "bullish" if rsi >= 50 else "bearish"
        lines.append(
            f"RSI {rsi:.0f} ({zone}); MACD is {'above' if ind['macd'] > ind['macd_signal'] else 'below'} "
            f"its signal line; volume is {ind['vol_ratio']:.1f}× its 20-day average."
        )
    lines.append(
        f"Nearest support {fmt(sr['below'][0] if sr['below'] else None)}, "
        f"nearest resistance {fmt(sr['above'][0] if sr['above'] else None)} "
        f"(52-week range {sr['low_52w']:.2f}–{sr['high_52w']:.2f})."
    )
    prob = k["probability"]
    pr = prob["similar_setups"]
    if pr["p_target_first"] is not None:
        lines.append(
            f"Signal: {sig['action']}. Historically, {pr['wins']}/{pr['n']} similar setups "
            f"({pr['p_target_first']:.0%}) reached the target before the stop within "
            f"{prob['horizon_sessions']} sessions "
            f"(target +{prob['target_pct']:.1f}% vs stop −{prob['stop_pct']:.1f}%; "
            f"all-days baseline {fmt(prob['all_days_baseline']['p_target_first'], '{:.0%}')})"
            + ("." if prob["reliable"] else " (too few samples to trust).")
        )
    else:
        lines.append(f"Signal: {sig['action']}. No comparable past setups to estimate a probability.")
    return lines
