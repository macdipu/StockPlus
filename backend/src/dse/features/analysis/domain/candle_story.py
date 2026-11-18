"""Plain-language candle analysis and the chart annotations that go with it.

Reads the indicator frame, the detected patterns, the support/resistance levels and the trade plan, and says
in words what the last few candles show and where to enter, exit, take profit and what to watch. Pure: no I/O.

Price levels:
  buy zone      nearest support within MAX_SUPPORT_ATR below the close: [support, support + ZONE_ATR];
                with no such support, the trade plan's own zone [close - 0.5 ATR, close]
  stop          the trade plan's stop (below support, or entry - 1.5 ATR)
  targets       the trade plan's target, then the next resistance above it
  watch         breakout trigger = the first resistance above the close;
                breakdown trigger = the nearest support below the close
"""

from collections.abc import Mapping, Sequence
from typing import Any

import pandas as pd

from dse.features.analysis.domain import vpa

RECENT = 5
ZONE_ATR = 1.0
MAX_SUPPORT_ATR = 3.0
HIGH_VOL = 1.5
LOW_VOL = 0.7

PATTERN_MEANING: dict[str, str] = {
    "Hammer": "sellers pushed the price down but buyers drove it back up, a possible bottom",
    "Inverted Hammer": "buyers tried to lift the price after a fall, an early sign the selling is tiring",
    "Shooting Star": "buyers pushed up but sellers slammed it back down, a possible top",
    "Doji": "buyers and sellers ended level, indecision; the next candle decides",
    "Bullish Engulfing": "a green body swallowed the prior red one, buyers took control",
    "Bearish Engulfing": "a red body swallowed the prior green one, sellers took control",
    "Morning Star": "a three-candle bottom reversal: fall, pause, strong recovery",
    "Evening Star": "a three-candle top reversal: rise, pause, sharp drop",
    "Three White Soldiers": "three strong green candles in a row, a steady uptrend",
    "Three Black Crows": "three strong red candles in a row, steady selling",
    "Bullish Marubozu": "a full green body with almost no wicks, buyers in charge all session",
    "Bearish Marubozu": "a full red body with almost no wicks, sellers in charge all session",
}


def _f(v: Any) -> float | None:
    return None if v is None or pd.isna(v) else float(v)


def _shape(body: float, upper: float, lower: float) -> str:
    if body <= 0.1:
        return "doji (tiny body)"
    if lower >= 0.5 and upper <= 0.2:
        return "long lower wick"
    if upper >= 0.5 and lower <= 0.2:
        return "long upper wick"
    if body >= 0.7:
        return "long body"
    if body <= 0.3:
        return "small body"
    return "medium body"


def _describe(colour: str, shape: str, close_pos: float, vol: float | None) -> tuple[str, str]:
    """(bias, one sentence) for a single candle."""
    vol_txt = "" if vol is None else f" on {vol:.1f}x average volume"
    if shape == "doji (tiny body)":
        return "neutral", f"Doji{vol_txt}: indecision, neither side won the session."
    if shape == "long lower wick":
        bias = "bullish"
        return bias, f"{colour.title()} candle with a long lower wick{vol_txt}: dip buyers stepped in."
    if shape == "long upper wick":
        return (
            "bearish",
            f"{colour.title()} candle with a long upper wick{vol_txt}: sellers rejected the high.",
        )
    if colour == "green":
        strength = "strong" if shape == "long body" and close_pos >= 0.7 else "modest"
        heavy = vol is not None and vol >= HIGH_VOL
        tail = " Heavy volume backs the move." if heavy and strength == "strong" else ""
        light = " Light volume, so conviction is weak." if vol is not None and vol < LOW_VOL else ""
        return (
            "bullish",
            f"{strength.title()} green candle closing {close_pos:.0%} up its range{vol_txt}.{tail}{light}",
        )
    if colour == "red":
        strength = "strong" if shape == "long body" and close_pos <= 0.3 else "modest"
        heavy = vol is not None and vol >= HIGH_VOL
        tail = " Heavy volume, real selling." if heavy and strength == "strong" else ""
        return (
            "bearish",
            f"{strength.title()} red candle closing {close_pos:.0%} up its range{vol_txt}.{tail}",
        )
    return "neutral", f"Flat candle{vol_txt}."


def recent_candles(
    ind: pd.DataFrame, pats: Sequence[Mapping[str, Any]], n: int = RECENT
) -> list[dict[str, Any]]:
    labels = vpa.classify(ind)
    by_date: dict[str, list[str]] = {}
    for p in pats:
        by_date.setdefault(str(p["date"]), []).append(str(p["pattern"]))
    out: list[dict[str, Any]] = []
    for i in range(max(0, len(ind) - n), len(ind)):
        r = ind.iloc[i]
        d = pd.Timestamp(ind.index[i]).strftime("%Y-%m-%d")
        o, h, lo, c = float(r["open"]), float(r["high"]), float(r["low"]), float(r["close"])
        rng = h - lo
        if rng <= 0:
            out.append(
                {
                    "date": d,
                    "colour": "flat",
                    "shape": "no range",
                    "bias": "neutral",
                    "body_pct": 0.0,
                    "upper_wick_pct": 0.0,
                    "lower_wick_pct": 0.0,
                    "close_pos_pct": None,
                    "vol_ratio": _f(r.get("vol_ratio")),
                    "vpa": None,
                    "patterns": by_date.get(d, []),
                    "text": "No range: the price did not move (no trades or a locked price).",
                }
            )
            continue
        body, upper, lower = abs(c - o) / rng, (h - max(o, c)) / rng, (min(o, c) - lo) / rng
        close_pos = (c - lo) / rng
        colour = "green" if c > o else "red" if c < o else "flat"
        avg = _f(r.get("vol_avg20"))
        vol = float(r["volume"]) / avg if avg else None
        shape = _shape(body, upper, lower)
        bias, text = _describe(colour, shape, close_pos, vol)
        names = by_date.get(d, [])
        for name in names:
            meaning = PATTERN_MEANING.get(name)
            if meaning:
                text += f" {name}: {meaning}."
        v = labels.iloc[i]
        if isinstance(v.get("vpa"), str) and v["vpa"]:
            text += f" Volume read: {v['vpa']}."
        out.append(
            {
                "date": d,
                "colour": colour,
                "shape": shape,
                "bias": bias,
                "body_pct": round(body * 100, 1),
                "upper_wick_pct": round(upper * 100, 1),
                "lower_wick_pct": round(lower * 100, 1),
                "close_pos_pct": round(close_pos * 100, 1),
                "vol_ratio": None if vol is None else round(vol, 2),
                "vpa": v.get("vpa") if isinstance(v.get("vpa"), str) else None,
                "patterns": names,
                "text": text,
            }
        )
    return out


def _r(v: float) -> float:
    return round(v, 2)


def story(
    ind: pd.DataFrame,
    pats: Sequence[Mapping[str, Any]],
    levels: Mapping[str, Any],
    plan: Mapping[str, Any],
    live: bool = False,
) -> dict[str, Any]:
    """Candle narrative + entry/exit/target/watch levels with the words that go on the chart."""
    last = ind.iloc[-1]
    close = float(last["close"])
    atr = _f(last.get("atr14")) or float(plan.get("atr") or 0) or close * 0.02
    below = [float(x) for x in levels.get("below") or []]
    above = [float(x) for x in levels.get("above") or []]

    support = next((s for s in below if close - s <= MAX_SUPPORT_ATR * atr), None)
    if support is not None:
        zone = (_r(support), _r(min(support + ZONE_ATR * atr, close)))
        zone_basis = f"support {support:.2f} to {ZONE_ATR} ATR above it"
    else:
        lo, hi = plan.get("entry_zone") or (close - ZONE_ATR * atr, close)
        zone = (_r(float(lo)), _r(float(hi)))
        zone_basis = "no support nearby: close minus half an ATR"
    stop = _r(float(plan["stop"]))
    stop_basis = str(plan.get("stop_basis", "stop"))
    if stop >= zone[0]:  # the stop must sit under the buy zone, or one tick of noise stops you out
        stop, stop_basis = _r(zone[0] - 0.25 * atr), f"buy zone low {zone[0]:.2f} − 0.25 ATR"
    target = _r(float(plan["target"]))
    target2 = next((r for r in above if r > target * 1.005), None)
    breakout = above[0] if above else None
    breakdown = support if support is not None else (below[0] if below else None)

    rsi = _f(last.get("rsi14"))
    if close < stop:
        where, headline = (
            "below_stop",
            f"Price {close:.2f} is under the stop {stop:.2f}: the setup has failed.",
        )
    elif close < zone[0]:
        where, headline = (
            "below_buy_zone",
            f"Price {close:.2f} has slipped under the buy zone; wait for it to recover {zone[0]:.2f}.",
        )
    elif close <= zone[1]:
        where, headline = (
            "inside_buy_zone",
            f"Price {close:.2f} is inside the buy zone {zone[0]:.2f}–{zone[1]:.2f}.",
        )
    else:
        gap = (close / zone[1] - 1) * 100
        where, headline = (
            "above_buy_zone",
            f"Price {close:.2f} is {gap:.1f}% above the buy zone; buying here means chasing.",
        )
    if rsi is not None and rsi >= 70:
        headline += f" RSI {rsi:.0f} is overbought, so a pullback is likely before a better entry."
    elif rsi is not None and rsi <= 30:
        headline += f" RSI {rsi:.0f} is oversold; look for a bullish candle before buying."

    recent = recent_candles(ind, pats)
    if live and recent:
        recent[-1]["text"] = "Today, still forming: " + recent[-1]["text"]
        recent[-1]["live"] = True
    last_c = recent[-1] if recent else None
    confirm = ""
    if last_c and where == "inside_buy_zone":
        confirm = (
            " The last candle is bullish, which supports an entry."
            if last_c["bias"] == "bullish"
            else " Wait for a green candle that closes in the upper half of its range."
        )

    annotations: list[dict[str, Any]] = [
        {
            "kind": "entry",
            "price": zone[1],
            "price_to": zone[0],
            "label": f"BUY ZONE {zone[0]:.2f}–{zone[1]:.2f}",
            "text": f"Enter between {zone[0]:.2f} and {zone[1]:.2f} ({zone_basis}).{confirm}",
        },
        {
            "kind": "stop",
            "price": stop,
            "label": f"EXIT below {stop:.2f}",
            "text": f"Sell if a session closes below {stop:.2f} ({stop_basis}).",
        },
        {
            "kind": "target",
            "price": target,
            "label": f"TAKE PROFIT {target:.2f}",
            "text": f"Take profit near {target:.2f} ({plan.get('target_basis', 'target')}).",
        },
    ]
    if target2 is not None:
        annotations.append(
            {
                "kind": "target",
                "price": _r(target2),
                "label": f"TARGET 2 {target2:.2f}",
                "text": f"If {target:.2f} breaks on volume, the next resistance is {target2:.2f}.",
            }
        )
    if breakout is not None and abs(breakout - target) > 0.005 * close:
        annotations.append(
            {
                "kind": "watch",
                "price": _r(breakout),
                "label": f"WATCH breakout {breakout:.2f}",
                "text": f"A close above {breakout:.2f} on above-average volume is a breakout.",
            }
        )
    elif breakout is not None:
        annotations.append(
            {
                "kind": "watch",
                "price": _r(breakout),
                "label": f"WATCH {breakout:.2f}",
                "text": f"{breakout:.2f} is both the first resistance and the target: "
                "a close above it on volume is a breakout.",
            }
        )
    if breakdown is not None and breakdown > stop:
        annotations.append(
            {
                "kind": "watch",
                "price": _r(breakdown),
                "label": f"WATCH support {breakdown:.2f}",
                "text": f"Support at {breakdown:.2f}: a close below it weakens the setup "
                "before the stop is hit.",
            }
        )

    plan_steps = [
        {"step": "Where to enter", "text": annotations[0]["text"]},
        {"step": "Where to exit (stop loss)", "text": annotations[1]["text"]},
        {
            "step": "Where to take profit",
            "text": annotations[2]["text"]
            + (f" Second target {target2:.2f}." if target2 is not None else ""),
        },
        {
            "step": "What to watch",
            "text": " ".join(a["text"] for a in annotations if a["kind"] == "watch")
            or "No nearby levels to watch.",
        },
    ]
    markers = [
        {
            "date": p["date"],
            "bias": p["direction"],
            "text": p["pattern"],
            "meaning": PATTERN_MEANING.get(str(p["pattern"]), ""),
        }
        for p in pats
    ]
    return {
        "where": where,
        "headline": headline,
        "recent": recent,
        "annotations": annotations,
        "plan": plan_steps,
        "markers": markers,
    }
