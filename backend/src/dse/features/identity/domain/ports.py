"""Repositories the identity application needs. Implemented in infrastructure; faked in tests."""

from datetime import datetime
from types import TracebackType
from typing import Protocol
from uuid import UUID

from dse.features.identity.domain.entities import Email, RefreshToken, User


class UserRepository(Protocol):
    async def get(self, user_id: UUID) -> User | None: ...

    async def get_by_email(self, email: Email) -> User | None: ...

    async def add(self, user: User) -> None:
        """Raises ConflictError when the email is already registered (also under a concurrent race)."""
        ...

    async def update_password_hash(self, user_id: UUID, password_hash: str) -> None: ...

    async def set_role(self, user_id: UUID, role: str) -> None: ...


class RefreshTokenRepository(Protocol):
    async def add(self, token: RefreshToken) -> None: ...

    async def get_by_hash(self, token_hash: str) -> RefreshToken | None: ...

    async def mark_rotated(self, token_id: UUID, at: datetime, replaced_by: UUID) -> None: ...

    async def revoke_family(self, family_id: UUID, at: datetime) -> int: ...

    async def revoke_all_for_user(self, user_id: UUID, at: datetime) -> int: ...


class IdentityUnitOfWork(Protocol):
    @property
    def users(self) -> UserRepository: ...

    @property
    def refresh_tokens(self) -> RefreshTokenRepository: ...

    async def __aenter__(self) -> "IdentityUnitOfWork": ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None: ...

    async def commit(self) -> None: ...
