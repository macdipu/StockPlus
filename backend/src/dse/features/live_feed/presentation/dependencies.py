"""Dependency providers. Build use cases from the process-wide resources on app.state."""

from dataclasses import dataclass
from datetime import tzinfo

from fastapi import Request

from dse.core.config import LiveSettings
from dse.core.db import Database
from dse.features.live_feed.application.facade import LiveFeedFacade
from dse.features.live_feed.application.hub import FeedHub
from dse.features.live_feed.application.ports import LiveStateStore
from dse.features.live_feed.application.use_cases import (
    GetDepth,
    GetFeedStatus,
    GetMarket,
    GetMinuteBars,
    GetMovers,
    GetQuotes,
)
from dse.features.live_feed.domain.ports import DepthFeed
from dse.features.live_feed.infrastructure.repositories import SqlLiveFeedUnitOfWork
from dse.shared_kernel.clock import Clock


@dataclass(frozen=True)
class LiveFeedContainer:
    """Read-side container for API replicas (the write side is wired in `dse.worker`)."""

    store: LiveStateStore
    hub: FeedHub
    clock: Clock
    settings: LiveSettings
    db: Database
    tz: tzinfo
    depth: DepthFeed

    @property
    def get_quotes(self) -> GetQuotes:
        return GetQuotes(self.store)

    @property
    def get_movers(self) -> GetMovers:
        return GetMovers(self.store)

    @property
    def get_market(self) -> GetMarket:
        return GetMarket(self.store)

    @property
    def get_feed_status(self) -> GetFeedStatus:
        return GetFeedStatus(self.store, self.clock, self.settings.stale_after_s)

    @property
    def get_depth(self) -> GetDepth:
        return GetDepth(self.depth, self.clock)

    @property
    def get_minute_bars(self) -> GetMinuteBars:
        return GetMinuteBars(lambda: SqlLiveFeedUnitOfWork(self.db.sessions), self.clock, self.tz)

    @property
    def facade(self) -> LiveFeedFacade:
        return LiveFeedFacade(self.get_quotes, self.get_market, minutes=self.get_minute_bars)


def container(request: Request) -> LiveFeedContainer:
    c: LiveFeedContainer = request.app.state.live_feed
    return c
