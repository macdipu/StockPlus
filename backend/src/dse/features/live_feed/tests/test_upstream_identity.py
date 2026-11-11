"""How the snapshot poller presents itself to the exchange: honestly, and politely when refused."""

import asyncio

import httpx
import pytest

from dse.features.live_feed.application.dto import PollOutcome
from dse.features.live_feed.application.use_cases import RunFeed
from dse.features.live_feed.domain.entities import PollPolicy
from dse.features.live_feed.infrastructure.dse_snapshot import DseSnapshotFeed
from dse.shared_kernel.errors import UpstreamForbiddenError, UpstreamUnavailableError

BROWSER_MIMICRY = ("mozilla", "chrome", "safari", "applewebkit", "gecko")
URL = "https://example.test"


def answering(status: int) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(status)))


async def test_the_snapshot_client_sends_only_the_identity_it_was_given() -> None:
    client = DseSnapshotFeed(URL, user_agent="my-tool/9 (ops@example.test)")._client
    try:
        assert client.headers["user-agent"] == "my-tool/9 (ops@example.test)"
        for name in ("referer", "accept-language", "origin", "sec-fetch-mode"):
            assert name not in client.headers  # none of the headers a browser would add
        assert not any(w in v.lower() for v in client.headers.values() for w in BROWSER_MIMICRY)
    finally:
        await client.aclose()


async def test_a_403_is_reported_as_a_refusal_not_a_glitch() -> None:
    feed = DseSnapshotFeed(URL, user_agent="x", client=answering(403))
    with pytest.raises(UpstreamForbiddenError, match="403"):
        await feed.fetch(None)
    assert issubclass(
        UpstreamForbiddenError, UpstreamUnavailableError
    )  # still an upstream failure (HTTP 502)


async def test_other_failures_are_still_ordinary_upstream_errors() -> None:
    feed = DseSnapshotFeed(URL, user_agent="x", client=answering(503))
    with pytest.raises(UpstreamUnavailableError) as e:
        await feed.fetch(None)
    assert not isinstance(e.value, UpstreamForbiddenError)


async def test_the_poll_loop_backs_off_for_fifteen_minutes_when_refused() -> None:
    delays: list[float] = []
    stop = asyncio.Event()
    results: list[PollOutcome | Exception] = [
        UpstreamForbiddenError("refused"),
        UpstreamUnavailableError("503"),
    ]

    async def poll() -> PollOutcome:
        item = results.pop(0)
        if not results:
            stop.set()
        if isinstance(item, Exception):
            raise item
        return item

    async def wait(_: asyncio.Event, delay: float) -> None:
        delays.append(delay)

    policy = PollPolicy(open_s=10, closed_s=60, floor_s=0)
    await RunFeed(poll, policy, wait=wait).run(stop)
    assert delays[0] == 10 + 900  # refused: a quarter of an hour, not the usual 5-120 s
    assert (
        delays[1] == 10 + 120
    )  # an ordinary failure afterwards uses the normal (capped) exponential backoff
