"""Dependency providers for identity: use cases built from process-wide resources on app.state."""

from dataclasses import dataclass
from datetime import timedelta

from fastapi import Request

from dse.core.config import SecuritySettings
from dse.core.db import Database
from dse.features.identity.application.ports import AccessTokens, LoginThrottle, PasswordHasher
from dse.features.identity.application.use_cases import (
    GetCurrentUser,
    Login,
    Logout,
    PromoteUser,
    Refresh,
    Register,
)
from dse.features.identity.domain.ports import IdentityUnitOfWork
from dse.features.identity.infrastructure.repositories import SqlIdentityUnitOfWork
from dse.shared_kernel.clock import Clock


@dataclass(frozen=True)
class IdentityContainer:
    db: Database
    hasher: PasswordHasher
    throttle: LoginThrottle
    tokens: AccessTokens
    clock: Clock
    settings: SecuritySettings
    cookie_secure: bool
    cookie_path: str

    def uow(self) -> IdentityUnitOfWork:
        return SqlIdentityUnitOfWork(self.db.sessions)

    @property
    def _refresh_ttl(self) -> timedelta:
        return timedelta(days=self.settings.refresh_token_days)

    @property
    def register(self) -> Register:
        return Register(self.uow, self.hasher, self.clock, self.settings.min_password_length)

    @property
    def login(self) -> Login:
        return Login(self.uow, self.hasher, self.throttle, self.tokens, self.clock, self._refresh_ttl)

    @property
    def refresh(self) -> Refresh:
        return Refresh(
            self.uow, self.tokens, self.clock, self._refresh_ttl, self.settings.refresh_reuse_grace_s
        )

    @property
    def logout(self) -> Logout:
        return Logout(self.uow, self.clock)

    @property
    def current_user(self) -> GetCurrentUser:
        return GetCurrentUser(self.uow)

    @property
    def promote(self) -> PromoteUser:
        return PromoteUser(self.uow, self.clock)


def container(request: Request) -> IdentityContainer:
    c: IdentityContainer = request.app.state.identity
    return c
