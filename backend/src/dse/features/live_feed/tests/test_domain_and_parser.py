"""Domain rules (change detection, session close, poll policy) and the parser's legacy contract."""

from dataclasses import replace
from datetime import datetime, time
from typing import Any

import pytest

from dse.core.clock import DHAKA
from dse.features.live_feed.application.mappers import market_dto, quote_dto
from dse.features.live_feed.domain.entities import LiveSnapshot, PollPolicy, SessionState
from dse.features.live_feed.infrastructure.codec import (
    market_from_json,
    market_to_json,
    quote_from_json,
    quote_to_json,
)
from dse.features.live_feed.infrastructure.dse_snapshot import parse_live_snapshot
from dse.features.live_feed.tests.fakes import with_quote, with_trade_time
from dse.shared_kernel.errors import UpstreamUnavailableError

# ---------------------------------------------------------------- parser == legacy scraper.parse_snapshot


def test_parser_matches_legacy_quotes(snapshot: LiveSnapshot, legacy_golden: dict[str, Any]) -> None:
    assert len(snapshot.quotes) == legacy_golden["count"]
    assert snapshot.trade_time == legacy_golden["tradeTime"]
    renames = {"value": "value_mn", "assetType": "asset_type", "tradeTime": "trade_time"}
    for sym, legacy in legacy_golden["quotes"].items():
        ours = quote_dto(snapshot.quotes[sym], snapshot.trade_time).model_dump()
        for key, want in legacy.items():
            got = ours[renames.get(key, key)]
            assert got == pytest.approx(want) if isinstance(want, float) else got == want, (sym, key)


def test_parser_market_session_and_breadth(snapshot: LiveSnapshot, legacy_golden: dict[str, Any]) -> None:
    s = snapshot.session
    assert (s.is_open, s.trading_day, s.opening, s.closing) == (True, True, time(10), time(14))
    assert s.day is not None
    assert s.day.isoformat() == legacy_golden["session"]["date"]
    m = market_dto(snapshot.state)
    assert [i.key for i in m.indices] == [i["key"] for i in legacy_golden["indices"]]
    assert m.breadth == legacy_golden["breadth"]
    assert "tradeTime" not in m.totals
    assert m.totals["trades"] > 0
    assert m.session.closing == "14:00"


def test_parser_rejects_changed_shape() -> None:
    with pytest.raises(UpstreamUnavailableError):
        parse_live_snapshot({"market": {}})


def test_codec_round_trip(snapshot: LiveSnapshot) -> None:
    q = snapshot.quotes["ORIONINFU"]
    assert quote_from_json("ORIONINFU", quote_to_json(q)) == q
    assert market_from_json(market_to_json(snapshot.state)) == snapshot.state


# ---------------------------------------------------------------- change detection


def test_first_snapshot_announces_nothing(snapshot: LiveSnapshot) -> None:
    ch = snapshot.changes_since(None)
    assert ch.first
    assert not ch.any


def test_only_moved_quotes_are_changes(snapshot: LiveSnapshot) -> None:
    moved = with_quote(snapshot, "GP", ltp=999.0)
    noise = with_quote(snapshot, "BATBC", percent=42.0, category="Z")  # not a QUOTE_FIELD
    assert [q.symbol.value for q in moved.changes_since(snapshot).quotes] == ["GP"]
    assert not noise.changes_since(snapshot).any
    assert not snapshot.changes_since(snapshot).any


def test_new_instrument_and_trade_time_are_changes(snapshot: LiveSnapshot) -> None:
    fewer = replace(snapshot, quotes={k: v for k, v in snapshot.quotes.items() if k != "GP"})
    assert [q.symbol.value for q in snapshot.changes_since(fewer).quotes] == ["GP"]
    later = with_trade_time(snapshot, "Nov 11, 2026 at 11:41 AM")
    ch = later.changes_since(snapshot)
    assert ch.market_changed
    assert not ch.quotes


# ---------------------------------------------------------------- session / policy

AT = datetime(2026, 11, 11, 14, 5, tzinfo=DHAKA)


@pytest.mark.parametrize(
    ("session", "now", "expected"),
    [
        (SessionState(AT.date(), False, True, "closed", time(10), time(14)), AT, True),
        (SessionState(AT.date(), True, True, "open", time(10), time(14)), AT, False),  # still open
        (
            SessionState(AT.date(), False, True, "pre", time(10), time(14)),
            AT.replace(hour=9),
            False,
        ),  # pre-open
        (SessionState(AT.date(), False, False, None, time(10), time(14)), AT, False),  # holiday
        (SessionState(AT.date(), False, True, None, time(10), None), AT, False),  # closing time unknown
        (
            SessionState(AT.date().replace(day=10), False, True, None, time(10), time(14)),
            AT,
            False,
        ),  # stale day
    ],
)
def test_after_close(session: SessionState, now: datetime, expected: bool) -> None:
    assert session.is_after_close(now) is expected


def test_poll_policy() -> None:
    p = PollPolicy(open_s=10, closed_s=60, floor_s=5)
    open_, closed = SessionState(None, True, True), SessionState(None, False, True)
    assert (p.interval(None), p.interval(open_), p.interval(closed)) == (10, 10, 60)
    assert PollPolicy(open_s=1, floor_s=5).interval(open_) == 5  # env cannot hammer upstream
    backoffs = [0.0]
    for _ in range(7):
        backoffs.append(p.next_backoff(backoffs[-1]))
    assert backoffs == [0, 5, 10, 20, 40, 80, 120, 120]
