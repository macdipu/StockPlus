"""Market picks: rank every instrument for value for money and for how good an entry point it is right now.

Two scores, each 0–100, built from columns the universe already has:

value  cheapness and quality: P/E, price/book, dividend yield, Graham number gap, sponsor holding
entry  timing: RSI band, trend (vs SMA 200 / SMA 50), place in the 52-week range, MACD momentum, the latest
       candle pattern, volume-price read and the setup score

pick score = 0.55 × value + 0.45 × entry. Each row is put in one bucket:

buy_zone       good value, good timing, nothing bearish on the last candle
wait_pullback  good value but overbought or stretched above its averages
watch          worth watching; one side (value or timing) is not there yet
avoid          loss-making, or a bearish candle while below the 50-day average
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import pandas as pd

from dse.features.scanner.domain.rules import UniverseFilter

VALUE_WEIGHT = 0.55
BUCKETS = ("buy_zone", "wait_pullback", "watch", "avoid")
BUCKET_LABELS = {
    "buy_zone": "Buy zone now",
    "wait_pullback": "Wait for a pullback",
    "watch": "Watch",
    "avoid": "Avoid for now",
}


def _v(row: pd.Series, key: str) -> float | None:
    v = row.get(key)
    if v is None or isinstance(v, bool):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if pd.isna(f) else f


def value_score(row: pd.Series) -> tuple[int, list[str]]:
    s, why = 0, []
    pe, pb, dy = _v(row, "pe"), _v(row, "pb"), _v(row, "dividend_yield_pct")
    gg, sponsor = _v(row, "graham_gap_pct"), _v(row, "sponsor_pct")
    if pe is not None and pe > 0:
        pts = 30 if pe < 8 else 24 if pe < 12 else 15 if pe < 16 else 6 if pe < 22 else 0
        s += pts
        if pts >= 24:
            why.append(f"cheap at P/E {pe:.1f}")
    if pb is not None and pb > 0:
        pts = 20 if pb < 1 else 14 if pb < 1.5 else 8 if pb < 2.5 else 2 if pb < 4 else 0
        s += pts
        if pb < 1:
            why.append(f"below book value (P/B {pb:.2f})")
    if dy is not None and dy > 0:
        pts = 25 if dy >= 7 else 19 if dy >= 5 else 12 if dy >= 3 else 5
        s += pts
        if dy >= 5:
            why.append(f"{dy:.1f}% dividend yield")
    if gg is not None:
        s += 15 if gg >= 30 else 10 if gg >= 0 else 0
        if gg >= 30:
            why.append(f"{gg:.0f}% under its Graham number")
    if sponsor is not None and sponsor >= 30:
        s += 10
    return min(s, 100), why


def entry_score(row: pd.Series) -> tuple[int, list[str], list[str]]:
    """(score, reasons for, reasons against)."""
    s, good, bad = 0, [], []
    c = _v(row, "ltp") or _v(row, "close")
    rsi, sma200, sma50, sma20 = _v(row, "rsi14"), _v(row, "sma200"), _v(row, "sma50"), _v(row, "sma20")
    if rsi is not None:
        if 35 <= rsi <= 58:
            s += 20
            good.append(f"RSI {rsi:.0f}, room to rise")
        elif 28 <= rsi < 35 or 58 < rsi <= 65:
            s += 12
        elif rsi < 28:
            s += 6
            bad.append(f"RSI {rsi:.0f}, still falling hard")
        else:
            bad.append(f"RSI {rsi:.0f}, overbought")
    if c and sma200:
        if c > sma200:
            s += 15
            good.append("above its 200-day average (uptrend)")
        else:
            bad.append("below its 200-day average")
    if c and sma50 and c >= sma50 * 0.97:
        s += 10
    lo, hi = _v(row, "low_52w"), _v(row, "high_52w")
    if c and lo and hi and hi > lo:
        pos = (c - lo) / (hi - lo) * 100
        s += 12 if pos <= 40 else 6 if pos <= 70 else 0
        if pos <= 25:
            good.append("near its 52-week low")
        elif pos >= 90:
            bad.append("near its 52-week high")
    mh, mh_prev = _v(row, "macd_hist"), _v(row, "macd_hist_prev")
    macd, sig = _v(row, "macd"), _v(row, "macd_signal")
    if mh is not None and macd is not None and sig is not None and macd > sig:
        s += 10
        good.append("MACD above its signal line")
    elif mh is not None and mh_prev is not None and mh > mh_prev:
        s += 6
    if bool(row.get("bullish_pattern")):
        s += 15
        pats = row.get("patterns")
        names = ", ".join(pats) if isinstance(pats, list | tuple) and pats else "bullish candle"
        good.append(f"bullish candle: {names}")
    if bool(row.get("bearish_pattern")):
        s -= 15
        bad.append("bearish candle on the last session")
    bias = row.get("vpa_bias")
    if bias == "bullish":
        s += 8
        good.append(f"volume read: {row.get('vpa')}")
    elif bias == "bearish":
        s -= 8
        bad.append(f"volume read: {row.get('vpa')}")
    setup = _v(row, "setup_score")
    if setup is not None:
        s += int(setup * 2)
    if c and sma20 and c > sma20 * 1.08:
        bad.append(f"{(c / sma20 - 1) * 100:.0f}% above its 20-day average, stretched")
    return max(0, min(s, 100)), good, bad


def bucket(row: pd.Series, value: int, entry: int) -> str:
    pe, rsi = _v(row, "pe"), _v(row, "rsi14")
    c, sma20, sma50 = _v(row, "ltp") or _v(row, "close"), _v(row, "sma20"), _v(row, "sma50")
    bearish = bool(row.get("bearish_pattern"))
    if pe is None or (bearish and c and sma50 and c < sma50):
        return "avoid"
    stretched = (rsi is not None and rsi >= 68) or bool(c and sma20 and c > sma20 * 1.08)
    if value >= 45 and stretched:
        return "wait_pullback"
    if value >= 45 and entry >= 55 and not bearish:
        return "buy_zone"
    return "watch"


@dataclass(frozen=True, slots=True)
class PickFilter:
    universe: UniverseFilter
    buckets: tuple[str, ...] = ()
    min_value_score: int = 0
    limit: int = 50


PICK_COLUMNS = (
    "symbol",
    "name",
    "sector",
    "category",
    "ltp",
    "change_pct",
    "pe",
    "pb",
    "dividend_yield_pct",
    "rsi14",
    "setup_score",
    "patterns",
    "vpa",
    "low_52w",
    "high_52w",
    "value_mn",
)


def rank(u: pd.DataFrame, flt: PickFilter, apply_limit: bool = True) -> list[dict[str, Any]]:
    """Scored and bucketed rows, best pick first."""
    if u.empty:
        return []
    frame = u[flt.universe.mask(u)]
    out: list[dict[str, Any]] = []
    for _, row in frame.iterrows():
        v, v_why = value_score(row)
        e, e_good, e_bad = entry_score(row)
        b = bucket(row, v, e)
        if flt.buckets and b not in flt.buckets:
            continue
        if v < flt.min_value_score:
            continue
        rec: dict[str, Any] = {k: _clean(row.get(k)) for k in PICK_COLUMNS}
        rec.update(
            pick_score=round(VALUE_WEIGHT * v + (1 - VALUE_WEIGHT) * e, 1),
            value_score=v,
            entry_score=e,
            bucket=b,
            bucket_label=BUCKET_LABELS[b],
            reasons=[*v_why, *e_good],
            warnings=e_bad,
        )
        out.append(rec)
    order = {b: i for i, b in enumerate(BUCKETS)}
    out.sort(key=lambda r: (order[r["bucket"]], -r["pick_score"], str(r["symbol"])))
    return out[: flt.limit] if apply_limit else out


def _clean(v: Any) -> Any:
    if isinstance(v, list | tuple):
        return [str(x) for x in v]
    if v is None or isinstance(v, bool | str):
        return v
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    return None if pd.isna(f) else round(f, 4)


def sector_names(u: pd.DataFrame) -> Sequence[str]:
    if u.empty or "sector" not in u:
        return []
    return sorted({str(s) for s in u["sector"].dropna().unique()})
