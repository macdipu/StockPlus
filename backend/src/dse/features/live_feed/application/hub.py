"""Per-replica fan-out: ONE bus subscription per API process, many SSE clients.

Each client has its own bounded queue; a slow client drops its oldest events instead of stalling the others
(quotes are state, so the newest value is what matters). The hub reconnects to the bus with backoff.
"""

import asyncio
import contextlib
import logging
from dataclasses import dataclass, field

from dse.features.live_feed.application.dto import PublishedEvent
from dse.features.live_feed.application.ports import EventStream

log = logging.getLogger("dse.live_feed.hub")


@dataclass(eq=False)  # identity semantics: each SSE connection is its own subscriber
class Subscriber:
    symbols: frozenset[str] | None  # None = every symbol
    queue: asyncio.Queue[PublishedEvent]
    dropped: int = 0

    def wants(self, event: PublishedEvent) -> bool:
        return event.symbol is None or self.symbols is None or event.symbol in self.symbols

    def offer(self, event: PublishedEvent) -> None:
        if self.queue.full():
            with contextlib.suppress(asyncio.QueueEmpty):
                self.queue.get_nowait()
            self.dropped += 1
        self.queue.put_nowait(event)


@dataclass
class FeedHub:
    stream: EventStream
    queue_size: int = 256
    retry_max_s: float = 30.0
    connected: bool = False
    last_event_id: int | None = None
    _subs: set[Subscriber] = field(default_factory=set)

    def subscribe(self, symbols: set[str] | None = None) -> Subscriber:
        sub = Subscriber(frozenset(symbols) if symbols else None, asyncio.Queue(self.queue_size))
        self._subs.add(sub)
        return sub

    def unsubscribe(self, sub: Subscriber) -> None:
        self._subs.discard(sub)

    @property
    def subscribers(self) -> int:
        return len(self._subs)

    def dispatch(self, event: PublishedEvent) -> None:
        self.last_event_id = event.id
        for sub in list(self._subs):
            if sub.wants(event):
                sub.offer(event)

    def _on_subscribed(self) -> None:
        self.connected = True

    async def run(self) -> None:
        delay = 0.5
        while True:
            try:
                async for event in self.stream.listen(self._on_subscribed):
                    delay = 0.5
                    self.dispatch(event)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                log.warning("event bus connection lost", extra={"error": f"{type(e).__name__}: {e}"})
            self.connected = False
            await asyncio.sleep(delay)
            delay = min(delay * 2, self.retry_max_s)
