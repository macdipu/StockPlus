"""ORM models. `owner_id` references users.id (same database; the `users` table is owned by identity, so the
FK is declared by name only: no import of another feature)."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from dse.core.db import Base


class _Owned:
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    owner_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(60))
    name_key: Mapped[str] = mapped_column(String(60))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WatchlistRow(_Owned, Base):
    __tablename__ = "watchlists"
    symbols: Mapped[list[str]] = mapped_column(ARRAY(String(24)), default=list)
    __table_args__ = (UniqueConstraint("owner_id", "name_key", name="uq_watchlists_owner_name"),)


class SavedScanRow(_Owned, Base):
    __tablename__ = "saved_scans"
    definition: Mapped[dict[str, Any]] = mapped_column(JSONB)
    __table_args__ = (UniqueConstraint("owner_id", "name_key", name="uq_saved_scans_owner_name"),)
