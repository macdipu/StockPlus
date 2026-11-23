"""What changed since the previous session, from one scanner row (see `universe_row.build_row`).

The row carries the previous bar's values for crossings, so no history needs storing: each rule compares
today's number with yesterday's and says so in a sentence. Pure and rule-based; `weight` orders the most
important change first.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

Tone = Literal["good", "bad", "info"]
MAX_CHANGES = 5


@dataclass(frozen=True, slots=True)
class Change:
    kind: str
    text: str
    tone: Tone
    weight: int


def _f(row: Mapping[str, Any], key: str) -> float | None:
    v = row.get(key)
    return float(v) if isinstance(v, int | float) and not isinstance(v, bool) and v == v else None


def _crossed(row: Mapping[str, Any], a: str, b: str) -> Literal["up", "down"] | None:
    """Did `a` cross above `b` (up) or below it (down) since the last bar? None if neither."""
    now_a, now_b = _f(row, a), _f(row, b)
    was_a, was_b = _f(row, f"{a}_prev"), _f(row, f"{b}_prev")
    if now_a is None or now_b is None or was_a is None or was_b is None:
        return None
    if now_a > now_b and was_a <= was_b:
        return "up"
    if now_a < now_b and was_a >= was_b:
        return "down"
    return None


def _num(v: float, d: int = 2) -> str:
    return f"{v:,.{d}f}"


def describe_changes(row: Mapping[str, Any]) -> list[Change]:
    """The most important changes first, at most five. Empty when nothing notable happened."""
    out: list[Change] = []
    add = out.append
    close = _f(row, "close")

    for key, name, weight in (("sma200", "200-day", 5), ("sma50", "50-day", 4), ("ema21", "21-day", 2)):
        c = _crossed(row, "close", key)
        level = _f(row, key)
        if c and level is not None and close is not None:
            if c == "up":
                add(
                    Change(
                        f"cross_{key}",
                        f"Closed back above its {name} average ({_num(level)}).",
                        "good",
                        weight,
                    )
                )
            else:
                add(
                    Change(f"cross_{key}", f"Closed below its {name} average ({_num(level)}).", "bad", weight)
                )
    ema = _crossed(row, "ema9", "ema21")
    if ema == "up":
        add(
            Change(
                "ema_cross",
                "The 9-day average crossed above the 21-day: short-term momentum turned up.",
                "good",
                3,
            )
        )
    elif ema == "down":
        add(
            Change(
                "ema_cross",
                "The 9-day average crossed below the 21-day: short-term momentum turned down.",
                "bad",
                3,
            )
        )
    macd = _crossed(row, "macd", "macd_signal")
    if macd == "up":
        add(Change("macd_cross", "MACD crossed above its signal line: momentum is improving.", "good", 3))
    elif macd == "down":
        add(Change("macd_cross", "MACD crossed below its signal line: momentum is weakening.", "bad", 3))

    rsi, was = _f(row, "rsi14"), _f(row, "rsi14_prev")
    if rsi is not None and was is not None:
        if rsi < 30 <= was:
            add(Change("rsi_oversold", f"RSI fell into oversold territory ({_num(rsi, 0)}).", "bad", 3))
        elif rsi >= 30 > was:
            add(Change("rsi_oversold", f"RSI climbed out of oversold territory ({_num(rsi, 0)}).", "good", 3))
        elif rsi > 70 >= was:
            add(
                Change(
                    "rsi_overbought",
                    f"RSI rose into overbought territory ({_num(rsi, 0)}): a pullback is likely.",
                    "info",
                    3,
                )
            )
        elif rsi <= 70 < was:
            add(
                Change(
                    "rsi_overbought", f"RSI came back from overbought territory ({_num(rsi, 0)}).", "info", 2
                )
            )
        elif rsi > 50 >= was:
            add(
                Change(
                    "rsi_mid", f"RSI moved above 50 ({_num(rsi, 0)}): buyers have the upper hand.", "good", 2
                )
            )
        elif rsi <= 50 < was:
            add(
                Change(
                    "rsi_mid", f"RSI moved below 50 ({_num(rsi, 0)}): sellers have the upper hand.", "bad", 2
                )
            )

    if row.get("new_52w_high"):
        add(Change("high_52w", "Hit a new 52-week high.", "good", 5))
    elif row.get("breakout_20d"):
        add(Change("breakout_20d", "Closed above its 20-day high: a breakout.", "good", 3))
    elif row.get("breakdown_20d"):
        add(Change("breakdown_20d", "Closed below its 20-day low: a breakdown.", "bad", 3))

    pct = _f(row, "change_pct")
    if pct is not None and abs(pct) >= 4:
        add(
            Change(
                "big_move",
                f"{'Up' if pct > 0 else 'Down'} {_num(abs(pct), 1)}% in the session.",
                "good" if pct > 0 else "bad",
                3,
            )
        )
    gap_up, gap_down = _f(row, "gap_up_pct"), _f(row, "gap_down_pct")
    if gap_up is not None and gap_up >= 2:
        add(Change("gap_up", f"Opened {_num(gap_up, 1)}% above the previous session's high.", "good", 2))
    elif gap_down is not None and gap_down <= -2:
        add(
            Change(
                "gap_down", f"Opened {_num(abs(gap_down), 1)}% below the previous session's low.", "bad", 2
            )
        )

    vol = _f(row, "vol_ratio")
    if vol is not None and vol >= 2:
        tone: Tone = "good" if (pct or 0) > 0 else "bad" if (pct or 0) < 0 else "info"
        add(Change("volume_spike", f"Heavy volume: {_num(vol, 1)}× its 20-day average.", tone, 2))

    label = row.get("vpa")
    bias = row.get("vpa_bias")
    if isinstance(label, str) and label:
        add(
            Change(
                "vpa",
                f"Volume-price signal: {label}.",
                "good" if bias == "bullish" else "bad" if bias == "bearish" else "info",
                2,
            )
        )
    patterns = row.get("patterns")
    if isinstance(patterns, list) and patterns:
        tone = (
            "good"
            if row.get("bullish_pattern") and not row.get("bearish_pattern")
            else "bad"
            if row.get("bearish_pattern") and not row.get("bullish_pattern")
            else "info"
        )
        add(
            Change(
                "pattern",
                f"Candle pattern on the last session: {', '.join(str(p) for p in patterns)}.",
                tone,
                1,
            )
        )

    out.sort(key=lambda c: -c.weight)  # stable: equal weights keep the order the rules ran in
    return out[:MAX_CHANGES]
