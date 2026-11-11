"""Live market feed.

One background task polls DSE's /api/live/snapshot (conditional GET with ETag), diffs every quote against the
previous tick, and fans out only what changed to subscribers. Each subscriber (an SSE connection) has its own
bounded queue; a slow client drops its oldest events instead of stalling the feed.

Latency model: upstream publishes about once a minute behind a 10-15 s CDN cache, so polling faster than
LIVE_POLL_S only re-reads the cache. From the moment a new tick lands here, delivery to the browser is a queue put
plus one SSE write — single-digit milliseconds. Every event carries server timestamps so the UI can show both.
"""
from __future__ import annotations

import asyncio
import contextlib
import itertools
import logging
import time
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Optional

import httpx

import config as C
import scraper

log = logging.getLogger("dse.live")
QUOTE_FIELDS = ("ltp", "open", "high", "low", "close", "volume", "trades", "value")


def _ms() -> int:
    return int(time.time() * 1000)


@dataclass(eq=False)  # identity semantics: each SSE connection is its own subscriber
class Subscriber:
    symbols: Optional[frozenset]          # None = every symbol
    queue: asyncio.Queue = field(default_factory=lambda: asyncio.Queue(C.SUBSCRIBER_QUEUE))
    dropped: int = 0

    def wants(self, symbol: Optional[str]) -> bool:
        return symbol is None or self.symbols is None or symbol in self.symbols

    def offer(self, event: dict) -> None:
        if self.queue.full():
            with contextlib.suppress(asyncio.QueueEmpty):
                self.queue.get_nowait()
            self.dropped += 1
        self.queue.put_nowait(event)


class LiveFeed:
    def __init__(self) -> None:
        self.quotes: dict[str, dict] = {}
        self.market: dict = {}
        self.session: dict = {}
        self.trade_time: Optional[str] = None
        self.etag: Optional[str] = None
        self.last_poll_ms: Optional[int] = None
        self.last_ok_ms: Optional[int] = None
        self.last_change_ms: Optional[int] = None
        self.last_error: Optional[str] = None
        self.polls = self.not_modified = self.changes = 0
        self._ids = itertools.count(1)
        self._subs: set[Subscriber] = set()
        self._task: Optional[asyncio.Task] = None
        self._client: Optional[httpx.AsyncClient] = None
        self._ready = False   # plain flag: an asyncio.Event would bind to the loop that created it (py3.9)
        self.on_change: list[Callable[[set], Awaitable[None]]] = []   # hooks, e.g. recompute analysis

    # ------------------------------------------------------------------ lifecycle
    async def start(self) -> None:
        self._client = httpx.AsyncClient(timeout=C.HTTP_TIMEOUT_S, follow_redirects=True,
                                         headers={"User-Agent": C.USER_AGENT, "Accept": "application/json",
                                                  "Referer": C.BASE_URL + "/"})
        self._task = asyncio.create_task(self._run(), name="dse-live-feed")

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        if self._client:
            await self._client.aclose()

    async def wait_ready(self, timeout: float = 10) -> bool:
        deadline = time.monotonic() + timeout
        while not self._ready and time.monotonic() < deadline:
            await asyncio.sleep(0.05)
        return self._ready

    @property
    def interval(self) -> float:
        base = C.LIVE_POLL_S if self.session.get("isOpen", True) else C.LIVE_POLL_CLOSED_S
        return max(C.LIVE_MIN_POLL_S, base)

    async def _run(self) -> None:
        backoff = 0.0
        while True:
            try:
                await self.poll_once()
                backoff = 0.0
            except asyncio.CancelledError:
                raise
            except Exception as e:  # keep the feed alive; surface the error on /ready
                self.last_error = f"{type(e).__name__}: {e}"
                backoff = min(max(backoff * 2, 5.0), 120.0)
                log.warning("live poll failed: %s (next in %.0fs)", self.last_error, self.interval + backoff)
            await asyncio.sleep(self.interval + backoff)

    # ------------------------------------------------------------------ polling
    async def poll_once(self) -> set:
        assert self._client is not None, "call start() first"
        headers = {"If-None-Match": self.etag} if self.etag else {}
        self.polls += 1
        self.last_poll_ms = _ms()
        r = await self._client.get(C.SNAPSHOT_URL, headers=headers)
        if r.status_code == 304:
            self.not_modified += 1
            self.last_ok_ms = _ms()
            return set()
        r.raise_for_status()
        self.etag = r.headers.get("etag")
        snap = scraper.parse_snapshot(r.json())
        self.last_ok_ms, self.last_error = _ms(), None
        return await self.apply(snap)

    async def apply(self, snap: dict) -> set:
        """Merge a parsed snapshot, publish what changed. Separated from HTTP so it is unit-testable."""
        received = _ms()
        changed = {s for s, q in snap["quotes"].items()
                   if s not in self.quotes or any(q.get(f) != self.quotes[s].get(f) for f in QUOTE_FIELDS)}
        market_changed = snap["tradeTime"] != self.trade_time or snap["session"] != self.session
        self.quotes.update(snap["quotes"])
        self.market, self.session, self.trade_time = snap["market"], snap["session"], snap["tradeTime"]
        first = not self._ready
        self._ready = True
        if first:
            return changed
        if changed or market_changed:
            self.changes += 1
            self.last_change_ms = received
        for sym in changed:
            self.publish("quote", self.quotes[sym], symbol=sym, received_ms=received)
        if market_changed:
            self.publish("market", self.market_summary(), received_ms=received)
        for hook in self.on_change:
            asyncio.create_task(hook(changed))
        return changed

    # ------------------------------------------------------------------ pub/sub
    def subscribe(self, symbols: Optional[set] = None) -> Subscriber:
        sub = Subscriber(frozenset(symbols) if symbols else None)
        self._subs.add(sub)
        return sub

    def unsubscribe(self, sub: Subscriber) -> None:
        self._subs.discard(sub)

    def watched_symbols(self) -> set:
        out: set = set()
        for s in self._subs:
            if s.symbols:
                out |= s.symbols
        return out

    def publish(self, kind: str, data: dict, symbol: Optional[str] = None, received_ms: Optional[int] = None) -> None:
        event = {"id": next(self._ids), "event": kind, "symbol": symbol,
                 "data": {**data, "_meta": {"tradeTime": self.trade_time, "receivedMs": received_ms or _ms(),
                                            "publishedMs": _ms()}}}
        for sub in list(self._subs):
            if sub.wants(symbol):
                sub.offer(event)

    # ------------------------------------------------------------------ read models
    def market_summary(self) -> dict:
        m = self.market
        return {"session": self.session, "tradeTime": self.trade_time, "indices": m.get("indices"),
                "totals": m.get("totals"), "breadth": m.get("breadth"), "movers": m.get("movers")}

    def status(self) -> dict:
        now = _ms()
        return {"ready": self._ready, "subscribers": len(self._subs), "pollIntervalS": self.interval,
                "lastPollAgeMs": now - self.last_poll_ms if self.last_poll_ms else None,
                "lastSuccessAgeMs": now - self.last_ok_ms if self.last_ok_ms else None,
                "lastChangeAgeMs": now - self.last_change_ms if self.last_change_ms else None,
                "tradeTime": self.trade_time, "marketOpen": self.session.get("isOpen"),
                "polls": self.polls, "notModified": self.not_modified, "changes": self.changes,
                "symbols": len(self.quotes), "lastError": self.last_error}
