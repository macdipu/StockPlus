"""Legacy-shaped `scanner` API on top of the new modules, so the legacy tests run with only their import line
changed. Pure translation (dict rules → Rule, legacy quote keys → QuoteInput); no logic of its own."""

from datetime import date
from typing import Any

import pandas as pd

from dse.features.analysis.application.facade import Bar, QuoteInput, UniverseInput, build_universe_rows
from dse.features.scanner.domain import analytics
from dse.features.scanner.domain.presets import PRESETS as _PRESETS
from dse.features.scanner.domain.rules import (
    Rule,
    ScanError,
    ScanSpec,
    Sort,
    UniverseFilter,
    compose,
    run_scan,
)
from dse.features.scanner.domain.universe import rows_to_frame

__all__ = ["PRESETS", "ScanError", "build_universe", "evaluate", "pe_summary", "run", "sectors"]


def _rule(d: dict[str, Any]) -> Rule:
    return Rule(d["field"], d["op"], d.get("value"), d.get("field2"))


PRESETS: dict[str, dict[str, Any]] = {
    k: {
        "name": p.name,
        "rules": [
            {
                k2: v
                for k2, v in (("field", r.field), ("op", r.op), ("value", r.value), ("field2", r.field2))
                if v is not None
            }
            for r in p.rules
        ],
        "match": p.match,
        "sort": {"field": p.sort.field, "desc": p.sort.desc},
        "premarket": p.premarket,
    }
    for k, p in _PRESETS.items()
}


def build_universe(
    bars: dict[str, pd.DataFrame],
    fundamentals: dict[str, dict[str, Any]],
    quotes: dict[str, dict[str, Any]],
    session: dict[str, Any],
    live: bool = True,
) -> pd.DataFrame:
    items = []
    for sym, df in bars.items():
        q = quotes.get(sym)
        quote = (
            QuoteInput(
                ltp=q.get("ltp"),
                ycp=q.get("ycp"),
                open=q.get("open"),
                high=q.get("high"),
                low=q.get("low"),
                close=q.get("close"),
                volume=float(q.get("volume") or 0),
                value_mn=q.get("value"),
                trades=q.get("trades"),
                percent=q.get("percent"),
                sector=q.get("sector"),
                category=q.get("category"),
                asset_type=q.get("assetType"),
            )
            if q
            else None
        )
        ohlcv = df[["open", "high", "low", "close", "volume"]].to_numpy(dtype=float)
        trades = df["trades"].to_numpy(dtype=float) if "trades" in df else [None] * len(df)
        series = tuple(
            Bar(ts.date(), float(o), float(h), float(lo), float(c), float(v), t)
            for ts, (o, h, lo, c, v), t in zip(df.index, ohlcv, trades, strict=True)
        )
        items.append(UniverseInput(sym, series, fundamentals.get(sym) or {}, quote))
    day = date.fromisoformat(session["date"]) if session.get("date") else None
    built = build_universe_rows(items, live=live, session_day=day)
    return rows_to_frame(built.rows, built.errors)


def _filter(d: dict[str, Any] | None) -> UniverseFilter:
    d = d or {}
    return UniverseFilter(
        tuple(d.get("sectors") or ()),
        tuple(d.get("categories") or ()),
        tuple(d.get("assetTypes") or ()),
        d.get("min_value_mn"),
    )


def evaluate(u: pd.DataFrame, rule: dict[str, Any]) -> pd.Series:
    return _rule(rule).mask(u)


def run(
    u: pd.DataFrame,
    rules: list[dict[str, Any]],
    match: str = "all",
    universe: dict[str, Any] | None = None,
    sort: dict[str, Any] | None = None,
    limit: int = 100,
) -> pd.DataFrame:
    spec = ScanSpec(
        tuple(_rule(r) for r in rules),
        match,  # type: ignore[arg-type]
        _filter(universe),
        Sort(sort["field"], sort.get("desc", True)) if sort else None,
        limit,
    )
    return run_scan(u, spec)


def sectors(u: pd.DataFrame) -> list[dict[str, Any]]:
    return analytics.sectors(u)


def pe_summary(u: pd.DataFrame) -> dict[str, Any]:
    return analytics.pe_summary(u)


_ = compose  # re-exported for completeness of the legacy surface
