"""Market depth: the buy and sell orders waiting at each price. Pure model and arithmetic."""

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DepthLevel:
    price: float
    quantity: int
    orders: int


@dataclass(frozen=True, slots=True)
class MarketDepth:
    symbol: str
    bids: tuple[DepthLevel, ...]  # buyers, highest price first
    asks: tuple[DepthLevel, ...]  # sellers, lowest price first
    as_of: str | None  # DSE's own timestamp text
    market_open: bool | None
    stats: dict[str, float | int | str | None]


@dataclass(frozen=True, slots=True)
class SideTotals:
    quantity: int
    orders: int
    average_price: float | None  # quantity-weighted


def side_totals(levels: Sequence[DepthLevel]) -> SideTotals:
    qty = sum(lv.quantity for lv in levels)
    avg = sum(lv.price * lv.quantity for lv in levels) / qty if qty else None
    return SideTotals(qty, sum(lv.orders for lv in levels), avg)


def spread(bids: Sequence[DepthLevel], asks: Sequence[DepthLevel]) -> float | None:
    """Best ask minus best bid; None when either side is empty."""
    return round(asks[0].price - bids[0].price, 4) if bids and asks else None
