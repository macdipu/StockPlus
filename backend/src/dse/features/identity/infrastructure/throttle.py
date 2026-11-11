"""Per-email failed-login throttle on Redis: a fixed window that starts at the first failure."""

import hashlib
from typing import cast

from redis.asyncio import Redis

from dse.shared_kernel.errors import TooManyRequestsError


class RedisLoginThrottle:
    def __init__(self, redis: "Redis", max_failures: int, window_s: int) -> None:
        self._r, self._max, self._window = redis, max_failures, window_s

    @staticmethod
    def _key(email: str) -> str:
        # hash the email so no address sits in Redis keys / MONITOR output
        return "auth:fail:" + hashlib.sha256(email.encode()).hexdigest()[:32]

    async def check(self, email: str) -> None:
        key = self._key(email)
        raw = cast(str | None, await self._r.get(key))
        if raw is not None and int(raw) >= self._max:
            ttl = int(await self._r.ttl(key))
            raise TooManyRequestsError(
                "Too many failed sign-in attempts. Try again later.", retry_after_s=max(ttl, 1)
            )

    async def record_failure(self, email: str) -> None:
        key = self._key(email)
        async with self._r.pipeline(transaction=True) as p:
            p.incr(key)
            p.expire(key, self._window, nx=True)  # the window starts at the first failure and never slides
            await p.execute()

    async def reset(self, email: str) -> None:
        await self._r.delete(self._key(email))
