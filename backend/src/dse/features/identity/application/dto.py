"""Application-boundary DTOs."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class UserDto(BaseModel):
    id: UUID
    email: str
    role: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class IssuedSession:
    """What a successful login/refresh yields. The refresh secret is handed to the HTTP layer exactly once
    (to become an HttpOnly cookie) and is never stored or logged in clear."""

    access_token: str
    access_expires_at: datetime
    refresh_secret: str
    refresh_expires_at: datetime
    user: UserDto
