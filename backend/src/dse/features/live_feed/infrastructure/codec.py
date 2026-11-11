"""JSON (de)serialisation of live-feed entities for the Redis read model. Compact, versioned by key prefix."""

import dataclasses
import json
from datetime import date, time
from typing import Any

from dse.features.live_feed.application.dto import FeedCounters
from dse.features.live_feed.domain.entities import (
    IndexLevel,
    LiveQuote,
    MarketState,
    MarketSummary,
    SessionState,
)
from dse.shared_kernel.symbol import Symbol

_QUOTE_FIELDS = [f.name for f in dataclasses.fields(LiveQuote) if f.name != "symbol"]


def dumps(obj: Any) -> str:
    return json.dumps(obj, separators=(",", ":"), default=str)


def quote_to_json(q: LiveQuote) -> str:
    return dumps([getattr(q, f) for f in _QUOTE_FIELDS])


def quote_from_json(symbol: str, raw: str) -> LiveQuote:
    return LiveQuote(Symbol(symbol), **dict(zip(_QUOTE_FIELDS, json.loads(raw), strict=True)))


def market_to_json(m: MarketState) -> str:
    s = m.session
    return dumps(
        {
            "session": {
                "day": s.day.isoformat() if s.day else None,
                "is_open": s.is_open,
                "trading_day": s.trading_day,
                "phase": s.phase,
                "opening": s.opening.isoformat() if s.opening else None,
                "closing": s.closing.isoformat() if s.closing else None,
            },
            "trade_time": m.trade_time,
            "indices": [dataclasses.astuple(i) for i in m.summary.indices],
            "totals": dict(m.summary.totals),
            "breadth": dict(m.summary.breadth),
            "movers": dict(m.summary.movers),
        }
    )


def market_from_json(raw: str) -> MarketState:
    d = json.loads(raw)
    s = d["session"]
    session = SessionState(
        day=date.fromisoformat(s["day"]) if s["day"] else None,
        is_open=s["is_open"],
        trading_day=s["trading_day"],
        phase=s["phase"],
        opening=time.fromisoformat(s["opening"]) if s["opening"] else None,
        closing=time.fromisoformat(s["closing"]) if s["closing"] else None,
    )
    summary = MarketSummary(
        indices=tuple(IndexLevel(*i) for i in d["indices"]),
        totals=d["totals"],
        breadth=d["breadth"],
        movers=d["movers"],
    )
    return MarketState(session, d["trade_time"], summary)


def counters_to_json(c: FeedCounters) -> str:
    return dumps(dataclasses.asdict(c))


def counters_from_json(raw: str) -> FeedCounters:
    known = {f.name for f in dataclasses.fields(FeedCounters)}
    return FeedCounters(**{k: v for k, v in json.loads(raw).items() if k in known})
