"""SQLAlchemy implementations of the identity ports, and the Unit of Work exposing them."""

from datetime import datetime
from typing import Self
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from dse.core.db import SqlAlchemyUnitOfWork
from dse.features.identity.domain.entities import Email, RefreshToken, User
from dse.features.identity.infrastructure.orm import RefreshTokenRow, UserRow
from dse.shared_kernel.errors import ConflictError
from dse.shared_kernel.principal import Role


def _user(r: UserRow) -> User:
    return User(r.id, Email(r.email), r.password_hash, r.role, r.is_active, r.created_at)


def _token(r: RefreshTokenRow) -> RefreshToken:
    return RefreshToken(
        r.id, r.user_id, r.family_id, r.token_hash, r.issued_at, r.expires_at, r.revoked_at, r.replaced_by
    )


class SqlUserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get(self, user_id: UUID) -> User | None:
        r = await self._s.get(UserRow, user_id)
        return _user(r) if r else None

    async def get_by_email(self, email: Email) -> User | None:
        r = await self._s.scalar(select(UserRow).where(UserRow.email == email.value))
        return _user(r) if r else None

    async def add(self, user: User) -> None:
        self._s.add(
            UserRow(
                id=user.id,
                email=user.email.value,
                password_hash=user.password_hash,
                role=user.role,
                is_active=user.is_active,
            )
        )
        try:
            await self._s.flush()  # surface the unique-email race here, not at commit
        except IntegrityError as e:
            await self._s.rollback()
            raise ConflictError("An account with this email already exists.") from e

    async def update_password_hash(self, user_id: UUID, password_hash: str) -> None:
        await self._s.execute(
            update(UserRow).where(UserRow.id == user_id).values(password_hash=password_hash)
        )

    async def set_role(self, user_id: UUID, role: str) -> None:
        await self._s.execute(update(UserRow).where(UserRow.id == user_id).values(role=Role(role)))


class SqlRefreshTokenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def add(self, token: RefreshToken) -> None:
        self._s.add(
            RefreshTokenRow(
                id=token.id,
                user_id=token.user_id,
                family_id=token.family_id,
                token_hash=token.token_hash,
                issued_at=token.issued_at,
                expires_at=token.expires_at,
            )
        )
        await self._s.flush()

    async def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        r = await self._s.scalar(select(RefreshTokenRow).where(RefreshTokenRow.token_hash == token_hash))
        return _token(r) if r else None

    async def mark_rotated(self, token_id: UUID, at: datetime, replaced_by: UUID) -> None:
        await self._s.execute(
            update(RefreshTokenRow)
            .where(RefreshTokenRow.id == token_id)
            .values(revoked_at=at, replaced_by=replaced_by)
        )

    async def revoke_family(self, family_id: UUID, at: datetime) -> int:
        res = await self._s.execute(
            update(RefreshTokenRow)
            .where(RefreshTokenRow.family_id == family_id, RefreshTokenRow.revoked_at.is_(None))
            .values(revoked_at=at)
        )
        return int(getattr(res, "rowcount", 0) or 0)

    async def revoke_all_for_user(self, user_id: UUID, at: datetime) -> int:
        res = await self._s.execute(
            update(RefreshTokenRow)
            .where(RefreshTokenRow.user_id == user_id, RefreshTokenRow.revoked_at.is_(None))
            .values(revoked_at=at)
        )
        return int(getattr(res, "rowcount", 0) or 0)


class SqlIdentityUnitOfWork(SqlAlchemyUnitOfWork):
    users: SqlUserRepository
    refresh_tokens: SqlRefreshTokenRepository

    async def __aenter__(self) -> Self:
        await super().__aenter__()
        self.users = SqlUserRepository(self.session)
        self.refresh_tokens = SqlRefreshTokenRepository(self.session)
        return self
