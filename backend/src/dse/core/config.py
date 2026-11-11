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


DEV_JWT_SECRET = "dev-only-insecure-secret-do-not-use-in-production-0123456789"  # noqa: S105 — public on purpose; production refuses it
MIN_PRODUCTION_SECRET_BYTES = 32


class SecuritySettings(BaseModel):
    jwt_secret: SecretStr = Field(default=SecretStr(DEV_JWT_SECRET))
    access_token_minutes: int = 15
    refresh_token_days: int = 14
    issuer: str = "dse-analyzer"
    refresh_cookie_name: str = "dse_refresh"
    cookie_secure: bool | None = None  # None → Secure in production, off for http://localhost dev
    max_failed_logins: int = 5  # per email within `lockout_minutes`
    lockout_minutes: int = 15
    refresh_reuse_grace_s: int = 10  # a just-rotated token replayed within this window is a race, not theft
    min_password_length: int = 10


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

    @property
    def cookie_secure(self) -> bool:
        return (
            self.env == "production" if self.security.cookie_secure is None else self.security.cookie_secure
        )

    def assert_production_safe(self) -> None:
        """Fail fast instead of running production with development defaults."""
        if self.env != "production":
            return
        secret = self.security.jwt_secret.get_secret_value()
        if secret == DEV_JWT_SECRET or secret == "dev-only-insecure-secret":  # noqa: S105
            raise RuntimeError("DSE_SECURITY__JWT_SECRET must be set in production")
        if len(secret.encode()) < MIN_PRODUCTION_SECRET_BYTES:
            raise RuntimeError(
                f"DSE_SECURITY__JWT_SECRET must be at least {MIN_PRODUCTION_SECRET_BYTES} bytes"
            )


@lru_cache
def get_settings() -> Settings:
    return Settings()
