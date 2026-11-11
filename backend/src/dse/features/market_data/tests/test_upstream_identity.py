"""How the company-page client presents itself to the exchange: honestly, and clearly when refused."""

import httpx
import pytest

from dse.features.market_data.infrastructure.dse_source import DseHttpSource
from dse.features.market_data.tests.fakes import FakeClock
from dse.shared_kernel.errors import UpstreamForbiddenError, UpstreamUnavailableError
from dse.shared_kernel.symbol import Symbol

BROWSER_MIMICRY = ("mozilla", "chrome", "safari", "applewebkit", "gecko")
URL = "https://example.test"


def answering(status: int) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(status)))


async def test_the_page_client_sends_only_the_identity_it_was_given() -> None:
    client = DseHttpSource(URL, FakeClock(), user_agent="my-tool/9 (ops@example.test)")._client
    try:
        assert client.headers["user-agent"] == "my-tool/9 (ops@example.test)"
        for name in ("referer", "accept-language", "origin", "sec-fetch-mode"):
            assert name not in client.headers
        assert not any(w in v.lower() for v in client.headers.values() for w in BROWSER_MIMICRY)
    finally:
        await client.aclose()


async def test_a_403_is_reported_as_a_refusal_for_pages_and_snapshots() -> None:
    source = DseHttpSource(URL, FakeClock(), user_agent="x", client=answering(403), min_page_interval_s=0)
    with pytest.raises(UpstreamForbiddenError, match="refuses this client"):
        await source.company_page(Symbol("GP"))
    with pytest.raises(UpstreamForbiddenError, match="403"):
        await source.market_snapshot()


async def test_a_404_is_still_an_unknown_symbol_and_a_503_an_ordinary_failure() -> None:
    from dse.shared_kernel.errors import NotFoundError

    missing = DseHttpSource(URL, FakeClock(), user_agent="x", client=answering(404), min_page_interval_s=0)
    with pytest.raises(NotFoundError):
        await missing.company_page(Symbol("NOPE"))
    down = DseHttpSource(URL, FakeClock(), user_agent="x", client=answering(503), min_page_interval_s=0)
    with pytest.raises(UpstreamUnavailableError) as e:
        await down.market_snapshot()
    assert not isinstance(e.value, UpstreamForbiddenError)
