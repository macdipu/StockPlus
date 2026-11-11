"""Bulk row building for the scanner's universe. Pure CPU, no I/O; the caller runs it in a worker thread."""

import logging
from collections.abc import Iterable
from datetime import date

import pandas as pd

from dse.features.analysis.application.inputs import UniverseInput, UniverseRows
from dse.features.analysis.domain.frames import LiveBar, merge_live, to_frame
from dse.features.analysis.domain.universe_row import MIN_BARS, build_row

log = logging.getLogger("dse.analysis")


def build_universe_rows(
    items: Iterable[UniverseInput], *, live: bool, session_day: date | None
) -> UniverseRows:
    """One row per instrument. `live=False` evaluates the last completed session (pre-market scans): bars
    from `session_day` onward are dropped and quotes ignored. One bad series is reported, never fatal."""
    rows, errors = [], {}
    for item in items:
        try:
            if not item.bars:
                continue
            df = to_frame(item.bars)
            q = item.quote if live else None
            if live:
                bar = None
                if q is not None and session_day is not None:
                    bar = LiveBar(session_day, q.ltp, q.open, q.high, q.low, q.close, q.volume, q.trades)
                df = merge_live(df, bar)
            else:
                df = df[df.index < pd.Timestamp(session_day or date(2100, 1, 1))]
            if len(df) >= MIN_BARS:
                quote = None
                if q is not None:
                    quote = {
                        "ltp": q.ltp,
                        "ycp": q.ycp,
                        "percent": q.percent,
                        "sector": q.sector,
                        "category": q.category,
                        "asset_type": q.asset_type,
                        "value_mn": q.value_mn,
                        "trades": q.trades,
                    }
                rows.append(build_row(item.symbol, df, item.fundamentals, quote))
        except Exception as e:
            errors[item.symbol] = f"{type(e).__name__}: {e}"
    return UniverseRows(rows, errors)
