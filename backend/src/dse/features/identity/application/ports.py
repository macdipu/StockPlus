"""Security services the use cases depend on (core.security / Redis fulfil them)."""

from datetime import datetime
from typing import Protocol
from uuid import UUID

from dse.shared_kernel.principal import Role


class PasswordHasher(Protocol):
    def hash(self, password: str) -> str: ...

    def verify(self, password_hash: str, password: str) -> bool: ...

    def needs_rehash(self, password_hash: str) -> bool: ...


class AccessTokens(Protocol):
    def encode(self, user_id: UUID, role: Role) -> tuple[str, datetime]: ...


class LoginThrottle(Protocol):
    async def check(self, email: str) -> None:
        """Raises TooManyRequestsError while the email is locked out."""
        ...

    async def record_failure(self, email: str) -> None: ...

    async def reset(self, email: str) -> None: ...
