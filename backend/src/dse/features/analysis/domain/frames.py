"""Building the OHLCV frame the analytics run on: stored daily bars + today's live bar."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

import pandas as pd


@dataclass(frozen=True, slots=True)
class Bar:
    day: date
    open: float
    high: float
    low: float
    close: float
    volume: float
    trades: float | None = None


@dataclass(frozen=True, slots=True)
class LiveBar:
    """Today's partial bar from the live snapshot; `close` is the official close once the session ends."""

    session_day: date
    ltp: float | None
    open: float | None
    high: float | None
    low: float | None
    close: float | None
    volume: float
    trades: float | None


def to_frame(bars: Sequence[Bar]) -> pd.DataFrame:
    df = pd.DataFrame(
        [
            {
                "date": b.day,
                "open": b.open,
                "high": b.high,
                "low": b.low,
                "close": b.close,
                "volume": b.volume,
                "trades": b.trades,
            }
            for b in bars
        ]
    )
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()
    return df[~df.index.duplicated(keep="last")].astype(float)


def merge_live(df: pd.DataFrame, live: LiveBar | None) -> pd.DataFrame:
    """Append (or refresh) today's bar from the live snapshot. No-op if it has not traded today."""
    if live is None or live.volume <= 0 or not live.ltp:
        return df
    day = pd.Timestamp(live.session_day)
    if len(df) and day < df.index[-1]:
        return df
    last = live.close or live.ltp
    bar = {
        "open": live.open or last,
        "high": live.high or last,
        "low": live.low or last,
        "close": last,
        "volume": float(live.volume),
        "trades": float(live.trades or 0),
    }
    df = df.copy()
    df.loc[day, list(bar)] = list(bar.values())
    return df.sort_index()
