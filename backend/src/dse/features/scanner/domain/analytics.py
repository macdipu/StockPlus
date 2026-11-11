"""Market analytics over the universe frame: sector table, P/E summary, 52-week position, record shaping."""

import math
from collections.abc import Sequence
from typing import Any

import pandas as pd


def _safe(v: Any) -> Any:
    if isinstance(v, float):
        return None if math.isnan(v) or math.isinf(v) else round(v, 4)
    return v


def to_records(df: pd.DataFrame, columns: Sequence[str]) -> list[dict[str, Any]]:
    """JSON-safe rows: NaN/inf → None, floats rounded to 4 dp, missing columns ignored."""
    cols = [c for c in columns if c in df.columns]
    records: list[dict[Any, Any]] = df[cols].to_dict("records")
    return [{str(k): _safe(v) for k, v in rec.items()} for rec in records]


def sectors(u: pd.DataFrame) -> list[dict[str, Any]]:
    g = u.groupby("sector")
    out = pd.DataFrame(
        {
            "instruments": g.size(),
            "advanced": g["change_pct"].apply(lambda s: int((s > 0).sum())),
            "declined": g["change_pct"].apply(lambda s: int((s < 0).sum())),
            "avg_change_pct": g["change_pct"].mean(),
            "turnover_mn": g["value_mn"].sum(),
            "median_pe": g["pe"].median(),
            "avg_rsi": g["rsi14"].mean(),
            "ret_1m": g["ret_1m"].median(),
        }
    ).reset_index()
    tot = out["turnover_mn"].sum() or 1
    out["turnover_share_pct"] = out["turnover_mn"] / tot * 100
    return to_records(out.sort_values("turnover_mn", ascending=False), list(out.columns))


def pe_summary(u: pd.DataFrame) -> dict[str, Any]:
    d = u[(u["pe"].notna()) & (u["pe"] > 0) & u["market_cap"].notna()].copy()
    d["earnings"] = d["market_cap"] / d["pe"]

    def agg(x: pd.DataFrame) -> dict[str, Any]:
        return {
            "instruments": len(x),
            "median_pe": float(x["pe"].median()) if len(x) else None,
            "weighted_pe": float(x["market_cap"].sum() / x["earnings"].sum()) if len(x) else None,
        }

    return {
        "market": agg(d),
        "by_sector": {k: agg(g) for k, g in d.groupby("sector")},
        "by_category": {k: agg(g) for k, g in d.groupby("category")},
        "note": "P/E uses TTM EPS (positive earnings only); weighted = Σ market cap / Σ earnings.",
    }


def range_52w(u: pd.DataFrame, near: str = "high", limit: int = 100) -> pd.DataFrame:
    """Equities ranked by their position in the 52-week range (0 = at the low, 100 = at the high)."""
    d = u[u["asset_type"] == "EQ"].copy()
    d["range_position_pct"] = (d["ltp"] - d["low_52w"]) / (d["high_52w"] - d["low_52w"]) * 100
    return d.sort_values("range_position_pct", ascending=near == "low").head(limit)
