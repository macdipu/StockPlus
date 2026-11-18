"""Watchlist alerts: turn one instrument's analysis into short messages worth a notification. Pure.

Input is plain data (the analysis JSON shape and the dossier's events), so this module never imports another
feature. Each alert has a stable `key` (symbol, kind, session day) so a client notifies once per event.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any

BULLISH_WORDS = {
    "Hammer": "a hammer",
    "Bullish Engulfing": "a bullish engulfing candle",
    "Morning Star": "a morning star",
    "Inverted Hammer": "an inverted hammer",
    "Three White Soldiers": "three white soldiers",
    "Bullish Marubozu": "a strong green candle",
}
BEARISH_WORDS = {
    "Shooting Star": "a shooting star",
    "Bearish Engulfing": "a bearish engulfing candle",
    "Evening Star": "an evening star",
    "Three Black Crows": "three black crows",
    "Bearish Marubozu": "a strong red candle",
}


@dataclass(frozen=True, slots=True)
class Alert:
    symbol: str
    kind: str  # buy_zone | stop | target | breakout | bearish_candle
    severity: str  # info | action | warning
    key: str
    price: float
    message: str


def _n(v: Any) -> str:
    f = float(v)
    return (
        f"{f:.0f}"
        if f >= 100 and f == int(f)
        else f"{f:.1f}"
        if f >= 100
        else f"{f:.2f}".rstrip("0").rstrip(".")
    )


def _dividend_note(
    events: Mapping[str, Any] | None, dividends: Sequence[Mapping[str, Any]], today: date
) -> str:
    if not events:
        return ""
    rd = events.get("record_date")
    try:
        record = date.fromisoformat(str(rd)[:10]) if rd else None
    except ValueError:
        record = None
    if record is None or record < today:
        return ""
    pct = events.get("declared_dividend_pct")
    cash = float(pct) / 10 if pct else (float(dividends[0]["cash_per_share"]) if dividends else 0.0)
    if cash <= 0:
        return ""
    return f" Tk {_n(cash)} dividend still ahead (record {record.day} {record.strftime('%b')})."


def alerts_for(
    a: Mapping[str, Any],
    events: Mapping[str, Any] | None,
    dividends: Sequence[Mapping[str, Any]],
    today: date,
) -> list[Alert]:
    sym = str(a["symbol"])
    st = a.get("candle_story") or {}
    price = float(a["price"]["ltp"])
    day = str(a["price"]["last_bar_date"])
    live = bool(a["price"].get("live_bar"))
    ann = {x["kind"]: x for x in st.get("annotations", []) if x["kind"] in ("entry", "stop")}
    targets = [x for x in st.get("annotations", []) if x["kind"] == "target"]
    watch = [
        x for x in st.get("annotations", []) if x["kind"] == "watch" and float(x["price"]) > price * 0.98
    ]
    entry, stop = ann.get("entry"), ann.get("stop")
    target = targets[0] if targets else None
    plan = ""
    if stop and target:
        plan = f" Stop {_n(stop['price'])}, target {_n(target['price'])}."
    todays = [p for p in (a.get("candles") or {}).get("patterns", []) if p.get("bars_ago") == 0]
    bull = next((BULLISH_WORDS[p["pattern"]] for p in todays if p["pattern"] in BULLISH_WORDS), None)
    bear = next((BEARISH_WORDS[p["pattern"]] for p in todays if p["pattern"] in BEARISH_WORDS), None)
    verb = "forming" if live else "on the last candle"
    div = _dividend_note(events, dividends, today)
    out: list[Alert] = []

    def add(kind: str, severity: str, msg: str) -> None:
        out.append(Alert(sym, kind, severity, f"{sym}:{kind}:{day}", price, msg))

    where = st.get("where")
    if where == "below_stop" and stop:
        add("stop", "warning", f"{sym} {_n(price)} is below the stop {_n(stop['price'])}: exit signal.")
    elif target and price >= float(target["price"]):
        add(
            "target",
            "action",
            f"{sym} {_n(price)} reached the target {_n(target['price'])}: consider taking profit.",
        )
    elif where == "inside_buy_zone" and entry:
        zone = f"({_n(entry['price_to'])}–{_n(entry['price'])})"  # noqa: RUF001
        candle = f" with {bull} {verb}." if bull else "."
        add("buy_zone", "action", f"{sym} {_n(price)} in buy zone {zone}{candle}{div}{plan}")
    for w in watch[:1]:
        lvl = float(w["price"])
        if price > lvl and "breakout" in str(w.get("label", "")).lower():
            add(
                "breakout",
                "action",
                f"{sym} {_n(price)} broke above {_n(lvl)}: breakout, needs a close above it on volume.{plan}",
            )
    if bear:
        add("bearish_candle", "warning", f"{sym} {_n(price)}: {bear} {verb}. Be careful with new buys.")
    return out
