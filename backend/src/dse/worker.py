"""Composition root for background processes (ADR 0002):  python -m dse.worker [--check]

Runs the live feed: PollSnapshot on a session-aware interval → Redis read model + `live:events` bus +
Postgres ticks. After the close it triggers market_data's AppendEndOfDay once per session. After every
real change it rebuilds the scanner universe in the background and publishes it to Redis.
Exactly one worker should run; API replicas are stateless readers.

`--check` is the container healthcheck: exit 0 while the poller has succeeded recently.
"""

import argparse
import asyncio
import contextlib
import logging
import signal
import sys

from dse.core.cache import create_redis
from dse.core.clock import SystemClock
from dse.core.config import Settings, get_settings
from dse.core.db import Database
from dse.core.logging import configure_logging
from dse.features.live_feed.application.dto import PollOutcome
from dse.features.live_feed.application.facade import LiveFeedFacade
from dse.features.live_feed.application.use_cases import (
    BroadcastEvent,
    EndOfDayTrigger,
    GetFeedStatus,
    GetMarket,
    GetQuotes,
    PollSnapshot,
    RunFeed,
)
from dse.features.live_feed.domain.entities import PollPolicy
from dse.features.live_feed.infrastructure.dse_snapshot import DseSnapshotFeed
from dse.features.live_feed.infrastructure.redis_adapters import (
    RedisEventPublisher,
    RedisLiveStateStore,
    RedisOnceGuard,
)
from dse.features.live_feed.infrastructure.repositories import SqlLiveFeedUnitOfWork
from dse.features.market_data.infrastructure.dse_source import DseHttpSource
from dse.features.market_data.presentation.dependencies import MarketDataContainer
from dse.features.scanner.application.use_cases import MaterialiseUniverse, UniverseRefresher
from dse.features.scanner.infrastructure.gateways import FacadeUniverseSource, LiveFeedUniverseNotifier
from dse.features.scanner.infrastructure.redis_store import RedisUniverseStore

log = logging.getLogger("dse.worker")


def policy_from(settings: Settings) -> PollPolicy:
    s = settings.live
    return PollPolicy(open_s=s.poll_open_s, closed_s=s.poll_closed_s, floor_s=s.min_poll_s)


async def run(settings: Settings) -> None:
    db, redis, clock = Database(settings.database), create_redis(settings.redis), SystemClock()
    up = settings.upstream
    feed = DseSnapshotFeed(up.base_url, timeout_s=up.timeout_s)
    source = DseHttpSource(
        up.base_url, clock, timeout_s=up.timeout_s, min_page_interval_s=up.min_page_interval_s
    )
    market_data = MarketDataContainer(db, source, clock)
    policy = policy_from(settings)

    live_store, publisher = RedisLiveStateStore(redis), RedisEventPublisher(redis)
    poll = PollSnapshot(
        feed, live_store, publisher, lambda: SqlLiveFeedUnitOfWork(db.sessions), clock, policy
    )

    # The scanner universe is rebuilt off the poll loop (single-flight, in threads): ADR 0002.
    live = LiveFeedFacade(GetQuotes(live_store), GetMarket(live_store), BroadcastEvent(publisher, clock))
    universe = UniverseRefresher(
        MaterialiseUniverse(
            FacadeUniverseSource(market_data.facade, live),
            RedisUniverseStore(redis),
            LiveFeedUniverseNotifier(live),
            clock,
        )
    )

    async def rebuild_universe(outcome: PollOutcome) -> None:
        await universe.on_poll(
            first=outcome.first, changed=bool(outcome.changed), market_changed=outcome.market_changed
        )

    async def end_of_day_then_rebuild() -> object:
        report = await market_data.append_end_of_day()
        universe.trigger()  # the official closing bars changed history
        return report

    end_of_day = EndOfDayTrigger(end_of_day_then_rebuild, RedisOnceGuard(redis), clock)
    loop = RunFeed(poll, policy, hooks=[end_of_day, rebuild_universe])

    stop = asyncio.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        with contextlib.suppress(NotImplementedError):
            asyncio.get_running_loop().add_signal_handler(sig, stop.set)
    log.info("worker started", extra={"poll_open_s": policy.open_s, "poll_closed_s": policy.closed_s})
    try:
        await loop.run(stop)
    finally:
        log.info("worker stopping")
        await universe.aclose()
        await feed.aclose()
        await source.aclose()
        await redis.aclose()
        await db.dispose()


async def check(settings: Settings) -> int:
    redis = create_redis(settings.redis)
    try:
        status = await GetFeedStatus(RedisLiveStateStore(redis), SystemClock(), settings.live.stale_after_s)()
    finally:
        await redis.aclose()
    print(status.model_dump_json())
    return 0 if status.ready and not status.stale else 1


def main() -> int:
    settings = get_settings()
    configure_logging(settings.log_level)
    ap = argparse.ArgumentParser(prog="python -m dse.worker")
    ap.add_argument("--check", action="store_true", help="healthcheck: exit 0 if the feed is fresh")
    args = ap.parse_args()
    if args.check:
        return asyncio.run(check(settings))
    asyncio.run(run(settings))
    return 0


if __name__ == "__main__":
    sys.exit(main())
