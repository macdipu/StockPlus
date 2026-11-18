"""Redis cache for computed charts (JSON values, expiring)."""

import json
from typing import Any

from redis.asyncio import Redis


class RedisChartCache:
    def __init__(self, redis: "Redis") -> None:
        self._r = redis

    async def get(self, key: str) -> dict[str, Any] | None:
        raw = await self._r.get(key)
        if raw is None:
            return None
        value = json.loads(raw)
        return value if isinstance(value, dict) else None

    async def put(self, key: str, value: dict[str, Any], ttl_s: int) -> None:
        await self._r.set(key, json.dumps(value, separators=(",", ":")), ex=ttl_s)
