"""Against the real stack (docker compose up -d db redis): Redis adapters, SQL ticks, and the Phase 2 exit
criterion — two API replicas (two real uvicorn servers) stream the same tick with the same event id.

Uses Redis database 15 so a running dev worker (db 0) cannot interfere.
"""

import asyncio
import json
import socket
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx
import pytest
import uvicorn
from redis.asyncio import Redis
from sqlalchemy import text

from dse.core.cache import create_redis
from dse.core.clock import SystemClock
from dse.core.config import RedisSettings, Settings, get_settings
from dse.core.db import Database
from dse.features.live_feed.application.dto import FeedEvent
from dse.features.live_feed.application.use_cases import PollSnapshot
from dse.features.live_feed.domain.entities import LiveSnapshot, PollPolicy, Tick
from dse.features.live_feed.domain.ports import FetchResult
from dse.features.live_feed.infrastructure.redis_adapters import (
    RedisEventPublisher,
    RedisEventStream,
    RedisLiveStateStore,
    RedisOnceGuard,
)
from dse.features.live_feed.infrastructure.repositories import SqlLiveFeedUnitOfWork
from dse.features.live_feed.tests.fakes import FakeFeed, with_quote
from dse.main import create_app

pytestmark = pytest.mark.integration


def isolated_settings() -> Settings:
    base = get_settings()
    url = base.redis.url.rsplit("/", 1)[0] + "/15"
    return base.model_copy(update={"redis": RedisSettings(url=url)})


@pytest.fixture
async def redis() -> AsyncIterator[Redis]:
    r = create_redis(isolated_settings().redis)
    await r.flushdb()
    yield r
    await r.flushdb()
    await r.aclose()


@pytest.fixture
async def db() -> AsyncIterator[Database]:
    d = Database(get_settings().database)
    async with d.engine.begin() as c:
        await c.execute(text("TRUNCATE ticks"))
    yield d
    async with d.engine.begin() as c:  # fixture prices stamped with real time must not linger in dev data
        await c.execute(text("TRUNCATE ticks"))
    await d.dispose()


async def test_redis_state_store_round_trip(redis: Redis, snapshot: LiveSnapshot) -> None:
    store = RedisLiveStateStore(redis)
    assert await store.load_snapshot() is None
    await store.save_snapshot(snapshot, list(snapshot.quotes.values()), full=True)
    loaded = await store.load_snapshot()
    assert loaded == snapshot
    moved = with_quote(snapshot, "GP", ltp=1.5)
    await store.save_snapshot(moved, [moved.quotes["GP"]])
    assert [q.ltp for q in await store.quotes(["GP", "NOPE"])] == [1.5]
    assert len(await store.quotes()) == 398
    fewer = LiveSnapshot(snapshot.state, {"GP": snapshot.quotes["GP"]})
    await store.save_snapshot(fewer, list(fewer.quotes.values()), full=True)  # delisted rows vanish
    assert [q.symbol.value for q in await store.quotes()] == ["GP"]


async def test_redis_bus_ids_are_global_and_guard_is_once(redis: Redis) -> None:
    ready = asyncio.Event()
    got: list[int] = []

    async def consume() -> None:
        async for e in RedisEventStream(redis).listen(ready.set):
            got.append(e.id)
            if len(got) == 3:
                return

    task = asyncio.create_task(consume())
    await asyncio.wait_for(ready.wait(), 5)
    pub = RedisEventPublisher(redis)
    ev = FeedEvent(event="quote", symbol="GP", data={}, received_ms=1)
    assert [p.id for p in await pub.publish([ev, ev])] == [1, 2]
    assert [p.id for p in await RedisEventPublisher(redis).publish([ev])] == [3]  # second "process"
    await asyncio.wait_for(task, 5)
    assert got == [1, 2, 3]

    guard = RedisOnceGuard(redis)
    assert await guard.claim("eod:2026-11-11", 60)
    assert not await guard.claim("eod:2026-11-11", 60)
    await guard.release("eod:2026-11-11")
    assert await guard.claim("eod:2026-11-11", 60)


async def test_sql_ticks_insert_and_ignore_duplicates(db: Database, snapshot: LiveSnapshot) -> None:
    ticks = [Tick.of(q, 1_762_839_600_000, snapshot.trade_time) for q in snapshot.quotes.values()]
    async with SqlLiveFeedUnitOfWork(db.sessions) as uow:
        assert await uow.ticks.record(ticks) == 398
        await uow.commit()
    async with SqlLiveFeedUnitOfWork(db.sessions) as uow:
        assert await uow.ticks.record(ticks[:5]) == 0
        await uow.commit()
    async with db.engine.connect() as c:
        assert (await c.execute(text("SELECT count(*) FROM ticks"))).scalar() == 398


# ---------------------------------------------------------------- two replicas, one tick


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@asynccontextmanager
async def replica(settings: Settings) -> AsyncIterator[str]:
    port = free_port()
    server = uvicorn.Server(
        uvicorn.Config(create_app(settings), host="127.0.0.1", port=port, log_level="warning")
    )
    task = asyncio.create_task(server.serve())
    try:
        for _ in range(200):
            if server.started:
                break
            await asyncio.sleep(0.02)
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        await asyncio.wait_for(task, 10)


async def sse_events(client: httpx.AsyncClient, url: str, out: asyncio.Queue[dict[str, Any]]) -> None:
    async with client.stream("GET", url) as r:
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")
        event: dict[str, Any] = {}
        async for line in r.aiter_lines():
            if not line:
                if "event" in event:
                    await out.put(event)
                event = {}
            elif line.startswith("event: "):
                event["event"] = line[7:]
            elif line.startswith("id: "):
                event["id"] = int(line[4:])
            elif line.startswith("data: "):
                event["data"] = json.loads(line[6:])


async def next_event(q: asyncio.Queue[dict[str, Any]], kind: str) -> dict[str, Any]:
    while True:
        e = await asyncio.wait_for(q.get(), 10)
        if e["event"] == kind:
            return e


async def test_two_api_replicas_stream_the_same_tick(
    redis: Redis, db: Database, snapshot: LiveSnapshot
) -> None:
    settings = isolated_settings()
    clock = SystemClock()  # the publisher stamps real time; keep received_ms on the same clock
    moved = with_quote(snapshot, "GP", ltp=777.7, volume=snapshot.quotes["GP"].volume + 100)
    feed = FakeFeed(FetchResult(snapshot, "a"), FetchResult(moved, "b"))
    poll = PollSnapshot(
        feed,
        RedisLiveStateStore(redis),
        RedisEventPublisher(redis),
        lambda: SqlLiveFeedUnitOfWork(db.sessions),
        clock,
        PollPolicy(),
    )
    await poll()  # the worker's first snapshot: replicas now have state to serve

    async with replica(settings) as a, replica(settings) as b, httpx.AsyncClient(timeout=15) as client:
        # REST read model is served identically by both replicas
        for base in (a, b):
            quotes = (await client.get(f"{base}/api/v1/quotes", params={"symbols": "GP"})).json()
            assert quotes["data"][0]["ltp"] == snapshot.quotes["GP"].ltp
            market = (await client.get(f"{base}/api/v1/market")).json()["data"]
            assert market["session"]["is_open"] is True
            for _ in range(100):  # each replica's single bus subscription is live
                status = (await client.get(f"{base}/api/v1/feed/status")).json()
                if status["meta"]["replica"]["busConnected"]:
                    break
                await asyncio.sleep(0.05)
            assert status["data"]["ready"] is True

        queues: list[asyncio.Queue[dict[str, Any]]] = [asyncio.Queue(), asyncio.Queue()]
        readers = [
            asyncio.create_task(sse_events(client, f"{base}/api/v1/stream?symbols=GP,BATBC", q))
            for base, q in zip((a, b), queues, strict=True)
        ]
        try:
            snaps = [await next_event(q, "snapshot") for q in queues]
            for s in snaps:
                assert set(s["data"]["quotes"]) == {"GP", "BATBC"}

            out = await poll()  # one upstream tick, processed once by the worker
            assert out.changed == ("GP",)

            ticks = [await next_event(q, "quote") for q in queues]
            assert ticks[0]["id"] == ticks[1]["id"]  # same global event id on both replicas
            assert ticks[0]["data"] == ticks[1]["data"]
            assert ticks[0]["data"]["symbol"] == "GP"
            assert ticks[0]["data"]["ltp"] == 777.7
            meta = ticks[0]["data"]["_meta"]
            assert meta["published_ms"] >= meta["received_ms"] > 0
        finally:
            for t in readers:
                t.cancel()
            await asyncio.gather(*readers, return_exceptions=True)

    async with db.engine.connect() as c:  # ticks recorded once (by the worker), not per replica
        n = (await c.execute(text("SELECT count(*) FROM ticks WHERE symbol = 'GP'"))).scalar()
    assert n == 2  # baseline + the change


async def test_stream_rejects_too_many_symbols(redis: Redis) -> None:
    async with replica(isolated_settings()) as a, httpx.AsyncClient() as client:
        many = ",".join(f"S{i}" for i in range(51))
        r = await client.get(f"{a}/api/v1/stream", params={"symbols": many})
        assert r.status_code == 400
        assert r.headers["content-type"] == "application/problem+json"
        r = await client.get(f"{a}/api/v1/quotes")
        assert r.status_code == 503  # no snapshot yet in this (empty) Redis db
