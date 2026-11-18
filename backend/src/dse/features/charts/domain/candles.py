"""Candles as columnar arrays (what indicators and the API both want). Pure: numpy and pandas only."""

import hashlib
from dataclasses import dataclass

import numpy as np
import pandas as pd

from dse.shared_kernel.errors import ValidationFailedError

RESOLUTIONS = {"1": "1 minute", "5": "5 minutes", "30": "30 minutes", "60": "1 hour", "D": "1 day"}
INDEX_CODES = frozenset(
    {"DSEX", "DS30", "DSES"}
)  # indices have no company page; their values come from the exchange's index endpoints


def check_resolution(resolution: str) -> str:
    if resolution not in RESOLUTIONS:
        raise ValidationFailedError(f"resolution must be one of {', '.join(RESOLUTIONS)}")
    return resolution


def is_index(symbol: str) -> bool:
    return symbol.upper() in INDEX_CODES


@dataclass(frozen=True, eq=False)
class Candles:
    """Oldest first. `time` is unix seconds (UTC); daily candles sit at 00:00 UTC of their trading day."""

    time: np.ndarray
    open: np.ndarray
    high: np.ndarray
    low: np.ndarray
    close: np.ndarray
    volume: np.ndarray
    # False for a series that only has closing values (a stock index): open, high and low repeat the close and
    # volume is zero, so indicators that need them cannot be computed.
    ohlc: bool = True

    def __post_init__(self) -> None:
        n = len(self.time)
        for name in ("open", "high", "low", "close", "volume"):
            if len(getattr(self, name)) != n:
                raise ValueError(f"candle column {name} has {len(getattr(self, name))} rows, expected {n}")

    def __len__(self) -> int:
        return len(self.time)

    @classmethod
    def from_rows(cls, rows: list[tuple[int, float, float, float, float, float]]) -> "Candles":
        """Rows of (time, open, high, low, close, volume). Sorted by time, duplicate times keep the last."""
        by_time = {r[0]: r for r in rows}
        ordered = [by_time[t] for t in sorted(by_time)]
        cols = list(zip(*ordered, strict=True)) if ordered else [()] * 6
        return cls(
            time=np.asarray(cols[0], dtype="int64"),
            open=np.asarray(cols[1], dtype="float64"),
            high=np.asarray(cols[2], dtype="float64"),
            low=np.asarray(cols[3], dtype="float64"),
            close=np.asarray(cols[4], dtype="float64"),
            volume=np.asarray(cols[5], dtype="float64"),
        )

    @classmethod
    def from_closes(cls, points: list[tuple[int, float]]) -> "Candles":
        """(time, value) points of a closes-only series; sorted by time, a repeated time keeps the last."""
        by_time = dict(points)
        times = sorted(by_time)
        values = np.asarray([by_time[t] for t in times], dtype="float64")
        return cls(
            time=np.asarray(times, dtype="int64"),
            open=values.copy(),
            high=values.copy(),
            low=values.copy(),
            close=values,
            volume=np.zeros(len(times), dtype="float64"),
            ohlc=False,
        )

    def frame(self) -> pd.DataFrame:
        """What the indicator engine takes: float OHLCV columns on an ascending UTC DatetimeIndex."""
        return pd.DataFrame(
            {
                "open": self.open,
                "high": self.high,
                "low": self.low,
                "close": self.close,
                "volume": self.volume,
            },
            index=pd.to_datetime(self.time, unit="s", utc=True),
        )

    def fingerprint(self) -> str:
        """Identifies the exact candle content; new or revised candles give a new value (for cache keys)."""
        h = hashlib.blake2b(digest_size=10)
        h.update(b"ohlc" if self.ohlc else b"close")
        for col in (self.time, self.open, self.high, self.low, self.close, self.volume):
            h.update(np.ascontiguousarray(col).tobytes())
        return h.hexdigest()


def aggregate(candles: Candles, minutes: int) -> Candles:
    """Combine candles into buckets of `minutes` (start = the time rounded down). Open is the first, close the
    last, high and low the extremes, volume the sum. Whole-hour timezones (Dhaka is UTC+6) keep the same
    boundaries in local time."""
    if minutes <= 1 or len(candles) == 0:
        return candles
    size = minutes * 60
    bucket = candles.time // size * size
    df = candles.frame().assign(bucket=bucket)
    g = df.groupby("bucket", sort=True)
    out = pd.DataFrame(
        {
            "open": g["open"].first(),
            "high": g["high"].max(),
            "low": g["low"].min(),
            "close": g["close"].last(),
            "volume": g["volume"].sum(),
        }
    )
    return Candles(
        time=out.index.to_numpy(dtype="int64"),
        open=out["open"].to_numpy(dtype="float64"),
        high=out["high"].to_numpy(dtype="float64"),
        low=out["low"].to_numpy(dtype="float64"),
        close=out["close"].to_numpy(dtype="float64"),
        volume=out["volume"].to_numpy(dtype="float64"),
        ohlc=candles.ohlc,
    )
