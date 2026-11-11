"""Who is calling. Pure value objects shared by every feature that has user-owned data."""

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class Role(StrEnum):
    USER = "user"
    ADMIN = "admin"


@dataclass(frozen=True, slots=True)
class Principal:
    """The authenticated caller, as proven by a valid access token."""

    user_id: UUID
    role: Role

    @property
    def is_admin(self) -> bool:
        return self.role is Role.ADMIN
