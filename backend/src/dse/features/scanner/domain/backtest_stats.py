"""Statistics for replaying the Picks score over past sessions. Pure pandas: no I/O, tested on small frames.

A *signal* is a share's bucket and scores as they were computed from bars before day D. The *outcome* is the
return from D's open to the close `h` sessions later, compared with the average share that day."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any

import pandas as pd

BUCKETS = ("buy_zone", "wait_pullback", "watch", "avoid")


@dataclass(frozen=True, slots=True)
class PriceSeries:
    days: tuple[date, ...]
    open: tuple[float, ...]
    close: tuple[float, ...]
    volume: tuple[float, ...]


class PriceBook:
    """Per-symbol daily prices, to read the outcome of a signal."""

    def __init__(self, series: dict[str, PriceSeries]) -> None:
        self._s = series
        self._index = {sym: {d: i for i, d in enumerate(s.days)} for sym, s in series.items()}

    def forward_return(self, symbol: str, day: date, horizon: int) -> float | None:
        """Open of `day` to the close `horizon` sessions later; None when the share did not trade that day,
        has no price, or the history ends first."""
        s = self._s.get(symbol)
        i = self._index.get(symbol, {}).get(day)
        if s is None or i is None or i + horizon >= len(s.days):
            return None
        entry, exit_ = s.open[i], s.close[i + horizon]
        if not entry or entry <= 0 or not exit_ or exit_ <= 0 or s.volume[i] <= 0:
            return None
        return exit_ / entry - 1

    def avg_turnover_mn(self, symbol: str, day: date, window: int = 20) -> float | None:
        """Average traded value (BDT million) over the `window` sessions before `day`: the liquidity a trader
        could see at the time. None without enough history."""
        s = self._s.get(symbol)
        i = self._index.get(symbol, {}).get(day)
        if s is None or i is None or i < window:
            return None
        values = [s.close[k] * s.volume[k] for k in range(i - window, i)]
        return sum(values) / window / 1_000_000


def add_excess(records: pd.DataFrame, horizons: Sequence[int]) -> pd.DataFrame:
    """Add `ex_{h}`: each share's return minus the average of all shares scored that day."""
    out = records.copy()
    for h in horizons:
        out[f"ex_{h}"] = out[f"ret_{h}"] - out.groupby("date")[f"ret_{h}"].transform("mean")
    return out


def _stats(frame: pd.DataFrame, h: int) -> dict[str, Any]:
    r = frame[f"ret_{h}"].dropna()
    e = frame[f"ex_{h}"].dropna()
    if r.empty:
        return {"n": 0}
    return {
        "n": len(r),
        "mean_pct": round(float(r.mean()) * 100, 2),
        "median_pct": round(float(r.median()) * 100, 2),
        "hit_rate_pct": round(float((r > 0).mean()) * 100, 1),
        "excess_pct": round(float(e.mean()) * 100, 2),
        "beat_market_pct": round(float((e > 0).mean()) * 100, 1),
    }


def _ic(records: pd.DataFrame, score: str, h: int) -> dict[str, Any]:
    """Rank correlation between a score and the forward return, per day, then averaged: positive means
    higher scores were followed by higher returns."""
    per_day = []
    for _, g in records.groupby("date"):
        g = g.dropna(subset=[score, f"ret_{h}"])
        if len(g) >= 20 and g[score].nunique() > 1:
            per_day.append(g[score].rank().corr(g[f"ret_{h}"].rank()))  # Spearman = Pearson on ranks
    s = pd.Series(per_day, dtype=float).dropna()
    if s.empty:
        return {"days": 0}
    return {
        "days": len(s),
        "mean_ic": round(float(s.mean()), 3),
        "share_of_days_positive_pct": round(float((s > 0).mean()) * 100, 1),
    }


def summarise(records: pd.DataFrame, horizons: Sequence[int]) -> dict[str, Any]:
    """Per bucket, per score quintile and rank-correlation results for each horizon."""
    if records.empty:
        return {"rows": 0}
    records = add_excess(records, horizons)
    out: dict[str, Any] = {
        "rows": len(records),
        "days": int(records["date"].nunique()),
        "shares": int(records["symbol"].nunique()),
        "from": str(records["date"].min()),
        "to": str(records["date"].max()),
        "by_bucket": {},
        "by_pick_quintile": {},
        "by_entry_quintile": {},
        "rank_correlation": {},
    }
    for h in horizons:
        out["by_bucket"][h] = {b: _stats(records[records["bucket"] == b], h) for b in BUCKETS}
        out["by_bucket"][h]["all"] = _stats(records, h)
        for score, key in (("pick_score", "by_pick_quintile"), ("entry_score", "by_entry_quintile")):
            ranked = records.assign(q=records.groupby("date")[score].transform(_quintile))
            out[key][h] = {_label(q): _stats(g, h) for q, g in ranked.groupby("q") if pd.notna(q)}
        out["rank_correlation"][h] = {
            s: _ic(records, s, h) for s in ("pick_score", "value_score", "entry_score")
        }
    return out


def _label(q: Any) -> str:
    return f"Q{int(q)}"


def _quintile(s: pd.Series) -> pd.Series:
    """1 (lowest) to 5 (highest) within one day; equal scores share a quintile by rank order."""
    if len(s) < 10:
        return pd.Series(float("nan"), index=s.index)
    return pd.qcut(s.rank(method="first"), 5, labels=False) + 1
