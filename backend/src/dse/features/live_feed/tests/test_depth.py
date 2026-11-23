"""Market depth: DSE's response parsed, summed, cached and served."""

import json
from pathlib import Path
from typing import Any

import pytest

from dse.features.live_feed.application.use_cases import GetDepth
from dse.features.live_feed.domain.depth import DepthLevel, MarketDepth, side_totals, spread
from dse.features.live_feed.infrastructure.dse_depth import CachedDepthFeed, parse_depth
from dse.features.live_feed.tests.fakes import FakeClock
from dse.shared_kernel.errors import UpstreamUnavailableError
from dse.shared_kernel.symbol import Symbol

FIXTURE = Path(__file__).parent / "fixtures" / "depth_ENVOYTEX.json"


@pytest.fixture
def raw() -> dict[str, Any]:
    return dict(json.loads(FIXTURE.read_text()))


def test_parses_dses_real_response_with_asks_sorted_lowest_first(raw: dict[str, Any]) -> None:
    d = parse_depth(raw, "ENVOYTEX")
    assert d.symbol == "ENVOYTEX"
    assert d.bids == ()  # the fixture was taken after the close, with no buyers waiting
    assert [lv.price for lv in d.asks] == sorted(lv.price for lv in d.asks)
    assert d.asks[0] == DepthLevel(83.5, 3060, 1)
    assert d.as_of
    assert d.market_open is False
    assert d.stats["lastTrade"] == 83.2


def test_levels_are_ordered_and_malformed_ones_skipped() -> None:
    d = parse_depth(
        {
            "bids": [
                {"price": 10, "quantity": 5, "orders": 1},
                {"price": 12, "quantity": 3, "orders": 2},
                {"price": "x"},
            ],
            "asks": [{"price": 20, "quantity": 1, "orders": 1}, {"price": 15, "quantity": 2}],
        },
        "X",
    )
    assert [lv.price for lv in d.bids] == [12.0, 10.0]  # highest buyer first
    assert [lv.price for lv in d.asks] == [15.0, 20.0]  # lowest seller first
    assert d.asks[0].orders == 0


def test_a_changed_response_shape_is_an_upstream_error() -> None:
    with pytest.raises(UpstreamUnavailableError):
        parse_depth({"rows": []}, "X")


def test_totals_use_a_quantity_weighted_average_and_spread_needs_both_sides() -> None:
    levels = (DepthLevel(10, 100, 1), DepthLevel(20, 300, 2))
    t = side_totals(levels)
    assert (t.quantity, t.orders, t.average_price) == (400, 3, 17.5)
    assert side_totals(()).average_price is None
    assert spread((DepthLevel(9.5, 1, 1),), (DepthLevel(10, 1, 1),)) == 0.5
    assert spread((), (DepthLevel(10, 1, 1),)) is None


class CountingFeed:
    def __init__(self, depth: MarketDepth) -> None:
        self.depth, self.calls = depth, 0

    async def fetch(self, symbol: Symbol) -> MarketDepth:
        self.calls += 1
        return self.depth


class MemoryRedis:
    def __init__(self) -> None:
        self.data: dict[str, str] = {}
        self.ttls: dict[str, int | None] = {}

    async def get(self, key: str) -> str | None:
        return self.data.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> bool:
        self.data[key], self.ttls[key] = value, ex
        return True


async def test_the_cache_serves_repeat_requests_without_asking_dse_again(raw: dict[str, Any]) -> None:
    inner, redis = CountingFeed(parse_depth(raw, "ENVOYTEX")), MemoryRedis()
    feed = CachedDepthFeed(inner, redis, ttl_s=10)  # type: ignore[arg-type]
    first = await feed.fetch(Symbol("ENVOYTEX"))
    second = await feed.fetch(Symbol("ENVOYTEX"))
    assert inner.calls == 1
    assert second == first  # survives the round trip through the cache
    assert redis.ttls["depth:ENVOYTEX"] == 10


async def test_the_depth_use_case_sums_each_side_and_stamps_the_fetch_time(raw: dict[str, Any]) -> None:
    feed = CountingFeed(parse_depth(raw, "ENVOYTEX"))
    dto = await GetDepth(feed, FakeClock())(Symbol("ENVOYTEX"))
    assert dto.sellers.total_quantity == 3060 + 3000 + 1500
    assert dto.sellers.total_orders == 3
    assert dto.sellers.average_price == round((83.5 * 3060 + 88 * 3000 + 88.3 * 1500) / 7560, 2)
    assert dto.buyers.total_quantity == 0
    assert dto.buyers.average_price is None
    assert dto.spread is None
    assert dto.fetched_at.endswith("+00:00")
