"""Redis adapters: the shared live read model, the cross-process event bus, and a once-per-key guard.

Keys (all under `live:`):
  live:quotes    HASH symbol → quote JSON       (deltas only per tick; replaced on a fresh start)
  live:market    STRING market-state JSON
  live:counters  STRING poller counters JSON     (status from any replica; ETag survives restarts)
  live:seq       INT    global event id          (same id on every replica → Last-Event-ID is meaningful)
  live:once:*    STRING once-per-key claims       (e.g. end-of-day per session date)
Channel `live:events` carries one JSON array of PublishedEvent per poll.
"""

import json
import time
from collections.abc import AsyncIterator, Callable, Sequence
from typing import cast

from redis.asyncio import Redis

from dse.features.live_feed.application.dto import FeedCounters, FeedEvent, PublishedEvent
from dse.features.live_feed.domain.entities import LiveQuote, LiveSnapshot, MarketState
from dse.features.live_feed.infrastructure.codec import (
    counters_from_json,
    counters_to_json,
    dumps,
    market_from_json,
    market_to_json,
    quote_from_json,
    quote_to_json,
)

QUOTES, MARKET, COUNTERS, SEQ = "live:quotes", "live:market", "live:counters", "live:seq"
CHANNEL = "live:events"
FIELDS = set(FeedEvent.model_fields)  # re-publishing a PublishedEvent gets fresh id/timestamp


class RedisLiveStateStore:
    def __init__(self, redis: "Redis") -> None:
        self._r = redis

    async def load_snapshot(self) -> LiveSnapshot | None:
        market = await self.market()
        if market is None:
            return None
        raw = cast(dict[str, str], await self._r.hgetall(QUOTES))
        return LiveSnapshot(market, {s: quote_from_json(s, v) for s, v in raw.items()})

    async def save_snapshot(
        self, snapshot: LiveSnapshot, changed: Sequence[LiveQuote], *, full: bool = False
    ) -> None:
        async with self._r.pipeline(transaction=True) as p:
            if full:
                p.delete(QUOTES)
            if changed:
                p.hset(QUOTES, mapping={q.symbol.value: quote_to_json(q) for q in changed})
            p.set(MARKET, market_to_json(snapshot.state))
            await p.execute()

    async def market(self) -> MarketState | None:
        raw = cast(str | None, await self._r.get(MARKET))
        return market_from_json(raw) if raw else None

    async def quotes(self, symbols: Sequence[str] | None = None) -> list[LiveQuote]:
        if symbols is None:
            raw = cast(dict[str, str], await self._r.hgetall(QUOTES))
            return [quote_from_json(s, raw[s]) for s in sorted(raw)]
        if not symbols:
            return []
        values = cast(list[str | None], await self._r.hmget(QUOTES, list(symbols)))
        return [quote_from_json(s, v) for s, v in zip(symbols, values, strict=True) if v is not None]

    async def load_counters(self) -> FeedCounters | None:
        raw = cast(str | None, await self._r.get(COUNTERS))
        return counters_from_json(raw) if raw else None

    async def save_counters(self, counters: FeedCounters) -> None:
        await self._r.set(COUNTERS, counters_to_json(counters))


class RedisEventPublisher:
    def __init__(self, redis: "Redis") -> None:
        self._r = redis

    async def publish(self, events: Sequence[FeedEvent]) -> list[PublishedEvent]:
        if not events:
            return []
        last: int = await self._r.incrby(SEQ, len(events))
        now = int(time.time() * 1000)
        first = last - len(events) + 1
        published = [
            PublishedEvent(**e.model_dump(include=FIELDS), id=first + i, published_ms=now)
            for i, e in enumerate(events)
        ]
        await self._r.publish(CHANNEL, dumps([p.model_dump(mode="json") for p in published]))
        return published


POLL_S = 0.5  # how long one pub/sub read may block (also the worst-case shutdown latency)


class RedisEventStream:
    def __init__(self, redis: "Redis") -> None:
        self._r = redis

    async def listen(self, on_subscribed: Callable[[], None]) -> AsyncIterator[PublishedEvent]:
        pubsub = self._r.pubsub(ignore_subscribe_messages=True)
        await pubsub.subscribe(CHANNEL)
        on_subscribed()
        try:
            # Poll with a short timeout instead of `pubsub.listen()`: cancelling a read blocked inside
            # redis-py can fail to complete, which hangs shutdown. A bounded wait always returns.
            while True:
                msg = await pubsub.get_message(timeout=POLL_S)
                if msg is None or msg.get("type") != "message":
                    continue
                for item in json.loads(msg["data"]):
                    yield PublishedEvent.model_validate(item)
        finally:
            await pubsub.aclose()  # type: ignore[no-untyped-call]


class RedisOnceGuard:
    def __init__(self, redis: "Redis", prefix: str = "live:once:") -> None:
        self._r, self._prefix = redis, prefix

    async def claim(self, key: str, ttl_s: int) -> bool:
        return bool(await self._r.set(self._prefix + key, "1", nx=True, ex=ttl_s))

    async def release(self, key: str) -> None:
        await self._r.delete(self._prefix + key)
