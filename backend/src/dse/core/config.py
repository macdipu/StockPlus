"""Typed, environment-driven settings. The only place that reads the environment."""

from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseModel):
    url: str = "postgresql+asyncpg://dse:dse@localhost:5433/dse"
    pool_size: int = 10
    echo: bool = False


class RedisSettings(BaseModel):
    url: str = "redis://localhost:6380/0"


class SecuritySettings(BaseModel):
    jwt_secret: SecretStr = Field(default=SecretStr("dev-only-insecure-secret"))
    access_token_minutes: int = 15
    refresh_token_days: int = 14


class UpstreamSettings(BaseModel):
    base_url: str = "https://www.dse.com.bd"
    timeout_s: float = 20.0
    min_page_interval_s: float = 2.5


class LiveSettings(BaseModel):
    poll_open_s: float = 10.0  # = upstream CDN max-age; faster only re-reads the cache
    poll_closed_s: float = 60.0
    min_poll_s: float = 5.0  # hard floor, whatever the env says
    stale_after_s: float = 300.0
    heartbeat_s: float = 15.0
    subscriber_queue: int = 256
    max_stream_symbols: int = 50


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DSE_", env_nested_delimiter="__", env_file=".env", extra="ignore"
    )

    env: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"
    api_prefix: str = "/api/v1"
    cors_origins: list[str] = ["http://localhost:3000"]
    database: DatabaseSettings = DatabaseSettings()
    redis: RedisSettings = RedisSettings()
    security: SecuritySettings = SecuritySettings()
    upstream: UpstreamSettings = UpstreamSettings()
    live: LiveSettings = LiveSettings()

    def assert_production_safe(self) -> None:
        """Fail fast instead of running production with development defaults."""
        if (
            self.env == "production"
            and self.security.jwt_secret.get_secret_value() == "dev-only-insecure-secret"
        ):
            raise RuntimeError("DSE_SECURITY__JWT_SECRET must be set in production")


@lru_cache
def get_settings() -> Settings:
    return Settings()
