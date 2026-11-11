"""Redis client factory (one pool per process)."""

from redis.asyncio import Redis

from dse.core.config import RedisSettings


def create_redis(settings: RedisSettings) -> "Redis":
    return Redis.from_url(settings.url, decode_responses=True)
