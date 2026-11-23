"""HTTP adapter for the live feed: latest quotes/market (read model) and the SSE stream (ADR 0006)."""

import asyncio
import json
import time
from collections.abc import AsyncIterator
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, Query, Request
from fastapi.responses import StreamingResponse

from dse.core.http import envelope
from dse.features.live_feed.application.use_cases import MoverKind
from dse.features.live_feed.presentation.dependencies import LiveFeedContainer, container
from dse.shared_kernel.errors import ServiceNotReadyError, ValidationFailedError
from dse.shared_kernel.symbol import Symbol

router = APIRouter(tags=["live"])
Container = Annotated[LiveFeedContainer, Depends(container)]
SymbolPath = Annotated[str, Path(description="DSE trading code", examples=["GP"], max_length=24)]
SymbolsQuery = Annotated[
    str | None, Query(description="Comma-separated DSE codes; omit for all", examples=["GP,BATBC"])
]


def parse_symbols(raw: str | None, limit: int | None = None) -> list[str] | None:
    if not raw or not raw.strip():
        return None
    out = list(dict.fromkeys(Symbol(s).value for s in raw.split(",") if s.strip()))
    if limit is not None and len(out) > limit:
        raise ValidationFailedError(f"At most {limit} symbols per request (got {len(out)}).")
    return out or None


@router.get("/quotes", summary="Latest quotes (every traded instrument, or a list)")
async def get_quotes(c: Container, symbols: SymbolsQuery = None) -> dict[str, Any]:
    rows = await c.get_quotes(parse_symbols(symbols, 500))
    return envelope([q.model_dump(mode="json") for q in rows], count=len(rows))


@router.get(
    "/quotes/{symbol}/depth",
    summary="Market depth: buyers and sellers waiting at each price, with totals and average prices",
    description="Straight from the exchange's own depth feed, cached for 10 seconds.",
)
async def get_depth(symbol: SymbolPath, c: Container) -> dict[str, Any]:
    return envelope((await c.get_depth(Symbol(symbol))).model_dump(mode="json"))


@router.get("/market", summary="Session, indices, breadth, totals, top movers")
async def get_market(c: Container) -> dict[str, Any]:
    return envelope((await c.get_market()).model_dump(mode="json"))


@router.get("/market/movers", summary="Top gainers / losers / most active today")
async def get_movers(
    c: Container,
    by: Annotated[MoverKind, Query()] = "gainers",
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    asset_types: Annotated[str, Query(description="Comma-separated, e.g. EQ,MF")] = "EQ",
) -> dict[str, Any]:
    kinds = [t.strip().upper() for t in asset_types.split(",") if t.strip()]
    rows = await c.get_movers(by, limit, kinds or None)
    return envelope([q.model_dump(mode="json") for q in rows], count=len(rows), by=by)


@router.get(
    "/feed/status", summary="Live feed health: poll ages, counters, staleness, this replica's fan-out"
)
async def get_feed_status(c: Container) -> dict[str, Any]:
    status = await c.get_feed_status()
    return envelope(status.model_dump(mode="json"), replica=_replica(c))


def _replica(c: LiveFeedContainer) -> dict[str, Any]:
    return {
        "busConnected": c.hub.connected,
        "subscribers": c.hub.subscribers,
        "lastEventId": c.hub.last_event_id,
    }


def sse(event: str, data: Any, eid: int | None = None) -> str:
    head = f"id: {eid}\n" if eid is not None else ""
    return f"{head}event: {event}\ndata: {json.dumps(data, separators=(',', ':'), default=str)}\n\n"


@router.get(
    "/stream",
    summary="Server-Sent Events: live quotes and market updates",
    description=(
        "Events: `snapshot` (full current state, sent on every connect, so reconnecting clients need no "
        "replay), `quote` (an instrument's quote changed; filtered by `symbols`), `market` (session, "
        "indices, breadth), `heartbeat` (feed health). Event ids are global across API replicas. "
        "Each event carries `received_ms` (tick reached the worker) and `published_ms` (put on the bus) "
        "for latency measurement."
    ),
    response_class=StreamingResponse,
)
async def stream(request: Request, c: Container, symbols: SymbolsQuery = None) -> StreamingResponse:
    wanted = parse_symbols(symbols, c.settings.max_stream_symbols)
    sub = c.hub.subscribe(set(wanted) if wanted else None)  # subscribe first: no gap before the snapshot

    async def snapshot() -> dict[str, Any]:
        try:
            market: Any = (await c.get_market()).model_dump(mode="json")
            quotes = {q.symbol: q.model_dump(mode="json") for q in await c.get_quotes(wanted)}
        except ServiceNotReadyError:
            market, quotes = None, {}
        return {
            "market": market,
            "quotes": quotes,
            "feed": (await c.get_feed_status()).model_dump(mode="json"),
        }

    async def gen() -> AsyncIterator[str]:
        try:
            yield "retry: 3000\n\n"
            yield sse("snapshot", await snapshot())
            while not await request.is_disconnected():
                try:
                    ev = await asyncio.wait_for(sub.queue.get(), timeout=c.settings.heartbeat_s)
                except TimeoutError:
                    status = (await c.get_feed_status()).model_dump(mode="json")
                    beat = {"server_ms": int(time.time() * 1000), "feed": status, "dropped": sub.dropped}
                    yield sse("heartbeat", {**beat, "replica": _replica(c)})
                    continue
                payload = {
                    **ev.data,
                    "_meta": {"received_ms": ev.received_ms, "published_ms": ev.published_ms},
                }
                yield sse(ev.event, payload, ev.id)
        finally:
            c.hub.unsubscribe(sub)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )
