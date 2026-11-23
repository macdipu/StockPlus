"""Replay the Picks score over past sessions and measure what each bucket went on to do (research).

For every sampled session D the universe is rebuilt from bars before D only, scored and bucketed exactly as
the live page does, and each share's outcome is read from the bars that followed. Pure CPU: the caller loads
history and runs this in a thread or a script.
"""

from collections.abc import Sequence
from datetime import date
from typing import Any

import pandas as pd

from dse.features.analysis.application.facade import UniverseInput, build_universe_rows
from dse.features.scanner.domain import picks
from dse.features.scanner.domain.backtest_stats import PriceBook, PriceSeries, summarise
from dse.features.scanner.domain.picks import PickFilter
from dse.features.scanner.domain.rules import UniverseFilter
from dse.features.scanner.domain.universe import rows_to_frame

NOTES = (
    "Fundamentals (P/E, EPS, dividend yield, sponsor holding) are today's values used at every past date, so "
    "the value score and the pick score look further ahead than a real investor could. The entry score uses "
    "only prices known on the day, so it is the cleaner test.",
    "Only shares listed today are included (survivorship), and only about a year of history exists, so the "
    "sample is small and overlapping windows are not independent.",
    "Returns are open of the signal day to the close the chosen number of sessions later, before fees and slippage, versus the "
    "average share scored that day.",
)


def price_book(history: Sequence[UniverseInput]) -> PriceBook:
    return PriceBook(
        {
            h.symbol: PriceSeries(
                tuple(b.day for b in h.bars),
                tuple(b.open for b in h.bars),
                tuple(b.close for b in h.bars),
                tuple(b.volume for b in h.bars),
            )
            for h in history
            if h.bars
        }
    )


def replay_days(
    history: Sequence[UniverseInput], horizons: Sequence[int], step: int, min_history: int
) -> list[date]:
    """Sessions to replay: far enough in that indicators exist, far enough from the end that outcomes do."""
    calendar = sorted({b.day for h in history for b in h.bars})
    last = len(calendar) - 1 - max(horizons)
    return [calendar[i] for i in range(min_history, last + 1, step)]


def run_backtest(
    history: Sequence[UniverseInput],
    *,
    horizons: Sequence[int] = (5, 10, 20),
    step: int = 3,
    min_history: int = 120,
    min_turnover_mn: float = 1.0,
) -> dict[str, Any]:
    prices = price_book(history)
    flt = PickFilter(UniverseFilter(asset_types=("EQ",)), limit=100_000)  # liquidity is checked from the bars
    records: list[dict[str, Any]] = []
    days = replay_days(history, horizons, step, min_history)
    for day in days:
        frame = rows_to_frame(build_universe_rows(history, live=False, session_day=day).rows)
        for r in picks.rank(frame, flt, apply_limit=False):
            liquidity = prices.avg_turnover_mn(str(r["symbol"]), day)
            if liquidity is None or liquidity < min_turnover_mn:
                continue  # too thin to have traded
            rets = {f"ret_{h}": prices.forward_return(str(r["symbol"]), day, h) for h in horizons}
            if all(v is None for v in rets.values()):
                continue
            records.append(
                {
                    "date": day,
                    "symbol": r["symbol"],
                    "bucket": r["bucket"],
                    "pick_score": r["pick_score"],
                    "value_score": r["value_score"],
                    "entry_score": r["entry_score"],
                    **rets,
                }
            )
    frame = pd.DataFrame(records)
    result = summarise(frame, horizons)
    result.update(
        {
            "horizons": list(horizons),
            "step": step,
            "min_history": min_history,
            "min_avg_turnover_mn": min_turnover_mn,
            "replayed_days": len(days),
            "notes": list(NOTES),
        }
    )
    return result
