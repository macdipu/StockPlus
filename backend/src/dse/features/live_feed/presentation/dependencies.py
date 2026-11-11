"""Dependency providers. Build use cases from the process-wide resources on app.state."""

from dataclasses import dataclass

from fastapi import Request

from dse.core.config import LiveSettings
from dse.features.live_feed.application.facade import LiveFeedFacade
from dse.features.live_feed.application.hub import FeedHub
from dse.features.live_feed.application.ports import LiveStateStore
from dse.features.live_feed.application.use_cases import GetFeedStatus, GetMarket, GetMovers, GetQuotes
from dse.shared_kernel.clock import Clock


@dataclass(frozen=True)
class LiveFeedContainer:
    """Read-side container for API replicas (the write side is wired in `dse.worker`)."""

    store: LiveStateStore
    hub: FeedHub
    clock: Clock
    settings: LiveSettings

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
    def facade(self) -> LiveFeedFacade:
        return LiveFeedFacade(self.get_quotes, self.get_market)


def container(request: Request) -> LiveFeedContainer:
    c: LiveFeedContainer = request.app.state.live_feed
    return c
