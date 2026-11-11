"""Redis-backed published universe (CQRS read model).

Keys:  scanner:universe          STRING  JSON {version, built_at_ms, ..., live_rows, last_close_rows}
       scanner:universe:version  STRING  the version inside the payload (cheap to poll)
       scanner:universe:seq      INT     monotonically increasing version source
Payload and version are replaced in one MULTI/EXEC, so a reader never sees a half-published universe.
"""

import json
from datetime import date
from typing import Any, cast

from redis.asyncio import Redis

from dse.features.scanner.application.ports import StoredUniverse

PAYLOAD, VERSION, SEQ = "scanner:universe", "scanner:universe:version", "scanner:universe:seq"


class RedisUniverseStore:
    def __init__(self, redis: "Redis") -> None:
        self._r = redis

    async def version(self) -> int | None:
        raw = cast(str | None, await self._r.get(VERSION))
        return int(raw) if raw is not None else None

    async def load(self) -> StoredUniverse | None:
        raw = cast(str | None, await self._r.get(PAYLOAD))
        if raw is None:
            return None
        d: dict[str, Any] = json.loads(raw)
        return StoredUniverse(
            version=d["version"],
            built_at_ms=d["built_at_ms"],
            build_ms=d["build_ms"],
            session_day=date.fromisoformat(d["session_day"]) if d["session_day"] else None,
            trade_time=d["trade_time"],
            live_rows=d["live_rows"],
            last_close_rows=d["last_close_rows"],
            errors=d["errors"],
        )

    async def save(self, universe: StoredUniverse) -> int:
        version = int(await self._r.incr(SEQ))
        payload = json.dumps(
            {
                "version": version,
                "built_at_ms": universe.built_at_ms,
                "build_ms": universe.build_ms,
                "session_day": universe.session_day.isoformat() if universe.session_day else None,
                "trade_time": universe.trade_time,
                "live_rows": universe.live_rows,
                "last_close_rows": universe.last_close_rows,
                "errors": universe.errors,
            },
            separators=(",", ":"),
            default=str,
        )
        async with self._r.pipeline(transaction=True) as p:
            p.set(PAYLOAD, payload)
            p.set(VERSION, version)
            await p.execute()
        return version
