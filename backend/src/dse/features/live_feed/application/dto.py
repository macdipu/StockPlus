"""Application-boundary DTOs. Presentation serialises these; it never sees entities."""

from dataclasses import dataclass
from datetime import date
from typing import Any

from pydantic import BaseModel

from dse.features.live_feed.domain.entities import SessionState


class QuoteDto(BaseModel):
    symbol: str
    ltp: float | None
    ycp: float | None
    open: float | None
    high: float | None
    low: float | None
    close: float | None
    change: float | None
    percent: float | None
    volume: int
    value_mn: float | None
    trades: int | None
    category: str | None
    board: str | None
    sector: str | None
    asset_type: str | None
    trade_time: str | None


class SessionDto(BaseModel):
    day: date | None
    is_open: bool
    trading_day: bool
    phase: str | None
    opening: str | None
    closing: str | None


class IndexDto(BaseModel):
    key: str
    value: float | None
    change: float | None
    percent: float | None


class MarketDto(BaseModel):
    session: SessionDto
    trade_time: str | None
    indices: list[IndexDto]
    totals: dict[str, Any]
    breadth: dict[str, Any]
    movers: dict[str, Any]


class FeedStatusDto(BaseModel):
    """Health of the worker's poller, as seen from any API replica."""

    ready: bool
    stale: bool
    market_open: bool | None
    trade_time: str | None
    symbols: int
    poll_interval_s: float | None
    last_poll_age_ms: int | None
    last_success_age_ms: int | None
    last_change_age_ms: int | None
    polls: int
    not_modified: int
    changes: int
    last_error: str | None


@dataclass(slots=True)
class FeedCounters:
    """Mutable poller bookkeeping, persisted next to the quotes so every replica can report it and a
    restarted worker resumes its ETag instead of re-downloading."""

    polls: int = 0
    not_modified: int = 0
    changes: int = 0
    last_poll_ms: int | None = None
    last_ok_ms: int | None = None
    last_change_ms: int | None = None
    last_error: str | None = None
    etag: str | None = None
    poll_interval_s: float | None = None
    symbols: int = 0
    market_open: bool | None = None
    trade_time: str | None = None


class FeedEvent(BaseModel):
    """An event the poller wants delivered. The publisher assigns `id` and `published_ms`."""

    event: str  # "quote" | "market"
    symbol: str | None
    data: dict[str, Any]
    received_ms: int


class PublishedEvent(FeedEvent):
    id: int
    published_ms: int


@dataclass(frozen=True, slots=True)
class PollOutcome:
    """Internal result handed to worker hooks (end-of-day trigger, later the universe build)."""

    not_modified: bool
    session: SessionState | None
    first: bool = False
    changed: tuple[str, ...] = ()
    market_changed: bool = False
    published: int = 0
