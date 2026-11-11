"""Composition root for background processes (ADR 0002):  python -m dse.worker [--check]

Runs the live feed: PollSnapshot on a session-aware interval → Redis read model + `live:events` bus +
Postgres ticks. After the close it triggers market_data's AppendEndOfDay once per session.
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
from dse.features.live_feed.application.use_cases import (
    EndOfDayTrigger,
    GetFeedStatus,
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

    poll = PollSnapshot(
        feed,
        RedisLiveStateStore(redis),
        RedisEventPublisher(redis),
        lambda: SqlLiveFeedUnitOfWork(db.sessions),
        clock,
        policy,
    )
    end_of_day = EndOfDayTrigger(lambda: market_data.append_end_of_day(), RedisOnceGuard(redis), clock)
    loop = RunFeed(poll, policy, hooks=[end_of_day])

    stop = asyncio.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        with contextlib.suppress(NotImplementedError):
            asyncio.get_running_loop().add_signal_handler(sig, stop.set)
    log.info("worker started", extra={"poll_open_s": policy.open_s, "poll_closed_s": policy.closed_s})
    try:
        await loop.run(stop)
    finally:
        log.info("worker stopping")
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
