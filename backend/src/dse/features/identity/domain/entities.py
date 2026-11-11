"""Identity domain: accounts and rotating refresh tokens. Pure Python (stdlib only)."""

import hashlib
import re
import secrets
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from uuid import UUID

from dse.shared_kernel.errors import ValidationFailedError
from dse.shared_kernel.principal import Role

_EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$")
MAX_EMAIL = 254
MAX_PASSWORD = 128  # argon2 handles long inputs, but unbounded input is a cheap denial-of-service


@dataclass(frozen=True, slots=True)
class Email:
    value: str

    def __post_init__(self) -> None:
        normalised = self.value.strip().lower()
        if len(normalised) > MAX_EMAIL or not _EMAIL.match(normalised):
            raise ValidationFailedError("Enter a valid email address.")
        object.__setattr__(self, "value", normalised)

    def __str__(self) -> str:
        return self.value


def validate_password(password: str, email: Email, min_length: int) -> None:
    """Length-first policy (NIST 800-63B): long enough, not absurdly long, not derived from the email."""
    if len(password) < min_length:
        raise ValidationFailedError(f"Password must be at least {min_length} characters.")
    if len(password) > MAX_PASSWORD:
        raise ValidationFailedError(f"Password must be at most {MAX_PASSWORD} characters.")
    local = email.value.split("@", 1)[0]
    if password.lower() in (email.value, local) or (local in password.lower() and len(local) >= 6):
        raise ValidationFailedError("Password must not contain your email address.")
    if len(set(password)) < 4:
        raise ValidationFailedError("Password is too repetitive.")


@dataclass(frozen=True, slots=True)
class User:
    id: UUID
    email: Email
    password_hash: str
    role: Role
    is_active: bool
    created_at: datetime


def new_refresh_secret() -> str:
    """256 bits from the OS CSPRNG. This is what the client holds; we store only its hash."""
    return secrets.token_urlsafe(32)


def hash_refresh_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class RefreshToken:
    """One link in a rotation chain (`family_id`). Each use revokes the link and issues the next."""

    id: UUID
    user_id: UUID
    family_id: UUID
    token_hash: str
    issued_at: datetime
    expires_at: datetime
    revoked_at: datetime | None = None
    replaced_by: UUID | None = None

    def is_expired(self, now: datetime) -> bool:
        return now >= self.expires_at

    def is_revoked(self) -> bool:
        return self.revoked_at is not None

    def recently_rotated(self, now: datetime, grace: timedelta) -> bool:
        """Revoked by a normal rotation a moment ago: a concurrent tab racing us, not a stolen token."""
        return self.revoked_at is not None and self.replaced_by is not None and now - self.revoked_at <= grace

    def revoked(self, now: datetime, replaced_by: UUID | None = None) -> "RefreshToken":
        return replace(self, revoked_at=now, replaced_by=replaced_by)
