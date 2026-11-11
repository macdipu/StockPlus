"""Small analytical tools over daily history: what a trade would have returned, and how returns co-move."""

from collections.abc import Mapping
from datetime import date
from typing import Any

import pandas as pd

from dse.shared_kernel.errors import ValidationFailedError

MAX_CORRELATION_SYMBOLS = 20
MIN_CORRELATION_OBSERVATIONS = 20


def return_between(
    df: pd.DataFrame, buy: date, sell: date | None, quantity: float, fee_pct: float
) -> dict[str, Any]:
    """Round-trip return of buying at the first close on/after `buy` and selling at the last close on/before
    `sell` (default: the latest bar), after `fee_pct` on each leg. Price return only: no dividends."""
    if df.empty:
        raise ValidationFailedError("No price history for this instrument.")
    bought = df[df.index >= pd.Timestamp(buy)]
    sold = df[df.index <= pd.Timestamp(sell)] if sell else df
    if bought.empty or sold.empty or sold.index[-1] < bought.index[0]:
        raise ValidationFailedError(
            f"No bars between {buy} and {sell or 'today'} "
            f"(history {df.index[0]:%Y-%m-%d} to {df.index[-1]:%Y-%m-%d})."
        )
    buy_price, sell_price = float(bought["close"].iloc[0]), float(sold["close"].iloc[-1])
    cost = buy_price * quantity * (1 + fee_pct / 100)
    proceeds = sell_price * quantity * (1 - fee_pct / 100)
    days = (sold.index[-1] - bought.index[0]).days
    return {
        "buy_date": f"{bought.index[0]:%Y-%m-%d}",
        "buy_price": buy_price,
        "sell_date": f"{sold.index[-1]:%Y-%m-%d}",
        "sell_price": sell_price,
        "quantity": quantity,
        "fee_pct": fee_pct,
        "cost": cost,
        "proceeds": proceeds,
        "profit": proceeds - cost,
        "return_pct": (proceeds / cost - 1) * 100,
        "days": days,
        "annualised_pct": ((proceeds / cost) ** (365 / days) - 1) * 100 if days > 0 else None,
        "note": "Price return after round-trip fees; dividends not included.",
    }


def correlation(closes: Mapping[str, pd.Series], days: int) -> dict[str, Any]:
    """Pearson correlation of daily returns over the last `days` sessions (pairwise, >= 20 shared days)."""
    frame = pd.DataFrame(dict(closes)).sort_index().iloc[-days - 1 :]
    returns = frame.pct_change().dropna(how="all")
    matrix = returns.corr(min_periods=MIN_CORRELATION_OBSERVATIONS).round(3)
    return {
        "symbols": [str(c) for c in matrix.columns],
        "days": days,
        "matrix": [[None if pd.isna(x) else float(x) for x in row] for row in matrix.to_numpy()],
    }
