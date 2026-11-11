"""How we present ourselves to the exchange: honestly, and politely when refused."""

import asyncio

import httpx
import pytest

from dse.core.config import DEFAULT_USER_AGENT, UpstreamSettings
from dse.features.live_feed.application.dto import PollOutcome
from dse.features.live_feed.application.use_cases import RunFeed
from dse.features.live_feed.domain.entities import PollPolicy
from dse.features.live_feed.infrastructure.dse_snapshot import DseSnapshotFeed
from dse.features.market_data.infrastructure.dse_source import DseHttpSource
from dse.features.market_data.tests.fakes import FakeClock
from dse.shared_kernel.errors import UpstreamForbiddenError, UpstreamUnavailableError
from dse.shared_kernel.symbol import Symbol

BROWSER_MIMICRY = ("mozilla", "chrome", "safari", "applewebkit", "gecko")
URL = "https://example.test"


def refusing(status: int) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(status)))


def test_the_default_identity_is_honest() -> None:
    ua = UpstreamSettings().user_agent
    assert ua == DEFAULT_USER_AGENT
    assert ua.startswith("dse-analyzer/")
    assert not any(word in ua.lower() for word in BROWSER_MIMICRY)
    assert "@" not in ua  # no personal contact baked into a default; the operator may add one


@pytest.mark.parametrize("make", ["snapshot", "pages"])
async def test_each_client_sends_only_the_identity_it_was_given(make: str) -> None:
    if make == "snapshot":
        client = DseSnapshotFeed(URL, user_agent="my-tool/9 (ops@example.test)")._client
    else:
        client = DseHttpSource(URL, FakeClock(), user_agent="my-tool/9 (ops@example.test)")._client
    try:
        assert client.headers["user-agent"] == "my-tool/9 (ops@example.test)"
        for name in ("referer", "accept-language", "origin", "sec-fetch-mode"):
            assert name not in client.headers  # none of the headers a browser would add
        assert not any(w in v.lower() for v in client.headers.values() for w in BROWSER_MIMICRY)
    finally:
        await client.aclose()


async def test_a_403_is_reported_as_a_refusal_not_a_glitch() -> None:
    feed = DseSnapshotFeed(URL, user_agent="x", client=refusing(403))
    with pytest.raises(UpstreamForbiddenError, match="403"):
        await feed.fetch(None)
    source = DseHttpSource(URL, FakeClock(), user_agent="x", client=refusing(403), min_page_interval_s=0)
    with pytest.raises(UpstreamForbiddenError, match="refuses this client"):
        await source.company_page(Symbol("GP"))
    with pytest.raises(UpstreamForbiddenError):
        await source.market_snapshot()
    assert issubclass(
        UpstreamForbiddenError, UpstreamUnavailableError
    )  # still an upstream failure (HTTP 502)


async def test_other_failures_are_still_ordinary_upstream_errors() -> None:
    feed = DseSnapshotFeed(URL, user_agent="x", client=refusing(503))
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
